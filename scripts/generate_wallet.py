#!/usr/bin/env python3
"""
Generate a new secp256k1 private key, the corresponding public key, and Ethereum address.

Usage:
  python scripts/generate_wallet.py              # print values (do not write files)
  python scripts/generate_wallet.py --write-env  # set PRIVATE_KEY in project .env

Requires: eth-account, eth-keys (installed with project requirements).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from eth_account import Account
from eth_keys import keys as eth_keys


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def normalize_private_key(raw: str) -> str:
    s = raw.strip()
    if not s.startswith("0x"):
        s = "0x" + s
    return s


def write_private_key_to_env(env_path: Path, private_key_hex: str) -> None:
    private_key_hex = normalize_private_key(private_key_hex)
    line = f"PRIVATE_KEY={private_key_hex}\n"

    if env_path.is_file():
        text = env_path.read_text(encoding="utf-8")
        lines = text.splitlines(keepends=True)
        pat = re.compile(r"^\s*PRIVATE_KEY\s*=")
        replaced = False
        out: list[str] = []
        for ln in lines:
            if pat.match(ln):
                if not replaced:
                    out.append(line)
                    replaced = True
                # skip duplicate PRIVATE_KEY lines
                continue
            out.append(ln)
        if not replaced:
            if out and not out[-1].endswith("\n"):
                out[-1] = out[-1] + "\n"
            out.append(line)
        env_path.write_text("".join(out), encoding="utf-8")
    else:
        env_path.write_text(line, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate wallet key material for local testing.")
    parser.add_argument(
        "--write-env",
        action="store_true",
        help=f"Write PRIVATE_KEY to {repo_root() / '.env'} (creates or updates that line only).",
    )
    args = parser.parse_args()

    acct = Account.create()
    private_hex = normalize_private_key(acct.key.hex())

    priv = eth_keys.PrivateKey(acct.key)
    public_hex = priv.public_key.to_hex()

    print("Generated wallet (keep the private key secret; never commit it):")
    print(f"  private_key: {private_hex}")
    print(f"  public_key:  {public_hex}")
    print(f"  address:     {acct.address}")

    if args.write_env:
        env_path = repo_root() / ".env"
        write_private_key_to_env(env_path, private_hex)
        print(f"\nWrote PRIVATE_KEY to {env_path}")

    else:
        print("\nTo use with this project, add to .env:")
        print(f"  PRIVATE_KEY={private_hex}")
        print("\nOr run: python scripts/generate_wallet.py --write-env")

    return 0


if __name__ == "__main__":
    sys.exit(main())
