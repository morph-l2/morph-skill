# On-Chain Research Guide

> Deep-dive guide for AI agents performing on-chain data analysis on Morph.
> Load this document when the user wants to investigate addresses, transactions, tokens, or contracts.

## Overview

The Explorer skill wraps the [Blockscout](https://explorer.morphl2.io) API, providing 9 commands for querying on-chain data. All data is public and requires no authentication.

## Research Workflows

### Investigate an Address

```
address-info   → basic profile (balance, tx count, type: EOA or contract)
address-txs    → transaction history (most recent first)
address-tokens → all ERC20 token holdings with balances
```

**What to look for:**
- High tx count + low balance → active trader or bot
- Contract type + verified → check `contract-info` for source code
- Large token diversity → possible DeFi power user

### Investigate a Transaction

```
tx-detail      → explorer view (decoded input, token transfers, internal txs)
tx-receipt     → RPC receipt (status, gas used, logs)
```

**When to use which:**
- `tx-detail` for human-readable info (what tokens moved, what function was called)
- `tx-receipt` for technical info (exact gas used, raw logs, revert reason)

### Token Research

```
token-search   → find a token by name or symbol
token-info     → dashboard data (supply, holders, transfers, market cap)
token-transfers→ recent transfer activity
token-list     → browse top tokens on Morph
```

**Token health signals:**
- Holder count trend (growing = adoption)
- Transfer count (high = active usage)
- Market cap vs total supply (circulating ratio)

### Contract Analysis

```
contract-info  → source code, ABI, verification status, proxy info
address-txs    → recent interactions with the contract
```

**What `contract-info` reveals:**
- `is_verified`: whether the source code is published and matches bytecode
- `is_proxy`: whether this is a proxy contract (upgradeable)
- `proxy_type`: EIP-1967, EIP-1822, etc.
- `implementations`: the actual logic contract addresses (for proxies)
- `abi`: full contract ABI for understanding callable functions
- `source_code`: Solidity source for manual review

## Blockscout API Details

### Base URL
```
https://explorer-api.morph.network/api/v2
```

### Pagination

Some endpoints return paginated data:
- `address-txs`: returns up to 50 most recent transactions per page; `--limit` truncates the result locally
- `token-transfers`: returns most recent transfers (default page)
- `token-list`: returns a single page of top tokens

The skill does not currently support cursor-based pagination beyond the first page.

### Rate Limits

The Blockscout API is public with no authentication. There are no documented rate limits, but agents should:
- Avoid rapid-fire sequential calls (add natural pauses between bulk queries)
- Cache results within a session when re-querying the same data
- Use `--limit` on `address-txs` to reduce output size (note: the API always returns a full page; truncation is local)

## Data Interpretation Tips

### Balance Formats
- `address-info` returns balance in wei (raw from Blockscout)
- `balance` command (morph-wallet skill) returns balance in ETH (human-readable)
- `address-tokens` returns token balances with decimal-adjusted values

### Transaction Status
- `tx-detail` status: `"success"` or `"error"`
- `tx-receipt` status: `1` (success) or `0` (reverted)
- Reverted transactions still consume gas

### Token Types
- `token-info` only works for ERC20 tokens — use `address-info` for native ETH data
- Some tokens may not have market data (price, market cap) if not tracked by the explorer

## Common Pitfalls

1. **Using `token-info` for ETH**: ETH is not an ERC20 token; use `balance` or `address-info` instead
2. **Confusing `tx-detail` and `tx-receipt`**: `tx-detail` is from the explorer (decoded, enriched); `tx-receipt` is from the RPC (raw, technical)
3. **Assuming all contracts are verified**: `contract-info` only returns source/ABI for verified contracts; unverified contracts return an error
4. **Large address-txs queries**: `--limit` only truncates locally; the API always returns a full page (50 items), so it does not speed up the request
