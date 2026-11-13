#!/bin/bash
# One measured run inside the rig: start the server on its core(s), warm up 10 s, load it 20 s with 64 connections,
# then store oha's summary and per-request log summary plus what Prometheus recorded during those 20 s.
# usage: run_one.sh <server> <route: users|users-post|users-db> <run>
set -euo pipefail
cd "$(dirname "$0")"
source servers.sh
source cores.sh
name=$1; route=$2; run=$3
DURATION=20
WARMUP=10
CONNECTIONS=${CONNECTIONS:-64}
export DATABASE_URL=${DATABASE_URL:-postgres://dev:dev@127.0.0.1/bench}
port=$(port_of "$name")
req=(-m GET)
path=/${route%-post}
if [ "$route" = users-post ]; then
  req=(-m POST -H "content-type: application/json" -d '{"name":"Ada","email":"ada@example.com","age":36}')
fi
mkdir -p results
work=$(mktemp -d)
cmd=$(server_cmd "$name" "$route")
exporter=
if [ "$run" = demo ]; then
  # The video's live requests-per-second panel counts the server's access log; demo runs are never quoted as numbers.
  cmd=${cmd//--no-access-log/--access-log}
  : > "$work/server.log"
  setsid taskset -c "${MONITOR_CORE:-0-1}" python3 monitoring/requests_exporter.py "$work/server.log" 9257 >/dev/null 2>&1 & exporter=$!
fi
setsid taskset -c "$(cores_of "$name")" bash -c "$cmd" >> "$work/server.log" 2>&1 & pid=$!
# A server that hasn't stopped 10 s after the signal is killed, so one stuck shutdown can't hang the session.
stop() {
  kill -- -"$pid" 2>/dev/null || true
  for _ in $(seq 100); do kill -0 "$pid" 2>/dev/null || break; sleep 0.1; done
  if kill -0 "$pid" 2>/dev/null; then
    echo "run_one: $name did not stop within 10 s, killing it" >&2
    kill -KILL -- -"$pid" 2>/dev/null || true
  fi
  wait "$pid" 2>/dev/null || true
  [ -z "$exporter" ] || kill "$exporter" 2>/dev/null || true
  rm -rf "$work"
}
trap stop EXIT
ready=0
for _ in $(seq 150); do curl -sf -o /dev/null "http://127.0.0.1:$port$path" && { ready=1; break; }; sleep 0.1; done
[ "$ready" = 1 ] || { echo "run_one: $name not ready on :$port$path after 15 s" >&2; tail -20 "$work/server.log" >&2; exit 1; }
url="http://127.0.0.1:$port$path"
taskset -c "$OHA_CORES" oha -z ${WARMUP}s -c $CONNECTIONS "${req[@]}" --no-tui --output-format quiet "$url" >/dev/null
start=$(date +%s.%N)
grep '^cpu[0-9]' /proc/stat > "$work/stat-start"
# The window ends when the load does, not when oha exits: oha writes its per-request log after the 20 s.
(sleep $DURATION; grep '^cpu[0-9]' /proc/stat > "$work/stat-end") & sampler=$!
taskset -c "$OHA_CORES" oha -z ${DURATION}s -c $CONNECTIONS "${req[@]}" --no-tui --output-format json \
  --db-url "$work/requests.db" "$url" > "$work/summary.json" 2>/dev/null
wait $sampler
end=$(python3 -c "print($start + $DURATION)")
echo "$(cores_of "$name")" > "$work/cores"
sleep 2 # let Prometheus take its last scrape of this run
python3 summarize_run.py "$work" "$DURATION" "$start" "$end" "$name" "$route" "results/${name}_${route}_run${run}.json"
