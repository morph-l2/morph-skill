# Morph Skill

## Overview

An AI Agent skill for interacting with the [Morph](https://morph.network/) L2 blockchain, enabling natural-language-driven wallet operations, on-chain data queries, DEX swaps, cross-chain bridge swaps, EIP-7702 EOA delegation, and x402 HTTP payment protocol.

## Role Boundary

This repository is the **Morph protocol and business layer** for AI agents. It owns Morph-native workflows such as:

- wallet RPC operations
- explorer queries
- DEX and bridge flows
- altfee gas payment
- EIP-8004 identity and reputation
- EIP-7702 EOA delegation and atomic batch calls
- x402 HTTP payment protocol (pay and receive USDC)

BGW should be treated as the separate **wallet product and signing layer**. BGW owns:

- Social Login Wallet (TEE-backed signing — private key never leaves Bitget's TEE)
- swap execution across chains including Morph (with TEE signing for Social Login Wallet users)
- token discovery, market data, and security audits

> **Note:** Social Login Wallet onboarding (email/Google/Apple login) happens in the Bitget Wallet APP, not through skill commands. See [docs/social-wallet-integration.md](docs/social-wallet-integration.md) for setup details.

This repository does **not** implement BGW login, Social Login Wallet session handling, or BGW runtime integration. If an agent is expected to help with both Morph protocol actions and Social Login Wallet flows, it should load **both** the Morph skill pack and the BGW skill pack up front.

For the combined model, see [docs/social-wallet-integration.md](docs/social-wallet-integration.md).

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
| **Agent Set Metadata** | Set a metadata key-value pair for an agent | "Update the role metadata for agent 12" |
| **Agent Set URI** | Set or update the agent URI | "Update the URI for agent 12" |
| **Agent Set Wallet** | Bind an operational wallet to an agent | "Bind wallet 0x... to agent 12" |
| **Agent Unset Wallet** | Unbind the operational wallet from an agent | "Remove the wallet binding from agent 12" |
| **Agent Revoke Feedback** | Revoke previously submitted feedback | "Retract my review for agent 12" |
| **Agent Append Response** | Append an owner response to a feedback entry | "Reply to the feedback on agent 12" |
| **Token Transfers** | Recent transfer history for a token or address | "Show recent USDT transfers" |
| **Token Info** | Token details: supply, holders, transfers | "How many holders does USDT have?" |
| **DEX Quote** | Best-route swap quote + calldata (Morph only) | "How much USDT for 1 ETH?" |
| **DEX Send** | Sign and broadcast swap transaction (Morph only) | Complete the swap on-chain |
| **DEX Approve** | Approve ERC-20 spending by a DEX router | "Approve USDT for the router" |
| **DEX Allowance** | Check ERC-20 allowance for a spender | "How much USDT can the router spend?" |
| **Bridge Quote** | Cross-chain swap quote across 6 chains | "How much to bridge USDC from Base to Morph?" |
| **Bridge Swap** | One-step cross-chain swap: create, sign, and submit | "Bridge 10 USDT from Morph to Base" |
| **Bridge Order** | Track cross-chain swap order status | "Check my bridge order status" |
| **Bridge Balance** | Token balance + USD price on any supported chain | "What's my USDC balance on Base?" |
| **Alt-Fee Tokens** | List supported alt-fee tokens | "What tokens can I use to pay gas?" |
| **Alt-Fee Token Info** | Fee token details (scale, rate) | "Get info for fee token 5" |
| **Alt-Fee Estimate** | Estimate gas cost in alt token | "How much USDT to cover gas?" |
| **Alt-Fee Send** | Send tx paying gas with alt token | "Transfer ETH, pay gas with USDT" |
| **7702 Delegate** | Check EOA delegation status | "Is this address delegated?" |
| **7702 Authorize** | Sign offline authorization | "Sign a 7702 authorization" |
| **7702 Send** | Single call via EIP-7702 delegation | "Send a delegated call" |
| **7702 Batch** | Atomic multi-call via SimpleDelegation | "Approve + swap in one tx" |
| **7702 Revoke** | Revoke EOA delegation | "Clear the delegation" |
| **x402 Supported** | Query Facilitator supported schemes | "What x402 payment methods are available?" |
| **x402 Discover** | Probe URL for payment requirements | "Does this API require payment?" |
| **x402 Pay** | Pay for x402-protected resource with USDC | "Pay and access this API" |
| **x402 Register** | Get merchant HMAC credentials | "Register as x402 merchant" |
| **x402 Verify** | Verify a received payment signature | "Is this payment valid?" |
| **x402 Settle** | Settle payment on-chain (USDC transfer) | "Settle the payment" |
| **x402 Server** | Start local x402 merchant test server | "Run a paid API endpoint" |

> **Amounts are human-readable** — pass `0.1` for 0.1 ETH, NOT `100000000000000000` wei.

### Data Sources

Query endpoints are public — **no API keys required**. Bridge order management requires JWT authentication via `bridge-login`.

| Source | Base URL | Auth |
|--------|----------|------|
| Morph RPC | `https://rpc.morph.network/` | None |
| Explorer API (Blockscout) | `https://explorer-api.morph.network/api/v2` | None |
| DEX / Bridge API | `https://api.bulbaswap.io` | None (queries) / JWT (orders) |
| x402 Facilitator | `https://morph-rails.morph.network/x402` | None (discover) / HMAC (verify, settle) |
| Bundled ABIs | `contracts/IdentityRegistry.json`, `contracts/ReputationRegistry.json` | Local files |

Default EIP-8004 contracts on Morph mainnet:
- `IdentityRegistry`: `0x8004A169FB4a3325136EB29fA0ceB6D2e539a432`
- `ReputationRegistry`: `0x8004BAa17C55a88189AE136b182e5fdA19dE9b63`

---

## Architecture

```
Natural Language Input
    ↓
AI Agent (Claude Code / Cursor / OpenClaw / Custom)
    ↓  ← loads skill from skills/ (wallet, explorer, agent, dex, bridge, altfee, 7702, x402)
morph_api.py (Python 3.9+)
    ↓  ← No API keys for queries; JWT for bridge orders
Direct RPC / Explorer / DEX / Bridge API calls
    ↓
Structured JSON → Agent interprets → Natural language response
```

### Architecture Boundary

- Morph Skill decides Morph-specific business logic, protocol rules, and chain operations.
- BGW should decide wallet-product concerns such as Social Login Wallet setup, TEE signing, and swap execution.
- Combined workflows should be orchestrated by the agent across both skill packs rather than by duplicating BGW logic inside `morph_api.py`.

**Security by Design:**
- No API keys required for queries — all Morph RPC, Explorer, and DEX quote endpoints are public
- Bridge order management uses JWT authentication (obtained via local EIP-191 wallet signature, valid 24h)
- Send commands (`transfer`, `transfer-token`, `dex-send`, `altfee-send`, `bridge-make-order`, `bridge-submit-order`, `bridge-swap`, `7702-send`, `7702-batch`, `7702-revoke`, `x402-pay`, `x402-settle`) only sign and broadcast; **the agent must confirm with the user before executing**
- Agent write commands (`agent-register`, `agent-feedback`) also sign locally and should be confirmed before execution
- Private keys are used locally for signing only — never sent to any API
- `create-wallet` is purely offline — no network call
- ERC-8004 ABI files are bundled under `contracts/`, so the skill does not depend on the workspace root layout

---

## Using Morph With BGW

Use Morph and BGW together when the user wants Morph chain actions from a BGW-backed wallet.

- BGW establishes the Social Login Wallet context (address, walletId).
- Morph handles Morph-specific reads, business rules, and protocol queries.
- This repository does not shell out to BGW scripts or manage BGW sessions directly.

Typical combined examples:

- Use BGW to obtain the wallet address, then use Morph `balance`, `token-balance`, or `address-tokens`.
- Use Morph `dex-quote` or `bridge-quote` for price comparison, then use BGW's swap flow for execution with a Social Login Wallet.
- Use Morph alone when the user explicitly wants local private-key control and direct self-custody flows.

Current execution note:

- Morph write commands require `--private-key` for local signing.
- Social Login Wallet users should use BGW's swap flow for writes on Morph — see [docs/social-wallet-integration.md](docs/social-wallet-integration.md).
- BGW is documented here as a companion wallet layer and routing target, not as an execution path wired into `morph_api.py`.

Start with the routing guide here: [docs/social-wallet-integration.md](docs/social-wallet-integration.md).

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

### 5. Agent Monetization
> "Register my agent and set up payment collection"

- `agent-register` → get on-chain identity (ERC-721 NFT)
- `x402-register --save` → bind agent wallet as x402 payment recipient
- `x402-server` → expose a local paid HTTP endpoint
- Other agents use `x402-pay` to access and pay USDC automatically
- For: builders of paid AI services, Agent Economy participants

---

## Quick Start

### Installation

```bash
git clone https://github.com/morph-l2/morph-skill.git
cd morph-skill
pip install requests eth_account eth_abi eth_utils
```

That's it — no API keys needed for queries. Bridge orders require JWT via `bridge-login`. Python 3.9+ required.

If you expect the agent to support Social Login Wallet flows as well, load the BGW companion skills too:

- [bitget-wallet-skill](https://github.com/bitget-wallet-ai-lab/bitget-wallet-skill)

### Hoodi Testnet Overrides

To test the EIP-8004 agent commands on Morph Hoodi, override the network and registry addresses:

```bash
export MORPH_RPC_URL="https://rpc-hoodi.morph.network"
export MORPH_CHAIN_ID=2910
export MORPH_IDENTITY_REGISTRY="0x8004A818BFB912233c491871b3d84c89A494BD9e"
export MORPH_REPUTATION_REGISTRY="0x8004B663056A597Dffe9eCcC1965A193B7388713"
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

# Register an agent with altfee gas payment
python3 scripts/morph_api.py agent-register --name "MorphBot" --fee-token-id 5 --private-key 0xYourKey

# Read agent reputation
python3 scripts/morph_api.py agent-reputation --agent-id <agent_id>

# Submit agent feedback
python3 scripts/morph_api.py agent-feedback --agent-id <agent_id> --value 4.5 --tag1 quality --feedback-uri "https://example.com/review/1" --private-key 0xYourKey

# Submit feedback with altfee gas payment
python3 scripts/morph_api.py agent-feedback --agent-id <agent_id> --value 4.5 --fee-token-id 5 --private-key 0xYourKey

# Check ERC-20 allowance before swapping
python3 scripts/morph_api.py dex-allowance --token USDT --owner 0xYourAddress --spender 0xRouterAddr

# Approve USDT for DEX router
python3 scripts/morph_api.py dex-approve --token USDT --spender 0xRouterAddr --amount 1000 --private-key 0xYourKey

# Set metadata on an agent
python3 scripts/morph_api.py agent-set-metadata --agent-id 42 --key "role" --value "assistant" --private-key 0xYourKey

# Bind an operational wallet to an agent (EIP-712; the new wallet signs `AgentWalletSet(agentId,newWallet,owner,deadline)` and the deadline must stay within 5 minutes)
python3 scripts/morph_api.py agent-set-wallet --agent-id 42 --new-wallet-key 0xNewKey --private-key 0xOwnerKey

# DEX swap quote (1 ETH → USDT)
python3 scripts/morph_api.py dex-quote --amount 1 --token-in ETH --token-out USDT

# Send ETH
python3 scripts/morph_api.py transfer --to 0xRecipient --amount 0.01 --private-key 0xYourKey

# List fee tokens (alt-fee: pay gas with non-ETH tokens)
python3 scripts/morph_api.py altfee-tokens

# Estimate gas cost in USDT (fee token ID 5)
python3 scripts/morph_api.py altfee-estimate --id 5 --gas-limit 21000

# Check EIP-7702 delegation status
python3 scripts/morph_api.py 7702-delegate --address 0xYourAddress

# Atomic approve + swap in one transaction via 7702
python3 scripts/morph_api.py 7702-batch --delegate 0xDelegateContract --calls '[{"to":"0xToken","value":"0","data":"0xApproveData"},{"to":"0xRouter","value":"0","data":"0xSwapData"}]' --private-key 0xYourKey

# Check if a URL requires x402 payment
python3 scripts/morph_api.py x402-discover --url https://api.example.com/resource

# Pay for an x402-protected resource
python3 scripts/morph_api.py x402-pay --url https://api.example.com/resource --private-key 0xYourKey

# Start a local x402 merchant test server
python3 scripts/morph_api.py x402-server --pay-to 0xYourAddress --price 0.001 --dev
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
| `agent-register` | Register an agent identity with optional URI and metadata; supports optional altfee gas payment |
| `agent-wallet` | Read the payment wallet for an agent |
| `agent-metadata` | Read a specific metadata key for an agent |
| `agent-reputation` | Aggregate reputation score and feedback count |
| `agent-feedback` | Submit feedback for an agent; supports optional altfee gas payment |
| `agent-reviews` | Read all feedback entries for an agent |
| `agent-set-metadata` | Set a metadata key-value pair for an agent |
| `agent-set-uri` | Set or update the agent URI |
| `agent-set-wallet` | Bind an operational wallet to an agent (EIP-712 `AgentWalletSet`; 5 minute deadline window) |
| `agent-unset-wallet` | Unbind the operational wallet from an agent |
| `agent-revoke-feedback` | Revoke previously submitted feedback |
| `agent-append-response` | Append an owner response to a feedback entry |

### DEX (Morph Only)

| Command | Description |
|---------|-------------|
| `dex-quote` | Get a swap quote (with --recipient for calldata) |
| `dex-send` | Sign and broadcast swap tx using calldata from dex-quote |
| `dex-approve` | Approve an ERC-20 token for spending by a DEX router |
| `dex-allowance` | Check the ERC-20 allowance granted to a spender |

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

### EIP-7702 (EOA Delegation)

| Command | Description |
|---------|-------------|
| `7702-delegate` | Check if an EOA has a 7702 delegation |
| `7702-authorize` | Sign a 7702 authorization offline for a supplied delegate contract (no tx sent) |
| `7702-send` | Execute a single delegated call via EIP-7702 (0x04) |
| `7702-batch` | Atomically execute multiple calls via a supplied delegate contract |
| `7702-revoke` | Revoke EIP-7702 delegation (authorize address(0)) |

### x402 (HTTP Payment Protocol)

| Command | Description |
|---------|-------------|
| `x402-supported` | Query Facilitator for supported payment schemes |
| `x402-discover` | Probe a URL for x402 payment requirements (no payment) |
| `x402-pay` | Pay for an x402-protected resource with USDC |
| `x402-register` | Register with Facilitator to get merchant HMAC credentials |
| `x402-verify` | Verify a received payment signature (merchant) |
| `x402-settle` | Settle a payment on-chain — USDC transfer (merchant) |
| `x402-server` | Start a local x402 merchant test server |

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
| [morph-7702](skills/morph-7702/SKILL.md) | EIP-7702 EOA delegation and batch calls (0x04 tx type) |
| [morph-x402](skills/morph-x402/SKILL.md) | x402 HTTP payment protocol (pay and receive USDC) |

---

## Security

- Query endpoints are public — no API keys needed
- Bridge order management uses JWT authentication (local EIP-191 signature, never sends private keys)
- No `eval()` / `exec()` or dynamic code execution
- Private keys are only used locally for transaction signing
- Send commands require explicit user confirmation (human-in-the-loop)
- No data collection, telemetry, or analytics
- x402 merchant credentials (HMAC secret key) stored with AES-256-GCM encryption at `~/.morph-agent/x402-credentials/`
- Dependencies: `requests`, `eth_account`, `eth_abi`, `eth_utils` (stdlib: `json`, `argparse`, `decimal`)
- We recommend auditing the source yourself before use

## License

MIT
