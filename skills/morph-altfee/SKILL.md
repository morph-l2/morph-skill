# Morph Alt-Fee — AI Agent Skill

> Pay gas with alternative tokens (tx type `0x7f`) on **Morph Mainnet** (Chain ID: 2818).
> All commands output JSON. Morph-exclusive feature not available on other L2s.

## Activation Triggers

Use this skill when the user wants to: list fee tokens, check fee token info, estimate gas cost in an alternative token, or send a transaction paying gas with a non-ETH token on Morph.

## Quick Start

```bash
pip install requests eth_account

# Run from repository root
python3 scripts/morph_api.py <command> [options]
```

No API keys required. Queries the on-chain TokenRegistry at `0x5300000000000000000000000000000000000021`.

---

## Commands

### `altfee-tokens`
List all supported fee tokens from the on-chain TokenRegistry.
```bash
python3 scripts/morph_api.py altfee-tokens
```

### `altfee-token-info`
Get details for a specific fee token: contract address, scale, feeRate, decimals, active status.
```bash
python3 scripts/morph_api.py altfee-token-info --id 5
```

### `altfee-estimate`
Estimate the minimum feeLimit needed to pay gas with a fee token. Includes a 10% safety margin.
```bash
# Estimate for a simple ETH transfer (21000 gas)
python3 scripts/morph_api.py altfee-estimate --id 5

# Estimate for an ERC20 transfer (200000 gas)
python3 scripts/morph_api.py altfee-estimate --id 5 --gas-limit 200000
```

### `altfee-send`
Sign and broadcast a transaction paying gas with an alternative fee token (tx type `0x7f`). `--fee-limit` defaults to 0 (no limit — uses available balance, unused portion is refunded).
```bash
# Simple ETH transfer, pay gas with USDT (token ID 5)
python3 scripts/morph_api.py altfee-send --to 0xRecipient --value 0.01 --fee-token-id 5 --private-key 0xKey

# Contract call with explicit fee limit and gas limit
python3 scripts/morph_api.py altfee-send --to 0xContract --data 0xCalldata... --fee-token-id 5 --fee-limit 500000 --gas-limit 200000 --private-key 0xKey
```

---

## Safety Rules

1. **Always confirm with the user before executing `altfee-send`** — show the recipient, amount, fee token, and fee limit before signing.
2. Private keys are used locally for signing only — never sent to any API.
3. Default `feeLimit=0` means no limit — unused portion is refunded, but confirm this with the user.

## Domain Knowledge

- Morph supports paying gas with alternative tokens via custom transaction type `0x7f`
- Fee tokens are managed by the on-chain TokenRegistry (IDs 1-5)
- Formula: `feeLimit >= (gasFeeCap × gasLimit + L1DataFee) × tokenScale / feeRate`
- `feeLimit = 0` means "no limit" — uses entire balance, unused portion is refunded
- Fee token 5 = USDT (`0xe7cd86e13AC4309349F30B3435a9d337750fC82D`)
- Alt-fee and EIP-7702 are mutually exclusive — cannot use both in one transaction
- L1 Data Fee depends on calldata size and L1 gas price; not estimable upfront

## Common Workflows

**Pay gas with alternative token:**
```
altfee-tokens (list available) → altfee-estimate (calculate cost) → altfee-send (sign & broadcast)
```

**DEX swap with alt-fee gas payment:**
```
dex-quote --recipient 0xAddr (morph-dex skill) → altfee-send --data 0xCalldata... --fee-token-id 5
```

## Cross-Skill Integration

- Use `dex-quote` (morph-dex) to get swap calldata, then pass to `altfee-send` for gas payment with alt tokens.
- Use `token-balance` (morph-wallet) to check fee token balance before sending.
- Use `balance` (morph-wallet) to check if user has ETH — if not, suggest alt-fee.
