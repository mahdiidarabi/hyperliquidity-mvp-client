"""CLI: place limit or market order via `ExchangeClient`."""
from __future__ import annotations

import json
from typing import Any

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
        parser.add_argument(
            "--leverage",
            type=int,
            default=None,
            help="If set, submit updateLeverage for this coin immediately before the order",
        )
        mx = parser.add_mutually_exclusive_group()
        mx.add_argument(
            "--isolated",
            action="store_true",
            help="Use with --leverage: isolated margin (isCross=false); required for many builder perps",
        )
        mx.add_argument(
            "--cross",
            action="store_true",
            help="Use with --leverage: cross margin (isCross=true); default when neither flag is set",
        )

    def handle(self, *args, **options):
        signer = SigningModule()
        client = ExchangeClient(signer, base_url=settings.HYPERLIQUID_API_URL)
        is_buy = options["side"] == "buy"
        ro = options["reduce_only"]
        coin = options["coin"]

        lev_out: dict[str, Any] | None = None
        if options["leverage"] is not None:
            is_cross = not options["isolated"]
            lev_out = client.update_leverage(coin, options["leverage"], is_cross=is_cross)

        if options["market"]:
            result = client.place_market_order(
                coin,
                is_buy,
                options["sz"],
                slippage=options["slippage"],
                reduce_only=ro,
            )
        else:
            result = client.place_limit_order(
                coin,
                is_buy,
                options["sz"],
                options["limit_px"],
                tif=options["tif"],
                reduce_only=ro,
            )

        if lev_out is not None:
            out = {"updateLeverage": lev_out, "order": result}
        else:
            out = result
        self.stdout.write(json.dumps(out, default=str, indent=2))
