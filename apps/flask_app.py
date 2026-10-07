"""Flask + Pydantic. Run: gunicorn -w 4 -k gthread --threads 16 -b 127.0.0.1:8303 apps.flask_app:app"""
import atexit

from flask import Flask, jsonify, request
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, EmailStr, Field, ValidationError

from apps.shared import (AGE_MAX, AGE_MIN, DATABASE_URL, NAME_MAX, NAME_MIN,
                         PAGE_QUERY, POOL_SIZE, random_start, users)

# gunicorn imports this module in each worker, so every worker gets its own pool.
pool = ConnectionPool(DATABASE_URL, min_size=POOL_SIZE, max_size=POOL_SIZE,
                      kwargs={"row_factory": dict_row}, open=True)
pool.wait()
atexit.register(pool.close)

app = Flask(__name__)


class NewUser(BaseModel):
    name: str = Field(min_length=NAME_MIN, max_length=NAME_MAX)
    email: EmailStr
    age: int = Field(ge=AGE_MIN, le=AGE_MAX)


@app.get("/users")
def list_users():
    return jsonify(users())


@app.post("/users")
def create_user():
    try:
        user = NewUser.model_validate(request.get_json())
    except ValidationError as err:
        return app.response_class(err.json(), status=400, mimetype="application/json")
    return jsonify({"id": 1, **user.model_dump()}), 201


@app.get("/users-db")
def users_db():
    with pool.connection() as conn:
        rows = conn.execute(PAGE_QUERY, (random_start(),)).fetchall()
    return jsonify(rows)
