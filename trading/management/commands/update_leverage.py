"""CLI: update per-asset leverage via `ExchangeClient.update_leverage`."""
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from signing import SigningModule
from trading.services import ExchangeClient


class Command(BaseCommand):
    help = (
        "Set leverage for a perp coin (updateLeverage). "
        "Builder / isolated-only markets need --isolated (isCross=false)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--coin", type=str, required=True, help="Perp coin name, e.g. BTC or xyz:BRENTOIL")
        parser.add_argument("--leverage", type=int, required=True, help="Target leverage (integer >= 1)")
        mx = parser.add_mutually_exclusive_group()
        mx.add_argument(
            "--isolated",
            action="store_true",
            help="Isolated margin (isCross=false); use for builder DEX perps such as xyz:*",
        )
        mx.add_argument(
            "--cross",
            action="store_true",
            help="Cross margin (isCross=true); default when neither flag is set",
        )

    def handle(self, *args, **options):
        if options["leverage"] < 1:
            raise CommandError("--leverage must be >= 1")
        is_cross = not options["isolated"]
        signer = SigningModule()
        client = ExchangeClient(signer, base_url=settings.HYPERLIQUID_API_URL)
        result = client.update_leverage(options["coin"], options["leverage"], is_cross=is_cross)
        self.stdout.write(json.dumps(result, default=str, indent=2))
