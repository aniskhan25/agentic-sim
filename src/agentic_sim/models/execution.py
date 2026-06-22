from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from agentic_sim.models.agent import AgentId, AgentProfile, AgentState
from agentic_sim.models.environment import EnvironmentAction, EnvironmentState
from agentic_sim.models.event import Event
from agentic_sim.models.message import Message
from agentic_sim.utils.ids import new_id
from agentic_sim.utils.time import utc_now


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
    backend_hint: str = "mock"


@dataclass(slots=True)
class ExecutionResult:
    agent_id: AgentId
    updated_state: AgentState
    outgoing_messages: list[Message] = field(default_factory=list)
    environment_actions: list[EnvironmentAction] = field(default_factory=list)
    emitted_events: list[Event] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SimulationTickResult:
    tick: int
    processed_events: int
    activations: int
    messages_emitted: int
    traces_written: int
