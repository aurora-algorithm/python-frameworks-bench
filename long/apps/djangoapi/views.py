from uuid import uuid4

from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.shared import AGE_MAX, AGE_MIN, EMAIL, NAME_MAX, NAME_MIN, PAGE_QUERY, random_start, sync_pool, users

pool = sync_pool()


class NewUserSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=NAME_MIN, max_length=NAME_MAX)
    email = serializers.RegexField(EMAIL)
    age = serializers.IntegerField(min_value=AGE_MIN, max_value=AGE_MAX)


@api_view(["GET", "POST"])
def users_view(request):
    if request.method == "GET":
        return Response(users())
    serializer = NewUserSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response({"id": str(uuid4()), **serializer.validated_data}, status=201)


@api_view(["GET"])
def users_db(request):
    with pool.connection() as conn:
        rows = conn.execute(PAGE_QUERY, (random_start(),)).fetchall()
    return Response(rows)
