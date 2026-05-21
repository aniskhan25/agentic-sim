from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from multiagent_demo.utils.ids import new_id
from multiagent_demo.utils.time import utc_now


@dataclass(slots=True)
class TraceRecord:
    trace_id: str
    timestamp: datetime
    event_name: str
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, event_name: str, payload: dict[str, Any] | None = None) -> "TraceRecord":
        return cls(
            trace_id=new_id("trc"),
            timestamp=utc_now(),
            event_name=event_name,
            payload=payload or {},
        )
