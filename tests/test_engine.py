import unittest

from multiagent_demo.engine import create_storm_engine


class EngineTests(unittest.TestCase):
    def test_storm_engine_runs_and_records_traces(self):
        engine = create_storm_engine()

        results = engine.run(3)

        self.assertEqual(len(results), 3)
        self.assertGreaterEqual(engine.store.environment.get().tick, 1)
        self.assertGreaterEqual(len(engine.store.traces.list()), 3)
        coordinator = engine.store.agents.get_state("agent_coordinator")
        self.assertGreaterEqual(coordinator.metrics["activations"], 1)
