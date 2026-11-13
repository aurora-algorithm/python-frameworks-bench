"""FastAPI + Pydantic, written like the first page of its tutorial: handlers return plain data, no return types.
Run: uvicorn apps.fastapi_app:app"""

from contextlib import asynccontextmanager
from uuid import uuid4

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


class NewUser(BaseModel):
    name: str = Field(min_length=NAME_MIN, max_length=NAME_MAX)
    email: str = Field(pattern=EMAIL)
    age: int = Field(ge=AGE_MIN, le=AGE_MAX)


@app.get("/users")
async def list_users():
    return users()


@app.post("/users", status_code=201)
async def create_user(user: NewUser):
    return {"id": str(uuid4()), **user.model_dump()}


@app.get("/users-db")
async def users_db():
    async with pool.connection() as conn:
        cur = await conn.execute(PAGE_QUERY, (random_start(),))
        return await cur.fetchall()
