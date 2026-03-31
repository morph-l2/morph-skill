#!/usr/bin/env python3
"""
morph_x402.py — x402 HTTP payment protocol for Morph L2.

Client-side: discover and pay for x402-protected resources with USDC.
Merchant-side: register for HMAC credentials, verify and settle payments.

Exports register_x402_commands(sub) called by morph_api.build_parser().
"""

import base64
import hashlib
import hmac as _hmac
import json
import os
import time

from morph_api import (
    _ok,
    _err,
    _load_account,
    CHAIN_ID,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

X402_FACILITATOR_BASE = "https://morph-rails.morph.network/x402"
X402_USDC_ADDRESS = "0xCfb1186F4e93D60E60a8bDd997427D1F33bc372B"
X402_USDC_DECIMALS = 6
X402_NETWORK = "eip155:2818"
X402_DEFAULT_MAX_USDC = 1.0

CREDENTIALS_DIR = os.path.expanduser("~/.morph-agent/x402-credentials")
ENCRYPTION_KEY_PATH = os.path.expanduser("~/.morph-agent/.encryption-key")

# ---------------------------------------------------------------------------
# Helpers — USDC amounts
# ---------------------------------------------------------------------------

def _usdc_to_raw(human: str) -> int:
    """Convert human-readable USDC (e.g. '1.0') to raw 6-decimal int (1000000)."""
    from decimal import Decimal
    return int(Decimal(str(human)) * Decimal(10 ** X402_USDC_DECIMALS))


def _usdc_from_raw(raw: str) -> str:
    """Convert raw USDC int string to human-readable (e.g. '1000000' → '1.0')."""
    from decimal import Decimal
    val = Decimal(str(raw)) / Decimal(10 ** X402_USDC_DECIMALS)
    s = str(val)
    if "." not in s:
        s += ".0"
    return s


# ---------------------------------------------------------------------------
# Helpers — HMAC auth for Facilitator
# ---------------------------------------------------------------------------

def _sort_object(obj):
    """Recursively sort dict keys lexicographically (for HMAC sign map)."""
    if isinstance(obj, dict):
        return {k: _sort_object(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_sort_object(i) for i in obj]
    return obj


def _x402_hmac_headers(method, path, body, access_key, secret_key, timestamp_ms=None):
    """Build HMAC-SHA256 signed headers for Facilitator API requests."""
    ts = timestamp_ms or str(int(time.time() * 1000))
    sign_map = _sort_object({
        "MORPH-ACCESS-BODY": body,
        "MORPH-ACCESS-KEY": access_key,
        "MORPH-ACCESS-METHOD": method.upper(),
        "MORPH-ACCESS-PATH": path,
        "MORPH-ACCESS-TIMESTAMP": ts,
    })
    content = json.dumps(sign_map, separators=(",", ":"), ensure_ascii=False)
    sig = base64.b64encode(
        _hmac.new(secret_key.encode(), content.encode(), hashlib.sha256).digest()
    ).decode()
    return {
        "Content-Type": "application/json",
        "MORPH-ACCESS-KEY": access_key,
        "MORPH-ACCESS-TIMESTAMP": ts,
        "MORPH-ACCESS-SIGN": sig,
    }


# ---------------------------------------------------------------------------
# Helpers — AES-256-GCM credential encryption
# ---------------------------------------------------------------------------

def _get_or_create_encryption_key(key_path=None):
    """Get or create the 32-byte master encryption key."""
    key_path = key_path or ENCRYPTION_KEY_PATH
    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            return f.read()
    key = os.urandom(32)
    os.makedirs(os.path.dirname(key_path), exist_ok=True)
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(key)
    return key


def _encrypt_credential(plaintext, key_path=None):
    """AES-256-GCM encrypt a string. Returns dict with nonce, ciphertext, tag."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key = _get_or_create_encryption_key(key_path)
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return {
        "nonce": nonce.hex(),
        "ciphertext": ct[:-16].hex(),
        "tag": ct[-16:].hex(),
    }


def _decrypt_credential(enc, key_path=None):
    """AES-256-GCM decrypt. Input is dict with nonce, ciphertext, tag."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key_path = key_path or ENCRYPTION_KEY_PATH
    if not os.path.exists(key_path):
        _err(f"encryption key not found at {key_path}")
    with open(key_path, "rb") as f:
        key = f.read()
    nonce = bytes.fromhex(enc["nonce"])
    ct_with_tag = bytes.fromhex(enc["ciphertext"]) + bytes.fromhex(enc["tag"])
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct_with_tag, None).decode()


# ---------------------------------------------------------------------------
# Helpers — credential storage
# ---------------------------------------------------------------------------

def _save_credentials(name, address, access_key, secret_key, key_path=None):
    """Save merchant HMAC credentials to encrypted file."""
    os.makedirs(CREDENTIALS_DIR, exist_ok=True)
    os.chmod(CREDENTIALS_DIR, 0o700)
    data = {
        "name": name,
        "address": address,
        "access_key": access_key,
        "secret_key": _encrypt_credential(secret_key, key_path),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    path = os.path.join(CREDENTIALS_DIR, f"{name}.json")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
    return path


def _load_credentials(name, key_path=None):
    """Load merchant HMAC credentials. Returns (access_key, secret_key)."""
    path = os.path.join(CREDENTIALS_DIR, f"{name}.json")
    if not os.path.exists(path):
        _err(f"credentials not found: {name}. Run x402-register --save --name {name}")
    with open(path, "r") as f:
        data = json.load(f)
    access_key = data["access_key"]
    secret_key = _decrypt_credential(data["secret_key"], key_path)
    return access_key, secret_key


def _resolve_credentials(args, key_path=None):
    """Resolve merchant credentials from --name or --access-key/--secret-key."""
    name = getattr(args, "name", None)
    if name:
        return _load_credentials(name, key_path)
    ak = getattr(args, "access_key", None)
    sk = getattr(args, "secret_key", None)
    if ak and sk:
        return ak, sk
    _err("provide --name (saved credentials) or both --access-key and --secret-key")


# ---------------------------------------------------------------------------
# Helpers — EIP-3009 signing
# ---------------------------------------------------------------------------

def _x402_nonce(address, timestamp_ms=None):
    """Generate x402 payment nonce: keccak256(abi.encode(address, timestamp_ms))."""
    from eth_abi import encode as abi_encode
    from eth_hash.auto import keccak
    ts = timestamp_ms or int(time.time() * 1000)
    packed = abi_encode(["address", "uint256"], [address, ts])
    return keccak(packed)


def _sign_eip3009(acct, requirements):
    """Sign EIP-3009 TransferWithAuthorization for x402 payment.

    Returns (payment_payload_dict, amount_raw).
    """
    extra = requirements.get("extra", {})
    domain = {
        "name": extra.get("name", "USDC"),
        "version": extra.get("version", "2"),
        "chainId": CHAIN_ID,
        "verifyingContract": X402_USDC_ADDRESS,
    }
    amount_raw = int(requirements.get("maxAmountRequired")
                     or requirements.get("amount")
                     or requirements.get("price", "0"))
    valid_before = int(time.time()) + 3600
    nonce = _x402_nonce(acct.address)

    types = {
        "TransferWithAuthorization": [
            {"name": "from", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "validAfter", "type": "uint256"},
            {"name": "validBefore", "type": "uint256"},
            {"name": "nonce", "type": "bytes32"},
        ]
    }
    message = {
        "from": acct.address,
        "to": requirements["payTo"],
        "value": amount_raw,
        "validAfter": 0,
        "validBefore": valid_before,
        "nonce": nonce,
    }
    signed = acct.sign_typed_data(domain, types, message)

    payload = {
        "x402Version": 2,
        "payload": {
            "signature": "0x" + signed.signature.hex(),
            "authorization": {
                "from": acct.address,
                "to": requirements["payTo"],
                "value": str(amount_raw),
                "validAfter": "0",
                "validBefore": str(valid_before),
                "nonce": "0x" + nonce.hex(),
            },
        },
        "accepted": requirements,
        "resource": {"url": requirements.get("resource", "")},
    }
    return payload, amount_raw


# ---------------------------------------------------------------------------
# Helpers — HTTP
# ---------------------------------------------------------------------------

def _facilitator_get(path):
    """GET request to Facilitator (no auth)."""
    import requests
    url = X402_FACILITATOR_BASE + path
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        _err(f"facilitator request failed: {e}")


def _facilitator_post(path, body, access_key, secret_key):
    """POST request to Facilitator with HMAC auth."""
    import requests
    url = X402_FACILITATOR_BASE + path
    headers = _x402_hmac_headers("POST", "/x402" + path, body, access_key, secret_key)
    try:
        r = requests.post(url, json=body, headers=headers, timeout=30)
        data = r.json()
        if not r.ok:
            reason = (data.get("invalidReason") or data.get("errorReason")
                      or data.get("message") or data.get("error") or str(data))
            _err(f"facilitator error: {reason}")
        return data
    except Exception as e:
        _err(f"facilitator request failed: {e}")


def _facilitator_post_raw(path, body, access_key, secret_key):
    """POST to Facilitator with HMAC auth — returns dict, raises on error (no sys.exit)."""
    import requests
    url = X402_FACILITATOR_BASE + path
    headers = _x402_hmac_headers("POST", "/x402" + path, body, access_key, secret_key)
    r = requests.post(url, json=body, headers=headers, timeout=30)
    data = r.json()
    if not r.ok:
        reason = (data.get("invalidReason") or data.get("errorReason")
                  or data.get("message") or data.get("error") or str(data))
        raise RuntimeError(f"facilitator error: {reason}")
    return data


def _parse_402_requirements(response):
    """Extract PaymentRequirements from a 402 HTTP response."""
    try:
        body = response.json()
        if "accepts" in body and body["accepts"]:
            return body["accepts"][0]
    except Exception:
        pass
    header = response.headers.get("PAYMENT-REQUIRED", "")
    if header:
        try:
            decoded = json.loads(base64.b64decode(header))
            if "accepts" in decoded and decoded["accepts"]:
                return decoded["accepts"][0]
        except Exception:
            pass
    header = response.headers.get("X-PAYMENT", "")
    if header:
        try:
            decoded = json.loads(header)
            if "accepts" in decoded and decoded["accepts"]:
                return decoded["accepts"][0]
        except Exception:
            pass
    _err("could not parse x402 payment requirements from 402 response")


# ---------------------------------------------------------------------------
# Commands — x402
# ---------------------------------------------------------------------------

def cmd_x402_supported(_args):
    """Query Facilitator for supported schemes and networks."""
    data = _facilitator_get("/v2/supported")
    _ok(data)


def cmd_x402_discover(args):
    """Probe a URL for x402 payment requirements (does not pay)."""
    import requests
    url = args.url
    try:
        r = requests.get(url, timeout=15, allow_redirects=True)
    except Exception as e:
        _err(f"request failed: {e}")

    if r.status_code != 402:
        _ok({"requires_payment": False, "status": r.status_code})
        return

    req = _parse_402_requirements(r)
    amount_raw = req.get("maxAmountRequired") or req.get("amount") or req.get("price", "0")
    _ok({
        "requires_payment": True,
        "scheme": req.get("scheme"),
        "network": req.get("network"),
        "amount_usdc": _usdc_from_raw(amount_raw),
        "amount_raw": str(amount_raw),
        "asset": req.get("asset"),
        "pay_to": req.get("payTo"),
        "description": req.get("description", ""),
        "max_timeout_seconds": req.get("maxTimeoutSeconds"),
    })


def cmd_x402_pay(args):
    """Pay for and access an x402-protected resource with USDC."""
    import requests

    max_payment = float(args.max_payment) if args.max_payment else X402_DEFAULT_MAX_USDC
    acct = _load_account(args.private_key)

    # Step 1: Probe URL
    try:
        r = requests.get(args.url, timeout=15, allow_redirects=True)
    except Exception as e:
        _err(f"request failed: {e}")

    if r.status_code != 402:
        _ok({"status": r.status_code, "requires_payment": False, "content": r.text})
        return

    # Step 2: Parse requirements and check max_payment
    requirements = _parse_402_requirements(r)
    amount_raw = int(requirements.get("maxAmountRequired")
                     or requirements.get("amount")
                     or requirements.get("price", "0"))
    amount_usdc = float(_usdc_from_raw(str(amount_raw)))

    if amount_usdc > max_payment:
        _err(f"payment required: {amount_usdc} USDC exceeds --max-payment {max_payment} USDC")

    # Step 3: Sign EIP-3009
    payload, _ = _sign_eip3009(acct, requirements)

    # Step 4: Replay request with payment header
    header_value = base64.b64encode(json.dumps(payload).encode()).decode()
    try:
        r2 = requests.get(args.url, headers={"PAYMENT-SIGNATURE": header_value}, timeout=30)
    except Exception as e:
        _err(f"payment replay failed: {e}")

    if r2.status_code != 200:
        _err(f"payment rejected: HTTP {r2.status_code} — {r2.text[:500]}")

    try:
        content = r2.json()
    except Exception:
        content = r2.text

    _ok({
        "status": r2.status_code,
        "amount_paid_usdc": _usdc_from_raw(str(amount_raw)),
        "pay_to": requirements.get("payTo"),
        "content": content,
    })


def cmd_x402_register(args):
    """Register with x402 Facilitator to get merchant HMAC credentials."""
    import requests
    from eth_account.messages import encode_defunct

    acct = _load_account(args.private_key)
    address = acct.address

    # Step 1: Get nonce
    try:
        r = requests.get(f"{X402_FACILITATOR_BASE}/auth/nonce",
                         params={"address": address}, timeout=15)
        r.raise_for_status()
        nonce_data = r.json()
    except Exception as e:
        _err(f"failed to get nonce: {e}")

    if nonce_data.get("code", 0) != 0:
        _err(f"nonce error: {nonce_data.get('message', str(nonce_data))}")
    nonce_info = nonce_data.get("data", nonce_data)
    message = nonce_info["message"]
    nonce = nonce_info["nonce"]

    # Step 2: Sign message with EIP-191
    signed = acct.sign_message(encode_defunct(text=message))
    signature = "0x" + signed.signature.hex()

    # Step 3: Login
    try:
        r = requests.post(f"{X402_FACILITATOR_BASE}/auth/login",
                          json={"address": address, "signature": signature, "nonce": nonce},
                          timeout=15)
        r.raise_for_status()
        login_data = r.json()
    except Exception as e:
        _err(f"login failed: {e}")

    if login_data.get("code", 0) != 0:
        _err(f"login error: {login_data.get('message', str(login_data))}")
    token = login_data.get("data", login_data).get("token")
    if not token:
        _err("login succeeded but no token returned")

    # Step 4: Create API key
    auth_headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        r = requests.post(f"{X402_FACILITATOR_BASE}/api-keys/create",
                          headers=auth_headers, json={}, timeout=15)
        key_data = r.json()
    except Exception as e:
        _err(f"failed to create API key: {e}")

    is_new = True
    if key_data.get("code") == 40005:
        is_new = False
        try:
            r = requests.get(f"{X402_FACILITATOR_BASE}/api-keys/detail",
                             headers=auth_headers, timeout=15)
            detail = r.json()
            key_info = detail.get("data", detail)
        except Exception as e:
            _err(f"key exists but failed to fetch details: {e}")
    elif key_data.get("code", 0) != 0:
        _err(f"create key error: {key_data.get('message', str(key_data))}")
    else:
        key_info = key_data.get("data", key_data)

    access_key = key_info.get("accessKey", "")
    secret_key = key_info.get("secretKey", "")

    saved = False
    name = getattr(args, "name", None)
    if getattr(args, "save", False) and not name:
        _err("--save requires --name: provide a credential name to save under")
    if getattr(args, "save", False) and name:
        if not secret_key:
            _err("cannot save: secretKey not available (key was previously created). "
                 "secretKey is only shown once at first creation.")
        _save_credentials(name, address, access_key, secret_key)
        saved = True

    result = {
        "access_key": access_key,
        "address": address,
        "is_new": is_new,
    }
    if secret_key:
        result["secret_key"] = secret_key
    else:
        result["secret_key_note"] = "not available — only shown on first creation"
    if saved:
        result["saved"] = True
        result["name"] = name

    _ok(result)


def cmd_x402_verify(args):
    """Verify an x402 payment signature (merchant-side, no on-chain action)."""
    try:
        payload = json.loads(args.payload)
    except (json.JSONDecodeError, TypeError) as e:
        _err(f"invalid --payload JSON: {e}")
    try:
        requirements = json.loads(args.requirements)
    except (json.JSONDecodeError, TypeError) as e:
        _err(f"invalid --requirements JSON: {e}")

    access_key, secret_key = _resolve_credentials(args)
    body = {
        "x402Version": 2,
        "paymentPayload": payload,
        "paymentRequirements": requirements,
    }
    result = _facilitator_post("/v2/verify", body, access_key, secret_key)
    _ok({
        "is_valid": result.get("isValid", False),
        "payer": result.get("payer"),
        "invalid_reason": result.get("invalidReason"),
    })


def cmd_x402_settle(args):
    """Settle an x402 payment on-chain (merchant-side, triggers USDC transfer)."""
    try:
        payload = json.loads(args.payload)
    except (json.JSONDecodeError, TypeError) as e:
        _err(f"invalid --payload JSON: {e}")
    try:
        requirements = json.loads(args.requirements)
    except (json.JSONDecodeError, TypeError) as e:
        _err(f"invalid --requirements JSON: {e}")

    access_key, secret_key = _resolve_credentials(args)
    body = {
        "x402Version": 2,
        "paymentPayload": payload,
        "paymentRequirements": requirements,
    }
    result = _facilitator_post("/v2/settle", body, access_key, secret_key)
    _ok({
        "settled": result.get("success", False),
        "tx_hash": result.get("transaction"),
        "payer": result.get("payer"),
        "network": result.get("network"),
        "error_reason": result.get("errorReason"),
    })


def cmd_x402_server(args):
    """Start a local x402 merchant test server."""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import threading

    pay_to = args.pay_to
    price_raw = _usdc_to_raw(args.price)
    port = args.port
    paid_path = args.path
    dev_mode = args.dev

    # Resolve credentials for verified mode
    creds = None
    if not dev_mode:
        try:
            ak, sk = _resolve_credentials(args)
            creds = (ak, sk)
        except SystemExit:
            _err("verified mode requires credentials. Use --name <saved> or --access-key/--secret-key, or add --dev for structural check only")

    requirements = {
        "scheme": "exact",
        "network": X402_NETWORK,
        "maxAmountRequired": str(price_raw),
        "resource": f"http://localhost:{port}{paid_path}",
        "description": "x402 protected resource",
        "mimeType": "application/json",
        "payTo": pay_to,
        "maxTimeoutSeconds": 15,
        "asset": X402_USDC_ADDRESS,
        "extra": {"name": "USDC", "version": "2"},
    }

    class X402Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            # CORS
            if self.path == "/api/free":
                self._respond(200, {"message": "This is free content", "path": self.path})
                return

            if self.path != paid_path:
                self._respond(404, {"error": "not found"})
                return

            # Check for payment header
            payment_b64 = self.headers.get("PAYMENT-SIGNATURE", "")
            payment_raw = self.headers.get("X-PAYMENT", "")

            if not payment_b64 and not payment_raw:
                # Return 402
                body = json.dumps({
                    "x402Version": 2,
                    "accepts": [requirements],
                    "error": "Payment Required",
                }).encode()
                self.send_response(402)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
                return

            # Parse payment
            try:
                if payment_b64:
                    payment = json.loads(base64.b64decode(payment_b64))
                else:
                    payment = json.loads(payment_raw)
            except Exception as e:
                self._respond(400, {"error": f"invalid payment: {e}"})
                return

            if dev_mode:
                # Dev mode: structural check only
                payload = payment.get("payload", {})
                auth = payload.get("authorization", {})
                if not payload.get("signature") or not auth.get("from") or not auth.get("to"):
                    self._respond(402, {"error": "payment structurally invalid"})
                    return
                if auth.get("to", "").lower() != pay_to.lower():
                    self._respond(402, {"error": f"payment to wrong address: {auth.get('to')} != {pay_to}"})
                    return
                print(f"[dev] payment accepted from {auth.get('from')} — structural check only")
                self._respond(200, {
                    "message": "Payment accepted (dev mode — not verified on-chain)",
                    "path": self.path,
                    "payTo": pay_to,
                    "priceUsdc": args.price,
                })
                return

            # Verified mode: verify + settle via Facilitator
            try:
                ak, sk = creds
                verify_body = {
                    "x402Version": 2,
                    "paymentPayload": payment,
                    "paymentRequirements": requirements,
                }
                verify_result = _facilitator_post_raw("/v2/verify", verify_body, ak, sk)
                if not verify_result.get("isValid"):
                    self._respond(402, {"error": f"payment invalid: {verify_result.get('invalidReason')}"})
                    return

                settle_result = _facilitator_post_raw("/v2/settle", verify_body, ak, sk)
                if not settle_result.get("success"):
                    self._respond(402, {"error": f"settlement failed: {settle_result.get('errorReason')}"})
                    return

                tx = settle_result.get("transaction", "")
                print(f"[verified] payment settled — tx: {tx}")
                self._respond(200, {
                    "message": "Payment accepted and settled on-chain",
                    "path": self.path,
                    "payTo": pay_to,
                    "priceUsdc": args.price,
                    "txHash": tx,
                })
            except Exception as e:
                self._respond(500, {"error": str(e)})

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-PAYMENT, PAYMENT-SIGNATURE")
            self.end_headers()

        def _respond(self, code, data):
            body = json.dumps(data, indent=2).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            # Suppress default access log, print our own
            pass

    # Need a non-exiting version of _facilitator_post for server context
    # (can't call sys.exit inside a request handler)

    server = HTTPServer(("", port), X402Handler)
    mode_label = "dev (structural check)" if dev_mode else "verified (Facilitator)"
    print(json.dumps({
        "success": True,
        "data": {
            "message": f"x402 server running on http://localhost:{port}",
            "paid_path": paid_path,
            "free_path": "/api/free",
            "pay_to": pay_to,
            "price_usdc": args.price,
            "mode": mode_label,
        }
    }, indent=2), flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


def register_x402_commands(sub):
    """Register x402 subcommands — called by morph_api.build_parser()."""
    p = sub.add_parser("x402-supported", help="Query x402 Facilitator for supported schemes")
    p.set_defaults(handler=cmd_x402_supported)

    p = sub.add_parser("x402-discover", help="Probe a URL for x402 payment requirements")
    p.set_defaults(handler=cmd_x402_discover)
    p.add_argument("--url", required=True, help="URL to probe")

    p = sub.add_parser("x402-pay", help="Pay for an x402-protected resource with USDC")
    p.set_defaults(handler=cmd_x402_pay)
    p.add_argument("--url", required=True, help="URL to pay for and access")
    p.add_argument("--private-key", required=True, help="Payer private key (must have USDC)")
    p.add_argument("--max-payment", default=None,
                   help=f"Max USDC to pay (default: {X402_DEFAULT_MAX_USDC})")

    p = sub.add_parser("x402-register",
                       help="Register with Facilitator to get merchant HMAC credentials")
    p.set_defaults(handler=cmd_x402_register)
    p.add_argument("--private-key", required=True, help="Wallet private key for signing")
    p.add_argument("--save", action="store_true",
                   help="Encrypt and save credentials locally")
    p.add_argument("--name", default=None,
                   help="Credential name for storage (required with --save)")

    # -- merchant: credential args helper
    def _add_cred_args(parser):
        parser.add_argument("--name", default=None,
                           help="Saved credential name (from x402-register --save)")
        parser.add_argument("--access-key", default=None, help="HMAC access key (morph_ak_...)")
        parser.add_argument("--secret-key", default=None, help="HMAC secret key (morph_sk_...)")

    p = sub.add_parser("x402-verify", help="Verify an x402 payment signature (merchant)")
    p.set_defaults(handler=cmd_x402_verify)
    p.add_argument("--payload", required=True, help="Payment payload JSON")
    p.add_argument("--requirements", required=True, help="Payment requirements JSON")
    _add_cred_args(p)

    p = sub.add_parser("x402-settle",
                       help="Settle an x402 payment on-chain (merchant, USDC transfer)")
    p.set_defaults(handler=cmd_x402_settle)
    p.add_argument("--payload", required=True, help="Payment payload JSON")
    p.add_argument("--requirements", required=True, help="Payment requirements JSON")
    _add_cred_args(p)

    p = sub.add_parser("x402-server", help="Start a local x402 merchant test server")
    p.set_defaults(handler=cmd_x402_server)
    p.add_argument("--pay-to", required=True, help="Merchant wallet address to receive USDC")
    p.add_argument("--price", default="0.001", help="Price in USDC per request (default: 0.001)")
    p.add_argument("--port", type=int, default=8402, help="Server port (default: 8402)")
    p.add_argument("--path", default="/api/resource", help="Paid endpoint path (default: /api/resource)")
    p.add_argument("--dev", action="store_true", help="Dev mode: structural check only, no Facilitator calls")
    p.add_argument("--name", default=None, help="Saved credential name (for verified mode)")
    p.add_argument("--access-key", default=None, help="HMAC access key (for verified mode)")
    p.add_argument("--secret-key", default=None, help="HMAC secret key (for verified mode)")
