#!/bin/bash
# The servers under test: name -> port, cores and start command (run from the bench folder). Sourced by the scripts.
#   <app>             the server its docs recommend: Gunicorn (WSGI, two sync workers) or Uvicorn (ASGI, one worker)
#   <app>-w<n>        Postgres test, sync: n Gunicorn workers;  <app>-t<n>: one gthread worker with n threads
PY=.venv/bin
declare -A WSGI=([flask]=apps.flask_app:app [django]=apps.djangoapi.wsgi:application)
declare -A ASGI=([fastapi]=apps.fastapi_app:app [fastapi-typed]=apps.fastapi_typed:app [litestar]=apps.litestar_app:app)
declare -A BASE_PORT=([flask]=8202 [django]=8203 [fastapi]=8204 [fastapi-typed]=8205 [litestar]=8206)
GUNICORN_FLAGS="--worker-tmp-dir /dev/shm"
# Two sync workers keep the core busy. With one (control session) Flask makes the same requests per second at ~90%
# busy and Django ~5% more at ~97%; three are slower (pilot); the docs' (2 x cores) + 1 would be three.
GUNICORN_WORKERS=2
UVICORN_FLAGS="--loop uvloop --http httptools --no-access-log"
# Database connections per worker process, used on the database route only: an async app's one pool (pilot),
# and one per request a sync worker can run at once.
ASYNC_POOL=${ASYNC_POOL:-8}

app_of() { # server name -> app key
  sed -E 's/-(w[0-9]+|t[0-9]+)$//' <<< "$1"
}
variant_of() { # server name -> variant suffix ("" for the recommended server)
  local app; app=$(app_of "$1")
  echo "${1#"$app"}"
}
port_of() { # the app's base port plus 30 for the worker and thread variants
  local app variant; app=$(app_of "$1"); variant=$(variant_of "$1")
  case $variant in
    "") echo "${BASE_PORT[$app]}" ;;
    -w* | -t*) echo $((BASE_PORT[$app] + 30)) ;;
  esac
}
cores_of() {
  source cores.sh
  echo "$SERVER_CORES"
}
server_cmd() { # name [route] -> the command that starts it in the foreground
  local name=$1 route=${2:-users} app variant port target iface pool
  app=$(app_of "$name"); variant=$(variant_of "$name"); port=$(port_of "$name")
  if [ -n "${WSGI[$app]:-}" ]; then target=${WSGI[$app]}; iface=wsgi; else target=${ASGI[$app]}; iface=asgi; fi
  case $variant in
    -t*) pool=${variant#-t} ;;
    *) if [ "$iface" = asgi ]; then pool=$ASYNC_POOL; else pool=1; fi ;;
  esac
  [ "$route" = users-db ] || pool=0
  local env="POOL_SIZE=$pool"
  case $variant in
    "")
      if [ "$iface" = wsgi ]; then
        echo "$env exec $PY/gunicorn -b 127.0.0.1:$port $GUNICORN_FLAGS -w $GUNICORN_WORKERS $target"
      else
        echo "$env exec $PY/uvicorn --port $port $UVICORN_FLAGS $target"
      fi ;;
    -w*) echo "$env exec $PY/gunicorn -b 127.0.0.1:$port $GUNICORN_FLAGS -w ${variant#-w} $target" ;;
    -t*) echo "$env exec $PY/gunicorn -b 127.0.0.1:$port $GUNICORN_FLAGS -k gthread -w 1 --threads ${variant#-t} $target" ;;
  esac
}
