"""Litestar + msgspec. Run: uvicorn apps.litestar_app:app"""

from typing import Annotated
from uuid import UUID, uuid4

import msgspec
from litestar import Litestar, get, post

from apps.shared import AGE_MAX, AGE_MIN, EMAIL, NAME_MAX, NAME_MIN, PAGE_QUERY, async_pool, random_start, users

pool = async_pool()


class NewUser(msgspec.Struct):
    name: Annotated[str, msgspec.Meta(min_length=NAME_MIN, max_length=NAME_MAX)]
    email: Annotated[str, msgspec.Meta(pattern=EMAIL)]
    age: Annotated[int, msgspec.Meta(ge=AGE_MIN, le=AGE_MAX)]


class CreatedUser(msgspec.Struct):
    id: UUID
    name: str
    email: str
    age: int


@get("/users")
async def list_users() -> list[dict]:
    return users()


@post("/users")
async def create_user(data: NewUser) -> CreatedUser:
    return CreatedUser(id=uuid4(), name=data.name, email=data.email, age=data.age)


@get("/users-db")
async def users_db() -> list[dict]:
    async with pool.connection() as conn:
        cur = await conn.execute(PAGE_QUERY, (random_start(),))
        return await cur.fetchall()


async def open_pool() -> None:
    if pool:
        await pool.open(wait=True)


async def close_pool() -> None:
    if pool:
        await pool.close()


app = Litestar([list_users, create_user, users_db], on_startup=[open_pool], on_shutdown=[close_pool])
