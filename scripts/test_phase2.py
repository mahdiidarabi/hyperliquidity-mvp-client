#!/usr/bin/env python3
"""
Phase 2: verify read-only Info client against the live Hyperliquid API (requires network).

Uses PRIVATE_KEY from .env only to derive the queried address — no signing.
Exit 0 on success.
"""
from __future__ import annotations

import json
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
        fail("PRIVATE_KEY missing in .env")
        return 1

    try:
        address = Account.from_key(raw).address
    except Exception as e:
        fail(f"Invalid PRIVATE_KEY: {e}")
        return 1

    os.chdir(root)

    from trading.services import InfoClient

    try:
        client = InfoClient()
    except Exception as e:
        fail(f"InfoClient init failed: {e}")
        return 1

    ok(f"API base URL: {client.base_url}")

    try:
        ch = client.get_clearinghouse_state(address)
        orders = client.get_open_orders(address)
        fills = client.get_trade_fills(address)
        deposits = client.get_deposits(address)
        spot = client.get_spot_clearinghouse_state(address)
        positions = client.get_positions(address)
    except Exception as e:
        fail(f"API request failed: {e}")
        return 1

    if not isinstance(ch, dict):
        fail(f"clearinghouse state should be dict, got {type(ch)}")
        return 1
    ok("clearinghouse state (dict)")

    for name, val in (
        ("positions", positions),
        ("open_orders", orders),
        ("fills", fills),
        ("deposits", deposits),
    ):
        if not isinstance(val, list):
            fail(f"{name} should be list, got {type(val)}")
            return 1
        ok(f"{name} (list, len={len(val)})")

    if not isinstance(spot, dict):
        fail(f"spot state should be dict, got {type(spot)}")
        return 1
    ok("spot clearinghouse (dict)")

    manage = root / "manage.py"
    try:
        proc = subprocess.run(
            [sys.executable, str(manage), "info_snapshot", "--indent", "0"],
            cwd=root,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        fail("manage.py info_snapshot timed out")
        return 1

    if proc.returncode != 0:
        fail("manage.py info_snapshot failed")
        if proc.stderr:
            print(proc.stderr, file=sys.stderr)
        if proc.stdout:
            print(proc.stdout, file=sys.stderr)
        return 1

    try:
        parsed = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"info_snapshot stdout is not JSON: {e}")
        return 1

    if parsed.get("address", "").lower() != address.lower():
        fail("snapshot address mismatch")
        return 1
    ok("manage.py info_snapshot JSON")

    print("\nPhase 2 checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
