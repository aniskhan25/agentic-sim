from __future__ import annotations

from dataclasses import dataclass

from agentic_sim.models import PlatformTelemetrySample
from agentic_sim.observability.base import CommandRunner, run_subprocess
from agentic_sim.utils.time import to_iso, utc_now

# One CSV line per GPU: index, utilization.gpu, memory.used, memory.total,
# power.draw (memory fields are MiB, stored as-is into hbm_used_mb/hbm_total_mb --
# nvidia-smi does not report raw bytes the way rocm-smi does). Field shape
# based on public nvidia-smi documentation/examples -- not verified against
# real hardware output in this session (no CUDA GPU is available here).
_NVIDIA_SMI_ARGS = [
    "--query-gpu=index,utilization.gpu,memory.used,memory.total,power.draw",
    "--format=csv,noheader,nounits",
]

_FIELD_NAMES = (
    "accelerator_index",
    "gpu_utilization_percent",
    "hbm_used_mb",
    "hbm_total_mb",
    "gpu_power_watts",
)


def parse_nvidia_smi_csv(text: str, *, collected_at: str) -> list[PlatformTelemetrySample]:
    samples: list[PlatformTelemetrySample] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != len(_FIELD_NAMES):
            samples.append(
                PlatformTelemetrySample(
                    collected_at=collected_at,
                    source="nvidia-smi",
                    error=f"unexpected nvidia-smi CSV line: {line!r}",
                )
            )
            continue

        values = dict(zip(_FIELD_NAMES, parts))
        samples.append(
            PlatformTelemetrySample(
                collected_at=collected_at,
                source="nvidia-smi",
                accelerator_index=_to_int(values["accelerator_index"]),
                gpu_utilization_percent=_to_float(values["gpu_utilization_percent"]),
                hbm_used_mb=_to_float(values["hbm_used_mb"]),
                hbm_total_mb=_to_float(values["hbm_total_mb"]),
                gpu_power_watts=_to_float(values["gpu_power_watts"]),
            )
        )
    return samples


def _to_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _to_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


@dataclass(slots=True)
class CudaTelemetryCollector:
    runner: CommandRunner = run_subprocess
    binary: str = "nvidia-smi"
    timeout_seconds: float = 5.0

    def collect(self) -> list[PlatformTelemetrySample]:
        collected_at = to_iso(utc_now())
        try:
            stdout = self.runner([self.binary, *_NVIDIA_SMI_ARGS], self.timeout_seconds)
        except Exception as exc:  # noqa: BLE001 - any collection failure becomes an explicit sample
            return [PlatformTelemetrySample(collected_at=collected_at, source="nvidia-smi", error=str(exc))]
        return parse_nvidia_smi_csv(stdout, collected_at=collected_at)
