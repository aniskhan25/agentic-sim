import unittest

from agentic_sim.observability.cuda_collector import CudaTelemetryCollector, parse_nvidia_smi_csv

# Fixture shape based on public nvidia-smi --query-gpu documentation/examples,
# not verified against real hardware output in this session.
NVIDIA_SMI_FIXTURE = """0, 45, 2048, 16384, 62.31
1, 0, 512, 16384, 20.10
"""


class ParseNvidiaSmiCsvTests(unittest.TestCase):
    def test_parses_multiple_gpus(self):
        samples = parse_nvidia_smi_csv(NVIDIA_SMI_FIXTURE, collected_at="2026-07-29T00:00:00+00:00")

        self.assertEqual(len(samples), 2)
        first = samples[0]
        self.assertEqual(first.source, "nvidia-smi")
        self.assertEqual(first.accelerator_index, 0)
        self.assertEqual(first.gpu_utilization_percent, 45.0)
        self.assertEqual(first.hbm_used_mb, 2048.0)
        self.assertEqual(first.hbm_total_mb, 16384.0)
        self.assertEqual(first.gpu_power_watts, 62.31)
        self.assertIsNone(first.error)

        second = samples[1]
        self.assertEqual(second.accelerator_index, 1)

    def test_ignores_blank_lines(self):
        samples = parse_nvidia_smi_csv("\n" + NVIDIA_SMI_FIXTURE + "\n", collected_at="2026-07-29T00:00:00+00:00")

        self.assertEqual(len(samples), 2)

    def test_malformed_line_returns_error_sample_not_exception(self):
        samples = parse_nvidia_smi_csv("0, 45\n", collected_at="2026-07-29T00:00:00+00:00")

        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0].source, "nvidia-smi")
        self.assertIsNotNone(samples[0].error)


class CudaTelemetryCollectorTests(unittest.TestCase):
    def test_collect_uses_injected_runner(self):
        collector = CudaTelemetryCollector(runner=lambda argv, timeout: NVIDIA_SMI_FIXTURE)

        samples = collector.collect()

        self.assertEqual(len(samples), 2)
        self.assertEqual(samples[0].source, "nvidia-smi")

    def test_collect_returns_error_sample_when_runner_raises(self):
        def failing_runner(argv, timeout):
            raise FileNotFoundError("nvidia-smi: command not found")

        collector = CudaTelemetryCollector(runner=failing_runner)

        samples = collector.collect()

        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0].source, "nvidia-smi")
        self.assertIn("nvidia-smi", samples[0].error)
