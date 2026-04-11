"""CLI: add or remove isolated margin for a perp (updateIsolatedMargin)."""
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from signing import SigningModule
from trading.services import ExchangeClient


class Command(BaseCommand):
    help = (
        "Allocate USDC from cross perp margin into isolated margin for a coin (or remove). "
        "noCross builder perps (e.g. xyz:BRENTOIL) require this before orders can use your balance."
    )

    def add_arguments(self, parser):
        parser.add_argument("--coin", type=str, required=True, help="Perp coin, e.g. xyz:BRENTOIL")
        parser.add_argument(
            "--amount",
            type=float,
            required=True,
            help="USDC notional to add (or remove with --remove)",
        )
        parser.add_argument(
            "--remove",
            action="store_true",
            help="Pull USDC out of isolated margin (maps to isBuy=false)",
        )

    def handle(self, *args, **options):
        amt = options["amount"]
        if amt <= 0:
            raise CommandError("--amount must be positive")
        signer = SigningModule()
        client = ExchangeClient(signer, base_url=settings.HYPERLIQUID_API_URL)
        result = client.update_isolated_margin(options["coin"], amt, add=not options["remove"])
        self.stdout.write(json.dumps(result, default=str, indent=2))
