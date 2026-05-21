from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from multiagent_demo.models.agent import AgentId, AgentProfile, AgentState
from multiagent_demo.models.environment import EnvironmentAction, EnvironmentState
from multiagent_demo.models.event import Event
from multiagent_demo.models.message import Message
from multiagent_demo.utils.ids import new_id
from multiagent_demo.utils.time import utc_now


@dataclass(slots=True)
class Activation:
    activation_id: str
    agent_id: AgentId
    trigger_event_id: str
    activation_reason: str
    priority: int
    ready_at: datetime

    @classmethod
    def create(
        cls,
        *,
        agent_id: AgentId,
        trigger_event_id: str,
        activation_reason: str,
        priority: int,
        ready_at: datetime | None = None,
    ) -> "Activation":
        return cls(
            activation_id=new_id("act"),
            agent_id=agent_id,
            trigger_event_id=trigger_event_id,
            activation_reason=activation_reason,
            priority=priority,
            ready_at=ready_at or utc_now(),
        )


@dataclass(slots=True)
class ExecutionRequest:
    activation: Activation
    agent_profile: AgentProfile
    agent_state: AgentState
    inbox_messages: list[Message]
    triggering_event: Event
    environment: EnvironmentState
    step_budget: int = 1
    backend_hint: str = "mock"


@dataclass(slots=True)
class ExecutionResult:
    agent_id: AgentId
    updated_state: AgentState
    outgoing_messages: list[Message] = field(default_factory=list)
    environment_actions: list[EnvironmentAction] = field(default_factory=list)
    emitted_events: list[Event] = field(default_factory=list)
    tool_requests: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SimulationTickResult:
    tick: int
    processed_events: int
    activations: int
    messages_emitted: int
    traces_written: int
