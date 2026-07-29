import unittest

from agentic_sim.execution import MockExecutionBackend, SynchronousProviderAdapter
from agentic_sim.execution.errors import ProviderError, ProviderTimeoutError
from agentic_sim.execution.failure_injecting_backend import FailureInjectingBackend
from agentic_sim.models import (
    Activation,
    AgentId,
    AgentProfile,
    AgentState,
    DispatchStatus,
    EnvironmentState,
    Event,
    EventType,
    ExecutionRequest,
)
from agentic_sim.scheduling import NaiveConcurrentDispatchPolicy
from agentic_sim.utils.time import utc_now


def _request(agent_id: str, role: str = "coordinator") -> ExecutionRequest:
    now = utc_now()
    event = Event.create(EventType.SYNTHETIC_TRIGGER, source="test", priority=1)
    return ExecutionRequest(
        activation=Activation.create(
            agent_id=AgentId(agent_id),
            trigger_event_id=event.event_id,
            activation_reason=event.event_type.value,
            priority=event.priority,
            ready_at=now,
        ),
        agent_profile=AgentProfile(agent_id=AgentId(agent_id), role=role, name=agent_id, region="test"),
        agent_state=AgentState(agent_id=AgentId(agent_id)),
        inbox_messages=[],
        triggering_event=event,
        environment=EnvironmentState(scenario="test", tick=0, updated_at=now, variables={}),
    )


class FailureInjectingBackendModeTests(unittest.TestCase):
    def test_timeout_mode_raises_timeout_error(self):
        backend = FailureInjectingBackend(MockExecutionBackend(), failure_plan={"agent_a": "timeout"})

        with self.assertRaises(TimeoutError):
            backend.run_batch([_request("agent_a")])

    def test_interruption_mode_raises_generically(self):
        backend = FailureInjectingBackend(MockExecutionBackend(), failure_plan={"agent_a": "interruption"})

        with self.assertRaises(RuntimeError):
            backend.run_batch([_request("agent_a")])

    def test_malformed_mode_returns_committable_invalid_flagged_result(self):
        backend = FailureInjectingBackend(MockExecutionBackend(), failure_plan={"agent_a": "malformed"})

        results = backend.run_batch([_request("agent_a")])

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].metadata.get("model_output_invalid"))
        self.assertEqual(results[0].updated_state.version, 1)

    def test_none_mode_passes_through_to_wrapped_backend(self):
        backend = FailureInjectingBackend(MockExecutionBackend(), failure_plan={"agent_a": "none"})

        results = backend.run_batch([_request("agent_a")])

        self.assertEqual(len(results), 1)
        self.assertNotIn("model_output_invalid", results[0].metadata)

    def test_unlisted_agent_falls_through_to_wrapped_backend(self):
        backend = FailureInjectingBackend(MockExecutionBackend(), failure_plan={"agent_a": "timeout"})

        results = backend.run_batch([_request("agent_b")])

        self.assertEqual(len(results), 1)

    def test_rejects_unsupported_mode_at_construction(self):
        with self.assertRaises(ValueError):
            FailureInjectingBackend(MockExecutionBackend(), failure_plan={"agent_a": "bogus"})


class FailureInjectingBackendDeterminismTests(unittest.TestCase):
    def test_cycling_plan_reproduces_identically_across_runs(self):
        def run_once():
            backend = FailureInjectingBackend(MockExecutionBackend(), cycle=["none", "timeout", "malformed"])
            outcomes = []
            for agent_id in ["a", "b", "c", "d", "e"]:
                try:
                    result = backend.run_batch([_request(agent_id)])
                    outcomes.append(("ok", result[0].metadata.get("model_output_invalid", False)))
                except Exception as exc:
                    outcomes.append((type(exc).__name__, None))
            return outcomes

        self.assertEqual(run_once(), run_once())


class FailureInjectingBackendIntegrationTests(unittest.TestCase):
    def test_dispatch_policy_captures_injected_failures_without_crashing(self):
        # failure_plan (not cycle) is used here since NaiveConcurrentDispatchPolicy
        # calls run_batch from multiple threads concurrently -- cycle's shared
        # counter has no ordering guarantee under real concurrent dispatch,
        # while a per-agent-id plan is safe regardless of call order.
        backend = FailureInjectingBackend(
            MockExecutionBackend(),
            failure_plan={
                "agent_0": "none",
                "agent_1": "timeout",
                "agent_2": "malformed",
                "agent_3": "interruption",
            },
        )
        adapter = SynchronousProviderAdapter(backend)
        requests = [_request(f"agent_{i}") for i in range(4)]

        outcomes = NaiveConcurrentDispatchPolicy().dispatch(requests, adapter)

        self.assertEqual(len(outcomes), 4)
        statuses = {str(request.agent_profile.agent_id): outcome.status for request, outcome in outcomes}
        errors = {str(request.agent_profile.agent_id): outcome.error for request, outcome in outcomes}

        self.assertEqual(statuses["agent_0"], DispatchStatus.COMPLETED)
        self.assertEqual(statuses["agent_1"], DispatchStatus.FAILED)
        self.assertIsInstance(errors["agent_1"], ProviderTimeoutError)
        self.assertEqual(statuses["agent_2"], DispatchStatus.COMPLETED)
        self.assertEqual(statuses["agent_3"], DispatchStatus.FAILED)
        self.assertIsInstance(errors["agent_3"], ProviderError)
        self.assertNotIsInstance(errors["agent_3"], ProviderTimeoutError)


if __name__ == "__main__":
    unittest.main()
