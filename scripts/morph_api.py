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

def dex_expect_success(data):
    """Fail fast when DEX API returns business error code with HTTP 200."""
    if isinstance(data, dict) and "code" in data and data.get("code") != 0:
        _err(f"DEX API error {data.get('code')}: {data.get('msg')}")

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

def resolve_erc20_token(symbol_or_address):
    """Resolve token and reject native ETH for ERC20-only commands."""
    token = resolve_token(symbol_or_address)
    if token == NATIVE_TOKEN:
        _err("ETH is a native token, not ERC20. Use `balance`/`transfer` for ETH, or pass an ERC20 token address/symbol.")
    return token

def token_for_dex(token_address):
    """Bulbaswap v2 uses literal ETH for native token, not zero-address."""
    return "ETH" if token_address == NATIVE_TOKEN else token_address

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
    token = resolve_erc20_token(args.token)
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

    token = resolve_erc20_token(args.token)
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
    """List top tracked tokens from the explorer (single page)."""
    data = explorer_get("/tokens")
    _ok(data)

# ---------------------------------------------------------------------------
# Commands — DEX
# ---------------------------------------------------------------------------

def cmd_dex_quote(args):
    """Get a swap quote from the DEX aggregator."""
    token_in = token_for_dex(resolve_token(args.token_in))
    token_out = token_for_dex(resolve_token(args.token_out))
    params = {
        "tokenInAddress": token_in,
        "tokenOutAddress": token_out,
        "amount": str(args.amount),
        "slippage": args.slippage or "1",
        "deadline": args.deadline,
        "protocols": args.protocols,
    }
    if args.recipient:
        params["recipient"] = args.recipient
    data = dex_get("/v2/quote", params)
    dex_expect_success(data)
    _ok(data)

def cmd_dex_send(args):
    """Sign and broadcast a DEX swap transaction using calldata from dex-quote."""
    try:
        from eth_account import Account
    except ImportError:
        _err("eth_account is required: pip install eth_account")

    acct = Account.from_key(args.private_key)
    nonce = rpc_call("eth_getTransactionCount", [acct.address, "latest"])
    gas_price = rpc_call("eth_gasPrice", [])

    value_wei = to_wei(args.value) if args.value else 0

    # Estimate gas
    tx_for_estimate = {
        "from": acct.address,
        "to": args.to,
        "data": args.data,
    }
    if value_wei > 0:
        tx_for_estimate["value"] = hex(value_wei)
    gas_est = rpc_call("eth_estimateGas", [tx_for_estimate])

    tx = {
        "chainId": CHAIN_ID,
        "nonce": int(nonce, 16),
        "to": args.to,
        "value": value_wei,
        "gas": int(gas_est, 16),
        "gasPrice": int(gas_price, 16),
        "data": args.data,
    }
    signed = acct.sign_transaction(tx)
    tx_hash = rpc_call("eth_sendRawTransaction", [signed.raw_transaction.hex()])
    _ok({
        "tx_hash": tx_hash,
        "from": acct.address,
        "to": args.to,
        "value_eth": args.value or "0",
        "gas": int(gas_est, 16),
    })

# ---------------------------------------------------------------------------
# Commands — Alt-Fee (pay gas with alternative tokens)
# ---------------------------------------------------------------------------

# -- Alt-fee transaction helpers (type 0x7f) --------------------------------

ALT_FEE_TX_TYPE = 0x7f

def _int_to_min_bytes(value):
    """Encode non-negative integer to minimal big-endian bytes (0 → b'')."""
    if value == 0:
        return b""
    byte_len = (value.bit_length() + 7) // 8
    return value.to_bytes(byte_len, "big")

def _hex_to_bytes(hex_str):
    """Convert hex string to bytes (''/None/'0x' → b'')."""
    if not hex_str or hex_str == "0x":
        return b""
    clean = hex_str[2:] if hex_str.startswith("0x") else hex_str
    if len(clean) % 2:
        clean = "0" + clean
    return bytes.fromhex(clean)

def _rlp_encode(obj):
    """Minimal RLP encoder (bytes and nested lists only)."""
    if isinstance(obj, (bytes, bytearray)):
        length = len(obj)
        if length == 0:
            return b"\x80"
        if length == 1 and obj[0] < 0x80:
            return bytes(obj)
        if length < 56:
            return bytes([0x80 + length]) + obj
        len_bytes = _int_to_min_bytes(length)
        return bytes([0xb7 + len(len_bytes)]) + len_bytes + obj
    elif isinstance(obj, list):
        payload = b"".join(_rlp_encode(item) for item in obj)
        length = len(payload)
        if length < 56:
            return bytes([0xc0 + length]) + payload
        len_bytes = _int_to_min_bytes(length)
        return bytes([0xf7 + len(len_bytes)]) + len_bytes + payload
    raise TypeError(f"Cannot RLP-encode type {type(obj)}")

