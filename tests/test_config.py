import json
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from agentic_sim.config import load_config, merge_cli


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

    def test_self_hosted_execution_options_load_from_config(self):
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "self_hosted.json"
            config_path.write_text(
                """
                {
                  "execution": {
                    "backend": "self_hosted",
                    "self_hosted_base_url": "http://localhost:8000/v1",
                    "self_hosted_model": "demo/model",
                    "self_hosted_timeout": 45,
                    "self_hosted_enable_prefix_caching": true
                  }
                }
                """
            )

            config = load_config(str(config_path))

        self.assertEqual(config.backend, "self_hosted")
        self.assertEqual(config.backend_options["self_hosted_base_url"], "http://localhost:8000/v1")
        self.assertEqual(config.backend_options["self_hosted_model"], "demo/model")
        self.assertEqual(config.backend_options["self_hosted_timeout"], 45)
        self.assertTrue(config.backend_options["self_hosted_enable_prefix_caching"])

    def test_seed_defaults_to_none(self):
        config = load_config(str(Path("configs") / "storm_small.json"))

        self.assertIsNone(config.seed)

    def test_seed_round_trips_through_load_and_merge(self):
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "seeded.json"
            config_path.write_text(json.dumps({"seed": 3}))
            config = load_config(str(config_path))

        self.assertEqual(config.seed, 3)

        overridden = merge_cli(config, {"seed": 7})
        self.assertEqual(overridden.seed, 7)

        unchanged = merge_cli(config, {"seed": None})
        self.assertEqual(unchanged.seed, 3)
