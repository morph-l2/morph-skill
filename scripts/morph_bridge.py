#!/usr/bin/env python3
"""
morph_bridge.py — Cross-chain bridge commands for Morph L2.

Exports register_bridge_commands(sub) called by morph_api.build_parser().
"""

import time
import requests

from morph_api import (
    _ok,
    _err,
    bridge_post,
    bridge_get,
    bridge_post_auth,
    _generate_auth_message,
    validate_address,
    to_wei,
    _load_account,
    rpc_call,
    CHAIN_ID,
    BRIDGE_TOKENS,
    NATIVE_TOKEN,
    DEX_API,
    _HEX_ADDRESS_RE,
    _BRIDGE_TOKENS_UPPER,
    _normalize_morph_token_item,
)


def _resolve_bridge_token(symbol_or_address, chain=None):
    """Resolve token for bridge API using multi-chain registry.

    Looks up symbol in BRIDGE_TOKENS[chain] (case-insensitive). Native tokens
    (ETH/BNB/POL) resolve to "" per chain. Falls back to morph if no chain.
    """
    if not symbol_or_address or symbol_or_address.upper() == "NATIVE":
        return ""
    if symbol_or_address.startswith("0x"):
        if not _HEX_ADDRESS_RE.match(symbol_or_address):
            _err(f"Invalid address: {symbol_or_address}. Must be 0x followed by 40 hex characters.")
        return symbol_or_address
    upper = symbol_or_address.upper()
    if chain:
        chain_tokens = _BRIDGE_TOKENS_UPPER.get(chain.lower(), {})
        if upper in chain_tokens:
            return chain_tokens[upper]
        # Show available symbols using original casing from BRIDGE_TOKENS
        orig_tokens = BRIDGE_TOKENS.get(chain.lower(), {})
        available = sorted(set(orig_tokens.keys()) - {"MATIC"})  # hide alias
        hint = f" Known symbols on {chain}: {', '.join(available[:15])}." if available else ""
        _err(f"Unknown token '{symbol_or_address}' on chain '{chain}'.{hint} "
             f"Use a contract address (0x...) or: bridge-token-search --keyword {symbol_or_address} --chain {chain}")
    # No chain — default to morph
    morph_tokens = _BRIDGE_TOKENS_UPPER.get("morph", {})
    if upper in morph_tokens:
        return morph_tokens[upper]
    _err(f"Unknown token: {symbol_or_address}. Provide a chain to resolve by chain, "
         f"use a contract address (0x...), or: bridge-token-search --keyword {symbol_or_address}")

def _build_make_order_body(args, to_address=None):
    """Build the request body for makeSwapOrder from parsed args."""
    from_contract = _resolve_bridge_token(args.from_contract, chain=args.from_chain)
    to_contract = _resolve_bridge_token(args.to_contract, chain=args.to_chain)
    body = {
        "fromChain": args.from_chain,
        "fromContract": from_contract,
        "fromAmount": str(args.from_amount),
        "toChain": args.to_chain,
        "toContract": to_contract,
        "toAddress": to_address or args.to_address,
        "market": args.market,
    }
    if args.slippage is not None:
        body["slippage"] = str(args.slippage)
    if args.feature:
        body["feature"] = args.feature
    return body

def _sign_bridge_txs(acct, txs):
    """Sign a list of unsigned bridge transactions, return raw hex strings."""
    signed_list = []
    for tx_info in txs:
        d = tx_info["data"]
        tx = {
            "chainId": int(tx_info["chainId"]),
            "nonce": int(d["nonce"]),
            "to": d["to"],
            "value": to_wei(d["value"]),
            "gas": int(d["gasLimit"]),
            "gasPrice": int(d["gasPrice"]),
            "data": d["calldata"],
        }
        signed = acct.sign_transaction(tx)
        raw = signed.raw_transaction.hex()
        if not raw.startswith("0x"):
            raw = "0x" + raw
        signed_list.append(raw)
    return signed_list

def cmd_bridge_chains(_args):
    """List supported chains for cross-chain swap."""
    data = bridge_get("/v2/order/chainList")
    _ok(data)

def cmd_bridge_tokens(args):
    """List available tokens for cross-chain swap on a given chain."""
    body = {}
    if args.chain:
        body["chain"] = args.chain
    data = bridge_post("/v2/order/tokenList", body)
    _ok(data)

def cmd_bridge_token_search(args):
    """Search tokens by symbol or contract address across chains."""
    body = {"keyword": args.keyword}
    if args.chain:
        body["chain"] = args.chain
    data = bridge_post("/v2/order/tokenSearch", body)
    _ok(data)

