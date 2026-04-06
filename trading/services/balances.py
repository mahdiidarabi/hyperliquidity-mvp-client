"""
Normalize perp vs spot balance fields from Hyperliquid /info for display and CLI.
"""
from __future__ import annotations

from typing import Any

from hyperliquid.info import Info


def _sf(x: Any) -> float | None:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def summarize_account_balances(info: Info, address: str, dex: str = "") -> dict[str, Any]:
    """
    Perp (clearinghouse) vs spot balances.

    - **Perp trading**: margin summary, withdrawable USDC to chain, open positions count.
    - **Spot**: token rows from `spotClearinghouseState` (USDC and spot tokens).
    """
    perp_raw = info.user_state(address, dex=dex)
    spot_raw = info.spot_user_state(address)

    perp: dict[str, Any] = {"raw_clearinghouse": perp_raw}
    if isinstance(perp_raw, dict):
        perp["withdrawable_usd"] = _sf(perp_raw.get("withdrawable"))
        ms = perp_raw.get("marginSummary")
        if isinstance(ms, dict):
            perp["account_value_usd"] = _sf(ms.get("accountValue"))
            perp["total_margin_used_usd"] = _sf(ms.get("totalMarginUsed"))
        cms = perp_raw.get("crossMarginSummary")
        if isinstance(cms, dict):
            perp["cross_account_value_usd"] = _sf(cms.get("accountValue"))
        ap = perp_raw.get("assetPositions")
        if isinstance(ap, list):
            perp["open_positions_count"] = len(ap)

    spot: dict[str, Any] = {"raw_spot_clearinghouse": spot_raw}
    if isinstance(spot_raw, dict):
        balances = spot_raw.get("balances")
        rows: list[dict[str, Any]] = []
        if isinstance(balances, list):
            for b in balances:
                if not isinstance(b, dict):
                    continue
                coin = b.get("coin")
                total = _sf(b.get("total"))
                hold = _sf(b.get("hold"))
                free = None
                if total is not None and hold is not None:
                    free = total - hold
                rows.append(
                    {
                        "coin": coin,
                        "total": total,
                        "hold": hold,
                        "available_estimate": free,
                    }
                )
        spot["balances"] = rows

    return {
        "address": address,
        "perp": perp,
        "spot": spot,
    }
