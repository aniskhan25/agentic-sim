import unittest
from datetime import datetime, timedelta, timezone
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

    def test_sqlite_store_orders_equal_priority_events_by_creation_time(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.sqlite"
            store = SQLiteStateStore(path, environment=StormEnvironment().initialize())
            scheduled_for = datetime(2026, 1, 1, tzinfo=timezone.utc)
            newer = Event(
                event_id="evt_newer",
                event_type=EventType.TIMER_FIRED,
                created_at=scheduled_for + timedelta(seconds=1),
                scheduled_for=scheduled_for,
                source="test",
                priority=1,
            )
            older = Event(
                event_id="evt_older",
                event_type=EventType.TIMER_FIRED,
                created_at=scheduled_for,
                scheduled_for=scheduled_for,
                source="test",
                priority=1,
            )

            store.events.put(newer)
            store.events.put(older)

            self.assertEqual(
                [event.event_id for event in store.events.pop_ready(utc_now())],
                ["evt_older", "evt_newer"],
            )
            store.close()

    def test_sqlite_store_initialization_starts_fresh_run(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.sqlite"
            environment = StormEnvironment().initialize()
            store = SQLiteStateStore(path, environment=environment)
            store.events.put(Event.create(EventType.TIMER_FIRED, source="test"))
            store.close()

            fresh = SQLiteStateStore(path, environment=environment)

            self.assertEqual(fresh.events.count_pending(), 0)
            self.assertEqual(fresh.messages.count(), 0)
            self.assertEqual(len(fresh.traces.list()), 0)
            fresh.close()
