# Morph Skill

## Overview

An AI Agent skill for interacting with the [Morph](https://www.morphl2.io/) L2 blockchain, enabling natural-language-driven wallet operations, on-chain data queries, and DEX swaps.

### Core Capabilities

| Capability | Description | Example |
|------------|-------------|---------|
| **Wallet Create** | Generate ETH key pair locally | "Create a new wallet" |
| **Balance Query** | Native ETH and ERC20 token balances | "How much ETH do I have?" |
| **Token Transfer** | Send ETH or ERC20 tokens | "Send 10 USDT to 0x..." |
| **Transaction Lookup** | Receipt and detailed tx info | "What happened in this tx?" |
| **Address Info** | On-chain address summary | "Show me this wallet's activity" |
| **Transaction History** | List transactions for an address | "Recent txs for 0x..." |
| **Token Holdings** | All token balances for an address | "What tokens does this wallet hold?" |
| **Token Search** | Find tokens by name or symbol | "Find the USDT contract address" |
| **Token Info** | Token details: supply, holders, transfers | "How many holders does USDT have?" |
| **DEX Quote** | Best-route swap quote + calldata | "How much USDT for 1 ETH?" |
| **DEX Send** | Sign and broadcast swap transaction | Complete the swap on-chain |
| **Alt-Fee Tokens** | List supported alt-fee tokens | "What tokens can I use to pay gas?" |
| **Alt-Fee Token Info** | Fee token details (scale, rate) | "Get info for fee token 5" |
| **Alt-Fee Estimate** | Estimate gas cost in alt token | "How much USDT to cover gas?" |
| **Alt-Fee Send** | Send tx paying gas with alt token | "Transfer ETH, pay gas with USDT" |

> **Amounts are human-readable** — pass `0.1` for 0.1 ETH, NOT `100000000000000000` wei.

### Data Sources

All endpoints are public — **no API keys required**.

| Source | Base URL |
|--------|----------|
| Morph RPC | `https://rpc.morph.network/` |
| Explorer API (Blockscout) | `https://explorer-api.morph.network/api/v2` |
| DEX Aggregator | `https://api.bulbaswap.io` |

---

## Architecture

```
Natural Language Input
    ↓
AI Agent (Claude Code / Cursor / OpenClaw / Custom)
    ↓  ← loads skill from skills/ (wallet, explorer, dex, altfee)
morph_api.py (Python 3.11+)
    ↓  ← No API keys needed, all public endpoints
Direct RPC / Explorer / DEX API calls
    ↓
Structured JSON → Agent interprets → Natural language response
```

**Security by Design:**
- No API keys or authentication required — all Morph endpoints are public
- Transfer commands only sign and broadcast; **the agent must confirm with the user before executing**
- Private keys are used locally for signing only — never sent to any API
- `create-wallet` is purely offline — no network call

---

## Agent Use Cases

### 1. Portfolio Tracker
> "What's my total balance on Morph?"

- Query ETH balance + all token holdings in one go
- For: DeFi users, fund managers

### 2. On-Chain Research Assistant
> "Show me recent transactions for this address and what tokens they hold."

- Address info + transaction history + token holdings combined
- For: researchers, analysts

### 3. Trading Assistant
> "Swap 1 ETH for USDT on Morph"

- DEX quote (with --recipient) → show price and route → user confirms → dex-send (sign & broadcast)
- **Human-in-the-loop** — the agent cannot sign without the user's private key
- For: active traders wanting an AI assistant

### 4. Token Discovery
> "What new tokens are on Morph? Is this token safe?"

- Token list + token search for discovery
- For: alpha hunters, community managers

---

## Quick Start

### Prerequisites

1. Python 3.11+
2. `pip install requests eth_account`
3. That's it — no API keys needed.

### Examples

```bash
# Create a new wallet
python3 scripts/morph_api.py create-wallet

# Check ETH balance
python3 scripts/morph_api.py balance --address 0xYourAddress

# Check USDT balance (symbol resolved automatically)
python3 scripts/morph_api.py token-balance --address 0xYourAddress --token USDT

# Address info from explorer
python3 scripts/morph_api.py address-info --address 0xYourAddress

# Search for a token
python3 scripts/morph_api.py token-search --query "USDC"

# DEX swap quote (1 ETH → USDT)
python3 scripts/morph_api.py dex-quote --amount 1 --token-in ETH --token-out USDT

# Send ETH
python3 scripts/morph_api.py transfer --to 0xRecipient --amount 0.01 --private-key 0xYourKey

# List fee tokens (alt-fee: pay gas with non-ETH tokens)
python3 scripts/morph_api.py altfee-tokens

# Estimate gas cost in USDT (fee token ID 5)
python3 scripts/morph_api.py altfee-estimate --id 5 --gas-limit 21000
```

---

## Commands

### Wallet (RPC)

| Command | Description |
|---------|-------------|
| `create-wallet` | Generate a new ETH key pair locally |
| `balance` | Query native ETH balance |
| `token-balance` | Query ERC20 token balance |
| `transfer` | Send ETH to an address |
| `transfer-token` | Send ERC20 tokens to an address |
| `tx-receipt` | Query transaction receipt |

### Explorer (Blockscout)

| Command | Description |
|---------|-------------|
| `address-info` | Address summary (balance, tx count, type) |
| `address-txs` | Transaction history for an address |
| `address-tokens` | All token holdings for an address |
| `tx-detail` | Full transaction details (decoded input, token transfers) |
| `token-search` | Search tokens by name or symbol |
| `token-info` | Token details (supply, holders, transfers, market data) |
| `token-list` | List top tracked tokens from the explorer (single page) |

### DEX

| Command | Description |
|---------|-------------|
| `dex-quote` | Get a swap quote (with --recipient for calldata) |
| `dex-send` | Sign and broadcast swap tx using calldata from dex-quote |

### Alt-Fee (Alternative Gas Payment)

| Command | Description |
|---------|-------------|
| `altfee-tokens` | List supported fee tokens from TokenRegistry |
| `altfee-token-info` | Get fee token details (scale, feeRate, decimals) |
| `altfee-estimate` | Estimate feeLimit for paying gas with alt token |
| `altfee-send` | Send transaction paying gas with alt fee token (0x7f) |

Run `python3 scripts/morph_api.py <command> --help` for detailed usage.

---

## Compatible Platforms

### Should Work (file system + Python + network access)

| Platform | Type | How to Use |
|----------|------|------------|
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | CLI Agent | Install as plugin via `.claude-plugin/` |
| [Cursor](https://cursor.com) | IDE Agent | Install as plugin via `.cursor-plugin/` |
| [Windsurf](https://codeium.com/windsurf) | IDE Agent | Clone into project workspace |
| [Cline](https://github.com/cline/cline) | VS Code Agent | Clone into project workspace |
| [OpenClaw](https://openclaw.ai) | Agent Platform | Native skill support |
| [Dify](https://dify.ai) | Workflow Platform | Use as Code node or external API Tool |
| [LangChain](https://langchain.com) / [CrewAI](https://crewai.com) | Frameworks | Wrap `morph_api.py` as a Tool |

### Compatibility Rule

Any AI agent that can **read files + run Python + access the internet** should work with this skill.

---

## For AI Agents

See [SKILL.md](SKILL.md) for the unified agent reference, or use individual skill modules:

| Skill | Description |
|-------|-------------|
| [morph-wallet](skills/morph-wallet/SKILL.md) | Wallet operations (create, balance, transfer) |
| [morph-explorer](skills/morph-explorer/SKILL.md) | On-chain data queries (address, tx, token info) |
| [morph-dex](skills/morph-dex/SKILL.md) | DEX swap (quote + send) |
| [morph-altfee](skills/morph-altfee/SKILL.md) | Alt-fee gas payment (0x7f tx type) |

---

## Security

- All data sources are public — no API keys, no authentication
- No `eval()` / `exec()` or dynamic code execution
- Private keys are only used locally for transaction signing
- Transfer commands require explicit user confirmation (human-in-the-loop)
- No data collection, telemetry, or analytics
- Dependencies: `requests`, `eth_account` (stdlib: `json`, `argparse`, `decimal`)
- We recommend auditing the source yourself before use

## License

MIT
