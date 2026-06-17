import json
import os
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from agentic_sim.cli import main


class CliTests(unittest.TestCase):
    def test_run_command_writes_full_artifact(self):
        with TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "run.json"

            with redirect_stdout(StringIO()):
                exit_code = main(
                    ["run", "--scenario", "storm", "--steps", "2", "--output", str(output)]
                )

            self.assertEqual(exit_code, 0)
            artifact = json.loads(output.read_text())
            self.assertIn("ticks", artifact)
            self.assertIn("summary", artifact)
            self.assertIn("environment", artifact)
            self.assertIn("traces", artifact)
            self.assertGreaterEqual(len(artifact["traces"]), 1)

    def test_run_command_writes_split_artifacts(self):
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "artifacts"

            with redirect_stdout(StringIO()) as stdout:
                exit_code = main(
                    [
                        "run",
                        "--scenario",
                        "storm",
                        "--steps",
                        "1",
                        "--output-dir",
                        str(output_dir),
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["artifacts"]["output_dir"], str(output_dir))
            for filename in [
                "metadata.json",
                "config.json",
                "summary.json",
                "ticks.json",
                "environment.json",
                "traces.json",
                "backend_metrics.json",
            ]:
                self.assertTrue((output_dir / filename).exists(), filename)

            metadata = json.loads((output_dir / "metadata.json").read_text())
            self.assertEqual(metadata["scenario"], "storm")
            self.assertEqual(metadata["backend"], "mock")

    def test_aggregate_runs_reads_split_artifacts(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "runs"
            output_dir = root / "run_0" / "artifacts"
            aggregate = root / "aggregate.json"

            with redirect_stdout(StringIO()):
                main(["run", "--scenario", "storm", "--steps", "1", "--output-dir", str(output_dir)])

            with redirect_stdout(StringIO()) as stdout:
                exit_code = main(["aggregate-runs", str(root), "--output", str(aggregate)])

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["run_count"], 1)
            self.assertTrue(aggregate.exists())
            saved = json.loads(aggregate.read_text())
            self.assertEqual(saved["runs"][0]["metadata"]["scenario"], "storm")

    def test_run_command_loads_supply_chain_config(self):
        with redirect_stdout(StringIO()) as stdout:
            exit_code = main(["run", "--config", "configs/supply_chain_small.json"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertGreaterEqual(payload["summary"]["environment_tick"], 1)
        self.assertGreaterEqual(payload["summary"]["messages"], 1)

    def test_check_aitta_reports_missing_credentials(self):
        keys = ["AITTA_API_KEY", "AITTA_BASE_URL", "AITTA_MODEL"]
        old_values = {key: os.environ.get(key) for key in keys}
        try:
            for key in keys:
                os.environ[key] = ""
            with redirect_stdout(StringIO()) as stdout:
                exit_code = main(["check-aitta"])
        finally:
            for key, value in old_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.assertEqual(exit_code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["ok"])
        self.assertIn("AITTA", payload["error"])

    def test_check_aitta_waits_until_probe_succeeds(self):
        with patch("agentic_sim.cli.time.sleep") as sleep:
            with patch(
                "agentic_sim.cli.check_aitta_connection",
                side_effect=[
                    RuntimeError("model is starting"),
                    {"ok": True, "base_url": "https://aitta.example/openai/v1/", "model": "demo"},
                ],
            ):
                with redirect_stdout(StringIO()) as stdout:
                    exit_code = main(
                        [
                            "check-aitta",
                            "--wait",
                            "--wait-timeout",
                            "30",
                            "--wait-interval",
                            "0",
                        ]
                    )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["attempts"], 2)
        sleep.assert_called_once_with(0)
