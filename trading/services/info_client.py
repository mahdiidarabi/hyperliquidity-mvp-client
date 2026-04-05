"""
Read-only Hyperliquid /info client. No signing, no private key — only address-based queries.
"""
from __future__ import annotations

from typing import Any

from hyperliquid.info import Info

from signing.env import hyperliquid_api_base_url


def default_base_url() -> str:
    return hyperliquid_api_base_url()


class InfoClient:
    """
    Thin wrapper around hyperliquid.info.Info with WebSocket disabled (suitable for scripts).
    """

    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        url = base_url if base_url is not None else default_base_url()
        self._info = Info(base_url=url, skip_ws=True, timeout=timeout)
        self.base_url = self._info.base_url

    def get_clearinghouse_state(self, address: str, dex: str = "") -> Any:
        """Full perp clearinghouse payload (positions, margin summary, withdrawable, …)."""
        return self._info.user_state(address, dex=dex)

    def get_positions(self, address: str, dex: str = "") -> Any:
        """Open perpetual positions: `assetPositions` from clearinghouse state."""
        state = self.get_clearinghouse_state(address, dex=dex)
        return state.get("assetPositions", [])

    def get_open_orders(self, address: str, dex: str = "") -> Any:
        return self._info.open_orders(address, dex=dex)

    def get_trade_fills(self, address: str) -> Any:
        return self._info.user_fills(address)

    def get_deposits(
        self,
        address: str,
        *,
        start_time_ms: int = 0,
        end_time_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Bridge deposits from non-funding ledger updates (`delta.type == "deposit"`).
        Hyperliquid does not expose a separate `userDeposits` info method in the public API.
        """
        raw = self._info.user_non_funding_ledger_updates(
            address, start_time_ms, end_time_ms
        )
        if not isinstance(raw, list):
            return []
        out: list[dict[str, Any]] = []
        for row in raw:
            if not isinstance(row, dict):
                continue
            delta = row.get("delta")
            if isinstance(delta, dict) and delta.get("type") == "deposit":
                out.append(row)
        return out

    def get_spot_clearinghouse_state(self, address: str) -> Any:
        """Spot balances / spot clearinghouse state (includes USDC and tokens)."""
        return self._info.spot_user_state(address)

    def snapshot(self, address: str, dex: str = "") -> dict[str, Any]:
        """Single call-site bundle for dashboards and smoke tests."""
        return {
            "address": address,
            "base_url": self.base_url,
            "clearinghouse": self.get_clearinghouse_state(address, dex=dex),
            "positions": self.get_positions(address, dex=dex),
            "open_orders": self.get_open_orders(address, dex=dex),
            "fills": self.get_trade_fills(address),
            "deposits": self.get_deposits(address),
            "spot": self.get_spot_clearinghouse_state(address),
        }
