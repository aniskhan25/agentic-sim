from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Protocol

from agentic_sim.execution.async_backend import AsyncExecutionBackend
from agentic_sim.execution.batcher import BatchBuilder
from agentic_sim.models import DispatchOutcome, ExecutionRequest


class DispatchPolicy(Protocol):
    """Decides the order/concurrency in which an already-scheduled tick's
    requests are dispatched via AsyncExecutionBackend.submit()/poll() -- the
    Phase 5 "baseline policies" (research_roadmap.md item 12). Operates on
    requests already produced by the unmodified FIFOScheduler (still one
    activation per agent per tick); it does not decide WHICH agents get
    activated, only HOW their already-planned requests get dispatched.
    """

    name: str

    def dispatch(
        self, requests: list[ExecutionRequest], backend: AsyncExecutionBackend
    ) -> list[tuple[ExecutionRequest, DispatchOutcome]]: ...


class SequentialDispatchPolicy:
    """Reference baseline: one request at a time, in submission order.
    Mechanically identical to calling backend.run_batch([request]) in a
    loop -- every existing backend's _run_one has no cross-request state,
    so this reproduces the pre-item-12 deterministic behavior exactly.
    """

    name = "sequential"

    def dispatch(self, requests, backend):
        results = []
        for request in requests:
            ticket = backend.submit(request)
            results.append((request, backend.poll(ticket)))
        return results


class NaiveConcurrentDispatchPolicy:
    """Dispatches all ready work concurrently with no causal-conflict
    protection at all (evaluation_plan.md: "dispatch ready work without
    causal conflict protection"). A real ThreadPoolExecutor, not simulated
    -- completion order genuinely depends on OS thread scheduling via
    as_completed(). The negative control: H2 expects this policy can
    produce stale reads, conflicting environment actions, or observation
    divergence for workloads with real state dependencies.
    """

    name = "naive_concurrent"

    def __init__(self, max_workers: int = 8):
        self.max_workers = max_workers

    def dispatch(self, requests, backend):
        if not requests:
            return []
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(requests))) as executor:
            futures = [executor.submit(self._run_one, request, backend) for request in requests]
            return [future.result() for future in as_completed(futures)]

    def _run_one(self, request, backend):
        ticket = backend.submit(request)
        return request, backend.poll(ticket)


class BarrierDispatchPolicy:
    """Batches only at explicit synchronization boundaries: reuses
    BatchBuilder's existing backend_hint grouping as that boundary.
    Dispatches each group fully concurrently (same mechanism as naive),
    but waits for one group to completely finish before starting the next
    -- the real distinction from naive-concurrent, which has no boundaries
    at all.
    """

    name = "barrier"

    def __init__(self, batch_builder: BatchBuilder | None = None, max_workers: int = 8):
        self.batch_builder = batch_builder or BatchBuilder()
        self.max_workers = max_workers

    def dispatch(self, requests, backend):
        concurrent_policy = NaiveConcurrentDispatchPolicy(max_workers=self.max_workers)
        results = []
        for group in self.batch_builder.group(requests):
            results.extend(concurrent_policy.dispatch(group, backend))
        return results


class CausalOnlyDispatchPolicy:
    """Causal readiness with no provider-capability/queue/prefix
    optimization (evaluation_plan.md's generic dependency-aware baseline).
    Scoped to MESSAGE-mediated causal ordering only, matching
    causal_verifier.py's existing, explicitly-recorded scope -- it does
    NOT protect against environment-level conflicts (e.g. the synthetic
    kernel's conflicting_write shape, whose writers exchange no messages
    at all); that is the same already-documented gap from items 8-10, not
    reinvented here.

    Within a causally-independent wave, activations dispatch concurrently
    (same mechanism as naive); waves themselves run strictly in order,
    since a later wave may depend on an earlier wave's results. Because
    message-mediated causal chains always span at least one tick boundary
    in this engine's model (a message sent this tick can only be read
    starting next tick), a single dispatch() call today always produces
    exactly one wave -- identical to naive-concurrent's single free-for-all
    for every existing scenario. The wave-building logic is nonetheless
    correct and independently verified by direct construction of an
    artificial in-batch dependency; it becomes load-bearing only if a
    future scheduler ever produces causally-chained activations within one
    tick.
    """

    name = "causal_only"

    def __init__(self, max_workers: int = 8):
        self.max_workers = max_workers

    def dispatch(self, requests, backend):
        concurrent_policy = NaiveConcurrentDispatchPolicy(max_workers=self.max_workers)
        results = []
        for wave in self._build_waves(requests):
            results.extend(concurrent_policy.dispatch(wave, backend))
        return results

    def _build_waves(self, requests: list[ExecutionRequest]) -> list[list[ExecutionRequest]]:
        activation_ids = {request.activation.activation_id for request in requests}
        parents_by_id: dict[str, set[str]] = {}
        for request in requests:
            parents = {
                message.origin_activation_id
                for message in request.inbox_messages
                if message.origin_activation_id
            }
            if request.triggering_event.causal_parent_activation_id:
                parents.add(request.triggering_event.causal_parent_activation_id)
            # Only in-batch parents impose an ordering constraint -- a parent
            # from a prior tick has already committed and imposes no wait here.
            parents_by_id[request.activation.activation_id] = parents & activation_ids

        remaining = {request.activation.activation_id: request for request in requests}
        resolved: set[str] = set()
        waves: list[list[ExecutionRequest]] = []
        while remaining:
            ready_ids = [
                activation_id
                for activation_id in remaining
                if parents_by_id[activation_id] <= resolved
            ]
            if not ready_ids:
                # Cycle guard: dispatch what's left rather than hang. Should be
                # unreachable (causal_verifier's cycle check guards this at
                # commit time), but fail safe rather than infinite-loop.
                ready_ids = list(remaining.keys())
            wave = [remaining.pop(activation_id) for activation_id in ready_ids]
            waves.append(wave)
            resolved.update(ready_ids)
        return waves
