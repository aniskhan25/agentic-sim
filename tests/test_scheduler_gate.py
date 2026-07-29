import json
import os
import unittest

from agentic_sim.observability import WORKLOAD_VARIANTS, run_scheduler_contribution_gate
from agentic_sim.observability.scheduler_gate import HETEROGENEITY_BEARING_VARIANTS

_TMP_OUTPUT = "/tmp/agentic_sim_scheduler_gate_test.json"

_EXPECTED_POLICIES = {
    "sequential",
    "naive_concurrent",
    "barrier",
    "causal_only",
    "capability_aware",
    "queue_aware",
    "full",
}


class SchedulerGateTests(unittest.TestCase):
    def tearDown(self):
        if os.path.exists(_TMP_OUTPUT):
            os.remove(_TMP_OUTPUT)

    def test_writes_all_policies_and_variants_with_expected_structure(self):
        payload = run_scheduler_contribution_gate(repeats=2, output_path=_TMP_OUTPUT)

        self.assertTrue(os.path.exists(_TMP_OUTPUT))
        with open(_TMP_OUTPUT) as f:
            on_disk = json.load(f)
        self.assertEqual(on_disk, payload)

        variant_names = {report["variant"] for report in payload["variants"]}
        self.assertEqual(variant_names, {name for name, _, _ in WORKLOAD_VARIANTS})

        for report in payload["variants"]:
            policy_stats = report["throughput_requests_per_second"]
            self.assertEqual(set(policy_stats.keys()), _EXPECTED_POLICIES)
            for stats in policy_stats.values():
                self.assertIn("mean", stats)
                self.assertIn("stdev", stats)
                self.assertIn("ci95", stats)
                self.assertEqual(len(stats["ci95"]), 2)

            gate = report["gate"]
            self.assertIn("cleared", gate)
            self.assertIsInstance(gate["cleared"], bool)
            if report["variant"] in HETEROGENEITY_BEARING_VARIANTS:
                self.assertTrue(gate["applicable"])
            else:
                self.assertFalse(gate["applicable"])

        self.assertIn("overall_gate_cleared", payload)
        self.assertIsInstance(payload["overall_gate_cleared"], bool)
        self.assertIn("excluded", payload)

    def test_control_variant_never_requires_an_effect(self):
        payload = run_scheduler_contribution_gate(repeats=2, output_path=_TMP_OUTPUT)

        control_report = next(
            report for report in payload["variants"] if report["variant"] == "single_provider"
        )
        self.assertTrue(control_report["gate"]["cleared"])
        self.assertFalse(control_report["gate"]["applicable"])


if __name__ == "__main__":
    unittest.main()
