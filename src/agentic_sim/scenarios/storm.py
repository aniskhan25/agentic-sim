from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agentic_sim.environment import StormEnvironment
from agentic_sim.execution import BatchBuilder, MockExecutionBackend, RuleExecutionBackend
from agentic_sim.models import AgentId, AgentProfile
from agentic_sim.scenarios.common import create_store, string_list
from agentic_sim.scheduling import FIFOScheduler
from agentic_sim.state.base import RuntimeStore

if TYPE_CHECKING:
    from agentic_sim.engine.simulation_engine import SimulationEngine


def create_storm_store(
    storage_mode: str = "memory",
    sqlite_path: str = "data/storm.sqlite",
    agent_replicas: int = 1,
    profiles: list[AgentProfile] | None = None,
    scenario_parameters: dict[str, Any] | None = None,
) -> RuntimeStore:
    scenario_parameters = scenario_parameters or {}
    profiles = profiles or _storm_profiles(agent_replicas)
    environment = _storm_environment(profiles, scenario_parameters)
    return create_store(
        storage_mode=storage_mode,
        sqlite_path=sqlite_path,
        environment=environment.initialize(),
        profiles=profiles,
    )


def create_storm_engine(
    *,
    storage_mode: str = "memory",
    sqlite_path: str = "data/storm.sqlite",
    backend_name: str = "mock",
    max_batch_size: int = 4,
    max_events_per_tick: int = 32,
    agent_replicas: int = 1,
    scenario_parameters: dict[str, Any] | None = None,
) -> SimulationEngine:
    scenario_parameters = scenario_parameters or {}
    profiles = _storm_profiles(agent_replicas)
    environment = _storm_environment(profiles, scenario_parameters)
    store = create_store(
        storage_mode=storage_mode,
        sqlite_path=sqlite_path,
        environment=environment.initialize(),
        profiles=profiles,
    )
    backend = RuleExecutionBackend() if backend_name == "rule" else MockExecutionBackend()
    from agentic_sim.engine.simulation_engine import SimulationEngine

    return SimulationEngine(
        store=store,
        scheduler=FIFOScheduler(),
        backend=backend,
        environment=environment,
        batch_builder=BatchBuilder(max_batch_size=max_batch_size),
        max_events_per_tick=max_events_per_tick,
    )


def _storm_profiles(agent_replicas: int) -> list[AgentProfile]:
    if agent_replicas < 1:
        raise ValueError("agent_replicas must be at least 1")

    profiles = [
        AgentProfile(
            agent_id=AgentId("agent_coordinator"),
            role="coordinator",
            name="Regional Coordinator",
            region="national",
            capabilities=["triage", "dispatch"],
            authority_level=3,
        ),
    ]
    for index in range(agent_replicas):
        suffix = "" if agent_replicas == 1 else f"_{index + 1:03d}"
        region = "helsinki" if index % 2 == 0 else "oulu"
        profiles.extend(
            [
                AgentProfile(
                    agent_id=AgentId(f"agent_hospital{suffix}"),
                    role="hospital",
                    name=f"Hospital Operations{suffix}",
                    region=region,
                    capabilities=["capacity_report"],
                    authority_level=2,
                ),
                AgentProfile(
                    agent_id=AgentId(f"agent_utility{suffix}"),
                    role="utility",
                    name=f"Utility Operations{suffix}",
                    region=region,
                    capabilities=["grid_report"],
                    authority_level=2,
                ),
                AgentProfile(
                    agent_id=AgentId(f"agent_forecaster{suffix}"),
                    role="forecaster",
                    name=f"Weather Forecaster{suffix}",
                    region="national",
                    capabilities=["forecast"],
                    authority_level=1,
                ),
            ]
        )
    return profiles


def _storm_environment(
    profiles: list[AgentProfile], scenario_parameters: dict[str, Any]
) -> StormEnvironment:
    operator_ids = [
        str(profile.agent_id) for profile in profiles if profile.role in {"hospital", "utility"}
    ]
    return StormEnvironment(
        regions=string_list(scenario_parameters.get("regions")) or None,
        severity_step=int(scenario_parameters.get("severity_step", 1)),
        operator_ids=operator_ids,
    )
