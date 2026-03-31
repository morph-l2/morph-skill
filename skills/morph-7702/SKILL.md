---
name: morph-7702
version: 1.0.0
description: EIP-7702 EOA delegation on Morph L2 — batch calls and delegation management via tx type 0x04
---

# Morph EIP-7702 — AI Agent Skill

> EOA delegation on **Morph Mainnet** (Chain ID: 2818) via EIP-7702 (tx type `0x04`).
> All commands output JSON. All amounts use human-readable units (e.g. `0.1` ETH, not wei).

## Activation Triggers

Use this skill when the user wants to: check EOA delegation status, sign an authorization, send a single call with 7702 delegation, execute an atomic batch of calls via SimpleDelegation, or revoke a delegation.

## BGW Routing Note

Decide the mode once via the root [SKILL.md](../../SKILL.md) and [docs/social-wallet-integration.md](../../docs/social-wallet-integration.md).

- EIP-7702 commands require `--private-key` (local signing only).
- Social Login Wallet users cannot use 7702 commands through this skill. Route to BGW instead.

---

## Quick Start

```bash
pip install requests eth_account eth_abi eth_utils

# Run from repository root
python3 scripts/morph_api.py <command> [options]
```

No API keys required.

---

## Commands

### `7702-delegate`
Check whether an EOA has been delegated via EIP-7702.
```bash
python3 scripts/morph_api.py 7702-delegate --address 0xYourEOA
```

### `7702-authorize`
Sign a 7702 authorization object offline. No transaction is sent.
```bash
python3 scripts/morph_api.py 7702-authorize --private-key 0xKey

# Specify a custom delegate contract
python3 scripts/morph_api.py 7702-authorize --private-key 0xKey --delegate 0xCustomContract
```

### `7702-send`
Send a single call using EIP-7702 delegation (tx type `0x04`).
```bash
# Simple call
python3 scripts/morph_api.py 7702-send --to 0xContract --data 0xCalldata --private-key 0xKey

# With ETH value and custom gas
python3 scripts/morph_api.py 7702-send --to 0xContract --value 0.01 --data 0x --private-key 0xKey --gas 200000
```

### `7702-batch`
Atomically execute multiple calls via SimpleDelegation. The primary use case: approve + swap + transfer in a single atomic transaction.
```bash
python3 scripts/morph_api.py 7702-batch \
  --calls '[{"to":"0xTokenAddr","value":"0","data":"0xApproveCalldata"},{"to":"0xRouterAddr","value":"0","data":"0xSwapCalldata"}]' \
  --private-key 0xKey
```

`--calls` is a JSON array of `{to, value, data}` objects. `value` is in ETH (human-readable). `data` defaults to `0x` if omitted.

### `7702-revoke`
Revoke the EIP-7702 delegation. Clears the delegate by authorizing `address(0)`.
```bash
python3 scripts/morph_api.py 7702-revoke --private-key 0xKey
```

---

## Safety Rules

1. **Always confirm with the user before executing `7702-send`, `7702-batch`, or `7702-revoke`** — show the target, calls, and values before signing.
2. EIP-7702 and alt-fee (`0x7f`) are **mutually exclusive** — cannot use both in a single transaction.
3. `7702-revoke` clears the delegation — the EOA returns to a normal EOA until re-delegated.
4. Private keys are used locally for signing only — never sent to any API.
5. `7702-authorize` is offline — it returns a signed authorization without sending any transaction.

## Domain Knowledge

- **SimpleDelegation contract**: `0xBD7093Ded667289F9808Fa0C678F81dbB4d2eEb7` — an ERC-1271 compatible contract on Morph that supports `execute(calls, nonce, signature)` for atomic batch calls.
- **Delegation detection**: delegated EOAs have on-chain code starting with `0xef0100` followed by the 20-byte delegate address.
- **Geth nonce offset**: Morph (Geth-based) increments the sender nonce before processing the authorization list. For self-delegation, the auth nonce must be `tx_nonce + 1`. This is handled automatically by all 7702 commands.
- **delegation_nonce vs tx_nonce**: `tx_nonce` is the EOA's standard transaction nonce. `delegation_nonce` is the SimpleDelegation replay-protection counter, read from the EOA (after delegation) via `nonce()`.
- **tx type `0x04`**: EIP-7702 transactions include an `authorizationList` in the RLP encoding, enabling temporary or permanent EOA delegation within the transaction.

## Common Workflows

**Atomic approve + swap:**
```
dex-quote --recipient 0xEOA (morph-dex skill, get approve + swap calldata)
  → 7702-batch --calls '[{"to":"token","value":"0","data":"approveData"},{"to":"router","value":"0","data":"swapData"}]'
```

**Check delegation → batch → revoke:**
```
7702-delegate --address 0xEOA (check current status)
  → 7702-batch --calls '[...]' (execute atomic operations)
  → 7702-revoke (clean up delegation)
```

**One-time delegated call:**
```
7702-send --to 0xContract --data 0xCalldata (single call with temporary delegation)
```

## Cross-Skill Integration

- **morph-dex**: Use `dex-quote` to get swap calldata, then pass to `7702-batch --calls` for atomic approve + swap.
- **morph-altfee**: Mutually exclusive. Alt-fee uses tx type `0x7f`; EIP-7702 uses tx type `0x04`. Cannot combine in one transaction.
- **morph-identity**: `agent-register` calldata can be included in a `7702-batch` to combine registration with other operations atomically.
