# Hyperliquid MVP Client — Implementation & Reference

This document is the **technical reference** for `hyperliquidity-mvp-client`: architecture, env, modules, Hyperliquid-specific behavior, and phased delivery. Use it (or excerpts) as **context in other chats** alongside [README.md](README.md).

---

## Purpose

Minimal **Django** app that:

- Loads **`PRIVATE_KEY` only from `.env`** (never DB, never committed).
- Derives the wallet address; signs writes via **EIP-712** using the official **`hyperliquid-python-sdk`** helpers.
- Separates **`signing/`** (framework-free) from **`trading/`** (Django + services + CLI).
- Reads **`/info`** via **`InfoClient`**; posts signed payloads to **`/exchange`** via **`ExchangeClient`** + **`SigningModule`**.
- Uses **Django admin** only for non-secret metadata (`TradingAccount` labels).

---

## Quick context (for AI / copy-paste)

- **Stack:** Django, `hyperliquid-python-sdk`, `eth_account`, `python-dotenv`, SQLite dev DB.
- **API base:** From `.env` only — `HYPERLIQUID_MAINNET_API_URL`, `HYPERLIQUID_TESTNET_API_URL`, optional `HYPERLIQUID_API_URL`, `HYPERLIQUID_MAINNET`. Resolved in `signing/env.py`; exposed as `settings.HYPERLIQUID_API_URL`.
- **Signing:** `SigningModule` in `signing/signer.py` — only reader of `PRIVATE_KEY`.
  - **L1 actions** (phantom agent): `sign_l1_action` — orders, cancel, `updateLeverage`, `updateIsolatedMargin`, `usdClassTransfer`-style payloads posted with `nonce` in body.
  - **User-signed typed data:** `sign_withdraw_from_bridge_action` (`withdraw3`), `sign_usd_class_transfer_action` (`usdClassTransfer`), `sign_send_asset_action` (`sendAsset`).