def _serialize_altfee_tx(tx, signature=None):
    """Serialize a Morph alt-fee (0x7f) transaction.

    RLP fields: [chainId, nonce, maxPriorityFeePerGas, maxFeePerGas,
                 gas, to, value, data, accessList, feeTokenID, feeLimit,
                 (yParity, r, s if signed)]
    """
    fields = [
        _int_to_min_bytes(tx["chainId"]),
        _int_to_min_bytes(tx["nonce"]),
        _int_to_min_bytes(tx["maxPriorityFeePerGas"]),
        _int_to_min_bytes(tx["maxFeePerGas"]),
        _int_to_min_bytes(tx["gas"]),
        _hex_to_bytes(tx.get("to", "0x")),
        _int_to_min_bytes(tx.get("value", 0)),
        _hex_to_bytes(tx.get("data", "0x")),
        [],  # accessList (empty)
        _int_to_min_bytes(tx["feeTokenID"]),
        _int_to_min_bytes(tx["feeLimit"]),
    ]
    if signature:
        y_parity, r, s = signature
        fields.extend([
            _int_to_min_bytes(y_parity),
            _int_to_min_bytes(r),
            _int_to_min_bytes(s),
        ])
    return bytes([ALT_FEE_TX_TYPE]) + _rlp_encode(fields)

def _sign_altfee_tx(tx, private_key_hex):
    """Sign a 0x7f alt-fee transaction, return raw tx as hex string."""
    try:
        from eth_keys import keys as _keys
        from eth_hash.auto import keccak as _keccak
    except ImportError:
        _err("eth_account is required: pip install eth_account")

    unsigned = _serialize_altfee_tx(tx)
    msg_hash = _keccak(unsigned)

    pk = _keys.PrivateKey(_hex_to_bytes(private_key_hex))
    sig = pk.sign_msg_hash(msg_hash)

    signed = _serialize_altfee_tx(tx, (sig.v, sig.r, sig.s))
    return "0x" + signed.hex()

def _get_fee_params(token_id):
    """Query TokenRegistry for scale, feeRate, decimals of a fee token."""
    id_hex = hex(token_id)[2:].zfill(64)
    info_result = rpc_call("eth_call", [
        {"to": TOKEN_REGISTRY, "data": TR_GET_TOKEN_INFO_SIG + id_hex},
        "latest",
    ])
    if not info_result or info_result == "0x":
        _err(f"Token ID {token_id} not found in registry")
    raw = info_result[2:]
    decimals = int(raw[192:256], 16)
    scale = int(raw[256:320], 16)

    ratio_result = rpc_call("eth_call", [
        {"to": TOKEN_REGISTRY, "data": TR_PRICE_RATIO_SIG + id_hex},
        "latest",
    ])
    fee_rate = int(ratio_result, 16) if ratio_result and ratio_result != "0x" else 0
    if fee_rate == 0:
        _err(f"Token ID {token_id} has zero fee rate")
    return scale, fee_rate, decimals

# -- Alt-fee query commands -------------------------------------------------

def _decode_uint256(hex_str):
    """Decode a single uint256 from hex."""
    return int(hex_str, 16)

def cmd_altfee_tokens(_args):
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

def cmd_altfee_token_info(args):
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

def cmd_altfee_estimate(args):
    """Estimate the minimum feeLimit to pay gas with an alternative token.

    Formula: feeLimit >= (gasFeeCap * gasLimit + L1DataFee) * tokenScale / feeRate
    """
    token_id = args.id
    gas_limit = args.gas_limit
    scale, fee_rate, decimals = _get_fee_params(token_id)

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

