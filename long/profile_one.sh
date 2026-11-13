#!/bin/bash
# A CPU profile of one server under load (separate from the measured runs): the server on its core, oha warming
# it up for 10 s, then py-spy sampling every Python thread for 15 s while the load continues. py-spy runs on the
# spare core, and with --nonblocking it never pauses the server to read its stacks.
# usage: profile_one.sh <server> [route]   -> profiles/<server>_<route>.speedscope.json
set -euo pipefail
cd "$(dirname "$0")"
source servers.sh
source cores.sh
name=$1; route=${2:-users}
export DATABASE_URL=${DATABASE_URL:-postgres://dev:dev@127.0.0.1/bench}
port=$(port_of "$name")
mkdir -p profiles
setsid taskset -c "$(cores_of "$name")" bash -c "$(server_cmd "$name" "$route")" > /tmp/profile-server.log 2>&1 & pid=$!
trap 'kill -- -"$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true' EXIT
for _ in $(seq 150); do curl -sf -o /dev/null "http://127.0.0.1:$port/users" && break; sleep 0.1; done
taskset -c "$OHA_CORES" oha -z 27s -c 64 --no-tui --output-format quiet "http://127.0.0.1:$port/${route}" & load=$!
sleep 10
sudo taskset -c 9 .venv/bin/py-spy record --pid "$pid" --subprocesses --nonblocking --nolineno --rate 1000 --duration 15 \
  --format speedscope -o "profiles/${name}_${route}.speedscope.json" >/dev/null
# Only the load: a bare `wait` would also wait for the server, which only the exit trap stops.
wait "$load"
