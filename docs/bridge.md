# Cross-Chain Swap (Bridge) — Deep Guide

> Reference for the cross-chain swap API via Bulbaswap (`/v2/order/*`).
> Load this guide when the user asks about cross-chain swaps, bridge quotes, order management, or multi-chain token operations.

If the user has a Social Login Wallet, use BGW's swap flow for cross-chain execution — see [social-wallet-integration.md](social-wallet-integration.md) for routing and setup details. This guide covers Morph-side bridge logic for local-key execution via `bridge-swap --private-key`.

## Supported Chains

The bridge supports swaps between these 6 chains:

| Chain Key | Network | Native Token |
|-----------|---------|-------------|
| morph | Morph L2 (Chain ID 2818) | ETH |
| eth | Ethereum Mainnet | ETH |
| base | Base L2 | ETH |
| bnb | BNB Chain | BNB |
| arbitrum | Arbitrum One | ETH |
| matic | Polygon PoS | MATIC |

Use `bridge-chains` to fetch the current list — new chains may be added.

## API Endpoints

All endpoints use base URL `https://api.bulbaswap.io`. Query endpoints require no authentication; order management endpoints require JWT.

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/v2/order/chainList` | GET | None | List supported chains |
| `/v2/order/tokenList` | POST | None | List tokens (optionally filtered by chain) |
| `/v2/order/tokenSearch` | POST | None | Search tokens by symbol or address |
| `/v2/order/getSwapPrice` | POST | None | Get swap quote with price, fees, route |
| `/v2/order/tokenBalancePrice` | POST | None | Get token balance + USD price |
| `/v1/auth/sign-in` | POST | None | EIP-191 sign-in, returns JWT |
| `/v2/order/makeSwapOrder` | POST | JWT | Create swap order, returns unsigned txs |
| `/v2/order/submitSwapOrder` | POST | JWT | Submit signed transactions |
| `/v2/order/getSwapOrder` | POST | JWT | Query order status |
| `/v2/order/history` | POST | JWT | Query historical orders |

## Response Format

All responses follow the same structure:

```json
{
  "status": 0,
  "msg": "success",
  "data": { ... }
}
```

- `status: 0` → success
- `status: non-zero` → error (check `error_code` and `msg`)

## Native Token Handling

**Critical**: The bridge API uses **empty string** `""` for native tokens, not the conventional representations:

| Convention | Value | Used By |
|-----------|-------|---------|
| Zero address | `0x0000...0000` | Most EVM tools |
| Literal string | `"ETH"` | Bulbaswap DEX `/v2/quote` |
| **Empty string** | `""` | **Bridge API `/v2/order/*`** |

The CLI handles this automatically via the multi-chain token registry:
- `ETH` on morph/eth/base/arbitrum → `""` (native)
- `BNB` on bnb → `""` (native)
- `POL` or `MATIC` on matic → `""` (native)
- `ETH` on bnb → `0x2170...` (wrapped Binance-Peg Ethereum, **not** native)

## Multi-Chain Symbol Resolution

Token symbols are resolved per chain using the built-in `BRIDGE_TOKENS` registry. The same symbol maps to different contract addresses on different chains:

```
USDC on morph    → 0xCfb1186F4e93D60E60a8bDd997427D1F33bc372B
USDC on base     → 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
USDC on eth      → 0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48
```

For tokens not in the registry, use `bridge-token-search --keyword <symbol> --chain <chain>` to find the address, then pass the contract address directly.

## Quote Response Fields

The `bridge-quote` (getSwapPrice) response contains:

```json
{
  "toAmount": "1.99",
  "fee": "0.01",
  "priceImpact": "0.05",
  "features": ["no_gas"],
  "market": "stargate",
  "estimatedTime": 120,
  "fromToken": { ... },
  "toToken": { ... },
  "route": [ ... ]
}
```

### Key Fields

| Field | Description |
|-------|-------------|
| `toAmount` | Estimated amount received on destination chain |
| `fee` | Total fee for the swap (bridge fee + gas) |
| `priceImpact` | Price impact as percentage (e.g. `"0.05"` = 0.05%) |
| `features` | Special features — see below |
| `market` | The bridge/DEX protocol used for routing |
| `estimatedTime` | Estimated completion time in seconds |
| `route` | Detailed routing path |

### Features

| Feature | Meaning |
|---------|---------|
| `no_gas` | Destination gas is included — user does not need destination chain gas tokens |

When `no_gas` is present, the user can receive tokens on the destination chain without holding native gas tokens there.

## Same-Chain vs Cross-Chain Quotes

The bridge API supports both:

### Cross-Chain (different fromChain and toChain)
- Routes through bridge protocols (Stargate, LayerZero, etc.)
- Has bridge fees and estimated settlement time
- May have `no_gas` feature

### Same-Chain (same fromChain and toChain)
- Routes through DEX aggregation (similar to `/v2/quote`)
- Lower fees, near-instant settlement
- Useful for comparing with `dex-quote`

## Common Error Codes

| Code | Meaning | Resolution |
|------|---------|------------|
| 80001 | Insufficient balance | User does not have enough of the source token |
| 80002 | Amount too small | Increase the swap amount |
| 80005 | Insufficient liquidity | Try a smaller amount or different token pair |
| 80006 | Route not found | This token pair may not be supported |
| 80010 | Chain not supported | Check `bridge-chains` for supported chains |

## Token Address Discovery

The CLI includes a built-in multi-chain token registry (`BRIDGE_TOKENS`). Common tokens resolve automatically by symbol when a chain is provided. For tokens not in the registry:

1. Use `bridge-token-search --keyword USDT --chain base` to find the address
2. Pass the contract address directly (always works regardless of registry)

## Agent Decision Flow

```
User wants to move tokens between chains?
  ├── YES → bridge-quote (cross-chain)
  │         └── Show: toAmount, fee, estimatedTime, features
  │         └── Execute: bridge-swap (recommended one-step command)
  └── NO (same chain swap on Morph?)
        ├── YES → dex-quote (morph-dex skill, better for Morph-only swaps)
        └── NO (same chain swap on other chain?)
              └── bridge-quote with same fromChain/toChain
                    └── Execute: bridge-swap
```

## Authentication (JWT)

Order management commands require a JWT access token obtained via EIP-191 wallet signature.

### Sign-In Flow

1. Generate a timestamp: `int(time.time() * 1000)` (milliseconds)
2. Construct the message:
   ```
   Welcome to Bulba.

   Please sign this message to verify your wallet.

   Timestamp: <timestamp>.

   Your authentication status will be reset after 24 hours.
   ```
3. Sign with EIP-191 (`eth_account.messages.encode_defunct`)
4. POST `/v1/auth/sign-in` with `{address, signature, timestamp}`
5. Response contains `accessToken` (JWT, valid 24h)

### Using the Token

Pass the JWT in subsequent requests as:
- CLI: `--jwt <JWT>`
- HTTP: `Authorization: Bearer <token>` header

## Order Management Flow

### Complete Cross-Chain Swap — Recommended (bridge-swap)

```
1. bridge-login --private-key 0x...                              → JWT
2. bridge-quote --from-chain morph ... --from-address 0x...      → toAmount, market, fee
3. bridge-swap --jwt <JWT> ... --market stargate --private-key   → orderId (creates, signs, submits in one step)
4. bridge-order --jwt <JWT> --order-id X                          → poll until completed
```

### Complete Cross-Chain Swap — Advanced (manual signing)

```
1. bridge-login --private-key 0x...                              → JWT
2. bridge-quote --from-chain morph ... --from-address 0x...      → toAmount, market, fee
3. bridge-make-order --jwt <JWT> ... --market stargate            → orderId + txs[{to, calldata, value, gasLimit, ...}]
4. Agent signs each tx using eth_account (may involve different RPCs per chain)
5. bridge-submit-order --jwt <JWT> --order-id X --signed-txs 0x...
6. bridge-order --jwt <JWT> --order-id X                          → poll until completed
```

### Step Details

**Step 3 — makeSwapOrder response:**
```json
{
  "orderId": "abc123",
  "txs": [
    {
      "chainId": 2818,
      "data": {
        "nonce": "0",
        "to": "0xContractAddress",
        "value": "0",
        "gasLimit": "200000",
        "gasPrice": "50000000",
        "calldata": "0x..."
      }
    }
  ]
}
```

**Step 4 — Transaction signing:**
- Each tx in `txs` may be on a different chain (different `chainId`)
- Agent must use the appropriate RPC for each chain
- Sign with `eth_account.Account.sign_transaction()`
- Collect all signed tx hex strings

**Step 5 — submitSwapOrder:**
- Pass signed txs as comma-separated hex strings
- API broadcasts them to the respective chains

**Step 6 — Order tracking:**
- Poll `bridge-order` until status is `completed` or `failed`
- Use `bridge-history` to list all past orders

## Limitations

- **Rate limits**: Public API may have rate limits; space out rapid queries
- **Price volatility**: Quotes are indicative — actual prices may change between quote and execution
- **JWT expiry**: Access tokens expire after 24 hours; re-authenticate with `bridge-login`
- **Transaction signing**: Use `bridge-swap` for one-step execution. For advanced scenarios, `bridge-make-order` returns unsigned transactions that the agent must sign externally before submitting via `bridge-submit-order`.
