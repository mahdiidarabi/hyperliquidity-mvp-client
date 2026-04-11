"""CLI: move USDC between perp DEX collateral books (sendAsset — user-signed)."""
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from signing import SigningModule
from trading.services import ExchangeClient


def _normalize_dex(name: str) -> str:
    n = name.strip().lower()
    if n in ("primary", "default", "main", ""):
        return ""
    return name.strip()


class Command(BaseCommand):
    help = (
        "Transfer USDC collateral from one perp DEX to another (e.g. primary '' → builder 'xyz'). "
        "Required before update_isolated_margin / orders on HIP-3 markets if funds are only on the default DEX."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--amount",
            type=float,
            required=True,
            help="USDC amount to move",
        )
        parser.add_argument(
            "--from-dex",
            type=str,
            default="primary",
            help='Source perp DEX: "primary" (default USDC perp, dex "") or e.g. xyz',
        )
        parser.add_argument(
            "--to-dex",
            type=str,
            required=True,
            help='Destination perp DEX name (e.g. "xyz" for XYZ builder DEX)',
        )
        parser.add_argument(
            "--destination",
            type=str,
            default=None,
            help="Recipient address (default: wallet from PRIVATE_KEY; use self-transfer)",
        )

    def handle(self, *args, **options):
        amt = options["amount"]
        if amt <= 0:
            raise CommandError("--amount must be positive")
        src = _normalize_dex(options["from_dex"])
        dst = _normalize_dex(options["to_dex"])
        if src == dst:
            raise CommandError("--from-dex and --to-dex must differ")

        signer = SigningModule()
        client = ExchangeClient(signer, base_url=settings.HYPERLIQUID_API_URL)
        result = client.send_usdc_between_perp_dexes(
            amt,
            source_dex=src,
            destination_dex=dst,
            destination=options["destination"],
        )
        self.stdout.write(json.dumps(result, default=str, indent=2))
