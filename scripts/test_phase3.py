#!/usr/bin/env python3
"""
Phase 3: ExchangeClient wiring, trade history report shape (requires network).

Does not place real orders unless PHASE3_PLACE_SMOKE=1 (optional tiny testnet smoke).
"""
from __future__ import annotations

import os
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
    load_dotenv(root / ".env")
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
    from trading.services import ExchangeClient, InfoClient
    from trading.services.trade_history import build_trade_history_report

    signer = SigningModule()
    if signer.address.lower() != address.lower():
        fail("Signer address mismatch")
        return 1
    ok(f"Signer matches .env address ({address[:10]}…)")

    if settings.HYPERLIQUID_API_URL.rstrip("/") != ExchangeClient(signer).base_url.rstrip("/"):
        fail("HYPERLIQUID_API_URL vs ExchangeClient base_url mismatch")
        return 1
    ok(f"API base aligned: {settings.HYPERLIQUID_API_URL}")

    ic = InfoClient(base_url=settings.HYPERLIQUID_API_URL)
    report = ic.trade_history_report(address, enrich_order_status=False)
    if "fills" not in report or "by_order_id" not in report:
        fail("trade_history_report missing keys")
        return 1
    ok("trade_history_report (no enrich)")

    report2 = build_trade_history_report(ic.raw_info, address, enrich_order_status=False)
    if report2.get("fill_count") != len(report2.get("fills", [])):
        fail("fill_count inconsistent")
        return 1
    ok("build_trade_history_report direct")

    if os.environ.get("PHASE3_PLACE_SMOKE") == "1":
        ex = ExchangeClient(signer, base_url=settings.HYPERLIQUID_API_URL)
        r = ex.place_limit_order(
            "BTC",
            is_buy=True,
            sz=0.0001,
            limit_px=1.0,
            tif="Alo",
            reduce_only=False,
        )
        if not isinstance(r, dict):
            fail("place_order unexpected return type")
            return 1
        ok("PHASE3_PLACE_SMOKE: place_limit_order returned (inspect JSON; may rest or error)")

    print("\nPhase 3 checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
