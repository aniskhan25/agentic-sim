from __future__ import annotations

from agentic_sim.models import (
    AgentId,
    AgentState,
    AgentStatus,
    EnvironmentAction,
    ExecutionRequest,
    ExecutionResult,
    Message,
    MessageType,
)
from agentic_sim.utils.time import utc_now


class MockExecutionBackend:
    """Deterministic backend for tests and local smoke runs."""

    name = "mock"

    def run_batch(self, requests: list[ExecutionRequest]) -> list[ExecutionResult]:
        return [self._run_one(request) for request in requests]

    def _run_one(self, request: ExecutionRequest) -> ExecutionResult:
        state = self._update_state(request)
        role = request.agent_profile.role
        if role == "coordinator":
            return self._coordinator_result(request, state)
        if role in {"hospital", "utility"}:
            return self._operator_result(request, state)
        if role == "forecaster":
            return self._forecaster_result(request, state)
        return ExecutionResult(agent_id=request.agent_profile.agent_id, updated_state=state)

    def _update_state(self, request: ExecutionRequest) -> AgentState:
        memory = dict(request.agent_state.working_memory)
        memory["last_event_type"] = request.triggering_event.event_type.value
        memory["last_environment_tick"] = request.environment.tick
        state = request.agent_state.with_activation_count()
        return AgentState(
            agent_id=state.agent_id,
            status=AgentStatus.IDLE,
            current_goal=f"respond to {request.triggering_event.event_type.value}",
            working_memory=memory,
            pending_tasks=list(state.pending_tasks),
            inbox_cursor=request.inbox_messages[-1].message_id if request.inbox_messages else state.inbox_cursor,
            last_active_at=utc_now(),
            metrics=state.metrics,
        )

    def _coordinator_result(
        self, request: ExecutionRequest, state: AgentState
    ) -> ExecutionResult:
        messages: list[Message] = []
        for profile_id in request.triggering_event.payload.get("operator_ids", []):
            messages.append(
                Message.create(
                    sender_id=request.agent_profile.agent_id,
                    recipient_id=AgentId(profile_id),
                    message_type=MessageType.STATUS_REQUEST,
                    priority=request.triggering_event.priority,
                    payload={"severity": request.environment.variables.get("severity", 0)},
                    correlation_id=request.triggering_event.correlation_id or request.triggering_event.event_id,
                )
            )

        actions = [
            EnvironmentAction(
                action_type="update_summary",
                payload={
                    "summary": f"coordinator reviewed severity {request.environment.variables.get('severity')}"
                },
            )
        ]
        return ExecutionResult(
            agent_id=request.agent_profile.agent_id,
            updated_state=state,
            outgoing_messages=messages,
            environment_actions=actions,
            metadata={"backend": self.name, "role": "coordinator"},
        )

    def _operator_result(self, request: ExecutionRequest, state: AgentState) -> ExecutionResult:
        coordinator_id = request.triggering_event.payload.get("coordinator_id", "agent_coordinator")
        severity = int(request.environment.variables.get("severity", 0))
        region = request.agent_profile.region
        message = Message.create(
            sender_id=request.agent_profile.agent_id,
            recipient_id=AgentId(coordinator_id),
            message_type=MessageType.STATUS_UPDATE,
            priority=severity,
            payload={
                "role": request.agent_profile.role,
                "region": region,
                "status": "strained" if severity >= 3 else "normal",
                "severity": severity,
            },
            correlation_id=request.triggering_event.correlation_id or request.triggering_event.event_id,
        )
        return ExecutionResult(
            agent_id=request.agent_profile.agent_id,
            updated_state=state,
            outgoing_messages=[message],
            metadata={"backend": self.name, "role": request.agent_profile.role},
        )

    def _forecaster_result(self, request: ExecutionRequest, state: AgentState) -> ExecutionResult:
        severity = int(request.environment.variables.get("severity", 0))
        action = EnvironmentAction(
            action_type="update_summary",
            payload={"summary": f"forecast confirms severity trend at {severity}"},
        )
        return ExecutionResult(
            agent_id=request.agent_profile.agent_id,
            updated_state=state,
            environment_actions=[action],
            metadata={"backend": self.name, "role": "forecaster"},
        )
