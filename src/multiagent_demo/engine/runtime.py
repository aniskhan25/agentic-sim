from __future__ import annotations

from multiagent_demo.engine.simulation_engine import SimulationEngine
from multiagent_demo.environment import StormEnvironment
from multiagent_demo.execution import BatchBuilder, MockExecutionBackend, RuleExecutionBackend
from multiagent_demo.models import AgentId, AgentProfile, AgentState
from multiagent_demo.scheduling import FIFOScheduler
from multiagent_demo.state import InMemoryStateStore, SQLiteStateStore
from multiagent_demo.state.base import RuntimeStore


def create_storm_store(storage_mode: str = "memory", sqlite_path: str = "data/storm.sqlite") -> RuntimeStore:
    environment = StormEnvironment()
    initial_state = environment.initialize()
    if storage_mode == "sqlite":
        store: RuntimeStore = SQLiteStateStore(sqlite_path, environment=initial_state)
    else:
        store = InMemoryStateStore(initial_state)

    profiles = [
        AgentProfile(
            agent_id=AgentId("agent_coordinator"),
            role="coordinator",
            name="Regional Coordinator",
            region="national",
            capabilities=["triage", "dispatch"],
            authority_level=3,
        ),
        AgentProfile(
            agent_id=AgentId("agent_hospital"),
            role="hospital",
            name="Hospital Operations",
            region="helsinki",
            capabilities=["capacity_report"],
            authority_level=2,
        ),
        AgentProfile(
            agent_id=AgentId("agent_utility"),
            role="utility",
            name="Utility Operations",
            region="oulu",
            capabilities=["grid_report"],
            authority_level=2,
        ),
        AgentProfile(
            agent_id=AgentId("agent_forecaster"),
            role="forecaster",
            name="Weather Forecaster",
            region="national",
            capabilities=["forecast"],
            authority_level=1,
        ),
    ]
    for profile in profiles:
        store.agents.put_profile(profile)
        store.agents.put_state(AgentState(agent_id=profile.agent_id))
    return store


def create_storm_engine(
    *,
    storage_mode: str = "memory",
    sqlite_path: str = "data/storm.sqlite",
    backend_name: str = "mock",
    max_activations_per_tick: int = 8,
    max_batch_size: int = 4,
) -> SimulationEngine:
    environment = StormEnvironment()
    store = create_storm_store(storage_mode=storage_mode, sqlite_path=sqlite_path)
    backend = RuleExecutionBackend() if backend_name == "rule" else MockExecutionBackend()
    return SimulationEngine(
        store=store,
        scheduler=FIFOScheduler(max_activations_per_tick=max_activations_per_tick),
        backend=backend,
        environment=environment,
        batch_builder=BatchBuilder(max_batch_size=max_batch_size),
    )
