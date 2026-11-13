"""FastAPI + Pydantic with return types, so Pydantic serializes every response. Run: uvicorn apps.fastapi_typed:app"""

from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import FastAPI
from pydantic import BaseModel, Field

from apps.shared import AGE_MAX, AGE_MIN, EMAIL, NAME_MAX, NAME_MIN, PAGE_QUERY, async_pool, random_start, users

pool = async_pool()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if pool:
        await pool.open(wait=True)
    yield
    if pool:
        await pool.close()


app = FastAPI(lifespan=lifespan)


class User(BaseModel):
    id: int
    name: str
    email: str
    active: bool
    tags: list[str]


class NewUser(BaseModel):
    name: str = Field(min_length=NAME_MIN, max_length=NAME_MAX)
    email: str = Field(pattern=EMAIL)
    age: int = Field(ge=AGE_MIN, le=AGE_MAX)


class CreatedUser(BaseModel):
    id: UUID
    name: str
    email: str
    age: int


@app.get("/users")
async def list_users() -> list[User]:
    return users()


@app.post("/users", status_code=201)
async def create_user(user: NewUser) -> CreatedUser:
    return CreatedUser(id=uuid4(), **user.model_dump())


@app.get("/users-db")
async def users_db() -> list[User]:
    async with pool.connection() as conn:
        cur = await conn.execute(PAGE_QUERY, (random_start(),))
        return await cur.fetchall()
