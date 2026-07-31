import unittest

from agentic_sim.observability.b2_selection import select_best_candidate


def _candidate(value, mean, stdev, had_preemption=False):
    return {
        "value": value,
        "useful_agent_steps_per_second": {"mean": mean, "stdev": stdev},
        "had_preemption": had_preemption,
    }


class SelectBestCandidateTests(unittest.TestCase):
    def test_preempting_candidate_is_disqualified_even_with_best_throughput(self):
        candidates = [
            _candidate(8192, mean=1.0, stdev=0.05),
            _candidate(65536, mean=5.0, stdev=0.05, had_preemption=True),  # best raw throughput, but preempts
        ]

        result = select_best_candidate(candidates)

        self.assertEqual(result["winner"], 8192)
        self.assertEqual(result["disqualified"], [65536])

    def test_clear_non_overlapping_winner_is_picked(self):
        candidates = [
            _candidate(32, mean=1.0, stdev=0.05),
            _candidate(64, mean=1.5, stdev=0.05),
            _candidate(128, mean=1.2, stdev=0.05),
        ]

        result = select_best_candidate(candidates)

        self.assertEqual(result["winner"], 64)
        self.assertEqual(result["tied"], [])

    def test_overlapping_bands_resolve_to_smaller_numeric_value(self):
        candidates = [
            _candidate(0.85, mean=1.40, stdev=0.20),
            _candidate(0.90, mean=1.45, stdev=0.20),  # overlaps 0.85's band, nominally higher
            _candidate(0.95, mean=1.00, stdev=0.05),  # clearly worse, not tied
        ]

        result = select_best_candidate(candidates)

        self.assertEqual(result["winner"], 0.85)
        self.assertIn(0.85, result["tied"])
        self.assertIn(0.90, result["tied"])
        self.assertNotIn(0.95, result["tied"])

    def test_overlapping_bands_for_non_numeric_values_prefer_first_listed(self):
        candidates = [
            _candidate("baseline", mean=1.40, stdev=0.20),
            _candidate("aiter", mean=1.45, stdev=0.20),  # overlaps, nominally higher
        ]

        result = select_best_candidate(candidates)

        self.assertEqual(result["winner"], "baseline")

    def test_all_disqualified_reports_no_winner_not_a_crash(self):
        candidates = [
            _candidate(8192, mean=1.0, stdev=0.05, had_preemption=True),
            _candidate(16384, mean=2.0, stdev=0.05, had_preemption=True),
        ]

        result = select_best_candidate(candidates)

        self.assertIsNone(result["winner"])
        self.assertEqual(set(result["disqualified"]), {8192, 16384})

    def test_empty_candidates_handled(self):
        result = select_best_candidate([])

        self.assertIsNone(result["winner"])
        self.assertEqual(result["reason"], "no candidates")


if __name__ == "__main__":
    unittest.main()
