import threading
import time
import unittest

from agentic_sim.execution import SynchronousProviderAdapter
from agentic_sim.execution.capabilities import ProviderCapabilities
from agentic_sim.models import (
    Activation,
    AgentId,
    AgentProfile,
    AgentState,
    DispatchStatus,
    EnvironmentState,
    Event,
    EventType,
    ExecutionRequest,
    ExecutionResult,
    Message,
    MessageType,
)
from agentic_sim.scheduling import (
    BarrierDispatchPolicy,
    CapabilityAwareDispatchPolicy,
    CausalOnlyDispatchPolicy,
    FullDispatchPolicy,
    NaiveConcurrentDispatchPolicy,
    QueueAwareDispatchPolicy,
    SequentialDispatchPolicy,
)
from agentic_sim.utils.time import utc_now

_CAPABILITIES = ProviderCapabilities(
    supports_concurrency=False,
    supports_server_batching=False,
    supports_structured_output=False,
    supports_prefix_caching=False,
    max_context_tokens=0,
    observable_token_usage=False,
    observable_energy=False,
)


def _capabilities(supports_concurrency: bool) -> ProviderCapabilities:
    return ProviderCapabilities(
        supports_concurrency=supports_concurrency,
        supports_server_batching=False,
        supports_structured_output=False,
        supports_prefix_caching=False,
        max_context_tokens=0,
        observable_token_usage=False,
        observable_energy=False,
    )


class _RecordingBackend:
    """Stub ExecutionBackend that records thread identity, call order, and
    call start/end intervals per request -- used to prove real concurrency
    and real ordering behavior deterministically (via engineered delays),
    not by relying on flaky real-timing luck.
    """

    name = "stub"

    def __init__(self, delays: dict[str, float] | None = None, capabilities: ProviderCapabilities = _CAPABILITIES):
        self.delays = delays or {}
        self.capabilities = capabilities
        self.thread_idents: list[int] = []
        self.call_order: list[str] = []
        self.call_intervals: list[tuple[str, float, float]] = []
        self._lock = threading.Lock()

    def run_batch(self, requests):
        request = requests[0]
        agent_id = str(request.agent_profile.agent_id)
        start = time.perf_counter()
        delay = self.delays.get(agent_id, 0)
        if delay:
            time.sleep(delay)
        end = time.perf_counter()
        with self._lock:
            self.thread_idents.append(threading.current_thread().ident)
            self.call_order.append(agent_id)
            self.call_intervals.append((agent_id, start, end))
        return [ExecutionResult(agent_id=request.agent_profile.agent_id, updated_state=request.agent_state)]


class _PeakConcurrencyBackend:
    """Stub ExecutionBackend that tracks the PEAK number of simultaneously
    in-flight run_batch calls -- used to prove a bounded backpressure cap
    is actually respected, not just that "more than one thread" was used.
    """

    name = "peak_stub"
    capabilities = _capabilities(supports_concurrency=True)

    def __init__(self, delay: float = 0.02):
        self.delay = delay
        self.active = 0
        self.peak_active = 0
        self._lock = threading.Lock()

    def run_batch(self, requests):
        with self._lock:
            self.active += 1
            self.peak_active = max(self.peak_active, self.active)
        time.sleep(self.delay)
        with self._lock:
            self.active -= 1
        request = requests[0]
        return [ExecutionResult(agent_id=request.agent_profile.agent_id, updated_state=request.agent_state)]


def _request(
    agent_id: str,
    *,
    backend_hint: str = "mock",
    role: str = "node",
    inbox_messages: list[Message] | None = None,
    causal_parent_activation_id: str | None = None,
) -> ExecutionRequest:
    now = utc_now()
    event = Event.create(
        EventType.SYNTHETIC_TRIGGER,
        source="test",
        priority=1,
        causal_parent_activation_id=causal_parent_activation_id,
    )
    return ExecutionRequest(
        activation=Activation.create(
            agent_id=AgentId(agent_id),
            trigger_event_id=event.event_id,
            activation_reason=event.event_type.value,
            priority=event.priority,
            ready_at=now,
        ),
        agent_profile=AgentProfile(
            agent_id=AgentId(agent_id), role=role, name=agent_id, region="test", backend=backend_hint
        ),
        agent_state=AgentState(agent_id=AgentId(agent_id)),
        inbox_messages=inbox_messages or [],
        triggering_event=event,
        environment=EnvironmentState(scenario="test", tick=0, updated_at=now, variables={}),
        backend_hint=backend_hint,
    )


