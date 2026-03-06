#!/usr/bin/env python3
"""
morph_api.py — Morph Mainnet CLI / AI-Agent Skill

Interact with Morph L2 (Chain ID 2818) via public RPC, Blockscout Explorer
API, and DEX API.  All amounts use human-readable units (ETH, not wei).
Output is always JSON for easy agent parsing.

Dependencies:
    pip install requests eth_account
"""

import argparse
import json
import sys
import requests
from decimal import Decimal

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RPC_URL = "https://rpc.morph.network/"
EXPLORER_API = "https://explorer-api.morph.network/api/v2"
DEX_API = "https://api.bulbaswap.io"
CHAIN_ID = 2818

NATIVE_TOKEN = "0x0000000000000000000000000000000000000000"

# Verified token addresses on Morph Mainnet
# Source: Bitget Wallet Skill verified stablecoin list
KNOWN_TOKENS = {
    "USDT":  "0xe7cd86e13AC4309349F30B3435a9d337750fC82D",
}

ERC20_BALANCE_OF_SIG = "0x70a08231"
ERC20_DECIMALS_SIG   = "0x313ce567"
ERC20_TRANSFER_SIG   = "0xa9059cbb"

# TokenRegistry contract (Morph pre-deploy)
TOKEN_REGISTRY = "0x5300000000000000000000000000000000000021"
TR_GET_TOKEN_LIST_SIG      = "0x1585458c"  # getSupportedTokenList()
TR_GET_TOKEN_INFO_SIG      = "0x1c58e793"  # getTokenInfo(uint16)
TR_PRICE_RATIO_SIG         = "0x19904c33"  # priceRatio(uint16)
TR_CALCULATE_AMOUNT_SIG    = "0xdddc98be"  # calculateTokenAmount(uint16,uint256)

# ---------------------------------------------------------------------------
# Helpers — output
# ---------------------------------------------------------------------------

def _ok(data):
    print(json.dumps({"success": True, "data": data}, indent=2, default=str))
    sys.exit(0)

def _err(msg):
    print(json.dumps({"success": False, "error": str(msg)}, indent=2))
    sys.exit(1)

# ---------------------------------------------------------------------------
# Helpers — RPC
# ---------------------------------------------------------------------------

_rpc_id = 0

def rpc_call(method, params=None):
    global _rpc_id
    _rpc_id += 1
    payload = {
        "jsonrpc": "2.0",
        "id": _rpc_id,
        "method": method,
        "params": params or [],
    }
    try:
        r = requests.post(RPC_URL, json=payload, timeout=30)
        r.raise_for_status()
        body = r.json()
        if "error" in body:
            _err(f"RPC error: {body['error']}")
        return body.get("result")
    except requests.RequestException as e:
        _err(f"RPC request failed: {e}")

# ---------------------------------------------------------------------------
# Helpers — Explorer (Blockscout v2)
# ---------------------------------------------------------------------------

def explorer_get(path, params=None):
    url = f"{EXPLORER_API}{path}"
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        _err(f"Explorer request failed: {e}")

# ---------------------------------------------------------------------------
# Helpers — DEX
# ---------------------------------------------------------------------------

def dex_get(path, params=None):
    url = f"{DEX_API}{path}"
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        _err(f"DEX request failed: {e}")

