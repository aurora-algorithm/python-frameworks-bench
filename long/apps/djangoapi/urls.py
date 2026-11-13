from django.urls import path

from apps.djangoapi import views

urlpatterns = [
    path("users", views.users_view),
    path("users-db", views.users_db),
]
