import unittest
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from agentic_sim.models import (
    AgentId,
    AgentProfile,
    AgentState,
    CommitStatus,
    CommitUnit,
    EnvironmentState,
    Event,
    EventType,
    Message,
    MessageType,
)
from agentic_sim.state import InMemoryStateStore, SQLiteStateStore
from agentic_sim.utils.time import utc_now


def _test_environment() -> EnvironmentState:
    return EnvironmentState(scenario="test", tick=0, updated_at=utc_now(), variables={})


class CommitConformanceMixin:
    """Shared behavioral contract every RuntimeStore backend must satisfy,
    per ADR 0001: "no duplicate, late, or partial commit can occur."
    Subclasses provide make_store()."""

    def make_store(self):
        raise NotImplementedError

    def setUp(self):
        self.store = self.make_store()
        self.agent_id = AgentId("agent_a")
        self.store.agents.put_profile(
            AgentProfile(agent_id=self.agent_id, role="synthetic_node", name="a", region="test")
        )
        self.store.agents.put_state(AgentState(agent_id=self.agent_id))

    def test_commit_applies_state_messages_and_events_together(self):
        message = Message.create(
            sender_id=self.agent_id,
            recipient_id=self.agent_id,
            message_type=MessageType.SYNTHETIC_HOP,
        )
        event = Event.create(EventType.SYNTHETIC_TRIGGER, source="test")
        unit = CommitUnit(
            activation_id="act_1",
            agent_id=self.agent_id,
            expected_state_version=0,
            updated_state=AgentState(agent_id=self.agent_id, version=1),
            outgoing_messages=[message],
            emitted_events=[event],
        )

        receipt = self.store.commit(unit)

        self.assertEqual(receipt.status, CommitStatus.COMMITTED)
        self.assertEqual(receipt.commit_version_written, 1)
        self.assertEqual(self.store.agents.get_state(self.agent_id).version, 1)
        self.assertEqual(self.store.messages.count(), 1)
        self.assertEqual(
            len(self.store.events.pop_ready(utc_now() + timedelta(seconds=1))), 1
        )

    def test_duplicate_activation_id_is_idempotent_noop(self):
        unit = CommitUnit(
            activation_id="act_dup",
            agent_id=self.agent_id,
            expected_state_version=0,
            updated_state=AgentState(agent_id=self.agent_id, version=1),
        )
        first = self.store.commit(unit)
        self.assertEqual(first.status, CommitStatus.COMMITTED)

        second = self.store.commit(unit)

        self.assertEqual(second.status, CommitStatus.DUPLICATE)
        self.assertEqual(second.commit_version_written, 1)
        self.assertEqual(self.store.agents.get_state(self.agent_id).version, 1)

    def test_stale_expected_version_is_rejected_and_nothing_applied(self):
        message = Message.create(
            sender_id=self.agent_id,
            recipient_id=self.agent_id,
            message_type=MessageType.SYNTHETIC_HOP,
        )
        unit = CommitUnit(
            activation_id="act_conflict",
            agent_id=self.agent_id,
            expected_state_version=5,
            updated_state=AgentState(agent_id=self.agent_id, version=6),
            outgoing_messages=[message],
        )

        receipt = self.store.commit(unit)

        self.assertEqual(receipt.status, CommitStatus.CONFLICT)
        self.assertIsNone(receipt.commit_version_written)
        self.assertEqual(self.store.agents.get_state(self.agent_id).version, 0)
        self.assertEqual(self.store.messages.count(), 0)

    def test_sequential_commits_chain_versions(self):
        first = self.store.commit(
            CommitUnit(
                activation_id="act_a",
                agent_id=self.agent_id,
                expected_state_version=0,
                updated_state=AgentState(agent_id=self.agent_id, version=1),
            )
        )
        second = self.store.commit(
            CommitUnit(
                activation_id="act_b",
                agent_id=self.agent_id,
                expected_state_version=1,
                updated_state=AgentState(agent_id=self.agent_id, version=2),
            )
        )

        self.assertEqual([first.status, second.status], [CommitStatus.COMMITTED, CommitStatus.COMMITTED])
        self.assertEqual(self.store.agents.get_state(self.agent_id).version, 2)


class InMemoryCommitConformanceTests(CommitConformanceMixin, unittest.TestCase):
    def make_store(self):
        return InMemoryStateStore(_test_environment())


class SQLiteCommitConformanceTests(CommitConformanceMixin, unittest.TestCase):
    def make_store(self):
        self._tmpdir = TemporaryDirectory()
        path = Path(self._tmpdir.name) / "state.sqlite"
        return SQLiteStateStore(path, environment=_test_environment())

    def tearDown(self):
        self.store.close()
        self._tmpdir.cleanup()


if __name__ == "__main__":
    unittest.main()
