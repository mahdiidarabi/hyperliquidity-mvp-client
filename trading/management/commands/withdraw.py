"""CLI: withdraw USDC from Hyperliquid to an EVM address (`withdraw3`); use --execute to send."""
import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from signing import SigningModule
from trading.services.exchange_client import ExchangeClient, validate_evm_address


class Command(BaseCommand):
    help = (
        "Withdraw USDC to a destination wallet (on-chain bridge). "
        "Defaults to dry-run unless --execute is passed."
    )

    def add_arguments(self, parser):
        parser.add_argument("--amount", type=float, required=True)
        parser.add_argument(
            "--destination",
            type=str,
            required=True,
            help="0x… address to receive USDC (validated + checksummed).",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Actually submit the signed withdrawal (otherwise print dry-run only).",
        )

    def handle(self, *args, **options):
        signer = SigningModule()
        amt = options["amount"]
        dest = options["destination"]

        if not options["execute"]:
            try:
                dest_ok = validate_evm_address(dest)
            except ValueError as e:
                raise CommandError(str(e)) from e
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN — no transaction sent. Re-run with --execute to submit withdrawal.\n"
                )
            )
            self.stdout.write(
                json.dumps(
                    {
                        "dry_run": True,
                        "amount_usd": amt,
                        "destination": dest_ok,
                        "from_wallet": signer.address,
                        "api_base_url": settings.HYPERLIQUID_API_URL,
                    },
                    indent=2,
                )
            )
            return

        ack = (os.environ.get("HYPERLIQUID_REAL_MONEY_ACK") or "").strip()
        if ack != "I_UNDERSTAND":
            raise CommandError(
                "Refusing --execute: set HYPERLIQUID_REAL_MONEY_ACK=I_UNDERSTAND in .env "
                "to confirm you accept loss of funds / bridge risk."
            )

        ex = ExchangeClient(signer, base_url=settings.HYPERLIQUID_API_URL)
        try:
            r = ex.withdraw_to_wallet(amt, dest)
        except ValueError as e:
            raise CommandError(str(e)) from e
        self.stdout.write(json.dumps(r, default=str, indent=2))
