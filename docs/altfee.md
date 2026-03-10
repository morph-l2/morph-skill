# Alt-Fee: Pay Gas with Alternative Tokens

> Deep-dive guide for AI agents working with Morph's alternative fee payment system.
> Load this document when the user asks about paying gas with non-ETH tokens.

## Overview

Morph is the only L2 that supports **paying gas fees with ERC20 tokens** instead of ETH. This is implemented as a custom transaction type `0x7f`, managed by an on-chain TokenRegistry.

When a user has no ETH but holds USDT0 (or another supported fee token), they can still send transactions by paying gas in that token.

## How It Works

### Transaction Type `0x7f`

Standard Ethereum transactions use type `0x02` (EIP-1559). Morph extends this with type `0x7f`, which adds two extra fields:

| Field | Type | Description |
|-------|------|-------------|
| `feeTokenId` | `uint256` | ID of the fee token in the TokenRegistry (1-5) |
| `feeTokenAmount` | `uint256` | Maximum amount of fee token to spend (`feeLimit`) |

The rest of the transaction fields (nonce, gas, to, value, data) are identical to EIP-1559.

### Fee Calculation

```
feeLimit >= (gasFeeCap × gasLimit + L1DataFee) × tokenScale / feeRate
```

Where:
- **gasFeeCap × gasLimit**: maximum L2 gas cost in wei
- **L1DataFee**: cost of posting calldata to L1 (depends on calldata size and L1 gas price)
- **tokenScale**: scaling factor from TokenRegistry (handles decimal differences)
- **feeRate**: exchange rate from TokenRegistry

### What `feeLimit = 0` Means

Setting `feeLimit` to `0` does **not** mean "free". It means "no limit" — the protocol will deduct whatever gas costs from the user's fee token balance. Any unused portion is refunded.

This is the recommended default for most use cases. The user's balance acts as the natural cap.

### Refund Mechanism

After transaction execution:
1. Actual gas used is calculated
2. Fee token cost = actual gas cost × tokenScale / feeRate
3. Excess fee token (feeLimit - actual cost) is refunded to the sender

## TokenRegistry

The TokenRegistry is a pre-deployed system contract at `0x5300000000000000000000000000000000000021`. It stores:

- Which ERC20 tokens are accepted as fee tokens
- The exchange rate (`feeRate`) and scaling factor (`tokenScale`) for each
- Whether each token is currently active

### Known Fee Tokens

| ID | Token | Status |
|----|-------|--------|
| 5 | USDT0 (`0xe7cd86e13AC4309349F30B3435a9d337750fC82D`) | Active |

Use `altfee-tokens` to get the current full list, as tokens and rates can change.

## Agent Decision Flow

```
User wants to send a transaction
    ↓
Check ETH balance (balance command)
    ↓
├── Has ETH → use normal transfer / dex-send
└── No ETH → check fee token balance (token-balance)
        ↓
        ├── Has fee token → use altfee-send
        └── No fee token → inform user they need ETH or a fee token
```

## Combining with DEX Swaps

Alt-fee transactions can carry arbitrary calldata, making them compatible with DEX swaps:

```
1. dex-quote --recipient 0xAddr     → get swap calldata
2. altfee-send --to <router>        → send swap tx, pay gas with USDT0
     --data <calldata from step 1>
     --fee-token-id 5
     --private-key 0xKey
```

This lets users swap tokens even when they have zero ETH.

## Limitations

- **EIP-7702 incompatible**: Alt-fee and EIP-7702 (account abstraction) cannot be used in the same transaction
- **Fee token must be pre-approved**: only tokens registered in the TokenRegistry are accepted
- **L1DataFee is not fully estimable**: `altfee-estimate` provides a conservative estimate for L2 gas only; actual cost includes L1 data posting fees
- **Token rates are not real-time**: TokenRegistry rates are updated periodically, not per-block

## Common Pitfalls

1. **Forgetting to check fee token balance**: `altfee-send` will fail on-chain if the user lacks sufficient fee token balance
2. **Using `altfee-estimate` as exact cost**: the estimate covers L2 gas only; actual cost may be higher due to L1DataFee — recommend `feeLimit = 0` unless the user specifically wants a cap
3. **Assuming all tokens are fee tokens**: only tokens in the TokenRegistry (currently IDs 1-5) are accepted; arbitrary ERC20 tokens cannot be used for gas payment
