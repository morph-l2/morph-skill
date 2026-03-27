---
name: morph-identity
version: 1.4.0
description: EIP-8004 agent identity and reputation commands for Morph — register agents, query metadata, submit and read feedback
---

# Morph Identity — AI Agent Skill

> EIP-8004 agent identity and reputation on **Morph Mainnet** (Chain ID: 2818).
> All commands output JSON. On-chain via bundled ABIs — no external API keys required.

## Activation Triggers

Use this skill when the user wants to: register an agent identity, query agent metadata or wallet, check agent reputation, submit feedback for an agent, or read agent reviews.

## Quick Start

```bash
pip install requests eth_account eth_abi eth_utils

# Run from repository root
python3 scripts/morph_api.py <command> [options]
```

No API keys required. Talks directly to Morph RPC using bundled ABI files.

---

## Commands

### `agent-register`
Register an agent identity with optional URI and metadata. Optionally pass `--fee-token-id` to pay gas via altfee.
```bash
python3 scripts/morph_api.py agent-register --name "MorphBot" --agent-uri "https://example.com/agent.json" --metadata role=assistant,team=research --private-key 0xYourKey

# With altfee gas payment
python3 scripts/morph_api.py agent-register --name "MorphBot" --fee-token-id 5 --private-key 0xYourKey
```

### `agent-wallet`
Read the payment wallet for an agent.
```bash
python3 scripts/morph_api.py agent-wallet --agent-id <agent_id>
```

### `agent-metadata`
Read one metadata value by key.
```bash
python3 scripts/morph_api.py agent-metadata --agent-id <agent_id> --key name
```

### `agent-reputation`
Read aggregated reputation and feedback count.
```bash
python3 scripts/morph_api.py agent-reputation --agent-id <agent_id> --tag1 quality
```

### `agent-feedback`
Submit feedback for an agent. Scores are encoded with 2 decimals. Optionally pass `--fee-token-id` to pay gas via altfee.
```bash
python3 scripts/morph_api.py agent-feedback --agent-id <agent_id> --value 4.5 --tag1 quality --feedback-uri "https://example.com/review/1" --private-key 0xYourKey

# With altfee gas payment
python3 scripts/morph_api.py agent-feedback --agent-id <agent_id> --value 4.5 --fee-token-id 5 --private-key 0xYourKey
```

### `agent-reviews`
Read all feedback entries for an agent.
```bash
python3 scripts/morph_api.py agent-reviews --agent-id <agent_id> --include-revoked
```

---

## Safety Rules

1. **Always confirm with the user before executing `agent-register`** — show the name, URI, and metadata before signing.
2. **Always confirm with the user before executing `agent-feedback`** — show the target agentId, score, and tags before signing.
3. Private keys are used locally for signing only — never sent to any API.
4. Read-only commands (`agent-wallet`, `agent-metadata`, `agent-reputation`, `agent-reviews`) require no private key.

## Domain Knowledge

- **EIP-8004** defines a standard for on-chain agent identity and reputation, enabling agents to register an identity (as an ERC-721 NFT), attach metadata, and receive feedback from other participants.
- **IdentityRegistry** contract: default `0x8004A169FB4a3325136EB29fA0ceB6D2e539a432` (override via `MORPH_IDENTITY_REGISTRY` env var)
- **ReputationRegistry** contract: default `0x8004BAa17C55a88189AE136b182e5fdA19dE9b63` (override via `MORPH_REPUTATION_REGISTRY` env var)
- ABI files bundled under `contracts/IdentityRegistry.json` and `contracts/ReputationRegistry.json`
- Network overrides: `MORPH_RPC_URL`, `MORPH_CHAIN_ID`
- For Hoodi testnet, set all env vars to testnet values (see root SKILL.md)

## Common Workflows

**Register an agent and verify:**
```
agent-register → agent-wallet → agent-metadata --key name
```

**Check an agent's reputation:**
```
agent-reputation → agent-reviews
```

**Submit feedback for an agent:**
```
agent-feedback --value 4.5 --tag1 quality → agent-reputation (verify updated)
```

## Cross-Skill Integration

- Use `balance` (morph-wallet) to check ETH for gas before `agent-register` or `agent-feedback`.
- Use `tx-receipt` (morph-wallet) to inspect transaction logs if `agent-register` times out before returning `agent_id`.
- Use `--fee-token-id` on `agent-register` or `agent-feedback` if the user wants to pay gas with an alternative token.
