#!/usr/bin/env python3
"""
morph_dex.py — Bulbaswap DEX commands for Morph L2.

Exports register_dex_commands(sub) called by morph_api.build_parser().
"""

from morph_api import (
    _ok,
    _err,
    dex_get,
    dex_expect_success,
    validate_address,
    resolve_token,
    to_wei,
    wei_to_ether,
    get_token_decimals,
    token_for_dex,
    _load_account,
    rpc_call,
    CHAIN_ID,
    NATIVE_TOKEN,
)


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
    validate_address(args.to)
    acct = _load_account(args.private_key)
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
    tx_hash = rpc_call("eth_sendRawTransaction", ["0x" + signed.raw_transaction.hex()])
    _ok({
        "tx_hash": tx_hash,
        "from": acct.address,
        "to": args.to,
        "value_eth": args.value or "0",
        "gas": int(gas_est, 16),
    })


def register_dex_commands(sub):
    p = sub.add_parser("dex-quote", help="Get a swap quote (Bulbaswap v2)")
    p.set_defaults(handler=cmd_dex_quote)
    p.add_argument("--amount", required=True, help="Amount to swap (human-readable)")
    p.add_argument("--token-in", required=True, help="Source token symbol or address (ETH for native)")
    p.add_argument("--token-out", required=True, help="Destination token symbol or address")
    p.add_argument("--slippage", default="1", help="Slippage tolerance %% (default: 1)")
    p.add_argument("--deadline", default="300", help="Quote validity seconds (default: 300)")
    p.add_argument("--protocols", default="v2,v3", help="Routing protocols (default: v2,v3)")
    p.add_argument("--recipient", default=None, help="Optional recipient address")

    p = sub.add_parser("dex-send", help="Sign and broadcast a swap tx using calldata from dex-quote")
    p.set_defaults(handler=cmd_dex_send)
    p.add_argument("--to", required=True, help="Router contract address (from methodParameters.to)")
    p.add_argument("--value", default=None, help="ETH value in ETH (from methodParameters.value, default: 0)")
    p.add_argument("--data", required=True, help="Calldata hex (from methodParameters.calldata)")
    p.add_argument("--private-key", required=True, help="Sender private key")
