from __future__ import annotations

from typing import Any

from agentic_sim.models import (
    AgentId,
    EnvironmentAction,
    ExecutionRequest,
    Message,
    MessageType,
)


def build_role_policy(request: ExecutionRequest) -> dict[str, Any]:
    scenario = request.environment.scenario
    role = request.agent_profile.role
    variables = request.environment.variables
    event_payload = request.triggering_event.payload
    policy: dict[str, Any] = {
        "scenario": scenario,
        "role": role,
        "requirements": [],
        "allowed_environment_actions": allowed_environment_actions(scenario, role),
    }
    if role == "coordinator":
        all_operator_ids = list(event_payload.get("operator_ids", []))
        policy["requirements"].append(
            {
                "type": "outgoing_messages",
                "instruction": "Send status_request to each operator_id listed in the triggering event payload.",
                "example_operator_ids": all_operator_ids[:3],
                "total_operators": len(all_operator_ids),
                "message_type": MessageType.STATUS_REQUEST.value,
            }
        )
        policy["requirements"].append(
            {
                "type": "environment_action",
                "action_type": "update_summary",
                "instruction": "Write a one-sentence summary of the event and which operators were contacted.",
            }
        )
    elif role in {"hospital", "utility"}:
        severity = int(variables.get("severity", 0))
        policy["requirements"].append(
            {
                "type": "outgoing_message",
                "recipient_id": event_payload.get("coordinator_id") or event_payload.get("sender_id", "agent_coordinator"),
                "message_type": MessageType.STATUS_UPDATE.value,
                "status": "strained" if severity >= 3 else "normal",
            }
        )
    elif role == "forecaster":
        policy["requirements"].append(
            {
                "type": "environment_action",
                "action_type": "update_summary",
                "instruction": "Write a one-sentence forecast: severity, regions, trend.",
            }
        )
    elif role in {"supplier", "warehouse", "transport", "retailer"}:
        risk_level = str(variables.get("risk_level", "normal"))
        policy["requirements"].append(
            {
                "type": "outgoing_message",
                "recipient_id": event_payload.get("coordinator_id") or event_payload.get("sender_id", "agent_coordinator"),
                "message_type": MessageType.STATUS_UPDATE.value,
                "status": "strained" if risk_level != "normal" else "normal",
            }
        )
        if risk_level != "normal":
            allowed = allowed_environment_actions(scenario, role)
            if allowed:
                policy["requirements"].append(
                    {
                        "type": "environment_action",
                        "action_type": allowed[0],
                        "instruction": "Propose one concrete mitigation action.",
                    }
                )
    policy["must_not"] = [
        {"type": "self_message", "instruction": "Never message your own agent_id."},
        {
            "type": "action_outside_allowed_set",
            "allowed_action_types": policy["allowed_environment_actions"],
            "instruction": "Never propose an environment_action outside allowed_environment_actions.",
        },
    ]
    return policy


def allowed_environment_actions(scenario: str, role: str) -> list[str]:
    if scenario == "storm" and role in {"coordinator", "forecaster"}:
        return ["update_summary"]
    if scenario == "storm" and role in {"hospital", "utility"}:
        return ["adjust_capacity"]
    if scenario == "supply_chain" and role in {"coordinator", "warehouse"}:
        return ["update_summary"]
    if scenario == "supply_chain" and role == "supplier":
        return ["adjust_inventory"]
    if scenario == "supply_chain" and role == "transport":
        return ["adjust_transport_capacity"]
    return []


def _find_must_not_violations(
    request: ExecutionRequest,
    messages: list[Message],
    actions: list[EnvironmentAction],
    policy: dict[str, Any],
) -> tuple[list[str], set[int], set[int]]:
    """Return (violation reasons, indices of violating messages, indices of violating actions)."""
    self_id = request.agent_profile.agent_id
    allowed_actions = set(policy.get("allowed_environment_actions", []))
    reasons: list[str] = []
    bad_message_idx: set[int] = set()
    bad_action_idx: set[int] = set()
    for i, message in enumerate(messages):
        if message.recipient_id == self_id:
            reasons.append(f"self_message: message to own agent_id {self_id}")
            bad_message_idx.add(i)
    for i, action in enumerate(actions):
        if action.action_type not in allowed_actions:
            reasons.append(
                f"action_outside_allowed_set: {action.action_type} not in {sorted(allowed_actions)}"
            )
            bad_action_idx.add(i)
    return reasons, bad_message_idx, bad_action_idx


