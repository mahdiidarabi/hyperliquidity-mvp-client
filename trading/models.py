"""Django models for non-secret metadata (optional labels in admin)."""
from django.db import models


class TradingAccount(models.Model):
    """Non-secret metadata for your Hyperliquid wallet (key stays in .env)."""

    name = models.CharField(max_length=100)
    use_testnet = models.BooleanField(
        default=False,
        help_text="Display only for now; API network is controlled by .env "
        "(HYPERLIQUID_MAINNET / HYPERLIQUID_API_URL).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name
