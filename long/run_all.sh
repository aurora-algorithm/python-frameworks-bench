#!/bin/bash
# The full session, run from the Mac: every configuration 5 times, in a new random order each round, inside the rig.
# A follow-up check runs only the configurations given in CHECK (e.g. CHECK="flask users,django users")
# as runs named check<round>, in their own random order; it never touches the main session's runs.
# Before each run the Mac must be quiet (background CPU outside the Docker VM); a run during which the background
# averaged too much is thrown away and measured again. RESUME=1 keeps finished runs.
set -euo pipefail
cd "$(dirname "$0")"
QUIET_PCT=${QUIET_PCT:-150}       # summed %CPU of Mac processes outside the VM; this Mac idles around 100
DISTURBED_PCT=${DISTURBED_PCT:-180}
ATTEMPTS=8
ROUNDS=5
CONFIGS=(
  # Test 1: returning 50 users as JSON, on the server each framework's docs recommend; FastAPI as in its tutorial
  # and with return types.
  "flask users" "django users" "fastapi users" "fastapi-typed users" "litestar users"
  # Test 2: validating a new user.
  "flask users-post" "django users-post" "fastapi-typed users-post" "litestar users-post"
  # Test 3: reading 50 rows from Postgres. Flask with one sync worker, then the sync frameworks with eight gthread
  # threads, and the async ones with their pool of eight.
  "flask-w1 users-db" "flask-t8 users-db" "django-t8 users-db" "fastapi-typed users-db" "litestar users-db"
)
if [ -n "${CHECK:-}" ]; then
  IFS=',' read -r -a CONFIGS <<< "$CHECK"
fi
# Check runs are stored as results/<server>_<route>_runcheck<round>.json, with their own shuffle seeds.
# SESSION_PREFIX="" makes a CHECK run a full re-measurement under the normal run names (old runs moved aside first).
PREFIX=${SESSION_PREFIX-${CHECK:+check}}
SEED_BASE=${CHECK:+1000}
SEED_BASE=${SEED_BASE:-0}
rig() { docker exec -u dev longs-rig bash -lc "cd ~/pybench && $1"; }

background_cpu() {
  ps -axo %cpu=,comm= | awk '/com\.docker|Docker\.app|ps$|awk$/ { next } { s += $1 } END { printf "%.0f", s }'
}
wait_quiet() {
  local calm=0
  while [ "$calm" -lt 5 ]; do
    if [ "$(background_cpu)" -le "$QUIET_PCT" ]; then calm=$((calm + 1)); else calm=0; fi
    sleep 1
  done
}

measure() { # server route round
  local out="results/$1_$2_run${PREFIX}$3.json"
  if rig "test -f $out"; then return 0; fi
  for attempt in $(seq 1 $ATTEMPTS); do
    wait_quiet
    ( while true; do background_cpu; echo; sleep 1; done ) > "$tmp/bg.txt" &
    local sampler=$!
    rig "./run_one.sh $1 $2 ${PREFIX}$3"
    kill $sampler; wait $sampler 2>/dev/null || true
    local bg; bg=$(awk 'NF { s += $1; n++ } END { printf "%.0f", s / n }' "$tmp/bg.txt")
    if [ "$bg" -le "$DISTURBED_PCT" ]; then
      rig "python3 -c \"import json; p='$out'; d=json.load(open(p)); d['mac_background_cpu_pct']=$bg; d['attempt']=$attempt; json.dump(d, open(p, 'w'))\""
      return 0
    fi
    echo "  $1 $2 run $3 disturbed (Mac background ${bg}%), retry $attempt" >&2
    rig "rm -f $out"
  done
  echo "  $1 $2 run $3 still disturbed after $ATTEMPTS attempts; stopping the session" >&2
  exit 1
}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
if [ -z "${CHECK:-}" ]; then
  [ "${RESUME:-0}" = 1 ] || rig "rm -f results/*_run*.json"
  rig "mkdir -p results && ./prepare.sh"
fi
for round in $(seq 1 $ROUNDS); do
  order=$(printf '%s\n' "${CONFIGS[@]}" | python3 -c "import random, sys; lines = sys.stdin.read().splitlines(); random.Random($((SEED_BASE + round))).shuffle(lines); print('\n'.join(lines))")
  rig "echo \"${PREFIX}round $round: $(echo "$order" | tr '\n' ',')\" >> results/order.txt"
  while read -r server route; do
    measure "$server" "$route" "$round"
  done <<< "$order"
  echo "round $round done"
done
