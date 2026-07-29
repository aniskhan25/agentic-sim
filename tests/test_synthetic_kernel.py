import unittest

from agentic_sim.engine import create_engine, create_synthetic_engine
from agentic_sim.observability import graph_metrics, run_kernel_benchmarks, verify
from agentic_sim.scenarios.synthetic import expected_invariants, step_count_for
from agentic_sim.scheduling import (
    BarrierDispatchPolicy,
    CapabilityAwareDispatchPolicy,
    CausalOnlyDispatchPolicy,
    FullDispatchPolicy,
    NaiveConcurrentDispatchPolicy,
    QueueAwareDispatchPolicy,
    SequentialDispatchPolicy,
)

SHAPE_PARAMS = [
    ("chain", {"length": 4}),
    ("fan_out", {"width": 3}),
    ("fork_join", {"width": 3}),
    ("independent_branches", {"branch_count": 3, "length": 3}),
    ("mixed_dag", {"length": 3}),
    ("conflicting_write", {"writers": 3}),
]

# Shapes with no shared-state contention -- FIFOScheduler still guarantees one
# activation per agent per tick, and none of these involve environment writes,
# so every dispatch policy must produce byte-identical results.
NON_CONFLICT_SHAPE_PARAMS = [item for item in SHAPE_PARAMS if item[0] != "conflicting_write"]


class SyntheticKernelShapeTests(unittest.TestCase):
    def test_every_shape_matches_its_expected_invariants_with_zero_violations(self):
        for shape, params in SHAPE_PARAMS:
            with self.subTest(shape=shape):
                engine = create_synthetic_engine(scenario_parameters={"shape": shape, **params})
                engine.run(step_count_for(shape, params))

                traces = engine.store.traces.list()
                result = verify(traces)
                self.assertEqual(result.violations, [])
                self.assertEqual(graph_metrics(traces), expected_invariants(shape, params))

    def test_via_scenario_registry(self):
        engine = create_engine(
            scenario="synthetic",
            scenario_parameters={"shape": "fork_join", "width": 3},
        )
        engine.run(step_count_for("fork_join", {"width": 3}))

        result = verify(engine.store.traces.list())
        self.assertEqual(result.violations, [])

    def test_conflicting_write_is_deterministic_across_runs(self):
        params = {"writers": 4}

        def run_once():
            engine = create_synthetic_engine(
                scenario_parameters={"shape": "conflicting_write", **params}
            )
            engine.run(step_count_for("conflicting_write", params))
            return engine.store.environment.get().variables["x"]

        first = run_once()
        second = run_once()

        self.assertEqual(first, second)

    def test_conflicting_write_reports_zero_causal_violations(self):
        params = {"writers": 3}
        engine = create_synthetic_engine(
            scenario_parameters={"shape": "conflicting_write", **params}
        )
        engine.run(step_count_for("conflicting_write", params))

        result = verify(engine.store.traces.list())

        self.assertEqual(result.violations, [])

    def test_aitta_backend_is_rejected(self):
        with self.assertRaises(ValueError):
            create_synthetic_engine(backend_name="aitta", scenario_parameters={"shape": "chain"})

    def test_all_dispatch_policies_run_identical_workloads_on_non_conflict_shapes(self):
        policies = [
            None,
            SequentialDispatchPolicy(),
            NaiveConcurrentDispatchPolicy(),
            BarrierDispatchPolicy(),
            CausalOnlyDispatchPolicy(),
            CapabilityAwareDispatchPolicy(),
            QueueAwareDispatchPolicy(),
            FullDispatchPolicy(),
        ]
        for shape, params in NON_CONFLICT_SHAPE_PARAMS:
            expected = expected_invariants(shape, params)
            for policy in policies:
                with self.subTest(shape=shape, policy=policy.name if policy else "default"):
                    engine = create_synthetic_engine(scenario_parameters={"shape": shape, **params})
                    engine.dispatch_policy = policy
                    engine.run(step_count_for(shape, params))

                    traces = engine.store.traces.list()
                    self.assertEqual(verify(traces).violations, [])
                    self.assertEqual(graph_metrics(traces), expected)


class KernelBenchmarksTests(unittest.TestCase):
    def test_writes_expected_timing_categories(self, tmp_output="/tmp/agentic_sim_kernel_bench_test.json"):
        payload = run_kernel_benchmarks(
            shapes=[("chain", {"length": 3})],
            repeats=2,
            output_path=tmp_output,
        )

        import json
        import os

        self.assertTrue(os.path.exists(tmp_output))
        with open(tmp_output) as f:
            on_disk = json.load(f)
        os.remove(tmp_output)

        self.assertEqual(on_disk, payload)
        timing = payload["shapes"][0]["timing_ms"]
        for key in ("scheduling_ms", "state_commit_ms", "message_delivery_ms", "tracing_ms"):
            self.assertIn(key, timing)
            self.assertIn("min", timing[key])
            self.assertIn("mean", timing[key])
            self.assertIn("max", timing[key])


if __name__ == "__main__":
    unittest.main()
