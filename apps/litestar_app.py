"""Litestar + msgspec. Run: uvicorn apps.litestar_app:app --workers 4 --port 8302"""
from typing import Annotated

import msgspec
from litestar import Litestar, get, post
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from apps.shared import (AGE_MAX, AGE_MIN, DATABASE_URL, NAME_MAX, NAME_MIN,
                         PAGE_QUERY, POOL_SIZE, random_start, users)

pool = AsyncConnectionPool(DATABASE_URL, min_size=POOL_SIZE, max_size=POOL_SIZE,
                           open=False, kwargs={"row_factory": dict_row})

# msgspec has no email type; this is the usual "something@domain.tld" check.
EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class NewUser(msgspec.Struct):
    name: Annotated[
        str,
        msgspec.Meta(min_length=1, max_length=64),
    ]
    email: Annotated[str, msgspec.Meta(pattern=EMAIL)]
    age: Annotated[
        int,
        msgspec.Meta(ge=18, le=120),
    ]


@get("/users")
async def list_users() -> list[dict]:
    return users()


@post("/users")
async def create_user(data: NewUser) -> dict:
    return {"id": 1, **msgspec.structs.asdict(data)}


@get("/users-db")
async def users_db() -> list[dict]:
    async with pool.connection() as conn:
        cur = await conn.execute(PAGE_QUERY, (random_start(),))
        return await cur.fetchall()


async def open_pool() -> None:
    await pool.open(wait=True)


async def close_pool() -> None:
    await pool.close()


app = Litestar([list_users, create_user, users_db], on_startup=[open_pool], on_shutdown=[close_pool])
