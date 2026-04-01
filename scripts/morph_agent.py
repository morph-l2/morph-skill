#!/usr/bin/env python3
"""
morph_agent.py — EIP-8004 agent identity and reputation commands for Morph L2.

Exports register_agent_commands(sub) called by morph_api.build_parser().
Imports _send_contract_tx_altfee from morph_altfee for
commands that support --fee-token-id (agent-register, agent-feedback).
"""

import json
import os
from decimal import Decimal

from morph_api import (
    _ok,
    _err,
    rpc_call,
    _load_account,
    validate_address,
    to_wei,
    pad_address,
    CHAIN_ID,
    IDENTITY_REGISTRY,
    REPUTATION_REGISTRY,
    CONTRACTS_DIR,
    NATIVE_TOKEN,
)
from morph_altfee import _send_contract_tx_altfee

# ---------------------------------------------------------------------------
# ABI loading
# ---------------------------------------------------------------------------

_IDENTITY_ABI = None
_REPUTATION_ABI = None


def _require_abi_modules():
    try:
        from eth_abi import encode as abi_encode, decode as abi_decode
        from eth_utils import keccak
        return abi_encode, abi_decode, keccak
    except ImportError:
        _err("Agent commands require eth_abi and eth_utils: pip install requests eth_account eth_abi eth_utils")