- **Services:** `trading/services/info_client.py` (`InfoClient`), `exchange_client.py` (`ExchangeClient`), `balances.py`, `trade_history.py`; `trading/deposit_info.py` for wallet deposit text.
- **CLI:** `trading/management/commands/*.py` — see [Management commands](#management-commands) below.
- **Tests:** `scripts/test_phase1.py` … `test_phase4.py`.
- **Hyperliquid gotchas:**
  - **`list_markets`** merges `meta(dex="")` + `meta(dex=name)` for each builder DEX from `perpDexs` — builder coins are `xyz:SYMBOL`.
  - **`ExchangeClient`** constructs `Info(perp_dexs=[""]+builder names)` so `name_to_asset("xyz:…")` works.
  - **Builder DEX margin:** USDC on primary perp (`dex=""`) is **not** on the `xyz` book — use **`send_usdc_between_perp_dexes`** (`sendAsset`) before `update_isolated_margin` on `xyz:*` if funds are only on the default DEX.
  - **Bridge (Bridge2 docs):** deposits are often credited in about a minute; withdrawals after `withdraw3` are often visible on Arbitrum in a few minutes.
  - **`deposit_history` / `withdraw_history`:** `userNonFundingLedgerUpdates` — **finalized** ledger rows only; pending chain txs may be absent until credited.

---

## Core API model (Hyperliquid)

- **Reads:** `POST https://…/info` with typed body (`clearinghouseState`, `userFills`, `userNonFundingLedgerUpdates`, …).
- **Writes:** `POST https://…/exchange` with `action`, `nonce` (ms timestamp), `signature`, optional `vaultAddress`, `expiresAfter`.
- **Nonce:** Use **current time in milliseconds** for exchange actions (SDK `get_timestamp_ms()` pattern).

---

## Architecture

```
Django (config/, trading/, manage.py)
    ↓
InfoClient / ExchangeClient (trading/services/)
    ↓
SigningModule (signing/signer.py)  ← only module reading PRIVATE_KEY
    ↓
Hyperliquid HTTP API (/info, /exchange)
```

- **`ExchangeClient`** builds action dicts, calls **`SigningModule`**, then **`API.post("/exchange", payload)`** — it does **not** embed wallet logic like the SDK’s high-level `Exchange` class for everything; it mirrors the **sign → post** boundary explicitly.
- **`Info`** is constructed with **`skip_ws=True`** and full **`perp_dexs`** list so multi-DEX metadata resolves.

---

## Environment variables

**Source of truth:** [.env.example](.env.example). Required keys are also listed in `signing/required_env.py` where applicable.

| Variable | Role |
|----------|------|
| `PRIVATE_KEY` | Hex private key for signing. |
| `HYPERLIQUID_MAINNET_API_URL` | Canonical mainnet API URL. |
| `HYPERLIQUID_TESTNET_API_URL` | Canonical testnet API URL. |
| `HYPERLIQUID_API_URL` | Optional override; if unset, `HYPERLIQUID_MAINNET` picks canonical URL. |
| `HYPERLIQUID_MAINNET` | Boolean when `HYPERLIQUID_API_URL` unset. |
| `HYPERLIQUID_DOCS_URL` | Docs URL string for `wallet_info`. |
| `DEPOSIT_USDC_LAYER2_NAME` | Human label (e.g. Arbitrum One). |
| `DEPOSIT_ARBITRUM_CHAIN_ID` | Chain id string (e.g. `42161`). |
| `HYPERLIQUID_REAL_MONEY_ACK` | Must be `I_UNDERSTAND` for `withdraw --execute`. |
| `DJANGO_SECRET_KEY` | Optional Django secret. |

---

## Repository layout (current)

```
.
├── config/                 # Django project; settings loads dotenv, HYPERLIQUID_API_URL
├── signing/
│   ├── env.py              # URL + mainnet flag for signing alignment
│   ├── required_env.py     # Required keys for tooling / deposit validation
│   └── signer.py           # SigningModule
├── trading/
│   ├── models.py           # TradingAccount (metadata)
│   ├── admin.py
│   ├── deposit_info.py     # Deposit network summary for wallet_info
│   ├── services/
│   │   ├── info_client.py  # InfoClient + list_symbols, ledger helpers, …
│   │   ├── exchange_client.py
│   │   ├── balances.py
│   │   └── trade_history.py
│   └── management/commands/
└── scripts/
    ├── generate_wallet.py
    └── test_phase1.py … test_phase4.py
```

---

## SigningModule (`signing/signer.py`)

| Method | Used for |
|--------|----------|
| `sign_l1_action(action, nonce, vault_address?)` | Order, cancel, `updateLeverage`, `updateIsolatedMargin` |
| `sign_withdraw_from_bridge_action(action)` | `withdraw3` |
| `sign_usd_class_transfer_action(action)` | Spot ↔ perp `usdClassTransfer` |
| `sign_send_asset_action(action)` | `sendAsset` (perp DEX ↔ perp DEX USDC) |

`expires_after` optional on `SigningModule` constructor; passed into L1 sign helper.

---

## InfoClient (`trading/services/info_client.py`)

Thin wrapper over **`hyperliquid.info.Info`** (`skip_ws=True`).

Notable:

- **`list_symbols()`** — `perp`, `spot`, **`perp_by_dex`** (primary + each `perpDexs` name).
- **`get_non_funding_ledger`**, **`get_deposits`**, **`get_withdrawals`** — `userNonFundingLedgerUpdates`.
- **`get_account_balances`** — uses `summarize_account_balances` (`balances.py`); optional **`dex`** for clearinghouse.
- **`snapshot`**, **`trade_history_report`**, **`get_order_status`**, etc.

---

## ExchangeClient (`trading/services/exchange_client.py`)

- **`place_limit_order`**, **`place_market_order`** (IOC + slippage from mid).
- **`cancel_order`**
- **`update_leverage`**, **`update_isolated_margin`**
- **`send_usdc_between_perp_dexes`** — `sendAsset`; canonical USDC token string from `spotMeta`.
- **`usd_class_transfer`**, **`withdraw_to_wallet`**

Constructs **`Info(..., perp_dexs=_perp_dex_ids_for_info(...))`** so all builder universe names resolve.

---

## Management commands

| Command | Purpose |
|---------|---------|
| `smoke_signing` | Offline L1 sign smoke |
| `wallet_info` | Address + deposit help |
| `account_balances` | Perp + spot; `--dex` for builder clearinghouse |
| `list_markets` | Perp/spot names + `perp_by_dex` |
| `info_snapshot` | Full read-only snapshot |
| `trade_history` | Fills + optional `--enrich` |
| `deposit_history` | Ledger deposits (`--days`) |
| `withdraw_history` | Ledger withdraws (`--days`) |
| `place_order` | Limit or market; optional `--leverage`, `--isolated` / `--cross` |
| `cancel_order` | By `coin` + `oid` |
| `update_leverage` | Standalone `updateLeverage` |
| `update_isolated_margin` | `updateIsolatedMargin` |
| `send_perp_usdc` | `sendAsset` between perp DEX books |
| `transfer_usd_class` | Spot ↔ perp |
| `withdraw` | `withdraw3`; dry-run unless `--execute` |

---

## Hyperliquid operational notes

1. **`--limit-px` vs `--market`** on `place_order` — mutually exclusive.
2. **Minimum order notional** — often ~$10 on many perps; API returns explicit errors.
3. **Builder perps** — isolated / noCross: fund **`xyz`** book first, then isolated margin, then trade (see README use case).
4. **Cancel** — only **open** orders; filled trades require a **new** order to close (e.g. `reduce-only` opposite side).
5. **Ledger history** — not a mempool view; pending deposits/withdrawals may be missing until finalized.

---

## Implementation phases (delivery history)

### Phase 1 — Django + SigningModule

Runnable Django project; `SigningModule`; `smoke_signing`; `scripts/generate_wallet.py`, `scripts/test_phase1.py`.

### Phase 2 — Read-only `/info`

`InfoClient`, `info_snapshot`, deposits from ledger, `scripts/test_phase2.py`.

### Phase 3 — Trading + history

`ExchangeClient` (orders, cancel, leverage, isolated margin, `sendAsset`, spot↔perp), `trade_history`, `list_markets` (multi-DEX), `place_order` / `cancel_order` / `update_leverage` / `update_isolated_margin` / `send_perp_usdc`, `scripts/test_phase3.py`.

### Phase 4 — Withdrawals

`withdraw_to_wallet`, `manage.py withdraw` (dry-run default, `--execute` + `HYPERLIQUID_REAL_MONEY_ACK`), `scripts/test_phase4.py`.

---

## Security rules

| Rule | Detail |
|------|--------|
| `.env` gitignored | Never commit secrets |
| No key in DB | `TradingAccount` is labels only |
| Testnet first | For new flows |
| `withdraw --execute` | Explicit env ack |

---

## Testing scripts

| Script | What it checks |
|--------|----------------|
| `test_phase1.py` | Key, `SigningModule`, `smoke_signing` |
| `test_phase2.py` | `InfoClient` / `info_snapshot` (network) |
| `test_phase3.py` | `ExchangeClient` URL alignment, `trade_history_report` (optional live order via env) |
| `test_phase4.py` | Withdraw dry-run, `--execute` blocked without ack |

---

## Future work

- Remote / HSM signing: replace internals of `SigningModule` only; keep the same public methods.

---

## MVP checklist

- [x] Phase 1: Django, admin, signing smoke
- [x] Phase 2: Read `/info`
- [x] Phase 3: Trade, multi-DEX markets, leverage, isolated, sendAsset, history commands
- [x] Phase 4: Withdraw with guards
- [x] Ledger deposit/withdraw history CLI
- [ ] Verify `.gitignore` excludes `.env` before publishing

---

## User flow (summary)

See **[README.md — End-to-end user flow](README.md#end-to-end-user-flow)** for the step table (key → deposit → balances → spot/perp → trade → history → cancel → withdraw).
