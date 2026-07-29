from __future__ import annotations

import json
from dataclasses import dataclass

from agentic_sim.models import PlatformTelemetrySample
from agentic_sim.observability.base import CommandRunner, run_subprocess
from agentic_sim.utils.time import to_iso, utc_now

# rocm-smi --json nests one object per GPU under keys like "card0", "card1"
# (plus sometimes a non-card "system" key, skipped below). Field shape based
# on public rocm-smi documentation/examples -- not verified against real
# hardware output in this session (no ROCm GPU is available here).
_ROCM_SMI_ARGS = ["--showuse", "--showmeminfo", "vram", "--showpower", "--json"]

_BYTES_PER_MB = 1024 * 1024


def parse_rocm_smi_json(text: str, *, collected_at: str) -> list[PlatformTelemetrySample]:
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        return [PlatformTelemetrySample(collected_at=collected_at, source="rocm-smi", error=str(exc))]

    samples: list[PlatformTelemetrySample] = []
    for card_key, fields in payload.items():
        if not card_key.startswith("card") or not isinstance(fields, dict):
            continue
        try:
            index = int(card_key.removeprefix("card"))
        except ValueError:
            index = None

        vram_used_bytes = _to_float(fields.get("VRAM Total Used Memory (B)"))
        vram_total_bytes = _to_float(fields.get("VRAM Total Memory (B)"))

        samples.append(
            PlatformTelemetrySample(
                collected_at=collected_at,
                source="rocm-smi",
                accelerator_index=index,
                gpu_utilization_percent=_to_float(fields.get("GPU use (%)")),
                hbm_used_mb=vram_used_bytes / _BYTES_PER_MB if vram_used_bytes is not None else None,
                hbm_total_mb=vram_total_bytes / _BYTES_PER_MB if vram_total_bytes is not None else None,
                gpu_power_watts=_to_float(fields.get("Average Graphics Package Power (W)")),
            )
        )
    return samples


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(slots=True)
class RocmTelemetryCollector:
    runner: CommandRunner = run_subprocess
    binary: str = "rocm-smi"
    timeout_seconds: float = 5.0

    def collect(self) -> list[PlatformTelemetrySample]:
        collected_at = to_iso(utc_now())
        try:
            stdout = self.runner([self.binary, *_ROCM_SMI_ARGS], self.timeout_seconds)
        except Exception as exc:  # noqa: BLE001 - any collection failure becomes an explicit sample
            return [PlatformTelemetrySample(collected_at=collected_at, source="rocm-smi", error=str(exc))]
        return parse_rocm_smi_json(stdout, collected_at=collected_at)
