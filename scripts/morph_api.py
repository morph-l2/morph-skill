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
import os
import sys
import re
import time
import requests
from decimal import Decimal

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RPC_URL = os.environ.get("MORPH_RPC_URL", "https://rpc.morph.network/")
EXPLORER_API = os.environ.get("MORPH_EXPLORER_API", "https://explorer-api.morph.network/api/v2")
DEX_API = os.environ.get("MORPH_DEX_API", "https://api.bulbaswap.io")
CHAIN_ID = int(os.environ.get("MORPH_CHAIN_ID", "2818"))
IDENTITY_REGISTRY = os.environ.get("MORPH_IDENTITY_REGISTRY", "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432")
REPUTATION_REGISTRY = os.environ.get("MORPH_REPUTATION_REGISTRY", "0x8004BAa17C55a88189AE136b182e5fdA19dE9b63")
CONTRACTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "contracts"))

NATIVE_TOKEN = "0x0000000000000000000000000000000000000000"

# ---------------------------------------------------------------------------
# Multi-chain token registry for bridge commands
# Source: bgw /swap-go/swapx/getTokenList
# Keys use original symbol casing from source. Native tokens use "".
# ---------------------------------------------------------------------------

BRIDGE_TOKENS = {
    "morph": {
        "ETH": "",
        "USDT.e": "0xc7D67A9cBB121b3b0b9c053DD9f469523243379A",
        "USDT": "0xe7cd86e13AC4309349F30B3435a9d337750fC82D",
        "USDC": "0xCfb1186F4e93D60E60a8bDd997427D1F33bc372B",
        "USDC.e": "0xe34c91815d7fc18A9e2148bcD4241d0a5848b693",
        "BGB": "0x389C08Bc23A7317000a1FD76c7c5B0cb0b4640b5",
        "BGB (old)": "0x55d1f1879969bdbB9960d269974564C58DBc3238",
        "KOALA": "0x051bc29e6d13671f6bcbd8be8bb7d889e0d89079",
        "BAI": "0xe2e7d83dfbd25407045fd061e4c17cc76007dead",
        "MX": "0x0beef4b01281d85492713a015d51fec5b6d14687",
        "BGLIFE": "0x341270fEc15C43c5F150fc648dB33890E54E1111",
        "WETH": "0x5300000000000000000000000000000000000011",
    },
    "eth": {
        "ETH": "",
        "USDT": "0xdac17f958d2ee523a2206206994597c13d831ec7",
        "USDC": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        "WBTC": "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599",
        "DAI": "0x6b175474e89094c44da98b954eedeac495271d0f",
        "BGB": "0x54D2252757e1672EEaD234D27B1270728fF90581",
        "LINK": "0x514910771af9ca656af840dff83e8264ecf986ca",
        "UNI": "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",
        "WTAO": "0x77e06c9eccf2e797fd462a92b6d7642ef85b0a44",
        "PRIME": "0xb23d80f5fefcddaa212212f028021b41ded428cf",
        "PEPE": "0x6982508145454ce325ddbe47a25d4ec3d2311933",
        "RNDR": "0x6de037ef9ad2725eb40118bb1702ebb27e4aeb24",
        "EIGEN": "0xec53bf9167f50cdeb3ae105f56099aaab9061f83",
        "NEIRO": "0x812ba41e071c7b7fa4ebcfb62df5f45f6fa853ee",
        "SPX": "0xe0f63a424a4439cbe457d80e4f4b51ad25b2c56c",
        "ONDO": "0xfaba6f8e4a5e8ab82f62fe7c39859fa577269be3",
        "INJ": "0xe28b3b32b6c345a34ff64674606124dd5aceca30",
        "FET": "0xaea46a60368a7bd060eec7df8cba43b7ef41ad85",
        "PAAL": "0x14fee680690900ba0cccfc76ad70fd1b95d10e16",
        "LDO": "0x5a98fcbea516cf06857215779fd812ca3bef1b32",
        "FLOKI": "0xcf0c122c6b73ff809c693db761e7baebe62b6a2e",
    },
    "base": {
        "ETH": "",
        "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "USDT": "0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2",
        "WETH": "0x4200000000000000000000000000000000000006",
        "DAI": "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
        "MOEW": "0x15aC90165f8B45A80534228BdCB124A011F62Fee",
        "VIRTUAL": "0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b",
        "cbBTC": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",
        "ROLL": "0xAb6363dA0C80cEF3Ae105Bd6241E30872355d021",
        "AERO": "0x940181a94a35a4569e4529a3cdfb74e38fd98631",
        "AVNT": "0x696F9436B67233384889472Cd7cD58A6fB5DF4f1",
        "ZORA": "0x1111111111166b7fe7bd91427724b487980afc69",
        "KTA": "0xc0634090F2Fe6c6d75e61Be2b949464aBB498973",
        "RECALL": "0x1f16e03C1a590818F47f6EE7bB16690b40D0671",
        "ELSA": "0x29cC30f9D113B356Ce408667aa6433589CeCBDcA",
        "ZEN": "0xf43eb8de897fbc7f2502483b2bef7bb9ea179229",
    },
    "matic": {
        "POL": "",
        "MATIC": "",  # alias for native
        "USDT0": "0xc2132d05d31c914a87c6611c10748aeb04b58e8f",
        "USDC": "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359",
        "WETH": "0x7ceb23fd6bc0add59e62ac25578270cff1b9f619",
        "WBTC": "0x1bfd67037b42cf73acf2047067bd4f2c47d9bfd6",
        "USDC.e": "0x2791bca1f2de4661ed88a30c99a7a9449aa84174",
        "QUICK": "0xb5c064f955d8e7f38fe0460c556a72987494ee17",
        "AAVE": "0xd6df932a45c0f255f85145f286ea0b292b21c90b",
        "LGNS": "0xeb51d9a39ad5eef215dc0bf39a8821ff804a0f01",
        "DAI": "0x8f3cf7ad23cd3cadbD9735AFf958023239c6a063",
        "APEPE": "0xA3f751662e282E83EC3cBc387d225Ca56dD63D3A",
        "IXT": "0xe06bd4f5aac8d0aa337d13ec88db6defc6eaeefe",
        "RNDR": "0x61299774020da444af134c82fa83e3810b309991",
        "LINK": "0x53e0bca35ec356bd5dddfebbd1fc0fd03fabad39",
        "GHST": "0x385eeac5cb85a38a9a07a70c73e0a3271cfb54a7",
        "VOXEL": "0xd0258a3fd00f38aa8090dfee343f10a9d4d30d3f",
        "GNS": "0xE5417Af564e4bFDA1c483642db72007871397896",
        "WIFI": "0xe238ecb42c424e877652ad82d8a939183a04c35f",
        "TEL": "0xdf7837de1f2fa4631d716cf2502f8b230f1dcc32",
        "LDO": "0xc3c7d422809852031b44ab29eec9f1eff2a58756",
    },
    "bnb": {
        "BNB": "",
        "USDT": "0x55d398326f99059ff775485246999027b3197955",
        "USDC": "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d",
        "BTCB": "0x7130d2a12b9bcbfae4f2634d864a1ee1ce3ead9c",
        "Cake": "0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82",
        "ETH": "0x2170ed0880ac9a755fd29b2688956bd959f933f8",
        "DOGE": "0xba2ae424d960c26247dd6c32edc70b295c744c43",
        "ADA": "0x3ee2200efb3400fabb9aacf31297cbdd1d435d47",
        "XRP": "0x1d2f0da169ceb9fc7b3144628db156f3f6c60dbe",
        "AIO": "0x81a7da4074b8e0ed51bea40f9dcbdf4d9d4832b4",
        "AT": "0x9be61A38725b265BC3eb7Bfdf17AfDFc9D26C130",
        "ASTER": "0x000Ae314E2A2172a039B26378814C252734f556A",
        "LIGHT": "0x477C2c0459004E3354Ba427FA285D7C053203c0E",
        "SKYAI": "0x92aa03137385f18539301349dcfc9ebc923ffb10",
        "RTX": "0x4829A1D1fB6DED1F81d26868ab8976648baF9893",
        "elizaOS": "0xea17df5cf6d172224892b5477a16acb111182478",
        "$AIAV": "0x76CC9E532Bb6803EFc3d7766ac16A884a015951f",
        "SENTIS": "0x8fd0d741e09a98e82256c63f25f90301ea71a83e",
        "PIEVERSE": "0x0E63B9C287E32A05E6b9AB8ee8dF88A2760225A9",
        "MYX": "0xD82544bf0dfe8385eF8FA34D67e6e4940CC63e16",
    },
    "arbitrum": {
        "ETH": "",
        "USDT0": "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9",
        "USDC": "0xaf88d065e77c8cc2239327c5edb3a432268e5831",
        "ARB": "0x912CE59144191C1204E64559FE8253a0e49E6548",
        "WBTC": "0x2f2a2543b76a4166549f7aab2e75bef0aefc5b0f",
        "GMX": "0xfc5a1a6eb076a2c7ad06ed22c90d7e710e35ad0a",
        "MAGIC": "0x539bdE0d7Dbd336b79148AA742883198BBF60342",
        "ZRO": "0x6985884C4392D348587B19cb9eAAf157F13271cd",
        "RDNT": "0x3082cc23568ea640225c2467653db90e9250aaa0",
        "VSN": "0x6fbbbd8bfb1cd3986b1d05e7861a0f62f87db74b",
        "PENDLE": "0x0c880f6761f1af8d9aa9c466984b80dab9a8c9e8",
        "ezETH": "0x2416092f143378750bb29b79eD961ab195cCEea5",
        "LINK": "0xf97f4df75117a78c1a5a0dbb814af92458539fb4",
        "MOR": "0x092bAaDB7DEf4C3981454dD9c0A0D7FF07bCFc86",
        "GRT": "0x9623063377ad1b27544c965ccd7342f7ea7e88c7",
        "XAI": "0x4Cb9a7AE498CEDcBb5EAe9f25736aE7d428C9D66",
        "GNS": "0x18c11fd286c5ec11c3b683caa813b77f5163a122",
    },
}