def _load_contract_abi(filename):
    path = os.path.join(CONTRACTS_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        _err(f"ABI file not found: {path}")
    except json.JSONDecodeError as e:
        _err(f"Invalid ABI JSON in {path}: {e}")
    if isinstance(data, dict) and "abi" in data:
        return data["abi"]
    if isinstance(data, list):
        return data
    _err(f"Unsupported ABI format in {path}")


def get_identity_abi():
    global _IDENTITY_ABI
    if _IDENTITY_ABI is None:
        _IDENTITY_ABI = _load_contract_abi("IdentityRegistry.json")
    return _IDENTITY_ABI


def get_reputation_abi():
    global _REPUTATION_ABI
    if _REPUTATION_ABI is None:
        _REPUTATION_ABI = _load_contract_abi("ReputationRegistry.json")
    return _REPUTATION_ABI

# ---------------------------------------------------------------------------
# ABI encoding/decoding helpers
# ---------------------------------------------------------------------------


def _abi_function_signature(entry):
    inputs = entry.get("inputs", [])
    return f"{entry['name']}({','.join(_canonical_abi_type(i) for i in inputs)})"


def _canonical_abi_type(item):
    raw = item["type"]
    if not raw.startswith("tuple"):
        return raw
    suffix = raw[len("tuple"):]
    components = item.get("components", [])
    inner = ",".join(_canonical_abi_type(component) for component in components)
    return f"({inner}){suffix}"


def _get_abi_function(abi, signature):
    for entry in abi:
        if entry.get("type") == "function" and _abi_function_signature(entry) == signature:
            return entry
    _err(f"ABI function not found: {signature}")


def _normalize_hex_data(data):
    if not data:
        return "0x"
    return data if data.startswith("0x") else f"0x{data}"


def _encode_abi_call(abi, signature, args):
    abi_encode, _abi_decode, keccak = _require_abi_modules()
    fn = _get_abi_function(abi, signature)
    selector = keccak(text=signature)[:4].hex()
    arg_types = [_canonical_abi_type(item) for item in fn.get("inputs", [])]
    encoded_args = abi_encode(arg_types, args).hex() if arg_types else ""
    return "0x" + selector + encoded_args


def _decode_abi_output(abi, signature, data):
    _abi_encode, abi_decode, _keccak = _require_abi_modules()
    fn = _get_abi_function(abi, signature)
    outputs = fn.get("outputs", [])
    if not outputs:
        return tuple()
    data = _normalize_hex_data(data)
    if data == "0x":
        return tuple()
    output_types = [_canonical_abi_type(item) for item in outputs]
    raw = abi_decode(output_types, bytes.fromhex(data[2:]))
    return tuple(raw)


def _eth_call_contract(address, abi, signature, args=None):
    validate_address(address)
    calldata = _encode_abi_call(abi, signature, args or [])
    return rpc_call("eth_call", [{"to": address, "data": calldata}, "latest"])


def _eth_call_contract_allow_revert(address, abi, signature, args=None):
    """Call a contract and return (result, error) without exiting on EVM revert."""
    validate_address(address)
    calldata = _encode_abi_call(abi, signature, args or [])
    return rpc_call("eth_call", [{"to": address, "data": calldata}, "latest"], allow_error=True)


def _send_contract_tx(contract_address, calldata, private_key):
    acct = _load_account(private_key)
    return _send_contract_tx_from_account(contract_address, calldata, acct)


def _send_contract_tx_from_account(contract_address, calldata, acct):
    nonce = rpc_call("eth_getTransactionCount", [acct.address, "latest"])
    gas_price = rpc_call("eth_gasPrice", [])
    gas_est = rpc_call("eth_estimateGas", [{
        "from": acct.address,
        "to": contract_address,
        "data": calldata,
    }])

    tx = {
        "chainId": CHAIN_ID,
        "nonce": int(nonce, 16),
        "to": contract_address,
        "value": 0,
        "gas": int(gas_est, 16),
        "gasPrice": int(gas_price, 16),
        "data": calldata,
    }
    signed = acct.sign_transaction(tx)
    tx_hash = rpc_call("eth_sendRawTransaction", ["0x" + signed.raw_transaction.hex()])
    return acct.address, tx_hash, int(gas_est, 16)


def _wait_for_receipt(tx_hash, retries=10):
    """Poll eth_getTransactionReceipt until the tx is confirmed."""
    import time
    for _ in range(retries):
        receipt = rpc_call("eth_getTransactionReceipt", [tx_hash])
        if receipt is not None:
            return receipt
        time.sleep(2)
    return None

# ---------------------------------------------------------------------------
# Agent-specific helpers
# ---------------------------------------------------------------------------

# ERC-721 Transfer event: Transfer(address indexed from, address indexed to, uint256 indexed tokenId)
_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
AGENT_WALLET_DOMAIN_NAME = "ERC8004IdentityRegistry"
AGENT_WALLET_DOMAIN_VERSION = "1"
AGENT_WALLET_MAX_DEADLINE_DELAY = 5 * 60


def _parse_agent_id_from_receipt(receipt):
    """Extract agentId (tokenId) from the ERC-721 Transfer event in tx logs."""
    for log in receipt.get("logs", []):
        topics = log.get("topics", [])
        if len(topics) >= 4 and topics[0].lower() == _TRANSFER_TOPIC:
            return str(int(topics[3], 16))
    return None


def _decimal_from_int(value, decimals):
    value = int(value)
    sign = "-" if value < 0 else ""
    raw = abs(value)
    human = Decimal(raw) / Decimal(10 ** int(decimals))
    return f"{sign}{human}"


def _decode_text_bytes(value):
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return "0x" + bytes(value).hex()
    return str(value)


def _parse_metadata_pairs(metadata_str):
    items = []
    if not metadata_str:
        return items
    for pair in metadata_str.split(","):
        key, sep, value = pair.partition("=")
        if not sep:
            _err(f"Invalid metadata entry: {pair}. Use key=value,key=value.")
        key = key.strip()
        value = value.strip()
        if not key:
            _err("Metadata key must not be empty")
        items.append((key, value.encode("utf-8")))
    return items


def _zero_bytes32():
    return b"\x00" * 32


def _agent_exists(agent_id):
    # The upgraded registry removed `agentExists(uint256)`. `ownerOf(uint256)`
    # cleanly reverts for nonexistent agents, which we treat as a false result.
    result, error = _eth_call_contract_allow_revert(
        IDENTITY_REGISTRY,
        get_identity_abi(),
        "ownerOf(uint256)",
        [int(agent_id)],
    )
    if error:
        if "execution reverted" in str(error.get("message", "")):
            return False
        _err(f"RPC error: {error}")
    decoded = _decode_abi_output(get_identity_abi(), "ownerOf(uint256)", result)
    return bool(decoded and decoded[0])


def _require_agent_exists(agent_id):
    if not _agent_exists(agent_id):
        _err(f"Agent does not exist: {agent_id}")


def _require_altfee_selection(fee_token_id, fee_limit=None, gas_limit=None):
    if fee_token_id is None and (fee_limit is not None or gas_limit is not None):
        _err("`--fee-limit` and `--gas-limit` require `--fee-token-id`.")


def _send_contract_tx_for_args(contract_address, calldata, args, acct=None):
    """Send a contract tx with optional altfee, preserving existing CLI semantics."""
    fee_token_id = getattr(args, "fee_token_id", None)
    fee_limit = getattr(args, "fee_limit", None)
    gas_limit = getattr(args, "gas_limit", None)
    _require_altfee_selection(fee_token_id, fee_limit, gas_limit)

    if fee_token_id is not None:
        sender, tx_hash, gas, fee_limit = _send_contract_tx_altfee(
            contract_address,
            calldata,
            args.private_key,
            fee_token_id,
            fee_limit=fee_limit,
            gas_limit=gas_limit,
        )
    else:
        sender, tx_hash, gas = _send_contract_tx_from_account(
            contract_address,
            calldata,
            acct or _load_account(args.private_key),
        )
        fee_limit = None

    return sender, tx_hash, gas, fee_token_id, fee_limit


def _attach_altfee_result(result, fee_token_id, fee_limit):
    """Annotate a command result with altfee fields when applicable."""
    if fee_token_id is None:
        return result
    result["fee_token_id"] = fee_token_id
    result["fee_limit"] = str(fee_limit)
    result["type"] = "0x7f"
    return result

# ---------------------------------------------------------------------------
# Commands — Agent (EIP-8004)
# ---------------------------------------------------------------------------


def cmd_agent_register(args):
    """Register an agent identity via IdentityRegistry."""
    abi = get_identity_abi()
    metadata = _parse_metadata_pairs(args.metadata)
    if args.name:
        metadata.append(("name", args.name.encode("utf-8")))

    if args.agent_uri and metadata:
        signature = "register(string,(string,bytes)[])"
        calldata = _encode_abi_call(abi, signature, [args.agent_uri, metadata])
    elif metadata:
        signature = "register(string,(string,bytes)[])"
        calldata = _encode_abi_call(abi, signature, ["", metadata])
    elif args.agent_uri:
        signature = "register(string)"
        calldata = _encode_abi_call(abi, signature, [args.agent_uri])
    else:
        signature = "register()"
        calldata = _encode_abi_call(abi, signature, [])

    sender, tx_hash, gas, fee_token_id, fee_limit = _send_contract_tx_for_args(
        IDENTITY_REGISTRY,
        calldata,
        args,
    )

    # Wait for receipt and extract agentId from Transfer event
    agent_id = None
    receipt = _wait_for_receipt(tx_hash)
    if receipt:
        agent_id = _parse_agent_id_from_receipt(receipt)

    result = {
        "tx_hash": tx_hash,
        "from": sender,
        "contract": IDENTITY_REGISTRY,
        "agent_uri": args.agent_uri or "",
        "metadata_keys": [key for key, _value in metadata],
        "gas": gas,
    }
    _attach_altfee_result(result, fee_token_id, fee_limit)
    if agent_id:
        result["agent_id"] = agent_id
        result["message"] = f"Agent registered successfully. Your agentId is {agent_id}."
    elif receipt:
        status = receipt.get("status", "0x1")
        if status == "0x0":
            result["message"] = "Transaction reverted. Registration failed — check gas and contract state."
        else:
            result["message"] = "Transaction confirmed but agentId could not be parsed from logs. Use tx-receipt to inspect."
    else:
        result["message"] = "Transaction submitted but receipt not yet available. Use tx-receipt to check status and retrieve agentId."
    _ok(result)


def cmd_agent_wallet(args):
    """Get the payment wallet for an agent."""
    agent_id = int(args.agent_id)
    _require_agent_exists(agent_id)
    result = _eth_call_contract(IDENTITY_REGISTRY, get_identity_abi(), "getAgentWallet(uint256)", [agent_id])
    decoded = _decode_abi_output(get_identity_abi(), "getAgentWallet(uint256)", result)
    wallet = decoded[0] if decoded else NATIVE_TOKEN
    _ok({
        "agent_id": str(agent_id),
        "agent_wallet": wallet,
        "has_wallet": wallet.lower() != NATIVE_TOKEN.lower(),
        "contract": IDENTITY_REGISTRY,
    })


def cmd_agent_metadata(args):
    """Read metadata for an agent by key."""
    agent_id = int(args.agent_id)
    _require_agent_exists(agent_id)
    result = _eth_call_contract(
        IDENTITY_REGISTRY,
        get_identity_abi(),
        "getMetadata(uint256,string)",
        [agent_id, args.key],
    )
    decoded = _decode_abi_output(get_identity_abi(), "getMetadata(uint256,string)", result)
    value = decoded[0] if decoded else b""
    _ok({
        "agent_id": str(agent_id),
        "key": args.key,
        "value": _decode_text_bytes(value),
        "value_hex": "0x" + bytes(value).hex(),
        "contract": IDENTITY_REGISTRY,
    })


def cmd_agent_reputation(args):
    """Read reputation summary for an agent."""
    agent_id = int(args.agent_id)
    tag1 = args.tag1 or ""
    tag2 = args.tag2 or ""

    _require_agent_exists(agent_id)

    clients_result = _eth_call_contract(REPUTATION_REGISTRY, get_reputation_abi(), "getClients(uint256)", [agent_id])
    clients_decoded = _decode_abi_output(get_reputation_abi(), "getClients(uint256)", clients_result)
    clients = list(clients_decoded[0]) if clients_decoded else []

    if not clients:
        _ok({
            "agent_id": str(agent_id),
            "feedback_count": 0,
            "reputation_score": "0",
            "decimals": 0,
            "client_count": 0,
            "tag1": tag1 or "all",
            "tag2": tag2 or "all",
            "contract": REPUTATION_REGISTRY,
            "message": "No feedback received yet",
        })

    summary_result = _eth_call_contract(
        REPUTATION_REGISTRY,
        get_reputation_abi(),
        "getSummary(uint256,address[],string,string)",
        [agent_id, clients, tag1, tag2],
    )
    count, summary_value, summary_decimals = _decode_abi_output(
        get_reputation_abi(),
        "getSummary(uint256,address[],string,string)",
        summary_result,
    )
    _ok({
        "agent_id": str(agent_id),
        "feedback_count": int(count),
        "reputation_score": _decimal_from_int(summary_value, summary_decimals),
        "decimals": int(summary_decimals),
        "client_count": len(clients),
        "clients": clients,
        "tag1": tag1 or "all",
        "tag2": tag2 or "all",
        "contract": REPUTATION_REGISTRY,
    })


def cmd_agent_feedback(args):
    """Submit feedback for an agent."""
    agent_id = int(args.agent_id)

    _require_agent_exists(agent_id)

    tag1 = args.tag1 or ""
    tag2 = args.tag2 or ""
    endpoint = args.endpoint or ""
    feedback_uri = args.feedback_uri or ""
    decimals = 2
    value_int = int(Decimal(args.value) * Decimal(10 ** decimals))

    calldata = _encode_abi_call(
        get_reputation_abi(),
        "giveFeedback(uint256,int128,uint8,string,string,string,string,bytes32)",
        [agent_id, value_int, decimals, tag1, tag2, endpoint, feedback_uri, _zero_bytes32()],
    )
    sender, tx_hash, gas, fee_token_id, fee_limit = _send_contract_tx_for_args(
        REPUTATION_REGISTRY,
        calldata,
        args,
    )
    result = {
        "tx_hash": tx_hash,
        "from": sender,
        "agent_id": str(agent_id),
        "value": args.value,
        "decimals": decimals,
        "tag1": tag1,
        "tag2": tag2,
        "endpoint": endpoint,
        "feedback_uri": feedback_uri,
        "feedback_hash": "0x" + _zero_bytes32().hex(),
        "contract": REPUTATION_REGISTRY,
        "gas": gas,
        "message": "Feedback submitted successfully",
    }
    _attach_altfee_result(result, fee_token_id, fee_limit)
    _ok(result)


def cmd_agent_reviews(args):
    """Read all feedback entries for an agent."""
    agent_id = int(args.agent_id)
    tag1 = args.tag1 or ""
    tag2 = args.tag2 or ""
    include_revoked = bool(args.include_revoked)

    _require_agent_exists(agent_id)

    clients_result = _eth_call_contract(REPUTATION_REGISTRY, get_reputation_abi(), "getClients(uint256)", [agent_id])
    clients_decoded = _decode_abi_output(get_reputation_abi(), "getClients(uint256)", clients_result)
    clients = list(clients_decoded[0]) if clients_decoded else []

    reviews_result = _eth_call_contract(
        REPUTATION_REGISTRY,
        get_reputation_abi(),
        "readAllFeedback(uint256,address[],string,string,bool)",
        [agent_id, clients, tag1, tag2, include_revoked],
    )
    decoded = _decode_abi_output(
        get_reputation_abi(),
        "readAllFeedback(uint256,address[],string,string,bool)",
        reviews_result,
    )

    feedback = []
    if decoded:
        clients_list, indexes, values, decimals_list, tag1s, tag2s, revoked = decoded
        for idx in range(len(clients_list)):
            feedback.append({
                "client": clients_list[idx],
                "index": int(indexes[idx]),
                "value": _decimal_from_int(values[idx], decimals_list[idx]),
                "value_raw": str(int(values[idx])),
                "decimals": int(decimals_list[idx]),
                "tag1": tag1s[idx],
                "tag2": tag2s[idx],
                "revoked": bool(revoked[idx]),
            })

    _ok({
        "agent_id": str(agent_id),
        "feedback_count": len(feedback),
        "include_revoked": include_revoked,
        "tag1": tag1 or "all",
        "tag2": tag2 or "all",
        "contract": REPUTATION_REGISTRY,
        "feedback": feedback,
    })


def cmd_agent_set_metadata(args):
    """Set a metadata key-value for an agent."""
    abi = get_identity_abi()
    agent_id = int(args.agent_id)
    key = args.key
    value_bytes = args.value.encode("utf-8")

    calldata = _encode_abi_call(abi, "setMetadata(uint256,string,bytes)", [agent_id, key, value_bytes])

    sender, tx_hash, gas, fee_token_id, fee_limit = _send_contract_tx_for_args(
        IDENTITY_REGISTRY,
        calldata,
        args,
    )

    result = {
        "tx_hash": tx_hash,
        "from": sender,
        "agent_id": str(agent_id),
        "key": key,
        "value": args.value,
        "contract": IDENTITY_REGISTRY,
        "gas": gas,
        "message": "Metadata set successfully",
    }
    _ok(_attach_altfee_result(result, fee_token_id, fee_limit))


def cmd_agent_set_uri(args):
    """Set the agent URI for an agent."""
    abi = get_identity_abi()
    agent_id = int(args.agent_id)
    uri = args.uri

    calldata = _encode_abi_call(abi, "setAgentURI(uint256,string)", [agent_id, uri])

    sender, tx_hash, gas, fee_token_id, fee_limit = _send_contract_tx_for_args(
        IDENTITY_REGISTRY,
        calldata,
        args,
    )

    result = {
        "tx_hash": tx_hash,
        "from": sender,
        "agent_id": str(agent_id),
        "uri": uri,
        "contract": IDENTITY_REGISTRY,
        "gas": gas,
        "message": "Agent URI set successfully",
    }
    _ok(_attach_altfee_result(result, fee_token_id, fee_limit))


def cmd_agent_set_wallet(args):
    """Bind an operational wallet to an agent using an EIP-712 signature from the new wallet."""
    abi = get_identity_abi()
    agent_id = int(args.agent_id)

    owner_acct = _load_account(args.private_key)
    new_wallet_acct = _load_account(args.new_wallet_key)
    new_wallet_address = new_wallet_acct.address

    # Mainnet IdentityRegistry enforces MAX_DEADLINE_DELAY = 5 minutes.
    block = rpc_call("eth_getBlockByNumber", ["latest", False])
    current_ts = int(block["timestamp"], 16)
    deadline = current_ts + AGENT_WALLET_MAX_DEADLINE_DELAY

    # The signed payload must match the on-chain AgentWalletSet struct exactly.
    typed_data = {
        "domain": {
            "name": AGENT_WALLET_DOMAIN_NAME,
            "version": AGENT_WALLET_DOMAIN_VERSION,
            "chainId": CHAIN_ID,
            "verifyingContract": IDENTITY_REGISTRY,
        },
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "AgentWalletSet": [
                {"name": "agentId", "type": "uint256"},
                {"name": "newWallet", "type": "address"},
                {"name": "owner", "type": "address"},
                {"name": "deadline", "type": "uint256"},
            ],
        },
        "primaryType": "AgentWalletSet",
        "message": {
            "agentId": agent_id,
            "newWallet": new_wallet_address,
            "owner": owner_acct.address,
            "deadline": deadline,
        },
    }
    signed = new_wallet_acct.sign_typed_data(
        domain_data=typed_data["domain"],
        message_types={"AgentWalletSet": typed_data["types"]["AgentWalletSet"]},
        message_data=typed_data["message"],
    )
    signature = signed.signature

    calldata = _encode_abi_call(
        abi,
        "setAgentWallet(uint256,address,uint256,bytes)",
        [agent_id, new_wallet_address, deadline, signature],
    )

    sender, tx_hash, gas, fee_token_id, fee_limit = _send_contract_tx_for_args(
        IDENTITY_REGISTRY,
        calldata,
        args,
        acct=owner_acct,
    )

    result = {
        "tx_hash": tx_hash,
        "from": sender,
        "agent_id": str(agent_id),
        "new_wallet": new_wallet_address,
        "deadline": deadline,
        "contract": IDENTITY_REGISTRY,
        "gas": gas,
        "message": "Agent wallet set successfully",
    }
    _ok(_attach_altfee_result(result, fee_token_id, fee_limit))


