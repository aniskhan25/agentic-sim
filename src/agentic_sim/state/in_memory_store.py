from __future__ import annotations

from datetime import datetime

from agentic_sim.models import (
    AgentId,
    AgentProfile,
    AgentState,
    EnvironmentState,
    Event,
    Message,
    TraceRecord,
)


class InMemoryStateStore:
    """Small inspectable state store used by tests and local runs."""

    def __init__(self, environment: EnvironmentState):
        self.agents = self
        self.events = self
        self.messages = self
        self.environment = self
        self.traces = self
        self._profiles: dict[AgentId, AgentProfile] = {}
        self._states: dict[AgentId, AgentState] = {}
        self._events: dict[str, Event] = {}
        self._messages: dict[str, Message] = {}
        self._environment = environment
        self._traces: list[TraceRecord] = []

    def get_profile(self, agent_id: AgentId) -> AgentProfile:
        return self._profiles[agent_id]

    def put_profile(self, profile: AgentProfile) -> None:
        self._profiles[profile.agent_id] = profile

    def list_profiles(self) -> list[AgentProfile]:
        return list(self._profiles.values())

    def get_state(self, agent_id: AgentId) -> AgentState:
        return self._states[agent_id]

    def put_state(self, state: AgentState) -> None:
        self._states[state.agent_id] = state

    def put(self, item: Event | Message | EnvironmentState | TraceRecord) -> None:
        if isinstance(item, Event):
            self._events[item.event_id] = item
            return
        if isinstance(item, Message):
            self._messages[item.message_id] = item
            return
        if isinstance(item, EnvironmentState):
            self._environment = item
            return
        if isinstance(item, TraceRecord):
            self._traces.append(item)
            return
        raise TypeError(f"unsupported store item: {type(item)!r}")

    def put_many(self, items: list[Event] | list[Message]) -> None:
        for item in items:
            self.put(item)

    def pop_ready(self, now: datetime, limit: int | None = None) -> list[Event]:
        ready = [event for event in self._events.values() if event.scheduled_for <= now]
        ready.sort(key=lambda event: (-event.priority, event.scheduled_for, event.created_at))
        if limit is not None:
            ready = ready[:limit]
        for event in ready:
            del self._events[event.event_id]
        return ready

    def count_pending(self) -> int:
        return len(self._events)

    def inbox(self, agent_id: AgentId, limit: int = 10, after: str | None = None) -> list[Message]:
        messages = [m for m in self._messages.values() if m.recipient_id == agent_id]
        if after and after in self._messages:
            cursor_time = self._messages[after].created_at
            messages = [m for m in messages if m.created_at > cursor_time]
        messages.sort(key=lambda m: (-m.priority, m.created_at))
        return messages[:limit]

    def count(self) -> int:
        return len(self._messages)

    def get(self) -> EnvironmentState:
        return self._environment

    def list(self) -> list[TraceRecord]:
        return list(self._traces)
