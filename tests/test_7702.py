# tests/test_7702.py
"""Unit tests for morph_7702 pure crypto functions."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from morph_7702 import (
    _compute_auth_hash,
    _serialize_7702_tx,
    SIMPLE_DELEGATION,
    AUTH_MAGIC_BYTE,
    EIP7702_TYPE_BYTE,
)


def test_compute_auth_hash_deterministic():
    """Same inputs must produce the same hash."""
    h1 = _compute_auth_hash(2818, SIMPLE_DELEGATION, 5)
    h2 = _compute_auth_hash(2818, SIMPLE_DELEGATION, 5)
    assert h1 == h2
    assert len(h1) == 32  # keccak256 is 32 bytes


def test_compute_auth_hash_different_nonce():
    """Different nonces must produce different hashes."""
    h1 = _compute_auth_hash(2818, SIMPLE_DELEGATION, 0)
    h2 = _compute_auth_hash(2818, SIMPLE_DELEGATION, 1)
    assert h1 != h2


def test_compute_auth_hash_different_chain():
    """Different chain IDs must produce different hashes."""
    h_mainnet = _compute_auth_hash(2818, SIMPLE_DELEGATION, 0)
    h_testnet = _compute_auth_hash(2910, SIMPLE_DELEGATION, 0)
    assert h_mainnet != h_testnet


def test_serialize_7702_tx_type_prefix():
    """Serialized tx must start with 0x04 type byte."""
    tx = {
        "chainId": 2818,
        "nonce": 0,
        "maxFeePerGas": 1_000_000_000,
        "gas": 21000,
        "to": "0x" + "ab" * 20,
        "value": 0,
        "data": "0x",
    }
    auth_list = [{
        "chainId": 2818,
        "contract": SIMPLE_DELEGATION,
        "nonce": 1,
        "y_parity": 0,
        "r": 1,
        "s": 1,
    }]
    raw = _serialize_7702_tx(tx, auth_list)
    assert raw[0] == EIP7702_TYPE_BYTE


def test_serialize_7702_tx_unsigned_vs_signed():
    """Signed tx must be longer than unsigned (has 3 extra RLP fields)."""
    tx = {
        "chainId": 2818,
        "nonce": 0,
        "maxFeePerGas": 1_000_000_000,
        "gas": 21000,
        "to": "0x" + "ab" * 20,
        "value": 0,
        "data": "0x",
    }
    auth_list = [{
        "chainId": 2818,
        "contract": SIMPLE_DELEGATION,
        "nonce": 1,
        "y_parity": 0,
        "r": 1,
        "s": 1,
    }]
    unsigned = _serialize_7702_tx(tx, auth_list)
    signed = _serialize_7702_tx(tx, auth_list, sig=(0, 12345, 67890))
    assert len(signed) > len(unsigned)


if __name__ == "__main__":
    test_compute_auth_hash_deterministic()
    test_compute_auth_hash_different_nonce()
    test_compute_auth_hash_different_chain()
    test_serialize_7702_tx_type_prefix()
    test_serialize_7702_tx_unsigned_vs_signed()
    print("All tests passed.")
