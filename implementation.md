# Hyperliquid Client — MVP Implementation Plan (Django)

## Goal

Build a minimal **Django** app that wraps a Python Hyperliquid client:

- Loads a private key from `.env` (never stored in the database, never logged)
- Derives the wallet address locally
- Signs write actions with EIP-712 via the official SDK’s signing helpers
- Keeps signing in an isolated, swappable `signing/` package (usable outside Django)
- Uses **simple models and Django admin** only for non-secret metadata (labels, testnet flag)
- Eventually supports: account info, deposit tracking, trading, withdrawals, trade history

---

## Core Concepts

- **Your account = your wallet address** (derived from the private key in `.env`)
- **All write actions = EIP-712 signed messages** posted to `/exchange`
- **All read actions = unsigned POST requests** to `/info`
- **Nonce = current timestamp in milliseconds** (Hyperliquid requirement)

---

## Architecture

```
Django (admin + optional views later)
        ↓
trading/services (InfoClient today; Exchange later)   ← info + (future) exchange
        ↓
SigningModule (signing/signer.py)              ← reads PRIVATE_KEY from env; EIP-712
        ↓
Hyperliquid API
  https://api.hyperliquid.xyz (mainnet)
  https://api.hyperliquid-testnet.xyz (testnet)
```

### Repository Layout

```
.
├── manage.py
├── requirements.txt
├── .env.example
├── .env                         # PRIVATE_KEY=0x...  ← never committed
│
├── config/                      # Django project settings, urls, wsgi
│   ├── settings.py
│   └── ...
│
├── trading/                     # Django app — simple models + admin
│   ├── models.py                # TradingAccount (metadata only)
│   ├── admin.py
│   ├── services/
│   │   ├── info_client.py       # InfoClient (read-only /info)
│   │   ├── exchange_client.py   # ExchangeClient (signed /exchange orders)
│   │   └── trade_history.py     # fills + optional fill % via orderStatus
│   └── management/commands/     # smoke_signing, info_snapshot, place_order, …
│
├── signing/                     # Plain Python; no Django imports
│   ├── __init__.py
│   ├── env.py                   # HYPERLIQUID_MAINNET / HYPERLIQUID_API_URL → URL + signing domain
│   └── signer.py                # SigningModule
│
├── scripts/
│   ├── generate_wallet.py       # new key + public key + address; optional --write-env
│   ├── test_phase1.py           # automated Phase 1 checks (exit code)
│   ├── test_phase2.py           # Phase 2: live /info calls + info_snapshot (network)
│   └── test_phase3.py           # Phase 3: ExchangeClient + trade history (network)
```

**Security:** The private key lives only in environment variables loaded at startup (`python-dotenv` in `config/settings.py`). Admin and models never hold key material.

**Network:** `signing/env.py` reads **only** environment variables (see `.env.example`): canonical `HYPERLIQUID_MAINNET_API_URL` / `HYPERLIQUID_TESTNET_API_URL`, optional `HYPERLIQUID_API_URL`, and `HYPERLIQUID_MAINNET`. There are no hardcoded API URLs in app code. `signing/required_env.py` lists keys required for deposit text and validation. `config.settings.HYPERLIQUID_API_URL`, `InfoClient()`, and `SigningModule` all use the same resolution. The `TradingAccount.use_testnet` admin field is metadata only until wired to env.

---

## Tech Stack

| Concern | Tool |
|--------|------|
| Web / admin | Django 5.x (LTS track: 4.2+ compatible) |
| Hyperliquid SDK | `hyperliquid-python-sdk` |
| Signing | `hyperliquid.utils.signing.sign_l1_action` + `eth_account` |
| Key loading | `python-dotenv` |
| DB (dev) | SQLite (`db.sqlite3`, gitignored) |

Install:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then set PRIVATE_KEY
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

---

## SigningModule (Modular Boundary)

The only place the private key string is read from the environment. Callers pass `action`, `nonce`, and optional vault address; the module returns the `signature` dict expected by the API payload.

```python
# signing/signer.py — concept

class SigningModule:
    """Isolated signing boundary. Replace internals later (HSM, vault) without touching Django views."""

    def __init__(self, *, is_mainnet: bool = True, expires_after: int | None = None):
        ...

    @property
    def address(self) -> str: ...

    def sign_l1_action(
        self, action: dict, nonce: int, vault_address: str | None = None
    ) -> dict: ...
```

`Exchange` code (future phase) receives a `SigningModule` or the underlying `LocalAccount` only through explicit wiring — not from the database.

---

## Implementation Phases

### Phase 1 — Django skeleton + SigningModule

**Goal:** Runnable Django project, admin for metadata, env-based key, signing smoke check.

**Tasks:**

1. `requirements.txt`, `.env.example`, ensure `.gitignore` covers `.env` and `db.sqlite3`
2. Django project `config` and app `trading`
3. `TradingAccount` model: `name`, `use_testnet`, `created_at` (no secrets)
4. Register model in admin
5. `signing/signer.py`: load `PRIVATE_KEY`, expose `address`, delegate `sign_l1_action` to the SDK
6. Management command `smoke_signing`: print wallet address; optionally produce a signature for a minimal L1 action (e.g. `scheduleCancel`) without posting

