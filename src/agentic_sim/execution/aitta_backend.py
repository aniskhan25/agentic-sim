from __future__ import annotations

import json
import os
import time
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from agentic_sim.models import (
    AgentId,
    AgentState,
    AgentStatus,
    EnvironmentAction,
    Event,
    EventType,
    ExecutionRequest,
    ExecutionResult,
    Message,
    MessageType,
)
from agentic_sim.utils.serialization import to_jsonable
from agentic_sim.utils.time import utc_now

Transport = Callable[[str, dict[str, str], dict[str, Any], float], dict[str, Any]]


class AittaExecutionBackend:
    """OpenAI-compatible Aitta chat-completions backend."""

    name = "aitta"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model_name: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int = 3,
        max_concurrency: int = 1,
        temperature: float = 0.2,
        top_p: float = 0.95,
        max_completion_tokens: int | None = None,
        transport: Transport | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("AITTA_API_KEY", "")
        self.base_url = base_url or os.environ.get("AITTA_BASE_URL", "")
        self.model_name = model_name or os.environ.get("AITTA_MODEL", "")
        self.timeout_seconds = float(
            timeout_seconds if timeout_seconds is not None else os.environ.get("AITTA_REQUEST_TIMEOUT", 120)
        )
        self.max_retries = max(0, max_retries)
        self.max_concurrency = max(1, max_concurrency)
        self.temperature = temperature
        self.top_p = top_p
        self.max_completion_tokens = int(
            max_completion_tokens or os.environ.get("AITTA_MAX_COMPLETION_TOKENS", 256)
        )
        self.transport = transport or _post_json

        if not self.api_key:
            raise ValueError("AITTA_API_KEY is required for the Aitta backend")
        if not self.base_url:
            raise ValueError("AITTA_BASE_URL is required for the Aitta backend")
        if not self.model_name:
            raise ValueError("AITTA_MODEL is required for the Aitta backend")

    def run_batch(self, requests: list[ExecutionRequest]) -> list[ExecutionResult]:
        if self.max_concurrency == 1 or len(requests) <= 1:
            return [self._run_one(request) for request in requests]
        workers = min(self.max_concurrency, len(requests))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            return list(executor.map(self._run_one, requests))

    def _run_one(self, request: ExecutionRequest) -> ExecutionResult:
        payload = self._request_payload(request)
        started = time.perf_counter()
        response, retry_count = self._send(payload)
        latency_seconds = time.perf_counter() - started
        content = _first_choice_text(response)
        try:
            proposal = _json_object(content)
        except (json.JSONDecodeError, ValueError) as exc:
            proposal = {
                "metadata": {
                    "model_output_invalid": True,
                    "model_output_error": str(exc),
                }
            }
        return self._result_from_proposal(request, proposal, response, latency_seconds, retry_count)

    def _send(self, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
        url = self.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return self.transport(url, headers, payload, self.timeout_seconds), attempt
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
        raise RuntimeError(
            f"Aitta request failed after {self.max_retries + 1} attempt(s): {last_error}"
        ) from last_error

    def _request_payload(self, request: ExecutionRequest) -> dict[str, Any]:
        return {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": _request_prompt(request)},
            ],
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_completion_tokens": self.max_completion_tokens,
            "n": 1,
        }

    def _result_from_proposal(
        self,
        request: ExecutionRequest,
        proposal: dict[str, Any],
        response: dict[str, Any],
        latency_seconds: float,
        retry_count: int = 0,
    ) -> ExecutionResult:
        state = _updated_state(request, proposal)
        metadata = {
            "backend": self.name,
            "model": self.model_name,
            "role": request.agent_profile.role,
            "latency_seconds": round(latency_seconds, 3),
            "retry_count": retry_count,
            "usage": response.get("usage"),
        }
        metadata.update(_optional_dict(proposal, "metadata"))
        messages = _messages(request, proposal.get("outgoing_messages", []))
        actions = _environment_actions(proposal.get("environment_actions", []))
        policy = _role_policy(request)
        messages, added_messages = _ensure_required_messages(request, messages, policy)
        actions, added_actions = _ensure_required_actions(request, actions, policy)
        metadata["policy_guard_added_messages"] = added_messages
        metadata["policy_guard_added_actions"] = added_actions
        return ExecutionResult(
            agent_id=request.agent_profile.agent_id,
            updated_state=state,
            outgoing_messages=messages,
            environment_actions=actions,
            emitted_events=_events(request, proposal.get("emitted_events", [])),
            metadata=metadata,
        )


