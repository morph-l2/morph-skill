# Changelog

All notable changes to this project are documented in this file.

---

## [1.0.0] — 2026-03-10

### Added
- **contract-info** command: query smart contract source code, ABI, verification status, compiler version, proxy type from Blockscout
- **token-transfers** command: query recent token transfers by token symbol/address or by wallet address
- **token-info** command: token dashboard data — name, symbol, total supply, holders count, transfer count, market data
- **token-list** command: list top tracked tokens from the explorer
- IDE plugin integration: `.claude-plugin/` (Claude Code) and `.cursor-plugin/` (Cursor)
- Modular skill split: `skills/` directory with 4 independent modules (morph-wallet, morph-explorer, morph-dex, morph-altfee)
- Input validation: address format validation (`0x` + 40 hex chars) with fail-fast JSON errors on send commands and direct address parameters
- Error hardening: top-level exception handler ensures all error paths return structured JSON — no Python tracebacks
- Private key validation: `_load_account()` helper catches invalid keys before any network call

### Security Audit
- **Dependencies**: `requests`, `eth_account` — no new dependencies added
- **Endpoints**: no new external endpoints; all queries use existing Morph RPC, Blockscout Explorer API, and Bulbaswap DEX API
- **Credential handling**: unchanged — private keys used locally for signing only, never transmitted
- **Error paths**: all exceptions now produce `{"success": false, "error": "..."}` — no stack traces leak internal paths

---

## [0.3.0] — 2026-03-08

### Added
- **dex-send** command: sign and broadcast swap transactions using calldata from `dex-quote --recipient`
- **altfee-send** command: sign and broadcast transactions paying gas with alternative ERC20 tokens (tx type `0x7f`)
- Custom RLP encoder for `0x7f` transaction serialization (no external RLP library needed)
- Pure Python signing for alt-fee transactions using `eth_keys` / `eth_hash`

### Changed
- Renamed all `fee-*` commands to `altfee-*` for clarity (`fee-tokens` → `altfee-tokens`, etc.)
- Project renamed from "Morph Skills" to "Morph Skill"

### Security Audit
- **Dependencies**: no new dependencies; `0x7f` signing uses `eth_keys` and `eth_hash` (sub-dependencies of `eth_account`)
- **Endpoints**: no new external endpoints
- **Credential handling**: `altfee-send` and `dex-send` sign transactions locally, same model as `transfer`
- **Breaking change**: `fee-*` CLI names removed — use `altfee-*` instead

---

## [0.2.0] — 2026-03-07

### Added
- **altfee-tokens** command: list supported fee tokens from on-chain TokenRegistry
- **altfee-token-info** command: get fee token details (contract address, scale, feeRate, decimals, active status)
- **altfee-estimate** command: estimate feeLimit for paying gas with alternative tokens (includes 10% safety margin)
- **dex-quote** command: get swap quotes from Bulbaswap DEX aggregator with optional `--recipient` for calldata generation

### Security Audit
- **Dependencies**: unchanged (`requests`, `eth_account`)
- **Endpoints**: added Bulbaswap DEX API (`https://api.bulbaswap.io`) — public, no auth required
- **Credential handling**: no signing in this release; quote and estimate commands are read-only

---

## [0.1.0] — 2026-03-06

### Added
- Initial release
- **Wallet commands**: `create-wallet`, `balance`, `token-balance`, `transfer`, `transfer-token`, `tx-receipt`
- **Explorer commands**: `address-info`, `address-txs`, `address-tokens`, `tx-detail`, `token-search`
- Unified CLI entry point: `python3 scripts/morph_api.py <command> [options]`
- Structured JSON output for all commands (`{"success": true/false, ...}`)
- Human-readable amounts (ETH, not wei)
- SKILL.md agent reference document
- Well-known token registry (USDT)

### Security Audit
- **Dependencies**: `requests` (HTTP), `eth_account` (key generation and tx signing)
- **Endpoints**: Morph RPC (`https://rpc.morph.network/`), Blockscout Explorer API (`https://explorer-api.morph.network/api/v2`) — all public, no auth
- **Credential handling**: private keys used locally for `transfer` / `transfer-token` signing only; `create-wallet` is purely offline
- **Code safety**: no `eval()`, `exec()`, or dynamic code execution; no telemetry or data collection
