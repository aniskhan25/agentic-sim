from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, NewType

AgentId = NewType("AgentId", str)


class AgentStatus(StrEnum):
    IDLE = "idle"
    ACTIVE = "active"
    PAUSED = "paused"


@dataclass(slots=True)
class AgentProfile:
    agent_id: AgentId
    role: str
    name: str
    region: str
    capabilities: list[str] = field(default_factory=list)
    authority_level: int = 0
    backend: str = "mock"


@dataclass(slots=True)
class AgentState:
    agent_id: AgentId
    status: AgentStatus = AgentStatus.IDLE
    current_goal: str = ""
    working_memory: dict[str, Any] = field(default_factory=dict)
    pending_tasks: list[str] = field(default_factory=list)
    inbox_cursor: str | None = None
    last_active_at: datetime | None = None
    metrics: dict[str, int | float] = field(default_factory=dict)

    def with_activation_count(self) -> "AgentState":
        metrics = dict(self.metrics)
        metrics["activations"] = int(metrics.get("activations", 0)) + 1
        return AgentState(
            agent_id=self.agent_id,
            status=self.status,
            current_goal=self.current_goal,
            working_memory=dict(self.working_memory),
            pending_tasks=list(self.pending_tasks),
            inbox_cursor=self.inbox_cursor,
            last_active_at=self.last_active_at,
            metrics=metrics,
        )
