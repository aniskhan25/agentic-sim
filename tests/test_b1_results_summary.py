import math
import unittest

from agentic_sim.observability.b1_results_summary import summarize_b1_results


def _policy_stats(mean, stdev, count=10):
    return {"useful_agent_steps_per_second": {"mean": mean, "stdev": stdev, "count": count}}


def _payload(policies: dict) -> dict:
    return {"policies": policies}


class SummarizeB1ResultsTests(unittest.TestCase):
    def test_single_device_entry_produces_direct_rows(self):
        entries = [
            {
                "system": "roihu",
                "workload": "storm",
                "placement": "single_device",
                "replica_group": None,
                "payload": _payload(
                    {
                        "sequential": _policy_stats(0.85, 0.1),
                        "causal_only": _policy_stats(1.4, 0.2),
                        "full": _policy_stats(1.5, 0.3),
                    }
                ),
            }
        ]

        result = summarize_b1_results(entries)

        rows = {(r["policy"]): r for r in result["rows"]}
        self.assertEqual(rows["sequential"]["mean"], 0.85)
        self.assertEqual(rows["sequential"]["capacity_type"], "per_device")
        self.assertEqual(rows["sequential"]["n_replicas"], 1)
        self.assertIsNone(rows["sequential"]["per_replica_min"])

        contrast_names = {c["contrast"] for c in result["contrasts"]}
        self.assertEqual(contrast_names, {"causal_only_vs_sequential", "full_vs_causal_only", "full_vs_sequential"})

    def test_full_node_replicas_are_summed_with_propagated_stdev(self):
        entries = [
            {
                "system": "lumi",
                "workload": "storm",
                "placement": "full_node",
                "replica_group": "lumi|storm",
                "payload": _payload({"causal_only": _policy_stats(0.35, 0.05)}),
            },
            {
                "system": "lumi",
                "workload": "storm",
                "placement": "full_node",
                "replica_group": "lumi|storm",
                "payload": _payload({"causal_only": _policy_stats(0.40, 0.06)}),
            },
        ]

        result = summarize_b1_results(entries)

        row = next(r for r in result["rows"] if r["policy"] == "causal_only")
        self.assertEqual(row["capacity_type"], "node_total")
        self.assertEqual(row["n_replicas"], 2)
        self.assertAlmostEqual(row["mean"], 0.75)
        self.assertAlmostEqual(row["stdev"], math.sqrt(0.05**2 + 0.06**2))
        self.assertEqual(row["per_replica_min"], 0.35)
        self.assertEqual(row["per_replica_max"], 0.40)

    def test_full_node_contrasts_computed_from_summed_capacity(self):
        entries = [
            {
                "system": "roihu",
                "workload": "storm",
                "placement": "full_node",
                "replica_group": "roihu|storm",
                "payload": _payload(
                    {
                        "sequential": _policy_stats(0.8, 0.1),
                        "causal_only": _policy_stats(1.4, 0.2),
                        "full": _policy_stats(1.5, 0.2),
                    }
                ),
            },
            {
                "system": "roihu",
                "workload": "storm",
                "placement": "full_node",
                "replica_group": "roihu|storm",
                "payload": _payload(
                    {
                        "sequential": _policy_stats(0.8, 0.1),
                        "causal_only": _policy_stats(1.4, 0.2),
                        "full": _policy_stats(1.5, 0.2),
                    }
                ),
            },
        ]

        result = summarize_b1_results(entries)

        node_contrasts = {c["contrast"]: c for c in result["contrasts"] if c["capacity_type"] == "node_total"}
        self.assertTrue(node_contrasts["causal_only_vs_sequential"]["applicable"])
        self.assertGreater(node_contrasts["causal_only_vs_sequential"]["relative_improvement"], 0)

    def test_replica_missing_a_policy_is_not_silently_summed(self):
        entries = [
            {
                "system": "lumi",
                "workload": "storm",
                "placement": "full_node",
                "replica_group": "lumi|storm",
                "payload": _payload({"full": _policy_stats(0.3, 0.05)}),
            },
            {
                "system": "lumi",
                "workload": "storm",
                "placement": "full_node",
                "replica_group": "lumi|storm",
                "payload": _payload({}),  # this replica has no "full" entry at all
            },
        ]

        result = summarize_b1_results(entries)

        row = next(r for r in result["rows"] if r["policy"] == "full")
        self.assertIsNone(row["mean"])
        self.assertEqual(row["count"], 1)

    def test_mixed_single_device_and_full_node_entries(self):
        entries = [
            {
                "system": "roihu",
                "workload": "storm",
                "placement": "single_device",
                "replica_group": None,
                "payload": _payload({"sequential": _policy_stats(0.85, 0.1)}),
            },
            {
                "system": "roihu",
                "workload": "storm",
                "placement": "full_node",
                "replica_group": "roihu|storm",
                "payload": _payload({"sequential": _policy_stats(0.8, 0.1)}),
            },
            {
                "system": "roihu",
                "workload": "storm",
                "placement": "full_node",
                "replica_group": "roihu|storm",
                "payload": _payload({"sequential": _policy_stats(0.82, 0.1)}),
            },
        ]

        result = summarize_b1_results(entries)

        capacity_types = {r["capacity_type"] for r in result["rows"]}
        self.assertEqual(capacity_types, {"per_device", "node_total"})
        self.assertEqual(len(result["rows"]), 2)  # one per_device row, one node_total row


if __name__ == "__main__":
    unittest.main()
