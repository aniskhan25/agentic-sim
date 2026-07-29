import unittest

from agentic_sim.execution import (
    AittaExecutionBackend,
    MockExecutionBackend,
    SelfHostedExecutionBackend,
    SupplyChainRuleBackend,
    create_execution_backend,
)


class BackendFactoryTests(unittest.TestCase):
    def test_aitta_dispatches_to_aitta_backend(self):
        backend = create_execution_backend(
            "aitta",
            scenario="storm",
            backend_options={
                "aitta_api_key": "secret",
                "aitta_base_url": "https://aitta.example/openai/v1/",
                "aitta_model": "demo/model",
            },
        )

        self.assertIsInstance(backend, AittaExecutionBackend)

    def test_self_hosted_dispatches_to_self_hosted_backend(self):
        backend = create_execution_backend(
            "self_hosted",
            scenario="storm",
            backend_options={
                "self_hosted_base_url": "http://localhost:8000/v1",
                "self_hosted_model": "demo/model",
            },
        )

        self.assertIsInstance(backend, SelfHostedExecutionBackend)

    def test_self_hosted_dispatch_does_not_require_scenario_gating(self):
        backend = create_execution_backend(
            "self_hosted",
            scenario="supply_chain",
            backend_options={
                "self_hosted_base_url": "http://localhost:8000/v1",
                "self_hosted_model": "demo/model",
            },
        )

        self.assertIsInstance(backend, SelfHostedExecutionBackend)

    def test_mock_dispatches_per_scenario(self):
        storm_backend = create_execution_backend("mock", scenario="storm")
        self.assertIsInstance(storm_backend, MockExecutionBackend)

        supply_chain_backend = create_execution_backend("rule", scenario="supply_chain")
        self.assertIsInstance(supply_chain_backend, SupplyChainRuleBackend)

    def test_unknown_backend_name_raises_value_error(self):
        with self.assertRaises(ValueError):
            create_execution_backend("bogus", scenario="storm")


if __name__ == "__main__":
    unittest.main()
