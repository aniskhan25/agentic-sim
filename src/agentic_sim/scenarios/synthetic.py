from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agentic_sim.environment import SyntheticEnvironment
from agentic_sim.execution import BatchBuilder, ContextBuilder
from agentic_sim.execution.synthetic_backend import SyntheticExecutionBackend
from agentic_sim.models import AgentId, AgentProfile
from agentic_sim.scenarios.common import create_store
from agentic_sim.scheduling import FIFOScheduler
from agentic_sim.state.base import RuntimeStore

if TYPE_CHECKING:
    from agentic_sim.engine.simulation_engine import SimulationEngine

_SUPPORTED_BACKENDS = {"mock", "rule"}


def create_synthetic_engine(
    *,
    storage_mode: str = "memory",
    sqlite_path: str = "data/synthetic.sqlite",
    backend_name: str = "mock",
    max_batch_size: int = 4,
    max_events_per_tick: int = 32,
    agent_replicas: int = 1,
    scenario_parameters: dict[str, Any] | None = None,
    backend_options: dict[str, Any] | None = None,
) -> SimulationEngine:
    if backend_name not in _SUPPORTED_BACKENDS:
        supported = ", ".join(sorted(_SUPPORTED_BACKENDS))
        raise ValueError(
            f"unsupported backend_name {backend_name!r} for the synthetic kernel; "
            f"supported backend names: {supported} (it is deterministic-only by design)"
        )

    scenario_parameters = scenario_parameters or {}
    shape = scenario_parameters.get("shape", "chain")
    roster, hop_plan, conflict_writes, root_agent_ids = _build_topology(shape, scenario_parameters)

    profiles = [
        AgentProfile(
            agent_id=AgentId(agent_id),
            role="synthetic_node",
            name=agent_id,
            region="synthetic",
            capabilities=[],
            authority_level=1,
        )
        for agent_id in roster
    ]
    environment = SyntheticEnvironment(root_agent_ids=root_agent_ids)
    store: RuntimeStore = create_store(
        storage_mode=storage_mode,
        sqlite_path=sqlite_path,
        environment=environment.initialize(),
        profiles=profiles,
    )
    backend = SyntheticExecutionBackend(hop_plan=hop_plan, conflict_writes=conflict_writes)
    inbox_limit = max(len(roster), 5)

    from agentic_sim.engine.simulation_engine import SimulationEngine

    return SimulationEngine(
        store=store,
        scheduler=FIFOScheduler(),
        backend=backend,
        environment=environment,
        context_builder=ContextBuilder(inbox_limit=inbox_limit),
        batch_builder=BatchBuilder(max_batch_size=max_batch_size),
        max_events_per_tick=max_events_per_tick,
    )


