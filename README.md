# hyperliquidity-mvp-client

Minimal Django-backed client for [Hyperliquid](https://hyperliquid.xyz): keep your private key in `.env`, sign with EIP-712 via the official SDK, and query or trade over HTTPS without exporting the key.

Phased design and roadmap: [implementation.md](implementation.md).

## Contents

- [Overview](#overview)
- [End-to-end user flow](#end-to-end-user-flow)
- [Setup](#setup)
- [Configuration and safety](#configuration-and-safety)
- [Use cases](#use-cases)
  - [Wallet, deposits, and bridge timing](#wallet-deposits-and-bridge-timing)
  - [Balances and markets](#balances-and-markets)
  - [Spot ↔ perp (on-exchange, not chain)](#spot--perp-on-exchange-not-chain)
  - [Trading: standard perps and spot](#trading-standard-perps-and-spot)
  - [Trading: builder DEX (e.g. `xyz:BRENTOIL`)](#trading-builder-dex-eg-xyzbrentoil)
  - [History, fills, and ledger](#history-fills-and-ledger)
  - [Withdraw USDC to Arbitrum](#withdraw-usdc-to-arbitrum)
- [Command index](#command-index)
- [Reference: `list_markets`](#reference-list_markets)
- [Reference: `place_order` and `cancel_order`](#reference-place_order-and-cancel_order)
- [Scripts (`scripts/`)](#scripts-scripts)
- [Project layout and Python API](#project-layout-and-python-api)
- [Admin and performance](#admin-and-performance)

---

## Overview

| Area | What you get |
|------|----------------|
| **Secrets** | `PRIVATE_KEY` from `.env` only (never the database). |
| **Network** | API URLs and deposit labels from `.env` (`signing/env.py`); no hardcoded API hosts in app code. |
| **Signing** | `SigningModule`: messages in, signatures out (EIP-712 / SDK-aligned). |
| **Read-only** | `InfoClient`: balances, markets, snapshots, fills, ledger deposits/withdrawals. |
| **Signed actions** | `ExchangeClient`: orders, leverage, isolated margin, `sendAsset` between perp DEXes, spot↔perp, `withdraw3`. |
| **Tests** | `scripts/test_phase1.py` … `test_phase4.py` |

---

## End-to-end user flow

Linear path from zero to funded trading and exit. For deeper architecture and phased delivery, see [implementation.md](implementation.md).

| Step | What you need | Command / action |
|------|----------------|-------------------|
| **1. Key in `.env`** | New or imported wallet | `python scripts/generate_wallet.py` or `--write-env` → set `PRIVATE_KEY` (never commit). |
| **2. Address + deposit guidance** | Same `0x` on Hyperliquid and Arbitrum bridge; USDC on **Arbitrum One** (`42161`) on mainnet; use [official app](https://hyperliquid.xyz). | `python manage.py wallet_info` |
| **3. Balances** | Perp margin / withdrawable; spot USDC and tokens | `python manage.py account_balances` (`--address`, `--dex xyz` optional). |
| **4. Spot ↔ perp** | On-exchange move (not chain withdrawal) | `python manage.py transfer_usd_class --amount 100 --to-perp` or `--to-spot`. |
| **5. Markets + trade** | `coin` from `list_markets` for this network | `python manage.py list_markets` → `place_order` … ([Use cases](#use-cases), [Command index](#command-index)). |
| **6. Trade history** | Fills; optional `orderStatus` / fill % | `python manage.py trade_history` / `--enrich`. |
| **7. Cancel** | Open order id | `python manage.py cancel_order --coin … --oid …` |
| **8. Withdraw** | Signed bridge withdrawal; **dry-run default** | `python manage.py withdraw --amount … --destination 0x…` → **`--execute`** only with `HYPERLIQUID_REAL_MONEY_ACK=I_UNDERSTAND`. |

**Also useful:** `info_snapshot`, `deposit_history`, `withdraw_history`, builder-DEX flow (`send_perp_usdc`, `update_isolated_margin`, `update_leverage`) — see [Use cases](#use-cases).

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # set PRIVATE_KEY and network vars
python manage.py migrate
python manage.py createsuperuser   # optional, for /admin/
```

Run `manage.py` and `scripts/` from the **repo root** with the venv active.

---

## Configuration and safety

**Source of truth:** [.env.example](.env.example) — copy to `.env`. Do not commit `.env`.

| Variable | Role |
|----------|------|
| `PRIVATE_KEY` | Required; wallet used for signing. |
| `HYPERLIQUID_MAINNET_API_URL` | Required; canonical mainnet API (signing domain alignment). |
| `HYPERLIQUID_TESTNET_API_URL` | Required; canonical testnet API. |
| `HYPERLIQUID_API_URL` | Optional; if set, active API. If unset, `HYPERLIQUID_MAINNET` picks between the two canonical URLs. |
| `HYPERLIQUID_MAINNET` | When `HYPERLIQUID_API_URL` unset: `true` → mainnet, `false` → testnet. |
| `HYPERLIQUID_DOCS_URL` | Required; docs link for `wallet_info` / deposit text. |
| `DEPOSIT_USDC_LAYER2_NAME` | Required; e.g. Arbitrum One. |
| `DEPOSIT_ARBITRUM_CHAIN_ID` | Required; e.g. `42161`. |
| `HYPERLIQUID_REAL_MONEY_ACK` | Set to `I_UNDERSTAND` for `withdraw --execute`. |
| `DJANGO_SECRET_KEY` | Optional; dev placeholder if unset. |

Keep `HYPERLIQUID_API_URL` aligned with the network you sign for (the SDK compares against canonical hosts). Prefer **testnet** while learning. **`place_order` has no extra guard** — treat orders as binding. **`withdraw --execute`** requires `HYPERLIQUID_REAL_MONEY_ACK=I_UNDERSTAND`.

---

## Use cases

All commands: `python manage.py <command>` from the repo root; they use `settings.HYPERLIQUID_API_URL`.

### Wallet, deposits, and bridge timing

| Goal | Command / note |
|------|----------------|
| Generate a new key (optional write to `.env`) | `python scripts/generate_wallet.py` or `--write-env` |
| Offline signing sanity check | `python manage.py smoke_signing` |
| Show address + deposit network help | `python manage.py wallet_info` |
| See **confirmed** bridge deposits (ledger) | `python manage.py deposit_history --days 90` |

Use the **official** [Hyperliquid app](https://hyperliquid.xyz) for deposits: same `0x` as in `wallet_info`; USDC on **Arbitrum One** (chain id `42161`) on mainnet. Do not send to random addresses.

**Typical bridge timing** ([Bridge2](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/bridge2)): deposits usually credit **&lt; ~1 minute** (minimum **5 USDC**). Withdrawals after signing **`withdraw3`** typically land on Arbitrum in **~3–4 minutes**. **Pending** chain transactions may not appear in `deposit_history` / `withdraw_history` until the ledger records them—use the app or Arbiscan for in-flight status.

### Balances and markets

| Goal | Command |
|------|---------|
| Perp margin / withdrawable + spot tokens | `python manage.py account_balances` |
| Same for another address | `--address 0x…` |
| Builder DEX clearinghouse view (e.g. `xyz`) | `python manage.py account_balances --dex xyz` |
| Valid **`--coin`** names (perp + spot, all DEXes) | `python manage.py list_markets` |
| Compact / save JSON | `list_markets --indent 0` or `> markets.json` |
| Full dashboard JSON (positions, orders, fills, deposits slice, spot) | `python manage.py info_snapshot` |

Use `list_markets` output **`perp`** / **`spot`** (and **`perp_by_dex`**) so `--coin` matches this API and network (testnet vs mainnet lists differ). Details: [Reference: `list_markets`](#reference-list_markets).

### Spot ↔ perp (on-exchange, not chain)

| Goal | Command |
|------|---------|
| Move USDC spot → perp margin | `python manage.py transfer_usd_class --amount 100 --to-perp` |
| Perp → spot | `--to-spot` |

This is **not** an Arbitrum withdrawal; it only moves USDC inside Hyperliquid accounts.

### Trading: standard perps and spot

1. `python manage.py list_markets` — pick `coin` (e.g. `BTC`, `ETH`, or spot names).
2. Place a **limit** or **market-style** order (`--market` = aggressive IOC from mid ± slippage). **`--limit-px` and `--market` are mutually exclusive.**

```bash
python manage.py place_order --coin BTC --side buy --sz 0.01 --limit-px 95000 --tif Gtc
python manage.py place_order --coin ETH --side sell --sz 0.1 --market
python manage.py place_order --coin "PURR/USDC" --side buy --sz 100 --limit-px 0.42 --tif Gtc
```

3. **Cancel** only **open** (resting) orders: get `oid` from the place response or `info_snapshot` → `python manage.py cancel_order --coin BTC --oid …`

4. **Close a filled position** with a new order (e.g. **sell** same size, often `--reduce-only`)—you cannot “cancel” an executed fill.

Flag details: [Reference: `place_order` and `cancel_order`](#reference-place_order-and-cancel_order).

### Trading: builder DEX (e.g. `xyz:BRENTOIL`)

Builder coins look like `xyz:CL`, `xyz:BRENTOIL`. Hyperliquid holds **separate USDC collateral per perp DEX**. If your USDC is only on the **primary** book (`account_balances` with default `perp_dex`), you must move it to the **`xyz` book** before isolated margin / orders on `xyz:*`.

**Recommended order:**

1. `transfer_usd_class --to-perp` if USDC is still on spot.  
2. **`send_perp_usdc`** — primary → `xyz`:  
   `python manage.py send_perp_usdc --amount 18 --from-dex primary --to-dex xyz`  
3. **`update_isolated_margin`** for noCross names (e.g. `--coin "xyz:BRENTOIL" --amount 12`).  
4. **`update_leverage`** or `place_order --leverage … --isolated`.  
5. **`place_order`** — mind **~$10** minimum notional; **`sz`** is in coin units. Use **either** `--limit-px` **or** `--market`, not both.

```bash
python manage.py send_perp_usdc --amount 18 --from-dex primary --to-dex xyz
python manage.py account_balances --dex xyz
python manage.py update_isolated_margin --coin "xyz:BRENTOIL" --amount 12
python manage.py update_leverage --coin "xyz:BRENTOIL" --leverage 10 --isolated
python manage.py place_order --coin "xyz:BRENTOIL" --side buy --sz 0.11 --limit-px 91 --tif Gtc
```

Standalone leverage: `python manage.py update_leverage --coin "xyz:BRENTOIL" --leverage 10 --isolated`.

**Errors:** “Insufficient margin” on order → collateral / leverage / minimum size. “Account does not have sufficient margin available for increase” on **`update_isolated_margin`** → run **`send_perp_usdc`** first. “Minimum value of $10” → increase size × price notional.

### History, fills, and ledger

| Goal | Command |
|------|---------|
| Fills + optional per-order enrichment | `python manage.py trade_history` / `--enrich` / `--address` |
| Confirmed **deposits** (ledger) | `python manage.py deposit_history --days 90` |
| Recorded **withdrawals** (ledger) | `python manage.py withdraw_history --days 90` |

`deposit_history` / `withdraw_history` use [`userNonFundingLedgerUpdates`](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint)—finalized rows only; see [Wallet, deposits, and bridge timing](#wallet-deposits-and-bridge-timing) for timing and pending limits.

### Withdraw USDC to Arbitrum

| Goal | Command |
|------|---------|
| Preview (no chain tx) | `python manage.py withdraw --amount 10 --destination 0xYourWallet` |
| Submit **`withdraw3`** | Set `HYPERLIQUID_REAL_MONEY_ACK=I_UNDERSTAND`, then same with **`--execute`** |

See Bridge2 timing above (~3–4 minutes typical after signing).

---

## Command index

| Command | Description |
|---------|-------------|
| `smoke_signing` | Offline L1 sign smoke; no HTTP. |
| `wallet_info` | Address + USDC deposit network guidance. |
| `account_balances` | Perp + spot; `--dex xyz` for builder clearinghouse. |
| `send_perp_usdc` | USDC between perp DEX books ([`sendAsset`](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/exchange-endpoint)). |
| `update_isolated_margin` | Cross ↔ isolated for one coin (same DEX). |
| `transfer_usd_class` | Spot ↔ perp USDC. |
| `withdraw` | `withdraw3`; dry-run unless `--execute`. |
| `info_snapshot` | Full JSON snapshot (clearinghouse, orders, fills, deposits slice, spot). |
| `list_markets` | Perp + spot names (`perp_by_dex` included). |
| `place_order` | Limit or market IOC; optional `--leverage` + `--isolated` / `--cross`. |
| `update_leverage` | `updateLeverage` only. |
| `cancel_order` | Cancel by `coin` + `oid`. |
| `trade_history` | Fills; `--enrich` for order status / fill %. |
| `deposit_history` | Ledger deposits; `--days`. |
| `withdraw_history` | Ledger withdraws; `--days`. |

`python manage.py <command> --help` for flags.

---

## Reference: `list_markets`

Implementation: [`InfoClient.list_symbols`](trading/services/info_client.py). Loads [`spotMeta`](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint) and, for perps, merges [`meta` with `dex=""`](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint) plus [`meta` for each `perpDexs`](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint) entry (e.g. `xyz` → `xyz:CL`).

| Field | Meaning |
|-------|---------|
| `base_url` | Active API base. |
| `perp` | All merged perp `coin` names (primary + builder DEXes). |
| `perp_by_dex` | `{ "dex": "" \| "xyz" \| …, "assets": [ … ] }`. |
| `spot` | Spot pair names from `spotMeta.universe`. |

Perp vs spot `coin` formats: [Perpetuals vs Spot](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint#perpetuals-vs-spot), [asset IDs](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/asset-ids).

---

## Reference: `place_order` and `cancel_order`

Both POST signed actions to the Hyperliquid [**Exchange** API](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/exchange-endpoint) (SDK-style: build → sign → submit).

**`place_order`**

| Flag | Role |
|------|------|
| `--coin` | From `list_markets` for this network ([Exchange → Asset](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/exchange-endpoint#asset)). |
| `--side` | `buy` / `sell`. |
| `--sz` | Size in **coin units** (not USDC notional). |
| `--limit-px` | Limit price (**mutually exclusive** with `--market`). |
| `--market` | Aggressive IOC from mid ± `--slippage` (default `0.05`). |
| `--tif` | `Gtc` / `Ioc` / `Alo` for **limit** only ([Place an order](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/exchange-endpoint#place-an-order)). |
| `--reduce-only` | Only reduce position. |
| `--leverage` | Runs [`updateLeverage`](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/exchange-endpoint) first; output `{ "updateLeverage": …, "order": … }`. |
| `--isolated` / `--cross` | With `--leverage`: margin mode (builder `xyz:*` usually needs **`--isolated`**). |

**`cancel_order`:** `--coin` + `--oid` ([Cancel](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/exchange-endpoint#cancel-order-s)). No `cancelByCloid` in this CLI.

---

## Scripts (`scripts/`)

| Script | Description |
|--------|-------------|
| [scripts/generate_wallet.py](scripts/generate_wallet.py) | New keypair; `--write-env` → `PRIVATE_KEY` in `.env`. |
| [scripts/test_phase1.py](scripts/test_phase1.py) | Offline: signing + `smoke_signing`. |
| [scripts/test_phase2.py](scripts/test_phase2.py) | Network: `InfoClient` + `info_snapshot`. |
| [scripts/test_phase3.py](scripts/test_phase3.py) | `ExchangeClient` + trade report; optional risky live order. |
| [scripts/test_phase4.py](scripts/test_phase4.py) | Withdraw dry-run + `--execute` guard. |

```bash
python scripts/generate_wallet.py
python scripts/test_phase1.py
python scripts/test_phase2.py
python scripts/test_phase3.py
python scripts/test_phase4.py
```

---

## Project layout and Python API

```
.
├── manage.py
├── config/                 # Django settings (loads .env)
├── signing/                # env + SigningModule
├── trading/
│   ├── services/
│   │   ├── info_client.py
│   │   ├── exchange_client.py
│   │   ├── balances.py
│   │   └── trade_history.py
│   └── management/commands/
└── scripts/
```

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

**Extend:** add read calls on `InfoClient` / `raw_info`; add signed flows on `ExchangeClient`. Centralize network rules in `signing/env.py`.

---

## Admin and performance

```bash
python manage.py runserver
```

Admin: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/) — optional `TradingAccount` labels (no keys stored).

First use of `Info` / `InfoClient` / `ExchangeClient` may be slow while the SDK loads `meta` / `spotMeta` over the network.
