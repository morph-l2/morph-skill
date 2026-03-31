#!/usr/bin/env python3
"""
morph_explorer.py — Blockscout explorer commands for Morph L2.

Exports register_explorer_commands(sub) called by morph_api.build_parser().
"""

from morph_api import (
    _ok,
    _err,
    explorer_get,
    validate_address,
    resolve_token,
    _normalize_morph_token_item,
    _normalize_morph_explorer_items,
    NATIVE_TOKEN,
)

from morph_api import resolve_erc20_token, _normalize_morph_token_meta
from decimal import Decimal


def cmd_address_info(args):
    """Get address summary from Blockscout."""
    data = explorer_get(f"/addresses/{args.address}")
    _ok(data)

def cmd_address_txs(args):
    """List transactions for an address."""
    data = explorer_get(f"/addresses/{args.address}/transactions")
    if args.limit and isinstance(data, dict) and "items" in data:
        data["items"] = data["items"][:int(args.limit)]
    _ok(data)

def cmd_address_tokens(args):
    """List token holdings for an address."""
    data = explorer_get(f"/addresses/{args.address}/token-balances")
    if isinstance(data, list):
        data = [
            {**dict(item), "token": _normalize_morph_token_item(item.get("token"))}
            for item in data
        ]
    _ok(data)

def cmd_tx_detail(args):
    """Get full transaction details from Blockscout."""
    data = explorer_get(f"/transactions/{args.hash}")
    _ok(data)

def cmd_token_search(args):
    """Search tokens by name or symbol."""
    data = explorer_get("/tokens", {"q": args.query})
    data = _normalize_morph_explorer_items(data)
    _ok(data)

def cmd_contract_info(args):
    """Get smart contract info: source code, ABI, verification status, compiler."""
    addr = validate_address(args.address)
    data = explorer_get(f"/smart-contracts/{addr}")
    if not data or (isinstance(data, dict) and data.get("message")):
        _err(f"Contract not found or not verified at {addr}")
    _ok({
        "address": addr,
        "name": data.get("name"),
        "is_verified": data.get("is_verified"),
        "is_proxy": data.get("proxy_type") is not None,
        "proxy_type": data.get("proxy_type"),
        "implementations": data.get("implementations", []),
        "compiler_version": data.get("compiler_version"),
        "optimization_enabled": data.get("optimization_enabled"),
        "evm_version": data.get("evm_version"),
        "license_type": data.get("license_type"),
        "abi": data.get("abi"),
        "source_code": data.get("source_code"),
    })

def cmd_token_transfers(args):
    """Get recent token transfers for a token or address."""
    if args.token:
        token = resolve_erc20_token(args.token)
        data = explorer_get(f"/tokens/{token}/transfers")
    elif args.address:
        validate_address(args.address)
        data = explorer_get(f"/addresses/{args.address}/token-transfers")
    else:
        _err("Provide --token or --address")

    items = data.get("items", []) if isinstance(data, dict) else []
    transfers = []
    for t in items:
        total = t.get("total", {})
        decimals = int(total.get("decimals") or 18)
        raw_value = int(total.get("value") or 0)
        human_value = str(Decimal(raw_value) / Decimal(10**decimals))

        token_info = t.get("token", {})
        token_symbol, _token_name = _normalize_morph_token_meta(
            token_info.get("address_hash"),
            token_info.get("symbol"),
            token_info.get("name"),
        )
        transfers.append({
            "tx_hash": t.get("transaction_hash"),
            "from": t.get("from", {}).get("hash"),
            "to": t.get("to", {}).get("hash"),
            "token_symbol": token_symbol,
            "token_address": token_info.get("address_hash"),
            "amount": human_value,
            "amount_raw": str(raw_value),
            "method": t.get("method"),
            "timestamp": t.get("timestamp"),
            "block_number": t.get("block_number"),
        })
    _ok({"transfers": transfers, "count": len(transfers)})

def cmd_token_info(args):
    """Get token details: name, symbol, supply, holders, transfers."""
    token = resolve_erc20_token(args.token)
    data = explorer_get(f"/tokens/{token}")
    counters = explorer_get(f"/tokens/{token}/counters")

    decimals = int(data.get("decimals") or 18)
    total_supply_raw = int(data.get("total_supply") or 0)
    total_supply = str(Decimal(total_supply_raw) / Decimal(10**decimals))
    token_address = data.get("address_hash", token)
    token_symbol, token_name = _normalize_morph_token_meta(
        token_address,
        data.get("symbol"),
        data.get("name"),
    )

    _ok({
        "address": token_address,
        "name": token_name,
        "symbol": token_symbol,
        "type": data.get("type"),
        "decimals": decimals,
        "total_supply": total_supply,
        "holders_count": counters.get("token_holders_count"),
        "transfers_count": counters.get("transfers_count"),
        "exchange_rate": data.get("exchange_rate"),
        "volume_24h": data.get("volume_24h"),
        "circulating_market_cap": data.get("circulating_market_cap"),
        "icon_url": data.get("icon_url"),
    })

def cmd_token_list(_args):
    """List top tracked tokens from the explorer (single page)."""
    data = explorer_get("/tokens")
    data = _normalize_morph_explorer_items(data)
    _ok(data)


def register_explorer_commands(sub):
    p = sub.add_parser("address-info", help="Address summary from explorer")
    p.set_defaults(handler=cmd_address_info)
    p.add_argument("--address", required=True, help="Wallet address")

    p = sub.add_parser("address-txs", help="List transactions for an address")
    p.set_defaults(handler=cmd_address_txs)
    p.add_argument("--address", required=True, help="Wallet address")
    p.add_argument("--limit", type=int, default=None, help="Max results (optional)")

    p = sub.add_parser("address-tokens", help="Token holdings for an address")
    p.set_defaults(handler=cmd_address_tokens)
    p.add_argument("--address", required=True, help="Wallet address")

    p = sub.add_parser("tx-detail", help="Transaction details from explorer")
    p.set_defaults(handler=cmd_tx_detail)
    p.add_argument("--hash", required=True, help="Transaction hash")

    p = sub.add_parser("token-search", help="Search tokens by name or symbol")
    p.set_defaults(handler=cmd_token_search)
    p.add_argument("--query", required=True, help="Search query")

    p = sub.add_parser("contract-info", help="Smart contract info: source code, ABI, verification")
    p.set_defaults(handler=cmd_contract_info)
    p.add_argument("--address", required=True, help="Contract address")

    p = sub.add_parser("token-transfers", help="Recent token transfers for a token or address")
    p.set_defaults(handler=cmd_token_transfers)
    p.add_argument("--token", default=None, help="Token symbol or address (show transfers of this token)")
    p.add_argument("--address", default=None, help="Address (show token transfers involving this address)")

    p = sub.add_parser("token-info", help="Token details: name, supply, holders, transfers")
    p.set_defaults(handler=cmd_token_info)
    p.add_argument("--token", required=True, help="Token symbol (e.g. USDT) or contract address")

    p = sub.add_parser("token-list", help="List top tracked tokens from the explorer (single page)")
    p.set_defaults(handler=cmd_token_list)
