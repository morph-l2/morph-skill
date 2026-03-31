# Social Login Wallet Integration Guide

> Use this guide when the user asks about Social Login Wallet, TEE signing, or how BGW skills should work together with Morph skills.

## Responsibility Split

Morph and BGW are two cooperating skill packs with different responsibilities:

| Layer | Owns | Examples |
|-------|------|----------|
| Morph skills | Morph protocol and business logic | explorer queries, wallet RPC reads, DEX quotes, bridge quotes/orders, altfee, EIP-8004 identity and reputation |
| BGW skills | Wallet product, market data, and signing layer | Social Login Wallet (TEE signing), swap execution across chains, token discovery, market data, security audits |

### Morph Owns

- Morph chain reads and local-key writes
- Token resolution and Morph business naming
- DEX quote generation (Morph-only)
- Bridge quote generation and order management
- Altfee transaction mechanics
- EIP-8004 identity and reputation workflows

### BGW Owns

- Social Login Wallet onboarding and TEE-backed signing
- Swap execution across all supported chains including Morph
- Token discovery, market data, security audits
- Wallet session identity

> **Note:** BGW's login flow (email/Google/Apple) happens in the Bitget Wallet APP, not through skill commands. Account recovery and device management are also handled in the APP, not in the skill pack.

## Required Agent Setup

For agents expected to help with both Morph protocol actions and Social Login Wallet flows:

1. Load the Morph skills.
2. When a Social Login Wallet flow is needed, locate or auto-clone the BGW skills (see "Locating BGW Skills" below).
3. **Read BGW's `SKILL.md`** after locating it — that is the authoritative source for all BGW commands, parameters, and flows. Do not rely on this document for BGW command details.
4. Decide which skill pack owns the current step before executing anything.

Do not assume the Morph repo alone can complete a Social Login Wallet flow. Do not ask the user to manually install BGW — auto-clone it when needed.

### Locating BGW Skills (Auto-Setup)

Morph and BGW scripts live in **separate repositories**. Before executing any BGW command, the agent must locate or install the BGW skill directory.

**Resolution order:**

1. Check if `BGW_DIR` environment variable is set → use it.
2. Look for `bitget-wallet-skill/` as a sibling directory (next to the Morph skill directory).
3. **If not found → auto-clone:**

```bash
# Auto-clone BGW to sibling directory of Morph skills
MORPH_DIR="$(cd "$(dirname "$0")" && pwd)"  # or the known Morph skill path
BGW_DIR="$(dirname "$MORPH_DIR")/bitget-wallet-skill"
git clone https://github.com/bitget-wallet-ai-lab/bitget-wallet-skill.git "$BGW_DIR"
pip install -r "$BGW_DIR/requirements.txt" 2>/dev/null || pip install requests
```

After cloning, **read `$BGW_DIR/SKILL.md`** to understand BGW's commands and flows.

**Do not ask the user to manually clone.** If the agent has shell access and BGW is needed, clone it automatically and continue.

### Working Directory Rule

When executing commands, use the correct working directory:

- **Morph commands** (`morph_api.py`): run from the Morph skill directory.
- **BGW commands**: run from the BGW skill directory (`$BGW_DIR`). Check BGW's `SKILL.md` for exact script names and parameters.

> **Important:** This document intentionally does not list BGW script names, command names, or parameters. BGW's `SKILL.md` is the single source of truth for BGW implementation details. This ensures that BGW updates never break Morph's documentation.

## Routing Rules

### One-Time Route Selection

Pick a mode once at the beginning of the task:

| Mode | Use when | Result |
|------|----------|--------|
| `morph-local-execution` | user supplied a private key or explicitly wants local-key execution now | stay in Morph |
| `bgw-wallet-mode` | user wants Social Login Wallet, TEE signing, swap execution via BGW, or market data queries | stay in BGW |
| `bgw-address-then-morph-read` | user has a BGW wallet but only needs Morph reads | BGW resolves address, Morph handles reads |
| `bgw-plus-morph-planning` | user wants BGW wallet context plus Morph protocol reasoning (no writes through Morph) | BGW provides wallet context, Morph provides read/planning logic |

