"""CLI: list perp + spot symbols for the current API base (`InfoClient.list_symbols`)."""
import json

from django.conf import settings
from django.core.management.base import BaseCommand

from trading.services import InfoClient


class Command(BaseCommand):
    help = "List perp and spot symbol names valid for --coin on this API (mainnet/testnet from .env)."

    def add_arguments(self, parser):
        parser.add_argument("--indent", type=int, default=2)

    def handle(self, *args, **options):
        ic = InfoClient(base_url=settings.HYPERLIQUID_API_URL)
        data = ic.list_symbols()
        ind = options["indent"]
        self.stdout.write(json.dumps(data, default=str, indent=ind if ind > 0 else None))