def enforce_must_not(
    request: ExecutionRequest,
    messages: list[Message],
    actions: list[EnvironmentAction],
    policy: dict[str, Any],
) -> tuple[list[Message], list[EnvironmentAction], int]:
    """Strip messages/actions violating policy['must_not']; return (kept_messages, kept_actions, violations)."""
    reasons, bad_message_idx, bad_action_idx = _find_must_not_violations(request, messages, actions, policy)
    kept_messages = [m for i, m in enumerate(messages) if i not in bad_message_idx]
    kept_actions = [a for i, a in enumerate(actions) if i not in bad_action_idx]
    return kept_messages, kept_actions, len(reasons)


def semantic_violations(
    request: ExecutionRequest,
    messages: list[Message],
    actions: list[EnvironmentAction],
    policy: dict[str, Any],
) -> list[str]:
    """Report must_not violation reasons without stripping anything."""
    reasons, _, _ = _find_must_not_violations(request, messages, actions, policy)
    return reasons


def ensure_required_messages(
    request: ExecutionRequest, messages: list[Message], policy: dict[str, Any]
) -> tuple[list[Message], int]:
    required = _required_messages(request, policy)
    existing = {(str(message.recipient_id), message.message_type) for message in messages}
    added = []
    for message in required:
        key = (str(message.recipient_id), message.message_type)
        if key not in existing:
            added.append(message)
            existing.add(key)
    return messages + added, len(added)


def ensure_required_actions(
    request: ExecutionRequest, actions: list[EnvironmentAction], policy: dict[str, Any]
) -> tuple[list[EnvironmentAction], int]:
    required = _required_actions(request, policy)
    existing = {action.action_type for action in actions}
    added = []
    for action in required:
        if action.action_type not in existing:
            added.append(action)
            existing.add(action.action_type)
    return actions + added, len(added)


def _required_messages(request: ExecutionRequest, policy: dict[str, Any]) -> list[Message]:
    messages = []
    for req in policy.get("requirements", []):
        req_type = req.get("type", "")
        if req_type == "outgoing_messages":
            # Read from the triggering event payload (authoritative), not the policy summary
            all_ids = list(request.triggering_event.payload.get("operator_ids", []))
            for agent_id in all_ids:
                messages.append(Message.create(
                    sender_id=request.agent_profile.agent_id,
                    recipient_id=AgentId(agent_id),
                    message_type=MessageType(req["message_type"]),
                    priority=request.triggering_event.priority,
                    payload=_status_request_payload(request),
                    correlation_id=request.triggering_event.correlation_id or request.triggering_event.event_id,
                ))
        elif req_type == "outgoing_message":
            messages.append(Message.create(
                sender_id=request.agent_profile.agent_id,
                recipient_id=AgentId(req["recipient_id"]),
                message_type=MessageType(req["message_type"]),
                priority=request.triggering_event.priority,
                payload=_status_update_payload(request),
                correlation_id=request.triggering_event.correlation_id or request.triggering_event.event_id,
            ))
    return messages


def _required_actions(request: ExecutionRequest, policy: dict[str, Any]) -> list[EnvironmentAction]:
    actions = []
    for req in policy.get("requirements", []):
        if req.get("type") != "environment_action":
            continue
        action_type = req["action_type"]
        actions.append(EnvironmentAction(
            action_type=action_type,
            payload=_action_payload(request, action_type),
        ))
    return actions


def _action_payload(request: ExecutionRequest, action_type: str) -> dict[str, Any]:
    if action_type == "adjust_inventory":
        return {"region": request.agent_profile.region, "delta": 15}
    if action_type == "adjust_transport_capacity":
        return {"delta": 5}
    return {
        "summary": (
            f"{request.agent_profile.role} reviewed "
            f"{request.environment.scenario} "
            f"event {request.triggering_event.event_type.value}"
        )
    }


def _status_request_payload(request: ExecutionRequest) -> dict[str, Any]:
    variables = request.environment.variables
    if request.environment.scenario == "supply_chain":
        return {
            "demand": variables.get("demand", 0),
            "risk_level": variables.get("risk_level", "normal"),
            "summary": request.triggering_event.payload.get("summary", ""),
        }
    return {
        "severity": variables.get("severity", 0),
        "regions": list(variables.get("regions", [])),
        "summary": request.triggering_event.payload.get("summary", ""),
    }


def _status_update_payload(request: ExecutionRequest) -> dict[str, Any]:
    variables = request.environment.variables
    role = request.agent_profile.role
    payload: dict[str, Any] = {
        "role": role,
        "region": request.agent_profile.region,
    }
    if request.environment.scenario == "supply_chain":
        risk_level = str(variables.get("risk_level", "normal"))
        payload.update(
            {
                "status": "strained" if risk_level != "normal" else "normal",
                "demand": variables.get("demand", 0),
                "risk_level": risk_level,
            }
        )
    else:
        severity = int(variables.get("severity", 0))
        payload.update(
            {
                "status": "strained" if severity >= 3 else "normal",
                "severity": severity,
            }
        )
    return payload
