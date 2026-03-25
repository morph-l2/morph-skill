# DEX Swap Guide

> Deep-dive guide for AI agents executing token swaps on Morph via the Bulbaswap aggregator.
> Load this document when the user wants to swap tokens and needs detailed guidance.

## Overview

Morph's DEX infrastructure is powered by [Bulbaswap](https://bulbaswap.io), a swap aggregator that routes across multiple liquidity sources (Uniswap V2/V3 style pools) to find the best price.

The skill provides a two-step swap flow: **quote → send**.

## Swap Flow

### Step 1: Get a Quote

```bash
python3 scripts/morph_api.py dex-quote \
  --amount 1 \
  --token-in ETH \
  --token-out USDT \
  --recipient 0xYourAddress
```

The `--recipient` flag is critical. Without it, the quote returns price info only. With it, the response includes `methodParameters` containing the calldata needed to execute the swap on-chain.

**Quote response includes:**
- `quoteAmount`: estimated output amount (human-readable)
- `priceImpact`: percentage price impact
- `route`: path through liquidity pools
- `methodParameters.to`: router contract address
- `methodParameters.value`: ETH value to send (human-readable, e.g. `"0.001"`)
- `methodParameters.calldata`: encoded swap function call

### Step 2: Execute the Swap

```bash
python3 scripts/morph_api.py dex-send \
  --to <methodParameters.to> \
  --value <ETH amount or 0> \
  --data <methodParameters.calldata> \
  --private-key 0xKey
```

**Important**: always use the `to`, `value`, and `calldata` from the quote response — do not construct these manually.

## Token Resolution

The DEX commands accept both symbols and contract addresses:

| Input | Resolved To |
|-------|------------|
| `ETH` | Native ETH (wrapped as WETH internally by the router) |
| `USDT` | `0xe7cd86e13AC4309349F30B3435a9d337750fC82D` |
| `0x...` (40 hex chars) | Used as-is |

For tokens not in the well-known list, use `token-search` first:
```bash
python3 scripts/morph_api.py token-search --query "USDC"
```

## Slippage Protection

Default slippage tolerance is **1%**. Override with `--slippage`:

```bash
# Tight slippage for stablecoin pairs
python3 scripts/morph_api.py dex-quote --amount 100 --token-in USDT --token-out USDC --slippage 0.1

# Wider slippage for volatile pairs
python3 scripts/morph_api.py dex-quote --amount 1 --token-in ETH --token-out MEME_TOKEN --slippage 5
```

**Guidelines for agents:**
- Stablecoin ↔ Stablecoin: `0.1 - 0.5%`
- Major token pairs (ETH/USDT): `0.5 - 1%`
- Small-cap or volatile tokens: `2 - 5%`
- If a swap fails with "slippage too high", increase slippage or reduce amount

## Paying Swap Gas with Alt-Fee

Users with no ETH can still swap by combining DEX quote with alt-fee send:

```bash
# 1. Get swap calldata
python3 scripts/morph_api.py dex-quote \
  --amount 10 --token-in USDT --token-out ETH \
  --recipient 0xYourAddr

# 2. Send via alt-fee (pay gas with USDT)
python3 scripts/morph_api.py altfee-send \
  --to <router from quote> \
  --value 0 \
  --data <calldata from quote> \
  --fee-token-id 5 \
  --private-key 0xKey
```

This is especially useful for new users who received tokens but no ETH.

## ERC20 Approval

When swapping **from** an ERC20 token (not ETH), the token must be approved for the router contract first. The skill does **not** handle approvals automatically.

**Agent workflow for ERC20 → ERC20 swaps:**
1. Check if the router has sufficient allowance (not currently supported by the skill — inform the user)
2. If not approved, the user must approve the router contract manually or via a separate tool
3. Then proceed with `dex-quote` → `dex-send`

For ETH → ERC20 swaps, no approval is needed (ETH is wrapped by the router).

## Quote Expiry

DEX quotes are **not** stored on-chain — they represent a snapshot of current pool state. The calldata includes a deadline (default: **300 seconds / 5 minutes**). Between quoting and sending:
- Pool prices may shift
- Liquidity may change
- The transaction may revert if slippage bounds are exceeded

**Best practice**: quote and send within the same interaction. Do not cache quotes for later use.

## Common Pitfalls

1. **Missing `--recipient`**: without it, `dex-quote` returns price info only — no calldata for execution
2. **Stale quotes**: pool state changes every block (~2 seconds); always get a fresh quote before sending
3. **Insufficient gas**: swap transactions use more gas than simple transfers; default gas estimation should suffice, but complex routes may need higher limits
4. **Token not found**: if `token-in` or `token-out` is not in the well-known list, resolve the contract address with `token-search` first
5. **Swapping full balance**: leave enough for gas (or use alt-fee), and account for slippage reducing the output
