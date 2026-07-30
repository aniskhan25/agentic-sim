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
        for wave in build_causal_waves(requests):
            results.extend(concurrent_policy.dispatch(wave, backend))
        return results

    def _build_waves(self, requests: list[ExecutionRequest]) -> list[list[ExecutionRequest]]:
        return build_causal_waves(requests)


def build_causal_waves(requests: list[ExecutionRequest]) -> list[list[ExecutionRequest]]:
    """Partitions requests into message-causally-independent waves: wave 0
    has no in-batch parents, wave 1's parents are all in wave 0, etc.
    Requests within a wave are causally safe to dispatch concurrently;
    waves themselves must run in order. Only in-batch parents (via
    Message.origin_activation_id / Event.causal_parent_activation_id)
    impose an ordering constraint -- a parent from a prior tick has already
    committed and imposes no wait here. Shared by CausalOnlyDispatchPolicy
    and the capability/queue-aware/full policies built on top of it.
    """
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
        parents_by_id[request.activation.activation_id] = parents & activation_ids

    remaining = {request.activation.activation_id: request for request in requests}
    resolved: set[str] = set()
    waves: list[list[ExecutionRequest]] = []
    while remaining:
        ready_ids = [
            activation_id for activation_id in remaining if parents_by_id[activation_id] <= resolved
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


class CapabilityAwareDispatchPolicy:
    """Rung 5: causal-only (rung 4) plus capability-constrained placement.
    Rungs 1-4 all dispatch via ThreadPoolExecutor regardless of whether the
    backend declares itself safe for concurrent access -- a real,
    previously-unaddressed gap. This rung closes it: within each causal
    wave, requests are grouped by backend_hint (BatchBuilder, same
    mechanism BarrierDispatchPolicy uses), and each group dispatches
    concurrently only if backend.capabilities.supports_concurrency is
    True, otherwise sequentially.

    "Capability-constrained batching" in the server-side merged-batch
    sense is explicitly deferred: no backend in this codebase declares
    supports_server_batching=True today, so building logic to exploit it
    would be untestable dead code.
    """

    name = "capability_aware"

    def __init__(self, batch_builder: BatchBuilder | None = None, max_workers: int = 8):
        self.batch_builder = batch_builder or BatchBuilder()
        self.max_workers = max_workers

    def dispatch(self, requests, backend):
        results = []
        for wave in build_causal_waves(requests):
            for group in self.batch_builder.group(wave):
                results.extend(self._dispatch_group(group, backend))
        return results

    def _dispatch_group(self, group, backend):
        if not backend.capabilities.supports_concurrency:
            return SequentialDispatchPolicy().dispatch(group, backend)
        return NaiveConcurrentDispatchPolicy(max_workers=self.max_workers).dispatch(group, backend)


class QueueAwareDispatchPolicy(CapabilityAwareDispatchPolicy):
    """Rung 6: capability-aware (rung 5) plus provider-queue awareness and
    bounded backpressure. Each backend_hint group's concurrency is capped
    at a configurable max-in-flight limit (default_max_in_flight, or a
    per-backend_hint override via max_in_flight) instead of the uncapped
    default -- ready work beyond the cap queues inside the executor rather
    than all firing at once. This is real, bounded provider-queue
    awareness: treating each backend_hint as a provider with a finite
    concurrent-request budget, something rungs 1-5 do not do (they always
    dispatch an entire ready group concurrently, uncapped).

    default_max_in_flight=4 is an evidence-based default, not an arbitrary
    illustrative one: a real 7-rung pilot against live self-hosted vLLM
    servers on both LUMI and Roihu (docs/research_roadmap.md item 19) found
    the original default of 2 caused a statistically real throughput
    regression relative to capability_aware (rung 5) on both systems. A
    follow-up sweep over {2, 4, 8} (docs/baseline/b1_retune_sweep_{lumi,roihu}
    _result.json) found 4 is the smallest value whose useful-agent-steps/sec
    mean+-1-stdev band overlaps capability_aware's on both systems (2 does
    not; 4 and 8 both do) -- per docs/hpc_data_collection_procedures.md's
    tie-breaking rule, the smaller of two statistically-indistinguishable
    options wins. Note this only retunes queue_aware itself: FullDispatchPolicy
    (which inherits this default) did NOT improve with a larger cap in the
    same sweep -- its bottleneck is its own sequential role-group-by-role-group
    dispatch, a separate mechanism this value does not address.
    """

    name = "queue_aware"

    def __init__(
        self,
        batch_builder: BatchBuilder | None = None,
        default_max_in_flight: int = 4,
        max_in_flight: dict[str, int] | None = None,
    ):
        self.batch_builder = batch_builder or BatchBuilder()
        self.default_max_in_flight = default_max_in_flight
        self.max_in_flight = max_in_flight or {}

    def _dispatch_group(self, group, backend):
        if not backend.capabilities.supports_concurrency:
            return SequentialDispatchPolicy().dispatch(group, backend)
        hint = group[0].backend_hint
        limit = self.max_in_flight.get(hint, self.default_max_in_flight)
        return NaiveConcurrentDispatchPolicy(max_workers=max(1, limit)).dispatch(group, backend)


class FullDispatchPolicy(QueueAwareDispatchPolicy):
    """Rung 7: queue-aware (rung 6) plus reusable-prefix grouping. No
    backend in this codebase declares supports_prefix_caching today, so
    there is no real prompt-level prefix-cache signal to exploit; this
    approximates Phase 6's own "prefix or role similarity" wording via
    AgentProfile.role -- requests sharing a role share the same
    role_policy-driven prompt template and are the most likely to share a
    reusable prefix in practice. Same-role requests are reordered to be
    adjacent in dispatch order, so a real prefix-caching-capable backend
    would see them submitted next to each other. Real token/prompt-level
    prefix similarity is deferred as premature -- no backend could exploit
    it yet.

    Dispatching each role group through its own blocking concurrent call
    (one ThreadPoolExecutor per role, waiting for it to fully drain before
    starting the next) was tried first and found, via a real 7-rung B1
    pilot against live self-hosted vLLM servers on both LUMI and Roihu
    (docs/research_roadmap.md item 19), to serialize execution across
    roles -- pathological whenever a role has few concurrent requests per
    wave (e.g. one agent per role), collapsing this policy to near-
    sequential throughput. Fixed by reordering role-adjacent but
    dispatching the whole group as a single concurrent batch (inherited
    from QueueAwareDispatchPolicy's dispatch()), preserving the ordering
    property the docstring actually needs without the accidental blocking.
    """

    name = "full"

    def _dispatch_group(self, group, backend):
        if not backend.capabilities.supports_concurrency:
            return SequentialDispatchPolicy().dispatch(group, backend)
        hint = group[0].backend_hint
        limit = self.max_in_flight.get(hint, self.default_max_in_flight)
        role_ordered = [request for role_group in self._group_by_role(group) for request in role_group]
        return NaiveConcurrentDispatchPolicy(max_workers=max(1, limit)).dispatch(role_ordered, backend)

    def _group_by_role(self, requests: list[ExecutionRequest]) -> list[list[ExecutionRequest]]:
        grouped: dict[str, list[ExecutionRequest]] = {}
        for request in requests:
            grouped.setdefault(request.agent_profile.role, []).append(request)
        return list(grouped.values())
