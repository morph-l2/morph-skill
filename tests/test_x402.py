# tests/test_x402.py
"""Unit tests for morph_x402 pure functions."""

import sys, os, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def test_sort_object_flat():
    from morph_x402 import _sort_object
    result = _sort_object({"z": 1, "a": 2, "m": 3})
    keys = list(result.keys())
    assert keys == ["a", "m", "z"]


def test_sort_object_nested():
    from morph_x402 import _sort_object
    result = _sort_object({"b": {"z": 1, "a": 2}, "a": 3})
    keys = list(result.keys())
    assert keys == ["a", "b"]
    inner_keys = list(result["b"].keys())
    assert inner_keys == ["a", "z"]


def test_usdc_to_raw():
    from morph_x402 import _usdc_to_raw
    assert _usdc_to_raw("1.0") == 1_000_000
    assert _usdc_to_raw("0.001") == 1_000
    assert _usdc_to_raw("0") == 0


def test_usdc_from_raw():
    from morph_x402 import _usdc_from_raw
    assert _usdc_from_raw("1000000") == "1.0"
    assert _usdc_from_raw("1000") == "0.001"
    assert _usdc_from_raw("0") == "0.0"


def test_x402_nonce_is_32_bytes():
    from morph_x402 import _x402_nonce
    nonce = _x402_nonce("0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266")
    assert isinstance(nonce, bytes)
    assert len(nonce) == 32


def test_x402_nonce_deterministic_same_ms():
    """Same address + same timestamp → same nonce."""
    from morph_x402 import _x402_nonce
    n1 = _x402_nonce("0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266", timestamp_ms=1000)
    n2 = _x402_nonce("0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266", timestamp_ms=1000)
    assert n1 == n2


def test_encrypt_decrypt_roundtrip():
    from morph_x402 import _encrypt_credential, _decrypt_credential
    tmpdir = tempfile.mkdtemp()
    key_path = os.path.join(tmpdir, ".encryption-key")
    try:
        original = "morph_sk_test_secret_key_123"
        enc = _encrypt_credential(original, key_path=key_path)
        assert "nonce" in enc
        assert "ciphertext" in enc
        assert "tag" in enc
        dec = _decrypt_credential(enc, key_path=key_path)
        assert dec == original
    finally:
        shutil.rmtree(tmpdir)


def test_hmac_headers_structure():
    from morph_x402 import _x402_hmac_headers
    headers = _x402_hmac_headers(
        "POST", "/x402/v2/verify", {"test": "data"},
        "morph_ak_test", "morph_sk_test",
        timestamp_ms="1000000000000",
    )
    assert headers["MORPH-ACCESS-KEY"] == "morph_ak_test"
    assert headers["MORPH-ACCESS-TIMESTAMP"] == "1000000000000"
    assert "MORPH-ACCESS-SIGN" in headers
    assert headers["Content-Type"] == "application/json"


def test_hmac_headers_deterministic():
    """Same inputs → same HMAC signature."""
    from morph_x402 import _x402_hmac_headers
    h1 = _x402_hmac_headers("POST", "/x402/v2/verify", {"a": 1}, "ak", "sk", timestamp_ms="123")
    h2 = _x402_hmac_headers("POST", "/x402/v2/verify", {"a": 1}, "ak", "sk", timestamp_ms="123")
    assert h1["MORPH-ACCESS-SIGN"] == h2["MORPH-ACCESS-SIGN"]


if __name__ == "__main__":
    test_sort_object_flat()
    test_sort_object_nested()
    test_usdc_to_raw()
    test_usdc_from_raw()
    test_x402_nonce_is_32_bytes()
    test_x402_nonce_deterministic_same_ms()
    test_encrypt_decrypt_roundtrip()
    test_hmac_headers_structure()
    test_hmac_headers_deterministic()
    print("All x402 tests passed.")