def cmd_bridge_quote(args):
    """Get a cross-chain or same-chain swap quote."""
    from_token = _resolve_bridge_token(args.from_token, chain=args.from_chain)
    to_token = _resolve_bridge_token(args.to_token, chain=args.to_chain)
    body = {
        "fromChain": args.from_chain,
        "fromContract": from_token,
        "fromAmount": str(args.amount),
        "toChain": args.to_chain,
        "toContract": to_token,
        "fromAddress": args.from_address,
    }
    data = bridge_post("/v2/order/getSwapPrice", body)
    _ok(data)

def cmd_bridge_balance(args):
    """Query token balance and USD price via bridge API."""
    token = _resolve_bridge_token(args.token, chain=args.chain)
    body = {
        "list": [{
            "chain": args.chain,
            "contract": token,
            "address": args.address,
        }],
    }
    data = bridge_post("/v2/order/tokenBalancePrice", body)
    if args.chain.lower() == "morph" and isinstance(data, dict) and isinstance(data.get("list"), list):
        data["list"] = [_normalize_morph_token_item(item, address_key="contract") for item in data["list"]]
    _ok(data)

def cmd_bridge_login(args):
    """Sign in with EIP-191 signature to get a JWT access token."""
    from eth_account.messages import encode_defunct
    acct = _load_account(args.private_key)
    timestamp = int(time.time() * 1000)
    message = _generate_auth_message(timestamp)
    signable = encode_defunct(text=message)
    signed = acct.sign_message(signable)
    sig_hex = signed.signature.hex() if isinstance(signed.signature, bytes) else str(signed.signature)
    if not sig_hex.startswith("0x"):
        sig_hex = "0x" + sig_hex
    body = {
        "address": acct.address,
        "signature": sig_hex,
        "timestamp": timestamp,
    }
    # Auth endpoint uses v1 response format (code/data) not v2 (status/data)
    url = f"{DEX_API}/v1/auth/sign-in"
    try:
        r = requests.post(url, json=body, timeout=30)
        r.raise_for_status()
        resp = r.json()
        if resp.get("code") != 200:
            _err(f"Auth error: {resp.get('msg')}")
        _ok(resp.get("data"))
    except requests.RequestException as e:
        _err(f"Auth request failed: {e}")

def cmd_bridge_make_order(args):
    """Create a cross-chain swap order. Returns orderId and unsigned transactions."""
    body = _build_make_order_body(args)
    data = bridge_post_auth("/v2/order/makeSwapOrder", body, args.jwt)
    _ok(data)

def cmd_bridge_submit_order(args):
    """Submit signed transactions for a swap order."""
    signed_txs = [tx.strip() for tx in args.signed_txs.split(",") if tx.strip()]
    body = {
        "orderId": args.order_id,
        "signedTxs": signed_txs,
    }
    data = bridge_post_auth("/v2/order/submitSwapOrder", body, args.jwt)
    _ok(data)

def cmd_bridge_swap(args):
    """One-step cross-chain swap: create order, sign transactions, and submit."""
    acct = _load_account(args.private_key)
    to_address = args.to_address or acct.address

    # Step 1: make order
    body = _build_make_order_body(args, to_address=to_address)
    order = bridge_post_auth("/v2/order/makeSwapOrder", body, args.jwt)

    # Step 2: sign each tx
    signed_list = _sign_bridge_txs(acct, order.get("txs", []))

    # Step 3: submit
    order_id = order["orderId"]
    bridge_post_auth("/v2/order/submitSwapOrder",
                     {"orderId": order_id, "signedTxs": signed_list}, args.jwt)

    _ok({
        "orderId": order_id,
        "fromChain": args.from_chain,
        "toChain": args.to_chain,
        "fromAmount": str(args.from_amount),
        "toMinAmount": order.get("toMinAmount"),
        "txCount": len(signed_list),
        "status": "submitted",
    })

def cmd_bridge_order(args):
    """Query the status of a swap order."""
    body = {"orderId": args.order_id}
    data = bridge_post_auth("/v2/order/getSwapOrder", body, args.jwt)
    _ok(data)

def cmd_bridge_history(args):
    """Query historical swap orders."""
    body = {}
    if args.page is not None:
        body["page"] = args.page
    if args.page_size is not None:
        body["pageSize"] = args.page_size
    if args.status:
        body["status"] = args.status
    data = bridge_post_auth("/v2/order/history", body, args.jwt)
    _ok(data)