class DispatchPolicyPairingTests(unittest.TestCase):
    def test_every_policy_pairs_each_request_with_exactly_one_completed_outcome(self):
        requests = [_request("agent_a"), _request("agent_b"), _request("agent_c")]
        for policy in [
            SequentialDispatchPolicy(),
            NaiveConcurrentDispatchPolicy(),
            BarrierDispatchPolicy(),
            CausalOnlyDispatchPolicy(),
            CapabilityAwareDispatchPolicy(),
            QueueAwareDispatchPolicy(),
            FullDispatchPolicy(),
        ]:
            with self.subTest(policy=policy.name):
                adapter = SynchronousProviderAdapter(_RecordingBackend())
                outcomes = policy.dispatch(requests, adapter)

                self.assertEqual(len(outcomes), 3)
                seen_agents = set()
                for request, outcome in outcomes:
                    self.assertEqual(outcome.status, DispatchStatus.COMPLETED)
                    self.assertEqual(outcome.result.agent_id, request.agent_profile.agent_id)
                    seen_agents.add(str(request.agent_profile.agent_id))
                self.assertEqual(seen_agents, {"agent_a", "agent_b", "agent_c"})


class DispatchPolicyConcurrencyTests(unittest.TestCase):
    def test_sequential_uses_only_the_calling_thread(self):
        backend = _RecordingBackend()
        adapter = SynchronousProviderAdapter(backend)
        requests = [_request("agent_a"), _request("agent_b"), _request("agent_c")]

        SequentialDispatchPolicy().dispatch(requests, adapter)

        self.assertEqual(set(backend.thread_idents), {threading.current_thread().ident})

    def test_naive_concurrent_uses_more_than_one_thread(self):
        # A small shared delay keeps all three tasks genuinely in flight at
        # once -- without it, near-instant tasks can complete fast enough
        # for the pool to reuse a single worker thread, making this flaky.
        backend = _RecordingBackend(delays={"agent_a": 0.02, "agent_b": 0.02, "agent_c": 0.02})
        adapter = SynchronousProviderAdapter(backend)
        requests = [_request("agent_a"), _request("agent_b"), _request("agent_c")]

        NaiveConcurrentDispatchPolicy().dispatch(requests, adapter)

        self.assertGreater(len(set(backend.thread_idents)), 1)

    def test_barrier_uses_more_than_one_thread(self):
        backend = _RecordingBackend(delays={"agent_a": 0.02, "agent_b": 0.02, "agent_c": 0.02})
        adapter = SynchronousProviderAdapter(backend)
        requests = [_request("agent_a"), _request("agent_b"), _request("agent_c")]

        BarrierDispatchPolicy().dispatch(requests, adapter)

        self.assertGreater(len(set(backend.thread_idents)), 1)

    def test_causal_only_uses_more_than_one_thread(self):
        backend = _RecordingBackend(delays={"agent_a": 0.02, "agent_b": 0.02, "agent_c": 0.02})
        adapter = SynchronousProviderAdapter(backend)
        requests = [_request("agent_a"), _request("agent_b"), _request("agent_c")]

        CausalOnlyDispatchPolicy().dispatch(requests, adapter)

        self.assertGreater(len(set(backend.thread_idents)), 1)


class DispatchPolicyOrderingTests(unittest.TestCase):
    def test_sequential_preserves_submission_order_regardless_of_delay(self):
        backend = _RecordingBackend(delays={"agent_slow": 0.05})
        adapter = SynchronousProviderAdapter(backend)
        requests = [_request("agent_slow"), _request("agent_fast")]

        outcomes = SequentialDispatchPolicy().dispatch(requests, adapter)

        self.assertEqual(
            [str(request.agent_profile.agent_id) for request, _ in outcomes],
            ["agent_slow", "agent_fast"],
        )

    def test_naive_concurrent_reorders_by_completion_time(self):
        backend = _RecordingBackend(delays={"agent_slow": 0.05})
        adapter = SynchronousProviderAdapter(backend)
        requests = [_request("agent_slow"), _request("agent_fast")]

        outcomes = NaiveConcurrentDispatchPolicy().dispatch(requests, adapter)

        self.assertEqual(str(outcomes[0][0].agent_profile.agent_id), "agent_fast")


class BarrierDispatchPolicyBoundaryTests(unittest.TestCase):
    def test_second_backend_hint_group_waits_for_the_first_to_finish(self):
        backend = _RecordingBackend(delays={"agent_a1": 0.05})
        adapter = SynchronousProviderAdapter(backend)
        requests = [
            _request("agent_a1", backend_hint="mock"),
            _request("agent_a2", backend_hint="mock"),
            _request("agent_b1", backend_hint="other"),
            _request("agent_b2", backend_hint="other"),
        ]

        BarrierDispatchPolicy().dispatch(requests, adapter)

        group1_end = max(
            end for agent_id, _, end in backend.call_intervals if agent_id in {"agent_a1", "agent_a2"}
        )
        group2_start = min(
            start for agent_id, start, _ in backend.call_intervals if agent_id in {"agent_b1", "agent_b2"}
        )
        self.assertGreaterEqual(group2_start, group1_end)

    def test_naive_concurrent_ignores_backend_hint_boundaries(self):
        backend = _RecordingBackend(delays={"agent_a1": 0.05})
        adapter = SynchronousProviderAdapter(backend)
        requests = [
            _request("agent_a1", backend_hint="mock"),
            _request("agent_a2", backend_hint="mock"),
            _request("agent_b1", backend_hint="other"),
            _request("agent_b2", backend_hint="other"),
        ]

        NaiveConcurrentDispatchPolicy().dispatch(requests, adapter)

        group1_end = max(
            end for agent_id, _, end in backend.call_intervals if agent_id in {"agent_a1", "agent_a2"}
        )
        group2_start = min(
            start for agent_id, start, _ in backend.call_intervals if agent_id in {"agent_b1", "agent_b2"}
        )
        self.assertLess(group2_start, group1_end)


