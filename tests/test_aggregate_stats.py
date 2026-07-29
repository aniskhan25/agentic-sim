import json
import statistics
import tempfile
import unittest
from pathlib import Path

from agentic_sim.observability import aggregate_run_stats


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def _base_config(model: str) -> dict:
    return {
        "scenario": "storm",
        "scenario_parameters": {},
        "steps": 8,
        "backend": "aitta",
        "storage_mode": "sqlite",
        "sqlite_path": None,
        "max_batch_size": 4,
        "max_events_per_tick": 32,
        "agent_replicas": 64,
        "backend_options": {"aitta_model": model},
    }


def _write_run(
    root: Path,
    name: str,
    *,
    model: str,
    seed: int,
    invalid: int,
    guard_messages: int,
    guard_actions: int,
    latency_avg: float,
    backend_steps: int = 100,
    extra_metrics: dict | None = None,
) -> None:
    run_dir = root / name
    config = _base_config(model)
    config["seed"] = seed
    _write_json(run_dir / "config.json", config)

    backend_metrics = {
        "backend_steps": backend_steps,
        "invalid_model_outputs": invalid,
        "policy_guard_added_messages": guard_messages,
        "policy_guard_added_actions": guard_actions,
        "latency_seconds": {"avg": latency_avg},
    }
    if extra_metrics:
        backend_metrics.update(extra_metrics)
    _write_json(run_dir / "backend_metrics.json", backend_metrics)


