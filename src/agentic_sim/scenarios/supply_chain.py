from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agentic_sim.environment import SupplyChainEnvironment
from agentic_sim.execution import BatchBuilder, create_execution_backend
from agentic_sim.models import AgentId, AgentProfile
from agentic_sim.scenarios.common import create_store, string_list
from agentic_sim.scheduling import FIFOScheduler
from agentic_sim.state.base import RuntimeStore

if TYPE_CHECKING:
    from agentic_sim.engine.simulation_engine import SimulationEngine


def create_supply_chain_store(
    storage_mode: str = "memory",
    sqlite_path: str = "data/supply_chain.sqlite",
    agent_replicas: int = 1,
    profiles: list[AgentProfile] | None = None,
    scenario_parameters: dict[str, Any] | None = None,
) -> RuntimeStore:
    scenario_parameters = scenario_parameters or {}
    profiles = profiles or _supply_chain_profiles(agent_replicas)
    environment = _supply_chain_environment(profiles, scenario_parameters)
    return create_store(
        storage_mode=storage_mode,
        sqlite_path=sqlite_path,
        environment=environment.initialize(),
        profiles=profiles,
    )


def create_supply_chain_engine(
    *,
    storage_mode: str = "memory",
    sqlite_path: str = "data/supply_chain.sqlite",
    backend_name: str = "mock",
    max_batch_size: int = 4,
    max_events_per_tick: int = 32,
    agent_replicas: int = 1,
    scenario_parameters: dict[str, Any] | None = None,
    backend_options: dict[str, Any] | None = None,
) -> SimulationEngine:
    scenario_parameters = scenario_parameters or {}
    profiles = _supply_chain_profiles(agent_replicas)
    environment = _supply_chain_environment(profiles, scenario_parameters)
    store = create_store(
        storage_mode=storage_mode,
        sqlite_path=sqlite_path,
        environment=environment.initialize(),
        profiles=profiles,
    )
    backend = create_execution_backend(
        backend_name,
        scenario="supply_chain",
        backend_options=backend_options,
    )
    from agentic_sim.engine.simulation_engine import SimulationEngine

    return SimulationEngine(
        store=store,
        scheduler=FIFOScheduler(),
        backend=backend,
        environment=environment,
        batch_builder=BatchBuilder(max_batch_size=max_batch_size),
        max_events_per_tick=max_events_per_tick,
    )


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


def _supply_chain_environment(
    profiles: list[AgentProfile], scenario_parameters: dict[str, Any]
) -> SupplyChainEnvironment:
    operator_ids = [str(profile.agent_id) for profile in profiles if profile.role != "coordinator"]
    return SupplyChainEnvironment(
        regions=string_list(scenario_parameters.get("regions")) or None,
        demand_step=int(scenario_parameters.get("demand_step", 10)),
        delay_step=int(scenario_parameters.get("delay_step", 4)),
        operator_ids=operator_ids,
    )
