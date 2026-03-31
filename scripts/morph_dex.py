#!/usr/bin/env python3
"""
morph_dex.py — Bulbaswap DEX commands for Morph L2.

Exports register_dex_commands(sub) called by morph_api.build_parser().
"""

from decimal import Decimal

from morph_api import (
    _ok,
    _err,
    dex_get,
    dex_expect_success,
    validate_address,
    resolve_token,
    resolve_erc20_token,
    to_wei,
    wei_to_ether,
    get_token_decimals,
    token_for_dex,
    pad_address,
    _load_account,
    rpc_call,
    CHAIN_ID,
    NATIVE_TOKEN,
)

ERC20_APPROVE_SIG   = "0x095ea7b3"
ERC20_ALLOWANCE_SIG = "0xdd62ed3e"


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


def cmd_dex_approve(args):
    """Approve an ERC-20 token for spending by a DEX router."""
    token_address = resolve_erc20_token(args.token)
    decimals = get_token_decimals(token_address)
    amount_raw = to_wei(args.amount, decimals)

    # encode approve(address,uint256) calldata
    spender_padded = pad_address(args.spender)[2:]   # strip 0x, 32-byte hex
    amount_padded  = hex(amount_raw)[2:].zfill(64)   # 32-byte hex
    calldata = ERC20_APPROVE_SIG + spender_padded + amount_padded

    acct = _load_account(args.private_key)
    nonce     = rpc_call("eth_getTransactionCount", [acct.address, "latest"])
    gas_price = rpc_call("eth_gasPrice", [])
    gas_est   = rpc_call("eth_estimateGas", [{"from": acct.address, "to": token_address, "data": calldata}])

    tx = {
        "chainId":  CHAIN_ID,
        "nonce":    int(nonce, 16),
        "to":       token_address,
        "value":    0,
        "gas":      int(gas_est, 16),
        "gasPrice": int(gas_price, 16),
        "data":     calldata,
    }
    signed   = acct.sign_transaction(tx)
    tx_hash  = rpc_call("eth_sendRawTransaction", ["0x" + signed.raw_transaction.hex()])
    _ok({
        "tx_hash":    tx_hash,
        "token":      token_address,
        "spender":    args.spender,
        "amount":     args.amount,
        "amount_raw": str(amount_raw),
    })


def cmd_dex_allowance(args):
    """Check the ERC-20 allowance granted to a spender."""
    token_address = resolve_erc20_token(args.token)
    decimals = get_token_decimals(token_address)

    # encode allowance(address,address) calldata
    owner_padded   = pad_address(args.owner)[2:]    # strip 0x
    spender_padded = pad_address(args.spender)[2:]
    calldata = ERC20_ALLOWANCE_SIG + owner_padded + spender_padded

    result = rpc_call("eth_call", [{"to": token_address, "data": calldata}, "latest"])
    if not result or result == "0x":
        allowance_raw = 0
    else:
        allowance_raw = int(result, 16)

    allowance_human = str(Decimal(allowance_raw) / Decimal(10 ** decimals))
    _ok({
        "token":         token_address,
        "owner":         args.owner,
        "spender":       args.spender,
        "allowance":     allowance_human,
        "allowance_raw": str(allowance_raw),
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

    p = sub.add_parser("dex-approve", help="Approve an ERC-20 token for spending by a DEX router")
    p.set_defaults(handler=cmd_dex_approve)
    p.add_argument("--token", required=True, help="Token symbol or contract address (e.g. USDT)")
    p.add_argument("--spender", required=True, help="Spender address (e.g. DEX router)")
    p.add_argument("--amount", required=True, help="Amount to approve (human-readable, e.g. 1000)")
    p.add_argument("--private-key", required=True, help="Sender private key")

    p = sub.add_parser("dex-allowance", help="Check ERC-20 allowance granted to a spender")
    p.set_defaults(handler=cmd_dex_allowance)
    p.add_argument("--token", required=True, help="Token symbol or contract address (e.g. USDT)")
    p.add_argument("--owner", required=True, help="Token owner address")
    p.add_argument("--spender", required=True, help="Spender address to check allowance for")
