#!/usr/bin/env python3
"""
Verify Phase 1: .env PRIVATE_KEY, SigningModule address match, L1 smoke signature, Django command.

Exit code 0 = all checks passed, non-zero = failure.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
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
        fail(f"Missing {env_path}. Run: python scripts/generate_wallet.py --write-env")
        return 1

    load_dotenv(env_path)
    sys.path.insert(0, str(root))

    from signing.required_env import missing_required_env_vars

    miss = missing_required_env_vars()
    if miss:
        fail(f"Missing env vars (copy from .env.example): {', '.join(miss)}")
        return 1

    raw = os.environ.get("PRIVATE_KEY")
    if not raw or not str(raw).strip():
        fail("PRIVATE_KEY is empty in .env")
        return 1

    try:
        expected_acct = Account.from_key(raw)
    except Exception as e:
        fail(f"Invalid PRIVATE_KEY: {e}")
        return 1

    os.chdir(root)

    from signing import SigningModule

    signer = SigningModule()
    if signer.address.lower() != expected_acct.address.lower():
        fail(f"Address mismatch: SigningModule={signer.address} eth_account={expected_acct.address}")
        return 1
    ok(f"SigningModule address matches eth_account ({signer.address})")

    nonce = int(time.time() * 1000)
    action = {"type": "scheduleCancel"}
    try:
        sig = signer.sign_l1_action(action, nonce, vault_address=None)
    except Exception as e:
        fail(f"L1 sign raised: {e}")
        return 1

    if not isinstance(sig, dict) or not sig.get("r") or not sig.get("s") or sig.get("v") is None:
        fail(f"Unexpected signature shape: {sig!r}")
        return 1
    ok("L1 signature (scheduleCancel, local only)")

    manage = root / "manage.py"
    if not manage.is_file():
        fail(f"Missing {manage}")
        return 1

    try:
        subprocess.run(
            [sys.executable, str(manage), "smoke_signing"],
            cwd=root,
            env=os.environ.copy(),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        fail("manage.py smoke_signing failed")
        if e.stdout:
            print(e.stdout, file=sys.stderr)
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        return 1

    ok("manage.py smoke_signing")
    print("\nPhase 1 checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
