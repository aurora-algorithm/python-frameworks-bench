"""FastAPI + Pydantic. Run: uvicorn apps.fastapi_app:app --workers 4 --port 8301"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, EmailStr, Field

from apps.shared import (AGE_MAX, AGE_MIN, DATABASE_URL, NAME_MAX, NAME_MIN,
                         PAGE_QUERY, POOL_SIZE, random_start, users)

pool = AsyncConnectionPool(DATABASE_URL, min_size=POOL_SIZE, max_size=POOL_SIZE,
                           open=False, kwargs={"row_factory": dict_row})


@asynccontextmanager
async def lifespan(app: FastAPI):
    await pool.open(wait=True)
    yield
    await pool.close()


app = FastAPI(lifespan=lifespan)


class NewUser(BaseModel):
    name: str = Field(min_length=NAME_MIN, max_length=NAME_MAX)
    email: EmailStr
    age: int = Field(ge=AGE_MIN, le=AGE_MAX)


@app.get("/users")
async def list_users():
    return users()


@app.post("/users", status_code=201)
async def create_user(user: NewUser):
    return {"id": 1, **user.model_dump()}


@app.get("/users-db")
async def users_db():
    async with pool.connection() as conn:
        cur = await conn.execute(PAGE_QUERY, (random_start(),))
        return await cur.fetchall()
