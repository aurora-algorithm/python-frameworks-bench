"""Django + Django REST framework, in one file.
Run: gunicorn -w 4 -k gthread --threads 16 -b 127.0.0.1:8304 apps.django_app:application"""
import atexit
import os

import django
from django.conf import settings

settings.configure(
    DEBUG=False,
    ALLOWED_HOSTS=["*"],
    ROOT_URLCONF=__name__,
    # Signs nothing here (no sessions, no auth); a real project reads it from the environment.
    SECRET_KEY=os.environ.get("DJANGO_SECRET_KEY", "benchmark-only"),
    # startproject's defaults, minus the ones that need Django's own database (sessions, auth, messages).
    MIDDLEWARE=[
        "django.middleware.security.SecurityMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
        "django.middleware.clickjacking.XFrameOptionsMiddleware",
    ],
    INSTALLED_APPS=["rest_framework"],
    DATABASES={},
    REST_FRAMEWORK={
        "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
        "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
        "DEFAULT_AUTHENTICATION_CLASSES": [],
        "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
        "UNAUTHENTICATED_USER": None,
    },
)
django.setup()

from django.core.wsgi import get_wsgi_application  # noqa: E402
from django.urls import path  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402
from psycopg_pool import ConnectionPool  # noqa: E402
from rest_framework import serializers  # noqa: E402
from rest_framework.decorators import api_view  # noqa: E402
from rest_framework.response import Response  # noqa: E402

from apps.shared import (AGE_MAX, AGE_MIN, DATABASE_URL, NAME_MAX, NAME_MIN,  # noqa: E402
                         PAGE_QUERY, POOL_SIZE, random_start, users)

# gunicorn imports this module in each worker, so every worker gets its own pool.
pool = ConnectionPool(DATABASE_URL, min_size=POOL_SIZE, max_size=POOL_SIZE,
                      kwargs={"row_factory": dict_row}, open=True)
pool.wait()
atexit.register(pool.close)


class NewUserSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=NAME_MIN, max_length=NAME_MAX)
    email = serializers.EmailField()
    age = serializers.IntegerField(min_value=AGE_MIN, max_value=AGE_MAX)


@api_view(["GET", "POST"])
def users_view(request):
    if request.method == "GET":
        return Response(users())
    data = NewUserSerializer(data=request.data)
    data.is_valid(raise_exception=True)
    return Response({"id": 1, **data.validated_data}, status=201)


@api_view(["GET"])
def users_db(request):
    with pool.connection() as conn:
        rows = conn.execute(PAGE_QUERY, (random_start(),)).fetchall()
    return Response(rows)


urlpatterns = [path("users", users_view), path("users-db", users_db)]
application = get_wsgi_application()
