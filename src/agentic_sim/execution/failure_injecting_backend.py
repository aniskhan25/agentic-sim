from __future__ import annotations

from agentic_sim.execution.base import ExecutionBackend
from agentic_sim.models import ExecutionRequest, ExecutionResult

_MODES = {"none", "timeout", "malformed", "interruption"}


class FailureInjectingBackend:
    """Wraps another ExecutionBackend and deterministically injects failures
    -- no RNG anywhere, matching this codebase's "seeded means deterministic"
    convention throughout. Models evaluation_plan.md's "failure workloads"
    dimension (invalid outputs, timeouts, provider interruption). Duplicate
    response injection is deliberately not reimplemented here -- item 10's
    tests/test_commit_conformance.py already directly tests duplicate
    activation_id handling at the commit layer.

    Failure workloads are only meaningfully demonstrable through the
    dispatch-policy path (SimulationEngine.dispatch_policy set to one of
    the seven DispatchPolicy implementations): SynchronousProviderAdapter's
    submit() catches exceptions and converts them into a structured
    DispatchOutcome(status=FAILED, ...) instead of crashing, exactly like
    it would for a real failing backend. Using this backend directly as
    SimulationEngine.backend with dispatch_policy=None has no such
    protection -- a raised exception propagates and crashes the run, which
    is the existing, correct behavior for any backend, not a new gap.
    """

    def __init__(
        self,
        backend: ExecutionBackend,
        *,
        cycle: list[str] | None = None,
        failure_plan: dict[str, str] | None = None,
    ):
        for mode in (cycle or []) :
            if mode not in _MODES:
                raise ValueError(f"unsupported failure mode {mode!r}")
        for mode in (failure_plan or {}).values():
            if mode not in _MODES:
                raise ValueError(f"unsupported failure mode {mode!r}")

        self.backend = backend
        self.name = backend.name
        self.capabilities = backend.capabilities
        self.cycle = cycle or []
        self.failure_plan = failure_plan or {}
        self._call_count = 0

    def run_batch(self, requests: list[ExecutionRequest]) -> list[ExecutionResult]:
        results = []
        for request in requests:
            mode = self._mode_for(request)
            if mode is None or mode == "none":
                results.extend(self.backend.run_batch([request]))
                continue
            results.append(self._inject(request, mode))
        return results

    def _mode_for(self, request: ExecutionRequest) -> str | None:
        agent_id = str(request.agent_profile.agent_id)
        if agent_id in self.failure_plan:
            return self.failure_plan[agent_id]
        if self.cycle:
            mode = self.cycle[self._call_count % len(self.cycle)]
            self._call_count += 1
            return mode
        return None

    def _inject(self, request: ExecutionRequest, mode: str) -> ExecutionResult:
        if mode == "timeout":
            raise TimeoutError(f"simulated timeout for {request.agent_profile.agent_id}")
        if mode == "interruption":
            raise RuntimeError(f"simulated provider interruption for {request.agent_profile.agent_id}")
        if mode == "malformed":
            state = request.agent_state.with_activation_count()
            return ExecutionResult(
                agent_id=request.agent_profile.agent_id,
                updated_state=state,
                metadata={"model_output_invalid": True},
            )
        raise ValueError(f"unsupported failure mode {mode!r}")