# Build case-insensitive lookup: {chain: {SYMBOL_UPPER: address}}
_BRIDGE_TOKENS_UPPER = {
    chain: {k.upper(): v for k, v in tokens.items()}
    for chain, tokens in BRIDGE_TOKENS.items()
}

# Morph ERC20 tokens for wallet/DEX commands (derived from BRIDGE_TOKENS, excludes native ETH)
KNOWN_TOKENS = {k: v for k, v in BRIDGE_TOKENS["morph"].items() if v}
_KNOWN_TOKENS_UPPER = {k.upper(): v for k, v in KNOWN_TOKENS.items()}

# address → symbol: derived from KNOWN_TOKENS (no duplicate address data)
_MORPH_TOKEN_ADDRESS_TO_SYMBOL = {v.lower(): k for k, v in KNOWN_TOKENS.items()}
# address → canonical display name (only data not available in KNOWN_TOKENS)
_MORPH_TOKEN_NAMES = {
    "0xc7d67a9cbb121b3b0b9c053dd9f469523243379a": "Tether Morph Bridged",
    "0xe7cd86e13ac4309349f30b3435a9d337750fc82d": "USDT",
    "0xcfb1186f4e93d60e60a8bdd997427d1f33bc372b": "USD Coin",
    "0xe34c91815d7fc18a9e2148bcd4241d0a5848b693": "USD Coin Morph Bridged",
    "0x389c08bc23a7317000a1fd76c7c5b0cb0b4640b5": "BitgetToken",
    "0x55d1f1879969bdbb9960d269974564c58dbc3238": "BitgetToken (old)",
    "0x5300000000000000000000000000000000000011": "Wrapped Ether",
}

