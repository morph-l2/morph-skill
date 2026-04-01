import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import morph_7702


class Morph7702Tests(unittest.TestCase):
    def test_cmd_7702_send_routes_single_call_through_execute(self):
        acct = SimpleNamespace(address="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        delegate_addr = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        args = SimpleNamespace(
            to="0x1111111111111111111111111111111111111111",
            value="0.5",
            data="0xdead",
            private_key="0xkey",
            delegate=delegate_addr,
            gas=None,
        )

        with patch.object(morph_7702, "validate_address") as validate_address, \
             patch.object(morph_7702, "to_wei", return_value=123) as to_wei, \
             patch.object(morph_7702, "_hex_to_bytes", return_value=b"\xde\xad") as hex_to_bytes, \
             patch.object(morph_7702, "_load_account", return_value=acct) as load_account, \
             patch.object(morph_7702, "_send_delegated_execute", return_value="0xtxhash") as send_execute, \
             patch.object(morph_7702, "_ok") as ok:
            morph_7702.cmd_7702_send(args)

        validate_address.assert_any_call(args.to)
        validate_address.assert_any_call(delegate_addr)
        to_wei.assert_called_once_with(args.value)
        hex_to_bytes.assert_called_once_with(args.data)
        load_account.assert_called_once_with(args.private_key)
        send_execute.assert_called_once_with(
            acct,
            args.private_key,
            delegate_addr,
            [(args.to, 123, b"\xde\xad")],
            gas=None,
            gas_fallback=morph_7702.GAS_FALLBACK_SEND,
        )
        ok.assert_called_once_with({"tx_hash": "0xtxhash", "calls_count": 1})

    def test_send_delegated_execute_targets_eoa(self):
        acct = SimpleNamespace(address="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        delegate_addr = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        calls_tuples = [("0x1111111111111111111111111111111111111111", 1, b"\xaa")]
        auth = {
            "chainId": morph_7702.CHAIN_ID,
            "contract": delegate_addr,
            "nonce": 6,
            "y_parity": 0,
            "r": 1,
            "s": 2,
        }

        with patch.object(morph_7702, "_build_execute_calldata", return_value="0xexecute") as build_execute, \
             patch.object(morph_7702, "_sign_auth", return_value=auth) as sign_auth, \
             patch.object(morph_7702, "_estimate_gas_7702", return_value=654321) as estimate_gas, \
             patch.object(morph_7702, "_sign_7702_tx", return_value="0xsigned") as sign_tx, \
             patch.object(morph_7702, "rpc_call", side_effect=["0x5", "0xa", "0xtxhash"]) as rpc_call:
            tx_hash = morph_7702._send_delegated_execute(
                acct,
                "0xkey",
                delegate_addr,
                calls_tuples,
                gas=None,
                gas_fallback=123,
            )

        self.assertEqual(tx_hash, "0xtxhash")
        build_execute.assert_called_once_with(acct, calls_tuples, acct.address)
        sign_auth.assert_called_once_with("0xkey", morph_7702.CHAIN_ID, delegate_addr, 6)
        estimate_gas.assert_called_once_with(acct.address, acct.address, 0, "0xexecute", 123)
        tx_arg, auth_list, private_key = sign_tx.call_args.args
        self.assertEqual(tx_arg["to"], acct.address)
        self.assertEqual(tx_arg["value"], 0)
        self.assertEqual(tx_arg["data"], "0xexecute")
        self.assertEqual(auth_list, [auth])
        self.assertEqual(private_key, "0xkey")
        self.assertEqual(rpc_call.call_args_list[-1].args, ("eth_sendRawTransaction", ["0xsigned"]))


if __name__ == "__main__":
    unittest.main()
