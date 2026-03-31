---
name: morph-skill
version: 1.6.0
description: AI Agent skill for Morph L2 — wallet, explorer, DEX swap, cross-chain bridge with order management, EIP-8004 agent identity & reputation, alt-fee gas payment, EIP-7702 delegation, and x402 payment protocol
---

# Morph Skill — AI Agent Reference

> CLI toolkit for AI agents to interact with the **Morph Mainnet** (Chain ID: 2818).
> All commands output JSON. All amounts use human-readable units (e.g. `0.1` ETH, not wei).

## Quick Start

```bash
# Install dependencies
pip install requests eth_account eth_abi eth_utils

# Run any command
python3 scripts/morph_api.py <command> [options]
```

No API keys required for queries. Bridge order management requires JWT authentication via `bridge-login`.

---

## Must Read First

Before executing any Morph workflow, decide whether the user is asking for:

- a **Morph protocol/business** task
- a **wallet/Social Login Wallet** task
- or a combined flow that needs both Morph and BGW skills

This repo is the **Morph protocol and business layer**. BGW should be treated as the **wallet product and signing layer**.

- Morph owns wallet RPC operations, explorer queries, DEX quotes, bridge quotes/orders, altfee, and EIP-8004 identity/reputation logic.
- BGW owns Social Login Wallet (TEE signing), swap execution across chains, token discovery, market data, and security audits.
- This repo does **not** call BGW scripts, embed BGW tooling, or manage BGW sessions at runtime.

If the user may need Social Login Wallet behavior, load both the Morph skill pack and the BGW skill pack. BGW scripts live in a separate repo. To locate BGW: check `BGW_DIR` env var → look for `bitget-wallet-skill/` as a sibling directory → if not found, auto-clone from `https://github.com/bitget-wallet-ai-lab/bitget-wallet-skill.git` to the sibling directory. See [docs/social-wallet-integration.md](docs/social-wallet-integration.md) for the full setup flow.

See [docs/social-wallet-integration.md](docs/social-wallet-integration.md) before handling combined Morph + BGW workflows.

### Routing Table

| User Need | Use |
|-----------|-----|
| Local private-key wallet on Morph | Morph skills |
| Explorer, swap, bridge, altfee, identity, reputation on Morph (with local key) | Morph skills |
| EIP-7702 delegation, batch calls (with local key) | Morph skills |
| x402 payment (pay or receive USDC, with local key) | Morph skills |
| x402 discover / verify / settle / server (no signing needed) | Morph skills |
| Social Login Wallet, TEE signing, market data, token discovery | BGW skills |
| Swap/bridge execution with Social Login Wallet (including on Morph) | **BGW skills** — BGW supports Morph chain natively with TEE signing |
| Social Login Wallet + Morph protocol reads | BGW for address, then Morph for reads |
| x402 pay with Social Login Wallet | Agent orchestration: Morph `x402-discover` → BGW signs EIP-3009 → Agent replays with `PAYMENT-SIGNATURE` header |
| EIP-7702 batch with Social Login Wallet | Agent orchestration: Morph computes hashes → BGW signs via TEE → Agent assembles and broadcasts |

Current execution note:

