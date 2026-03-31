#!/usr/bin/env python3
"""
morph_7702.py — EIP-7702 EOA delegation for Morph L2

Provides 5 commands: 7702-delegate, 7702-authorize, 7702-send, 7702-batch, 7702-revoke.
Imported by morph_api.py at runtime (late import inside build_parser).
"""

import json

from morph_api import (
    CHAIN_ID,
    _ok,
    _err,
    rpc_call,
    _rlp_encode,
    _int_to_min_bytes,
    _hex_to_bytes,
    _load_account,
    validate_address,
    to_wei,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SIMPLE_DELEGATION = "0xBD7093Ded667289F9808Fa0C678F81dbB4d2eEb7"
DELEGATION_PREFIX = "0xef0100"
EIP7702_TYPE_BYTE = 0x04
AUTH_MAGIC_BYTE = 0x05
REVOKE_ADDR = "0x0000000000000000000000000000000000000000"
GAS_FALLBACK_SEND = 200_000
GAS_FALLBACK_BATCH = 300_000
GAS_BUFFER = 50_000
GAS_REVOKE = 80_000


# ---------------------------------------------------------------------------
# Helpers — EIP-7702 crypto
# ---------------------------------------------------------------------------

def _keccak(data: bytes) -> bytes:
    """keccak256 hash, returns 32 bytes."""
    from eth_hash.auto import keccak
    return keccak(data)


def _compute_auth_hash(chain_id: int, contract_addr: str, nonce: int) -> bytes:
    """Compute EIP-7702 authorization hash.

    Formula: keccak256(0x05 || RLP([chainId, contractAddress, nonce]))
    """
    fields = _rlp_encode([
        _int_to_min_bytes(chain_id),
        _hex_to_bytes(contract_addr),
        _int_to_min_bytes(nonce),
    ])
    return _keccak(bytes([AUTH_MAGIC_BYTE]) + fields)


def _serialize_7702_tx(tx, auth_list, sig=None):
    """Serialize an EIP-7702 (type 0x04) transaction.

    RLP fields: [chainId, nonce, maxPriorityFeePerGas, maxFeePerGas,
                 gas, to, value, data, accessList, authorizationList,
                 (yParity, r, s if signed)]

    auth_list: list of dicts with keys: chainId, contract, nonce, y_parity, r, s
    sig: optional tuple (y_parity, r, s) for the outer tx signature
    """
    auth_rlp = [
        [
            _int_to_min_bytes(a["chainId"]),
            _hex_to_bytes(a["contract"]),
            _int_to_min_bytes(a["nonce"]),
            _int_to_min_bytes(a["y_parity"]),
            _int_to_min_bytes(a["r"]),
            _int_to_min_bytes(a["s"]),
        ]
        for a in auth_list
    ]
    fields = [
        _int_to_min_bytes(tx["chainId"]),
        _int_to_min_bytes(tx["nonce"]),
        _int_to_min_bytes(0),  # maxPriorityFeePerGas = 0 (L2, no priority fee)
        _int_to_min_bytes(tx["maxFeePerGas"]),
        _int_to_min_bytes(tx["gas"]),
        _hex_to_bytes(tx["to"]),
        _int_to_min_bytes(tx.get("value", 0)),
        _hex_to_bytes(tx.get("data", "0x")),
        [],  # accessList (always empty)
        auth_rlp,
    ]
    if sig:
        y_parity, r, s = sig
        fields.extend([
            _int_to_min_bytes(y_parity),
            _int_to_min_bytes(r),
            _int_to_min_bytes(s),
        ])
    return bytes([EIP7702_TYPE_BYTE]) + _rlp_encode(fields)


def _sign_7702_tx(tx, auth_list, private_key_hex):
    """Sign a type 0x04 transaction, return raw tx hex string."""
    from eth_keys import keys as _keys

    unsigned = _serialize_7702_tx(tx, auth_list)
    msg_hash = _keccak(unsigned)

    pk = _keys.PrivateKey(_hex_to_bytes(private_key_hex))
    sig = pk.sign_msg_hash(msg_hash)

    signed = _serialize_7702_tx(tx, auth_list, (sig.v, sig.r, sig.s))
    return "0x" + signed.hex()


def _sign_auth(private_key_hex, chain_id, contract_addr, nonce):
    """Sign an EIP-7702 authorization, return dict with y_parity, r, s."""
    from eth_keys import keys as _keys

    auth_hash = _compute_auth_hash(chain_id, contract_addr, nonce)
    pk = _keys.PrivateKey(_hex_to_bytes(private_key_hex))
    sig = pk.sign_msg_hash(auth_hash)
    return {
        "chainId": chain_id,
        "contract": contract_addr,
        "nonce": nonce,
        "y_parity": sig.v,
        "r": sig.r,
        "s": sig.s,
    }


def _estimate_gas_7702(eoa, to, value, data, fallback):
    """Estimate gas with a buffer for 7702 overhead. Falls back on error."""
    try:
        params = {"from": eoa, "to": to, "value": hex(value), "data": data}
        gas_hex = rpc_call("eth_estimateGas", [params])
        return int(gas_hex, 16) + GAS_BUFFER
    except SystemExit:
        return fallback


# ---------------------------------------------------------------------------
# SimpleDelegation contract interaction
# ---------------------------------------------------------------------------

def _fn_selector(signature: str) -> bytes:
    """Compute 4-byte function selector from signature string."""
    return _keccak(signature.encode())[:4]

_NONCE_SIG = _fn_selector("nonce()")
_EXECUTE_SIG = _fn_selector("execute((address,uint256,bytes)[],uint256,bytes)")


def _get_delegation_nonce(eoa: str) -> int:
    """Read SimpleDelegation.nonce() from a delegated EOA. Returns 0 if not delegated."""
    result, err = rpc_call("eth_call", [
        {"to": eoa, "data": "0x" + _NONCE_SIG.hex()},
        "latest",
    ], allow_error=True)
    if err or not result or result == "0x":
        return 0
    return int(result, 16)


def _encode_batch_calldata(calls_tuples, delegation_nonce, sig_bytes):
    """Encode SimpleDelegation.execute(Call[], uint256, bytes) calldata."""
    from eth_abi import encode as abi_encode
    params = abi_encode(
        ['(address,uint256,bytes)[]', 'uint256', 'bytes'],
        [calls_tuples, delegation_nonce, sig_bytes],
    )
    return "0x" + _EXECUTE_SIG.hex() + params.hex()


def _compute_data_hash(calls_tuples, delegation_nonce, chain_id, eoa):
    """Compute SimpleDelegation data hash for EIP-191 signing.

    hash = keccak256(abi.encode(calls, nonce, chainId, address(this)))
    """
    from eth_abi import encode as abi_encode
    encoded = abi_encode(
        ['(address,uint256,bytes)[]', 'uint256', 'uint256', 'address'],
        [calls_tuples, delegation_nonce, chain_id, eoa],
    )
    return _keccak(encoded)


# ---------------------------------------------------------------------------
# Commands — EIP-7702
# ---------------------------------------------------------------------------

def cmd_7702_delegate(args):
    """Check whether an EOA has been delegated via EIP-7702."""
    addr = validate_address(args.address)
    code = rpc_call("eth_getCode", [addr, "latest"])
    if code and code.startswith(DELEGATION_PREFIX):
        contract = "0x" + code[8:48]
        _ok({
            "address": addr,
            "delegated": True,
            "contract": contract,
            "code_prefix": DELEGATION_PREFIX,
        })
    else:
        _ok({
            "address": addr,
            "delegated": False,
            "contract": None,
            "code_prefix": None,
        })


def cmd_7702_authorize(args):
    """Sign a 7702 authorization offline — no transaction is sent."""
    delegate_addr = args.delegate or SIMPLE_DELEGATION
    validate_address(delegate_addr)

    acct = _load_account(args.private_key)
    eoa = acct.address

    tx_nonce = int(rpc_call("eth_getTransactionCount", [eoa, "latest"]), 16)
    auth_nonce = tx_nonce + 1

    auth = _sign_auth(args.private_key, CHAIN_ID, delegate_addr, auth_nonce)

    _ok({
        "chainId": CHAIN_ID,
        "contractAddress": delegate_addr,
        "nonce": auth_nonce,
        "yParity": hex(auth["y_parity"]),
        "r": hex(auth["r"]),
        "s": hex(auth["s"]),
    })


def cmd_7702_send(args):
    """Send a single call using EIP-7702 delegation (tx type 0x04)."""
    validate_address(args.to)
    delegate_addr = args.delegate or SIMPLE_DELEGATION
    validate_address(delegate_addr)

    value_wei = to_wei(args.value) if args.value else 0
    data_hex = args.data or "0x"

    acct = _load_account(args.private_key)
    eoa = acct.address

    tx_nonce = int(rpc_call("eth_getTransactionCount", [eoa, "latest"]), 16)
    auth_nonce = tx_nonce + 1

    auth = _sign_auth(args.private_key, CHAIN_ID, delegate_addr, auth_nonce)

    gas_price = int(rpc_call("eth_gasPrice", []), 16)
    gas = args.gas or _estimate_gas_7702(eoa, args.to, value_wei, data_hex, GAS_FALLBACK_SEND)

    tx = {
        "chainId": CHAIN_ID,
        "nonce": tx_nonce,
        "maxFeePerGas": gas_price,
        "gas": gas,
        "to": args.to,
        "value": value_wei,
        "data": data_hex,
    }
    raw_tx = _sign_7702_tx(tx, [auth], args.private_key)
    tx_hash = rpc_call("eth_sendRawTransaction", [raw_tx])
    _ok({"tx_hash": tx_hash})


def cmd_7702_batch(args):
    """Atomically execute multiple calls via SimpleDelegation (tx type 0x04).

    Signing flow:
    1. eth_getTransactionCount(eoa)          -> tx_nonce
    2. SimpleDelegation.nonce(eoa)           -> delegation_nonce
    3. compute data_hash                     -> keccak256
    4. sign data_hash with EIP-191           -> execute signature
    5. encode execute(calls, nonce, sig)     -> calldata
    6. sign 7702 authorization               -> auth_sig
    7. serialize + sign type 0x04 tx         -> raw_tx
    8. eth_sendRawTransaction                -> tx_hash
    """
    try:
        raw_calls = json.loads(args.calls)
    except (json.JSONDecodeError, TypeError) as e:
        _err(f"invalid --calls JSON: {e}")
    if not isinstance(raw_calls, list) or len(raw_calls) == 0:
        _err("--calls must be a non-empty JSON array")

    delegate_addr = args.delegate or SIMPLE_DELEGATION
    validate_address(delegate_addr)

    acct = _load_account(args.private_key)
    eoa = acct.address

    calls_tuples = []
    for i, c in enumerate(raw_calls):
        if "to" not in c:
            _err(f"call[{i}] missing 'to' field")
        validate_address(c["to"])
        value_wei = to_wei(str(c.get("value", "0")))
        data_bytes = _hex_to_bytes(c.get("data", "0x"))
        calls_tuples.append((c["to"], value_wei, data_bytes))

    tx_nonce = int(rpc_call("eth_getTransactionCount", [eoa, "latest"]), 16)
    auth_nonce = tx_nonce + 1

    delegation_nonce = _get_delegation_nonce(eoa)

    data_hash = _compute_data_hash(calls_tuples, delegation_nonce, CHAIN_ID, eoa)

    from eth_account.messages import encode_defunct
    signed_msg = acct.sign_message(encode_defunct(primitive=data_hash))
    sig_bytes = signed_msg.signature

    execute_calldata = _encode_batch_calldata(calls_tuples, delegation_nonce, sig_bytes)

    auth = _sign_auth(args.private_key, CHAIN_ID, delegate_addr, auth_nonce)

    gas_price = int(rpc_call("eth_gasPrice", []), 16)
    gas = args.gas or _estimate_gas_7702(eoa, eoa, 0, execute_calldata, GAS_FALLBACK_BATCH)

    tx = {
        "chainId": CHAIN_ID,
        "nonce": tx_nonce,
        "maxFeePerGas": gas_price,
        "gas": gas,
        "to": eoa,
        "value": 0,
        "data": execute_calldata,
    }
    raw_tx = _sign_7702_tx(tx, [auth], args.private_key)

    tx_hash = rpc_call("eth_sendRawTransaction", [raw_tx])
    _ok({"tx_hash": tx_hash, "calls_count": len(calls_tuples)})


def register_7702_commands(sub):
    """Register EIP-7702 subcommands — called by morph_api.build_parser()."""
    p = sub.add_parser("7702-delegate", help="Check if an EOA has a 7702 delegation")
    p.set_defaults(handler=cmd_7702_delegate)
    p.add_argument("--address", required=True, help="EOA address to check")

    p = sub.add_parser("7702-authorize", help="Sign a 7702 authorization offline (no tx sent)")
    p.set_defaults(handler=cmd_7702_authorize)
    p.add_argument("--private-key", required=True, help="Signer private key")
    p.add_argument("--delegate", default=None,
                   help=f"Delegate contract (default: SimpleDelegation {SIMPLE_DELEGATION})")

    p = sub.add_parser("7702-send", help="Send a single call via EIP-7702 delegation (type 0x04)")
    p.set_defaults(handler=cmd_7702_send)
    p.add_argument("--to", required=True, help="Target contract address")
    p.add_argument("--value", default=None, help="ETH value to send (default: 0)")
    p.add_argument("--data", default=None, help="Calldata hex (default: 0x)")
    p.add_argument("--private-key", required=True, help="Sender private key")
    p.add_argument("--delegate", default=None,
                   help=f"Delegate contract (default: SimpleDelegation {SIMPLE_DELEGATION})")
    p.add_argument("--gas", type=int, default=None, help="Gas limit (auto-estimated if omitted)")

    p = sub.add_parser("7702-batch",
                       help="Atomically execute multiple calls via SimpleDelegation (type 0x04)")
    p.set_defaults(handler=cmd_7702_batch)
    p.add_argument("--calls", required=True,
                   help='JSON array of {to, value, data} objects')
    p.add_argument("--private-key", required=True, help="Sender private key")
    p.add_argument("--delegate", default=None,
                   help=f"SimpleDelegation contract (default: {SIMPLE_DELEGATION})")
    p.add_argument("--gas", type=int, default=None, help="Gas limit (auto-estimated if omitted)")
