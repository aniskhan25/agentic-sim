import unittest

from multiagent_demo.environment import StormEnvironment
from multiagent_demo.models import AgentId, AgentProfile, AgentState, Event, EventType
from multiagent_demo.state import InMemoryStateStore
from multiagent_demo.utils.time import utc_now


class StateStoreTests(unittest.TestCase):
    def test_in_memory_store_pops_ready_events_once(self):
        store = InMemoryStateStore(StormEnvironment().initialize())
        profile = AgentProfile(
            agent_id=AgentId("agent_1"),
            role="coordinator",
            name="Coordinator",
            region="test",
        )
        event = Event.create(EventType.TIMER_FIRED, source="test")

        store.agents.put_profile(profile)
        store.agents.put_state(AgentState(agent_id=profile.agent_id))
        store.events.put(event)

        self.assertEqual(store.events.pop_ready(utc_now()), [event])
        self.assertEqual(store.events.pop_ready(utc_now()), [])
