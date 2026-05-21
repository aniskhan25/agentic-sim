import unittest

from multiagent_demo.engine import create_storm_engine
from multiagent_demo.observability import RunSummaryBuilder


class StormScenarioTests(unittest.TestCase):
    def test_storm_scenario_creates_messages_and_summary(self):
        engine = create_storm_engine(backend_name="rule")
        engine.run(4)

        summary = RunSummaryBuilder().build(engine.store)

        self.assertGreaterEqual(summary.messages, 2)
        self.assertGreaterEqual(summary.pending_events, 0)
        self.assertGreaterEqual(summary.agent_activations["agent_hospital"], 1)
