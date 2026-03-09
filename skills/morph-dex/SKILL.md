# Morph DEX — AI Agent Skill

> DEX swap operations via Bulbaswap aggregator on **Morph Mainnet** (Chain ID: 2818).
> All commands output JSON. All amounts use human-readable units.

## Activation Triggers

Use this skill when the user wants to: get a swap quote, check token prices, or execute a token swap on Morph.

## Quick Start

```bash
pip install requests eth_account
python3 scripts/morph_api.py <command> [options]
```

No API keys required. DEX API: `https://api.bulbaswap.io`

---

## Commands

### `dex-quote`
Get a swap quote. Returns estimated output amount and price impact. Pass `--recipient` to include `methodParameters` (calldata for on-chain execution).
```bash
# Preview quote only
python3 scripts/morph_api.py dex-quote --amount 1 --token-in ETH --token-out USDT

# With recipient (returns methodParameters.calldata for dex-send)
python3 scripts/morph_api.py dex-quote --amount 1 --token-in ETH --token-out USDT --recipient 0xYourAddr
```

Optional: `--slippage 0.5` (default: 1%), `--deadline 60`, `--protocols v2,v3`.

### `dex-send`
Sign and broadcast a swap transaction using calldata from `dex-quote --recipient`. Uses `methodParameters` fields (to, value, calldata) from the quote response.
```bash
python3 scripts/morph_api.py dex-send --to 0xRouterAddr --value 1 --data 0xCalldata... --private-key 0xKey
```

---

## Critical Notes

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
