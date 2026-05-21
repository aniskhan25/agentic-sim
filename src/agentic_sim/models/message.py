from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from agentic_sim.models.agent import AgentId
from agentic_sim.utils.ids import new_id
from agentic_sim.utils.time import utc_now


class MessageType(StrEnum):
    STATUS_REQUEST = "status_request"
    STATUS_UPDATE = "status_update"
    FORECAST_UPDATE = "forecast_update"
    COORDINATION_NOTICE = "coordination_notice"


@dataclass(slots=True)
class Message:
    message_id: str
    sender_id: AgentId
    recipient_id: AgentId
    message_type: MessageType
    priority: int
    created_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)
    thread_id: str | None = None
    reply_to: str | None = None
    correlation_id: str | None = None

    @classmethod
    def create(
        cls,
        *,
        sender_id: AgentId,
        recipient_id: AgentId,
        message_type: MessageType,
        payload: dict[str, Any] | None = None,
        priority: int = 0,
        thread_id: str | None = None,
        reply_to: str | None = None,
        correlation_id: str | None = None,
    ) -> "Message":
        return cls(
            message_id=new_id("msg"),
            sender_id=sender_id,
            recipient_id=recipient_id,
            message_type=message_type,
            priority=priority,
            created_at=utc_now(),
            payload=payload or {},
            thread_id=thread_id,
            reply_to=reply_to,
            correlation_id=correlation_id,
        )
