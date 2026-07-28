import unittest

from agentic_sim.execution import AittaExecutionBackend, MockExecutionBackend, SupplyChainRuleBackend


class BackendCapabilitiesTests(unittest.TestCase):
    def test_mock_backend_capabilities(self):
        capabilities = MockExecutionBackend.capabilities

        self.assertTrue(capabilities.supports_concurrency)
        self.assertFalse(capabilities.observable_token_usage)
        self.assertFalse(capabilities.observable_energy)

    def test_supply_chain_rule_backend_inherits_mock_capabilities(self):
        backend = SupplyChainRuleBackend(name="rule")

        self.assertEqual(backend.capabilities, MockExecutionBackend.capabilities)

    def test_aitta_backend_capabilities_reflect_configuration(self):
        concurrent_backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            max_concurrency=4,
            max_completion_tokens=512,
        )
        sequential_backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            max_concurrency=1,
        )

        self.assertTrue(concurrent_backend.capabilities.supports_concurrency)
        self.assertFalse(sequential_backend.capabilities.supports_concurrency)
        self.assertTrue(concurrent_backend.capabilities.observable_token_usage)
        self.assertEqual(concurrent_backend.capabilities.max_context_tokens, 512)
