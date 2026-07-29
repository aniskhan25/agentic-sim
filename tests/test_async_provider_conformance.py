import json
import unittest

from agentic_sim.execution import (
    AittaExecutionBackend,
    MockExecutionBackend,
    SupplyChainRuleBackend,
    SynchronousProviderAdapter,
)
from agentic_sim.execution.synthetic_backend import SyntheticExecutionBackend
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


def _request(role: str = "generic_node", agent_id: str = "agent_a") -> ExecutionRequest:
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
        agent_profile=AgentProfile(
            agent_id=AgentId(agent_id), role=role, name=agent_id, region="test"
        ),
        agent_state=AgentState(agent_id=AgentId(agent_id)),
        inbox_messages=[],
        triggering_event=event,
        environment=EnvironmentState(scenario="test", tick=0, updated_at=now, variables={}),
    )


class AsyncProviderConformanceMixin:
    """Shared behavioral contract every AsyncExecutionBackend adapter must
    satisfy, mirroring tests/test_commit_conformance.py's mixin pattern from
    item 10. Subclasses provide make_adapter() and make_request()."""

    def make_adapter(self):
        raise NotImplementedError

    def make_request(self) -> ExecutionRequest:
        raise NotImplementedError

    def setUp(self):
        self.adapter = self.make_adapter()

    def test_submit_then_poll_returns_completed_result(self):
        request = self.make_request()

        ticket = self.adapter.submit(request)
        outcome = self.adapter.poll(ticket)

        self.assertEqual(outcome.status, DispatchStatus.COMPLETED)
        self.assertIsNotNone(outcome.result)
        self.assertEqual(outcome.result.agent_id, request.agent_profile.agent_id)
        self.assertIsNone(outcome.error)

    def test_poll_unknown_ticket_raises_key_error(self):
        from agentic_sim.models import DispatchTicket

        with self.assertRaises(KeyError):
            self.adapter.poll(DispatchTicket(ticket_id="does_not_exist", activation_id="none"))

    def test_cancel_after_completion_returns_false(self):
        ticket = self.adapter.submit(self.make_request())

        self.assertFalse(self.adapter.cancel(ticket))

    def test_capabilities_and_name_passthrough(self):
        self.assertEqual(self.adapter.name, self.adapter.backend.name)
        self.assertEqual(self.adapter.capabilities, self.adapter.backend.capabilities)


class MockAdapterConformanceTests(AsyncProviderConformanceMixin, unittest.TestCase):
    def make_adapter(self):
        return SynchronousProviderAdapter(MockExecutionBackend())

    def make_request(self):
        return _request(role="coordinator", agent_id="agent_coordinator")


class RuleAdapterConformanceTests(AsyncProviderConformanceMixin, unittest.TestCase):
    def make_adapter(self):
        return SynchronousProviderAdapter(SupplyChainRuleBackend())

    def make_request(self):
        return _request(role="supplier", agent_id="agent_supplier")


class SyntheticAdapterConformanceTests(AsyncProviderConformanceMixin, unittest.TestCase):
    def make_adapter(self):
        return SynchronousProviderAdapter(SyntheticExecutionBackend(hop_plan={}))

    def make_request(self):
        return _request(role="synthetic_node", agent_id="node_0")


class AittaAdapterConformanceTests(AsyncProviderConformanceMixin, unittest.TestCase):
    def make_adapter(self):
        def transport(url, headers, payload, timeout):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "current_goal": "noop",
                                    "working_memory": {},
                                    "outgoing_messages": [],
                                    "environment_actions": [],
                                    "metadata": {},
                                }
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            timeout_seconds=30,
            transport=transport,
        )
        return SynchronousProviderAdapter(backend)

    def make_request(self):
        return _request(role="coordinator", agent_id="agent_coordinator")


if __name__ == "__main__":
    unittest.main()
