import json

from django.conf import settings
from django.core.management.base import BaseCommand

from signing import SigningModule
from trading.services import InfoClient


class Command(BaseCommand):
    help = "Fetch read-only account snapshot from Hyperliquid /info (no signing)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--address",
            type=str,
            default=None,
            help="0x… address to query (default: address derived from PRIVATE_KEY in .env).",
        )
        parser.add_argument(
            "--indent",
            type=int,
            default=2,
            help="JSON indent (default 2; use 0 for compact).",
        )

    def handle(self, *args, **options):
        addr = options["address"]
        if not addr:
            addr = SigningModule().address

        client = InfoClient(base_url=settings.HYPERLIQUID_API_URL)
        snap = client.snapshot(addr)

        ind = options["indent"]
        text = json.dumps(snap, default=str, indent=ind if ind > 0 else None)
        self.stdout.write(text)
