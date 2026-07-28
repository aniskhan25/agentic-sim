from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CausalViolation:
    check: str  # "missing_parent" | "duplicate" | "cycle" | "stale_read_or_conflict"
    node_id: str
    detail: str


@dataclass(slots=True)
class CausalVerificationResult:
    node_count: int
    violations: list[CausalViolation] = field(default_factory=list)


def verify(traces: list[Any]) -> CausalVerificationResult:
    """Reconstruct the causal graph from agent_step traces and check it.

    Scoped to the message-mediated causal chain (activation -> message ->
    recipient's next activation): messages are always activation-produced in
    this system, with no root case, unlike events (which can legitimately
    originate from a periodic environment tick with no causal parent).
    Event-level causal_parent_activation_id is populated elsewhere but not
    yet consumed here -- see docs/research_roadmap.md item 8.
    """
    steps = [
        trace.payload
        for trace in traces
        if trace.event_name == "agent_step" and "activation_id" in trace.payload
    ]

    violations: list[CausalViolation] = []
    violations.extend(_check_duplicates(steps))
    violations.extend(_check_missing_parents(steps))
    violations.extend(_check_cycles(steps))
    violations.extend(_check_stale_read_or_conflict(steps))

    return CausalVerificationResult(node_count=len(steps), violations=violations)


def _check_duplicates(steps: list[dict[str, Any]]) -> list[CausalViolation]:
    activation_counts: dict[str, int] = {}
    message_counts: dict[str, int] = {}
    for step in steps:
        activation_id = step["activation_id"]
        activation_counts[activation_id] = activation_counts.get(activation_id, 0) + 1
        for message_id in step.get("outgoing_message_ids", []):
            message_counts[message_id] = message_counts.get(message_id, 0) + 1

    violations = [
        CausalViolation("duplicate", activation_id, f"activation_id committed {count} times")
        for activation_id, count in activation_counts.items()
        if count > 1
    ]
    violations.extend(
        CausalViolation("duplicate", message_id, f"message_id produced {count} times")
        for message_id, count in message_counts.items()
        if count > 1
    )
    return violations


def _check_missing_parents(steps: list[dict[str, Any]]) -> list[CausalViolation]:
    produced_message_ids = {
        message_id for step in steps for message_id in step.get("outgoing_message_ids", [])
    }
    violations = []
    for step in steps:
        for parent_id in step.get("causal_parents", []):
            if parent_id.startswith("msg_") and parent_id not in produced_message_ids:
                violations.append(
                    CausalViolation(
                        "missing_parent",
                        step["activation_id"],
                        f"references message {parent_id}, never produced in this run",
                    )
                )
    return violations


def _check_cycles(steps: list[dict[str, Any]]) -> list[CausalViolation]:
    producer_by_message: dict[str, str] = {}
    for step in steps:
        for message_id in step.get("outgoing_message_ids", []):
            producer_by_message[message_id] = step["activation_id"]

    edges: dict[str, list[str]] = {step["activation_id"]: [] for step in steps}
    for step in steps:
        for parent_id in step.get("causal_parents", []):
            producer = producer_by_message.get(parent_id)
            if producer is not None and producer in edges:
                edges[step["activation_id"]].append(producer)

    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for parent in edges.get(node, []):
            if dfs(parent):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return [
        CausalViolation("cycle", node, "causal parent chain contains a cycle")
        for node in edges
        if node not in visited and dfs(node)
    ]


def _check_stale_read_or_conflict(steps: list[dict[str, Any]]) -> list[CausalViolation]:
    """A conflict is two commits claiming the same state_version_read; a stale
    read is a commit_version_written that isn't state_version_read + 1. Always
    passes on today's sequential execution -- it's a regression guard that
    with_activation_count() fires exactly once per commit, and becomes the
    load-bearing check once Phase 5 introduces concurrency.
    """
    violations: list[CausalViolation] = []
    seen_reads_by_agent: dict[str, set[int]] = {}
    for step in steps:
        agent_id = step.get("agent_id")
        version_read = step.get("state_version_read")
        version_written = step.get("commit_version_written")
        if agent_id is None or version_read is None or version_written is None:
            continue
        seen_reads = seen_reads_by_agent.setdefault(agent_id, set())
        if version_read in seen_reads:
            violations.append(
                CausalViolation(
                    "stale_read_or_conflict",
                    step["activation_id"],
                    f"agent {agent_id}: state_version_read={version_read} claimed by more than one activation",
                )
            )
        seen_reads.add(version_read)
        if version_written != version_read + 1:
            violations.append(
                CausalViolation(
                    "stale_read_or_conflict",
                    step["activation_id"],
                    f"agent {agent_id}: commit_version_written={version_written} "
                    f"is not state_version_read+1 ({version_read + 1})",
                )
            )
    return violations
