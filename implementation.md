

```markdown
# Hyperliquid Client (MVP Implementation Plan)

## 🎯 Goal

Build a minimal client that:
- Uses a private key stored internally (never exported)
- Interacts with Hyperliquid via signed API requests
- Supports:
  - Account (address) usage
  - Deposits tracking
  - Trading
  - Withdrawals
  - Trade history

---

## 🧩 Core Idea

Hyperliquid does NOT require account creation.

- Your account = your wallet address
- All actions = signed messages
- No MetaMask needed

---

## 🏗️ Architecture (MVP)

Trading Engine
↓
Hyperliquid Client
↓
Signing Service (holds private key)
↓
Hyperliquid API

---

## ⚙️ Step-by-Step Implementation

### 1. Setup Signing Service

Expose:

#### Get Address
GET /address  
→ returns: `0xYourAddress`

#### Sign Payload
POST /sign  
Input:
```

{ "message": ... }

```
Output:
```

{ "signature": ... }

```

---

### 2. Initialize Account

- Call `/address`
- Store the returned address

✅ This is your Hyperliquid account

---

### 3. Deposit

- Send USDC to your address
- No signing required

Track deposits via:
```

POST /info
{
"type": "userFills",
"user": "0xYourAddress"
}

```

---

### 4. Nonce Management (IMPORTANT)

Create a simple counter per account:

```

nonce = getNonce(address)
incrementNonce(address)

```

Store in:
- Redis OR DB

---

### 5. Place Order

#### Build action:
```

{
"type": "order",
"orders": [{
"coin": "OIL",
"is_buy": false,
"sz": "100",
"limit_px": "75.5"
}]
}

```

#### Flow:
1. Add nonce
2. Send to `/sign`
3. Send signed payload to:
```

POST /exchange

```

---

### 6. Cancel Order

Same flow as order:
```

{
"type": "cancel",
...
}

```

---

### 7. Get Data (No Signing Needed)

#### Trade History
```

POST /info
{
"type": "userFills",
"user": "0xYourAddress"
}

```

#### Open Orders
```

type: "openOrders"

```

#### Positions
```

type: "clearinghouseState"

```

---

### 8. Withdraw (Use Separate Service)

Create `withdrawalService`

#### Build action:
```

{
"type": "withdraw",
"destination": "0xYourWallet",
"amount": "1000",
"coin": "USDC"
}

```

#### Flow:
1. Validate request
2. Send to `/sign`
3. Send to `/exchange`

---

## 🔐 Security (MVP)

- Private key ONLY inside signing service
- Never log raw messages or signatures
- Restrict withdrawal access
- Validate before signing

---

## 📦 Recommended Tools

- Language: Python or TypeScript
- Storage:
  - Redis → nonce
  - Postgres → logs/history

---

## ⚠️ MVP Risks

- Nonce mismatch → failed trades
- No retry logic → lost requests
- No rate limits → risk exposure

---

## ✅ MVP Checklist

- [ ] Signing service working
- [ ] Address derived
- [ ] Nonce tracking implemented
- [ ] Order placement works
- [ ] Data fetching works
- [ ] Withdrawal flow works

