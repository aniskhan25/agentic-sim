from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from agentic_sim.execution import role_policy
from agentic_sim.execution.capabilities import ProviderCapabilities
from agentic_sim.models import (
    AgentId,
    AgentState,
    AgentStatus,
    EnvironmentAction,
    Event,
    EventType,
    ExecutionReceipt,
    ExecutionRequest,
    ExecutionResult,
    Message,
    MessageType,
    Proposal,
    ValidationResult,
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
        max_json_repair_attempts: int = 1,
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
        self.max_json_repair_attempts = max(0, max_json_repair_attempts)
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

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_concurrency=self.max_concurrency > 1,
            supports_server_batching=False,
            supports_structured_output=True,
            supports_prefix_caching=False,
            max_context_tokens=self.max_completion_tokens,
            observable_token_usage=True,
            observable_energy=False,
        )

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
        content = _first_choice_text(response)
        proposal = self._try_parse(content)
        json_repair_attempts = 0
        attempt = 0
        while _is_invalid(proposal) and attempt < self.max_json_repair_attempts:
            attempt += 1
            payload = self._repair_payload(payload, content, proposal)
            response, extra_retries = self._send(payload)
            retry_count += extra_retries
            content = _first_choice_text(response)
            proposal = self._try_parse(content)
            json_repair_attempts = attempt
        latency_seconds = time.perf_counter() - started
        return self._result_from_proposal(
            request,
            proposal,
            response,
            latency_seconds,
            retry_count,
            json_repair_attempts=json_repair_attempts,
            raw_content=content,
        )

    def _try_parse(self, content: str) -> dict[str, Any]:
        try:
            return _json_object(content)
        except (json.JSONDecodeError, ValueError) as exc:
            return {
                "metadata": {
                    "model_output_invalid": True,
                    "model_output_error": str(exc),
                }
            }

    def _repair_payload(
        self, payload: dict[str, Any], bad_content: str, proposal: dict[str, Any]
    ) -> dict[str, Any]:
        error = proposal["metadata"]["model_output_error"]
        messages = list(payload["messages"]) + [
            {"role": "assistant", "content": bad_content},
            {
                "role": "user",
                "content": (
                    f"Your previous response was not valid JSON: {error}. "
                    "Return corrected JSON only, with no markdown or commentary."
                ),
            },
        ]
        return {**payload, "messages": messages}

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
        json_repair_attempts: int = 0,
        raw_content: str = "",
    ) -> ExecutionResult:
        state, state_mutation_violations, state_mutation_provenance = _updated_state(request, proposal)
        metadata = {
            "backend": self.name,
            "model": self.model_name,
            "role": request.agent_profile.role,
            "latency_seconds": round(latency_seconds, 3),
            "retry_count": retry_count,
            "usage": response.get("usage"),
        }
        metadata.update(_optional_dict(proposal, "metadata"))
        metadata["json_repair_attempts"] = json_repair_attempts
        messages = _messages(request, proposal.get("outgoing_messages", []))
        actions = _environment_actions(proposal.get("environment_actions", []))
        policy = role_policy.build_role_policy(request)

        raw_violations = role_policy.semantic_violations(request, messages, actions, policy)
        metadata["semantic_valid"] = not _is_invalid(proposal) and not raw_violations

        messages, actions, must_not_violations = role_policy.enforce_must_not(request, messages, actions, policy)
        metadata["must_not_violations"] = must_not_violations

        actions, bounded_violations = role_policy.enforce_bounded(actions)
        metadata["bounded_violations"] = bounded_violations

        messages, actions, cardinality_violations = role_policy.enforce_cardinality(request, messages, actions)
        metadata["cardinality_violations"] = cardinality_violations

        metadata["state_mutation_violations"] = state_mutation_violations

        kept_count = len(messages) + len(actions)

        messages, added_messages = role_policy.ensure_required_messages(request, messages, policy)
        actions, added_actions = role_policy.ensure_required_actions(request, actions, policy)
        metadata["policy_guard_added_messages"] = added_messages
        metadata["policy_guard_added_actions"] = added_actions

        total_final = kept_count + added_messages + added_actions
        metadata["message_action_committed_atom_count"] = total_final
        metadata["message_action_autonomy_rate"] = (
            round(kept_count / total_final, 6) if total_final else None
        )

        final_violations = role_policy.semantic_violations(request, messages, actions, policy)
        final_bounded_violations = role_policy.enforce_bounded(actions)[1]
        final_cardinality_violations = role_policy.enforce_cardinality(request, messages, actions)[2]
        metadata["useful_step"] = (
            not final_violations
            and final_bounded_violations == 0
            and final_cardinality_violations == 0
            and state_mutation_violations == 0
        )

        proposal_obj = Proposal(
            raw_content=raw_content,
            current_goal=proposal.get("current_goal"),
            working_memory=_optional_dict(proposal, "working_memory"),
            outgoing_messages=proposal.get("outgoing_messages") or [],
            environment_actions=proposal.get("environment_actions") or [],
            emitted_events=proposal.get("emitted_events") or [],
            metadata=_optional_dict(proposal, "metadata"),
            is_valid=not _is_invalid(proposal),
            parse_error=proposal.get("metadata", {}).get("model_output_error"),
        )

        validation_result = ValidationResult(
            semantic_valid=metadata["semantic_valid"],
            model_output_invalid=_is_invalid(proposal),
            model_output_error=proposal.get("metadata", {}).get("model_output_error"),
            json_repair_attempts=json_repair_attempts,
            must_not_violations=metadata["must_not_violations"],
            violation_reasons=final_violations,
            bounded_violations=metadata["bounded_violations"],
            cardinality_violations=metadata["cardinality_violations"],
            state_mutation_violations=state_mutation_violations,
            state_mutation_provenance=state_mutation_provenance,
            policy_guard_added_messages=added_messages,
            policy_guard_added_actions=added_actions,
            message_action_autonomy_rate=metadata["message_action_autonomy_rate"],
            message_action_committed_atom_count=metadata["message_action_committed_atom_count"],
            useful_step=metadata["useful_step"],
        )
        metadata["validation_result"] = to_jsonable(validation_result)

        receipt = ExecutionReceipt(
            activation_id=request.activation.activation_id,
            attempt_number=request.activation.attempt_number,
            provider=self.name,
            model=self.model_name,
            total_latency_seconds=round(latency_seconds, 3),
            token_usage=response.get("usage"),
            schema_valid=not _is_invalid(proposal),
            semantic_valid=metadata["semantic_valid"],
            repair_attempts=json_repair_attempts,
            policy_completion_applied=bool(added_messages or added_actions),
            fallback_used=_is_invalid(proposal),
            commit_status="proposed",
            error_reason=proposal.get("metadata", {}).get("model_output_error"),
        )
        metadata["execution_receipt"] = to_jsonable(receipt)

        return ExecutionResult(
            agent_id=request.agent_profile.agent_id,
            updated_state=state,
            outgoing_messages=messages,
            environment_actions=actions,
            emitted_events=_events(request, proposal.get("emitted_events", [])),
            metadata=metadata,
            proposal=proposal_obj,
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
    import urllib.error as _ue
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except _ue.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        raise _ue.HTTPError(exc.url, exc.code, f"{exc.reason} | body: {body}", exc.headers, None) from None


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
    profile = request.agent_profile
    payload = {
        "agent": {
            "agent_id": str(profile.agent_id),
            "role": profile.role,
            "region": profile.region,
        },
        "agent_state": {
            "status": request.agent_state.status.value,
            "current_goal": request.agent_state.current_goal,
            "working_memory": request.agent_state.working_memory,
        },
        "triggering_event": {
            "event_type": request.triggering_event.event_type.value,
            "priority": request.triggering_event.priority,
            "payload": _slim_payload(request.triggering_event.payload),
        },
        "environment": {
            "scenario": request.environment.scenario,
            "tick": request.environment.tick,
            "variables": request.environment.variables,
        },
        "inbox_messages": [
            {
                "sender_id": str(m.sender_id),
                "message_type": m.message_type.value,
                "payload": m.payload,
            }
            for m in request.inbox_messages
        ],
        "role_policy": role_policy.build_role_policy(request),
    }
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def _slim_payload(payload: dict[str, Any], max_list: int = 3) -> dict[str, Any]:
    result = {}
    for k, v in payload.items():
        if isinstance(v, list) and len(v) > max_list:
            result[k] = v[:max_list]
            result[f"{k}_total"] = len(v)
        else:
            result[k] = v
    return result


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


def _strip_code_fence(text: str) -> str:
    if text.startswith("```"):
        lines = text.splitlines()
        start = 1  # skip opening fence line (```json or ```)
        end = len(lines) if lines[-1].strip() != "```" else len(lines) - 1
        return "\n".join(lines[start:end])
    return text


def _scan_balanced(text: str, start: int) -> str | None:
    """Return the balanced {...} span beginning at `start`, or None if it never closes."""
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _iter_json_candidates(text: str, limit: int = 5):
    pos = 0
    tried = 0
    while tried < limit:
        start = text.find("{", pos)
        if start == -1:
            return
        span = _scan_balanced(text, start)
        if span is not None:
            yield span
        pos = start + 1
        tried += 1


def _strip_trailing_commas(text: str) -> str:
    return re.sub(r",\s*([}\]])", r"\1", text)


def _json_object(text: str) -> dict[str, Any]:
    cleaned = _strip_code_fence(text.strip())
    last_exc: Exception = ValueError("no JSON object found in model output")
    found_any_candidate = False
    for candidate in _iter_json_candidates(cleaned):
        found_any_candidate = True
        for attempt in (candidate, _strip_trailing_commas(candidate)):
            try:
                data = json.loads(attempt)
            except json.JSONDecodeError as exc:
                last_exc = exc
                continue
            if isinstance(data, dict):
                return data
            last_exc = ValueError("Aitta output must be a JSON object")
    if not found_any_candidate:
        last_exc = ValueError("no balanced JSON object found in model output (possibly truncated)")
    raise last_exc


SYSTEM_MANAGED_WORKING_MEMORY_KEYS = {"last_event_type", "last_environment_tick"}


def _updated_state(
    request: ExecutionRequest, proposal: dict[str, Any]
) -> tuple[AgentState, int, dict[str, str]]:
    state = request.agent_state.with_activation_count()
    model_memory = _optional_dict(proposal, "working_memory")
    violations = sum(1 for key in model_memory if key in SYSTEM_MANAGED_WORKING_MEMORY_KEYS)

    memory = dict(state.working_memory)
    memory.update(
        {key: value for key, value in model_memory.items() if key not in SYSTEM_MANAGED_WORKING_MEMORY_KEYS}
    )
    # system-managed keys are set last so the model can never silently override them
    memory["last_event_type"] = request.triggering_event.event_type.value
    memory["last_environment_tick"] = request.environment.tick

    provenance = {
        key: "model" for key in model_memory if key not in SYSTEM_MANAGED_WORKING_MEMORY_KEYS
    }
    provenance["last_event_type"] = "system"
    provenance["last_environment_tick"] = "system"

    current_goal = proposal.get("current_goal")
    provenance["current_goal"] = "model" if isinstance(current_goal, str) else "unchanged"

    new_state = AgentState(
        agent_id=state.agent_id,
        status=AgentStatus.IDLE,
        current_goal=current_goal if isinstance(current_goal, str) else state.current_goal,
        working_memory=memory,
        pending_tasks=list(state.pending_tasks),
        inbox_cursor=request.inbox_messages[-1].message_id if request.inbox_messages else state.inbox_cursor,
        last_active_at=utc_now(),
        metrics=state.metrics,
    )
    return new_state, violations, provenance


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


def _is_invalid(proposal: dict[str, Any]) -> bool:
    return bool(proposal.get("metadata", {}).get("model_output_invalid"))


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