**How to test Phase 1**

1. Generate a fresh keypair and write `PRIVATE_KEY` to `.env`:

   ```bash
   python scripts/generate_wallet.py --write-env
   ```

   Without `--write-env`, the script only prints `private_key`, `public_key` (uncompressed secp256k1 hex), and `address`; copy `PRIVATE_KEY=...` into `.env` yourself.

2. Run the automated verifier (checks `eth_account` vs `SigningModule` address, L1 sign shape, and `manage.py smoke_signing`):

   ```bash
   python scripts/test_phase1.py
   ```

   Exit code `0` means Phase 1 is behaving correctly; non-zero prints what failed.

**Phase output (example):**

```
Wallet address: 0xYourDerivedAddress
L1 signature produced (smoke): ok
```

---

### Phase 2 — Read-only info queries

**Goal:** Fetch account state without signing.

**Tasks:**

1. Add `trading/services/info_client.py` (or similar) wrapping `hyperliquid.info.Info`
2. Methods: positions, open orders, fills, deposits, spot balances
3. Management command or admin action to dump read-only snapshot (optional)

**Implemented:**

- `trading/services/info_client.py` — `InfoClient` with `skip_ws=True`, `HYPERLIQUID_API_URL` / mainnet flag from env or `settings.HYPERLIQUID_API_URL`
- Methods: `get_clearinghouse_state`, `get_positions`, `get_open_orders`, `get_trade_fills`, `get_deposits` (ledger rows with `delta.type == "deposit"`), `get_spot_clearinghouse_state`, `snapshot`
- `python manage.py info_snapshot` — JSON dump (default address = wallet from `PRIVATE_KEY`; override with `--address`)

**How to test Phase 2** (requires outbound HTTPS to Hyperliquid):

```bash
python scripts/test_phase2.py
```

Also:

```bash
python manage.py info_snapshot
```

The first `InfoClient()` call can take a while while the SDK loads `meta` / `spotMeta` over the network.

---

### Phase 3 — Orders (mainnet + testnet via `.env`)

**Goal:** Place and cancel orders on any listed perp or spot market; inspect trade history with optional fill %.

**Implemented:**

- `trading/services/exchange_client.py` — `ExchangeClient(SigningModule)` wrapping SDK `Exchange` with `settings.HYPERLIQUID_API_URL` / `signing/env.py` (SDK uses the same base URL for signing domain checks).
- `place_limit_order`, `place_market_order` (IOC + slippage; reduce-only supported), `cancel_order`.
- `trading/services/trade_history.py` — `userFills` with `_notional_usd`, grouping by `oid`, optional `orderStatus` + `filled_pct_of_orig_sz` when `--enrich`.
- Commands: `place_order`, `cancel_order`, `trade_history`, `list_markets` (perp + spot names for `--coin`).
- `python scripts/test_phase3.py` — validates wiring and report shape (network). Optional `PHASE3_PLACE_SMOKE=1` sends a **test** limit (use only on testnet / with care).

**How to test Phase 3**

```bash
python scripts/test_phase3.py
python manage.py list_markets
python manage.py trade_history
python manage.py trade_history --enrich --max-order-lookups 20
```

Place/cancel (real money risk on mainnet — prefer testnet in `.env`):

```bash
# testnet example: HYPERLIQUID_MAINNET=false or HYPERLIQUID_API_URL=https://api.hyperliquid-testnet.xyz
python manage.py place_order --coin BTC --side buy --sz 0.001 --limit-px 30000 --tif Gtc
python manage.py cancel_order --coin BTC --oid 123456789
```

---

### Phase 4 — Withdrawals

**Goal:** `withdraw3` (or current SDK action) with address validation and dry-run guard.

**Implemented:**

- `ExchangeClient.withdraw_to_wallet(amount, destination)` — checksummed EVM address via `eth_utils`.
- `python manage.py withdraw --amount … --destination 0x…` — **dry-run by default**; `--execute` submits the signed withdrawal only if `HYPERLIQUID_REAL_MONEY_ACK=I_UNDERSTAND` is set in `.env`.
- `python scripts/test_phase4.py` — validates withdraw wiring, dry-run output, and real-money guard (no live withdrawal unless you opt in manually).

---

## Security Rules

| Rule | Detail |
|------|--------|
| `.env` never committed | `.gitignore` includes `.env` |
| Key not in DB | Models store labels/flags only |
| Key never logged | No logging of key, raw signatures, or full signed payloads in production code |
| Testnet first | New write flows on testnet before mainnet |

---

## Future: Remote signing

Swap implementation inside `signing/signer.py` only; Django and service layers keep the same interface.

---

## MVP Checklist

- [x] Phase 1: Django runs, admin works, signing smoke command succeeds
- [x] Phase 2: Read queries working
- [x] Phase 3: Place/cancel + trade history (mainnet/testnet via env)
- [x] Phase 4: Withdrawal flow (CLI + dry-run default + `test_phase4.py`)
- [ ] `.env` in `.gitignore` verified before first commit
