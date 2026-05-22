from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RuntimeConfig:
    scenario: str = "storm"
    scenario_parameters: dict[str, Any] = field(default_factory=dict)
    steps: int = 4
    backend: str = "mock"
    storage_mode: str = "memory"
    sqlite_path: str | None = None
    max_batch_size: int = 4
    max_events_per_tick: int = 32
    agent_replicas: int = 1


def load_config(path: str | None) -> RuntimeConfig:
    if path is None:
        return RuntimeConfig()
    data = json.loads(Path(path).read_text())
    scenario = data.get("scenario", "storm")
    scenario_name = (
        str(scenario.get("name", "storm")) if isinstance(scenario, dict) else str(scenario)
    )
    scenario_parameters = (
        dict(scenario.get("parameters", {})) if isinstance(scenario, dict) else {}
    )
    return RuntimeConfig(
        scenario=scenario_name,
        scenario_parameters=scenario_parameters,
        steps=int(data.get("steps", 4)),
        backend=str(data.get("execution", {}).get("backend", "mock")),
        storage_mode=str(data.get("storage", {}).get("mode", "memory")),
        sqlite_path=data.get("storage", {}).get("sqlite_path"),
        max_batch_size=int(data.get("execution", {}).get("max_batch_size", 4)),
        max_events_per_tick=int(data.get("scheduler", {}).get("max_events_per_tick", 32)),
        agent_replicas=int(data.get("scenario", {}).get("agent_replicas", 1))
        if isinstance(data.get("scenario"), dict)
        else int(data.get("agent_replicas", 1)),
    )


def merge_cli(config: RuntimeConfig, overrides: dict[str, Any]) -> RuntimeConfig:
    values = {
        "scenario": config.scenario,
        "scenario_parameters": config.scenario_parameters,
        "steps": config.steps,
        "backend": config.backend,
        "storage_mode": config.storage_mode,
        "sqlite_path": config.sqlite_path,
        "max_batch_size": config.max_batch_size,
        "max_events_per_tick": config.max_events_per_tick,
        "agent_replicas": config.agent_replicas,
    }
    values.update({key: value for key, value in overrides.items() if value is not None})
    return RuntimeConfig(**values)