def register_bridge_commands(sub):
    p = sub.add_parser("bridge-chains", help="List supported chains for cross-chain swap")
    p.set_defaults(handler=cmd_bridge_chains)

    p = sub.add_parser("bridge-tokens", help="List available tokens for cross-chain swap")
    p.set_defaults(handler=cmd_bridge_tokens)
    p.add_argument("--chain", default=None, help="Chain name (e.g. morph, eth, base). Default: all chains")

    p = sub.add_parser("bridge-token-search", help="Search tokens by symbol or address across chains")
    p.set_defaults(handler=cmd_bridge_token_search)
    p.add_argument("--keyword", required=True, help="Token symbol or contract address to search")
    p.add_argument("--chain", default=None, help="Filter by chain (optional)")

    p = sub.add_parser("bridge-quote", help="Get cross-chain or same-chain swap quote")
    p.set_defaults(handler=cmd_bridge_quote)
    p.add_argument("--from-chain", required=True, help="Source chain (e.g. morph, eth, base, bnb, arbitrum, matic)")
    p.add_argument("--from-token", required=True, help="Source token address or symbol (ETH for native)")
    p.add_argument("--amount", required=True, help="Amount to swap (human-readable)")
    p.add_argument("--to-chain", required=True, help="Destination chain")
    p.add_argument("--to-token", required=True, help="Destination token address or symbol")
    p.add_argument("--from-address", required=True, help="Sender wallet address")

    p = sub.add_parser("bridge-balance", help="Query token balance and USD price via bridge API")
    p.set_defaults(handler=cmd_bridge_balance)
    p.add_argument("--chain", required=True, help="Chain name (e.g. morph, eth, base)")
    p.add_argument("--token", required=True, help="Token address or symbol (ETH for native)")
    p.add_argument("--address", required=True, help="Wallet address")

    p = sub.add_parser("bridge-login", help="Sign in with EIP-191 signature to get a JWT access token")
    p.set_defaults(handler=cmd_bridge_login)
    p.add_argument("--private-key", required=True, help="Wallet private key for signing")

    p = sub.add_parser("bridge-make-order", help="Create a cross-chain swap order")
    p.set_defaults(handler=cmd_bridge_make_order)
    p.add_argument("--jwt", required=True, help="JWT access token from bridge-login")
    p.add_argument("--from-chain", required=True, help="Source chain (e.g. morph, eth, base)")
    p.add_argument("--from-contract", required=True, help="Source token contract address or symbol")
    p.add_argument("--from-amount", required=True, help="Amount to swap (human-readable)")
    p.add_argument("--to-chain", required=True, help="Destination chain")
    p.add_argument("--to-contract", required=True, help="Destination token contract address or symbol")
    p.add_argument("--to-address", required=True, help="Recipient address on destination chain")
    p.add_argument("--market", required=True, help="Market/protocol from quote (e.g. stargate)")
    p.add_argument("--slippage", type=float, default=None, help="Slippage tolerance %% (optional)")
    p.add_argument("--feature", default=None, help="Feature flag (e.g. no_gas)")

    p = sub.add_parser("bridge-submit-order", help="Submit signed transactions for a swap order")
    p.set_defaults(handler=cmd_bridge_submit_order)
    p.add_argument("--jwt", required=True, help="JWT access token from bridge-login")
    p.add_argument("--order-id", required=True, help="Order ID from bridge-make-order")
    p.add_argument("--signed-txs", required=True, help="Comma-separated signed transaction hex strings")

    p = sub.add_parser("bridge-swap", help="One-step cross-chain swap: create order, sign, and submit")
    p.set_defaults(handler=cmd_bridge_swap)
    p.add_argument("--jwt", required=True, help="JWT access token from bridge-login")
    p.add_argument("--from-chain", required=True, help="Source chain (e.g. morph, eth, base)")
    p.add_argument("--from-contract", required=True, help="Source token contract address or symbol")
    p.add_argument("--from-amount", required=True, help="Amount to swap (human-readable)")
    p.add_argument("--to-chain", required=True, help="Destination chain")
    p.add_argument("--to-contract", required=True, help="Destination token contract address or symbol")
    p.add_argument("--to-address", default=None, help="Recipient address (default: sender address)")
    p.add_argument("--market", required=True, help="Market/protocol from quote (e.g. stargate)")
    p.add_argument("--slippage", type=float, default=None, help="Slippage tolerance %% (optional)")
    p.add_argument("--feature", default=None, help="Feature flag (e.g. no_gas)")
    p.add_argument("--private-key", required=True, help="Private key for signing transactions")

    p = sub.add_parser("bridge-order", help="Query the status of a swap order")
    p.set_defaults(handler=cmd_bridge_order)
    p.add_argument("--jwt", required=True, help="JWT access token from bridge-login")
    p.add_argument("--order-id", required=True, help="Order ID to query")

    p = sub.add_parser("bridge-history", help="Query historical swap orders")
    p.set_defaults(handler=cmd_bridge_history)
    p.add_argument("--jwt", required=True, help="JWT access token from bridge-login")
    p.add_argument("--page", type=int, default=None, help="Page number (optional)")
    p.add_argument("--page-size", type=int, default=None, help="Results per page (optional)")
    p.add_argument("--status", default=None, help="Filter by status (e.g. completed)")
