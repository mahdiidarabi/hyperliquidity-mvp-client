# Hyperliquid Client — MVP Implementation Plan

## Goal

Build a minimal Python client that:
- Loads a private key from `.env` (never exported, never logged)
- Derives the wallet address locally
- Signs all actions using EIP-712 (Hyperliquid's required signing standard)
- Keeps the signing logic in an isolated, swappable module
- Supports: account info, deposit tracking, trading, withdrawals, trade history

---

## Core Concepts

- **Your account = your wallet address** (derived from private key, no registration needed)
- **All write actions = EIP-712 signed messages** sent to `/exchange`
- **All read actions = unsigned POST requests** sent to `/info`
- **Nonce = current timestamp in milliseconds** (not a counter — Hyperliquid requires this)

---

## Architecture

```
Your Code / Trading Engine
        ↓
HyperliquidClient          ← main interface (info + exchange)
        ↓
SigningModule              ← isolated module; reads key from .env; EIP-712 signer
        ↓                    (can be replaced with a remote signing service later)
Hyperliquid API            ← https://api.hyperliquid.xyz  (mainnet)
                              https://api.hyperliquid-testnet.xyz (testnet)
```

### Module Layout

```
hyperliquid_client/
├── .env                        # PRIVATE_KEY=0x...   ← never committed
├── .env.example                # PRIVATE_KEY=0x<your_key_here>
├── .gitignore                  # must include .env
│
├── signing/
│   ├── __init__.py
│   └── signer.py               # SigningModule class — all key logic lives here
│
├── client/
│   ├── __init__.py
│   ├── info.py                 # read-only queries (no signing)
│   └── exchange.py             # write actions (order, cancel, withdraw)
│
├── models/
│   └── types.py                # dataclasses / typed dicts for actions and responses
│
└── main.py                     # entry point / usage example
```

---

## Tech Stack

| Concern | Tool |
|---|---|
| Language | Python 3.11+ |
| Hyperliquid SDK | `hyperliquid-python-sdk` (official) |
| EIP-712 signing | `eth_account` (bundled with SDK) |
| Key loading | `python-dotenv` |
| HTTP | `requests` (via SDK) |
| Types | `dataclasses` / `TypedDict` |
| Env isolation | `.env` file, never committed |

Install:
```bash
pip install hyperliquid-python-sdk python-dotenv
```

---

## SigningModule Design (Modular Boundary)

This is the only place the private key exists in memory. Everything else calls into it.

```python
# signing/signer.py

class SigningModule:
    """
    Isolated signing boundary.
    Currently: loads key from .env.
    Future: can be replaced with a call to a remote signing service (HSM, vault, sidecar).
    """

    def __init__(self):
        # Key is loaded once at startup, held in memory as an Account object
        # It is never returned, logged, or serialized.
        private_key = os.environ["PRIVATE_KEY"]
        self._account = eth_account.Account.from_key(private_key)

    @property
    def address(self) -> str:
        return self._account.address

    def sign_l1_action(self, action: dict, nonce: int, vault_address=None) -> dict:
        # Uses EIP-712 structured signing as required by Hyperliquid
        # Returns the full signed payload ready to POST to /exchange
        ...
```

The `SigningModule` is injected into the `exchange.py` client — it is never instantiated elsewhere.

---

## Implementation Phases

---

### Phase 1 — Project Setup + Signing Module

**Goal:** Establish the project skeleton and prove the key loads and signs correctly.

**Tasks:**
1. Create directory structure and `__init__.py` files
2. Add `.env`, `.env.example`, `.gitignore`
3. Implement `SigningModule` in `signing/signer.py`:
   - Load `PRIVATE_KEY` from `.env` via `python-dotenv`
   - Derive and expose wallet address
   - Implement `sign_l1_action()` using `eth_account` + EIP-712 (as used by `hyperliquid-python-sdk`)
4. Write a minimal smoke test in `main.py` that prints the derived address

**Phase Output:**
```
Wallet address: 0xYourDerivedAddress
Signing module ready.
```
At this point: the key is loaded, address is known, signing works. Nothing has been sent to the API yet.

---

### Phase 2 — Read-Only Info Queries

**Goal:** Fetch account state from Hyperliquid without signing anything.

**Tasks:**
1. Implement `InfoClient` in `client/info.py` wrapping `hyperliquid.info.Info`
2. Expose methods:
   - `get_positions(address)` → open perpetual positions (`clearinghouseState`)
   - `get_open_orders(address)` → open orders (`openOrders`)
   - `get_trade_fills(address)` → trade history (`userFills`)
   - `get_deposits(address)` → deposit history (`userDeposits`)  ← not `userFills`
   - `get_spot_balances(address)` → USDC and spot token balances (`spotClearinghouseState`)
3. Print results in `main.py`

**Phase Output:**
```
Positions:    [...]
Open orders:  [...]
Trade fills:  [...]
Deposits:     [...]
USDC balance: 1000.00
```
At this point: full read visibility into the account. No funds at risk.

---

### Phase 3 — Order Placement and Cancellation

**Goal:** Place and cancel orders using signed actions.

**Tasks:**
1. Implement `ExchangeClient` in `client/exchange.py`:
   - Accept a `SigningModule` instance in constructor (injected, not created internally)
   - Use `int(time.time() * 1000)` as nonce — no DB or Redis needed
2. Implement `place_order(coin, is_buy, size, limit_px, order_type)`:
   - Build the `order` action dict
   - Sign via `signing_module.sign_l1_action(action, nonce)`
   - POST to `/exchange`
3. Implement `cancel_order(coin, order_id)`:
   - Build the `cancel` action dict
   - Same sign + POST flow
4. Test on **testnet** first using `https://api.hyperliquid-testnet.xyz`

**Nonce pattern (correct):**
```python
nonce = int(time.time() * 1000)   # milliseconds — Hyperliquid requirement
```

**Phase Output:**
```
Order placed: { "status": "ok", "response": { "type": "order", "data": { "statuses": ["filled"] } } }
Order cancelled: { "status": "ok" }
```
At this point: full trading capability on testnet, ready to switch to mainnet.

---

### Phase 4 — Withdrawals

**Goal:** Withdraw USDC from Hyperliquid back to an on-chain wallet address.

**Tasks:**
1. Implement `withdraw(destination_address, amount_usd)` in `ExchangeClient`:
   - Use action type `withdraw3` (Hyperliquid's current withdrawal action)
   - Validate `destination_address` is a valid checksummed EVM address before signing
   - Sign and POST to `/exchange`
2. Add a confirmation/dry-run flag to prevent accidental execution

**Correct action format:**
```python
action = {
    "type": "withdraw3",
    "hyperliquidChain": "Mainnet",   # or "Testnet"
    "signatureChainId": "0xa4b1",    # Arbitrum chain ID (hex)
    "destination": "0xYourWalletAddress",
    "amount": "100.0",               # string, USD amount
    "time": nonce,
}
```

**Phase Output:**
```
Withdrawal submitted: { "status": "ok" }
```
At this point: all core flows are working. MVP is complete.

---

## Security Rules

| Rule | Detail |
|---|---|
| `.env` never committed | `.gitignore` must include `.env` from day one |
| Key loaded once | `SigningModule.__init__` only — never re-read or passed around |
| Key never returned | `address` is a property; the raw key string is not exposed |
| Nothing logged | No logging of private key, raw action payloads, or signatures |
| Testnet first | All new flows tested on testnet before mainnet |
| Withdrawal validated | Destination address checked before signing |

---

## Future: Extracting the Signing Module

When you want to move the key off your machine entirely, the only change is inside `signing/signer.py`. The rest of the codebase does not change.

```
Current:  SigningModule reads from .env → signs locally
Future:   SigningModule calls a remote vault/sidecar → returns signature
```

The `ExchangeClient` only ever calls `signing_module.sign_l1_action(action, nonce)` — it has no knowledge of where the key lives.

---

## MVP Checklist

- [ ] Phase 1: Signing module loads key, derives address
- [ ] Phase 2: All read queries working (positions, orders, fills, deposits, balance)
- [ ] Phase 3: Order placement and cancellation on testnet
- [ ] Phase 3: Switch to mainnet
- [ ] Phase 4: Withdrawal flow tested and working
- [ ] `.env` in `.gitignore` verified before first commit
