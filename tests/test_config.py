import unittest
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
