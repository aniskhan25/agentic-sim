import unittest

from agentic_sim.models import (
    Activation,
    AgentId,
    AgentProfile,
    AgentState,
    Event,
    EventType,
    ExecutionReceipt,
    PlatformManifest,
    Proposal,
    ValidationResult,
)
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

    def test_activation_attempt_number_defaults_to_zero(self):
        activation = Activation.create(
            agent_id=AgentId("agent_1"),
            trigger_event_id="evt_1",
            activation_reason="environment_update",
            priority=1,
        )

        self.assertEqual(activation.attempt_number, 0)

        retried = Activation.create(
            agent_id=AgentId("agent_1"),
            trigger_event_id="evt_1",
            activation_reason="environment_update",
            priority=1,
            attempt_number=2,
        )
        self.assertEqual(retried.attempt_number, 2)

    def test_agent_state_with_activation_count_increments_version(self):
        state = AgentState(agent_id=AgentId("agent_1"))
        self.assertEqual(state.version, 0)

        once = state.with_activation_count()
        self.assertEqual(once.version, 1)

        twice = once.with_activation_count()
        self.assertEqual(twice.version, 2)

    def test_proposal_defaults_and_jsonable(self):
        proposal = Proposal(raw_content="{}")

        self.assertTrue(proposal.is_valid)
        self.assertIsNone(proposal.parse_error)
        self.assertEqual(proposal.outgoing_messages, [])

        jsonable = to_jsonable(proposal)
        self.assertEqual(jsonable["raw_content"], "{}")
        self.assertTrue(jsonable["is_valid"])

    def test_validation_result_defaults_and_jsonable(self):
        result = ValidationResult(semantic_valid=False, violation_reasons=["self_message: x"])

        jsonable = to_jsonable(result)
        self.assertFalse(jsonable["semantic_valid"])
        self.assertEqual(jsonable["violation_reasons"], ["self_message: x"])
        self.assertIsNone(jsonable["message_action_autonomy_rate"])
        self.assertEqual(jsonable["message_action_committed_atom_count"], 0)
        self.assertTrue(jsonable["useful_step"])

    def test_execution_receipt_unknown_fields_stay_none_not_fake(self):
        receipt = ExecutionReceipt(activation_id="act_1", provider="aitta", total_latency_seconds=1.2)

        jsonable = to_jsonable(receipt)
        self.assertEqual(jsonable["activation_id"], "act_1")
        self.assertEqual(jsonable["total_latency_seconds"], 1.2)
        self.assertIsNone(jsonable["state_version_read"])
        self.assertIsNone(jsonable["commit_version_written"])
        self.assertIsNone(jsonable["request_hash"])
        self.assertIsNone(jsonable["dispatch_seconds"])
        self.assertIsNone(jsonable["accelerator"])
        self.assertEqual(jsonable["causal_parents"], [])
        self.assertEqual(jsonable["commit_status"], "unknown")

    def test_platform_manifest_local_default_is_constructible(self):
        manifest = PlatformManifest.local_default("mock")

        self.assertEqual(manifest.backend_name, "mock")
        self.assertEqual(manifest.accelerator, "none")

        jsonable = to_jsonable(manifest)
        self.assertEqual(jsonable["backend_name"], "mock")
        self.assertIn("host_architecture", jsonable)
        self.assertIn("python_version", jsonable)