def cmd_agent_unset_wallet(args):
    """Unbind the operational wallet from an agent."""
    abi = get_identity_abi()
    agent_id = int(args.agent_id)

    calldata = _encode_abi_call(abi, "unsetAgentWallet(uint256)", [agent_id])

    sender, tx_hash, gas, fee_token_id, fee_limit = _send_contract_tx_for_args(
        IDENTITY_REGISTRY,
        calldata,
        args,
    )

    result = {
        "tx_hash": tx_hash,
        "from": sender,
        "agent_id": str(agent_id),
        "contract": IDENTITY_REGISTRY,
        "gas": gas,
        "message": "Agent wallet unset successfully",
    }
    _ok(_attach_altfee_result(result, fee_token_id, fee_limit))


def cmd_agent_revoke_feedback(args):
    """Revoke own feedback for an agent."""
    reputation_abi = get_reputation_abi()
    agent_id = int(args.agent_id)
    feedback_index = int(args.feedback_index)

    calldata = _encode_abi_call(
        reputation_abi,
        "revokeFeedback(uint256,uint64)",
        [agent_id, feedback_index],
    )

    sender, tx_hash, gas, fee_token_id, fee_limit = _send_contract_tx_for_args(
        REPUTATION_REGISTRY,
        calldata,
        args,
    )

    result = {
        "tx_hash": tx_hash,
        "from": sender,
        "agent_id": str(agent_id),
        "feedback_index": feedback_index,
        "contract": REPUTATION_REGISTRY,
        "gas": gas,
        "message": "Feedback revoked successfully",
    }
    _ok(_attach_altfee_result(result, fee_token_id, fee_limit))


