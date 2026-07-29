from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PlatformTelemetrySample:
    """One provider-neutral live telemetry snapshot (evaluation_plan.md's
    "Platform telemetry" section), polled repeatedly over a run -- distinct
    from PlatformManifest (a static, one-shot hardware/software descriptor)
    and ExecutionReceipt (a one-shot per-activation-attempt record).

    kv_cache_used_percent/preemption_count/queue_depth are part of the shared
    schema because evaluation_plan.md names serving-runtime request/KV-cache
    metrics as a required telemetry source, but no collector in this phase
    populates them -- item 16 builds only the ROCm/CUDA collectors below; a
    serving-runtime (e.g. vLLM /metrics) collector is future work (ADR 0002).
    Every field defaults to None rather than a fabricated value, matching
    PlatformManifest/ExecutionReceipt's established discipline: "missing
    telemetry is explicit rather than imputed."
    """

    collected_at: str
    source: str
    accelerator_index: int | None = None
    gpu_utilization_percent: float | None = None
    hbm_used_mb: float | None = None
    hbm_total_mb: float | None = None
    gpu_power_watts: float | None = None
    energy_joules: float | None = None
    host_cpu_utilization_percent: float | None = None
    kv_cache_used_percent: float | None = None
    preemption_count: int | None = None
    queue_depth: int | None = None
    error: str | None = None
