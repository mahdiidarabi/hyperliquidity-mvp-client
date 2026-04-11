"""
EIP-712 L1 signing for Hyperliquid actions.

`SigningModule` is the only module that reads `PRIVATE_KEY` from the environment.
Network (mainnet vs testnet) for signing matches `signing.env.hyperliquid_signing_is_mainnet`.
"""
import os
from typing import Any

from eth_account import Account
from eth_account.signers.local import LocalAccount
from hyperliquid.utils.signing import (
    sign_l1_action as hl_sign_l1_action,
    sign_send_asset_action as hl_sign_send_asset_action,
    sign_usd_class_transfer_action,
    sign_withdraw_from_bridge_action,
)

from signing.env import hyperliquid_signing_is_mainnet


class SigningModule:
    """
    Isolated signing boundary. Loads PRIVATE_KEY from the environment once.
    """

    def __init__(
        self,
        *,
        is_mainnet: bool | None = None,
        expires_after: int | None = None,
    ) -> None:
        raw = os.environ.get("PRIVATE_KEY")
        if not raw:
            raise RuntimeError("PRIVATE_KEY is not set in the environment (.env).")
        self._account: LocalAccount = Account.from_key(raw)
        if is_mainnet is None:
            is_mainnet = hyperliquid_signing_is_mainnet()
        self._is_mainnet = is_mainnet
        self._expires_after = expires_after

    @property
    def address(self) -> str:
        return self._account.address

    @property
    def expires_after(self) -> int | None:
        return self._expires_after

    def sign_l1_action(
        self,
        action: dict[str, Any],
        nonce: int,
        vault_address: str | None = None,
    ) -> Any:
        return hl_sign_l1_action(
            self._account,
            action,
            vault_address,
            nonce,
            self._expires_after,
            self._is_mainnet,
        )

    def sign_usd_class_transfer_action(self, action: dict[str, Any]) -> Any:
        return sign_usd_class_transfer_action(self._account, action, self._is_mainnet)

    def sign_withdraw_from_bridge_action(self, action: dict[str, Any]) -> Any:
        return sign_withdraw_from_bridge_action(self._account, action, self._is_mainnet)

    def sign_send_asset_action(self, action: dict[str, Any]) -> Any:
        """User-signed EIP-712 action (not L1 phantom agent)."""
        return hl_sign_send_asset_action(self._account, action, self._is_mainnet)
