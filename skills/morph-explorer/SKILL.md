# Morph Explorer — AI Agent Skill

> On-chain data queries via Blockscout Explorer API on **Morph Mainnet** (Chain ID: 2818).
> All commands output JSON.

## Activation Triggers

Use this skill when the user wants to: look up an address, view transaction history, check token holdings, search tokens, get token details (holders, supply, transfers), or investigate a transaction on Morph.

## Quick Start

```bash
pip install requests
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

**Token dashboard:**
```
token-search (find token) → token-info (holders, supply, transfers)
```