- Morph write commands require `--private-key` for local signing.
- Social Login Wallet users do not have a local private key (keys live in Bitget's TEE). For writes on Morph with a Social Login Wallet, use BGW's swap flow — see [docs/social-wallet-integration.md](docs/social-wallet-integration.md).
- BGW routing in this phase is a documentation/orchestration model, not a new runtime execution path inside `morph_api.py`.

### Single-Pass Routing Model

Choose exactly one mode at the start of the task and stay in it unless the user changes intent:

1. `morph-local-execution`
   Use Morph directly. The user has provided a private key or explicitly wants local-key self-custody.
2. `bgw-wallet-mode`
   Use BGW directly. The user wants Social Login Wallet, TEE signing, swap execution via BGW, or market data queries.
3. `bgw-address-then-morph-read`
   Use BGW first only to resolve the wallet/address context, then use Morph read commands.
4. `bgw-plus-morph-planning`
   Use BGW for wallet context and Morph for protocol reasoning, but do not imply that Morph already has a BGW-native write execution path.

Do not bounce between BGW and Morph more than once for the same task. Route once, hand off the minimum required context, and continue in the selected mode.

### Fast Routing Rules

- If the user already supplied a private key and wants a Morph action executed now, stay in Morph.
- If the user asks for Social Login Wallet or TEE signing, route to BGW.
- If the user wants to swap/bridge with a Social Login Wallet (even on Morph chain), use BGW's swap flow — it supports Morph natively with TEE signing.
- If the user has a BGW wallet but only needs Morph reads, obtain the address from BGW first and then use Morph commands normally.
- If the user asks for BGW-backed execution inside this CLI, explain that Morph CLI requires `--private-key`; for Social Login Wallet execution, use BGW's swap/sign flows instead.

### Handoff Rule

When handing off from BGW to Morph, only carry forward the minimum context needed:

- wallet address
- network/chain intent
- whether the user wants reads, planning, or immediate execution

Do not restate the entire BGW workflow inside each Morph sub-skill.

---

## Data Sources

| Source | Base URL | Auth |
|--------|----------|------|
| Morph RPC | `https://rpc.morph.network/` | None |
| Explorer API (Blockscout) | `https://explorer-api.morph.network/api/v2` | None |
| DEX Aggregator | `https://api.bulbaswap.io` | None (queries) / JWT (orders) |
| Bundled ABIs | `contracts/IdentityRegistry.json`, `contracts/ReputationRegistry.json` | Local files |

Default EIP-8004 contracts on Morph mainnet:
- `IdentityRegistry`: `0x8004A169FB4a3325136EB29fA0ceB6D2e539a432`
- `ReputationRegistry`: `0x8004BAa17C55a88189AE136b182e5fdA19dE9b63`

---

## Commands

### Wallet (RPC)

Use these commands for Morph-local wallet generation, direct address reads, and local private-key signing. For BGW routing, decide the mode once using the rules above, then return here only if the selected mode still requires Morph wallet reads or local-key execution.

#### `create-wallet`
Generate a new Ethereum key pair locally (local private-key wallet). No network call. **Not** for Social Login Wallet — if the user asks for a "social wallet", route to BGW instead.
```bash
python3 scripts/morph_api.py create-wallet
```

#### `balance`
Query native ETH balance.
```bash
python3 scripts/morph_api.py balance --address 0xYourAddress
```

#### `token-balance`
Query ERC20 token balance. Pass the token contract address or known symbol.
```bash
python3 scripts/morph_api.py token-balance --address 0xAddr --token USDT
python3 scripts/morph_api.py token-balance --address 0xAddr --token 0xe7cd86e13AC4309349F30B3435a9d337750fC82D
```

#### `transfer`
Send ETH. Amount is in ETH (e.g. `0.01`).
```bash
python3 scripts/morph_api.py transfer --to 0xRecipient --amount 0.01 --private-key 0xYourKey
```

#### `transfer-token`
Send ERC20 tokens. Amount is in token units (e.g. `10.5` USDC).
```bash
python3 scripts/morph_api.py transfer-token --token USDT --to 0xRecipient --amount 10 --private-key 0xKey
python3 scripts/morph_api.py transfer-token --token 0xe7cd86e13AC4309349F30B3435a9d337750fC82D --to 0xRecipient --amount 10 --private-key 0xKey
```

#### `tx-receipt`
Get transaction receipt (status, gas used, logs).
```bash
python3 scripts/morph_api.py tx-receipt --hash 0xTxHash
```

### Explorer (Blockscout)

#### `address-info`
Address summary: balance, tx count, type.
```bash
python3 scripts/morph_api.py address-info --address 0xAddr
```

#### `address-txs`
List transactions for an address. Optional `--limit`.
```bash
python3 scripts/morph_api.py address-txs --address 0xAddr --limit 5
```

#### `address-tokens`
List all token holdings.
```bash
python3 scripts/morph_api.py address-tokens --address 0xAddr
```

#### `tx-detail`
Full transaction details from explorer (decoded input, token transfers, etc.).
```bash
python3 scripts/morph_api.py tx-detail --hash 0xTxHash
```

#### `token-search`
Search tokens by name or symbol.
```bash
python3 scripts/morph_api.py token-search --query "USDC"
```

#### `contract-info`
Get smart contract info: source code, ABI, verification status, compiler, proxy type.
```bash
python3 scripts/morph_api.py contract-info --address 0xe7cd86e13AC4309349F30B3435a9d337750fC82D
```

#### `token-transfers`
Get recent token transfers by token or by address.
```bash
# All transfers of a specific token
python3 scripts/morph_api.py token-transfers --token USDT

# Token transfers involving a specific address
python3 scripts/morph_api.py token-transfers --address 0xYourAddress
```

#### `token-info`
Get token details: name, symbol, total supply, holders count, transfer count, market data.
```bash
python3 scripts/morph_api.py token-info --token USDT
python3 scripts/morph_api.py token-info --token 0xe7cd86e13AC4309349F30B3435a9d337750fC82D
```

#### `token-list`
List top tracked tokens from the explorer (single page response).
```bash
python3 scripts/morph_api.py token-list
```

### Agent (EIP-8004)

These commands use the ABI files bundled under `contracts/` and talk directly to Morph RPC.
They own the Morph-side identity and reputation logic. If the selected mode is BGW-based, BGW supplies wallet context while Morph still owns the protocol logic here.

`agent_id` is a **numeric ERC-721 token ID** (e.g. `1`, `42`) returned by `agent-register`.

#### `agent-register`
Register an agent identity with optional URI and metadata. Optionally pass `--fee-token-id` to pay gas via altfee.
```bash
python3 scripts/morph_api.py agent-register --name "MorphBot" --agent-uri "https://example.com/agent.json" --metadata role=assistant,team=research --private-key 0xYourKey

# With altfee gas payment
python3 scripts/morph_api.py agent-register --name "MorphBot" --fee-token-id 5 --private-key 0xYourKey
```

#### `agent-wallet`
Get the payment wallet for an agent.
```bash
python3 scripts/morph_api.py agent-wallet --agent-id <agent_id>
```

#### `agent-metadata`
Read one metadata value by key.
```bash
python3 scripts/morph_api.py agent-metadata --agent-id <agent_id> --key name
```

#### `agent-reputation`
Get aggregated reputation score and feedback count, optionally filtered by tags.
```bash
python3 scripts/morph_api.py agent-reputation --agent-id <agent_id> --tag1 quality
```

#### `agent-feedback`
Submit feedback for an agent. Scores are encoded with 2 decimals, matching the Polygon reference implementation. Optionally pass `--fee-token-id` to pay gas via altfee.
```bash
python3 scripts/morph_api.py agent-feedback --agent-id <agent_id> --value 4.5 --tag1 quality --feedback-uri "https://example.com/review/1" --private-key 0xYourKey

# With altfee gas payment
python3 scripts/morph_api.py agent-feedback --agent-id <agent_id> --value 4.5 --fee-token-id 5 --private-key 0xYourKey
```

#### `agent-reviews`
Read all feedback entries for an agent.
```bash
python3 scripts/morph_api.py agent-reviews --agent-id <agent_id> --include-revoked
```

### DEX (Morph only)

Use Morph for quote generation and swap workflow reasoning. If the selected mode is BGW-based, treat BGW as the wallet layer and avoid implying a BGW-native `dex-send` path inside this repo.

#### `dex-quote`
Get a swap quote on **Morph chain only**. Returns estimated output amount and price impact. Pass `--recipient` to include `methodParameters` (calldata for on-chain execution).
```bash
# Preview quote only
python3 scripts/morph_api.py dex-quote --amount 1 --token-in ETH --token-out 0xe7cd86e13AC4309349F30B3435a9d337750fC82D

# With recipient (returns methodParameters.calldata for dex-send)
python3 scripts/morph_api.py dex-quote --amount 1 --token-in ETH --token-out USDT --recipient 0xYourAddr
```

Optional: `--slippage 0.5` (default: 1%), `--deadline 300` (seconds, default: 300), `--protocols v2,v3`.

#### `dex-send`
Sign and broadcast a swap transaction using calldata from `dex-quote --recipient`. Uses `methodParameters` fields (to, value, calldata) from the quote response.
```bash
python3 scripts/morph_api.py dex-send --to 0xRouterAddr --value 0.001 --data 0xCalldata... --private-key 0xKey
```

### Bridge (Cross-Chain & Multi-Chain Swap)

Use Morph for bridge quotes, JWT auth flow, order reasoning, and order tracking. If the selected mode is BGW-based, BGW still owns the wallet/session side and Morph only owns the protocol side documented here.

#### `bridge-chains`
List all supported chains for cross-chain swap.
```bash
python3 scripts/morph_api.py bridge-chains
```

#### `bridge-tokens`
List available tokens for cross-chain swap. Optionally filter by chain.
```bash
python3 scripts/morph_api.py bridge-tokens --chain morph
```

#### `bridge-token-search`
Search tokens by symbol or contract address across chains.
```bash
python3 scripts/morph_api.py bridge-token-search --keyword USDT --chain base
```

#### `bridge-quote`
Get a cross-chain or same-chain swap quote with price, fees, and route info.
```bash
python3 scripts/morph_api.py bridge-quote \
  --from-chain base --from-token 0x833589fcd6edb6e08f4c7c32d4f71b54bda02913 \
  --amount 2 --to-chain bnb \
  --to-token 0x55d398326f99059ff775485246999027b3197955 \
  --from-address 0xYourAddress
```

#### `bridge-balance`
Query token balance and USD price for an address on any supported chain.
```bash
python3 scripts/morph_api.py bridge-balance --chain morph --token USDT --address 0xYourAddress
```

#### `bridge-login`
Sign in with EIP-191 wallet signature to get a JWT access token (valid 24h).
```bash
python3 scripts/morph_api.py bridge-login --private-key 0xYourKey
```

#### `bridge-make-order`
Create a cross-chain swap order. Returns `orderId` and unsigned transactions to sign.
```bash
python3 scripts/morph_api.py bridge-make-order --jwt <JWT> \
  --from-chain morph --from-contract 0xe7cd86e13AC4309349F30B3435a9d337750fC82D \
  --from-amount 10 --to-chain base \
  --to-contract 0x833589fcd6edb6e08f4c7c32d4f71b54bda02913 \
  --to-address 0xRecipient --market stargate
```

#### `bridge-submit-order`
Submit signed transactions for a swap order.
```bash
python3 scripts/morph_api.py bridge-submit-order --jwt <JWT> --order-id abc123 --signed-txs 0xSignedTx1,0xSignedTx2
```

#### `bridge-swap`
One-step cross-chain swap: create order, sign transactions, and submit — all in one command. This is the recommended way for agents to execute bridge swaps.
```bash
python3 scripts/morph_api.py bridge-swap --jwt <JWT> \
  --from-chain morph --from-contract USDT.e --from-amount 5 \
  --to-chain base --to-contract USDC \
  --market stargate --private-key 0xYourKey
```
Optional: `--to-address` (default: sender), `--slippage 0.5`, `--feature no_gas`.

#### `bridge-order`
Query the status of a swap order.
```bash
python3 scripts/morph_api.py bridge-order --jwt <JWT> --order-id abc123
```

#### `bridge-history`
Query historical swap orders with optional pagination and status filter.
```bash
python3 scripts/morph_api.py bridge-history --jwt <JWT> --page 1 --page-size 10
```

### EIP-7702 (EOA delegation, tx type `0x04`)

Morph supports EIP-7702 EOA delegation via tx type `0x04`. Delegate an EOA to a smart contract (e.g. SimpleDelegation at `0xBD7093Ded667289F9808Fa0C678F81dbB4d2eEb7`) for atomic batch calls.

#### `7702-delegate`
Check whether an EOA has been delegated via EIP-7702.
```bash
python3 scripts/morph_api.py 7702-delegate --address 0xEOA
```

#### `7702-authorize`
Sign a 7702 authorization offline (no transaction sent).
```bash
python3 scripts/morph_api.py 7702-authorize --private-key 0xKey
```

#### `7702-send`
Send a single call via EIP-7702 delegation.
```bash
python3 scripts/morph_api.py 7702-send --to 0xContract --value 0.01 --data 0xCalldata --private-key 0xKey
```

#### `7702-batch`
Atomically execute multiple calls via SimpleDelegation.
```bash
python3 scripts/morph_api.py 7702-batch --calls '[{"to":"0x...","value":"0","data":"0x..."}]' --private-key 0xKey
```

#### `7702-revoke`
Revoke the EIP-7702 delegation.
```bash
python3 scripts/morph_api.py 7702-revoke --private-key 0xKey
```

### x402 (HTTP payment protocol)

Morph supports the x402 v2 HTTP payment protocol for Agent-to-Agent USDC payments. Client commands let agents pay for protected resources; merchant commands let agents receive payments.

#### `x402-supported`
Query the Facilitator for supported payment schemes.
```bash
python3 scripts/morph_api.py x402-supported
```

#### `x402-discover`
Probe a URL for x402 payment requirements (does not pay).
```bash
python3 scripts/morph_api.py x402-discover --url https://api.example.com/resource
```

#### `x402-pay`
Pay for an x402-protected resource with USDC.
```bash
python3 scripts/morph_api.py x402-pay --url https://api.example.com/resource --private-key 0xKey
```

#### `x402-register`
Register with Facilitator to get merchant HMAC credentials.
```bash
python3 scripts/morph_api.py x402-register --private-key 0xKey --save --name myagent
```

#### `x402-verify`
Verify a received x402 payment signature (merchant).
```bash
python3 scripts/morph_api.py x402-verify --payload '...' --requirements '...' --name myagent
```

#### `x402-settle`
Settle a payment on-chain (USDC transfer, merchant).
```bash
python3 scripts/morph_api.py x402-settle --payload '...' --requirements '...' --name myagent
```

#### `x402-server`
Start a local x402 merchant test server.
```bash
python3 scripts/morph_api.py x402-server --pay-to 0xWalletAddr --price 0.001 --dev
```

---

### Alt-Fee (pay gas with alternative tokens)

Morph supports paying gas fees with alternative tokens (tx type `0x7f`) instead of ETH. Use these commands to query fee token info, estimate costs, and send alt-fee transactions.

#### `altfee-tokens`
List all supported fee tokens from the on-chain TokenRegistry.
```bash
python3 scripts/morph_api.py altfee-tokens
```

#### `altfee-token-info`
Get details for a specific fee token: contract address, scale, feeRate, decimals, active status.
```bash
python3 scripts/morph_api.py altfee-token-info --id 5
```

#### `altfee-estimate`
Estimate the minimum feeLimit needed to pay gas with a fee token. Includes a 10% safety margin.
```bash
# Estimate for a simple ETH transfer (21000 gas)
python3 scripts/morph_api.py altfee-estimate --id 5

# Estimate for an ERC20 transfer (200000 gas)
python3 scripts/morph_api.py altfee-estimate --id 5 --gas-limit 200000
```

#### `altfee-send`
Sign and broadcast a transaction paying gas with an alternative fee token (tx type `0x7f`). `--fee-limit` defaults to 0 (no limit — uses available balance, unused portion is refunded).
```bash
# Simple ETH transfer, pay gas with USDT (token ID 5)
python3 scripts/morph_api.py altfee-send --to 0xRecipient --value 0.01 --fee-token-id 5 --private-key 0xKey

# Contract call with explicit fee limit and gas limit
python3 scripts/morph_api.py altfee-send --to 0xContract --data 0xCalldata... --fee-token-id 5 --fee-limit 500000 --gas-limit 200000 --private-key 0xKey
```

---

## Well-Known Token Addresses (Morph Mainnet)

For native ETH, use empty string `""` or `ETH` as the contract address.

| Symbol | Name | Contract Address |
|--------|------|-----------------|
| USDT | USDT | `0xe7cd86e13AC4309349F30B3435a9d337750fC82D` |
| USDT.e | Tether Morph Bridged | `0xc7D67A9cBB121b3b0b9c053DD9f469523243379A` |
| USDC | USD Coin | `0xCfb1186F4e93D60E60a8bDd997427D1F33bc372B` |
| USDC.e | USD Coin Morph Bridged | `0xe34c91815d7fc18A9e2148bcD4241d0a5848b693` |
| WETH | Wrapped Ether | `0x5300000000000000000000000000000000000011` |
| BGB | BitgetToken | `0x389C08Bc23A7317000a1FD76c7c5B0cb0b4640b5` |
| BGB (old) | BitgetToken (old) | `0x55d1f1879969bdbB9960d269974564C58DBc3238` |

> **Note:** Morph has two USDT variants and two USDC variants. When the user says "USDT" or "USDC" without specifying, **ask the user to choose** (USDT vs USDT.e, or USDC vs USDC.e) before proceeding.

For other tokens, use `token-search` to look up the contract address:
```bash
python3 scripts/morph_api.py token-search --query "USDC"
```

---

## Domain Knowledge

### Morph Chain
- **Network**: Morph Mainnet
- **Chain ID**: 2818
- **Layer**: L2 (optimistic rollup on Ethereum)
- **Gas token**: ETH
- **Block time**: ~2 seconds
- **Explorer API**: https://explorer-api.morph.network/api/v2
- **Bundled ERC-8004 ABIs**: `contracts/IdentityRegistry.json`, `contracts/ReputationRegistry.json`
- **Runtime overrides**: `MORPH_RPC_URL`, `MORPH_EXPLORER_API`, `MORPH_DEX_API`, `MORPH_CHAIN_ID`
- **Registry address overrides**: `MORPH_IDENTITY_REGISTRY`, `MORPH_REPUTATION_REGISTRY`
- **Default mainnet registries**:
  `IdentityRegistry=0x8004A169FB4a3325136EB29fA0ceB6D2e539a432`,
  `ReputationRegistry=0x8004BAa17C55a88189AE136b182e5fdA19dE9b63`

### Hoodi Testnet Example

To test the bundled EIP-8004 commands against Morph Hoodi, override the runtime network and registry addresses:

```bash
export MORPH_RPC_URL="https://rpc-hoodi.morph.network"
export MORPH_CHAIN_ID=2910
export MORPH_IDENTITY_REGISTRY="0x8004A818BFB912233c491871b3d84c89A494BD9e"
export MORPH_REPUTATION_REGISTRY="0x8004B663056A597Dffe9eCcC1965A193B7388713"
```

### Safety Rules
1. **Always confirm with the user before executing send commands** (`transfer`, `transfer-token`, `agent-register`, `agent-feedback`, `dex-send`, `altfee-send`, `bridge-make-order`, `bridge-submit-order`, `bridge-swap`, `7702-send`, `7702-batch`, `7702-revoke`, `x402-pay`, `x402-settle`) — show the recipient, amount, token, or agent fields before signing. For `bridge-submit-order`, confirm the orderId and number of transactions before broadcasting. For `bridge-swap`, confirm the swap details (chains, tokens, amounts) before executing.
2. All amounts are in human-readable units — `0.1` means 0.1 ETH, not 0.1 wei.
3. Private keys are only used locally for signing. They are never sent to any API.
4. `create-wallet` is purely local — it generates a key pair without any network call.
5. For large amounts, suggest the user verify the recipient address character by character.
6. DEX quotes may change between quote and execution — always use the `--slippage` parameter.
7. **JWT tokens** from `bridge-login` expire after 24h. Re-authenticate if order commands return auth errors.

### Alt-Fee (Alternative Gas Payment)
- Morph supports paying gas with alternative tokens via transaction type `0x7f`
- Use `altfee-tokens` to list available fee tokens (IDs 1-6)
- Current fee tokens: `1=USDT.e`, `2=USDC.e`, `3=BGB (old)`, `4=BGB`, `5=USDT`, `6=USDC`
- Use `altfee-estimate` to calculate how much fee token is needed for a given gas limit
- Formula: `feeLimit >= (gasFeeCap × gasLimit + L1DataFee) × tokenScale / feeRate`
- Fee token 5 = USDT (`0xe7cd86e13AC4309349F30B3435a9d337750fC82D`)
- Alt-fee and EIP-7702 are mutually exclusive — cannot use both in one transaction
- `transfer`, `transfer-token`, and `dex-send` do **not** support `--fee-token-id` — use `altfee-send` instead for alt-fee gas payment with those operations

### EIP-7702 (EOA Delegation)
- Morph supports EIP-7702 via transaction type `0x04`
- SimpleDelegation contract: `0xBD7093Ded667289F9808Fa0C678F81dbB4d2eEb7`
- Delegated EOAs have on-chain code starting with `0xef0100`
- Use `7702-batch` for atomic multi-call (approve + swap in one tx)
- EIP-7702 and alt-fee (`0x7f`) are mutually exclusive in a single transaction
- `7702-send`, `7702-batch`, `7702-revoke` require `--private-key` — Social Login Wallet users should use BGW

### x402 (HTTP Payment Protocol)
- Morph supports x402 v2 (Coinbase open standard) for Agent-to-Agent USDC payments
- Payment token: USDC (`0xCfb1186F4e93D60E60a8bDd997427D1F33bc372B`, 6 decimals)
- Facilitator: `https://morph-rails.morph.network/x402`
- EIP-3009 gasless authorization — payer signs, Facilitator settles on-chain
- `x402-pay` enforces `--max-payment` (default 1.0 USDC) safety limit
- Merchant HMAC credentials stored encrypted at `~/.morph-agent/x402-credentials/`

### Common Workflows

**Agent routing — swap/bridge decision:**
```
User wants to swap tokens?
  ├── Same chain, on Morph? → dex-quote → dex-send (faster, lower fees)
  ├── Same chain, on other chain (Base/BNB/etc.)? → bridge-quote (same fromChain/toChain) → bridge-swap
  └── Cross-chain? → bridge-quote → bridge-swap
```

> **Important**: `dex-quote` / `dex-send` only work on Morph. For swaps on other chains or cross-chain transfers, always use bridge commands.

**Check a wallet's portfolio:**
```
balance → token-balance (for each token) → address-tokens (for full list)
```

**Inspect an agent's identity and reputation:**
```
agent-wallet → agent-metadata --key name → agent-reputation → agent-reviews
```

**Register or review an agent:**
```
agent-register → agent-wallet / agent-metadata → agent-feedback → agent-reputation
```

**Send tokens safely:**
```
balance (verify funds) → transfer/transfer-token → tx-receipt (confirm)
```

**Swap tokens on Morph:**
```
dex-quote --recipient (get calldata in methodParameters) → dex-send (sign & broadcast)
```

**Swap or bridge on any chain:**
```
bridge-login (get JWT) → bridge-quote (get price + market) → bridge-swap (create, sign, submit in one step) → bridge-order (track status)
```

> **Advanced**: `bridge-make-order` → sign txs → `bridge-submit-order` is still available for scenarios requiring manual transaction inspection or custom signing.

**Investigate a transaction:**
```
tx-detail (explorer view) → tx-receipt (RPC receipt with logs)
```

**Pay gas with alternative token:**
```
altfee-tokens (list available) → altfee-estimate (calculate feeLimit) → altfee-send (sign & broadcast with 0x7f)
```

**Atomic batch call (EIP-7702):**
```
7702-delegate (check status) → 7702-batch --calls '[...]' (atomic execute) → tx-receipt (confirm)
```

**Pay for x402-protected API:**
```
x402-discover --url <url> (check price) → x402-pay --url <url> (sign EIP-3009 and access)
```

**Agent monetization (EIP-8004 + x402):**
```
agent-register (get agent NFT) → x402-register --save (get HMAC creds) → x402-verify / x402-settle (process payments)
```

---

## Extended Documentation

For complex workflows, load these guides on demand:

| Document | When to Load |
|----------|-------------|
| [docs/altfee.md](docs/altfee.md) | User asks about paying gas with non-ETH tokens, 0x7f transactions, or feeLimit calculation |
| [docs/dex-swap.md](docs/dex-swap.md) | User wants to swap tokens, needs slippage guidance, or wants to combine swap with alt-fee |
| [docs/bridge.md](docs/bridge.md) | User asks about cross-chain swaps, bridge quotes, or multi-chain token operations |
| [docs/explorer.md](docs/explorer.md) | User wants to investigate addresses, transactions, tokens, or analyze contracts |

---

## Version Check Protocol

On each session start, before executing any command:

1. Read the `version` from this file's YAML frontmatter (current: `1.6.0`)
2. Fetch the latest CHANGELOG.md from the remote:
   ```bash
   git -C <skill_path> fetch origin && git -C <skill_path> diff HEAD..origin/main -- CHANGELOG.md
   ```
   Or if git is unavailable, fetch via HTTP:
   ```
   https://raw.githubusercontent.com/morph-l2/morph-skill/main/CHANGELOG.md
   ```
3. Compare the local version against the first `## [x.y.z]` entry in the remote CHANGELOG
4. If a newer version exists:
   - Show the user: "Morph Skill update available: vX.Y.Z → vA.B.C"
   - Summarize what changed (from CHANGELOG entries between versions)
   - If the update includes a **Security Audit** section mentioning credential, endpoint, or dependency changes, flag it explicitly
   - Prompt the user to update: `cd <skill_path> && git pull`
5. If versions match, proceed silently
