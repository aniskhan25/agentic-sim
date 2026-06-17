import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from agentic_sim.config import load_config


class ConfigTests(unittest.TestCase):
    def test_scale_config_loads_lumi_knobs(self):
        config = load_config(str(Path("configs") / "storm_scale.json"))

        self.assertEqual(config.scenario, "storm")
        self.assertEqual(config.scenario_parameters, {})
        self.assertEqual(config.agent_replicas, 64)
        self.assertEqual(config.max_events_per_tick, 512)
        self.assertEqual(config.storage_mode, "sqlite")

    def test_string_scenario_config_loads_name(self):
        config = load_config(str(Path("configs") / "storm_small.json"))

        self.assertEqual(config.scenario, "storm")
        self.assertIsNone(config.sqlite_path)

    def test_scenario_parameters_load_from_config(self):
        config = load_config(str(Path("configs") / "supply_chain_scale.json"))

        self.assertEqual(config.scenario, "supply_chain")
        self.assertEqual(config.agent_replicas, 64)
        self.assertEqual(config.scenario_parameters["demand_step"], 15)
        self.assertEqual(
            config.scenario_parameters["regions"], ["helsinki", "oulu", "tampere", "turku"]
        )

    def test_aitta_execution_options_load_from_config(self):
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "aitta.json"
            config_path.write_text(
                """
                {
                  "execution": {
                    "backend": "aitta",
                    "aitta_base_url": "https://aitta.example/openai/v1/",
                    "aitta_model": "demo/model",
                    "aitta_timeout": 45,
                    "aitta_max_concurrency": 1
                  }
                }
                """
            )

            config = load_config(str(config_path))

        self.assertEqual(config.backend, "aitta")
        self.assertEqual(config.backend_options["aitta_base_url"], "https://aitta.example/openai/v1/")
        self.assertEqual(config.backend_options["aitta_model"], "demo/model")
        self.assertEqual(config.backend_options["aitta_timeout"], 45)
