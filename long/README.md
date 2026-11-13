# long/: the long video's benchmark

Code and per-run results behind the long video "Litestar Beat FastAPI, Flask and Django in Every Test". It is a separate, larger session from the Short's benchmark in the folder above: new versions, one server core, and a Postgres test that compares sync workers, threads and async.

The same small API is written in Flask, Django + Django REST framework, FastAPI and Litestar (`apps/`). Every app returns the same 50 users from one shared module (`apps/shared.py`) and reads Postgres through the same driver, psycopg 3, with a psycopg pool.

## What it measures

- **Test 1, returning 50 users as JSON:** `GET /users`. No request body, no database, nothing to check, so this measures what each framework and its server do on every request. FastAPI runs twice: as in its tutorial (`apps/fastapi_app.py`, no return type) and with a `User` model and `-> list[User]` (`apps/fastapi_typed.py`).
- **Test 2, validating a new user:** `POST /users` with `{"name": "Ada", "email": "ada@example.com", "age": 36}`. Each framework checks the same rules: name 1 to 50 characters, one email regex, age a whole number from 0 to 150. Flask and FastAPI use Pydantic, Litestar uses msgspec, Django uses a DRF serializer. `verify.py` sends 11 inputs to every server before anything is timed and fails if any of them answers differently.
- **Test 3, reading 50 rows from Postgres:** `GET /users-db` reads 50 rows from a random start in a 10,000-row table (`schema.sql`). Flask runs once with a single sync worker, to show the core sitting idle while the worker waits for Postgres, and then Flask and Django run as one Gunicorn gthread worker with 8 threads. FastAPI and Litestar use one async pool of 8 connections.

Servers: Flask and Django run on Gunicorn with 2 sync workers (2 fill the core; 3 were slower in a pilot). FastAPI and Litestar run on Uvicorn, one worker, with uvloop and httptools. `servers.sh` holds every start command.

Each configuration ran 5 times in a random order per round. A run is oha with 64 connections: 10 s of warm-up, then 20 s measured. A run fails on any non-2xx response. The server and every process and thread it starts are pinned to one core with `taskset`; oha, Postgres and monitoring get their own cores (`cores.sh`). `summarize_run.py` reads how busy the server's core was from `/proc/stat` and the server's CPU and memory from Prometheus (process-exporter).

## Results

Median requests per second of 5 runs, from `summary.json`. "Core busy" is how busy the server's core was in the median run.

| Test | Setup | Config | req/s (median) | slowest to fastest run | core busy |
|---|---|---|---:|---|---:|
| Test 1: JSON | Flask, Gunicorn, 2 sync workers | `flask/users` | 4,835.85 | 4,747.2 to 4,957.25 | 100.0% |
| Test 1: JSON | Django + DRF, Gunicorn, 2 sync workers | `django/users` | 2,946.45 | 2,898.65 to 3,002.55 | 100.0% |
| Test 1: JSON | FastAPI as in its tutorial (no return type), Uvicorn | `fastapi/users` | 2,764.7 | 2,717.1 to 2,790.0 | 100.0% |
| Test 1: JSON | FastAPI with return types, Uvicorn | `fastapi-typed/users` | 8,377.55 | 8,144.0 to 8,490.95 | 100.0% |
| Test 1: JSON | Litestar, Uvicorn | `litestar/users` | 18,943.5 | 18,096.9 to 19,106.6 | 99.9% |
| Test 2: validation | Flask + Pydantic, Gunicorn, 2 sync workers | `flask/users-post` | 5,142.6 | 5,094.9 to 5,206.6 | 99.8% |
| Test 2: validation | Django + DRF serializer, Gunicorn, 2 sync workers | `django/users-post` | 2,382.2 | 2,356.45 to 2,506.45 | 99.9% |
| Test 2: validation | FastAPI + Pydantic with return types, Uvicorn | `fastapi-typed/users-post` | 11,614.75 | 11,372.45 to 11,776.25 | 99.9% |
| Test 2: validation | Litestar + msgspec, Uvicorn | `litestar/users-post` | 16,857.5 | 16,539.05 to 17,634.95 | 99.9% |
| Test 3: Postgres | Flask, Gunicorn, 1 sync worker | `flask-w1/users-db` | 1,697.45 | 1,675.4 to 1,713.55 | 68.4% |
| Test 3: Postgres | Flask, Gunicorn gthread, 8 threads | `flask-t8/users-db` | 2,667.5 | 2,630.45 to 2,714.0 | 99.9% |
| Test 3: Postgres | Django + DRF, Gunicorn gthread, 8 threads | `django-t8/users-db` | 1,778.15 | 1,734.2 to 1,790.15 | 100.0% |
| Test 3: Postgres | FastAPI with return types, Uvicorn, async pool of 8 | `fastapi-typed/users-db` | 2,782.6 | 2,710.1 to 2,816.3 | 100.0% |
| Test 3: Postgres | Litestar, Uvicorn, async pool of 8 | `litestar/users-db` | 3,796.0 | 3,771.9 to 3,820.65 | 100.0% |

