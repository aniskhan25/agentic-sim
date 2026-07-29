from __future__ import annotations

import time

from agentic_sim.execution.capabilities import ProviderCapabilities
from agentic_sim.models import ExecutionRequest, ExecutionResult


class LatencySimulatingBackend:
    """Deterministic backend that sleeps a configured per-agent delay before
    returning a trivial result -- used to make dispatch-policy throughput
    differences observable (item 14's scheduler contribution decision
    gate). Nothing else in this codebase simulates per-request latency
    outside test-only fixtures, and production benchmarking code shouldn't
    import from tests/, so this is a real, standalone backend implementation
    at the same standing as MockExecutionBackend/SyntheticExecutionBackend.
    """

    name = "latency_simulating"

    def __init__(
        self,
        capabilities: ProviderCapabilities,
        delays: dict[str, float] | None = None,
        default_delay: float = 0.0,
    ):
        self.capabilities = capabilities
        self.delays = delays or {}
        self.default_delay = default_delay

    def run_batch(self, requests: list[ExecutionRequest]) -> list[ExecutionResult]:
        results = []
        for request in requests:
            agent_id = str(request.agent_profile.agent_id)
            delay = self.delays.get(agent_id, self.default_delay)
            if delay:
                time.sleep(delay)
            results.append(
                ExecutionResult(agent_id=request.agent_profile.agent_id, updated_state=request.agent_state)
            )
        return results
