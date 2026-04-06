"""CLI: perp vs spot balance summary (read-only /info)."""
import json

from django.conf import settings
from django.core.management.base import BaseCommand

from signing import SigningModule
from trading.services import InfoClient


class Command(BaseCommand):
    help = (
        "Show withdrawable / margin (perp) and spot token balances. "
        "Uses the same API base as HYPERLIQUID_MAINNET / HYPERLIQUID_API_URL."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--address",
            type=str,
            default=None,
            help="Account (default: address from PRIVATE_KEY)",
        )
        parser.add_argument("--indent", type=int, default=2)

    def handle(self, *args, **options):
        addr = options["address"] or SigningModule().address
        ic = InfoClient(base_url=settings.HYPERLIQUID_API_URL)
        data = ic.get_account_balances(addr)
        ind = options["indent"]
        self.stdout.write(json.dumps(data, default=str, indent=ind if ind > 0 else None))
