import unittest

from multiagent_demo.environment import StormEnvironment
from multiagent_demo.engine import create_storm_engine
from multiagent_demo.models import EventType
from multiagent_demo.observability import RunSummaryBuilder
from multiagent_demo.utils.time import utc_now


class StormScenarioTests(unittest.TestCase):
    def test_storm_scenario_creates_messages_and_summary(self):
        engine = create_storm_engine(backend_name="rule")
        engine.run(4)

        summary = RunSummaryBuilder().build(engine.store)

        self.assertGreaterEqual(summary.messages, 2)
        self.assertGreaterEqual(summary.pending_events, 0)
        self.assertGreaterEqual(summary.agent_activations["agent_hospital"], 1)

    def test_storm_environment_emits_outage_event_at_higher_severity(self):
        environment = StormEnvironment()
        state = environment.initialize()

        first = environment.tick(state, utc_now())
        second = environment.tick(first.state, utc_now())

        event_types = [event.event_type for event in second.emitted_events]
        self.assertIn(EventType.STORM_OUTAGE, event_types)
