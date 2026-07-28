import unittest
from types import SimpleNamespace

from agentic_sim.observability.artifacts import _backend_metrics


def _agent_step(metadata: dict) -> SimpleNamespace:
    return SimpleNamespace(event_name="agent_step", payload={"metadata": metadata})


def _tick(backend_execution_ms: float) -> SimpleNamespace:
    return SimpleNamespace(
        event_name="simulation_tick",
        payload={"timing_ms": {"backend_execution_ms": backend_execution_ms}},
    )


class BackendMetricsTests(unittest.TestCase):
    def test_useful_agent_steps_per_second_uses_tick_wall_clock_not_summed_latency(self):
        traces = [
            _agent_step({"latency_seconds": 5.0, "useful_step": True, "message_action_autonomy_rate": 1.0}),
            _agent_step({"latency_seconds": 5.0, "useful_step": True, "message_action_autonomy_rate": 1.0}),
            _tick(1000),  # 1s real wall-clock for both steps combined, e.g. under concurrent dispatch
        ]

        metrics = _backend_metrics(traces)

        self.assertEqual(metrics["useful_steps"], 2)
        self.assertAlmostEqual(metrics["backend_execution_wall_seconds"], 1.0)
        # Summed per-step latency would give 10s -> 0.2/s; the tick wall-clock gives 1s -> 2.0/s.
        # This is the regression this test guards against.
        self.assertAlmostEqual(metrics["useful_agent_steps_per_second"], 2.0)

    def test_must_not_semantic_and_autonomy_fields_aggregate(self):
        traces = [
            _agent_step({"must_not_violations": 1, "semantic_valid": False, "message_action_autonomy_rate": 0.0}),
            _agent_step({"must_not_violations": 0, "semantic_valid": True, "message_action_autonomy_rate": 1.0}),
        ]

        metrics = _backend_metrics(traces)

        self.assertEqual(metrics["backend_steps"], 2)
        self.assertEqual(metrics["must_not_violations"], 1)
        self.assertEqual(metrics["semantic_valid_count"], 1)
        self.assertEqual(metrics["message_action_autonomy_rate"]["count"], 2)
        self.assertAlmostEqual(metrics["message_action_autonomy_rate"]["avg"], 0.5)

    def test_useful_agent_steps_per_second_is_none_without_tick_traces(self):
        traces = [_agent_step({"useful_step": True})]

        metrics = _backend_metrics(traces)

        self.assertIsNone(metrics["useful_agent_steps_per_second"])
        self.assertEqual(metrics["backend_execution_wall_seconds"], 0.0)
        self.assertEqual(metrics["useful_steps"], 1)

    def test_autonomy_unavailable_distinguished_from_field_absent(self):
        traces = [
            # a real Aitta step where the rate was computed as unavailable (empty commit)
            _agent_step({"useful_step": True, "message_action_autonomy_rate": None}),
            # a mock/rule-backend step that never sets the field at all
            _agent_step({"useful_step": True}),
        ]

        metrics = _backend_metrics(traces)

        self.assertEqual(metrics["backend_steps"], 2)
        self.assertEqual(metrics["message_action_autonomy_unavailable_steps"], 1)
        self.assertEqual(metrics["message_action_autonomy_rate"]["count"], 0)
