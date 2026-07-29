import unittest

from agentic_sim.execution import SynchronousProviderAdapter
from agentic_sim.execution.capabilities import ProviderCapabilities
from agentic_sim.execution.errors import ProviderError, ProviderTimeoutError
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
from agentic_sim.utils.time import utc_now

_CAPABILITIES = ProviderCapabilities(
    supports_concurrency=False,
    supports_server_batching=False,
    supports_structured_output=False,
    supports_prefix_caching=False,
    max_context_tokens=0,
    observable_token_usage=False,
    observable_energy=False,
)


class _AlwaysTimesOutBackend:
    name = "always_times_out"
    capabilities = _CAPABILITIES

    def run_batch(self, requests):
        raise TimeoutError("simulated provider timeout")


class _AlwaysFailsBackend:
    name = "always_fails"
    capabilities = _CAPABILITIES

    def run_batch(self, requests):
        raise RuntimeError("simulated generic provider failure")


def _request() -> ExecutionRequest:
    now = utc_now()
    event = Event.create(EventType.SYNTHETIC_TRIGGER, source="test", priority=1)
    return ExecutionRequest(
        activation=Activation.create(
            agent_id=AgentId("agent_a"),
            trigger_event_id=event.event_id,
            activation_reason=event.event_type.value,
            priority=event.priority,
            ready_at=now,
        ),
        agent_profile=AgentProfile(agent_id=AgentId("agent_a"), role="node", name="a", region="t"),
        agent_state=AgentState(agent_id=AgentId("agent_a")),
        inbox_messages=[],
        triggering_event=event,
        environment=EnvironmentState(scenario="test", tick=0, updated_at=now, variables={}),
    )


class SyncProviderAdapterFailureTests(unittest.TestCase):
    def test_bare_timeout_error_classified_as_provider_timeout_error(self):
        adapter = SynchronousProviderAdapter(_AlwaysTimesOutBackend())

        ticket = adapter.submit(_request())
        outcome = adapter.poll(ticket)

        self.assertEqual(outcome.status, DispatchStatus.FAILED)
        self.assertIsNone(outcome.result)
        self.assertIsInstance(outcome.error, ProviderTimeoutError)

    def test_generic_exception_classified_as_provider_error(self):
        adapter = SynchronousProviderAdapter(_AlwaysFailsBackend())

        ticket = adapter.submit(_request())
        outcome = adapter.poll(ticket)

        self.assertEqual(outcome.status, DispatchStatus.FAILED)
        self.assertIsNone(outcome.result)
        self.assertIsInstance(outcome.error, ProviderError)
        self.assertNotIsInstance(outcome.error, ProviderTimeoutError)


if __name__ == "__main__":
    unittest.main()
