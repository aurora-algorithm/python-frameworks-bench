"""Shared by every framework: the same payload, the same validation rules, the same driver, pool and query."""

import atexit
import os
import random
import sys

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool, ConnectionPool

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://dev:dev@127.0.0.1/bench")
# Connections per worker process, set by servers.sh: one per sync worker (or per gthread thread), one async pool
# of ASYNC_POOL; 0 = no database (every route but users-db).
POOL_SIZE = int(os.environ.get("POOL_SIZE", "20"))
# fmt: off
PAGE_QUERY = (
    "SELECT id, name, email, active, tags FROM users "
    "WHERE id > %s ORDER BY id LIMIT 50"
)
# fmt: on

# POST /users rules, checked by each framework in its own way.
NAME_MIN, NAME_MAX = 1, 50
AGE_MIN, AGE_MAX = 0, 150
# One email check for all four, so no framework runs a heavier validator (Pydantic's EmailStr runs email-validator).
EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

_TAGS = ["a", "b"]


_reported = False


def report_gil() -> None:
    """Prints once per process whether the GIL is on, after every extension has loaded (the first request).
    On the free-threaded build, importing an extension that doesn't support it turns the GIL back on."""
    global _reported
    if not _reported:
        _reported = True
        print(f"pid {os.getpid()}: GIL enabled: {sys._is_gil_enabled()}", file=sys.stderr, flush=True)


def users() -> list[dict]:
    report_gil()
    return [
        {
            "id": i,
            "name": "User",
            "email": "user@example.com",
            "active": i % 2 == 0,
            "tags": _TAGS,
        }
        for i in range(50)
    ]


def random_start() -> int:
    return random.randrange(9950)


def sync_pool() -> ConnectionPool | None:
    """This worker's pool, connected before the first request (each worker process imports the app)."""
    if not POOL_SIZE:
        return None
    pool = ConnectionPool(DATABASE_URL, min_size=POOL_SIZE, max_size=POOL_SIZE, kwargs={"row_factory": dict_row})
    pool.wait()
    atexit.register(pool.close)
    return pool


def async_pool() -> AsyncConnectionPool | None:
    """Opened in the app's startup hook, on the event loop that will use it."""
    if not POOL_SIZE:
        return None
    return AsyncConnectionPool(
        DATABASE_URL, min_size=POOL_SIZE, max_size=POOL_SIZE, open=False, kwargs={"row_factory": dict_row}
    )