def cmd_altfee_send(args):
    """Sign and broadcast a transaction paying gas with an alternative fee token (type 0x7f).

    Constructs a Morph-specific alt-fee transaction, signs it locally, and broadcasts.
    feeLimit defaults to 0 (no limit — uses available balance, unused portion is refunded).
    """
    try:
        from eth_account import Account
    except ImportError:
        _err("eth_account is required: pip install eth_account")

    acct = Account.from_key(args.private_key)
    nonce = int(rpc_call("eth_getTransactionCount", [acct.address, "latest"]), 16)

    # Gas prices (EIP-1559 style)
    max_fee_per_gas = int(rpc_call("eth_gasPrice", []), 16)
    max_priority_fee_per_gas = 0  # Morph L2 sequencer; priority fee is negligible

    value_wei = to_wei(args.value) if args.value else 0
    data_hex = args.data or "0x"

    # Estimate gas
    tx_for_estimate = {"from": acct.address, "to": args.to}
    if data_hex != "0x":
        tx_for_estimate["data"] = data_hex
    if value_wei > 0:
        tx_for_estimate["value"] = hex(value_wei)
    gas_limit = args.gas_limit or int(rpc_call("eth_estimateGas", [tx_for_estimate]), 16)

    # Fee limit: default 0 = no limit (uses available balance, unused is refunded)
    token_id = args.fee_token_id
    fee_limit = args.fee_limit if args.fee_limit is not None else 0

    tx = {
        "chainId": CHAIN_ID,
        "nonce": nonce,
        "maxPriorityFeePerGas": max_priority_fee_per_gas,
        "maxFeePerGas": max_fee_per_gas,
        "gas": gas_limit,
        "to": args.to,
        "value": value_wei,
        "data": data_hex,
        "feeTokenID": token_id,
        "feeLimit": fee_limit,
    }

    raw_tx = _sign_altfee_tx(tx, args.private_key)
    tx_hash = rpc_call("eth_sendRawTransaction", [raw_tx])
    _ok({
        "tx_hash": tx_hash,
        "from": acct.address,
        "to": args.to,
        "value_eth": args.value or "0",
        "fee_token_id": token_id,
        "fee_limit": str(fee_limit),
        "gas": gas_limit,
        "type": "0x7f",
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

    sub.add_parser("token-list", help="List top tracked tokens from the explorer (single page)")

    # -- DEX ------------------------------------------------------------------
    p = sub.add_parser("dex-quote", help="Get a swap quote (Bulbaswap v2)")
    p.add_argument("--amount", required=True, help="Amount to swap (human-readable)")
    p.add_argument("--token-in", required=True, help="Source token symbol or address (ETH for native)")
    p.add_argument("--token-out", required=True, help="Destination token symbol or address")
    p.add_argument("--slippage", default="1", help="Slippage tolerance %% (default: 1)")
    p.add_argument("--deadline", default="60", help="Quote validity seconds (default: 60)")
    p.add_argument("--protocols", default="v2,v3", help="Routing protocols (default: v2,v3)")
    p.add_argument("--recipient", default=None, help="Optional recipient address")

    p = sub.add_parser("dex-send", help="Sign and broadcast a swap tx using calldata from dex-quote")
    p.add_argument("--to", required=True, help="Router contract address (from methodParameters.to)")
    p.add_argument("--value", default=None, help="ETH value in ETH (from methodParameters.value, default: 0)")
    p.add_argument("--data", required=True, help="Calldata hex (from methodParameters.calldata)")
    p.add_argument("--private-key", required=True, help="Sender private key")

    # -- Alt-Fee --------------------------------------------------------------
    sub.add_parser("altfee-tokens", help="List supported fee tokens from TokenRegistry")

    p = sub.add_parser("altfee-token-info", help="Get fee token details (scale, feeRate, etc.)")
    p.add_argument("--id", type=int, required=True, help="Fee token ID (1-5)")

    p = sub.add_parser("altfee-estimate", help="Estimate feeLimit for paying gas with alt token")
    p.add_argument("--id", type=int, required=True, help="Fee token ID (1-5)")
    p.add_argument("--gas-limit", type=int, default=21000, help="Gas limit (default: 21000)")

    p = sub.add_parser("altfee-send", help="Send a transaction paying gas with alt fee token (0x7f)")
    p.add_argument("--to", required=True, help="Recipient/contract address")
    p.add_argument("--value", default=None, help="ETH value to send (default: 0)")
    p.add_argument("--data", default=None, help="Transaction calldata hex (default: none)")
    p.add_argument("--fee-token-id", type=int, required=True, help="Fee token ID (1-5)")
    p.add_argument("--fee-limit", type=int, default=None, help="Max fee token amount in smallest units (default: 0 = no limit)")
    p.add_argument("--gas-limit", type=int, default=None, help="Gas limit (auto-estimated if omitted)")
    p.add_argument("--private-key", required=True, help="Sender private key")

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
    "dex-send":       cmd_dex_send,
    "altfee-tokens":     cmd_altfee_tokens,
    "altfee-token-info": cmd_altfee_token_info,
    "altfee-estimate":   cmd_altfee_estimate,
    "altfee-send":       cmd_altfee_send,
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