def dex_post(path, data=None):
    url = f"{DEX_API}{path}"
    try:
        r = requests.post(url, json=data, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        _err(f"DEX request failed: {e}")

# ---------------------------------------------------------------------------
# Helpers — Token utilities
# ---------------------------------------------------------------------------

def resolve_token(symbol_or_address):
    """Resolve a token symbol or contract address.

    - 'ETH' or '' → native token (zero address)
    - '0x...' (42 chars) → used as-is
    - known symbol (e.g. 'USDT') → looked up from verified list
    """
    if symbol_or_address == "" or symbol_or_address.upper() == "ETH":
        return NATIVE_TOKEN
    if symbol_or_address.startswith("0x") and len(symbol_or_address) == 42:
        return symbol_or_address
    upper = symbol_or_address.upper()
    if upper in KNOWN_TOKENS:
        return KNOWN_TOKENS[upper]
    _err(f"Unknown token: {symbol_or_address}. Known symbols: {', '.join(['ETH'] + list(KNOWN_TOKENS.keys()))}. Or pass a contract address (0x...).")

def get_token_decimals(token_address):
    """Query ERC20 decimals via RPC."""
    result = rpc_call("eth_call", [
        {"to": token_address, "data": ERC20_DECIMALS_SIG},
        "latest",
    ])
    if result and result != "0x":
        return int(result, 16)
    return 18  # default

def wei_to_ether(wei_hex):
    """Convert hex wei string to human-readable ETH string."""
    wei = int(wei_hex, 16)
    return str(Decimal(wei) / Decimal(10**18))

def to_wei(amount_str, decimals=18):
    """Convert human-readable amount to integer wei."""
    return int(Decimal(amount_str) * Decimal(10**decimals))

def pad_address(addr):
    """Left-pad an address to 32 bytes for ABI encoding."""
    return "0x" + addr.lower().replace("0x", "").zfill(64)

# ---------------------------------------------------------------------------
# Commands — Wallet (RPC)
# ---------------------------------------------------------------------------

def cmd_create_wallet(_args):
    """Generate a new Ethereum key pair locally."""
    try:
        from eth_account import Account
    except ImportError:
        _err("eth_account is required: pip install eth_account")
    acct = Account.create()
    _ok({
        "address": acct.address,
        "private_key": acct.key.hex(),
        "warning": "Store your private key securely. Never share it.",
    })

def cmd_balance(args):
    """Query native ETH balance."""
    result = rpc_call("eth_getBalance", [args.address, "latest"])
    _ok({
        "address": args.address,
        "balance_eth": wei_to_ether(result),
        "balance_wei": str(int(result, 16)),
    })

def cmd_token_balance(args):
    """Query ERC20 token balance."""
    token = resolve_token(args.token)
    data = ERC20_BALANCE_OF_SIG + pad_address(args.address)[2:]
    result = rpc_call("eth_call", [{"to": token, "data": data}, "latest"])
    decimals = get_token_decimals(token)
    raw = int(result, 16) if result and result != "0x" else 0
    human = str(Decimal(raw) / Decimal(10**decimals))
    _ok({
        "address": args.address,
        "token": token,
        "balance": human,
        "balance_raw": str(raw),
        "decimals": decimals,
    })

def cmd_transfer(args):
    """Sign and send an ETH transfer transaction."""
    try:
        from eth_account import Account
    except ImportError:
        _err("eth_account is required: pip install eth_account")

    acct = Account.from_key(args.private_key)
    value_wei = to_wei(args.amount)
    nonce = rpc_call("eth_getTransactionCount", [acct.address, "latest"])
    gas_price = rpc_call("eth_gasPrice", [])

    tx = {
        "chainId": CHAIN_ID,
        "nonce": int(nonce, 16),
        "to": args.to,
        "value": value_wei,
        "gas": 21000,
        "gasPrice": int(gas_price, 16),
    }
    signed = acct.sign_transaction(tx)
    tx_hash = rpc_call("eth_sendRawTransaction", [signed.raw_transaction.hex()])
    _ok({
        "tx_hash": tx_hash,
        "from": acct.address,
        "to": args.to,
        "amount_eth": args.amount,
    })

def cmd_transfer_token(args):
    """Sign and send an ERC20 transfer transaction."""
    try:
        from eth_account import Account
    except ImportError:
        _err("eth_account is required: pip install eth_account")

    token = resolve_token(args.token)
    decimals = get_token_decimals(token)
    amount_raw = to_wei(args.amount, decimals)

    acct = Account.from_key(args.private_key)
    nonce = rpc_call("eth_getTransactionCount", [acct.address, "latest"])
    gas_price = rpc_call("eth_gasPrice", [])

    # ERC20 transfer(address,uint256) calldata
    calldata = (
        ERC20_TRANSFER_SIG
        + pad_address(args.to)[2:]
        + hex(amount_raw)[2:].zfill(64)
    )

    # Estimate gas
    gas_est = rpc_call("eth_estimateGas", [{
        "from": acct.address,
        "to": token,
        "data": calldata,
    }])

    tx = {
        "chainId": CHAIN_ID,
        "nonce": int(nonce, 16),
        "to": token,
        "value": 0,
        "gas": int(gas_est, 16),
        "gasPrice": int(gas_price, 16),
        "data": calldata,
    }
    signed = acct.sign_transaction(tx)
    tx_hash = rpc_call("eth_sendRawTransaction", [signed.raw_transaction.hex()])
    _ok({
        "tx_hash": tx_hash,
        "from": acct.address,
        "to": args.to,
        "token": token,
        "amount": args.amount,
    })

def cmd_tx_receipt(args):
    """Query transaction receipt."""
    result = rpc_call("eth_getTransactionReceipt", [args.hash])
    if result is None:
        _err("Transaction not found or still pending")
    _ok(result)

# ---------------------------------------------------------------------------
# Commands — Explorer (Blockscout)
# ---------------------------------------------------------------------------

def cmd_address_info(args):
    """Get address summary from Blockscout."""
    data = explorer_get(f"/addresses/{args.address}")
    _ok(data)

def cmd_address_txs(args):
    """List transactions for an address."""
    params = {}
    if args.limit:
        params["limit"] = args.limit
    data = explorer_get(f"/addresses/{args.address}/transactions", params)
    _ok(data)

def cmd_address_tokens(args):
    """List token holdings for an address."""
    data = explorer_get(f"/addresses/{args.address}/token-balances")
    _ok(data)

def cmd_tx_detail(args):
    """Get full transaction details from Blockscout."""
    data = explorer_get(f"/transactions/{args.hash}")
    _ok(data)

def cmd_token_search(args):
    """Search tokens by name or symbol."""
    data = explorer_get("/tokens", {"q": args.query})
    _ok(data)

def cmd_token_list(_args):
    """List tokens tracked by the explorer."""
    data = explorer_get("/tokens")
    _ok(data)

# ---------------------------------------------------------------------------
# Commands — DEX
# ---------------------------------------------------------------------------

def cmd_dex_quote(args):
    """Get a swap quote from the DEX aggregator."""
    token_in = resolve_token(args.token_in)
    token_out = resolve_token(args.token_out)
    decimals_in = 18 if token_in == NATIVE_TOKEN else get_token_decimals(token_in)
    params = {
        "fromTokenAddress": token_in,
        "toTokenAddress": token_out,
        "amount": str(to_wei(args.amount, decimals_in)),
        "slippage": args.slippage or "1",
    }
    data = dex_get("/swap/v1/quote", params)
    _ok(data)

def cmd_dex_swap(args):
    """Generate swap calldata from the DEX aggregator."""
    token_in = resolve_token(args.token_in)
    token_out = resolve_token(args.token_out)
    decimals_in = 18 if token_in == NATIVE_TOKEN else get_token_decimals(token_in)
    params = {
        "fromTokenAddress": token_in,
        "toTokenAddress": token_out,
        "amount": str(to_wei(args.amount, decimals_in)),
        "slippage": args.slippage or "1",
        "userAddr": args.recipient,
    }
    data = dex_get("/swap/v1/swap", params)
    _ok(data)

# ---------------------------------------------------------------------------
# Commands — Alt-Fee (pay gas with alternative tokens)
# ---------------------------------------------------------------------------

def _decode_uint256(hex_str):
    """Decode a single uint256 from hex."""
    return int(hex_str, 16)

def cmd_fee_tokens(_args):
    """List supported fee tokens from TokenRegistry."""
    result = rpc_call("eth_call", [
        {"to": TOKEN_REGISTRY, "data": TR_GET_TOKEN_LIST_SIG},
        "latest",
    ])
    if not result or result == "0x":
        _ok({"tokens": []})
        return

    # Decode ABI: returns tuple[] of (uint16 tokenID, address tokenAddress)
    # ABI encoding: offset(32) + length(32) + N * (uint16_padded(32) + address_padded(32))
    raw = result[2:]  # strip 0x
    offset = int(raw[0:64], 16) * 2  # byte offset to data, convert to hex chars
    count = int(raw[offset:offset+64], 16)
    tokens = []
    data_start = offset + 64
    for i in range(count):
        # Each tuple is encoded inline: 2 * 32 bytes = 128 hex chars
        chunk_start = data_start + i * 128
        token_id = int(raw[chunk_start:chunk_start+64], 16)
        token_addr = "0x" + raw[chunk_start+64+24:chunk_start+128]  # last 20 bytes of 32-byte word
        tokens.append({
            "token_id": token_id,
            "address": token_addr,
        })
    _ok({"tokens": tokens})

def cmd_fee_token_info(args):
    """Get fee token details: scale, feeRate, decimals, isActive."""
    token_id = args.id
    id_hex = hex(token_id)[2:].zfill(64)

    # getTokenInfo(uint16)
    info_result = rpc_call("eth_call", [
        {"to": TOKEN_REGISTRY, "data": TR_GET_TOKEN_INFO_SIG + id_hex},
        "latest",
    ])
    # priceRatio(uint16)
    ratio_result = rpc_call("eth_call", [
        {"to": TOKEN_REGISTRY, "data": TR_PRICE_RATIO_SIG + id_hex},
        "latest",
    ])

    if not info_result or info_result == "0x":
        _err(f"Token ID {token_id} not found in registry")

    raw = info_result[2:]
    # getTokenInfo returns: (TokenInfo struct, bool hasBalanceSlot)
    # TokenInfo: address tokenAddress, bytes32 balanceSlot, bool isActive, uint8 decimals, uint256 scale
    # Encoded as 5 words for struct + 1 word for hasBalanceSlot = 6 * 64 hex chars
    token_addr = "0x" + raw[24:64]  # address (last 20 bytes of word 0)
    # word 1 = balanceSlot (skip)
    is_active = int(raw[128:192], 16) != 0  # word 2
    decimals = int(raw[192:256], 16)  # word 3
    scale = int(raw[256:320], 16)  # word 4

    fee_rate = int(ratio_result, 16) if ratio_result and ratio_result != "0x" else 0

    _ok({
        "token_id": token_id,
        "address": token_addr,
        "is_active": is_active,
        "decimals": decimals,
        "scale": str(scale),
        "fee_rate": str(fee_rate),
    })

def cmd_fee_estimate(args):
    """Estimate the minimum feeLimit to pay gas with an alternative token.

    Formula: feeLimit >= (gasFeeCap * gasLimit + L1DataFee) * tokenScale / feeRate
    """
    token_id = args.id
    gas_limit = args.gas_limit
    id_hex = hex(token_id)[2:].zfill(64)

    # Get tokenScale from getTokenInfo
    info_result = rpc_call("eth_call", [
        {"to": TOKEN_REGISTRY, "data": TR_GET_TOKEN_INFO_SIG + id_hex},
        "latest",
    ])
    if not info_result or info_result == "0x":
        _err(f"Token ID {token_id} not found in registry")

    raw = info_result[2:]
    decimals = int(raw[192:256], 16)
    scale = int(raw[256:320], 16)

    # Get feeRate from priceRatio
    ratio_result = rpc_call("eth_call", [
        {"to": TOKEN_REGISTRY, "data": TR_PRICE_RATIO_SIG + id_hex},
        "latest",
    ])
    fee_rate = int(ratio_result, 16) if ratio_result and ratio_result != "0x" else 0
    if fee_rate == 0:
        _err(f"Token ID {token_id} has zero fee rate")

    # Get current gas price as gasFeeCap
    gas_price_hex = rpc_call("eth_gasPrice", [])
    gas_fee_cap = int(gas_price_hex, 16)

    # Estimate L1 data fee (use 0 as conservative lower bound; actual L1 fee depends on tx data)
    l1_data_fee = 0

    # Calculate: feeLimit >= (gasFeeCap * gasLimit + L1DataFee) * tokenScale / feeRate
    total_fee_wei = gas_fee_cap * gas_limit + l1_data_fee
    numerator = total_fee_wei * scale
    fee_limit = (numerator + fee_rate - 1) // fee_rate  # ceiling division

    # Add 10% safety margin
    fee_limit_safe = fee_limit * 110 // 100

    human = str(Decimal(fee_limit_safe) / Decimal(10**decimals))

    _ok({
        "token_id": token_id,
        "gas_limit": gas_limit,
        "gas_fee_cap_wei": str(gas_fee_cap),
        "token_scale": str(scale),
        "fee_rate": str(fee_rate),
        "fee_limit_min": str(fee_limit),
        "fee_limit_recommended": str(fee_limit_safe),
        "fee_limit_human": human,
        "decimals": decimals,
        "note": "Recommended feeLimit includes 10% safety margin. L1 data fee not included; actual cost may be slightly higher.",
    })

# ---------------------------------------------------------------------------
# CLI — argparse
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="morph_api",
        description="Morph Mainnet CLI — wallet, explorer & DEX operations",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # -- Wallet ---------------------------------------------------------------
    sub.add_parser("create-wallet", help="Generate a new ETH key pair locally")

    p = sub.add_parser("balance", help="Query native ETH balance")
    p.add_argument("--address", required=True, help="Wallet address")

    p = sub.add_parser("token-balance", help="Query ERC20 token balance")
    p.add_argument("--address", required=True, help="Wallet address")
    p.add_argument("--token", required=True, help="Token symbol (e.g. USDT) or contract address")

    p = sub.add_parser("transfer", help="Send ETH to an address")
    p.add_argument("--to", required=True, help="Recipient address")
    p.add_argument("--amount", required=True, help="Amount in ETH (e.g. 0.1)")
    p.add_argument("--private-key", required=True, help="Sender private key")

    p = sub.add_parser("transfer-token", help="Send ERC20 tokens to an address")
    p.add_argument("--token", required=True, help="Token symbol (e.g. USDT) or contract address")
    p.add_argument("--to", required=True, help="Recipient address")
    p.add_argument("--amount", required=True, help="Amount in token units (e.g. 10.5)")
    p.add_argument("--private-key", required=True, help="Sender private key")

    p = sub.add_parser("tx-receipt", help="Query transaction receipt")
    p.add_argument("--hash", required=True, help="Transaction hash")

    # -- Explorer -------------------------------------------------------------
    p = sub.add_parser("address-info", help="Address summary from explorer")
    p.add_argument("--address", required=True, help="Wallet address")

    p = sub.add_parser("address-txs", help="List transactions for an address")
    p.add_argument("--address", required=True, help="Wallet address")
    p.add_argument("--limit", type=int, default=None, help="Max results (optional)")

    p = sub.add_parser("address-tokens", help="Token holdings for an address")
    p.add_argument("--address", required=True, help="Wallet address")

    p = sub.add_parser("tx-detail", help="Transaction details from explorer")
    p.add_argument("--hash", required=True, help="Transaction hash")

    p = sub.add_parser("token-search", help="Search tokens by name or symbol")
    p.add_argument("--query", required=True, help="Search query")

    sub.add_parser("token-list", help="List tokens tracked by the explorer")

    # -- DEX ------------------------------------------------------------------
    p = sub.add_parser("dex-quote", help="Get a swap quote")
    p.add_argument("--amount", required=True, help="Amount to swap (human-readable)")
    p.add_argument("--token-in", required=True, help="Source token symbol or address (ETH for native)")
    p.add_argument("--token-out", required=True, help="Destination token symbol or address")
    p.add_argument("--slippage", default="1", help="Slippage tolerance %% (default: 1)")

    p = sub.add_parser("dex-swap", help="Generate swap calldata")
    p.add_argument("--amount", required=True, help="Amount to swap (human-readable)")
    p.add_argument("--token-in", required=True, help="Source token symbol or address (ETH for native)")
    p.add_argument("--token-out", required=True, help="Destination token symbol or address")
    p.add_argument("--recipient", required=True, help="Recipient address")
    p.add_argument("--slippage", default="1", help="Slippage tolerance %% (default: 1)")

    # -- Alt-Fee --------------------------------------------------------------
    sub.add_parser("fee-tokens", help="List supported fee tokens from TokenRegistry")

    p = sub.add_parser("fee-token-info", help="Get fee token details (scale, feeRate, etc.)")
    p.add_argument("--id", type=int, required=True, help="Fee token ID (1-5)")

    p = sub.add_parser("fee-estimate", help="Estimate feeLimit for paying gas with alt token")
    p.add_argument("--id", type=int, required=True, help="Fee token ID (1-5)")
    p.add_argument("--gas-limit", type=int, default=21000, help="Gas limit (default: 21000)")

    return parser

COMMAND_MAP = {
    "create-wallet":  cmd_create_wallet,
    "balance":        cmd_balance,
    "token-balance":  cmd_token_balance,
    "transfer":       cmd_transfer,
    "transfer-token": cmd_transfer_token,
    "tx-receipt":     cmd_tx_receipt,
    "address-info":   cmd_address_info,
    "address-txs":    cmd_address_txs,
    "address-tokens": cmd_address_tokens,
    "tx-detail":      cmd_tx_detail,
    "token-search":   cmd_token_search,
    "token-list":     cmd_token_list,
    "dex-quote":      cmd_dex_quote,
    "dex-swap":       cmd_dex_swap,
    "fee-tokens":     cmd_fee_tokens,
    "fee-token-info": cmd_fee_token_info,
    "fee-estimate":   cmd_fee_estimate,
}

def main():
    parser = build_parser()
    args = parser.parse_args()
    handler = COMMAND_MAP.get(args.command)
    if handler is None:
        _err(f"Unknown command: {args.command}")
    handler(args)

if __name__ == "__main__":
    main()
