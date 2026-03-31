#!/usr/bin/env python3
"""
morph_wallet.py — Wallet operation commands for Morph L2.

Exports register_wallet_commands(sub) called by morph_api.build_parser().
"""

from morph_api import (
    _ok,
    _err,
    rpc_call,
    _load_account,
    validate_address,
    to_wei,
    wei_to_ether,
    resolve_erc20_token,
    get_token_decimals,
    pad_address,
    CHAIN_ID,
    ERC20_BALANCE_OF_SIG,
    ERC20_TRANSFER_SIG,
)

from decimal import Decimal


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
    validate_address(args.to)
    acct = _load_account(args.private_key)
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
    tx_hash = rpc_call("eth_sendRawTransaction", ["0x" + signed.raw_transaction.hex()])
    _ok({
        "tx_hash": tx_hash,
        "from": acct.address,
        "to": args.to,
        "amount_eth": args.amount,
    })

def cmd_transfer_token(args):
    """Sign and send an ERC20 transfer transaction."""
    validate_address(args.to)
    token = resolve_erc20_token(args.token)
    decimals = get_token_decimals(token)
    amount_raw = to_wei(args.amount, decimals)

    acct = _load_account(args.private_key)
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
    tx_hash = rpc_call("eth_sendRawTransaction", ["0x" + signed.raw_transaction.hex()])
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


def register_wallet_commands(sub):
    p = sub.add_parser("create-wallet", help="Generate a new ETH key pair locally")
    p.set_defaults(handler=cmd_create_wallet)

    p = sub.add_parser("balance", help="Query native ETH balance")
    p.set_defaults(handler=cmd_balance)
    p.add_argument("--address", required=True, help="Wallet address")

    p = sub.add_parser("token-balance", help="Query ERC20 token balance")
    p.set_defaults(handler=cmd_token_balance)
    p.add_argument("--address", required=True, help="Wallet address")
    p.add_argument("--token", required=True, help="Token symbol (e.g. USDT) or contract address")

    p = sub.add_parser("transfer", help="Send ETH to an address")
    p.set_defaults(handler=cmd_transfer)
    p.add_argument("--to", required=True, help="Recipient address")
    p.add_argument("--amount", required=True, help="Amount in ETH (e.g. 0.1)")
    p.add_argument("--private-key", required=True, help="Sender private key")

    p = sub.add_parser("transfer-token", help="Send ERC20 tokens to an address")
    p.set_defaults(handler=cmd_transfer_token)
    p.add_argument("--token", required=True, help="Token symbol (e.g. USDT) or contract address")
    p.add_argument("--to", required=True, help="Recipient address")
    p.add_argument("--amount", required=True, help="Amount in token units (e.g. 10.5)")
    p.add_argument("--private-key", required=True, help="Sender private key")

    p = sub.add_parser("tx-receipt", help="Query transaction receipt")
    p.set_defaults(handler=cmd_tx_receipt)
    p.add_argument("--hash", required=True, help="Transaction hash")