Flask with one sync worker is the only setup that leaves the core idle: the worker waits while Postgres answers.

`summary.json` also has latency (p50, p99), memory (PSS), thread and process counts and oha's and Postgres's CPU for each configuration. Every run is in `results/<server>_<route>_run<n>.json`. `python3 summarize_session.py results` rebuilds `summary.json` from them exactly. `results/order.txt` is the order the session ran in. That session also measured setups the video doesn't use (other servers, middleware, more workers, more cores); their results are not in this folder. `profiles/analysis.json` has the py-spy profiles (`profile_one.sh`, `analyze_profile.py`), which were separate runs.

The numbers said in the video over the screen recordings come from runs recorded on screen, which are a little slower because the recorder shares the machine. The charts in the video use the medians above.

## Versions

From `results/versions.txt`, recorded at measurement time:

Python 3.14.8, Flask 3.1.3 (Werkzeug 3.1.9), Django 6.1.2, Django REST framework 3.18.3, FastAPI 0.143.2 (Starlette 1.8.0), Pydantic 2.14.1 (pydantic-core 2.50.1), Litestar 2.24.0, msgspec 0.22.0, Gunicorn 26.2.0, Uvicorn 0.54.0, uvloop 0.23.0, httptools 0.9.0, psycopg 3.3.6 (binary), psycopg-pool 3.3.3, py-spy 0.4.2, oha 1.16.0, PostgreSQL 17.11.

## The machine

Everything ran inside one Docker container named `longs-rig`: Ubuntu 24.04 in Docker Desktop's VM on an Apple M1 Pro Mac. The server had one core of that VM. Before each run the scripts wait until the Mac outside the VM is quiet, and they throw away and repeat a run if the Mac got busy during it (`run_all.sh`). A container on a laptop is not a production server, so compare the gaps between frameworks, not the absolute numbers.

## Run it

The container image is not part of this repo. The scripts expect a container named `longs-rig` with a user `dev` (passwordless sudo), at least 10 cores, the `SYS_NICE` and `SYS_PTRACE` capabilities, and these installed: uv with Python 3.14.8, PostgreSQL 17 with a `dev` role, oha, and Prometheus, process-exporter and Grafana under `/opt/prometheus`, `/opt/process-exporter` and `/opt/grafana`.

From the Mac, in this folder:

```bash
./sync_in.sh          # copy the code into the container's ~/pybench
./run_all.sh          # prepare.sh inside the container (venv, database, monitoring, verify.py), then 5 rounds
./post_session.sh     # summarize_session.py, the py-spy profiles, and the results copied back here
```

`run_all.sh` runs `prepare.sh` itself; to run it alone, use `docker exec -u dev longs-rig bash -lc 'cd ~/pybench && ./prepare.sh'`. `RESUME=1 ./run_all.sh` keeps finished runs. To summarize results you already have: `python3 summarize_session.py results > summary.json`. To start one server by hand inside the container, the same way the runs do: `./serve.sh fastapi-typed users-db` (and `./serve.sh stop`).
