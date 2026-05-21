import unittest

from agentic_sim.models import AgentId, AgentProfile, AgentState, Event, EventType
from agentic_sim.utils.serialization import to_jsonable


class ModelTests(unittest.TestCase):
    def test_event_and_agent_models_are_jsonable(self):
        profile = AgentProfile(
            agent_id=AgentId("agent_1"),
            role="coordinator",
            name="Coordinator",
            region="test",
        )
        state = AgentState(agent_id=profile.agent_id).with_activation_count()
        event = Event.create(
            EventType.ENVIRONMENT_UPDATE,
            source="test",
            target_scope={"roles": ["coordinator"]},
            payload={"severity": 2},
        )

        self.assertEqual(to_jsonable(profile)["agent_id"], "agent_1")
        self.assertEqual(to_jsonable(state)["metrics"]["activations"], 1)
        self.assertEqual(to_jsonable(event)["event_type"], "environment_update")
