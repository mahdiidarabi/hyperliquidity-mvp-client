"""CLI: place limit or market order via `ExchangeClient`."""
import json

from django.conf import settings
from django.core.management.base import BaseCommand

from signing import SigningModule
from trading.services import ExchangeClient


class Command(BaseCommand):
    help = (
        "Place a limit or market order (perp or spot coin name per Hyperliquid). "
        "Uses PRIVATE_KEY and network from .env (see signing/env.py)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--coin", type=str, required=True, help="e.g. BTC, ETH, or a spot pair name from list_symbols")
        parser.add_argument("--side", type=str, choices=["buy", "sell"], required=True)
        parser.add_argument("--sz", type=float, required=True, help="Order size (asset units)")
        g = parser.add_mutually_exclusive_group(required=True)
        g.add_argument("--limit-px", type=float, help="Limit price")
        g.add_argument("--market", action="store_true", help="Market-style IOC order (uses slippage)")
        parser.add_argument(
            "--tif",
            type=str,
            choices=["Gtc", "Ioc", "Alo"],
            default="Gtc",
            help="Time in force for limit orders (ignored for --market)",
        )
        parser.add_argument("--slippage", type=float, default=0.05, help="Market order slippage (default 0.05)")
        parser.add_argument("--reduce-only", action="store_true", help="Reduce-only flag")

    def handle(self, *args, **options):
        signer = SigningModule()
        client = ExchangeClient(signer, base_url=settings.HYPERLIQUID_API_URL)
        is_buy = options["side"] == "buy"
        ro = options["reduce_only"]

        if options["market"]:
            result = client.place_market_order(
                options["coin"],
                is_buy,
                options["sz"],
                slippage=options["slippage"],
                reduce_only=ro,
            )
        else:
            result = client.place_limit_order(
                options["coin"],
                is_buy,
                options["sz"],
                options["limit_px"],
                tif=options["tif"],
                reduce_only=ro,
            )

        self.stdout.write(json.dumps(result, default=str, indent=2))