ERC20_BALANCE_OF_SIG = "0x70a08231"
ERC20_DECIMALS_SIG   = "0x313ce567"
ERC20_TRANSFER_SIG   = "0xa9059cbb"

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

def rpc_call(method, params=None, allow_error=False):
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
        if allow_error:
            return body.get("result"), body.get("error")
        if "error" in body:
            _err(f"RPC error: {body['error']}")
        return body.get("result")
    except requests.RequestException as e:
        _err(f"RPC request failed: {e}")

# ---------------------------------------------------------------------------
# Helpers — RLP encoding (used by morph_7702.py and morph_altfee.py)
# ---------------------------------------------------------------------------

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
# Helpers — Bridge (Cross-Chain Swap)
# ---------------------------------------------------------------------------

def bridge_post(path, data):
    """POST request to Cross-Chain Swap API."""
    url = f"{DEX_API}{path}"
    try:
        r = requests.post(url, json=data, timeout=30)
        r.raise_for_status()
        resp = r.json()
        if resp.get("status") != 0:
            _err(f"Bridge API error {resp.get('error_code')}: {resp.get('msg')}")
        return resp.get("data")
    except requests.RequestException as e:
        _err(f"Bridge request failed: {e}")

def bridge_get(path):
    """GET request to Cross-Chain Swap API."""
    url = f"{DEX_API}{path}"
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        resp = r.json()
        if resp.get("status") != 0:
            _err(f"Bridge API error {resp.get('error_code')}: {resp.get('msg')}")
        return resp.get("data")
    except requests.RequestException as e:
        _err(f"Bridge request failed: {e}")