class AggregateRunStatsTests(unittest.TestCase):
    def test_groups_repeated_runs_and_computes_mean_stdev(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            invalid_counts = [90, 92, 94, 96, 98]
            latencies = [1.40, 1.41, 1.42, 1.43, 1.44]
            for i, (invalid, latency) in enumerate(zip(invalid_counts, latencies)):
                _write_run(
                    root,
                    f"run_{i}",
                    model="TinyLlama-1.1B-Chat-v1.0",
                    seed=i,
                    invalid=invalid,
                    guard_messages=5,
                    guard_actions=0,
                    latency_avg=latency,
                )

            payload = aggregate_run_stats(root)

        self.assertEqual(payload["group_count"], 1)
        group = payload["groups"][0]
        self.assertEqual(group["run_count"], 5)
        self.assertEqual(group["seeds"], [0, 1, 2, 3, 4])

        expected_rates = [c / 100 for c in invalid_counts]
        self.assertAlmostEqual(group["invalid_model_output_rate"]["mean"], statistics.mean(expected_rates), places=5)
        self.assertAlmostEqual(group["invalid_model_output_rate"]["stdev"], statistics.stdev(expected_rates), places=5)
        self.assertEqual(group["invalid_model_output_rate"]["count"], 5)

        self.assertAlmostEqual(group["policy_guard_added_message_rate"]["mean"], 0.05)
        self.assertEqual(group["policy_guard_added_message_rate"]["stdev"], 0.0)
        self.assertEqual(group["policy_guard_added_action_rate"]["mean"], 0.0)

        self.assertAlmostEqual(group["latency_seconds_mean"]["mean"], statistics.mean(latencies), places=5)
        self.assertAlmostEqual(group["latency_seconds_mean"]["stdev"], statistics.stdev(latencies), places=5)

    def test_different_model_splits_into_separate_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for i in range(5):
                _write_run(
                    root,
                    f"tiny_{i}",
                    model="TinyLlama-1.1B-Chat-v1.0",
                    seed=i,
                    invalid=90 + i,
                    guard_messages=5,
                    guard_actions=0,
                    latency_avg=1.4,
                )
            for i in range(3):
                _write_run(
                    root,
                    f"big_{i}",
                    model="bigger-model",
                    seed=i,
                    invalid=10 + i,
                    guard_messages=1,
                    guard_actions=0,
                    latency_avg=2.1,
                )

            payload = aggregate_run_stats(root)

        self.assertEqual(payload["group_count"], 2)
        run_counts = sorted(group["run_count"] for group in payload["groups"])
        self.assertEqual(run_counts, [3, 5])

    def test_unknown_backend_metrics_field_does_not_break_aggregation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_run(
                root,
                "run_0",
                model="TinyLlama-1.1B-Chat-v1.0",
                seed=0,
                invalid=90,
                guard_messages=5,
                guard_actions=0,
                latency_avg=1.4,
                extra_metrics={"json_repair_attempts": 7},
            )
            _write_run(
                root,
                "run_1",
                model="TinyLlama-1.1B-Chat-v1.0",
                seed=1,
                invalid=92,
                guard_messages=5,
                guard_actions=0,
                latency_avg=1.41,
            )

            payload = aggregate_run_stats(root)

        self.assertEqual(payload["group_count"], 1)
        self.assertEqual(payload["groups"][0]["run_count"], 2)

    def test_aggregates_must_not_semantic_autonomy_and_useful_throughput(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            autonomy_avgs = [0.5, 0.6, 0.7]
            throughputs = [2.0, 2.2, 2.4]
            for i, (autonomy, throughput) in enumerate(zip(autonomy_avgs, throughputs)):
                _write_run(
                    root,
                    f"run_{i}",
                    model="TinyLlama-1.1B-Chat-v1.0",
                    seed=i,
                    invalid=10,
                    guard_messages=2,
                    guard_actions=1,
                    latency_avg=1.4,
                    extra_metrics={
                        "must_not_violations": 1,
                        "semantic_valid_count": 80,
                        "message_action_autonomy_rate": {"avg": autonomy},
                        "useful_agent_steps_per_second": throughput,
                    },
                )

            payload = aggregate_run_stats(root)

        group = payload["groups"][0]
        self.assertAlmostEqual(group["must_not_violation_rate"]["mean"], 0.01, places=5)
        self.assertAlmostEqual(group["semantic_valid_rate"]["mean"], 0.8, places=5)
        self.assertAlmostEqual(
            group["message_action_autonomy_rate_mean"]["mean"], statistics.mean(autonomy_avgs), places=5
        )
        self.assertAlmostEqual(
            group["useful_agent_steps_per_second_mean"]["mean"], statistics.mean(throughputs), places=5
        )
        self.assertEqual(group["useful_agent_steps_per_second_mean"]["count"], 3)

    def test_message_action_autonomy_unavailable_rate_aggregates_across_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unavailable_counts = [10, 20, 30]
            for i, unavailable in enumerate(unavailable_counts):
                _write_run(
                    root,
                    f"run_{i}",
                    model="TinyLlama-1.1B-Chat-v1.0",
                    seed=i,
                    invalid=10,
                    guard_messages=2,
                    guard_actions=1,
                    latency_avg=1.4,
                    extra_metrics={"message_action_autonomy_unavailable_steps": unavailable},
                )

            payload = aggregate_run_stats(root)

        group = payload["groups"][0]
        expected_rates = [c / 100 for c in unavailable_counts]
        self.assertAlmostEqual(
            group["message_action_autonomy_unavailable_rate"]["mean"],
            statistics.mean(expected_rates),
            places=5,
        )

    def test_platform_telemetry_mean_aggregates_when_present_and_is_absent_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gpu_utilization_avgs = [30.0, 40.0, 50.0]
            for i, avg in enumerate(gpu_utilization_avgs):
                _write_run(
                    root,
                    f"run_{i}",
                    model="TinyLlama-1.1B-Chat-v1.0",
                    seed=i,
                    invalid=10,
                    guard_messages=2,
                    guard_actions=1,
                    latency_avg=1.4,
                )
                if i < 2:
                    _write_json(
                        root / f"run_{i}" / "platform_telemetry.json",
                        {"gpu_utilization_percent": {"avg": avg}},
                    )
                # run_2 has no platform_telemetry.json at all -- must not crash aggregation.

            payload = aggregate_run_stats(root)

        group = payload["groups"][0]
        self.assertEqual(group["run_count"], 3)
        self.assertEqual(group["gpu_utilization_percent_mean"]["count"], 2)
        self.assertAlmostEqual(
            group["gpu_utilization_percent_mean"]["mean"], statistics.mean(gpu_utilization_avgs[:2]), places=5
        )

    def test_output_path_writes_json_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_run(
                root,
                "run_0",
                model="TinyLlama-1.1B-Chat-v1.0",
                seed=0,
                invalid=90,
                guard_messages=5,
                guard_actions=0,
                latency_avg=1.4,
            )
            output_path = root / "aggregate_stats.json"

            aggregate_run_stats(root, output_path=output_path)

            self.assertTrue(output_path.exists())
            saved = json.loads(output_path.read_text())
            self.assertEqual(saved["group_count"], 1)
