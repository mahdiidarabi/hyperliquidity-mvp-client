"""
Read-only Hyperliquid /info client. No signing, no private key — only address-based queries.

`Info(..., skip_ws=True)` avoids a background WebSocket thread (appropriate for scripts).
First use may hit the network to load meta; that can take a while.
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

    @property
    def raw_info(self) -> Info:
        """Underlying SDK `Info` (for advanced callers)."""
        return self._info

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

    def get_order_status(self, address: str, oid: int) -> Any:
        return self._info.query_order_by_oid(address, oid)

    def trade_history_report(
        self,
        address: str,
        *,
        enrich_order_status: bool = False,
        max_order_lookups: int = 50,
    ) -> dict[str, Any]:
        # Lazy import keeps `trade_history` optional for callers that only need snapshots.
        from trading.services.trade_history import build_trade_history_report

        return build_trade_history_report(
            self._info,
            address,
            enrich_order_status=enrich_order_status,
            max_order_lookups=max_order_lookups,
        )

    def list_symbols(self) -> dict[str, Any]:
        """Perp and spot instrument names as understood by the API (for `--coin`).

        Perpetuals include the **default** DEX (`meta` with ``dex=""``) and every
        **builder / HIP-3** DEX from `perpDexs` (e.g. ``xyz`` → coins like ``xyz:CL``).
        Calling `meta()` without a dex only returns the primary universe; oil and other
        deployed markets live under non-empty `dex` values.
        """
        spot = self._info.spot_meta()
        spots = [u["name"] for u in spot.get("universe", []) if isinstance(u, dict) and "name" in u]

        perps: list[str] = []
        perp_by_dex: list[dict[str, Any]] = []

        main = self._info.meta(dex="")
        main_names = [u["name"] for u in main.get("universe", []) if isinstance(u, dict) and "name" in u]
        perps.extend(main_names)
        perp_by_dex.append({"dex": "", "assets": main_names})

        dex_list = self._info.perp_dexs()
        if isinstance(dex_list, list):
            for entry in dex_list:
                if not isinstance(entry, dict):
                    continue
                dex_name = entry.get("name")
                if not dex_name:
                    continue
                m = self._info.meta(dex=dex_name)
                row = [u["name"] for u in m.get("universe", []) if isinstance(u, dict) and "name" in u]
                perps.extend(row)
                perp_by_dex.append({"dex": dex_name, "assets": row})

        return {
            "base_url": self.base_url,
            "perp": perps,
            "spot": spots,
            "perp_by_dex": perp_by_dex,
        }

    def get_account_balances(self, address: str, dex: str = "") -> dict[str, Any]:
        """Structured perp vs spot balances (see `trading.services.balances`)."""
        from trading.services.balances import summarize_account_balances

        return summarize_account_balances(self._info, address, dex=dex)
