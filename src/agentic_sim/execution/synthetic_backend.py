from __future__ import annotations

from agentic_sim.execution.capabilities import ProviderCapabilities
from agentic_sim.execution.mock_backend import MockExecutionBackend
from agentic_sim.models import (
    AgentId,
    EnvironmentAction,
    ExecutionRequest,
    ExecutionResult,
    Message,
    MessageType,
)


class SyntheticExecutionBackend(MockExecutionBackend):
    """Deterministic backend for the minimum DAG kernel.

    Message hops and optional environment-variable writes are driven
    entirely by a declarative topology (hop_plan/conflict_writes), never by
    role names -- this is what keeps role_policy.py and the domain scenarios
    fully untouched. Inherits MockExecutionBackend's _update_state as-is.
    """

    name = "synthetic"
    capabilities = ProviderCapabilities(
        supports_concurrency=True,
        supports_server_batching=False,
        supports_structured_output=True,
        supports_prefix_caching=False,
        max_context_tokens=0,
        observable_token_usage=False,
        observable_energy=False,
    )

    def __init__(
        self,
        hop_plan: dict[str, list[str]],
        conflict_writes: dict[str, dict] | None = None,
    ):
        self.hop_plan = hop_plan
        self.conflict_writes = conflict_writes or {}

    def _run_one(self, request: ExecutionRequest) -> ExecutionResult:
        state = self._update_state(request)
        agent_id = str(request.agent_profile.agent_id)

        messages = [
            Message.create(
                sender_id=request.agent_profile.agent_id,
                recipient_id=AgentId(target),
                message_type=MessageType.SYNTHETIC_HOP,
                priority=request.triggering_event.priority,
                payload={},
                correlation_id=request.triggering_event.correlation_id
                or request.triggering_event.event_id,
                origin_activation_id=request.activation.activation_id,
            )
            for target in self.hop_plan.get(agent_id, [])
        ]

        actions: list[EnvironmentAction] = []
        if agent_id in self.conflict_writes:
            actions.append(
                EnvironmentAction(action_type="set_variable", payload=self.conflict_writes[agent_id])
            )

        return ExecutionResult(
            agent_id=request.agent_profile.agent_id,
            updated_state=state,
            outgoing_messages=messages,
            environment_actions=actions,
            metadata={"backend": self.name},
        )