class CausalOnlyDispatchPolicyWaveTests(unittest.TestCase):
    def test_dependent_request_dispatches_only_after_its_parent(self):
        request_a = _request("agent_a")
        request_b = _request("agent_b")
        dependent_message = Message.create(
            sender_id=AgentId("agent_a"),
            recipient_id=AgentId("agent_c"),
            message_type=MessageType.SYNTHETIC_HOP,
            origin_activation_id=request_a.activation.activation_id,
        )
        request_c = _request("agent_c", inbox_messages=[dependent_message])

        backend = _RecordingBackend()
        adapter = SynchronousProviderAdapter(backend)

        # Deliberately out of causal order in the input list.
        CausalOnlyDispatchPolicy().dispatch([request_c, request_a, request_b], adapter)

        index_a = backend.call_order.index("agent_a")
        index_c = backend.call_order.index("agent_c")
        self.assertLess(index_a, index_c)

    def test_two_independent_requests_land_in_the_same_wave(self):
        waves = CausalOnlyDispatchPolicy()._build_waves([_request("agent_a"), _request("agent_b")])

        self.assertEqual(len(waves), 1)
        self.assertEqual(len(waves[0]), 2)


class CapabilityAwareDispatchPolicyTests(unittest.TestCase):
    def test_falls_back_to_sequential_when_backend_does_not_support_concurrency(self):
        backend = _RecordingBackend(capabilities=_capabilities(supports_concurrency=False))
        adapter = SynchronousProviderAdapter(backend)
        requests = [_request("agent_a"), _request("agent_b"), _request("agent_c")]

        CapabilityAwareDispatchPolicy().dispatch(requests, adapter)

        self.assertEqual(set(backend.thread_idents), {threading.current_thread().ident})

    def test_dispatches_concurrently_when_backend_supports_concurrency(self):
        backend = _RecordingBackend(
            delays={"agent_a": 0.02, "agent_b": 0.02, "agent_c": 0.02},
            capabilities=_capabilities(supports_concurrency=True),
        )
        adapter = SynchronousProviderAdapter(backend)
        requests = [_request("agent_a"), _request("agent_b"), _request("agent_c")]

        CapabilityAwareDispatchPolicy().dispatch(requests, adapter)

        self.assertGreater(len(set(backend.thread_idents)), 1)


class QueueAwareDispatchPolicyTests(unittest.TestCase):
    def test_peak_concurrency_never_exceeds_the_configured_cap(self):
        backend = _PeakConcurrencyBackend(delay=0.02)
        adapter = SynchronousProviderAdapter(backend)
        requests = [_request(f"agent_{i}") for i in range(6)]

        QueueAwareDispatchPolicy(default_max_in_flight=2).dispatch(requests, adapter)

        self.assertLessEqual(backend.peak_active, 2)

    def test_naive_concurrent_can_exceed_the_same_cap(self):
        backend = _PeakConcurrencyBackend(delay=0.02)
        adapter = SynchronousProviderAdapter(backend)
        requests = [_request(f"agent_{i}") for i in range(6)]

        NaiveConcurrentDispatchPolicy(max_workers=6).dispatch(requests, adapter)

        self.assertGreater(backend.peak_active, 2)


class FullDispatchPolicyTests(unittest.TestCase):
    def test_role_groups_dispatch_one_after_the_other(self):
        backend = _RecordingBackend(
            delays={"agent_a1": 0.05},
            capabilities=_capabilities(supports_concurrency=True),
        )
        adapter = SynchronousProviderAdapter(backend)
        requests = [
            _request("agent_a1", role="role_a"),
            _request("agent_a2", role="role_a"),
            _request("agent_b1", role="role_b"),
            _request("agent_b2", role="role_b"),
        ]

        FullDispatchPolicy(default_max_in_flight=4).dispatch(requests, adapter)

        role_a_end = max(
            end for agent_id, _, end in backend.call_intervals if agent_id in {"agent_a1", "agent_a2"}
        )
        role_b_start = min(
            start for agent_id, start, _ in backend.call_intervals if agent_id in {"agent_b1", "agent_b2"}
        )
        self.assertGreaterEqual(role_b_start, role_a_end)


if __name__ == "__main__":
    unittest.main()
