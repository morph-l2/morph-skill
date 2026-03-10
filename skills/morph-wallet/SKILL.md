# Morph Wallet — AI Agent Skill

> Wallet operations on **Morph Mainnet** (Chain ID: 2818).
> All commands output JSON. All amounts use human-readable units (e.g. `0.1` ETH, not wei).

## Activation Triggers

Use this skill when the user wants to: create a wallet, check ETH balance, check token balance, send ETH, send tokens, or get a transaction receipt on Morph.

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
python3 scripts/morph_api.py token-balance --address 0xAddr --token USDT0
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
python3 scripts/morph_api.py transfer-token --token USDT0 --to 0xRecipient --amount 10 --private-key 0xKey
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
| USDT0 | USDT0 | `0xe7cd86e13AC4309349F30B3435a9d337750fC82D` |
| USDT.e | Tether Morph Bridged | `0xc7D67A9cBB121b3b0b9c053DD9f469523243379A` |
| USDC | USD Coin | `0xe34c91815d7fc18A9e2148bcD4241d0a5848b693` |
| WETH | Wrapped Ether | `0x5300000000000000000000000000000000000011` |
| BGB | BitgetToken | `0x389C08Bc23A7317000a1FD76c7c5B0cb0b4640b5` |
| BGB(old) | BitgetToken | `0x55d1f1879969bdbB9960d269974564C58DBc3238` |

For other tokens, use `token-search` (see morph-explorer skill).

---

## Safety Rules

1. **Always confirm with the user before executing `transfer` or `transfer-token`** — show them the recipient, amount, and token before signing.
2. All amounts are in human-readable units — `0.1` means 0.1 ETH, not 0.1 wei.
3. Private keys are used locally for signing only — never sent to any API.
4. `create-wallet` is purely local — no network call.
5. For large amounts, suggest the user verify the recipient address character by character.

## Common Workflows

**Check a wallet's portfolio:**
```
balance → token-balance (for each token) → address-tokens (morph-explorer skill)
```

**Send tokens safely:**
```
balance (verify funds) → transfer/transfer-token → tx-receipt (confirm)
```
