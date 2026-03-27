---
name: morph-bridge
version: 1.3.0
description: Cross-chain swap with JWT auth — quote prices, create orders, submit transactions, track order status across 6 chains
---

# Morph Bridge — AI Agent Skill

> Cross-chain swap via Bulbaswap Cross-Chain Swap API.
> Supports 6 chains: Morph, Ethereum, Base, BNB Chain, Arbitrum, Polygon.
> All commands output JSON. Includes JWT-authenticated order management.

## Activation Triggers

Use this skill when the user wants to: bridge tokens across chains, get a cross-chain swap quote, search tokens on multiple chains, check token balances with USD prices, or create and manage cross-chain swap orders.

## Quick Start

```bash
pip install requests eth_account

# Run from repository root
python3 scripts/morph_api.py <command> [options]
```

No API keys required for queries. Order management requires JWT authentication via `bridge-login`.

## BGW Routing Note

Decide the mode once via the root [SKILL.md](../../SKILL.md) and [docs/social-wallet-integration.md](../../docs/social-wallet-integration.md).

- This skill handles bridge quotes, token discovery, JWT auth, and order management.
- `bridge-login`, `bridge-make-order`, `bridge-submit-order`, and `bridge-swap` require `--private-key` (local signing only).
- Social Login Wallet users should use BGW's swap flow for cross-chain execution — see [social-wallet-integration.md](../../docs/social-wallet-integration.md).
- `bridge-quote`, `bridge-chains`, `bridge-tokens`, `bridge-token-search`, and `bridge-balance` are read-only and work for any wallet type.

---

## Supported Chains

| Chain | Name |
|-------|------|
| morph | Morph |
| eth | Ethereum |
| base | Base |
| bnb | BNB Chain |
| arbitrum | Arbitrum |
| matic | Polygon |

Use `bridge-chains` to get the latest list.

---

## Commands

### `bridge-chains`
List all supported chains for cross-chain swap.
```bash
python3 scripts/morph_api.py bridge-chains
```

### `bridge-tokens`
List available tokens for cross-chain swap. Optionally filter by chain.
```bash
# All tokens across all chains
python3 scripts/morph_api.py bridge-tokens

# Tokens on Morph only
python3 scripts/morph_api.py bridge-tokens --chain morph
```

### `bridge-token-search`
Search tokens by symbol or contract address across chains.
```bash
# Search by symbol
python3 scripts/morph_api.py bridge-token-search --keyword USDT

# Search on a specific chain
python3 scripts/morph_api.py bridge-token-search --keyword USDC --chain base
```

### `bridge-quote`
Get a cross-chain or same-chain swap quote with price, fees, and route info.
```bash
# Cross-chain: USDT on Base → USDT on BNB
python3 scripts/morph_api.py bridge-quote \
  --from-chain base --from-token 0x833589fcd6edb6e08f4c7c32d4f71b54bda02913 \
  --amount 2 --to-chain bnb \
  --to-token 0x55d398326f99059ff775485246999027b3197955 \
  --from-address 0xYourAddress

# Same-chain: ETH → USDT on Morph
python3 scripts/morph_api.py bridge-quote \
  --from-chain morph --from-token ETH \
  --amount 0.01 --to-chain morph \
  --to-token USDT \
  --from-address 0xYourAddress
```

### `bridge-balance`
Query token balance and USD price for an address on any supported chain.
```bash
python3 scripts/morph_api.py bridge-balance \
  --chain morph --token USDT --address 0xYourAddress

# Native ETH balance
python3 scripts/morph_api.py bridge-balance \
  --chain eth --token ETH --address 0xYourAddress
```

### `bridge-login`
Sign in with an EIP-191 wallet signature to get a JWT access token (valid 24h). Required for order management commands.
```bash
python3 scripts/morph_api.py bridge-login --private-key 0xYourKey
```
Returns `accessToken` in response data.

### `bridge-make-order`
Create a cross-chain swap order. Returns `orderId` and unsigned transactions (`txs`) to sign.
```bash
python3 scripts/morph_api.py bridge-make-order --jwt <JWT> \
  --from-chain morph --from-contract 0xe7cd86e13AC4309349F30B3435a9d337750fC82D \
  --from-amount 10 --to-chain base \
  --to-contract 0x833589fcd6edb6e08f4c7c32d4f71b54bda02913 \
  --to-address 0xRecipient --market stargate \
  --slippage 0.5 --feature no_gas
```

### `bridge-submit-order`
Submit signed transactions for an existing swap order.
```bash
python3 scripts/morph_api.py bridge-submit-order --jwt <JWT> \
  --order-id abc123 --signed-txs 0xSignedTx1,0xSignedTx2
```

