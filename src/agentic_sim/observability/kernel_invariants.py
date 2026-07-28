from __future__ import annotations

from typing import Any

from agentic_sim.observability.causal_verifier import build_message_edges


def graph_metrics(traces: list[Any]) -> dict[str, int]:
    """Structural metrics over the message-mediated causal graph reconstructed
    from agent_step traces. A separate reader from causal_verifier.verify() --
    it doesn't check correctness, only describes shape (node/edge counts,
    depth, components, in-degree), for comparing a synthetic kernel run
    against its shape's hand-derived expected invariants.
    """
    steps = [
        trace.payload
        for trace in traces
        if trace.event_name == "agent_step" and "activation_id" in trace.payload
    ]
    edges = build_message_edges(steps)

    node_count = len(edges)
    edge_count = sum(len(parents) for parents in edges.values())
    max_in_degree = max((len(parents) for parents in edges.values()), default=0)

    depth_cache: dict[str, int] = {}

    def depth(node: str) -> int:
        if node in depth_cache:
            return depth_cache[node]
        parents = edges.get(node, [])
        result = 0 if not parents else 1 + max(depth(parent) for parent in parents)
        depth_cache[node] = result
        return result

    max_depth = max((depth(node) for node in edges), default=0)

    parent_of: dict[str, str] = {node: node for node in edges}

    def find(node: str) -> str:
        root = node
        while parent_of[root] != root:
            root = parent_of[root]
        while parent_of[node] != root:
            parent_of[node], node = root, parent_of[node]
        return root

    def union(a: str, b: str) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent_of[root_a] = root_b

    for node, parents in edges.items():
        for parent in parents:
            union(node, parent)

    component_count = len({find(node) for node in edges})

    return {
        "node_count": node_count,
        "edge_count": edge_count,
        "max_depth": max_depth,
        "component_count": component_count,
        "max_in_degree": max_in_degree,
    }
