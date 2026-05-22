from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agentic_sim.engine.simulation_engine import SimulationEngine
from agentic_sim.environment import StormEnvironment, SupplyChainEnvironment
from agentic_sim.execution import (
    BatchBuilder,
    MockExecutionBackend,
    RuleExecutionBackend,
    SupplyChainRuleBackend,
)
from agentic_sim.models import AgentId, AgentProfile, AgentState
from agentic_sim.scheduling import FIFOScheduler
from agentic_sim.state import InMemoryStateStore, SQLiteStateStore
from agentic_sim.state.base import RuntimeStore


def create_storm_store(
    storage_mode: str = "memory",
    sqlite_path: str = "data/storm.sqlite",
    agent_replicas: int = 1,
    profiles: list[AgentProfile] | None = None,
    scenario_parameters: dict[str, Any] | None = None,
) -> RuntimeStore:
    scenario_parameters = scenario_parameters or {}
    profiles = profiles or _storm_profiles(agent_replicas)
    operator_ids = [
        str(profile.agent_id) for profile in profiles if profile.role in {"hospital", "utility"}
    ]
    environment = StormEnvironment(
        regions=_string_list(scenario_parameters.get("regions")) or None,
        severity_step=int(scenario_parameters.get("severity_step", 1)),
        operator_ids=operator_ids,
    )
    initial_state = environment.initialize()
    if storage_mode == "sqlite":
        store: RuntimeStore = SQLiteStateStore(sqlite_path, environment=initial_state)
    else:
        store = InMemoryStateStore(initial_state)

    for profile in profiles:
        store.agents.put_profile(profile)
        store.agents.put_state(AgentState(agent_id=profile.agent_id))
    return store


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
    operator_ids = [
        str(profile.agent_id) for profile in profiles if profile.role in {"hospital", "utility"}
    ]
    environment = StormEnvironment(
        regions=_string_list(scenario_parameters.get("regions")) or None,
        severity_step=int(scenario_parameters.get("severity_step", 1)),
        operator_ids=operator_ids,
    )
    store = create_storm_store(
        storage_mode=storage_mode,
        sqlite_path=sqlite_path,
        agent_replicas=agent_replicas,
        profiles=profiles,
        scenario_parameters=scenario_parameters,
    )
    backend = RuleExecutionBackend() if backend_name == "rule" else MockExecutionBackend()
    return SimulationEngine(
        store=store,
        scheduler=FIFOScheduler(),
        backend=backend,
        environment=environment,
        batch_builder=BatchBuilder(max_batch_size=max_batch_size),
        max_events_per_tick=max_events_per_tick,
    )


def create_supply_chain_store(
    storage_mode: str = "memory",
    sqlite_path: str = "data/supply_chain.sqlite",
    agent_replicas: int = 1,
    profiles: list[AgentProfile] | None = None,
    scenario_parameters: dict[str, Any] | None = None,
) -> RuntimeStore:
    scenario_parameters = scenario_parameters or {}
    profiles = profiles or _supply_chain_profiles(agent_replicas)
    operator_ids = [str(profile.agent_id) for profile in profiles if profile.role != "coordinator"]
    environment = SupplyChainEnvironment(
        regions=_string_list(scenario_parameters.get("regions")) or None,
        demand_step=int(scenario_parameters.get("demand_step", 10)),
        delay_step=int(scenario_parameters.get("delay_step", 4)),
        operator_ids=operator_ids,
    )
    initial_state = environment.initialize()
    if storage_mode == "sqlite":
        store: RuntimeStore = SQLiteStateStore(sqlite_path, environment=initial_state)
    else:
        store = InMemoryStateStore(initial_state)

    for profile in profiles:
        store.agents.put_profile(profile)
        store.agents.put_state(AgentState(agent_id=profile.agent_id))
    return store


def _supply_chain_profiles(agent_replicas: int) -> list[AgentProfile]:
    if agent_replicas < 1:
        raise ValueError("agent_replicas must be at least 1")

    profiles = [
        AgentProfile(
            agent_id=AgentId("agent_coordinator"),
            role="coordinator",
            name="Supply Chain Coordinator",
            region="network",
            capabilities=["triage", "prioritize"],
            authority_level=3,
        ),
    ]
    for index in range(agent_replicas):
        suffix = "" if agent_replicas == 1 else f"_{index + 1:03d}"
        region = "helsinki" if index % 2 == 0 else "oulu"
        profiles.extend(
            [
                AgentProfile(
                    agent_id=AgentId(f"agent_supplier{suffix}"),
                    role="supplier",
                    name=f"Supplier Operations{suffix}",
                    region=region,
                    capabilities=["restock"],
                    authority_level=2,
                ),
                AgentProfile(
                    agent_id=AgentId(f"agent_warehouse{suffix}"),
                    role="warehouse",
                    name=f"Warehouse Operations{suffix}",
                    region=region,
                    capabilities=["inventory_report"],
                    authority_level=2,
                ),
                AgentProfile(
                    agent_id=AgentId(f"agent_transport{suffix}"),
                    role="transport",
                    name=f"Transport Operations{suffix}",
                    region=region,
                    capabilities=["shipment_report"],
                    authority_level=2,
                ),
                AgentProfile(
                    agent_id=AgentId(f"agent_retailer{suffix}"),
                    role="retailer",
                    name=f"Retail Operations{suffix}",
                    region=region,
                    capabilities=["demand_report"],
                    authority_level=1,
                ),
            ]
        )
    return profiles


def create_supply_chain_engine(
    *,
    storage_mode: str = "memory",
    sqlite_path: str = "data/supply_chain.sqlite",
    backend_name: str = "mock",
    max_batch_size: int = 4,
    max_events_per_tick: int = 32,
    agent_replicas: int = 1,
    scenario_parameters: dict[str, Any] | None = None,
) -> SimulationEngine:
    scenario_parameters = scenario_parameters or {}
    profiles = _supply_chain_profiles(agent_replicas)
    operator_ids = [str(profile.agent_id) for profile in profiles if profile.role != "coordinator"]
    environment = SupplyChainEnvironment(
        regions=_string_list(scenario_parameters.get("regions")) or None,
        demand_step=int(scenario_parameters.get("demand_step", 10)),
        delay_step=int(scenario_parameters.get("delay_step", 4)),
        operator_ids=operator_ids,
    )
    store = create_supply_chain_store(
        storage_mode=storage_mode,
        sqlite_path=sqlite_path,
        agent_replicas=agent_replicas,
        profiles=profiles,
        scenario_parameters=scenario_parameters,
    )
    if backend_name not in {"mock", "rule"}:
        raise ValueError(f"unsupported backend {backend_name!r}")
    backend = SupplyChainRuleBackend(name=backend_name)
    return SimulationEngine(
        store=store,
        scheduler=FIFOScheduler(),
        backend=backend,
        environment=environment,
        batch_builder=BatchBuilder(max_batch_size=max_batch_size),
        max_events_per_tick=max_events_per_tick,
    )


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


def _string_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]
