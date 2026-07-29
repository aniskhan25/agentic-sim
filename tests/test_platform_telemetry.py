import unittest
from types import SimpleNamespace

from agentic_sim.observability.artifacts import _platform_telemetry


def _telemetry_event(samples: list[dict]) -> SimpleNamespace:
    return SimpleNamespace(event_name="platform_telemetry", payload={"samples": samples})


class PlatformTelemetryTests(unittest.TestCase):
    def test_no_traces_returns_all_none_shape_without_crashing(self):
        metrics = _platform_telemetry([])

        self.assertEqual(metrics["sample_count"], 0)
        self.assertEqual(metrics["error_count"], 0)
        self.assertEqual(metrics["sources"], [])
        self.assertEqual(metrics["gpu_utilization_percent"], {"count": 0, "min": None, "max": None, "avg": None})

    def test_ignores_non_platform_telemetry_events(self):
        traces = [SimpleNamespace(event_name="agent_step", payload={"metadata": {}})]

        metrics = _platform_telemetry(traces)

        self.assertEqual(metrics["sample_count"], 0)

    def test_aggregates_samples_across_multiple_events(self):
        traces = [
            _telemetry_event(
                [
                    {"source": "rocm-smi", "gpu_utilization_percent": 20.0, "hbm_used_mb": 100.0},
                    {"source": "rocm-smi", "gpu_utilization_percent": 40.0, "hbm_used_mb": 200.0},
                ]
            ),
            _telemetry_event([{"source": "rocm-smi", "gpu_utilization_percent": 60.0, "hbm_used_mb": 300.0}]),
        ]

        metrics = _platform_telemetry(traces)

        self.assertEqual(metrics["sample_count"], 3)
        self.assertEqual(metrics["sources"], ["rocm-smi"])
        self.assertEqual(metrics["gpu_utilization_percent"]["count"], 3)
        self.assertAlmostEqual(metrics["gpu_utilization_percent"]["avg"], 40.0)
        self.assertEqual(metrics["gpu_utilization_percent"]["min"], 20.0)
        self.assertEqual(metrics["gpu_utilization_percent"]["max"], 60.0)
        self.assertAlmostEqual(metrics["hbm_used_mb"]["avg"], 200.0)

    def test_error_count_tracks_failed_collections_separately_from_missing_fields(self):
        traces = [
            _telemetry_event(
                [
                    {"source": "rocm-smi", "error": "rocm-smi: command not found"},
                    {"source": "nvidia-smi", "gpu_utilization_percent": 10.0},
                ]
            )
        ]

        metrics = _platform_telemetry(traces)

        self.assertEqual(metrics["sample_count"], 2)
        self.assertEqual(metrics["error_count"], 1)
        self.assertEqual(metrics["sources"], ["nvidia-smi", "rocm-smi"])

    def test_unpopulated_serving_runtime_fields_report_zero_count_not_fabricated(self):
        traces = [_telemetry_event([{"source": "rocm-smi", "gpu_utilization_percent": 10.0}])]

        metrics = _platform_telemetry(traces)

        self.assertEqual(metrics["kv_cache_used_percent"], {"count": 0, "min": None, "max": None, "avg": None})
        self.assertEqual(metrics["preemption_count"], {"count": 0, "min": None, "max": None, "avg": None})
        self.assertEqual(metrics["queue_depth"], {"count": 0, "min": None, "max": None, "avg": None})