def check_aitta_connection(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model_name: str | None = None,
    timeout_seconds: float | None = None,
    max_retries: int = 0,
    transport: Transport | None = None,
) -> dict[str, Any]:
    backend = AittaExecutionBackend(
        api_key=api_key,
        base_url=base_url,
        model_name=model_name,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        temperature=0,
        max_completion_tokens=64,
        transport=transport,
    )
    payload = {
        "model": backend.model_name,
        "messages": [
            {"role": "system", "content": "Return only valid JSON."},
            {"role": "user", "content": 'Return exactly {"ok": true}.'},
        ],
        "temperature": 0,
        "max_completion_tokens": 64,
        "response_format": {"type": "json_object"},
        "n": 1,
    }
    started = time.perf_counter()
    response, _ = backend._send(payload)
    latency_seconds = round(time.perf_counter() - started, 3)
    content = _first_choice_text(response)
    parsed = _json_object(content)
    return {
        "ok": parsed.get("ok") is True,
        "base_url": backend.base_url,
        "model": backend.model_name,
        "latency_seconds": latency_seconds,
        "usage": response.get("usage"),
    }


def _post_json(
    url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _system_prompt() -> str:
    return (
        "You are controlling one agent in an event-driven simulation. "
        "Return only valid JSON. Do not include markdown or explanatory text. "
        "Allowed top-level keys: current_goal, working_memory, outgoing_messages, "
        "environment_actions, emitted_events, metadata. "
        "Messages require recipient_id, message_type, and optional priority and payload. "
        "Environment actions require action_type and optional payload. "
        "Use the environment state, triggering event, and inbox messages to write specific, "
        "context-aware content. Payload values should reflect actual conditions such as "
        "severity, risk level, region, demand, or capacity — not generic placeholders. "
        "Follow the role_policy exactly; if it lists required outputs, include them."
    )


def _request_prompt(request: ExecutionRequest) -> str:
    payload = {
        "agent_profile": to_jsonable(request.agent_profile),
        "agent_state": to_jsonable(request.agent_state),
        "triggering_event": to_jsonable(request.triggering_event),
        "environment": to_jsonable(request.environment),
        "inbox_messages": [to_jsonable(message) for message in request.inbox_messages],
        "allowed_message_types": [item.value for item in MessageType],
        "allowed_event_types": [item.value for item in EventType],
        "role_policy": _role_policy(request),
        "response_shape": _response_shape(request),
    }
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def _response_shape(request: ExecutionRequest) -> dict[str, Any]:
    """Return a role- and scenario-specific example showing the expected output shape."""
    role = request.agent_profile.role
    scenario = request.environment.scenario
    variables = request.environment.variables
    event_payload = request.triggering_event.payload
    priority = request.triggering_event.priority
    agent_id = str(request.agent_profile.agent_id)
    region = request.agent_profile.region or "unknown"

    if scenario == "storm":
        severity = int(variables.get("severity", 0))
        regions = list(variables.get("regions", []))
        regions_str = ", ".join(regions) if regions else "affected regions"
        status = "strained" if severity >= 3 else "normal"

        if role == "coordinator":
            operator_ids = list(event_payload.get("operator_ids", []))
            example_recipient = operator_ids[0] if operator_ids else "agent_hospital"
            return {
                "current_goal": f"Coordinate severity-{severity} storm response across {regions_str}",
                "working_memory": {
                    "decision": f"Requesting status from {len(operator_ids)} operator(s); severity {severity} requires immediate coordination"
                },
                "outgoing_messages": [
                    {
                        "recipient_id": example_recipient,
                        "message_type": MessageType.STATUS_REQUEST.value,
                        "priority": priority,
                        "payload": {
                            "severity": severity,
                            "regions": regions,
                            "coordinator_id": agent_id,
                            "summary": f"Severity-{severity} storm event; report current capacity and operational status",
                        },
                    }
                ],
                "environment_actions": [
                    {
                        "action_type": "update_summary",
                        "payload": {
                            "summary": (
                                f"Coordinator activated: severity-{severity} storm affecting {regions_str}; "
                                f"status requested from {len(operator_ids)} operator(s)"
                            )
                        },
                    }
                ],
                "emitted_events": [],
                "metadata": {"policy_reason": f"Severity {severity} triggers mandatory coordination protocol"},
            }

        if role in {"hospital", "utility"}:
            coordinator_id = event_payload.get("coordinator_id") or event_payload.get("sender_id", "agent_coordinator")
            capacity_note = "reduced capacity due to storm conditions" if severity >= 3 else "operating within normal parameters"
            return {
                "current_goal": f"Report {status} operational status to coordinator under severity-{severity} conditions",
                "working_memory": {
                    "decision": f"Severity {severity} {'exceeds' if severity >= 3 else 'is below'} threshold; reporting {status}"
                },
                "outgoing_messages": [
                    {
                        "recipient_id": coordinator_id,
                        "message_type": MessageType.STATUS_UPDATE.value,
                        "priority": priority,
                        "payload": {
                            "role": role,
                            "region": region,
                            "status": status,
                            "severity": severity,
                            "notes": capacity_note,
                        },
                    }
                ],
                "environment_actions": [],
                "emitted_events": [],
                "metadata": {"policy_reason": f"Severity {severity} {'requires strained' if severity >= 3 else 'allows normal'} status report"},
            }

        if role == "forecaster":
            trend = "intensifying" if severity >= 4 else ("stable" if severity >= 2 else "weakening")
            return {
                "current_goal": f"Issue updated forecast for severity-{severity} storm",
                "working_memory": {"decision": f"Storm is {trend}; updating environment with current assessment"},
                "outgoing_messages": [],
                "environment_actions": [
                    {
                        "action_type": "update_summary",
                        "payload": {
                            "summary": (
                                f"Forecaster: severity-{severity} storm {trend}, "
                                f"affecting {regions_str}; monitoring for escalation"
                            )
                        },
                    }
                ],
                "emitted_events": [],
                "metadata": {"policy_reason": f"Active severity-{severity} event requires forecast update"},
            }

    if scenario == "supply_chain":
        risk_level = str(variables.get("risk_level", "normal"))
        demand = variables.get("demand", 0)
        status = "strained" if risk_level != "normal" else "normal"

        if role == "coordinator":
            operator_ids = list(event_payload.get("operator_ids", []))
            example_recipient = operator_ids[0] if operator_ids else "agent_supplier"
            return {
                "current_goal": f"Coordinate supply chain response to {risk_level} risk conditions",
                "working_memory": {
                    "decision": f"Risk level {risk_level} with demand {demand}; contacting {len(operator_ids)} node(s)"
                },
                "outgoing_messages": [
                    {
                        "recipient_id": example_recipient,
                        "message_type": MessageType.STATUS_REQUEST.value,
                        "priority": priority,
                        "payload": {
                            "demand": demand,
                            "risk_level": risk_level,
                            "coordinator_id": agent_id,
                            "summary": f"Risk level {risk_level} with demand {demand}; report operational status",
                        },
                    }
                ],
                "environment_actions": [
                    {
                        "action_type": "update_summary",
                        "payload": {
                            "summary": (
                                f"Coordinator activated: {risk_level} risk, demand {demand}; "
                                f"status requested from {len(operator_ids)} supply chain node(s)"
                            )
                        },
                    }
                ],
                "emitted_events": [],
                "metadata": {"policy_reason": f"Risk level {risk_level} triggers supply chain coordination"},
            }

        if role in {"supplier", "warehouse", "transport", "retailer"}:
            coordinator_id = event_payload.get("coordinator_id") or event_payload.get("sender_id", "agent_coordinator")
            role_notes = {
                "supplier": f"inventory pressure elevated at demand {demand}",
                "warehouse": f"prioritising stock allocation for demand {demand}",
                "transport": f"routing capacity {'stressed' if risk_level != 'normal' else 'nominal'} at demand {demand}",
                "retailer": f"demand spike of {demand} exceeding normal levels" if risk_level != "normal" else f"demand {demand} within normal range",
            }
            notes = role_notes.get(role, f"operating under {risk_level} risk conditions")
            messages = [
                {
                    "recipient_id": coordinator_id,
                    "message_type": MessageType.STATUS_UPDATE.value,
                    "priority": priority,
                    "payload": {
                        "role": role,
                        "region": region,
                        "status": status,
                        "demand": demand,
                        "risk_level": risk_level,
                        "notes": notes,
                    },
                }
            ]
            actions: list[dict[str, Any]] = []
            if risk_level != "normal":
                allowed = _allowed_environment_actions(scenario, role)
                if "adjust_inventory" in allowed:
                    actions.append({"action_type": "adjust_inventory", "payload": {"region": region, "delta": 15}})
                elif "adjust_transport_capacity" in allowed:
                    actions.append({"action_type": "adjust_transport_capacity", "payload": {"delta": 5}})
                elif "update_summary" in allowed:
                    actions.append({"action_type": "update_summary", "payload": {"summary": f"{role} in {region} prioritising inventory under {risk_level} risk"}})
            return {
                "current_goal": f"Report {status} supply chain status as {role} in {region}",
                "working_memory": {"decision": f"Risk level {risk_level} with demand {demand}; reporting {status} status"},
                "outgoing_messages": messages,
                "environment_actions": actions,
                "emitted_events": [],
                "metadata": {"policy_reason": f"Risk level {risk_level} requires {status} status report"},
            }

    # Fallback for unrecognised scenario/role combinations
    return {
        "current_goal": "Respond to triggering event",
        "working_memory": {"decision": "processing event"},
        "outgoing_messages": [],
        "environment_actions": [],
        "emitted_events": [],
        "metadata": {"policy_reason": "following role policy"},
    }


def _role_policy(request: ExecutionRequest) -> dict[str, Any]:
    scenario = request.environment.scenario
    role = request.agent_profile.role
    variables = request.environment.variables
    event_payload = request.triggering_event.payload
    policy: dict[str, Any] = {
        "scenario": scenario,
        "role": role,
        "requirements": [],
        "allowed_environment_actions": _allowed_environment_actions(scenario, role),
    }
    if role == "coordinator":
        policy["requirements"].append(
            {
                "type": "outgoing_messages",
                "instruction": "Send a status_request to every operator_id in the triggering event payload.",
                "operator_ids": list(event_payload.get("operator_ids", [])),
                "message_type": MessageType.STATUS_REQUEST.value,
                "payload_guidance": (
                    "Include your agent_id as coordinator_id, the current severity or risk_level "
                    "from environment variables, affected regions or demand, and a concise summary "
                    "of the event so operators have context for their response."
                ),
            }
        )
        policy["requirements"].append(
            {
                "type": "environment_action",
                "instruction": "Update the environment summary with the coordinator assessment.",
                "action_type": "update_summary",
                "payload_guidance": (
                    "Write a one-sentence summary naming the event type, current severity or risk level, "
                    "affected scope, and which operators you have contacted."
                ),
            }
        )
    elif role in {"hospital", "utility"}:
        severity = int(variables.get("severity", 0))
        policy["requirements"].append(
            {
                "type": "outgoing_message",
                "instruction": "Send one status_update to the coordinator_id from the triggering event payload.",
                "recipient_id": event_payload.get("coordinator_id") or event_payload.get("sender_id", "agent_coordinator"),
                "message_type": MessageType.STATUS_UPDATE.value,
                "status_rule": "Use strained when severity is 3 or higher; otherwise normal.",
                "severity": severity,
                "payload_guidance": (
                    f"Set status to {'strained' if severity >= 3 else 'normal'}. "
                    "Include your role, region, current severity, and a brief note on operational impact "
                    f"(e.g. capacity constraints for hospital, service disruption for utility)."
                ),
            }
        )
    elif role == "forecaster":
        policy["requirements"].append(
            {
                "type": "environment_action",
                "instruction": "Update the environment summary with a concise forecast assessment.",
                "action_type": "update_summary",
                "payload_guidance": (
                    "Write a summary that names the current severity, affected regions, trend direction "
                    "(intensifying / stable / weakening), and estimated time to peak impact. "
                    "Base it on environment variables."
                ),
            }
        )
    elif role in {"supplier", "warehouse", "transport", "retailer"}:
        risk_level = str(variables.get("risk_level", "normal"))
        policy["requirements"].append(
            {
                "type": "outgoing_message",
                "instruction": "Send one status_update to the coordinator_id from the triggering event payload.",
                "recipient_id": event_payload.get("coordinator_id") or event_payload.get("sender_id", "agent_coordinator"),
                "message_type": MessageType.STATUS_UPDATE.value,
                "risk_level": risk_level,
                "payload_guidance": (
                    f"Set status to {'strained' if risk_level != 'normal' else 'normal'}. "
                    "Include your role, region, current risk_level, demand value, and a brief note "
                    "on operational impact relevant to your role "
                    "(e.g. inventory pressure for supplier, routing delays for transport, "
                    "stock prioritisation for warehouse, demand spike for retailer)."
                ),
            }
        )
        if risk_level != "normal":
            allowed = _allowed_environment_actions(scenario, role)
            if allowed:
                policy["requirements"].append(
                    {
                        "type": "environment_action",
                        "action_type": allowed[0],
                        "instruction": "Propose one mitigation action relevant to your role.",
                        "payload_guidance": (
                            "Propose a concrete mitigation: specify a numeric delta for inventory or "
                            "capacity adjustments, or write a one-sentence summary for update_summary. "
                            "Use region from your agent_profile."
                        ),
                    }
                )
    return policy


def _first_choice_text(response: dict[str, Any]) -> str:
    try:
        choice = response["choices"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Aitta response did not include choices") from exc
    message = choice.get("message", {}) if isinstance(choice, dict) else {}
    content = message.get("content") or choice.get("text")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Aitta response choice did not include text content")
    return content


def _json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        start = 1  # skip opening fence line (```json or ```)
        end = len(lines) if lines[-1].strip() != "```" else len(lines) - 1
        cleaned = "\n".join(lines[start:end])
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Aitta output must be a JSON object")
    return data


def _updated_state(request: ExecutionRequest, proposal: dict[str, Any]) -> AgentState:
    state = request.agent_state.with_activation_count()
    memory = dict(state.working_memory)
    memory["last_event_type"] = request.triggering_event.event_type.value
    memory["last_environment_tick"] = request.environment.tick
    memory.update(_optional_dict(proposal, "working_memory"))
    current_goal = proposal.get("current_goal")
    return AgentState(
        agent_id=state.agent_id,
        status=AgentStatus.IDLE,
        current_goal=current_goal if isinstance(current_goal, str) else state.current_goal,
        working_memory=memory,
        pending_tasks=list(state.pending_tasks),
        inbox_cursor=request.inbox_messages[-1].message_id if request.inbox_messages else state.inbox_cursor,
        last_active_at=utc_now(),
        metrics=state.metrics,
    )


def _messages(request: ExecutionRequest, value: Any) -> list[Message]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("outgoing_messages must be a list")
    messages = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("outgoing_messages entries must be objects")
        recipient_id = _required_str(item, "recipient_id")
        message_type = MessageType(_required_str(item, "message_type"))
        messages.append(
            Message.create(
                sender_id=request.agent_profile.agent_id,
                recipient_id=AgentId(recipient_id),
                message_type=message_type,
                priority=int(item.get("priority", request.triggering_event.priority)),
                payload=_optional_dict(item, "payload"),
                correlation_id=item.get("correlation_id")
                or request.triggering_event.correlation_id
                or request.triggering_event.event_id,
            )
        )
    return messages


def _environment_actions(value: Any) -> list[EnvironmentAction]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("environment_actions must be a list")
    actions = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("environment_actions entries must be objects")
        actions.append(
            EnvironmentAction(
                action_type=_required_str(item, "action_type"),
                payload=_optional_dict(item, "payload"),
            )
        )
    return actions


def _events(request: ExecutionRequest, value: Any) -> list[Event]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("emitted_events must be a list")
    events = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("emitted_events entries must be objects")
        events.append(
            Event.create(
                EventType(_required_str(item, "event_type")),
                source=str(item.get("source") or request.agent_profile.agent_id),
                target_scope=_optional_dict(item, "target_scope") or {"agent_ids": [str(request.agent_profile.agent_id)]},
                payload=_optional_dict(item, "payload"),
                priority=int(item.get("priority", request.triggering_event.priority)),
                correlation_id=item.get("correlation_id")
                or request.triggering_event.correlation_id
                or request.triggering_event.event_id,
            )
        )
    return events


def _ensure_required_messages(
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


def _ensure_required_actions(
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
            for agent_id in req.get("operator_ids", []):
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


def _allowed_environment_actions(scenario: str, role: str) -> list[str]:
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


def _optional_dict(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return dict(value)


def _required_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} is required")
    return value
