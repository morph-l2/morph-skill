#!/usr/bin/env python3
"""
morph_altfee.py — Alt-fee gas payment commands for Morph L2 (tx type 0x7f).

Exports register_altfee_commands(sub) called by morph_api.build_parser().
Also exports _send_altfee_tx and _send_contract_tx_altfee used by morph_agent.
"""

from decimal import Decimal

from morph_api import (
    _ok,
    _err,
    rpc_call,
    _load_account,
    validate_address,
    to_wei,
    _rlp_encode,
    _int_to_min_bytes,
    _hex_to_bytes,
    _normalize_morph_token_meta,
    CHAIN_ID,
)

# ---------------------------------------------------------------------------
# Alt-fee constants
# ---------------------------------------------------------------------------

ALT_FEE_TX_TYPE = 0x7f

# TokenRegistry contract (Morph pre-deploy)
TOKEN_REGISTRY = "0x5300000000000000000000000000000000000021"
TR_GET_TOKEN_LIST_SIG      = "0x1585458c"  # getSupportedTokenList()
TR_GET_TOKEN_INFO_SIG      = "0x1c58e793"  # getTokenInfo(uint16)
TR_PRICE_RATIO_SIG         = "0x19904c33"  # priceRatio(uint16)

# ---------------------------------------------------------------------------
# Alt-fee transaction helpers (type 0x7f)
# ---------------------------------------------------------------------------

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

    try:
        pk = _keys.PrivateKey(_hex_to_bytes(private_key_hex))
    except Exception as e:
        _err(f"Invalid private key: {e}")
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

# ---------------------------------------------------------------------------
# Shared helpers (also used by morph_agent.py)
# ---------------------------------------------------------------------------

def _send_altfee_tx(to, value_wei, data_hex, private_key, fee_token_id, fee_limit=None, gas_limit=None):
    """Sign and broadcast a 0x7f alt-fee transaction."""
    validate_address(to)
    acct = _load_account(private_key)
    nonce = int(rpc_call("eth_getTransactionCount", [acct.address, "latest"]), 16)

    max_fee_per_gas = int(rpc_call("eth_gasPrice", []), 16)
    max_priority_fee_per_gas = 0  # Morph L2 sequencer; priority fee is negligible

    tx_for_estimate = {"from": acct.address, "to": to}
    if data_hex != "0x":
        tx_for_estimate["data"] = data_hex
    if value_wei > 0:
        tx_for_estimate["value"] = hex(value_wei)
    gas_limit = gas_limit or int(rpc_call("eth_estimateGas", [tx_for_estimate]), 16)

    fee_limit = fee_limit if fee_limit is not None else 0

    tx = {
        "chainId": CHAIN_ID,
        "nonce": nonce,
        "maxPriorityFeePerGas": max_priority_fee_per_gas,
        "maxFeePerGas": max_fee_per_gas,
        "gas": gas_limit,
        "to": to,
        "value": value_wei,
        "data": data_hex,
        "feeTokenID": fee_token_id,
        "feeLimit": fee_limit,
    }

    raw_tx = _sign_altfee_tx(tx, private_key)
    tx_hash = rpc_call("eth_sendRawTransaction", [raw_tx])
    return acct.address, tx_hash, gas_limit, fee_limit

def _send_contract_tx_altfee(contract_address, calldata, private_key, fee_token_id, fee_limit=None, gas_limit=None):
    """Send a contract call using alt-fee gas payment."""
    return _send_altfee_tx(contract_address, 0, calldata, private_key, fee_token_id, fee_limit, gas_limit)

# ---------------------------------------------------------------------------
# Command functions
# ---------------------------------------------------------------------------

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
        token_symbol, token_name = _normalize_morph_token_meta(token_addr)
        tokens.append({
            "token_id": token_id,
            "address": token_addr,
            "symbol": token_symbol,
            "name": token_name,
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
    token_symbol, token_name = _normalize_morph_token_meta(token_addr)

    fee_rate = int(ratio_result, 16) if ratio_result and ratio_result != "0x" else 0

    _ok({
        "token_id": token_id,
        "address": token_addr,
        "symbol": token_symbol,
        "name": token_name,
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
    value_wei = to_wei(args.value) if args.value else 0
    data_hex = args.data or "0x"
    sender, tx_hash, gas_limit, fee_limit = _send_altfee_tx(
        args.to,
        value_wei,
        data_hex,
        args.private_key,
        args.fee_token_id,
        fee_limit=args.fee_limit,
        gas_limit=args.gas_limit,
    )
    _ok({
        "tx_hash": tx_hash,
        "from": sender,
        "to": args.to,
        "value_eth": args.value or "0",
        "fee_token_id": args.fee_token_id,
        "fee_limit": str(fee_limit),
        "gas": gas_limit,
        "type": "0x7f",
    })

# ---------------------------------------------------------------------------
# Argparse registration
# ---------------------------------------------------------------------------

def register_altfee_commands(sub):
    """Register alt-fee subcommands — called by morph_api.build_parser()."""
    p = sub.add_parser("altfee-tokens", help="List supported fee tokens from TokenRegistry")
    p.set_defaults(handler=cmd_altfee_tokens)

    p = sub.add_parser("altfee-token-info", help="Get fee token details (scale, feeRate, etc.)")
    p.set_defaults(handler=cmd_altfee_token_info)
    p.add_argument("--id", type=int, required=True, help="Fee token ID (1-6)")

    p = sub.add_parser("altfee-estimate", help="Estimate feeLimit for paying gas with alt token")
    p.set_defaults(handler=cmd_altfee_estimate)
    p.add_argument("--id", type=int, required=True, help="Fee token ID (1-6)")
    p.add_argument("--gas-limit", type=int, default=21000, help="Gas limit (default: 21000)")

    p = sub.add_parser("altfee-send", help="Send a transaction paying gas with alt fee token (0x7f)")
    p.set_defaults(handler=cmd_altfee_send)
    p.add_argument("--to", required=True, help="Recipient/contract address")
    p.add_argument("--value", default=None, help="ETH value to send (default: 0)")
    p.add_argument("--data", default=None, help="Transaction calldata hex (default: none)")
    p.add_argument("--fee-token-id", type=int, required=True, help="Fee token ID (1-6)")
    p.add_argument("--fee-limit", type=int, default=None,
                   help="Max fee token amount in smallest units (default: 0 = no limit)")
    p.add_argument("--gas-limit", type=int, default=None,
                   help="Gas limit (auto-estimated if omitted)")
    p.add_argument("--private-key", required=True, help="Sender private key")
