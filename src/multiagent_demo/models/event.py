from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from multiagent_demo.utils.ids import new_id
from multiagent_demo.utils.time import utc_now


class EventType(StrEnum):
    ENVIRONMENT_UPDATE = "environment_update"
    STORM_OUTAGE = "storm_outage"
    MESSAGE_ARRIVED = "message_arrived"
    TIMER_FIRED = "timer_fired"
    TOOL_RESULT = "tool_result"
    ESCALATION_NEEDED = "escalation_needed"


@dataclass(slots=True)
class Event:
    event_id: str
    event_type: EventType
    created_at: datetime
    scheduled_for: datetime
    source: str
    target_scope: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    correlation_id: str | None = None

    @classmethod
    def create(
        cls,
        event_type: EventType,
        *,
        source: str,
        target_scope: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        priority: int = 0,
        scheduled_for: datetime | None = None,
        correlation_id: str | None = None,
    ) -> "Event":
        now = utc_now()
        return cls(
            event_id=new_id("evt"),
            event_type=event_type,
            created_at=now,
            scheduled_for=scheduled_for or now,
            source=source,
            target_scope=target_scope or {},
            payload=payload or {},
            priority=priority,
            correlation_id=correlation_id,
        )
