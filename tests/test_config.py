import unittest
from pathlib import Path

from agentic_sim.config import load_config


class ConfigTests(unittest.TestCase):
    def test_scale_config_loads_lumi_knobs(self):
        config = load_config(str(Path("configs") / "storm_scale.json"))

        self.assertEqual(config.agent_replicas, 64)
        self.assertEqual(config.max_events_per_tick, 512)
        self.assertEqual(config.storage_mode, "sqlite")
