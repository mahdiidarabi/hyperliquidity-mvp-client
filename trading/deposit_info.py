"""
Deposit / bridge context for README and `wallet_info` (no private keys).

All display strings and URLs come from environment variables — see `.env.example`.
"""
from __future__ import annotations

import os

from signing.env import hyperliquid_api_base_url


def _required(key: str) -> str:
    v = (os.environ.get(key) or "").strip()
    if not v:
        raise RuntimeError(
            f"Missing required environment variable {key}. See .env.example."
        )
    return v


def deposit_network_summary() -> dict[str, str]:
    """
    Human-oriented summary for USDC deposit network (mainnet vs testnet) from env only.
    """
    api = hyperliquid_api_base_url()
    docs = _required("HYPERLIQUID_DOCS_URL")
    testnet_canonical = _required("HYPERLIQUID_TESTNET_API_URL").rstrip("/").lower()

    if api.rstrip("/").lower() == testnet_canonical:
        return {
            "hyperliquid_environment": os.environ.get(
                "DEPOSIT_LABEL_TESTNET", "testnet API"
            ),
            "usdc_deposit_layer2": os.environ.get(
                "DEPOSIT_TESTNET_LAYER2_HINT", "See HYPERLIQUID_DOCS_URL"
            ),
            "arbitrum_chain_id": os.environ.get("DEPOSIT_TESTNET_CHAIN_ID", "N/A"),
            "note": os.environ.get(
                "DEPOSIT_TESTNET_NOTE",
                "Testnet funding differs from mainnet; follow official testnet instructions.",
            ),
            "docs": docs,
            "api_base_url": api,
        }

    return {
        "hyperliquid_environment": os.environ.get(
            "DEPOSIT_LABEL_MAINNET", "mainnet (production API)"
        ),
        "usdc_deposit_layer2": _required("DEPOSIT_USDC_LAYER2_NAME"),
        "arbitrum_chain_id": _required("DEPOSIT_ARBITRUM_CHAIN_ID"),
        "note": os.environ.get(
            "DEPOSIT_MAINNET_NOTE",
            "Deposit USDC via the official Hyperliquid bridge UI; your trading wallet "
            "address is the same 0x address derived from PRIVATE_KEY. "
            "Do not send funds to random addresses — use only the in-app deposit flow.",
        ),
        "docs": docs,
        "api_base_url": api,
    }
