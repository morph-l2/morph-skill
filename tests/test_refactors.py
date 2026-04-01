import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import morph_agent
import morph_x402


class MorphAgentRefactorTests(unittest.TestCase):
    def test_send_contract_tx_for_args_uses_altfee_path(self):
        args = SimpleNamespace(
            private_key="0xkey",
            fee_token_id=7,
            fee_limit=1234,
            gas_limit=5678,
        )

        with patch.object(morph_agent, "_send_contract_tx_altfee", return_value=("0xsender", "0xtx", 21000, 1234)) as send_altfee, \
             patch.object(morph_agent, "_send_contract_tx_from_account") as send_standard:
            result = morph_agent._send_contract_tx_for_args("0xcontract", "0xdata", args)

        self.assertEqual(result, ("0xsender", "0xtx", 21000, 7, 1234))
        send_altfee.assert_called_once_with(
            "0xcontract",
            "0xdata",
            "0xkey",
            7,
            fee_limit=1234,
            gas_limit=5678,
        )
        send_standard.assert_not_called()

    def test_send_contract_tx_for_args_uses_provided_account_for_standard_path(self):
        acct = SimpleNamespace(address="0xabc")
        args = SimpleNamespace(
            private_key="0xkey",
            fee_token_id=None,
            fee_limit=None,
            gas_limit=None,
        )

        with patch.object(morph_agent, "_send_contract_tx_from_account", return_value=("0xabc", "0xtx", 42000)) as send_standard, \
             patch.object(morph_agent, "_load_account") as load_account:
            result = morph_agent._send_contract_tx_for_args("0xcontract", "0xdata", args, acct=acct)

        self.assertEqual(result, ("0xabc", "0xtx", 42000, None, None))
        send_standard.assert_called_once_with("0xcontract", "0xdata", acct)
        load_account.assert_not_called()

    def test_attach_altfee_result_is_noop_without_fee_token(self):
        result = {"tx_hash": "0xtx"}
        self.assertIs(morph_agent._attach_altfee_result(result, None, None), result)
        self.assertEqual(result, {"tx_hash": "0xtx"})

    def test_attach_altfee_result_adds_expected_fields(self):
        result = {"tx_hash": "0xtx"}
        morph_agent._attach_altfee_result(result, 5, 999)
        self.assertEqual(
            result,
            {"tx_hash": "0xtx", "fee_token_id": 5, "fee_limit": "999", "type": "0x7f"},
        )

    def test_agent_set_wallet_uses_onchain_typed_data_shape(self):
        owner_acct = SimpleNamespace(address="0x1111111111111111111111111111111111111111")
        new_wallet_acct = SimpleNamespace(
            address="0x2222222222222222222222222222222222222222",
            sign_typed_data=Mock(return_value=SimpleNamespace(signature=b"\x12\x34")),
        )
        args = SimpleNamespace(
            private_key="0xowner",
            new_wallet_key="0xnew",
            agent_id="2",
            fee_token_id=None,
            fee_limit=None,
            gas_limit=None,
        )

        with patch.object(morph_agent, "_load_account", side_effect=[owner_acct, new_wallet_acct]), \
             patch.object(morph_agent, "rpc_call", return_value={"timestamp": hex(1_700_000_000)}), \
             patch.object(morph_agent, "_encode_abi_call", return_value="0xcalldata") as encode_abi_call, \
             patch.object(morph_agent, "_send_contract_tx_for_args", return_value=("0xowner", "0xtx", 123456, None, None)) as send_tx, \
             patch.object(morph_agent, "_ok") as ok:
            morph_agent.cmd_agent_set_wallet(args)

        new_wallet_acct.sign_typed_data.assert_called_once_with(
            domain_data={
                "name": morph_agent.AGENT_WALLET_DOMAIN_NAME,
                "version": morph_agent.AGENT_WALLET_DOMAIN_VERSION,
                "chainId": morph_agent.CHAIN_ID,
                "verifyingContract": morph_agent.IDENTITY_REGISTRY,
            },
            message_types={
                "AgentWalletSet": [
                    {"name": "agentId", "type": "uint256"},
                    {"name": "newWallet", "type": "address"},
                    {"name": "owner", "type": "address"},
                    {"name": "deadline", "type": "uint256"},
                ]
            },
            message_data={
                "agentId": 2,
                "newWallet": new_wallet_acct.address,
                "owner": owner_acct.address,
                "deadline": 1_700_000_000 + morph_agent.AGENT_WALLET_MAX_DEADLINE_DELAY,
            },
        )
        encode_abi_call.assert_called_once_with(
            morph_agent.get_identity_abi(),
            "setAgentWallet(uint256,address,uint256,bytes)",
            [2, new_wallet_acct.address, 1_700_000_000 + morph_agent.AGENT_WALLET_MAX_DEADLINE_DELAY, b"\x12\x34"],
        )
        send_tx.assert_called_once_with(
            morph_agent.IDENTITY_REGISTRY,
            "0xcalldata",
            args,
            acct=owner_acct,
        )
        ok.assert_called_once()

    def test_agent_wallet_max_deadline_delay_matches_mainnet_constraint(self):
        self.assertEqual(morph_agent.AGENT_WALLET_MAX_DEADLINE_DELAY, 5 * 60)


class MorphX402RefactorTests(unittest.TestCase):
    def test_required_amount_raw_prefers_max_amount_required(self):
        requirements = {"maxAmountRequired": "1000", "amount": "999", "price": "888"}
        self.assertEqual(morph_x402._required_amount_raw(requirements), 1000)

    def test_required_amount_raw_falls_back_to_amount_then_price(self):
        self.assertEqual(morph_x402._required_amount_raw({"amount": "25"}), 25)
        self.assertEqual(morph_x402._required_amount_raw({"price": "7"}), 7)

    def test_payment_request_body_matches_existing_shape(self):
        payload = {"payload": {"signature": "0xsig"}}
        requirements = {"payTo": "0xpay"}
        self.assertEqual(
            morph_x402._payment_request_body(payload, requirements),
            {
                "x402Version": 2,
                "paymentPayload": payload,
                "paymentRequirements": requirements,
            },
        )

    def test_server_payment_requirements_preserve_existing_fields(self):
        req = morph_x402._server_payment_requirements("0xpay", 1000, 8402, "/api/resource")
        self.assertEqual(req["scheme"], "exact")
        self.assertEqual(req["network"], morph_x402.X402_NETWORK)
        self.assertEqual(req["maxAmountRequired"], "1000")
        self.assertEqual(req["resource"], "http://localhost:8402/api/resource")
        self.assertEqual(req["payTo"], "0xpay")
        self.assertEqual(req["asset"], morph_x402.X402_USDC_ADDRESS)
        self.assertEqual(req["extra"], {"name": "USDC", "version": "2"})


if __name__ == "__main__":
    unittest.main()
