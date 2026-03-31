# tests/test_cli_regression.py
"""Regression test: all CLI commands must remain registered after refactoring."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def _get_registered_commands():
    from morph_api import build_parser
    parser = build_parser()
    for action in parser._actions:
        if hasattr(action, "_name_parser_map"):
            return set(action._name_parser_map.keys())
    return set()


def test_all_commands_registered():
    registered = _get_registered_commands()
    expected = {
        # wallet (6)
        "create-wallet", "balance", "token-balance", "transfer",
        "transfer-token", "tx-receipt",
        # explorer (9)
        "address-info", "address-txs", "address-tokens", "tx-detail",
        "token-search", "contract-info", "token-transfers", "token-info", "token-list",
        # agent (6)
        "agent-register", "agent-wallet", "agent-metadata", "agent-reputation",
        "agent-feedback", "agent-reviews",
        # dex (2)
        "dex-quote", "dex-send",
        # bridge (11)
        "bridge-chains", "bridge-tokens", "bridge-token-search", "bridge-quote",
        "bridge-balance", "bridge-login", "bridge-make-order", "bridge-submit-order",
        "bridge-swap", "bridge-order", "bridge-history",
        # altfee (4)
        "altfee-tokens", "altfee-token-info", "altfee-estimate", "altfee-send",
        # 7702 (5)
        "7702-delegate", "7702-authorize", "7702-send", "7702-batch", "7702-revoke",
        # x402 (6)
        "x402-supported", "x402-discover", "x402-pay",
        "x402-register", "x402-verify", "x402-settle",
    }
    missing = expected - registered
    extra = registered - expected
    assert not missing, f"Missing commands after refactor: {sorted(missing)}"
    assert not extra, f"Unexpected extra commands: {sorted(extra)}"


if __name__ == "__main__":
    test_all_commands_registered()
    print("All 50 commands registered. OK.")
