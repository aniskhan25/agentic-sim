from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from agentic_sim.models.agent import AgentId, AgentState
from agentic_sim.models.event import Event
from agentic_sim.models.message import Message


class CommitStatus(StrEnum):
    COMMITTED = "committed"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"


@dataclass(slots=True)
class CommitUnit:
    """Everything one activation's atomic commit must apply together: its
    agent state mutation (guarded by expected_state_version for optimistic
    conflict detection), the messages it sends, and the events it emits
    (including router-derived MESSAGE_ARRIVED events). Environment mutation
    is intentionally out of scope -- see docs/research_roadmap.md item 10.
    """

    activation_id: str
    agent_id: AgentId
    expected_state_version: int
    updated_state: AgentState
    outgoing_messages: list[Message] = field(default_factory=list)
    emitted_events: list[Event] = field(default_factory=list)


@dataclass(slots=True)
class CommitReceipt:
    activation_id: str
    status: CommitStatus
    state_version_read: int
    commit_version_written: int | None
