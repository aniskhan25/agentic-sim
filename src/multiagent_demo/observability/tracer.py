from __future__ import annotations

from multiagent_demo.models import TraceRecord
from multiagent_demo.state.base import RuntimeStore


class TraceWriter:
    def write(self, store: RuntimeStore, event_name: str, payload: dict) -> TraceRecord:
        trace = TraceRecord.create(event_name=event_name, payload=payload)
        store.traces.put(trace)
        return trace
