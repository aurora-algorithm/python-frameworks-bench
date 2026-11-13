# python-frameworks-bench

Code and per-run results behind the "Which Python framework is fastest?" Short: FastAPI, Litestar, Flask and Django on Python 3.14.

The long video's benchmark is in [`long/`](long/): typed and untyped FastAPI side by side, and Flask and Django with workers vs threads on Postgres.

## What is measured
- **Test 1 — plain JSON:** `GET /users` returns the same 50 users (4,116 bytes, identical across all frameworks).
- **Test 2 — validated input:** `POST /users` with `{"name","email","age"}`; each framework validates it (FastAPI + Pydantic, Litestar + msgspec, Flask + Pydantic, Django + DRF serializer) and replies 201 with the created object.
- **Test 3 — Postgres:** `GET /users-db` reads 50 rows from a random start in a 10,000-row table (`schema.sql`) with psycopg 3, using a connection pool of 5 connections per worker opened at startup.
- Per run: requests/second (per 0.5 s), latency percentiles, peak memory (RSS) summed over all 4 server worker processes.

## Results (median of 5 runs)
| Test | Framework | req/s (median) | slowest–fastest run | typical (p50) | slowest 1% (p99) | peak memory |
|---|---|---|---|---|---|---|
| Plain JSON | FastAPI | 10,297 | 9,971–10,326 | 5.84 ms | 12.01 ms | 384.1 MiB |
| Plain JSON | FastAPI, typed responses | 33,066 | 29,540–33,288 | 1.73 ms | 3.96 ms | 386.6 MiB |
| Plain JSON | Litestar | 71,460 | 68,793–72,495 | 0.79 ms | 1.94 ms | 393.8 MiB |
| Plain JSON | Flask | 5,010 | 4,823–5,032 | 12.55 ms | 21.46 ms | 300.9 MiB |
| Plain JSON | Django + DRF | 4,563 | 4,465–4,585 | 13.75 ms | 23.88 ms | 326.7 MiB |
| Validated POST | FastAPI + Pydantic | 29,034 | 28,997–29,199 | 2.0 ms | 4.58 ms | 386.8 MiB |
| Validated POST | FastAPI + Pydantic, typed responses | 30,378 | 29,511–30,698 | 1.91 ms | 4.38 ms | 386.1 MiB |
| Validated POST | Litestar + msgspec | 70,372 | 69,762–70,644 | 0.8 ms | 1.98 ms | 394.5 MiB |
| Validated POST | Flask + Pydantic | 4,838 | 4,714–4,844 | 12.98 ms | 22.25 ms | 301.9 MiB |
| Validated POST | Django + DRF serializer | 4,232 | 4,048–4,272 | 14.81 ms | 26.32 ms | 320.1 MiB |
| Postgres | FastAPI · psycopg async | 6,789 | 6,772–6,822 | 9.13 ms | 12.88 ms | 393.4 MiB |
| Postgres | FastAPI · psycopg async, typed responses | 12,404 | 11,835–12,529 | 4.94 ms | 8.29 ms | 394.1 MiB |
| Postgres | Litestar · psycopg async | 16,463 | 16,317–16,560 | 3.74 ms | 6.45 ms | 401.1 MiB |
| Postgres | Flask · psycopg | 3,206 | 3,159–3,216 | 19.58 ms | 31.8 ms | 306.8 MiB |
| Postgres | Django + DRF · psycopg | 2,885 | 2,780–2,910 | 21.51 ms | 42.05 ms | 355.2 MiB |

Versions: Python 3.14.7 · fastapi 0.142.2 · litestar 2.24.0 · flask 3.1.3 · django 6.1.1 · djangorestframework 3.18.1 · uvicorn 0.54.0 · uvloop 0.23.0 · httptools 0.8.0 · gunicorn 26.2.0 · pydantic 2.13.5 · msgspec 0.22.0 · psycopg 3.3.6 · psycopg-pool 3.3.3 · oha 1.16.0 · postgres 17.11. Raw per-run files are in `results/`.

## Method
- Apple M1 Pro (10 cores, 16 GB), macOS. 4 worker processes per framework.
- ASGI apps (FastAPI, Litestar) run on uvicorn with uvloop and httptools.
- WSGI apps (Flask, Django) run on gunicorn with 4 workers and 16 threads per worker (`-k gthread --threads 16`).
- oha with 64 connections: 10 s warm-up, then 20 s measured; 5 runs per configuration, alternating; median reported.
- A run only starts when background CPU is quiet (≤ 170%), and is repeated if background load exceeds 190% (`run_all.sh`).
- Every configuration was measured in the same session, alternating.

## Caveats
- FastAPI serializing untyped Python dicts (`return users()`) goes through `jsonable_encoder`, which is slow in pure Python. Adding an explicit response type annotation (`-> list[User]`) lets Pydantic-core serialize directly, boosting throughput by 221% (+3.2×).
- Litestar uses `msgspec`, a high-performance C/Rust serialization library, giving it an inherent serialization advantage.
- The load tool, server processes and Postgres share one laptop. Compare the relative gaps, not absolute numbers.

## Run it
```bash
psql -c 'CREATE DATABASE bench' && psql bench -f schema.sql
uv sync
./run_all.sh
python3 export_charts.py summary.json charts.json
```