Do not repeatedly re-route the same task. Once the mode is chosen, only hand off the minimal context needed.

### Quick Handoff Rules

| Situation | Route |
|----------|-------|
| User already supplied a local private key and wants Morph execution now | Stay in Morph |
| User asks for Social Login Wallet or TEE signing | Route to BGW |
| User only needs Morph reads for a BGW wallet | Get the address from BGW, then use Morph reads |
| User wants to swap/bridge with a Social Login Wallet | **Use BGW's swap flow** — read BGW's `SKILL.md` for execution details |
| User asks for BGW-backed execution inside Morph CLI | Explain that Morph CLI requires `--private-key`; for Social Login Wallet execution, use BGW's flows instead |

### Morph-only

Use Morph skills directly when the user wants:

- local wallet creation with a local private key
- Morph balance, token balance, transaction, address, token, or contract queries
- DEX quotes and swaps on Morph through direct local signing
- bridge quotes and order management through direct local signing
- altfee gas payment on Morph
- EIP-8004 agent registration, metadata, reputation, and feedback through direct local signing

### BGW-only

Use BGW skills (read BGW's `SKILL.md` for commands) when the user wants:

- Social Login Wallet setup or wallet identity
- TEE-backed signing
- swap execution (BGW supports Morph and other chains natively with TEE signing)
- token discovery, market data, or security audits
- wallet session identity

### Combined BGW + Morph

Use both skill packs when the user wants Morph-specific protocol queries from a BGW-backed wallet.

Typical pattern:

1. Use BGW to resolve the wallet address (read BGW's `SKILL.md` for the address command).
2. Use Morph skills for Morph-specific reads or protocol reasoning.

The handoff should be minimal:

- address
- user intent
- whether the next step is read-only or planning-only

Do not copy the entire BGW workflow into Morph prompts or vice versa.

### Critical: Writes with a Social Login Wallet

Morph write commands (`transfer`, `transfer-token`, `dex-send`, `altfee-send`, `bridge-swap`, `agent-register`, `agent-feedback`) all require `--private-key`. Social Login Wallet users do not have a local private key — their keys live in Bitget's TEE.

**For Social Login Wallet users who want to execute writes on Morph:**

Use BGW's swap flow directly. BGW supports Morph chain natively with TEE signing. Read BGW's `SKILL.md` for the full swap execution flow (setup, balance checks, quote, confirm, sign, send).

Do not attempt to use Morph's `dex-send` or `transfer` with a Social Login Wallet — they require `--private-key` which Social Login Wallets do not expose.

## Combined Flow Examples

### BGW address → Morph reads

Use this pattern when the user has a Social Login Wallet and wants Morph-specific data.

1. **Get address from BGW** — use BGW's address command (read BGW's `SKILL.md`). EVM addresses are chain-agnostic, so the address works on Morph.
2. **Use Morph reads** with the address:

```bash
# Morph reads (Morph chain only)
python3 scripts/morph_api.py balance --address 0xAbC123...
python3 scripts/morph_api.py token-balance --address 0xAbC123... --token USDT
python3 scripts/morph_api.py address-info --address 0xAbC123...
python3 scripts/morph_api.py address-tokens --address 0xAbC123...
```

> **Chain selection:** Morph's `balance` and `address-tokens` only query the Morph chain. If the user asks for balance without specifying a chain, use BGW's balance command instead (it supports all chains and returns USD prices). Use Morph reads only when the user specifically asks about Morph chain data.

### Morph protocol reasoning → BGW execution

Use Morph skills for protocol reasoning (read-only, works for any wallet type):

```bash
# Compare DEX prices on Morph
python3 scripts/morph_api.py dex-quote --amount 1 --token-in ETH --token-out USDT

# Compare bridge prices across chains
python3 scripts/morph_api.py bridge-quote --from-chain morph --from-token ETH --amount 1 --to-chain base --to-token USDC --from-address 0xAbC123...
```

Then for execution with a Social Login Wallet, switch to BGW. Read BGW's `SKILL.md` for the swap execution flow. Do not use Morph's write commands — they require `--private-key`.

### Identity or reputation with a BGW wallet

Morph identity and reputation remain Morph-side business capabilities. For Social Login Wallet users:

- Read commands work directly: resolve address from BGW, then look up the agent ID (via `agent-register` receipt or explorer logs), and use `agent-reputation`, `agent-reviews`, `agent-metadata` with `--agent-id`.
- Write commands (`agent-register`, `agent-feedback`) require `--private-key`. Social Login Wallet users cannot use these through Morph CLI today.

## Current Direct Execution Status

| Scenario | Status |
|----------|--------|
| Morph read commands with any known address | Directly supported |
| Morph write commands with local signing (`--private-key`) | Directly supported |
| Morph write commands paid with altfee where available | Directly supported |
| BGW as a companion wallet source for address discovery and reads | Supported as an orchestration pattern |
| Swap/bridge execution for Social Login Wallet users | **Use BGW's swap flow** — read BGW's `SKILL.md` |
| Identity writes for Social Login Wallet users | Not supported — `agent-register` and `agent-feedback` require `--private-key` |

## Preference Rules For Agents

When both options are possible, prefer:

1. Direct Morph execution when the user has explicitly provided a private key and wants the action completed in this repo now.
2. BGW when the user is asking for Social Login Wallet capabilities or TEE-backed signing.
3. BGW's swap flow for Social Login Wallet users who want to execute swaps or bridges on Morph — BGW supports Morph chain natively.
4. A combined flow only when the task genuinely spans both layers, such as "use my BGW wallet address to inspect Morph positions."

Do not escalate a straightforward local-key Morph flow into BGW unless the user is actually asking for BGW-specific behavior.

### Preferred Communication Pattern

When routing, the agent should communicate in this order:

1. state the selected mode once
2. explain why that mode applies
3. continue with the next concrete action

Avoid saying:

- "go to BGW, then come back, then maybe go back again"
- "this might use either Morph or BGW" without choosing

Prefer saying:

- "This is a BGW wallet task first; once we have the address, we will use Morph reads."
- "This is a Morph local-execution task because you already supplied a private key."
- "You are using a Social Login Wallet, so I will use BGW's swap flow for execution."

## What This Repo Does Not Do

In this phase, the Morph repo intentionally does not:

- call BGW scripts directly
- vendor or embed BGW tooling
- add `--wallet-provider bgw` to Morph commands
- manage BGW login or session state
- replace BGW's own signing or wallet UX
- document BGW command details (BGW's `SKILL.md` is the source of truth)

The integration point is routing logic and auto-setup, not runtime coupling or documentation mirroring.

## Decision Checklist For Agents

Before acting, decide:

1. Is this a Morph protocol task or a wallet-product task?
2. Does the user want local-key self-custody, or do they want Social Login Wallet behavior?
3. If the user wants writes on Morph with a Social Login Wallet, use BGW's swap flow (not Morph's write commands). Read BGW's `SKILL.md` for details.
4. If both are involved, which skill pack owns the current step?

Simple rule:

- wallet product problem → BGW (read BGW's `SKILL.md`)
- Morph chain/protocol read → Morph
- Morph write with private key → Morph
- Morph write with Social Login Wallet → BGW's swap flow
- combined flow → BGW first for wallet context, Morph second for chain reads/planning

## Important Clarifications

- Altfee is a Morph gas-payment mechanism. It is not the same thing as Social Login Wallet.
- Morph bridge, swap, and identity flows may be combined with a BGW wallet at the orchestration level, but this repo does not directly wrap BGW execution.
- If the user asks for a Social Login Wallet flow and the agent only has Morph skills loaded, the agent should explicitly state that BGW skills are also needed, then auto-clone BGW.
- Users may still choose the direct local-signing path with `--private-key` for supported Morph write commands, even when BGW is also available as a companion skill.
- BGW uses empty string `""` for native token contract addresses; Morph DEX uses `ETH`. The agent should handle this difference when reasoning across both skills.
