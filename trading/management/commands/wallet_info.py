"""CLI: wallet address from PRIVATE_KEY + deposit / network guidance (read-only text + JSON)."""
import json

from django.core.management.base import BaseCommand

from signing import SigningModule
from trading.deposit_info import deposit_network_summary


class Command(BaseCommand):
    help = (
        "Show the trading wallet address and deposit-network guidance. "
        "Does not send transactions; use the official Hyperliquid UI to bridge USDC."
    )

    def add_arguments(self, parser):
        parser.add_argument("--indent", type=int, default=2)

    def handle(self, *args, **options):
        signer = SigningModule()
        addr = signer.address
        dep = deposit_network_summary()

        self.stdout.write(f"Wallet address (Hyperliquid / Arbitrum same 0x): {addr}\n")
        self.stdout.write(f"Deposit / network summary:\n{dep.get('note', '')}\n")
        self.stdout.write(f"API base: {dep.get('api_base_url')}\n")
        self.stdout.write(f"Docs: {dep.get('docs')}\n")

        ind = options["indent"]
        payload = {"wallet_address": addr, **dep}
        self.stdout.write("\nJSON:\n")
        self.stdout.write(json.dumps(payload, indent=ind if ind > 0 else None, default=str))
