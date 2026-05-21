import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentic_sim.environment import StormEnvironment
from agentic_sim.models import AgentId, AgentProfile, AgentState, Event, EventType
from agentic_sim.state import InMemoryStateStore, SQLiteStateStore
from agentic_sim.utils.time import utc_now


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

    def test_sqlite_store_persists_agent_environment_and_events(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.sqlite"
            environment = StormEnvironment().initialize()
            store = SQLiteStateStore(path, environment=environment)
            profile = AgentProfile(
                agent_id=AgentId("agent_sqlite"),
                role="utility",
                name="Utility",
                region="oulu",
            )
            event = Event.create(EventType.STORM_OUTAGE, source="test")

            store.agents.put_profile(profile)
            store.agents.put_state(AgentState(agent_id=profile.agent_id))
            store.events.put(event)
            store.close()

            reopened = SQLiteStateStore(path)
            self.assertEqual(reopened.agents.get_profile(profile.agent_id).role, "utility")
            self.assertEqual(reopened.environment.get().scenario, "storm")
            self.assertEqual(reopened.events.pop_ready(utc_now())[0].event_type, EventType.STORM_OUTAGE)
            reopened.close()
