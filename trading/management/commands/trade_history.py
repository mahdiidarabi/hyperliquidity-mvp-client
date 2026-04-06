"""CLI: user fills report with optional enrich (see `trade_history.build_trade_history_report`)."""
import json

from django.conf import settings
from django.core.management.base import BaseCommand

from signing import SigningModule
from trading.services import InfoClient


class Command(BaseCommand):
    help = (
        "User trade fills with optional per-order fill %% (orderStatus + origSz). "
        "Read-only; uses same API base as HYPERLIQUID_MAINNET / HYPERLIQUID_API_URL."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--address",
            type=str,
            default=None,
            help="Account to query (default: wallet from PRIVATE_KEY)",
        )
        parser.add_argument(
            "--enrich",
            action="store_true",
            help="Call orderStatus for each order id (caps at --max-order-lookups)",
        )
        parser.add_argument(
            "--max-order-lookups",
            type=int,
            default=50,
            help="Max orderStatus calls when --enrich (default 50)",
        )
        parser.add_argument("--indent", type=int, default=2)

    def handle(self, *args, **options):
        addr = options["address"] or SigningModule().address
        ic = InfoClient(base_url=settings.HYPERLIQUID_API_URL)
        report = ic.trade_history_report(
            addr,
            enrich_order_status=options["enrich"],
            max_order_lookups=options["max_order_lookups"],
        )
        ind = options["indent"]
        self.stdout.write(json.dumps(report, default=str, indent=ind if ind > 0 else None))
