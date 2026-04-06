"""Registers the `trading` Django app (models + management commands)."""
from django.apps import AppConfig


class TradingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "trading"
    verbose_name = "Trading"
