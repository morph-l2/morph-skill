# morph-skills

CLI toolkit for AI agents to interact with the **Morph Mainnet** (Chain ID: 2818).

Provides wallet management, on-chain data queries, and DEX operations through a single Python script. Designed to be consumed by AI agents via `SKILL.md`, but also works as a standalone CLI.

## Quick Start

```bash
# Install dependencies
pip install requests eth_account

# Create a wallet
python3 scripts/morph_api.py create-wallet

# Check ETH balance
python3 scripts/morph_api.py balance --address 0xYourAddress

# Look up address info on explorer
python3 scripts/morph_api.py address-info --address 0xYourAddress

# Get a DEX swap quote
python3 scripts/morph_api.py dex-quote --amount 1 --token-in ETH --token-out USDC
```

No API keys required — all Morph endpoints are public.

## Commands

### Wallet
| Command | Description |
|---------|-------------|
| `create-wallet` | Generate a new ETH key pair locally |
| `balance` | Query native ETH balance |
| `token-balance` | Query ERC20 token balance |
| `transfer` | Send ETH |
| `transfer-token` | Send ERC20 tokens |
| `tx-receipt` | Query transaction receipt |

### Explorer
| Command | Description |
|---------|-------------|
| `address-info` | Address summary from Blockscout |
| `address-txs` | Transaction history |
| `address-tokens` | Token holdings |
| `tx-detail` | Full transaction details |
| `token-search` | Search tokens by name/symbol |
| `token-list` | List all tracked tokens |

### DEX
| Command | Description |
|---------|-------------|
| `dex-quote` | Get a swap quote |
| `dex-swap` | Generate swap calldata |

Run `python3 scripts/morph_api.py <command> --help` for detailed usage.

## For AI Agents

See [SKILL.md](SKILL.md) for the full agent reference, including command examples, well-known token addresses, and safety rules.

## Requirements

- Python 3.11+
- `requests`
- `eth_account` (for wallet creation and transaction signing)

## License

MIT
