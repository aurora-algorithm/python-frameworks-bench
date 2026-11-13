#!/bin/bash
# Starts one server exactly as the measured runs do (same command, same core) and waits until it answers.
# usage: serve.sh <server> [route]    e.g. ./serve.sh fastapi    (stop it with: ./serve.sh stop)
set -euo pipefail
cd "$(dirname "$0")"
source servers.sh
source cores.sh
export DATABASE_URL=${DATABASE_URL:-postgres://dev:dev@127.0.0.1/bench}
name=$1
route=${2:-users}
if [ "$name" = stop ]; then
  pkill -f 'pybench/\.venv' || true
  exit 0
fi
port=$(port_of "$name")
path=/$route
[ "$route" = users-post ] && path=/users
setsid taskset -c "$(cores_of "$name")" bash -c "$(server_cmd "$name" "$route")" >"/tmp/serve-$name.log" 2>&1 &
for _ in $(seq 150); do
  if curl -sf -o /dev/null "http://127.0.0.1:$port$path"; then
    echo "$name is listening on port $port, on core $(cores_of "$name")"
    exit 0
  fi
  sleep 0.1
done
echo "$name did not start; see /tmp/serve-$name.log" >&2
exit 1
