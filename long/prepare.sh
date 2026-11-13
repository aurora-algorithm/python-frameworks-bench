#!/bin/bash
# Inside the rig, once per session (safe to re-run): the Python venv, the bench database, Postgres pinned to its
# cores, the monitoring stack, and a check that every server answers the same way.
set -euo pipefail
cd "$(dirname "$0")"
source cores.sh
export DATABASE_URL=${DATABASE_URL:-postgres://dev:dev@127.0.0.1/bench}
[ -x .venv/bin/python ] || uv venv -q -p 3.14.8 .venv
VIRTUAL_ENV=.venv uv pip install -q -r requirements.txt
if ! psql "$DATABASE_URL" -tAc 'select 1' >/dev/null 2>&1; then
  psql -d postgres -qc "ALTER ROLE dev PASSWORD 'dev'"
  createdb bench
  psql -q bench -f schema.sql
fi
for p in $(pgrep -x postgres); do sudo taskset -apc "$POSTGRES_CORES" "$p" >/dev/null; done
MONITOR_CORE=$MONITOR_CORES monitoring/up.sh
python3 verify.py
{ echo "python $(.venv/bin/python -c 'import platform; print(platform.python_version())')"
  VIRTUAL_ENV=.venv uv pip freeze | grep -iE '^(fastapi|starlette|pydantic|pydantic-core|uvicorn|uvloop|httptools|litestar|msgspec|flask|werkzeug|django|djangorestframework|gunicorn|psycopg|psycopg-binary|psycopg-pool|py-spy)=='
  .venv/bin/python -c 'import psycopg; print("psycopg implementation", psycopg.pq.__impl__)'
  oha --version
  psql "$DATABASE_URL" -tAc 'show server_version' | sed 's/^/postgres /'
  echo "cores: server $SERVER_CORES, oha $OHA_CORES, postgres $POSTGRES_CORES, monitoring $MONITOR_CORES"
} > results/versions.txt
cat results/versions.txt
