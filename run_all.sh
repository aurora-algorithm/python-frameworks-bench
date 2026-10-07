#!/bin/bash
# Measures FastAPI (returning dicts, and with declared response types), Litestar, Flask and Django on three
# routes, 5 alternating runs each.
# usage: ./run_all.sh     (RESUME=1 keeps finished runs)
set -euo pipefail
export DATABASE_URL="${DATABASE_URL:-postgresql://$USER@localhost:5432/bench}"
QUIET_PCT=170     # max background CPU (sum of %) before a run starts
DISTURBED_PCT=190 # a run averaging more background CPU than this is discarded and redone
ATTEMPTS=8
# Every server runs 4 worker processes: the ASGI apps on uvicorn, the WSGI apps on gunicorn with 16 threads each.
WORKERS=4
THREADS=16
BIN=.venv/bin

uv sync --frozen --quiet
mkdir -p results
[ "${RESUME:-0}" = 1 ] || rm -f results/*.json
{ $BIN/python --version
  $BIN/python -c "from importlib.metadata import version as v
for p in ['fastapi', 'litestar', 'flask', 'django', 'djangorestframework', 'uvicorn', 'uvloop', 'httptools',
          'gunicorn', 'pydantic', 'msgspec', 'psycopg', 'psycopg-pool']: print(p, v(p))"
  oha --version; psql "$DATABASE_URL" -tAc 'show server_version' | sed 's/^/postgres /'; } > results/versions.txt

ASGI="exec $BIN/uvicorn --workers $WORKERS --log-level warning --no-access-log"
WSGI="exec $BIN/gunicorn -w $WORKERS -k gthread --threads $THREADS --log-level warning"
FASTAPI="$ASGI --port 8301 apps.fastapi_app:app"
FASTAPI_TYPED="$ASGI --port 8305 apps.fastapi_typed:app"
LITESTAR="$ASGI --port 8302 apps.litestar_app:app"
FLASK="$WSGI -b 127.0.0.1:8303 apps.flask_app:app"
DJANGO="$WSGI -b 127.0.0.1:8304 apps.django_app:application"

background_cpu() {
  ps -axo %cpu=,comm= | awk '/postgres|oha|awk|ps$|perl|python3/ { next } { s += $1 } END { printf "%.0f", s }'
}

wait_quiet() {
  local calm=0
  while [ "$calm" -lt 5 ]; do
    if [ "$(background_cpu)" -le "$QUIET_PCT" ]; then calm=$((calm + 1)); else calm=0; fi
    sleep 1
  done
}

measure() { # name command port path run [POST]
  local route=${4#/}; [ "${6:-GET}" = POST ] && route="$route-post"
  [ -f "results/$1_${route}_run$5.json" ] && return 0
  for attempt in $(seq 1 $ATTEMPTS); do
    wait_quiet
    ./load.sh "$1" "$2" "$3" "$4" "$5" "${6:-GET}"
    local bg; bg=$(python3 -c "import json;print(json.load(open('results/$1_${route}_mem_run$5.json'))['bg_cpu_pct'])")
    if [ "$bg" -le "$DISTURBED_PCT" ]; then return 0; fi
    echo "  $1 $4 run $5 disturbed (background ${bg}%), retry $attempt" >&2
  done
  echo "  $1 $4 run $5 kept despite background load" >&2
}

for run in 1 2 3 4 5; do
  for test in "/users GET" "/users POST" "/users-db GET"; do
    set -- $test
    measure fastapi  "$FASTAPI"  8301 "$1" "$run" "$2"
    measure fastapi-typed "$FASTAPI_TYPED" 8305 "$1" "$run" "$2"
    measure litestar "$LITESTAR" 8302 "$1" "$run" "$2"
    measure flask    "$FLASK"    8303 "$1" "$run" "$2"
    measure django   "$DJANGO"   8304 "$1" "$run" "$2"
  done
  echo "run $run done"
done
