from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agentic_sim.engine.simulation_engine import SimulationEngine
from agentic_sim.scenarios.storm import create_storm_engine
from agentic_sim.scenarios.supply_chain import create_supply_chain_engine

ScenarioFactory = Callable[..., SimulationEngine]

SCENARIOS: dict[str, ScenarioFactory] = {
    "storm": create_storm_engine,
    "supply_chain": create_supply_chain_engine,
}


def create_engine(
    *,
    scenario: str = "storm",
    storage_mode: str = "memory",
    sqlite_path: str = "data/storm.sqlite",
    backend_name: str = "mock",
    max_batch_size: int = 4,
    max_events_per_tick: int = 32,
    agent_replicas: int = 1,
    scenario_parameters: dict[str, Any] | None = None,
) -> SimulationEngine:
    try:
        factory = SCENARIOS[scenario]
    except KeyError as exc:
        supported = ", ".join(sorted(SCENARIOS))
        message = f"unsupported scenario {scenario!r}; supported scenarios: {supported}"
        raise ValueError(message) from exc
    return factory(
        storage_mode=storage_mode,
        sqlite_path=sqlite_path,
        backend_name=backend_name,
        max_batch_size=max_batch_size,
        max_events_per_tick=max_events_per_tick,
        agent_replicas=agent_replicas,
        scenario_parameters=scenario_parameters,
    )
