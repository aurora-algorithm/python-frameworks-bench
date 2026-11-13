"""Flask + Pydantic. Run: gunicorn apps.flask_app:app"""

from uuid import uuid4

from flask import Flask, jsonify, request
from pydantic import BaseModel, Field, ValidationError

from apps.shared import AGE_MAX, AGE_MIN, EMAIL, NAME_MAX, NAME_MIN, PAGE_QUERY, random_start, sync_pool, users

app = Flask(__name__)

pool = sync_pool()


class NewUser(BaseModel):
    name: str = Field(min_length=NAME_MIN, max_length=NAME_MAX)
    email: str = Field(pattern=EMAIL)
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
    return jsonify({"id": str(uuid4()), **user.model_dump()}), 201


@app.get("/users-db")
def users_db():
    with pool.connection() as conn:
        rows = conn.execute(PAGE_QUERY, (random_start(),)).fetchall()
    return jsonify(rows)
