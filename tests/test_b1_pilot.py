import json
import os
import unittest

from agentic_sim.observability.b1_pilot import run_b1_pilot
from agentic_sim.scenarios.storm import create_storm_engine
from agentic_sim.scheduling import FullDispatchPolicy, SequentialDispatchPolicy

_TMP_OUTPUT = "/tmp/agentic_sim_b1_pilot_test.json"


class RaisingDispatchPolicy:
    name = "raising"

    def dispatch(self, requests, backend):
        raise RuntimeError("simulated dispatch failure")


def _mock_engine_factory():
    return create_storm_engine(backend_name="mock")


class B1PilotTests(unittest.TestCase):
    def tearDown(self):
        if os.path.exists(_TMP_OUTPUT):
            os.remove(_TMP_OUTPUT)

    def test_warmup_does_not_leak_into_measured_repetitions(self):
        result = run_b1_pilot(
            engine_factory=_mock_engine_factory,
            dispatch_policies={"sequential": SequentialDispatchPolicy()},
            repeats=1,
            steps_per_repeat=1,
            warmup_backend_step_count=20,
        )

        self.assertGreaterEqual(result["warmup_backend_steps_observed"], 20)
        # A fresh engine's first repetition should reflect only steps_per_repeat=1
        # tick's worth of backend calls, not the warm-up engine's accumulated state.
        first_rep = result["policies"]["sequential"]["raw_repetitions"][0]
        self.assertLess(first_rep["backend_steps"], 20)

    def test_both_policies_run_requested_repeats(self):
        result = run_b1_pilot(
            engine_factory=_mock_engine_factory,
            dispatch_policies={"sequential": SequentialDispatchPolicy(), "full": FullDispatchPolicy()},
            repeats=3,
            steps_per_repeat=2,
            warmup_backend_step_count=5,
        )

        self.assertEqual(result["policies"]["sequential"]["repeats_completed"], 3)
        self.assertEqual(result["policies"]["full"]["repeats_completed"], 3)
        self.assertEqual(len(result["policies"]["sequential"]["raw_repetitions"]), 3)
        self.assertEqual(result["excluded"], [])
        self.assertTrue(result["contrasts"]["full_vs_sequential"]["applicable"])

    def test_raising_policy_is_excluded_not_raised(self):
        result = run_b1_pilot(
            engine_factory=_mock_engine_factory,
            dispatch_policies={"sequential": SequentialDispatchPolicy(), "raising": RaisingDispatchPolicy()},
            repeats=2,
            steps_per_repeat=1,
            warmup_backend_step_count=5,
        )

        self.assertEqual(result["policies"]["raising"]["repeats_completed"], 0)
        self.assertEqual(len(result["excluded"]), 2)
        for entry in result["excluded"]:
            self.assertEqual(entry["policy"], "raising")
            self.assertIn("simulated dispatch failure", entry["error"])
        # sequential is unaffected by raising's failures
        self.assertEqual(result["policies"]["sequential"]["repeats_completed"], 2)

    def test_output_path_writes_json_file(self):
        result = run_b1_pilot(
            engine_factory=_mock_engine_factory,
            dispatch_policies={"sequential": SequentialDispatchPolicy(), "full": FullDispatchPolicy()},
            repeats=1,
            steps_per_repeat=1,
            warmup_backend_step_count=5,
            output_path=_TMP_OUTPUT,
        )

        self.assertTrue(os.path.exists(_TMP_OUTPUT))
        with open(_TMP_OUTPUT) as f:
            on_disk = json.load(f)
        self.assertEqual(on_disk, result)

    def test_contrasts_require_both_relevant_policy_keys(self):
        result = run_b1_pilot(
            engine_factory=_mock_engine_factory,
            dispatch_policies={"sequential": SequentialDispatchPolicy()},
            repeats=1,
            steps_per_repeat=1,
            warmup_backend_step_count=5,
        )

        self.assertFalse(result["contrasts"]["full_vs_sequential"]["applicable"])
        self.assertFalse(result["contrasts"]["causal_only_vs_sequential"]["applicable"])
        self.assertFalse(result["contrasts"]["full_vs_causal_only"]["applicable"])
