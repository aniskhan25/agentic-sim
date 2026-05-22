from __future__ import annotations

from agentic_sim.execution.mock_backend import MockExecutionBackend
from agentic_sim.models import (
    AgentId,
    AgentState,
    EnvironmentAction,
    ExecutionRequest,
    ExecutionResult,
    Message,
    MessageType,
)


class SupplyChainRuleBackend(MockExecutionBackend):
    """Deterministic role rules for the supply-chain scenario."""

    name = "rule"

    def __init__(self, name: str = "rule"):
        self.name = name

    def _run_one(self, request: ExecutionRequest) -> ExecutionResult:
        state = self._update_state(request)
        role = request.agent_profile.role
        if role == "coordinator":
            return self._coordinator_result(request, state)
        if role in {"supplier", "warehouse", "transport", "retailer"}:
            return self._operator_result(request, state)
        return ExecutionResult(agent_id=request.agent_profile.agent_id, updated_state=state)

    def _coordinator_result(
        self, request: ExecutionRequest, state: AgentState
    ) -> ExecutionResult:
        messages = [
            Message.create(
                sender_id=request.agent_profile.agent_id,
                recipient_id=AgentId(agent_id),
                message_type=MessageType.STATUS_REQUEST,
                priority=request.triggering_event.priority,
                payload={
                    "demand": request.environment.variables.get("demand", 0),
                    "risk_level": request.environment.variables.get("risk_level", "normal"),
                },
                correlation_id=request.triggering_event.correlation_id
                or request.triggering_event.event_id,
            )
            for agent_id in request.triggering_event.payload.get("operator_ids", [])
        ]
        actions = [
            EnvironmentAction(
                action_type="update_summary",
                payload={
                    "summary": (
                        "coordinator reviewed supply risk "
                        f"{request.environment.variables.get('risk_level', 'normal')}"
                    )
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
        variables = request.environment.variables
        role = request.agent_profile.role
        region = request.agent_profile.region
        risk_level = str(variables.get("risk_level", "normal"))
        actions = self._actions_for_role(role, region, risk_level)
        message = Message.create(
            sender_id=request.agent_profile.agent_id,
            recipient_id=AgentId(coordinator_id),
            message_type=MessageType.STATUS_UPDATE,
            priority=request.triggering_event.priority,
            payload={
                "role": role,
                "region": region,
                "status": "strained" if risk_level != "normal" else "normal",
                "demand": variables.get("demand", 0),
                "risk_level": risk_level,
            },
            correlation_id=request.triggering_event.correlation_id or request.triggering_event.event_id,
        )
        return ExecutionResult(
            agent_id=request.agent_profile.agent_id,
            updated_state=state,
            outgoing_messages=[message],
            environment_actions=actions,
            metadata={"backend": self.name, "role": role},
        )

    def _actions_for_role(
        self, role: str, region: str, risk_level: str
    ) -> list[EnvironmentAction]:
        if risk_level == "normal":
            return []
        if role == "supplier":
            return [
                EnvironmentAction(
                    action_type="adjust_inventory",
                    payload={"region": region, "delta": 15},
                )
            ]
        if role == "transport":
            return [
                EnvironmentAction(
                    action_type="adjust_transport_capacity",
                    payload={"delta": 5},
                )
            ]
        if role == "warehouse":
            return [
                EnvironmentAction(
                    action_type="update_summary",
                    payload={"summary": f"warehouse prioritizing inventory for {region}"},
                )
            ]
        return []
