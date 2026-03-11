---
name: morph-dex
version: 1.0.0
description: DEX swap execution on Morph L2 — quote and send swaps via Bulbaswap aggregator
---

# Morph DEX — AI Agent Skill

> DEX swap operations via Bulbaswap aggregator on **Morph Mainnet** (Chain ID: 2818).
> All commands output JSON. All amounts use human-readable units.

## Activation Triggers

Use this skill when the user wants to: get a swap quote, check token prices, or execute a token swap **on Morph chain only**. For swaps on other chains or cross-chain transfers, use the morph-bridge skill instead.

## Quick Start

```bash
pip install requests eth_account

# Run from repository root
python3 scripts/morph_api.py <command> [options]
```

No API keys required. DEX API: `https://api.bulbaswap.io`

---

## Commands

### `dex-quote`
Get a swap quote. Returns estimated output amount and price impact. Pass `--recipient` to include `methodParameters` (calldata for on-chain execution).
```bash
# Preview quote only
python3 scripts/morph_api.py dex-quote --amount 1 --token-in ETH --token-out USDT0

# With recipient (returns methodParameters.calldata for dex-send)
python3 scripts/morph_api.py dex-quote --amount 1 --token-in ETH --token-out USDT0 --recipient 0xYourAddr
```

Optional: `--slippage 0.5` (default: 1%), `--deadline 300` (seconds, default: 300), `--protocols v2,v3`.

### `dex-send`
Sign and broadcast a swap transaction using calldata from `dex-quote --recipient`. Uses `methodParameters` fields (to, value, calldata) from the quote response.
```bash
python3 scripts/morph_api.py dex-send --to 0xRouterAddr --value 0.001 --data 0xCalldata... --private-key 0xKey
```

---

## Safety Rules

1. **Always confirm with the user before executing `dex-send`** — show the swap details (token pair, amount, slippage, router address) before signing.
2. Private keys are used locally for signing only — never sent to any API.
3. DEX quotes expire quickly — get a fresh quote and send immediately.

## Critical Notes

- **Morph chain only** — `dex-quote` and `dex-send` only work for tokens on Morph. For other chains, use bridge commands.
- DEX quotes expire quickly — get a fresh quote and send immediately.
- Always use `--slippage` to protect against price movement.
- `dex-quote` returns amounts in human-readable units.
- `dex-send` requires `methodParameters` from a quote with `--recipient`.

## Common Workflows

**Swap tokens:**
```
dex-quote --recipient 0xAddr (get calldata) → dex-send (sign & broadcast)
```

**Swap with alt-fee gas payment:**
```
dex-quote --recipient 0xAddr → altfee-send (morph-altfee skill, pay gas with alt token)
```

## Cross-Skill Integration

- Use `token-search` (morph-explorer) to find token contract addresses before quoting.
- Use `balance` / `token-balance` (morph-wallet) to verify funds before swapping.
- Use `altfee-send` (morph-altfee) instead of `dex-send` to pay gas with alternative tokens.
