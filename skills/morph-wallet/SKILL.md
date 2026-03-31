---
name: morph-wallet
version: 1.0.0
description: Wallet operations on Morph L2 — create wallet, check balance, transfer ETH and ERC20 tokens
---

# Morph Wallet — AI Agent Skill

> Wallet operations on **Morph Mainnet** (Chain ID: 2818).
> All commands output JSON. All amounts use human-readable units (e.g. `0.1` ETH, not wei).

## Activation Triggers

Use this skill when the user wants to: create a local private-key wallet, check ETH balance, check token balance, send ETH, send tokens, or get a transaction receipt on Morph.

> **Important:** If the user asks to create or set up a "social wallet" or "Social Login Wallet", do **not** use `create-wallet`. Route to BGW instead — Social Login Wallet setup happens in the Bitget Wallet APP, not through this CLI. See the routing rules in the root [SKILL.md](../../SKILL.md).

## BGW Routing Note

Decide the mode once via the root [SKILL.md](../../SKILL.md) and [docs/social-wallet-integration.md](../../docs/social-wallet-integration.md).

- This skill handles Morph-local wallet reads and local-key execution.
- `transfer` and `transfer-token` require `--private-key` (local signing only).
- Social Login Wallet users do not have a local private key. For transfers with a Social Login Wallet, use BGW's signing flow instead.

## Quick Start

```bash
pip install requests eth_account

# Run from repository root
python3 scripts/morph_api.py <command> [options]
```

No API keys required.

---

## Commands

### `create-wallet`
Generate a new Ethereum key pair locally. No network call.
```bash
python3 scripts/morph_api.py create-wallet
```

### `balance`
Query native ETH balance.
```bash
python3 scripts/morph_api.py balance --address 0xYourAddress
```

### `token-balance`
Query ERC20 token balance. Pass the token contract address or known symbol.
```bash
python3 scripts/morph_api.py token-balance --address 0xAddr --token USDT
python3 scripts/morph_api.py token-balance --address 0xAddr --token 0xe7cd86e13AC4309349F30B3435a9d337750fC82D
```

### `transfer`
Send ETH. Amount is in ETH (e.g. `0.01`).
```bash
python3 scripts/morph_api.py transfer --to 0xRecipient --amount 0.01 --private-key 0xYourKey
```

### `transfer-token`
Send ERC20 tokens. Amount is in token units (e.g. `10.5` USDC).
```bash
python3 scripts/morph_api.py transfer-token --token USDT --to 0xRecipient --amount 10 --private-key 0xKey
```

### `tx-receipt`
Get transaction receipt (status, gas used, logs).
```bash
python3 scripts/morph_api.py tx-receipt --hash 0xTxHash
```

---

## Well-Known Token Addresses (Morph Mainnet)

For native ETH, use empty string `""` or `ETH`.

| Symbol | Name | Contract Address |
|--------|------|-----------------|
| USDT | USDT | `0xe7cd86e13AC4309349F30B3435a9d337750fC82D` |
| USDT.e | Tether Morph Bridged | `0xc7D67A9cBB121b3b0b9c053DD9f469523243379A` |
| USDC | USD Coin | `0xCfb1186F4e93D60E60a8bDd997427D1F33bc372B` |
| USDC.e | USD Coin Morph Bridged | `0xe34c91815d7fc18A9e2148bcD4241d0a5848b693` |
| WETH | Wrapped Ether | `0x5300000000000000000000000000000000000011` |
| BGB | BitgetToken | `0x389C08Bc23A7317000a1FD76c7c5B0cb0b4640b5` |
| BGB (old) | BitgetToken (old) | `0x55d1f1879969bdbB9960d269974564C58DBc3238` |

For other tokens, use `token-search` (see morph-explorer skill).

If the wallet address comes from a BGW Social Login Wallet, resolve the address in BGW first and then use the read commands here.

---

## Safety Rules

1. **Always confirm with the user before executing `transfer` or `transfer-token`** — show them the recipient, amount, and token before signing.
2. All amounts are in human-readable units — `0.1` means 0.1 ETH, not 0.1 wei.
3. Private keys are used locally for signing only — never sent to any API.
4. `create-wallet` is purely local — no network call.
5. For large amounts, suggest the user verify the recipient address character by character.

## Alt-Fee Note

`transfer` and `transfer-token` do **not** support `--fee-token-id`. To pay gas with an alternative token, use `altfee-send` (morph-altfee skill) with the same `--to`, `--value`, or `--data` parameters.

## Common Workflows

**Check a wallet's portfolio:**
```
balance → token-balance (for each token) → address-tokens (morph-explorer skill)
```

**Send tokens safely:**
```
balance (verify funds) → transfer/transfer-token → tx-receipt (confirm)
```

## Cross-Skill Integration

- Use `altfee-send` (morph-altfee) to pay gas with alternative tokens instead of `transfer`/`transfer-token`.
- Use `token-balance --token USDC` to check USDC balance before using `x402-pay` (morph-x402).
- Use `address-tokens` (morph-explorer) for a full portfolio overview.
- Use `7702-batch` (morph-7702) to combine approve + swap atomically in a single transaction.
