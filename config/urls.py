"""URL routing: Django admin only; trading is CLI/services for now."""
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
