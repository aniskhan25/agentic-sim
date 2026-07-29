from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from agentic_sim.models import PlatformTelemetrySample, TraceRecord
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


class TelemetryCollector(Protocol):
    """Source of provider-neutral platform telemetry samples (item 16).

    Distinct from Telemetry: Telemetry is a generic event sink already wired
    everywhere; TelemetryCollector is a typed GPU-specific source. A sample
    only ever reaches SimulationEngine via Telemetry.record_event -- it never
    affects scheduling or control flow (target_architecture.md Rule 6).
    """

    def collect(self) -> list[PlatformTelemetrySample]: ...


# (argv, timeout_seconds) -> captured stdout text. Injectable so collectors
# are unit-testable without the real rocm-smi/nvidia-smi binary present.
CommandRunner = Callable[[list[str], float], str]


def run_subprocess(argv: list[str], timeout_seconds: float) -> str:
    result = subprocess.run(
        argv, capture_output=True, text=True, timeout=timeout_seconds, check=True
    )
    return result.stdout
