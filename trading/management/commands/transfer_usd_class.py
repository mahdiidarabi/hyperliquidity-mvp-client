"""CLI: move USDC between spot and perp margin (signed `usdClassTransfer`)."""
import json

from django.conf import settings
from django.core.management.base import BaseCommand

from signing import SigningModule
from trading.services import ExchangeClient


class Command(BaseCommand):
    help = "Transfer USDC between spot and perpetual (not a chain withdrawal)."

    def add_arguments(self, parser):
        parser.add_argument("--amount", type=float, required=True)
        g = parser.add_mutually_exclusive_group(required=True)
        g.add_argument("--to-perp", action="store_true", help="Spot → perp margin")
        g.add_argument("--to-spot", action="store_true", help="Perp → spot margin")

    def handle(self, *args, **options):
        signer = SigningModule()
        ex = ExchangeClient(signer, base_url=settings.HYPERLIQUID_API_URL)
        to_perp = bool(options["to_perp"])
        r = ex.usd_class_transfer(options["amount"], to_perp=to_perp)
        self.stdout.write(json.dumps(r, default=str, indent=2))
