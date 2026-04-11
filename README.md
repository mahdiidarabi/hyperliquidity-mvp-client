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
| `account_balances` | Perp margin / withdrawable + spot balances; optional `--dex xyz` for builder-DEX clearinghouse view. |
| `send_perp_usdc` | Move USDC collateral between **perp DEX books** ([`sendAsset`](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/exchange-endpoint)—e.g. primary `""` → builder `xyz`). |
| `update_isolated_margin` | Move USDC between **cross and isolated** for one **within that DEX’s** margin (after `send_perp_usdc` if funds were only on the primary DEX). |
| `transfer_usd_class` | Move USDC **spot ↔ perp** margin (`--to-perp` or `--to-spot`). |
| `withdraw` | `withdraw3` to an EVM address; **dry-run unless `--execute`**. |
| `info_snapshot` | JSON snapshot: clearinghouse, positions, open orders, fills, deposits, spot. |
| `list_markets` | JSON: perp + spot names; perps include **primary + builder DEX** universes (e.g. `xyz:CL`). |
| `place_order` | Signed limit or market (IOC) order; optional `--leverage` + `--isolated` / `--cross` runs `updateLeverage` first. |
| `update_leverage` | Signed `updateLeverage` for a perp (`--coin`, `--leverage`, `--isolated` or `--cross`). |
| `cancel_order` | Signed cancel by `coin` + `oid`. |
| `trade_history` | Fills report; `--enrich` adds `orderStatus` and fill % where possible. |

### Examples

#### Signing, wallet, and transfers

```bash
python manage.py smoke_signing

python manage.py wallet_info
python manage.py account_balances

python manage.py transfer_usd_class --amount 50 --to-perp
python manage.py transfer_usd_class --amount 25 --to-spot

python manage.py withdraw --amount 10.0 --destination 0xYourWallet
python manage.py withdraw --amount 10.0 --destination 0xYourWallet --execute
```

#### `list_markets` (perp + spot names for `--coin`)

```bash
# Pretty-printed JSON (default indent)
python manage.py list_markets

# Compact (one line or minimal whitespace)
python manage.py list_markets --indent 0

# Save for reference while scripting
python manage.py list_markets --indent 2 > markets.json
```

Use the `perp` and `spot` arrays to pick valid `--coin` values for the **same** API URL as in `.env` (testnet lists differ from mainnet).

#### Read-only: balances, snapshot, and `trade_history`

```bash
python manage.py account_balances
python manage.py account_balances --dex xyz

python manage.py info_snapshot
python manage.py info_snapshot --address 0xYourAddress --indent 0

# Fills for the wallet derived from PRIVATE_KEY
python manage.py trade_history

# Another account (e.g. vault or subaccount you control)
python manage.py trade_history --address 0xOtherAddress

# Extra per-order context (more API calls; capped by --max-order-lookups)
python manage.py trade_history --enrich --max-order-lookups 30
python manage.py trade_history --address 0xYourAddress --enrich --max-order-lookups 20
```

`info_snapshot` includes open orders (with `oid`)—useful before `cancel_order`.

#### `place_order` (limits, market-style IOC, spot)

These **submit real orders** on mainnet. Prefer **testnet** in `.env` while experimenting.

```bash
# Limit, good-til-canceled (default)
python manage.py place_order --coin BTC --side buy --sz 0.01 --limit-px 95000 --tif Gtc

# Post-only / maker (canceled if it would cross the spread)
python manage.py place_order --coin ETH --side buy --sz 0.05 --limit-px 3200 --tif Alo

# IOC limit (fill now or cancel remainder)
python manage.py place_order --coin SOL --side sell --sz 1.0 --limit-px 150 --tif Ioc

# “Market”: aggressive IOC limit from mid ± slippage (default 0.05)
python manage.py place_order --coin ETH --side sell --sz 0.1 --market
python manage.py place_order --coin BTC --side buy --sz 0.001 --market --slippage 0.02

# Reduce-only (perp; must match exchange rules)
python manage.py place_order --coin BTC --side sell --sz 0.01 --limit-px 100000 --tif Gtc --reduce-only

# Builder / HIP-3 perp DEX (coin from `perp` or `perp_by_dex`, e.g. oil on XYZ DEX)
python manage.py place_order --coin "xyz:CL" --side buy --sz 0.1 --limit-px 70 --tif Gtc

# Brent (xyz:BRENTOIL) — full order: see prose section "Builder DEX (xyz) funding" below

# Spot: use a name from the `spot` list in `list_markets` (verify on your network)
python manage.py place_order --coin "PURR/USDC" --side buy --sz 100 --limit-px 0.42 --tif Gtc
python manage.py place_order --coin "@107" --side sell --sz 5 --limit-px 20 --tif Gtc
```

