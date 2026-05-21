from __future__ import annotations

from agentic_sim.models import TraceRecord
from agentic_sim.state.base import RuntimeStore


class TraceWriter:
    def write(self, store: RuntimeStore, event_name: str, payload: dict) -> TraceRecord:
        trace = TraceRecord.create(event_name=event_name, payload=payload)
        store.traces.put(trace)
        return trace