def cmd_agent_append_response(args):
    """Append a response to feedback as the agent owner."""
    _require_abi_modules()
    from eth_utils import keccak

    reputation_abi = get_reputation_abi()
    agent_id = int(args.agent_id)
    client = args.client
    feedback_index = int(args.feedback_index)
    response_uri = args.response_uri
    response_hash = keccak(text=response_uri)

    calldata = _encode_abi_call(
        reputation_abi,
        "appendResponse(uint256,address,uint64,string,bytes32)",
        [agent_id, client, feedback_index, response_uri, response_hash],
    )

    sender, tx_hash, gas, fee_token_id, fee_limit = _send_contract_tx_for_args(
        REPUTATION_REGISTRY,
        calldata,
        args,
    )

    result = {
        "tx_hash": tx_hash,
        "from": sender,
        "agent_id": str(agent_id),
        "client": client,
        "feedback_index": feedback_index,
        "response_uri": response_uri,
        "response_hash": "0x" + response_hash.hex(),
        "contract": REPUTATION_REGISTRY,
        "gas": gas,
        "message": "Response appended successfully",
    }
    _ok(_attach_altfee_result(result, fee_token_id, fee_limit))

# ---------------------------------------------------------------------------
# CLI registration
# ---------------------------------------------------------------------------


