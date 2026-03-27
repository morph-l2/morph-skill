---
name: morph-explorer
version: 1.0.0
description: On-chain data queries on Morph L2 — address info, transactions, tokens, contracts via Blockscout API
---

# Morph Explorer — AI Agent Skill

> On-chain data queries via Blockscout Explorer API on **Morph Mainnet** (Chain ID: 2818).
> All commands output JSON.

## Activation Triggers

Use this skill when the user wants to: look up an address, view transaction history, check token holdings, search tokens, get token details (holders, supply, transfers), or investigate a transaction on Morph.

## BGW Routing Note

Decide the mode once via the root [SKILL.md](../../SKILL.md) and [docs/social-wallet-integration.md](../../docs/social-wallet-integration.md).

- This skill is for Morph-side public reads and research. All commands are read-only.
- Works with any wallet type — if the address comes from a BGW Social Login Wallet, resolve the address via BGW first, then use these commands normally. See [social-wallet-integration.md](../../docs/social-wallet-integration.md).

## Quick Start

```bash
pip install requests

# Run from repository root
python3 scripts/morph_api.py <command> [options]
```

No API keys required. Explorer API: `https://explorer-api.morph.network/api/v2`

---

## Commands

### `address-info`
Address summary: balance, tx count, type.
```bash
python3 scripts/morph_api.py address-info --address 0xAddr
```

### `address-txs`
List transactions for an address. Optional `--limit`.
```bash
python3 scripts/morph_api.py address-txs --address 0xAddr --limit 5
```

### `address-tokens`
List all token holdings.
```bash
python3 scripts/morph_api.py address-tokens --address 0xAddr
```

### `tx-detail`
Full transaction details from explorer (decoded input, token transfers, etc.).
```bash
python3 scripts/morph_api.py tx-detail --hash 0xTxHash
```

### `token-search`
Search tokens by name or symbol.
```bash
python3 scripts/morph_api.py token-search --query "USDC"
```

### `contract-info`
Get smart contract info: source code, ABI, verification status, compiler version, proxy type. Only works for verified contracts.
```bash
python3 scripts/morph_api.py contract-info --address 0xe7cd86e13AC4309349F30B3435a9d337750fC82D
```

### `token-transfers`
Get recent token transfers. Query by token (all transfers of that token) or by address (all token transfers involving that address).
```bash
# Transfers of a specific token
python3 scripts/morph_api.py token-transfers --token USDT

# Token transfers involving a specific address
python3 scripts/morph_api.py token-transfers --address 0xYourAddress
```

### `token-info`
Get token details: name, symbol, total supply, holders count, transfer count, market data. ERC20 tokens only (not ETH — use `address-info` for ETH).
```bash
python3 scripts/morph_api.py token-info --token USDT
python3 scripts/morph_api.py token-info --token 0xe7cd86e13AC4309349F30B3435a9d337750fC82D
```

### `token-list`
List top tracked tokens from the explorer (single page response).
```bash
python3 scripts/morph_api.py token-list
```

---

## Common Workflows

**Investigate a transaction:**
```
tx-detail (explorer view) → tx-receipt (morph-wallet skill, RPC receipt with logs)
```

**Research an address:**
```
address-info → address-txs → address-tokens
```

If the address belongs to a BGW Social Login Wallet, obtain the address in BGW first and then run the same workflow here.

**Token dashboard:**
```
token-search (find token) → token-info (holders, supply) → token-transfers (recent activity)
```

**Analyze a contract:**
```
contract-info (source, ABI, proxy type) → address-txs (recent interactions)
```
