"""
Variables that must be set in `.env` (see `.env.example`) for `signing/env.py` and `deposit_info`.
"""
from __future__ import annotations

import os

# No defaults: copy values from .env.example into your .env.
REQUIRED_FOR_APP: tuple[str, ...] = (
    "HYPERLIQUID_MAINNET_API_URL",
    "HYPERLIQUID_TESTNET_API_URL",
    "HYPERLIQUID_DOCS_URL",
    "DEPOSIT_USDC_LAYER2_NAME",
    "DEPOSIT_ARBITRUM_CHAIN_ID",
)


def missing_required_env_vars(keys: tuple[str, ...] = REQUIRED_FOR_APP) -> list[str]:
    return [k for k in keys if not (os.environ.get(k) or "").strip()]
