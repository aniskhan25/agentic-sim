from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from agentic_sim.models import TraceRecord
from agentic_sim.state.base import TraceStore


class Telemetry(Protocol):
    def record_event(self, event_name: str, payload: dict[str, Any]) -> None: ...


@dataclass(slots=True)
class LocalTelemetry:
    """Default telemetry sink: writes straight into the run's trace store.

    This is the mechanism a future ROCm/CUDA collector (Phase 9) implements
    in place of, without SimulationEngine changing at all.
    """

    trace_store: TraceStore

    def record_event(self, event_name: str, payload: dict[str, Any]) -> None:
        self.trace_store.put(TraceRecord.create(event_name=event_name, payload=payload))