def _generate_auth_message(timestamp):
    """Generate Bulba auth message for signing."""
    return (
        "Welcome to Bulba.\n\n"
        "Please sign this message to verify your wallet.\n\n"
        f"Timestamp: {timestamp}.\n\n"
        "Your authentication status will be reset after 24 hours."
    )

def bridge_post_auth(path, data, token):
    """POST request to Bridge API with JWT auth."""
    url = f"{DEX_API}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.post(url, json=data, headers=headers, timeout=30)
        r.raise_for_status()
        resp = r.json()
        if resp.get("status") != 0:
            _err(f"Bridge API error {resp.get('error_code')}: {resp.get('msg')}")
        return resp.get("data")
    except requests.RequestException as e:
        _err(f"Bridge request failed: {e}")

# ---------------------------------------------------------------------------
# Helpers — Token utilities
# ---------------------------------------------------------------------------

_HEX_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")

def resolve_token(symbol_or_address):
    """Resolve a token symbol or contract address.

    - 'ETH' or '' → native token (zero address)
    - '0x...' (42 hex chars) → validated and used as-is
    - known symbol (e.g. 'USDT') → looked up from verified list
    """
    if symbol_or_address == "" or symbol_or_address.upper() == "ETH":
        return NATIVE_TOKEN
    if symbol_or_address.startswith("0x"):
        if not _HEX_ADDRESS_RE.match(symbol_or_address):
            _err(f"Invalid address: {symbol_or_address}. Must be 0x followed by 40 hex characters.")
        return symbol_or_address
    upper = symbol_or_address.upper()
    if upper in _KNOWN_TOKENS_UPPER:
        return _KNOWN_TOKENS_UPPER[upper]
    _err(f"Unknown token: {symbol_or_address}. Known symbols: {', '.join(['ETH'] + list(KNOWN_TOKENS.keys()))}. Or pass a contract address (0x...).")

def _normalize_morph_token_meta(address, symbol=None, name=None):
    """Normalize Morph token metadata to business-layer symbol/name."""
    if not address:
        return symbol, name
    key = address.lower()
    return (
        _MORPH_TOKEN_ADDRESS_TO_SYMBOL.get(key, symbol),
        _MORPH_TOKEN_NAMES.get(key, name),
    )

def _normalize_morph_token_item(token_info, address_key="address_hash"):
    """Return a token-info dict with business-layer symbol/name when known."""
    item = dict(token_info or {})
    item["symbol"], item["name"] = _normalize_morph_token_meta(
        item.get(address_key),
        item.get("symbol"),
        item.get("name"),
    )
    return item

def _normalize_morph_explorer_items(data):
    """Normalize `items` arrays returned by explorer token endpoints."""
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return data
    normalized = dict(data)
    normalized["items"] = [_normalize_morph_token_item(item) for item in data["items"]]
    return normalized

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
    result = int(Decimal(amount_str) * Decimal(10**decimals))
    if result < 0:
        _err(f"Amount must not be negative, got: {amount_str}")
    return result

