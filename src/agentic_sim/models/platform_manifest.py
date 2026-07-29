from __future__ import annotations

import platform
from dataclasses import dataclass, field


@dataclass(slots=True)
class PlatformManifest:
    """Describes the execution substrate a run happened on.

    Minimal today (local, no accelerator); Phase 9 extends this for ROCm/CUDA
    self-hosted deployments rather than redesigning it from scratch. The
    accelerator/serving-runtime fields below default to None (never a fake
    placeholder) until a real self-hosted backend populates them -- see
    docs/lumi_deployment_manifest.md and ADR 0005.
    """

    backend_name: str
    accelerator: str = "none"
    host_architecture: str = field(default_factory=platform.machine)
    python_version: str = field(default_factory=platform.python_version)
    framework_versions: dict[str, str] = field(default_factory=dict)
    accelerator_count: int | None = None
    accelerator_memory_gb: float | None = None
    driver_version: str | None = None
    serving_runtime: str | None = None
    serving_runtime_version: str | None = None
    interconnect: str | None = None
    placement_level: str | None = None
    manifest_mode: str | None = None

    @classmethod
    def local_default(cls, backend_name: str) -> "PlatformManifest":
        return cls(backend_name=backend_name)

    @classmethod
    def for_lumi(
        cls,
        backend_name: str,
        *,
        driver_version: str,
        serving_runtime_version: str,
        placement_level: str,
        manifest_mode: str,
        serving_runtime: str = "vllm",
    ) -> "PlatformManifest":
        """LUMI-G hardware constants are fixed (docs/lumi_deployment_manifest.md);
        run-time-only values (ROCm/driver version, serving-runtime version) have
        no sane default and must be supplied by whoever actually runs on the
        real cluster, refreshed at deployment time -- never invented here.
        """
        return cls(
            backend_name=backend_name,
            accelerator="AMD MI250X (1 GCD)" if placement_level == "single_device" else "AMD MI250X (8 GCDs)",
            host_architecture="x86_64",
            accelerator_count=1 if placement_level == "single_device" else 8,
            accelerator_memory_gb=64.0,
            driver_version=driver_version,
            serving_runtime=serving_runtime,
            serving_runtime_version=serving_runtime_version,
            interconnect="Slingshot",
            placement_level=placement_level,
            manifest_mode=manifest_mode,
        )

    @classmethod
    def for_roihu(
        cls,
        backend_name: str,
        *,
        driver_version: str,
        serving_runtime_version: str,
        placement_level: str,
        manifest_mode: str,
        serving_runtime: str = "vllm",
    ) -> "PlatformManifest":
        """Roihu hardware constants are fixed (docs/roihu_deployment_manifest.md);
        run-time-only values (CUDA driver version, serving-runtime version) have
        no sane default and must be supplied by whoever actually runs on the
        real cluster, refreshed at deployment time -- never invented here.
        """
        return cls(
            backend_name=backend_name,
            accelerator="NVIDIA GH200 (1 GPU)" if placement_level == "single_device" else "NVIDIA GH200 (4 GPUs)",
            host_architecture="aarch64",
            accelerator_count=1 if placement_level == "single_device" else 4,
            accelerator_memory_gb=96.0,
            driver_version=driver_version,
            serving_runtime=serving_runtime,
            serving_runtime_version=serving_runtime_version,
            interconnect="InfiniBand NDR",
            placement_level=placement_level,
            manifest_mode=manifest_mode,
        )