def _build_topology(
    shape: str, params: dict[str, Any]
) -> tuple[list[str], dict[str, list[str]], dict[str, dict], list[str]]:
    if shape == "chain":
        length = int(params.get("length", 3))
        if length < 1:
            raise ValueError("chain length must be at least 1")
        roster = [f"node_{i}" for i in range(length)]
        hop_plan = {roster[i]: [roster[i + 1]] for i in range(length - 1)}
        return roster, hop_plan, {}, [roster[0]]

    if shape == "fan_out":
        width = int(params.get("width", 3))
        if width < 1:
            raise ValueError("fan_out width must be at least 1")
        root = "root"
        leaves = [f"leaf_{i}" for i in range(width)]
        roster = [root, *leaves]
        hop_plan = {root: leaves}
        return roster, hop_plan, {}, [root]

    if shape == "fork_join":
        width = int(params.get("width", 3))
        if width < 1:
            raise ValueError("fork_join width must be at least 1")
        root = "root"
        branches = [f"branch_{i}" for i in range(width)]
        sink = "sink"
        roster = [root, *branches, sink]
        hop_plan = {root: list(branches)}
        for branch in branches:
            hop_plan[branch] = [sink]
        return roster, hop_plan, {}, [root]

    if shape == "independent_branches":
        branch_count = int(params.get("branch_count", 3))
        length = int(params.get("length", 3))
        if branch_count < 1 or length < 1:
            raise ValueError("branch_count and length must each be at least 1")
        roster: list[str] = []
        hop_plan: dict[str, list[str]] = {}
        root_agent_ids: list[str] = []
        for branch in range(branch_count):
            nodes = [f"branch{branch}_node{i}" for i in range(length)]
            roster.extend(nodes)
            for i in range(length - 1):
                hop_plan[nodes[i]] = [nodes[i + 1]]
            root_agent_ids.append(nodes[0])
        return roster, hop_plan, {}, root_agent_ids

    if shape == "mixed_dag":
        length = int(params.get("length", 3))
        if length < 1:
            raise ValueError("mixed_dag length must be at least 1")
        left = [f"left_{i}" for i in range(length)]
        right = [f"right_{i}" for i in range(length)]
        join = "join"
        roster = [*left, *right, join]
        hop_plan: dict[str, list[str]] = {}
        for i in range(length - 1):
            hop_plan[left[i]] = [left[i + 1]]
            hop_plan[right[i]] = [right[i + 1]]
        hop_plan[left[-1]] = [join]
        hop_plan[right[-1]] = [join]
        return roster, hop_plan, {}, [left[0], right[0]]

    if shape == "conflicting_write":
        writers = int(params.get("writers", 3))
        if writers < 1:
            raise ValueError("conflicting_write writers must be at least 1")
        roster = [f"writer_{i}" for i in range(writers)]
        conflict_writes = {
            agent_id: {"key": "x", "value": index} for index, agent_id in enumerate(roster)
        }
        return roster, {}, conflict_writes, list(roster)

    raise ValueError(f"unsupported synthetic shape {shape!r}")


def expected_invariants(shape: str, params: dict[str, Any]) -> dict[str, int]:
    if shape == "chain":
        length = int(params.get("length", 3))
        return {
            "node_count": length,
            "edge_count": length - 1,
            "max_depth": length - 1,
            "component_count": 1,
            "max_in_degree": 1 if length > 1 else 0,
        }

    if shape == "fan_out":
        width = int(params.get("width", 3))
        return {
            "node_count": width + 1,
            "edge_count": width,
            "max_depth": 1,
            "component_count": 1,
            "max_in_degree": 1,
        }

    if shape == "fork_join":
        width = int(params.get("width", 3))
        return {
            "node_count": width + 2,
            "edge_count": 2 * width,
            "max_depth": 2,
            "component_count": 1,
            "max_in_degree": width,
        }

    if shape == "independent_branches":
        branch_count = int(params.get("branch_count", 3))
        length = int(params.get("length", 3))
        return {
            "node_count": branch_count * length,
            "edge_count": branch_count * (length - 1),
            "max_depth": length - 1,
            "component_count": branch_count,
            "max_in_degree": 1 if length > 1 else 0,
        }

    if shape == "mixed_dag":
        length = int(params.get("length", 3))
        return {
            "node_count": 2 * length + 1,
            "edge_count": 2 * length,
            "max_depth": length,
            "component_count": 1,
            "max_in_degree": 2,
        }

    if shape == "conflicting_write":
        writers = int(params.get("writers", 3))
        return {
            "node_count": writers,
            "edge_count": 0,
            "max_depth": 0,
            "component_count": writers,
            "max_in_degree": 0,
        }

    raise ValueError(f"unsupported synthetic shape {shape!r}")


def step_count_for(shape: str, params: dict[str, Any]) -> int:
    if shape == "chain":
        return int(params.get("length", 3))
    if shape == "fan_out":
        return 2
    if shape == "fork_join":
        return 3
    if shape == "independent_branches":
        return int(params.get("length", 3))
    if shape == "mixed_dag":
        return int(params.get("length", 3)) + 1
    if shape == "conflicting_write":
        return 1
    raise ValueError(f"unsupported synthetic shape {shape!r}")