def register_agent_commands(sub):
    p = sub.add_parser("agent-register", help="Register an agent identity via EIP-8004")
    p.set_defaults(handler=cmd_agent_register)
    p.add_argument("--private-key", required=True, help="Private key for signing")
    p.add_argument("--name", default=None, help="Optional agent name (added to metadata as name=...)")
    p.add_argument("--agent-uri", dest="agent_uri", default=None, help="Optional agent URI")
    p.add_argument("--metadata", default=None, help="Comma-separated key=value pairs")
    p.add_argument("--fee-token-id", type=int, default=None, help="Optional fee token ID for altfee gas payment")
    p.add_argument("--fee-limit", type=int, default=None, help="Optional altfee cap in smallest units (requires --fee-token-id)")
    p.add_argument("--gas-limit", type=int, default=None, help="Optional gas limit for altfee execution (requires --fee-token-id)")

    p = sub.add_parser("agent-wallet", help="Get the payment wallet for an agent")
    p.set_defaults(handler=cmd_agent_wallet)
    p.add_argument("--agent-id", dest="agent_id", required=True, help="Agent ID")

    p = sub.add_parser("agent-metadata", help="Get metadata for an agent")
    p.set_defaults(handler=cmd_agent_metadata)
    p.add_argument("--agent-id", dest="agent_id", required=True, help="Agent ID")
    p.add_argument("--key", required=True, help="Metadata key")

    p = sub.add_parser("agent-reputation", help="Get aggregated reputation for an agent")
    p.set_defaults(handler=cmd_agent_reputation)
    p.add_argument("--agent-id", dest="agent_id", required=True, help="Agent ID")
    p.add_argument("--tag1", default=None, help="Optional first tag filter")
    p.add_argument("--tag2", default=None, help="Optional second tag filter")

    p = sub.add_parser("agent-feedback", help="Submit feedback for an agent")
    p.set_defaults(handler=cmd_agent_feedback)
    p.add_argument("--private-key", required=True, help="Private key for signing")
    p.add_argument("--agent-id", dest="agent_id", required=True, help="Agent ID")
    p.add_argument("--value", required=True, help="Feedback score, stored with 2 decimals")
    p.add_argument("--tag1", default=None, help="Optional first tag")
    p.add_argument("--tag2", default=None, help="Optional second tag")
    p.add_argument("--endpoint", default=None, help="Optional endpoint string")
    p.add_argument("--feedback-uri", dest="feedback_uri", default=None, help="Optional feedback URI")
    p.add_argument("--fee-token-id", type=int, default=None, help="Optional fee token ID for altfee gas payment")
    p.add_argument("--fee-limit", type=int, default=None, help="Optional altfee cap in smallest units (requires --fee-token-id)")
    p.add_argument("--gas-limit", type=int, default=None, help="Optional gas limit for altfee execution (requires --fee-token-id)")

    p = sub.add_parser("agent-reviews", help="Read all feedback entries for an agent")
    p.set_defaults(handler=cmd_agent_reviews)
    p.add_argument("--agent-id", dest="agent_id", required=True, help="Agent ID")
    p.add_argument("--tag1", default=None, help="Optional first tag filter")
    p.add_argument("--tag2", default=None, help="Optional second tag filter")
    p.add_argument("--include-revoked", action="store_true", help="Include revoked feedback")

    p = sub.add_parser("agent-set-metadata", help="Set a metadata key-value for an agent")
    p.set_defaults(handler=cmd_agent_set_metadata)
    p.add_argument("--private-key", required=True, help="Private key for signing")
    p.add_argument("--agent-id", dest="agent_id", required=True, help="Agent ID")
    p.add_argument("--key", required=True, help="Metadata key")
    p.add_argument("--value", required=True, help="Metadata value (encoded as UTF-8 bytes)")
    p.add_argument("--fee-token-id", type=int, default=None, help="Optional fee token ID for altfee gas payment")
    p.add_argument("--fee-limit", type=int, default=None, help="Optional altfee cap in smallest units (requires --fee-token-id)")
    p.add_argument("--gas-limit", type=int, default=None, help="Optional gas limit for altfee execution (requires --fee-token-id)")

    p = sub.add_parser("agent-set-uri", help="Set the agent URI for an agent")
    p.set_defaults(handler=cmd_agent_set_uri)
    p.add_argument("--private-key", required=True, help="Private key for signing")
    p.add_argument("--agent-id", dest="agent_id", required=True, help="Agent ID")
    p.add_argument("--uri", required=True, help="Agent URI to set")
    p.add_argument("--fee-token-id", type=int, default=None, help="Optional fee token ID for altfee gas payment")
    p.add_argument("--fee-limit", type=int, default=None, help="Optional altfee cap in smallest units (requires --fee-token-id)")
    p.add_argument("--gas-limit", type=int, default=None, help="Optional gas limit for altfee execution (requires --fee-token-id)")

    p = sub.add_parser("agent-set-wallet", help="Bind an operational wallet to an agent (requires new wallet's private key for EIP-712 signature)")
    p.set_defaults(handler=cmd_agent_set_wallet)
    p.add_argument("--private-key", required=True, help="Owner private key for signing the transaction")
    p.add_argument("--agent-id", dest="agent_id", required=True, help="Agent ID")
    p.add_argument("--new-wallet-key", dest="new_wallet_key", required=True, help="Private key of the new wallet to bind (used to sign EIP-712 authorization)")
    p.add_argument("--fee-token-id", type=int, default=None, help="Optional fee token ID for altfee gas payment")
    p.add_argument("--fee-limit", type=int, default=None, help="Optional altfee cap in smallest units (requires --fee-token-id)")
    p.add_argument("--gas-limit", type=int, default=None, help="Optional gas limit for altfee execution (requires --fee-token-id)")

    p = sub.add_parser("agent-unset-wallet", help="Unbind the operational wallet from an agent")
    p.set_defaults(handler=cmd_agent_unset_wallet)
    p.add_argument("--private-key", required=True, help="Private key for signing")
    p.add_argument("--agent-id", dest="agent_id", required=True, help="Agent ID")
    p.add_argument("--fee-token-id", type=int, default=None, help="Optional fee token ID for altfee gas payment")
    p.add_argument("--fee-limit", type=int, default=None, help="Optional altfee cap in smallest units (requires --fee-token-id)")
    p.add_argument("--gas-limit", type=int, default=None, help="Optional gas limit for altfee execution (requires --fee-token-id)")

    p = sub.add_parser("agent-revoke-feedback", help="Revoke own feedback for an agent")
    p.set_defaults(handler=cmd_agent_revoke_feedback)
    p.add_argument("--private-key", required=True, help="Private key for signing")
    p.add_argument("--agent-id", dest="agent_id", required=True, help="Agent ID")
    p.add_argument("--feedback-index", dest="feedback_index", required=True, help="Index of the feedback to revoke")
    p.add_argument("--fee-token-id", type=int, default=None, help="Optional fee token ID for altfee gas payment")
    p.add_argument("--fee-limit", type=int, default=None, help="Optional altfee cap in smallest units (requires --fee-token-id)")
    p.add_argument("--gas-limit", type=int, default=None, help="Optional gas limit for altfee execution (requires --fee-token-id)")

    p = sub.add_parser("agent-append-response", help="Append a response to feedback as the agent owner")
    p.set_defaults(handler=cmd_agent_append_response)
    p.add_argument("--private-key", required=True, help="Private key for signing")
    p.add_argument("--agent-id", dest="agent_id", required=True, help="Agent ID")
    p.add_argument("--client", required=True, help="Client address that submitted the feedback")
    p.add_argument("--feedback-index", dest="feedback_index", required=True, help="Index of the feedback to respond to")
    p.add_argument("--response-uri", dest="response_uri", required=True, help="URI of the response")
    p.add_argument("--fee-token-id", type=int, default=None, help="Optional fee token ID for altfee gas payment")
    p.add_argument("--fee-limit", type=int, default=None, help="Optional altfee cap in smallest units (requires --fee-token-id)")
    p.add_argument("--gas-limit", type=int, default=None, help="Optional gas limit for altfee execution (requires --fee-token-id)")
