# Morph Skill

## Overview

An AI Agent skill for interacting with the [Morph](https://morph.network/) L2 blockchain, enabling natural-language-driven wallet operations, on-chain data queries, DEX swaps, and cross-chain bridge swaps.

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
| **Contract Info** | Contract source code, ABI, proxy info | "Is this contract verified?" |
| **Agent Register** | Register an ERC-8004 agent identity on Morph | "Register this agent with name and metadata" |
| **Agent Wallet** | Read an agent's payment wallet | "What's the wallet for agent 12?" |
| **Agent Metadata** | Read agent metadata by key | "Get the name metadata for agent 12" |
| **Agent Reputation** | Aggregate on-chain reputation summary | "Show reputation for agent 12" |
| **Agent Feedback** | Submit EIP-8004 feedback for an agent | "Leave a 4.5 score for agent 12" |
| **Agent Reviews** | Read all recorded feedback entries | "Show all reviews for agent 12" |
| **Token Transfers** | Recent transfer history for a token or address | "Show recent USDT transfers" |
| **Token Info** | Token details: supply, holders, transfers | "How many holders does USDT have?" |
| **DEX Quote** | Best-route swap quote + calldata (Morph only) | "How much USDT for 1 ETH?" |
| **DEX Send** | Sign and broadcast swap transaction (Morph only) | Complete the swap on-chain |
| **Bridge Quote** | Cross-chain swap quote across 6 chains | "How much to bridge USDC from Base to Morph?" |
| **Bridge Swap** | One-step cross-chain swap: create, sign, and submit | "Bridge 10 USDT from Morph to Base" |
| **Bridge Order** | Track cross-chain swap order status | "Check my bridge order status" |
| **Bridge Balance** | Token balance + USD price on any supported chain | "What's my USDC balance on Base?" |
| **Alt-Fee Tokens** | List supported alt-fee tokens | "What tokens can I use to pay gas?" |
| **Alt-Fee Token Info** | Fee token details (scale, rate) | "Get info for fee token 5" |
| **Alt-Fee Estimate** | Estimate gas cost in alt token | "How much USDT to cover gas?" |
| **Alt-Fee Send** | Send tx paying gas with alt token | "Transfer ETH, pay gas with USDT" |

> **Amounts are human-readable** — pass `0.1` for 0.1 ETH, NOT `100000000000000000` wei.

### Data Sources

Query endpoints are public — **no API keys required**. Bridge order management requires JWT authentication via `bridge-login`.

| Source | Base URL | Auth |
|--------|----------|------|
| Morph RPC | `https://rpc.morph.network/` | None |
| Explorer API (Blockscout) | `https://explorer-api.morph.network/api/v2` | None |
| DEX / Bridge API | `https://api.bulbaswap.io` | None (queries) / JWT (orders) |
| Bundled ABIs | `contracts/IdentityRegistry.json`, `contracts/ReputationRegistry.json` | Local files |

Default EIP-8004 contracts on Morph mainnet:
- `IdentityRegistry`: `0x672c7c7A9562B8d1e31b1321C414b44e3C75a530`
- `ReputationRegistry`: `0x23AA2fD5D0268F0e523385B8eF26711eE820B4B5`
- `ValidationRegistry`: `0x049C29201EB98F646155d130ABC6B464397b0Ac2`

---

## Architecture

```
Natural Language Input
    ↓
AI Agent (Claude Code / Cursor / OpenClaw / Custom)
    ↓  ← loads skill from skills/ (wallet, explorer, agent, dex, bridge, altfee)
morph_api.py (Python 3.9+)
    ↓  ← No API keys for queries; JWT for bridge orders
Direct RPC / Explorer / DEX / Bridge API calls
    ↓
Structured JSON → Agent interprets → Natural language response
```

**Security by Design:**
- No API keys required for queries — all Morph RPC, Explorer, and DEX quote endpoints are public
- Bridge order management uses JWT authentication (obtained via local EIP-191 wallet signature, valid 24h)
- Send commands (`transfer`, `transfer-token`, `dex-send`, `altfee-send`, `bridge-make-order`, `bridge-submit-order`, `bridge-swap`) only sign and broadcast; **the agent must confirm with the user before executing**
- Agent write commands (`agent-register`, `agent-feedback`) also sign locally and should be confirmed before execution
- Private keys are used locally for signing only — never sent to any API
- `create-wallet` is purely offline — no network call
- ERC-8004 ABI files are bundled under `contracts/`, so the skill does not depend on the workspace root layout

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

### Installation

```bash
git clone https://github.com/morph-l2/morph-skill.git
cd morph-skill
pip install requests eth_account eth_abi eth_utils
```

That's it — no API keys needed for queries. Bridge orders require JWT via `bridge-login`. Python 3.9+ required.

### Hoodi Testnet Overrides

To test the EIP-8004 agent commands on Morph Hoodi, override the network and registry addresses:

```bash
export MORPH_RPC_URL="https://rpc-hoodi.morph.network"
export MORPH_CHAIN_ID=2910
export MORPH_IDENTITY_REGISTRY="0x7DA4ec6D651416413f9bAE06258Ba61764f6ec28"
export MORPH_REPUTATION_REGISTRY="0x3c3f5352Bc61D9242Dd08Bf2D7Bd1695057112D0"
export MORPH_VALIDATION_REGISTRY="0xCc68DeeAEEFf825c0bC4a27ebedB2ee9a9d34D7C"
```

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

# Register an agent
python3 scripts/morph_api.py agent-register --name "MorphBot" --agent-uri "https://example.com/agent.json" --metadata role=assistant,team=research --private-key 0xYourKey

# Read agent reputation
python3 scripts/morph_api.py agent-reputation --agent-id 1

# Submit agent feedback
python3 scripts/morph_api.py agent-feedback --agent-id 1 --value 4.5 --tag1 quality --feedback-uri "https://example.com/review/1" --private-key 0xYourKey

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
| `contract-info` | Smart contract source code, ABI, verification status |
| `token-transfers` | Recent token transfers by token or address |
| `token-info` | Token details (supply, holders, transfers, market data) |
| `token-list` | List top tracked tokens from the explorer (single page) |

### Agent (EIP-8004)

| Command | Description |
|---------|-------------|
| `agent-register` | Register an agent identity with optional URI and metadata |
| `agent-wallet` | Read the payment wallet for an agent |
| `agent-metadata` | Read a specific metadata key for an agent |
| `agent-reputation` | Aggregate reputation score and feedback count |
| `agent-feedback` | Submit feedback for an agent |
| `agent-reviews` | Read all feedback entries for an agent |

### DEX (Morph Only)

| Command | Description |
|---------|-------------|
| `dex-quote` | Get a swap quote (with --recipient for calldata) |
| `dex-send` | Sign and broadcast swap tx using calldata from dex-quote |

### Bridge (Cross-Chain, 6 Chains)

| Command | Description |
|---------|-------------|
| `bridge-chains` | List supported chains for cross-chain swap |
| `bridge-tokens` | List available tokens (optionally filter by chain) |
| `bridge-token-search` | Search tokens by symbol or address across chains |
| `bridge-quote` | Get cross-chain or same-chain swap quote |
| `bridge-balance` | Token balance + USD price on any supported chain |
| `bridge-login` | Sign in with EIP-191 signature, get JWT (valid 24h) |
| `bridge-make-order` | Create swap order, returns unsigned txs to sign |
| `bridge-submit-order` | Submit signed transactions for a swap order |
| `bridge-swap` | One-step cross-chain swap: create order, sign, and submit |
| `bridge-order` | Query swap order status |
| `bridge-history` | Query historical swap orders |

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
| [morph-identity](skills/morph-identity/SKILL.md) | EIP-8004 agent identity and reputation commands |
| [morph-dex](skills/morph-dex/SKILL.md) | DEX swap on Morph (quote + send) |
| [morph-bridge](skills/morph-bridge/SKILL.md) | Cross-chain swap across 6 chains (quote, order, JWT auth) |
| [morph-altfee](skills/morph-altfee/SKILL.md) | Alt-fee gas payment (0x7f tx type) |

---

## Security

- Query endpoints are public — no API keys needed
- Bridge order management uses JWT authentication (local EIP-191 signature, never sends private keys)
- No `eval()` / `exec()` or dynamic code execution
- Private keys are only used locally for transaction signing
- Send commands require explicit user confirmation (human-in-the-loop)
- No data collection, telemetry, or analytics
- Dependencies: `requests`, `eth_account`, `eth_abi`, `eth_utils` (stdlib: `json`, `argparse`, `decimal`)
- We recommend auditing the source yourself before use

## License

MIT
