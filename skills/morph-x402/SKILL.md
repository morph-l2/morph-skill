---
name: morph-x402
version: 1.0.0
description: x402 HTTP payment protocol on Morph L2 — pay for and receive USDC payments for API resources
---

# Morph x402 — AI Agent Skill

> HTTP 402 payment protocol on **Morph Mainnet** (Chain ID: 2818).
> Agents can pay for protected resources with USDC (client) and receive payments for services they expose (merchant).
> All commands output JSON.

## Activation Triggers

Use this skill when the user wants to: check x402 support, discover payment requirements for a URL, pay for an x402-protected resource, register as a merchant to receive payments, verify a payment signature, or settle a payment on-chain.

## BGW Routing Note

Decide the mode once via the root [SKILL.md](../../SKILL.md) and [docs/social-wallet-integration.md](../../docs/social-wallet-integration.md).

- `x402-pay` and `x402-register` require `--private-key` for local signing.
- `x402-discover`, `x402-supported`, `x402-verify`, `x402-settle`, `x402-server` do NOT require a private key — they work with any wallet type.
- Social Login Wallet users can still participate in x402 by combining Morph reads with BGW signing:

### Social Login Wallet + x402 (Agent orchestration pattern)

**Paying for a resource (SLW payer):**
```
1. Morph: x402-discover --url <url>          → get payment requirements (amount, payTo, asset)
2. BGW:   sign EIP-3009 TransferWithAuthorization using TEE
           (pass the requirements from step 1 to BGW's signing flow)
3. Agent: construct PAYMENT-SIGNATURE header from the BGW signature
4. Agent: replay GET <url> with the header    → receive paid content
```

**Receiving payments (SLW merchant):**
```
1. BGW:   resolve wallet address
2. Morph: x402-register --private-key <local-key> --save --name <name>
          (Note: registration requires a local key for EIP-191 signing.
           If the agent only has a SLW, use BGW to sign the registration challenge,
           then pass the JWT to Morph for API key creation — or use a separate local key.)
3. Morph: x402-server / x402-verify / x402-settle work with HMAC credentials only — no private key needed
```

The key insight: **only the signing step needs BGW**. All other x402 operations (discover, verify, settle, server) work without a private key.

---

## Quick Start

```bash
pip install requests eth_account eth_abi eth_utils

# Run from repository root
python3 scripts/morph_api.py <command> [options]
```

No API keys required for client-side commands. Merchant-side commands require HMAC credentials from `x402-register`.

---

## Commands

### Client (Payer) Side

#### `x402-supported`
Query the Morph Facilitator for supported payment schemes and networks.
```bash
python3 scripts/morph_api.py x402-supported
```

#### `x402-discover`
Probe a URL to check if it requires x402 payment. Does not pay.
```bash
python3 scripts/morph_api.py x402-discover --url https://api.example.com/resource
```

#### `x402-pay`
Pay for an x402-protected resource with USDC. Default max payment: 1.0 USDC.
```bash
python3 scripts/morph_api.py x402-pay --url https://api.example.com/resource --private-key 0xKey

# Allow higher payments
python3 scripts/morph_api.py x402-pay --url https://api.example.com/resource --private-key 0xKey --max-payment 5.0
```

### Merchant (Receiver) Side

#### `x402-register`
Register a wallet with the Facilitator to get HMAC credentials for merchant operations.
```bash
# Register and save credentials locally (encrypted)
python3 scripts/morph_api.py x402-register --private-key 0xKey --save --name myagent

# Register without saving (prints keys once)
python3 scripts/morph_api.py x402-register --private-key 0xKey
```

#### `x402-verify`
Verify a payment signature received from a payer. No on-chain action.
```bash
python3 scripts/morph_api.py x402-verify --payload '{"x402Version":2,...}' --requirements '{"scheme":"exact",...}' --name myagent
```

#### `x402-settle`
Settle a verified payment on-chain (triggers USDC transfer from payer to merchant).
```bash
python3 scripts/morph_api.py x402-settle --payload '...' --requirements '...' --name myagent
```

#### `x402-server`
Start a local HTTP server with x402 payment protection. Supports dev mode (structural check, no real payments) and verified mode (Facilitator verify + settle).
```bash
# Dev mode (no HMAC credentials needed, structural check only)
python3 scripts/morph_api.py x402-server --pay-to 0xWalletAddr --price 0.001 --dev

# Verified mode (requires saved credentials)
python3 scripts/morph_api.py x402-server --pay-to 0xWalletAddr --price 0.001 --name myagent

# Custom port and path
python3 scripts/morph_api.py x402-server --pay-to 0xAddr --price 0.01 --port 9000 --path /api/data --name myagent
```

Endpoints served: `/api/free` (free, 200), `<paid-path>` (402 → verify payment → 200).

---

## Safety Rules

1. **`x402-pay` enforces `--max-payment`** (default 1.0 USDC). Amounts exceeding the limit are rejected before signing.
2. **Always confirm with the user before executing `x402-pay`** — show the amount, recipient, and URL.
3. `x402-register` only shows `secretKey` on first creation. If `--save` is not used, the key is lost.
4. Private keys are used locally for signing only — never sent to any API.
5. EIP-7702 delegated EOAs using legacy SimpleDelegation may fail during x402 settlement — the USDC contract checks `isValidSignature` for delegated accounts.

## Domain Knowledge

- **x402 v2 protocol**: Coinbase open standard for HTTP 402 payment. Payer signs EIP-3009 TransferWithAuthorization, merchant verifies and settles via Facilitator.
- **Payment token**: USDC on Morph (`0xCfb1186F4e93D60E60a8bDd997427D1F33bc372B`, 6 decimals, FiatTokenV2.2)
- **Facilitator**: `https://morph-rails.morph.network/x402` — verifies signatures and settles on-chain
- **EIP-3009**: gasless USDC transfer authorization. Payer signs; Facilitator calls `receiveWithAuthorization` on USDC contract.
- **HMAC-SHA256**: merchant authenticates to Facilitator using `MORPH-ACCESS-KEY` / `MORPH-ACCESS-SIGN` / `MORPH-ACCESS-TIMESTAMP` headers
- **Credential storage**: HMAC credentials encrypted with AES-256-GCM at `~/.morph-agent/x402-credentials/`

## Common Workflows

**Agent pays for a premium API:**
```
x402-discover --url <url> (check price) → x402-pay --url <url> (sign and access)
```

**Agent monetizes its service (full flow):**
```
agent-register (morph-identity, get agent NFT)
  → x402-register --save --name myagent (get HMAC credentials, agentWallet = payTo)
  → x402-server --pay-to 0xWallet --price 0.001 --name myagent (expose paid HTTP endpoint)
  → other agents call: x402-discover → x402-pay (USDC auto-settles on-chain)
```

**Quick local test (dev mode, no real payments):**
```
x402-server --pay-to 0xAddr --price 0.001 --dev
  → x402-discover --url http://localhost:8402/api/resource
  → x402-pay --url http://localhost:8402/api/resource --private-key 0xTestKey
```

## Cross-Skill Integration

- **morph-identity (EIP-8004)**: `agent-register` creates the agent identity; `x402-register` turns its wallet into a payment recipient. Together they enable agent monetization.
- **morph-wallet**: Use `token-balance --token USDC` to check USDC balance before paying.
- **morph-7702**: EIP-7702 delegated EOAs using legacy SimpleDelegation may cause x402 settlement failures. Check with `7702-delegate` first.
