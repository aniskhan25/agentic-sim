from __future__ import annotations

import platform
from dataclasses import dataclass, field


@dataclass(slots=True)
class PlatformManifest:
    """Describes the execution substrate a run happened on.

    Minimal today (local, no accelerator); Phase 9 extends this for ROCm/CUDA
    self-hosted deployments rather than redesigning it from scratch.
    """

    backend_name: str
    accelerator: str = "none"
    host_architecture: str = field(default_factory=platform.machine)
    python_version: str = field(default_factory=platform.python_version)
    framework_versions: dict[str, str] = field(default_factory=dict)

    @classmethod
    def local_default(cls, backend_name: str) -> "PlatformManifest":
        return cls(backend_name=backend_name)