**`xyz:BRENTOIL` (Brent) — builder DEX (`xyz`) funding (read this if you see margin errors)**

[`xyz:BRENTOIL`](https://app.hyperliquid.xyz/trade/xyz:BRENTOIL) is on the **XYZ** HIP-3 / builder perp DEX. Hyperliquid keeps **separate USDC collateral per perp DEX** ([**Send Asset**](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/exchange-endpoint): use `""` for the default USDC perp DEX and `"xyz"` for the XYZ book).

**Why `account_balances` shows $20 but `update_isolated_margin` returns “Account does not have sufficient margin available for increase”:**  
`account_balances` with default **`perp_dex` `""`** reflects the **primary** perp wallet. Your USDC is there. **`updateIsolatedMargin` only reallocates margin that already exists on the same DEX as that asset.** It does **not** move USDC from the primary DEX into the `xyz` DEX—you must **[`sendAsset`](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/exchange-endpoint)** USDC **into** `xyz` first (`send_perp_usdc` below). Only **then** can isolated margin be increased for `xyz:BRENTOIL`.

**Recommended order of operations**

1. **Spot → primary perp** (if needed): `transfer_usd_class --to-perp` so USDC sits in the default perp book.  
2. **Primary perp → builder `xyz` perp** (required when funds are only on `dex=""`):  
   `python manage.py send_perp_usdc --amount 18 --from-dex primary --to-dex xyz`  
   (Self-transfer to your own address; moves collateral between DEX books per official docs.)  
3. **Isolated slot for the contract** (noCross):  
   `python manage.py update_isolated_margin --coin "xyz:BRENTOIL" --amount 15`  
4. **Leverage:** `update_leverage --coin "xyz:BRENTOIL" --leverage 10 --isolated` *or* `--leverage` on `place_order`.  
5. **Order:** `place_order` (≥ **~$10** notional—use **`sz 0.11`** × mid **~$91** as in earlier examples).

```bash
python manage.py account_balances
python manage.py send_perp_usdc --amount 18 --from-dex primary --to-dex xyz
python manage.py account_balances --dex xyz
python manage.py update_isolated_margin --coin "xyz:BRENTOIL" --amount 12
python manage.py update_leverage --coin "xyz:BRENTOIL" --leverage 10 --isolated
# Limit order (--limit-px; do not pass --market)
python manage.py place_order --coin "xyz:BRENTOIL" --side buy --sz 0.11 --limit-px 91 --tif Gtc
# Or market-style IOC only (--market; mutually exclusive with --limit-px)
python manage.py place_order --coin "xyz:BRENTOIL" --side buy --sz 0.11 --market
```

**Sizing:** `place_order` **`--sz`** is in **coin units**. At mid **~$91**, **`sz 0.11`** ≈ **$10** notional (minimum ~**$10** order value).

**Leverage:** higher leverage (e.g. **10×**) reduces **initial margin** vs **1×** for the same notional. **`--leverage 1 --isolated`** needs the **most** USDC in the **xyz** + isolated path above.

**Errors:** `"Insufficient margin to place order"` → under-collateralized for size/leverage, or skipped steps **1–3**. `"Account does not have sufficient margin available for increase"` on **`update_isolated_margin`** → run **`send_perp_usdc`** first. **USDC on spot** does not fund perp until **`transfer_usd_class --to-perp`**.

#### `cancel_order`

```bash
# oid from place_order JSON (resting.oid / filled.oid) or from info_snapshot open orders
python manage.py cancel_order --coin BTC --oid 123456789
python manage.py cancel_order --coin "PURR/USDC" --oid 987654321
```

#### Typical flow (testnet first)

```bash
python manage.py list_markets
python manage.py account_balances
python manage.py transfer_usd_class --amount 100 --to-perp
python manage.py place_order --coin BTC --side buy --sz 0.001 --limit-px 50000 --tif Gtc
python manage.py info_snapshot
python manage.py cancel_order --coin BTC --oid YOUR_OID  # from place_order JSON or info_snapshot
python manage.py trade_history --enrich --max-order-lookups 15
```

Use `python manage.py <command> --help` for full flags.

### `list_markets`

This command prints JSON from [`InfoClient.list_symbols`](trading/services/info_client.py). It loads [`spotMeta`](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint) for spot, and for perps it merges **[`meta` with `dex=""`](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint)** (the primary perpetual DEX) with **`meta` for each builder DEX** listed by [`perpDexs`](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint) (e.g. dex name `xyz` → coins like `xyz:CL` for oil). The app URL [`…/trade/xyz:CL`](https://app.hyperliquid.xyz/trade/xyz:CL) uses that full **coin** string; it does **not** appear if you only query the default `meta` without a `dex` parameter—which is why older versions of `list_markets` missed builder markets.

| Field | Meaning |
|-------|---------|
| `base_url` | Active API base (mainnet vs testnet alignment). |
| `perp` | All perpetual **coin names** merged from the primary DEX plus each builder DEX (e.g. `BTC`, `ETH`, `xyz:CL`, `xyz:BRENTOIL`). |
| `perp_by_dex` | Same data grouped by DEX: `dex` is `""` for the primary book, or e.g. `xyz` for the XYZ builder DEX; `assets` is the list of `coin` strings for that DEX. |
| `spot` | Spot pair **names** from `spotMeta.universe` (use these as `--coin` when trading spot). |

Hyperliquid’s docs explain how **perp vs spot** `coin` strings work in requests and subscriptions: for perpetuals, `coin` is the name from `meta` for that DEX; for spot, the API also accepts forms like `PURR/USDC` or indexed pairs such as `@1` depending on the asset—see [Perpetuals vs Spot](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint#perpetuals-vs-spot) and [asset IDs](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/asset-ids) for edge cases and UI remappings (e.g. display name vs on-chain name). **Always pick a `coin` that exists for your network** (`list_markets` on testnet vs mainnet can differ).

Optional: `--indent 0` for compact JSON.

### `place_order` and `cancel_order`

Both commands use your `PRIVATE_KEY` to sign an L1 action and `POST` it to the Hyperliquid [**Exchange** endpoint](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/exchange-endpoint) (same pattern as the official Python SDK: build order/cancel action → sign → submit).

**`place_order`**

| Flag | Role |
|------|------|
| `--coin` | Asset identifier as Hyperliquid expects it (perp or spot name—use `list_markets` for this API). The API resolves this to an **asset index** under the hood (perps: index in `meta.universe`; spot: `10000 +` spot universe index—see [Exchange → Asset](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/exchange-endpoint#asset)). |
| `--side` | `buy` or `sell`. |
| `--sz` | Order size in **coin units** (not USDC notional). |
| `--limit-px` | Limit price (required unless `--market`). |
| `--market` | **Not** a separate order type on-chain: the client sends an aggressive **IOC** limit using a price derived from the current mid and `--slippage` (default `0.05`). `--tif` is ignored when `--market` is set. |
| `--tif` | Time-in-force for **limit** orders only: `Gtc` (good til canceled—default), `Ioc` (immediate or cancel—unfilled remainder canceled), `Alo` (add liquidity only / post-only—would cross the book instead of resting). Definitions match [Place an order](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/exchange-endpoint#place-an-order). |
| `--slippage` | Used only with `--market` (see `ExchangeClient` in [`trading/services/exchange_client.py`](trading/services/exchange_client.py)). |
| `--reduce-only` | Passed through as `reduceOnly` so the order can only reduce an existing position. |
| `--leverage` | If set, submits [`updateLeverage`](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/exchange-endpoint) for `--coin` **before** the order (same nonce pattern as the SDK: separate signed action). |
| `--isolated` / `--cross` | Used with `--leverage`: margin mode (`isCross` false vs true). Builder perps such as `xyz:*` need **`--isolated`**. Default when neither flag is given is cross. |

When **`--leverage`** is set, stdout JSON is **`{ "updateLeverage": …, "order": … }`**.

**`update_leverage`** — same signing stack as `place_order`, but only [`updateLeverage`](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/exchange-endpoint): `--coin`, `--leverage`, and **`--isolated`** or **`--cross`**.

Successful responses include `statuses` with a **resting** `oid`, a **filled** summary, or an **error** string (e.g. minimum order value)—see the Exchange doc examples. **Trading spends real margin on mainnet**; use testnet in `.env` while learning.

**`cancel_order`**

| Flag | Role |
|------|------|
| `--coin` | Same asset naming as for placing the order (must match the order you are canceling). |
| `--oid` | Order id returned when the order was accepted (`resting.oid` or `filled.oid`), or visible under open orders / `info_snapshot`. |

The API cancel action is `{ asset, oid }`; Hyperliquid documents possible error statuses such as the order already being gone—see [Cancel order(s)](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/exchange-endpoint#cancel-order-s). This CLI does not implement **cancel by client order ID** (`cancelByCloid`); only `coin` + `oid`.

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
# ex.update_leverage("xyz:BRENTOIL", 10, is_cross=False)
# ex.send_usdc_between_perp_dexes(18.0, source_dex="", destination_dex="xyz")
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
