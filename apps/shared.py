"""Shared by every framework: the same payload, the same validation limits, the same driver, pool size and query."""
import os
import random

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/bench")
# Per worker process. Every server runs 4 workers, so 20 connections in total, like the Node benchmarks.
POOL_SIZE = 5
PAGE_QUERY = (
    "SELECT id, name, email, active, tags FROM users "
    "WHERE id > %s ORDER BY id LIMIT 50"
)

# POST /users limits: what each framework validates, in its own idiomatic way.
NAME_MIN, NAME_MAX = 1, 50
AGE_MIN, AGE_MAX = 0, 150

_TAGS = ["a", "b"]


def users() -> list[dict]:
    return [
        {"id": i, "name": "User", "email": "user@example.com",
         "active": i % 2 == 0, "tags": _TAGS}
        for i in range(50)
    ]


def random_start() -> int:
    return random.randrange(9950)
