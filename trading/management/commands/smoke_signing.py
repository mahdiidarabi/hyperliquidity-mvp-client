"""Offline signing smoke test (no HTTP)."""
import time

from django.core.management.base import BaseCommand

from signing import SigningModule


class Command(BaseCommand):
    help = "Verify PRIVATE_KEY loads and L1 signing runs (does not call the API)."

    def handle(self, *args, **options):
        signer = SigningModule()
        self.stdout.write(f"Wallet address: {signer.address}")

        nonce = int(time.time() * 1000)
        action = {"type": "scheduleCancel"}
        sig = signer.sign_l1_action(action, nonce, vault_address=None)
        if isinstance(sig, dict) and sig.get("r") and sig.get("s") and sig.get("v") is not None:
            self.stdout.write(self.style.SUCCESS("L1 signature produced (smoke): ok"))
        else:
            self.stdout.write(self.style.WARNING("L1 signature produced (smoke): unexpected shape"))
