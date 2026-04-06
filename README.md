# hyperliquidity-mvp-client

Minimal Django-backed client for [Hyperliquid](https://hyperliquid.xyz): keep your private key in local `.env`, derive the address, sign with EIP-712 via the official SDK, and query or trade over HTTPS without exporting the key.

Roadmap and phased design: [implementation.md](implementation.md).

---

## End-to-end user flow

This is the intended journey from zero to funded trading and exit. Commands assume the repo root and venv (see [Setup](#setup)).

| Step | What you need | Command / action |
|------|----------------|-------------------|
| **1. Create a key and put it in `.env`** | A new wallet or import your own key | `python scripts/generate_wallet.py` or `python scripts/generate_wallet.py --write-env` → set `PRIVATE_KEY` in `.env` (never commit it). |
| **2. See your address and where to deposit USDC** | Same `0x` address for Hyperliquid and the Arbitrum-side bridge; **network** for USDC is **Arbitrum One** on mainnet (chain id `42161`). Always use the **official** [Hyperliquid bridge / app](https://hyperliquid.xyz) — do not send to random addresses. | `python manage.py wallet_info` prints address + deposit guidance + JSON. |
| **3. Check balances (perp vs spot)** | Perp: margin summary, **withdrawable** USDC; **spot**: token rows (USDC + assets), with `available_estimate` where the API exposes `total` / `hold`. | `python manage.py account_balances` (or `--address 0x…`). Raw payloads are also under `perp.raw_clearinghouse` / `spot.raw_spot_clearinghouse` in JSON. |
| **4. Move USDC between spot ↔ perp margin** | On-exchange transfer (not a chain withdrawal). | `python manage.py transfer_usd_class --amount 100 --to-perp` or `--to-spot`. |
| **5. Place orders (perp or spot markets)** | `coin` must match `list_markets` for this network. | `python manage.py list_markets` then `python manage.py place_order …` (see [Examples](#django-management-commands)). |
| **6. Trade history, fills, fill %** | Fills from `userFills`; optional `orderStatus` for `origSz` and **filled_pct_of_orig_sz**. | `python manage.py trade_history` and `python manage.py trade_history --enrich`. |
| **7. Cancel orders** | Order id from open orders or API responses. | `python manage.py cancel_order --coin BTC --oid …` |
| **8. Withdraw USDC to any wallet** | **Phase 4** — signed bridge withdrawal; **dry-run by default**. | `python manage.py withdraw --amount … --destination 0x…` (prints plan only). **Submit:** set `HYPERLIQUID_REAL_MONEY_ACK=I_UNDERSTAND` in `.env`, then `python manage.py withdraw … --execute` (real funds). |

**Covered elsewhere:** `info_snapshot` (full snapshot), `trade_history` + `--enrich`, regression scripts `test_phase1`–`test_phase4`.

### Configuration (no hardcoded API URLs in code)

All API bases, canonical mainnet/testnet hosts, docs URL, and deposit labels are read from **environment variables** (see [.env.example](.env.example)). Copy it to `.env` and fill in values; the app raises a clear error if required keys are missing. The Hyperliquid **Python SDK** still compares your `base_url` to its own internal constants for signing — keep `HYPERLIQUID_API_URL` (or the canonical URLs) aligned with the official hosts you intend to use.

### Real money (mainnet)

Trading and withdrawals can move **real funds**. Prefer **testnet** first (`HYPERLIQUID_TESTNET_API_URL` + `HYPERLIQUID_API_URL` pointing at testnet, or `HYPERLIQUID_MAINNET=false` with canonical URLs in `.env`). For **withdraw --execute** on any network, you must set `HYPERLIQUID_REAL_MONEY_ACK=I_UNDERSTAND`. There is no automated guard on `place_order` — treat orders as financially binding.

---

## What this project does

| Area | Capability |
|------|------------|
| **Secrets** | Load `PRIVATE_KEY` from `.env` only (never the database). |
| **Network** | All API URLs and deposit metadata from `.env` (`signing/env.py`, `signing/required_env.py`); no hardcoded hosts in application code. |
| **Signing** | `SigningModule` is a pure signing boundary: service code sends signable messages in, receives signatures out. |
| **Wallet / deposits** | `wallet_info` + `trading/deposit_info.py` (address + Arbitrum/USDC guidance; no bridge contract addresses in-repo). |
| **Balances** | `account_balances` / `InfoClient.get_account_balances()` — perp + spot breakdown. |
| **Spot ↔ perp** | `transfer_usd_class` / `ExchangeClient.usd_class_transfer`. |
| **Read-only** | `InfoClient`: positions, orders, fills, deposits (ledger), spot state, snapshots. |
| **Trading** | `ExchangeClient`: build action payload -> ask `SigningModule` to sign -> submit `/exchange`; plus trade history with optional fill %. |
| **Withdraw** | `withdraw` (dry-run default) / `ExchangeClient.withdraw_to_wallet`. |
| **Admin** | Optional `TradingAccount` labels (no secrets). |
| **Regression tests** | `scripts/test_phase1.py` … `test_phase4.py` validate each layer (Phase 4: withdraw dry-run + real-money guard). |

---

## Project structure

```
.
├── manage.py                 # Django entrypoint
├── requirements.txt
├── .env.example             # Copy to .env; never commit .env
│
├── config/                  # Django project
│   ├── settings.py          # Loads .env; exposes HYPERLIQUID_API_URL
│   ├── urls.py              # Admin only (no public API routes yet)
│   ├── wsgi.py / asgi.py
│
├── signing/                 # Framework-free: key + env + EIP-712 helpers
│   ├── env.py               # API URL + signing network (values from .env only)
│   ├── required_env.py      # List of required env keys (shared with test scripts)
│   └── signer.py            # SigningModule
│
├── trading/                 # Django app
│   ├── models.py            # TradingAccount (metadata only)
│   ├── admin.py
│   ├── deposit_info.py      # Deposit network guidance (text/JSON for wallet_info)
│   ├── services/
│   │   ├── info_client.py   # Read-only /info
│   │   ├── exchange_client.py  # Signed /exchange (orders, transfer, withdraw)
│   │   ├── balances.py      # Normalized perp vs spot balances
│   │   └── trade_history.py    # Fills + optional orderStatus enrichment
│   └── management/commands/    # CLI wrappers (see tables below)
│
└── scripts/                 # Standalone tests and wallet generator
    ├── generate_wallet.py
    ├── test_phase1.py
    ├── test_phase2.py
    ├── test_phase3.py
    └── test_phase4.py
```

**Where to extend**

- New read calls: add methods on `InfoClient` or use `InfoClient.raw_info`.
- New signed actions: prefer extending `ExchangeClient` or calling SDK `Exchange` with `SigningModule.wallet`.
- Network rules: change only `signing/env.py` so CLI, settings, and signing stay aligned.

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # set PRIVATE_KEY and optional network vars
python manage.py migrate
python manage.py createsuperuser   # optional, for /admin/
```

Run scripts and `manage.py` from the **repository root** with the venv active (or `.venv/bin/python`).

---

## Environment variables

**Source of truth:** [.env.example](.env.example) — copy to `.env` and fill every required line. Do not commit `.env`.

| Variable | Role |
|----------|------|
| `PRIVATE_KEY` | Required; wallet used for signing. |
| `HYPERLIQUID_MAINNET_API_URL` | Required; canonical mainnet API base (used for signing domain match and defaults). |
| `HYPERLIQUID_TESTNET_API_URL` | Required; canonical testnet API base. |
| `HYPERLIQUID_API_URL` | Optional; if set, this is the active API. If unset, `HYPERLIQUID_MAINNET` picks between the two canonical URLs above. |
| `HYPERLIQUID_MAINNET` | When `HYPERLIQUID_API_URL` is unset: `true` → mainnet canonical URL, `false` → testnet. |
| `HYPERLIQUID_DOCS_URL` | Required; documentation link for `wallet_info` / deposit text. |
| `DEPOSIT_USDC_LAYER2_NAME` | Required; display name for USDC deposit L2 (e.g. Arbitrum One). |
| `DEPOSIT_ARBITRUM_CHAIN_ID` | Required; chain id string for deposit help (e.g. `42161`). |
| `HYPERLIQUID_REAL_MONEY_ACK` | Set to `I_UNDERSTAND` only when you accept risk; **required** for `withdraw --execute`. |
| `DJANGO_SECRET_KEY` | Optional; defaults to dev placeholder. |

---

## Scripts (`scripts/`)

Standalone utilities. `test_phase*` scripts call `load_dotenv` on `.env` where needed; they may call `django.setup()` for Phase 3.

| Script | Description |
|--------|-------------|
| [scripts/generate_wallet.py](scripts/generate_wallet.py) | New random keypair + address; optional `--write-env` to set `PRIVATE_KEY` in `.env`. |
| [scripts/test_phase1.py](scripts/test_phase1.py) | No network: key, `SigningModule`, offline L1 sign, `smoke_signing`. Exit `0` = pass. |
| [scripts/test_phase2.py](scripts/test_phase2.py) | Network: `InfoClient` shapes + `info_snapshot`. Exit `0` = pass. |
| [scripts/test_phase3.py](scripts/test_phase3.py) | Network: `ExchangeClient` URL alignment + `trade_history_report`. Optional `PHASE3_PLACE_SMOKE=1` places a real order (risky). |
| [scripts/test_phase4.py](scripts/test_phase4.py) | Withdraw wiring: env URLs, invalid address, `withdraw` dry-run, `--execute` blocked without `HYPERLIQUID_REAL_MONEY_ACK`. |

```bash
python scripts/generate_wallet.py
python scripts/generate_wallet.py --write-env

python scripts/test_phase1.py
python scripts/test_phase2.py
python scripts/test_phase3.py
python scripts/test_phase4.py
```

---

## Django management commands

Use `python manage.py <command>` from the repo root. All commands respect `settings.HYPERLIQUID_API_URL` (from `.env`).

| Command | Description |
|---------|-------------|
| `smoke_signing` | Offline L1 sign smoke (`scheduleCancel`); does **not** call HTTP. |
| `wallet_info` | Wallet address + USDC deposit **network** guidance (Arbitrum One on mainnet; use official bridge UI). |
| `account_balances` | Perp margin / withdrawable + spot token balances (structured JSON). |
| `transfer_usd_class` | Move USDC **spot ↔ perp** margin (`--to-perp` or `--to-spot`). |
| `withdraw` | `withdraw3` to an EVM address; **dry-run unless `--execute`**. |
| `info_snapshot` | JSON snapshot: clearinghouse, positions, open orders, fills, deposits, spot. |
| `list_markets` | JSON of perp + spot symbol names (valid `--coin` values for this network). |
| `place_order` | Signed limit or market (IOC) order. |
| `cancel_order` | Signed cancel by `coin` + `oid`. |
| `trade_history` | Fills report; `--enrich` adds `orderStatus` and fill % where possible. |

### Examples

```bash
python manage.py smoke_signing

python manage.py wallet_info
python manage.py account_balances

python manage.py transfer_usd_class --amount 50 --to-perp
python manage.py transfer_usd_class --amount 25 --to-spot

python manage.py withdraw --amount 10.0 --destination 0xYourWallet
python manage.py withdraw --amount 10.0 --destination 0xYourWallet --execute

python manage.py info_snapshot
python manage.py info_snapshot --address 0xYourAddress --indent 0

python manage.py list_markets

python manage.py trade_history
python manage.py trade_history --enrich --max-order-lookups 30

# Trading (real funds on mainnet — use testnet in .env first)
python manage.py place_order --coin BTC --side buy --sz 0.01 --limit-px 95000 --tif Gtc
python manage.py place_order --coin ETH --side sell --sz 0.1 --market
python manage.py place_order --coin BTC --side sell --sz 0.01 --limit-px 100000 --tif Gtc --reduce-only
python manage.py cancel_order --coin BTC --oid 123456789
```

Use `python manage.py <command> --help` for full flags.

---

## Using services from Python code

```python
from django.conf import settings
from signing import SigningModule
from trading.services import ExchangeClient, InfoClient

signer = SigningModule()
info = InfoClient(base_url=settings.HYPERLIQUID_API_URL)
ex = ExchangeClient(signer, base_url=settings.HYPERLIQUID_API_URL)

addr = signer.address
snap = info.snapshot(addr)
balances = info.get_account_balances(addr)
report = info.trade_history_report(addr, enrich_order_status=True, max_order_lookups=20)
# ex.place_limit_order("BTC", True, 0.01, 95000.0, tif="Gtc")
# ex.usd_class_transfer(100.0, to_perp=True)
# ex.withdraw_to_wallet(50.0, "0x…")
```

Prefer passing `settings.HYPERLIQUID_API_URL` in Django contexts so CLI and app stay consistent.

---

## Admin and dev server

```bash
python manage.py runserver
```

Admin: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/) — register labels under **Trading** (`TradingAccount`). Keys are never stored here.

---

## Performance note

The first construction of `Info` / `InfoClient` / `Exchange` may take a noticeable time while the SDK loads `meta` / `spotMeta` over the network.
