import unittest

from agentic_sim.observability.rocm_collector import RocmTelemetryCollector, parse_rocm_smi_json

# Fixture shape based on public rocm-smi --json documentation/examples, not
# verified against real hardware output in this session.
ROCM_SMI_FIXTURE = """
{
    "card0": {
        "GPU use (%)": "23",
        "VRAM Total Memory (B)": "68702699520",
        "VRAM Total Used Memory (B)": "2145845248",
        "Average Graphics Package Power (W)": "120.0"
    },
    "card1": {
        "GPU use (%)": "0",
        "VRAM Total Memory (B)": "68702699520",
        "VRAM Total Used Memory (B)": "104857600",
        "Average Graphics Package Power (W)": "35.5"
    },
    "system": {
        "Driver version": "6.2.0"
    }
}
"""


class ParseRocmSmiJsonTests(unittest.TestCase):
    def test_parses_multiple_cards_and_converts_bytes_to_mb(self):
        samples = parse_rocm_smi_json(ROCM_SMI_FIXTURE, collected_at="2026-07-29T00:00:00+00:00")

        self.assertEqual(len(samples), 2)
        first = samples[0]
        self.assertEqual(first.source, "rocm-smi")
        self.assertEqual(first.accelerator_index, 0)
        self.assertEqual(first.gpu_utilization_percent, 23.0)
        self.assertAlmostEqual(first.hbm_used_mb, 2145845248 / (1024 * 1024))
        self.assertAlmostEqual(first.hbm_total_mb, 68702699520 / (1024 * 1024))
        self.assertEqual(first.gpu_power_watts, 120.0)
        self.assertIsNone(first.error)

        second = samples[1]
        self.assertEqual(second.accelerator_index, 1)

    def test_ignores_non_card_keys(self):
        samples = parse_rocm_smi_json(ROCM_SMI_FIXTURE, collected_at="2026-07-29T00:00:00+00:00")

        self.assertTrue(all(sample.accelerator_index in (0, 1) for sample in samples))

    def test_malformed_json_returns_error_sample_not_exception(self):
        samples = parse_rocm_smi_json("not json", collected_at="2026-07-29T00:00:00+00:00")

        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0].source, "rocm-smi")
        self.assertIsNotNone(samples[0].error)


class RocmTelemetryCollectorTests(unittest.TestCase):
    def test_collect_uses_injected_runner(self):
        collector = RocmTelemetryCollector(runner=lambda argv, timeout: ROCM_SMI_FIXTURE)

        samples = collector.collect()

        self.assertEqual(len(samples), 2)
        self.assertEqual(samples[0].source, "rocm-smi")

    def test_collect_returns_error_sample_when_runner_raises(self):
        def failing_runner(argv, timeout):
            raise FileNotFoundError("rocm-smi: command not found")

        collector = RocmTelemetryCollector(runner=failing_runner)

        samples = collector.collect()

        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0].source, "rocm-smi")
        self.assertIn("rocm-smi", samples[0].error)
