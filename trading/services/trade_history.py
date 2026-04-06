"""
Trade fill history helpers: notional, grouping by order id, optional fill % via orderStatus.

Raw data comes from `userFills`. `filled_pct_of_orig_sz` needs `orderStatus` + `origSz`
(`--enrich` in the CLI); capped to avoid hammering the API.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from hyperliquid.info import Info


def _f(x: Any) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def enrich_fill_row(fill: dict[str, Any]) -> dict[str, Any]:
    """Add derived fields without removing API keys."""
    out = dict(fill)
    sz = _f(fill.get("sz"))
    px = _f(fill.get("px"))
    out["_notional_usd"] = abs(sz) * px
    return out


def group_fills_by_oid(fills: list[Any]) -> dict[int, list[dict[str, Any]]]:
    by_oid: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for raw in fills:
        if not isinstance(raw, dict):
            continue
        oid = raw.get("oid")
        if isinstance(oid, int):
            by_oid[oid].append(raw)
    return dict(by_oid)


def total_filled_sz(fills: list[dict[str, Any]]) -> float:
    return sum(abs(_f(f.get("sz"))) for f in fills)


def extract_orig_sz_from_order_status(resp: Any) -> float | None:
    """Best-effort parse of `orderStatus` payload for original order size."""
    if not isinstance(resp, dict) or resp.get("status") != "order":
        return None
    outer = resp.get("order")
    if not isinstance(outer, dict):
        return None
    inner = outer.get("order")
    if isinstance(inner, dict) and inner.get("origSz") is not None:
        return _f(inner["origSz"])
    return None


def extract_order_processing_status(resp: Any) -> str | None:
    if not isinstance(resp, dict) or resp.get("status") != "order":
        return None
    outer = resp.get("order")
    if not isinstance(outer, dict):
        return None
    st = outer.get("status")
    return str(st) if st is not None else None


def build_trade_history_report(
    info: Info,
    address: str,
    *,
    enrich_order_status: bool = False,
    max_order_lookups: int = 50,
) -> dict[str, Any]:
    """
    User fills plus grouping and optional per-order fill % (via orderStatus + origSz).

    Fills are returned newest-first from the API; we preserve order in `fills_enriched`.
    """
    raw_fills = info.user_fills(address)
    if not isinstance(raw_fills, list):
        raw_fills = []

    fills_enriched = [enrich_fill_row(f) for f in raw_fills if isinstance(f, dict)]
    by_oid = group_fills_by_oid(raw_fills)

    per_oid: dict[str, Any] = {}
    oids = [oid for oid in by_oid if isinstance(oid, int)]
    if enrich_order_status:
        oids = oids[: max(0, max_order_lookups)]

    order_status: dict[int, Any] = {}
    for oid in oids:
        try:
            order_status[oid] = info.query_order_by_oid(address, oid)
        except Exception as exc:
            order_status[oid] = {"_error": str(exc)}

    for oid, legs in by_oid.items():
        if not isinstance(oid, int):
            continue
        filled = total_filled_sz(legs)
        row: dict[str, Any] = {
            "oid": oid,
            "fill_count": len(legs),
            "total_filled_abs_sz": filled,
            "fills": [enrich_fill_row(x) for x in legs if isinstance(x, dict)],
        }
        orig = None
        if enrich_order_status:
            resp = order_status.get(oid)
            orig = extract_orig_sz_from_order_status(resp)
            row["order_status"] = resp
            row["order_processing_status"] = extract_order_processing_status(resp)
        if orig and orig > 0:
            row["filled_pct_of_orig_sz"] = min(100.0, (filled / orig) * 100.0)
            row["orig_sz_from_order_status"] = orig
        per_oid[str(oid)] = row

    return {
        "address": address,
        "fill_count": len(fills_enriched),
        "fills": fills_enriched,
        "by_order_id": per_oid,
        "order_status_lookups": len(order_status) if enrich_order_status else 0,
    }
