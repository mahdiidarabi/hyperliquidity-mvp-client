"""CLI: USDC withdrawals from Hyperliquid ledger (read-only /info)."""
import json

from django.conf import settings
from django.core.management.base import BaseCommand

from signing import SigningModule
from trading.services import InfoClient

LEDGER_NOTICE = (
    "Rows come from userNonFundingLedgerUpdates (finalized withdraw ledger entries). "
    "A withdraw3 you just signed may still be in flight to Arbitrum until validators complete it "
    "(see Bridge2 withdraw timing in the README); it appears here once recorded."
)


class Command(BaseCommand):
    help = "List USDC withdrawals from account ledger history (recorded completions)."

    def add_arguments(self, parser):
        parser.add_argument("--address", type=str, default=None, help="Account (default: PRIVATE_KEY wallet)")
        parser.add_argument(
            "--days",
            type=int,
            default=365,
            help="Window: time >= now - days (default 365). Use 0 for full history (API may cap).",
        )
        parser.add_argument("--indent", type=int, default=2)

    def handle(self, *args, **options):
        addr = options["address"] or SigningModule().address
        days = options["days"]
        start = InfoClient.default_start_ms_for_days(days)
        ic = InfoClient(base_url=settings.HYPERLIQUID_API_URL)
        items = ic.get_withdrawals(addr, start_time_ms=start)
        out = {
            "address": addr,
            "base_url": ic.base_url,
            "days": days,
            "start_time_ms": start,
            "source": "userNonFundingLedgerUpdates",
            "notice": LEDGER_NOTICE,
            "count": len(items),
            "withdrawals": items,
        }
        ind = options["indent"]
        self.stdout.write(json.dumps(out, default=str, indent=ind if ind > 0 else None))
