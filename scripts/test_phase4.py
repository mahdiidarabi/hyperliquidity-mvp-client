#!/usr/bin/env python3
"""
Phase 4: withdraw wiring, env-driven URLs, dry-run CLI, real-money guard.

- Does not submit a withdrawal unless PHASE4_LIVE_WITHDRAW=1 (optional; still needs --execute via subprocess test).
- By default: validates ExchangeClient, env, invalid address, manage.py withdraw dry-run,
  and that --execute fails without HYPERLIQUID_REAL_MONEY_ACK.

Requires network only for optional live checks; core tests are local.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from eth_account import Account


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)


def ok(msg: str) -> None:
    print(f"OK:   {msg}")


def main() -> int:
    root = repo_root()
    env_path = root / ".env"
    if not env_path.is_file():
        fail(f"Missing {env_path}")
        return 1

    load_dotenv(env_path)
    sys.path.insert(0, str(root))

    from signing.required_env import missing_required_env_vars

    miss = missing_required_env_vars()
    if miss:
        fail(f"Missing env vars (copy from .env.example): {', '.join(miss)}")
        return 1

    raw = os.environ.get("PRIVATE_KEY", "").strip()
    if not raw:
        fail("PRIVATE_KEY missing")
        return 1

    try:
        address = Account.from_key(raw).address
    except Exception as e:
        fail(f"Bad PRIVATE_KEY: {e}")
        return 1

    os.chdir(root)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()

    from django.conf import settings

    from signing import SigningModule
    from signing.env import hyperliquid_api_base_url
    from trading.services.exchange_client import validate_evm_address

    if not settings.HYPERLIQUID_API_URL:
        fail("HYPERLIQUID_API_URL resolution empty")
        return 1
    ok(f"HYPERLIQUID_API_URL = {settings.HYPERLIQUID_API_URL}")

    url = hyperliquid_api_base_url()
    if url.rstrip("/") != settings.HYPERLIQUID_API_URL.rstrip("/"):
        fail("settings vs hyperliquid_api_base_url mismatch")
        return 1
    ok("signing/env URL matches Django settings")

    signer = SigningModule()
    if signer.address.lower() != address.lower():
        fail("Signer address mismatch")
        return 1

    try:
        validate_evm_address("not_an_address")
    except ValueError:
        ok("validate_evm_address rejects invalid destination (no HTTP)")
    else:
        fail("expected ValueError for invalid destination")
        return 1

    # Dry-run withdraw (no --execute)
    proc = subprocess.run(
        [
            sys.executable,
            str(root / "manage.py"),
            "withdraw",
            "--amount",
            "0.01",
            "--destination",
            "0x0000000000000000000000000000000000000001",
        ],
        cwd=root,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        fail("manage.py withdraw dry-run failed")
        print(proc.stderr, file=sys.stderr)
        print(proc.stdout, file=sys.stderr)
        return 1
    if "DRY RUN" not in proc.stdout:
        fail("dry-run output missing DRY RUN marker")
        return 1
    ok("manage.py withdraw dry-run")

    # --execute without REAL_MONEY_ACK must fail
    env_no_ack = os.environ.copy()
    env_no_ack.pop("HYPERLIQUID_REAL_MONEY_ACK", None)
    proc2 = subprocess.run(
        [
            sys.executable,
            str(root / "manage.py"),
            "withdraw",
            "--amount",
            "0.01",
            "--destination",
            "0x0000000000000000000000000000000000000001",
            "--execute",
        ],
        cwd=root,
        env=env_no_ack,
        capture_output=True,
        text=True,
    )
    if proc2.returncode == 0:
        fail("withdraw --execute should fail without HYPERLIQUID_REAL_MONEY_ACK")
        return 1
    ok("withdraw --execute blocked without REAL_MONEY_ACK")

    print("\nPhase 4 checks passed.")
    print(
        "To submit a real withdrawal: set HYPERLIQUID_REAL_MONEY_ACK=I_UNDERSTAND in .env, "
        "then run `python manage.py withdraw --amount … --destination 0x… --execute`."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
