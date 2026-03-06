# Morph Skill — AI Agent Reference

> CLI toolkit for AI agents to interact with the **Morph Mainnet** (Chain ID: 2818).
> All commands output JSON. All amounts use human-readable units (e.g. `0.1` ETH, not wei).

## Quick Start

```bash
# Install dependencies
pip install requests eth_account

# Run any command
python3 scripts/morph_api.py <command> [options]
```

No API keys required — all endpoints are public.

---

## Data Sources

| Source | Base URL | Auth |
|--------|----------|------|
| Morph RPC | `https://rpc.morph.network/` | None |
| Explorer API (Blockscout) | `https://explorer-api.morph.network/api/v2` | None |
| DEX Aggregator | `https://api.bulbaswap.io` | None |

---

## Commands

### Wallet (RPC)

#### `create-wallet`
Generate a new Ethereum key pair locally. No network call.
```bash
python3 scripts/morph_api.py create-wallet
```

#### `balance`
Query native ETH balance.
```bash
python3 scripts/morph_api.py balance --address 0xYourAddress
```

#### `token-balance`
Query ERC20 token balance. Pass the token contract address.
```bash
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

#### `token-list`
List top tracked tokens from the explorer (single page response).
```bash
python3 scripts/morph_api.py token-list
```

### DEX

#### `dex-quote`
Get a swap quote. Returns estimated output amount and price impact. Pass `--recipient` to include `methodParameters` (calldata for on-chain execution).
```bash
# Preview quote only
python3 scripts/morph_api.py dex-quote --amount 1 --token-in ETH --token-out 0xe7cd86e13AC4309349F30B3435a9d337750fC82D

# With recipient (returns methodParameters.calldata for dex-send)
python3 scripts/morph_api.py dex-quote --amount 1 --token-in ETH --token-out USDT --recipient 0xYourAddr
```

Optional: `--slippage 0.5` (default: 1%), `--deadline 60`, `--protocols v2,v3`.

#### `dex-send`
Sign and broadcast a swap transaction using calldata from `dex-quote --recipient`. Uses `methodParameters` fields (to, value, calldata) from the quote response.
```bash
python3 scripts/morph_api.py dex-send --to 0xRouterAddr --value 1 --data 0xCalldata... --private-key 0xKey
```

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

| Token | Contract Address |
|-------|-----------------|
| USDT | `0xe7cd86e13AC4309349F30B3435a9d337750fC82D` |

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

### Safety Rules
1. **Always confirm with the user before executing `transfer` or `transfer-token`** — show them the recipient, amount, and token before signing.
2. All amounts are in human-readable units — `0.1` means 0.1 ETH, not 0.1 wei.
3. Private keys are only used locally for signing. They are never sent to any API.
4. `create-wallet` is purely local — it generates a key pair without any network call.
5. For large amounts, suggest the user verify the recipient address character by character.
6. DEX quotes may change between quote and execution — always use the `--slippage` parameter.

### Alt-Fee (Alternative Gas Payment)
- Morph supports paying gas with alternative tokens via transaction type `0x7f`
- Use `altfee-tokens` to list available fee tokens (IDs 1-5)
- Use `altfee-estimate` to calculate how much fee token is needed for a given gas limit
- Formula: `feeLimit >= (gasFeeCap × gasLimit + L1DataFee) × tokenScale / feeRate`
- Fee token 5 = USDT (`0xe7cd86e13AC4309349F30B3435a9d337750fC82D`)
- Alt-fee and EIP-7702 are mutually exclusive — cannot use both in one transaction

### Common Workflows

**Check a wallet's portfolio:**
```
balance → token-balance (for each token) → address-tokens (for full list)
```

**Send tokens safely:**
```
balance (verify funds) → transfer/transfer-token → tx-receipt (confirm)
```

**Swap tokens:**
```
dex-quote --recipient (get calldata in methodParameters) → dex-send (sign & broadcast)
```

**Investigate a transaction:**
```
tx-detail (explorer view) → tx-receipt (RPC receipt with logs)
```

**Pay gas with alternative token:**
```
altfee-tokens (list available) → altfee-estimate (calculate feeLimit) → altfee-send (sign & broadcast with 0x7f)
```
