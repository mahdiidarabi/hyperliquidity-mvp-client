"""
Hyperliquid network selection from environment (no Django).

- HYPERLIQUID_MAINNET: when HYPERLIQUID_API_URL is unset, picks mainnet vs testnet API base.
- HYPERLIQUID_API_URL: optional override. If set to the official mainnet or testnet URL, signing
  uses the matching EIP-712 domain so reads and writes stay consistent.
"""
from __future__ import annotations

import os

from hyperliquid.utils.constants import MAINNET_API_URL, TESTNET_API_URL

_MAINNET_TRUTHY = frozenset({"1", "true", "yes"})


def env_flag_hyperliquid_mainnet() -> bool:
    """Raw HYPERLIQUID_MAINNET interpretation (default: mainnet)."""
    return os.environ.get("HYPERLIQUID_MAINNET", "true").strip().lower() in _MAINNET_TRUTHY


def hyperliquid_api_base_url() -> str:
    """HTTP base URL for Info / Exchange (no trailing slash)."""
    explicit = (os.environ.get("HYPERLIQUID_API_URL") or "").strip()
    if explicit:
        return explicit.rstrip("/")
    return MAINNET_API_URL if env_flag_hyperliquid_mainnet() else TESTNET_API_URL


def hyperliquid_signing_is_mainnet() -> bool:
    """
    Whether L1 actions use the mainnet EIP-712 domain.

    If HYPERLIQUID_API_URL points at the official mainnet or testnet host, that wins.
    Otherwise HYPERLIQUID_MAINNET decides (for custom / local URLs).
    """
    explicit = (os.environ.get("HYPERLIQUID_API_URL") or "").strip()
    if explicit:
        u = explicit.rstrip("/").lower()
        if u == MAINNET_API_URL.rstrip("/").lower():
            return True
        if u == TESTNET_API_URL.rstrip("/").lower():
            return False
    return env_flag_hyperliquid_mainnet()