### `bridge-swap`
One-step cross-chain swap: create order, sign transactions, and submit — all in one command. This is the **recommended** way for agents to execute bridge swaps (equivalent to `bridge-make-order` → sign → `bridge-submit-order`).
```bash
python3 scripts/morph_api.py bridge-swap --jwt <JWT> \
  --from-chain morph --from-contract USDT.e --from-amount 5 \
  --to-chain base --to-contract USDC \
  --market stargate --private-key 0xYourKey

# With optional parameters
python3 scripts/morph_api.py bridge-swap --jwt <JWT> \
  --from-chain morph --from-contract USDT.e --from-amount 5 \
  --to-chain base --to-contract USDC \
  --to-address 0xRecipient --market stargate \
  --slippage 0.5 --feature no_gas --private-key 0xYourKey
```
- `--to-address` defaults to sender address if omitted
- Returns `orderId` for status tracking via `bridge-order`

### `bridge-order`
Query the status of a swap order.
```bash
python3 scripts/morph_api.py bridge-order --jwt <JWT> --order-id abc123
```

### `bridge-history`
Query historical swap orders. Supports pagination and status filtering.
```bash
# Default (page 1)
python3 scripts/morph_api.py bridge-history --jwt <JWT>

# With filters
python3 scripts/morph_api.py bridge-history --jwt <JWT> --page 1 --page-size 10 --status completed
```

---

## Authentication

Order management commands (`bridge-make-order`, `bridge-submit-order`, `bridge-swap`, `bridge-order`, `bridge-history`) require a JWT access token obtained via `bridge-login`.

### Auth Flow
1. `bridge-login --private-key 0x...` → signs an EIP-191 message with timestamp
2. API returns `accessToken` (JWT, valid 24h)
3. Pass the token to subsequent commands via `--jwt <JWT>`

### Security Rules
- **Private keys** are only used locally for EIP-191 message signing in `bridge-login`. They are never sent to the API.
- **JWT tokens** are sent as `Authorization: Bearer <token>` headers. They expire after 24 hours.
- **Always confirm with the user** before executing `bridge-make-order` or `bridge-swap` — show the swap details (chains, tokens, amounts) before creating the order.
- **Always confirm with the user** before executing `bridge-submit-order` — show the orderId and number of signed transactions before broadcasting to the chain.

## Difference from morph-dex

| Feature | morph-dex | morph-bridge |
|---------|-----------|-------------|
| API Path | `/v2/quote` | `/v2/order/*` |
| Scope | Same-chain swap (Morph only) | Cross-chain + same-chain (6 chains) |
| Execution | `dex-send` broadcasts tx | `bridge-swap` (recommended) or `bridge-make-order` → sign → `bridge-submit-order` |
| Auth | None | JWT via `bridge-login` (for orders) |
| Token format | `ETH` for native | `""` (empty string) for native |
| Use when | Swapping tokens on Morph | Cross-chain transfers or multi-chain swaps |

## Important Notes

- **Native token format**: Bridge API uses empty string `""` for native tokens. The CLI handles this automatically — pass `ETH` (on ETH/Morph/Base/Arbitrum chains), `BNB` (on BNB Chain), or `POL`/`MATIC` (on Polygon).
- **Multi-chain symbol resolution**: Token symbols are resolved per chain. `USDC` on `base` resolves to Base USDC (`0x8335...`), while `USDC` on `morph` resolves to Morph USDC (`0xCfb1...`). Use `bridge-token-search` for tokens not in the built-in registry.
- **Quote fees**: The quote response includes fee breakdown, price impact, and route information. Check `docs/bridge.md` for field details.
- **JWT expiry**: Access tokens from `bridge-login` expire after 24 hours. Re-authenticate if you get auth errors.

## Common Workflows

**Check cross-chain swap price:**
```
bridge-chains (list supported chains) → bridge-token-search --keyword USDT (find token on target chain) → bridge-quote (get price)
```

**Execute a cross-chain swap (recommended):**
```
bridge-login (get JWT) → bridge-quote (get price + market) → bridge-swap (create, sign, submit in one step) → bridge-order (track status)
```

**Execute a cross-chain swap (advanced — manual signing):**
```
bridge-login (get JWT) → bridge-quote (get price + market) → bridge-make-order (create order, get txs) → sign txs locally → bridge-submit-order (submit signed txs) → bridge-order (track status)
```

**Compare prices across chains:**
```
bridge-quote (chain A → chain B) → bridge-quote (chain A → chain C) → compare toAmount
```

**Check multi-chain portfolio:**
```
bridge-balance (chain 1) → bridge-balance (chain 2) → ... (each chain)
```

**Track order status:**
```
bridge-order --order-id X (poll until completed) or bridge-history (list all orders)
```

## Cross-Skill Integration

- Use `bridge-token-search` to find token addresses, then `dex-quote` (morph-dex) for on-chain Morph swaps.
- Use `bridge-balance` for multi-chain balance checks alongside `balance` / `token-balance` (morph-wallet) for Morph-specific queries.
- Use `bridge-quote` to compare cross-chain rates with `dex-quote` (morph-dex) same-chain rates.
- If the wallet source is a BGW Social Login Wallet, use BGW for the wallet context first and then use this skill for route selection and bridge workflow reasoning.
