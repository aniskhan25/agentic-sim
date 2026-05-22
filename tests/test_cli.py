import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

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

    def test_run_command_loads_supply_chain_config(self):
        with redirect_stdout(StringIO()) as stdout:
            exit_code = main(["run", "--config", "configs/supply_chain_small.json"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertGreaterEqual(payload["summary"]["environment_tick"], 1)
        self.assertGreaterEqual(payload["summary"]["messages"], 1)
