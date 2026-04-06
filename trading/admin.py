"""Django admin for `TradingAccount` (labels only; no secrets)."""
from django.contrib import admin

from trading.models import TradingAccount


@admin.register(TradingAccount)
class TradingAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "use_testnet", "created_at")
    list_filter = ("use_testnet",)
    search_fields = ("name",)
