"""
Signed Hyperliquid /exchange actions via SDK `Exchange` (place/cancel orders).

Uses the same API base URL and signing domain as `signing/env.py` (mainnet vs testnet).
"""
from __future__ import annotations

from typing import Any, Literal

from eth_utils import is_address, to_checksum_address
from hyperliquid.exchange import Exchange
from hyperliquid.utils.signing import OrderType

from signing import SigningModule
from signing.env import hyperliquid_api_base_url

Tif = Literal["Alo", "Ioc", "Gtc"]


def validate_evm_address(addr: str) -> str:
    """Return checksummed address or raise ValueError (no HTTP)."""
    if not is_address(addr):
        raise ValueError("destination must be a valid Ethereum address")
    return to_checksum_address(addr)


class ExchangeClient:
    """Thin wrapper around `hyperliquid.exchange.Exchange` with a `SigningModule`."""

    def __init__(
        self,
        signer: SigningModule,
        *,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        url = base_url if base_url is not None else hyperliquid_api_base_url()
        # SDK compares base_url to its internal mainnet constant for EIP-712; keep HYPERLIQUID_API_URL aligned with official hosts.
        self._ex = Exchange(signer.wallet, base_url=url, timeout=timeout)
        self.base_url = self._ex.base_url

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
        return self._ex.order(coin, is_buy, sz, limit_px, order_type, reduce_only)

    def place_market_order(
        self,
        coin: str,
        is_buy: bool,
        sz: float,
        *,
        slippage: float = Exchange.DEFAULT_SLIPPAGE,
        reduce_only: bool = False,
    ) -> Any:
        # market_open() does not support reduce_only; mirror SDK market_close pattern with IOC.
        if reduce_only:
            px = self._ex._slippage_price(coin, is_buy, slippage, px=None)
            return self._ex.order(
                coin,
                is_buy,
                sz,
                px,
                {"limit": {"tif": "Ioc"}},
                reduce_only=True,
            )
        return self._ex.market_open(coin, is_buy, sz, slippage=slippage)

    def cancel_order(self, coin: str, oid: int) -> Any:
        return self._ex.cancel(coin, oid)

    def usd_class_transfer(self, amount: float, *, to_perp: bool) -> Any:
        """
        Move USDC between spot and perp margin accounts (``usdClassTransfer``).

        ``to_perp=True`` moves from spot → perp; ``False`` moves perp → spot.
        """
        return self._ex.usd_class_transfer(amount, to_perp)

    def withdraw_to_wallet(self, amount: float, destination: str) -> Any:
        """
        Withdraw USDC from Hyperliquid to an EVM address (``withdraw3`` via SDK).

        Destination must be a valid 0x address; stored checksummed for the API.
        """
        dest = validate_evm_address(destination)
        return self._ex.withdraw_from_bridge(amount, dest)
