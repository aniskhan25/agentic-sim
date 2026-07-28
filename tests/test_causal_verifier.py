import unittest
from types import SimpleNamespace

from agentic_sim.engine import create_storm_engine, create_supply_chain_engine
from agentic_sim.observability.causal_verifier import verify


def _agent_step(payload: dict) -> SimpleNamespace:
    return SimpleNamespace(event_name="agent_step", payload=payload)


class CausalVerifierRealRunTests(unittest.TestCase):
    def test_storm_run_has_zero_violations(self):
        engine = create_storm_engine()
        engine.run(3)

        result = verify(engine.store.traces.list())

        self.assertGreater(result.node_count, 0)
        self.assertEqual(result.violations, [])

    def test_supply_chain_run_has_zero_violations(self):
        engine = create_supply_chain_engine()
        engine.run(3)

        result = verify(engine.store.traces.list())

        self.assertGreater(result.node_count, 0)
        self.assertEqual(result.violations, [])


class CausalVerifierSyntheticViolationTests(unittest.TestCase):
    def test_duplicate_activation_id_detected(self):
        traces = [
            _agent_step(
                {
                    "activation_id": "act_dup",
                    "agent_id": "agent_a",
                    "causal_parents": [],
                    "state_version_read": 0,
                    "commit_version_written": 1,
                    "outgoing_message_ids": [],
                }
            ),
            _agent_step(
                {
                    "activation_id": "act_dup",
                    "agent_id": "agent_b",
                    "causal_parents": [],
                    "state_version_read": 0,
                    "commit_version_written": 1,
                    "outgoing_message_ids": [],
                }
            ),
        ]

        result = verify(traces)

        checks = {v.check for v in result.violations}
        self.assertEqual(checks, {"duplicate"})

    def test_missing_parent_detected(self):
        traces = [
            _agent_step(
                {
                    "activation_id": "act_1",
                    "agent_id": "agent_a",
                    "causal_parents": ["msg_ghost00000001"],
                    "state_version_read": 0,
                    "commit_version_written": 1,
                    "outgoing_message_ids": [],
                }
            ),
        ]

        result = verify(traces)

        checks = {v.check for v in result.violations}
        self.assertEqual(checks, {"missing_parent"})

    def test_cycle_detected(self):
        traces = [
            _agent_step(
                {
                    "activation_id": "act_a",
                    "agent_id": "agent_a",
                    "causal_parents": ["msg_from_b0000001"],
                    "state_version_read": 0,
                    "commit_version_written": 1,
                    "outgoing_message_ids": ["msg_from_a0000001"],
                }
            ),
            _agent_step(
                {
                    "activation_id": "act_b",
                    "agent_id": "agent_b",
                    "causal_parents": ["msg_from_a0000001"],
                    "state_version_read": 0,
                    "commit_version_written": 1,
                    "outgoing_message_ids": ["msg_from_b0000001"],
                }
            ),
        ]

        result = verify(traces)

        checks = {v.check for v in result.violations}
        self.assertEqual(checks, {"cycle"})

    def test_stale_read_or_conflict_detected(self):
        traces = [
            _agent_step(
                {
                    "activation_id": "act_1",
                    "agent_id": "agent_a",
                    "causal_parents": [],
                    "state_version_read": 0,
                    "commit_version_written": 1,
                    "outgoing_message_ids": [],
                }
            ),
            _agent_step(
                {
                    "activation_id": "act_2",
                    "agent_id": "agent_a",
                    "causal_parents": [],
                    "state_version_read": 0,
                    "commit_version_written": 1,
                    "outgoing_message_ids": [],
                }
            ),
        ]

        result = verify(traces)

        checks = {v.check for v in result.violations}
        self.assertEqual(checks, {"stale_read_or_conflict"})
