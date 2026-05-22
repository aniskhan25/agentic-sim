from __future__ import annotations

from typing import Any

from agentic_sim.models import AgentProfile, AgentState, EnvironmentState
from agentic_sim.state import InMemoryStateStore, SQLiteStateStore
from agentic_sim.state.base import RuntimeStore


def create_store(
    *,
    storage_mode: str,
    sqlite_path: str,
    environment: EnvironmentState,
    profiles: list[AgentProfile],
) -> RuntimeStore:
    if storage_mode == "sqlite":
        store: RuntimeStore = SQLiteStateStore(sqlite_path, environment=environment)
    else:
        store = InMemoryStateStore(environment)

    for profile in profiles:
        store.agents.put_profile(profile)
        store.agents.put_state(AgentState(agent_id=profile.agent_id))
    return store


def string_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]
