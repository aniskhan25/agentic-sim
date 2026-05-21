from __future__ import annotations

from multiagent_demo.engine.simulation_engine import SimulationEngine
from multiagent_demo.environment import StormEnvironment
from multiagent_demo.execution import BatchBuilder, MockExecutionBackend, RuleExecutionBackend
from multiagent_demo.models import AgentId, AgentProfile, AgentState
from multiagent_demo.scheduling import FIFOScheduler
from multiagent_demo.state import InMemoryStateStore, SQLiteStateStore
from multiagent_demo.state.base import RuntimeStore


def create_storm_store(
    storage_mode: str = "memory",
    sqlite_path: str = "data/storm.sqlite",
    agent_replicas: int = 1,
) -> RuntimeStore:
    profiles = _storm_profiles(agent_replicas)
    operator_ids = [
        str(profile.agent_id) for profile in profiles if profile.role in {"hospital", "utility"}
    ]
    environment = StormEnvironment(operator_ids=operator_ids)
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
    max_activations_per_tick: int = 8,
    max_batch_size: int = 4,
    max_events_per_tick: int = 32,
    agent_replicas: int = 1,
) -> SimulationEngine:
    profiles = _storm_profiles(agent_replicas)
    operator_ids = [
        str(profile.agent_id) for profile in profiles if profile.role in {"hospital", "utility"}
    ]
    environment = StormEnvironment(operator_ids=operator_ids)
    store = create_storm_store(
        storage_mode=storage_mode,
        sqlite_path=sqlite_path,
        agent_replicas=agent_replicas,
    )
    backend = RuleExecutionBackend() if backend_name == "rule" else MockExecutionBackend()
    return SimulationEngine(
        store=store,
        scheduler=FIFOScheduler(max_activations_per_tick=max_activations_per_tick),
        backend=backend,
        environment=environment,
        batch_builder=BatchBuilder(max_batch_size=max_batch_size),
        max_events_per_tick=max_events_per_tick,
    )
