"""CLI: cancel an order by coin + oid via `ExchangeClient`."""
import json

from django.conf import settings
from django.core.management.base import BaseCommand

from signing import SigningModule
from trading.services import ExchangeClient


class Command(BaseCommand):
    help = "Cancel an open order by coin name and order id (oid)."

    def add_arguments(self, parser):
        parser.add_argument("--coin", type=str, required=True)
        parser.add_argument("--oid", type=int, required=True)

    def handle(self, *args, **options):
        signer = SigningModule()
        client = ExchangeClient(signer, base_url=settings.HYPERLIQUID_API_URL)
        result = client.cancel_order(options["coin"], options["oid"])
        self.stdout.write(json.dumps(result, default=str, indent=2))
