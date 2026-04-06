"""
Signed Hyperliquid /exchange actions via message-signature boundary.

ExchangeClient builds an action message, sends only that message to `SigningModule`,
receives the signature, then posts the final transaction payload.
"""
from __future__ import annotations

from typing import Any, Literal

from eth_utils import is_address, to_checksum_address
from hyperliquid.api import API
from hyperliquid.info import Info
from hyperliquid.utils.signing import (
    OrderType,
    get_timestamp_ms,
    order_request_to_order_wire,
    order_wires_to_order_action,
)

from signing import SigningModule
from signing.env import hyperliquid_api_base_url

Tif = Literal["Alo", "Ioc", "Gtc"]


def validate_evm_address(addr: str) -> str:
    """Return checksummed address or raise ValueError (no HTTP)."""
    if not is_address(addr):
        raise ValueError("destination must be a valid Ethereum address")
    return to_checksum_address(addr)


class ExchangeClient:
    """Build, sign, and submit /exchange payloads via SigningModule."""

    DEFAULT_SLIPPAGE = 0.05

    def __init__(
        self,
        signer: SigningModule,
        *,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        url = base_url if base_url is not None else hyperliquid_api_base_url()
        self._signer = signer
        self._api = API(base_url=url, timeout=timeout)
        # skip_ws=True: CLI/services do one-shot calls and do not need a background websocket.
        self._info = Info(base_url=url, skip_ws=True, timeout=timeout)
        self.base_url = self._api.base_url

    def _post_action(self, action: dict[str, Any], signature: Any, nonce: int) -> Any:
        payload = {
            "action": action,
            "nonce": nonce,
            "signature": signature,
            "vaultAddress": None if action.get("type") == "usdClassTransfer" else None,
            "expiresAfter": self._signer.expires_after,
        }
        return self._api.post("/exchange", payload)

    def _slippage_price(
        self,
        name: str,
        is_buy: bool,
        slippage: float,
        px: float | None = None,
    ) -> float:
        coin = self._info.name_to_coin[name]
        if px is None:
            dex = coin.split(":")[0] if ":" in coin else ""
            px = float(self._info.all_mids(dex)[coin])

        asset = self._info.coin_to_asset[coin]
        is_spot = asset >= 10_000
        px *= (1 + slippage) if is_buy else (1 - slippage)
        return round(float(f"{px:.5g}"), (6 if not is_spot else 8) - self._info.asset_to_sz_decimals[asset])

    def place_limit_order(
        self,
        coin: str,
        is_buy: bool,
        sz: float,
        limit_px: float,
        *,
        tif: Tif = "Gtc",
        reduce_only: bool = False,
    ) -> Any:
        order_type: OrderType = {"limit": {"tif": tif}}
        order_request = {
            "coin": coin,
            "is_buy": is_buy,
            "sz": sz,
            "limit_px": limit_px,
            "order_type": order_type,
            "reduce_only": reduce_only,
        }
        order_wire = order_request_to_order_wire(order_request, self._info.name_to_asset(coin))
        action = order_wires_to_order_action([order_wire], builder=None, grouping="na")
        nonce = get_timestamp_ms()
        signature = self._signer.sign_l1_action(action, nonce, vault_address=None)
        return self._post_action(action, signature, nonce)

    def place_market_order(
        self,
        coin: str,
        is_buy: bool,
        sz: float,
        *,
        slippage: float = DEFAULT_SLIPPAGE,
        reduce_only: bool = False,
    ) -> Any:
        # Hyperliquid market orders are aggressive IOC limits.
        px = self._slippage_price(coin, is_buy, slippage, px=None)
        return self.place_limit_order(
            coin=coin,
            is_buy=is_buy,
            sz=sz,
            limit_px=px,
            tif="Ioc",
            reduce_only=reduce_only,
        )

    def cancel_order(self, coin: str, oid: int) -> Any:
        nonce = get_timestamp_ms()
        action = {
            "type": "cancel",
            "cancels": [
                {
                    "a": self._info.name_to_asset(coin),
                    "o": oid,
                }
            ],
        }
        signature = self._signer.sign_l1_action(action, nonce, vault_address=None)
        return self._post_action(action, signature, nonce)

    def usd_class_transfer(self, amount: float, *, to_perp: bool) -> Any:
        """
        Move USDC between spot and perp margin accounts (``usdClassTransfer``).

        ``to_perp=True`` moves from spot → perp; ``False`` moves perp → spot.
        """
        nonce = get_timestamp_ms()
        action = {
            "type": "usdClassTransfer",
            "amount": str(amount),
            "toPerp": to_perp,
            "nonce": nonce,
        }
        signature = self._signer.sign_usd_class_transfer_action(action)
        return self._post_action(action, signature, nonce)

    def withdraw_to_wallet(self, amount: float, destination: str) -> Any:
        """
        Withdraw USDC from Hyperliquid to an EVM address (``withdraw3`` via SDK).

        Destination must be a valid 0x address; stored checksummed for the API.
        """
        dest = validate_evm_address(destination)
        nonce = get_timestamp_ms()
        action = {"destination": dest, "amount": str(amount), "time": nonce, "type": "withdraw3"}
        signature = self._signer.sign_withdraw_from_bridge_action(action)
        return self._post_action(action, signature, nonce)