def validate_address(addr):
    """Validate an Ethereum address (0x + 40 hex chars). Returns the address or calls _err."""
    if not _HEX_ADDRESS_RE.match(addr):
        _err(f"Invalid address: {addr}. Must be 0x followed by 40 hex characters.")
    return addr

def pad_address(addr):
    """Left-pad a validated address to 32 bytes for ABI encoding."""
    validate_address(addr)
    return "0x" + addr.lower().replace("0x", "").zfill(64)

def _load_account(private_key):
    """Load an Account from a private key, returning JSON error on invalid input."""
    try:
        from eth_account import Account
    except ImportError:
        _err("eth_account is required: pip install eth_account")
    try:
        return Account.from_key(private_key)
    except Exception as e:
        _err(f"Invalid private key: {e}")

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
    for _ in range(retries):
        receipt = rpc_call("eth_getTransactionReceipt", [tx_hash])
        if receipt is not None:
            return receipt
        time.sleep(2)
    return None

# ERC-721 Transfer event: Transfer(address indexed from, address indexed to, uint256 indexed tokenId)
_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

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

    _require_altfee_selection(args.fee_token_id, args.fee_limit, args.gas_limit)
    if args.fee_token_id is not None:
        sender, tx_hash, gas, fee_limit = _send_contract_tx_altfee(
            IDENTITY_REGISTRY,
            calldata,
            args.private_key,
            args.fee_token_id,
            fee_limit=args.fee_limit,
            gas_limit=args.gas_limit,
        )
    else:
        sender, tx_hash, gas = _send_contract_tx(IDENTITY_REGISTRY, calldata, args.private_key)
        fee_limit = None

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
    if args.fee_token_id is not None:
        result["fee_token_id"] = args.fee_token_id
        result["fee_limit"] = str(fee_limit)
        result["type"] = "0x7f"
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
    _require_altfee_selection(args.fee_token_id, args.fee_limit, args.gas_limit)
    if args.fee_token_id is not None:
        sender, tx_hash, gas, fee_limit = _send_contract_tx_altfee(
            REPUTATION_REGISTRY,
            calldata,
            args.private_key,
            args.fee_token_id,
            fee_limit=args.fee_limit,
            gas_limit=args.gas_limit,
        )
    else:
        sender, tx_hash, gas = _send_contract_tx(REPUTATION_REGISTRY, calldata, args.private_key)
        fee_limit = None
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
    if args.fee_token_id is not None:
        result["fee_token_id"] = args.fee_token_id
        result["fee_limit"] = str(fee_limit)
        result["type"] = "0x7f"
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

# ---------------------------------------------------------------------------
# CLI — argparse
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="morph_api",
        description="Morph Mainnet CLI — wallet, explorer, agent, DEX, bridge, alt-fee, and EIP-7702 operations",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # -- Wallet (from morph_wallet.py) ----------------------------------------
    from morph_wallet import register_wallet_commands
    register_wallet_commands(sub)

    # -- Explorer (from morph_explorer.py) ------------------------------------
    from morph_explorer import register_explorer_commands
    register_explorer_commands(sub)

    # -- Agent ----------------------------------------------------------------
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

    # -- DEX (from morph_dex.py) ----------------------------------------------
    from morph_dex import register_dex_commands
    register_dex_commands(sub)

    # -- Bridge (from morph_bridge.py) ----------------------------------------
    from morph_bridge import register_bridge_commands
    register_bridge_commands(sub)

    # -- Alt-Fee (from morph_altfee.py) ---------------------------------------
    from morph_altfee import register_altfee_commands
    register_altfee_commands(sub)

    # -- EIP-7702 (from morph_7702.py) ----------------------------------------
    from morph_7702 import register_7702_commands
    register_7702_commands(sub)

    return parser

def main():
    parser = build_parser()
    args = parser.parse_args()
    handler = getattr(args, "handler", None)
    if handler is None:
        _err(f"Unknown command: {args.command}")
    try:
        handler(args)
    except SystemExit:
        raise  # let _ok/_err exits pass through
    except Exception as e:
        _err(f"{type(e).__name__}: {e}")

if __name__ == "__main__":
    main()
