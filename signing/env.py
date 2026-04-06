"""
Hyperliquid network selection from environment (no Django, no hardcoded API URLs).

Required variables are listed in `.env.example`. Canonical mainnet/testnet API bases are used
to pick EIP-712 signing domain and to match the SDK’s internal checks when URLs align.
"""
from __future__ import annotations

import os

_MAINNET_TRUTHY = frozenset({"1", "true", "yes"})


def _required(key: str) -> str:
    v = (os.environ.get(key) or "").strip()
    if not v:
        raise RuntimeError(
            f"Missing required environment variable {key}. Copy .env.example to .env and set it."
        )
    return v


def env_flag_hyperliquid_mainnet() -> bool:
    """Raw HYPERLIQUID_MAINNET interpretation (default: mainnet)."""
    return os.environ.get("HYPERLIQUID_MAINNET", "true").strip().lower() in _MAINNET_TRUTHY


def hyperliquid_api_base_url() -> str:
    """
    Active HTTP API base (no trailing slash).

    If HYPERLIQUID_API_URL is set, it wins. Otherwise uses HYPERLIQUID_MAINNET + canonical
    HYPERLIQUID_MAINNET_API_URL / HYPERLIQUID_TESTNET_API_URL.
    """
    explicit = (os.environ.get("HYPERLIQUID_API_URL") or "").strip()
    if explicit:
        return explicit.rstrip("/")
    m = _required("HYPERLIQUID_MAINNET_API_URL").rstrip("/")
    t = _required("HYPERLIQUID_TESTNET_API_URL").rstrip("/")
    return m if env_flag_hyperliquid_mainnet() else t


def hyperliquid_signing_is_mainnet() -> bool:
    """
    Whether L1 actions use the mainnet EIP-712 domain.

    Compares the active API URL to HYPERLIQUID_MAINNET_API_URL / HYPERLIQUID_TESTNET_API_URL.
    If neither matches (custom URL), falls back to HYPERLIQUID_MAINNET.
    """
    u = hyperliquid_api_base_url().lower()
    m = _required("HYPERLIQUID_MAINNET_API_URL").rstrip("/").lower()
    t = _required("HYPERLIQUID_TESTNET_API_URL").rstrip("/").lower()
    if u == m:
        return True
    if u == t:
        return False
    return env_flag_hyperliquid_mainnet()
