# hyperliquidity-mvp-client

Minimal Django-backed client for [Hyperliquid](https://hyperliquid.xyz): keep your private key in local `.env`, derive the address, sign with EIP-712 via the official SDK, and query account state over HTTPS without exporting the key.

For architecture and roadmap, see [implementation.md](implementation.md).

## Setup (short)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # set PRIVATE_KEY and optional network vars
python manage.py migrate
```

Run scripts and management commands from the **repository root** with the virtualenv activated (or use `.venv/bin/python` explicitly).

---

## Scripts (`scripts/`)

Standalone Python utilities. They load `.env` from the project root when relevant (via `python-dotenv` inside Django settings is not used by all scripts; `test_phase1` / `test_phase2` call `load_dotenv` on `.env` themselves).

| Script | Description |
|--------|-------------|
| [scripts/generate_wallet.py](scripts/generate_wallet.py) | Creates a new random secp256k1 **private key**, **uncompressed public key** (hex), and **Ethereum address**. Optional: write `PRIVATE_KEY` into `.env`. |
| [scripts/test_phase1.py](scripts/test_phase1.py) | **Phase 1 regression test** (no network): validates `.env` key, matches `eth_account` and `SigningModule` addresses, runs an offline L1 sign smoke, and runs `manage.py smoke_signing`. Exit `0` = pass. |
| [scripts/test_phase2.py](scripts/test_phase2.py) | **Phase 2 regression test** (**requires internet**): calls live Hyperliquid `/info` via `InfoClient`, checks response shapes, then runs `manage.py info_snapshot` and validates JSON. Exit `0` = pass. |

### `generate_wallet.py`

```bash
# Print private key, public key, and address only (does not modify files)
python scripts/generate_wallet.py

# Create or update the PRIVATE_KEY= line in .env (other lines preserved)
python scripts/generate_wallet.py --write-env
```

**Note:** `--write-env` replaces an existing `PRIVATE_KEY` line. Do not commit `.env`.

### `test_phase1.py`

```bash
python scripts/test_phase1.py
```

Requires a valid `PRIVATE_KEY` in `.env`. No API calls.

### `test_phase2.py`

```bash
python scripts/test_phase2.py
```

Requires `PRIVATE_KEY` in `.env` (only to know which address to query) and outbound HTTPS. The first `InfoClient()` construction can be slow while the SDK loads metadata.

---

## Django management commands

These require Django setup (`DJANGO_SETTINGS_MODULE=config.settings`); use `manage.py` from the repo root.

| Command | Description |
|---------|-------------|
| `smoke_signing` | Loads `PRIVATE_KEY`, prints the wallet address, and signs a minimal L1 action (`scheduleCancel`) locally. **Does not** POST to the API. |
| `info_snapshot` | Fetches a read-only JSON **snapshot** (clearinghouse, positions, open orders, fills, deposit ledger rows, spot state) from `/info`. **No signing.** |

### `smoke_signing`

```bash
python manage.py smoke_signing
```

### `info_snapshot`

```bash
# Default: address derived from PRIVATE_KEY in .env
python manage.py info_snapshot

# Any address (read-only; key not required for the query itself)
python manage.py info_snapshot --address 0xYourAddress

# Compact JSON (single line)
python manage.py info_snapshot --indent 0
```

---

## Environment variables (for scripts and Django)

See [.env.example](.env.example). The important ones:

- **`PRIVATE_KEY`** — Required for signing and for default address in snapshot/tests.
- **`HYPERLIQUID_MAINNET`** — If `HYPERLIQUID_API_URL` is unset, chooses mainnet vs testnet (default: mainnet).
- **`HYPERLIQUID_API_URL`** — Optional explicit API base; if set to the official mainnet or testnet URL, signing domain stays aligned (see `signing/env.py`).

---

## Admin and server

```bash
python manage.py createsuperuser
python manage.py runserver
```

Admin URL: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)
