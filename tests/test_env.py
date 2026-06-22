import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentic_sim.utils.env import load_env_files


class EnvTests(unittest.TestCase):
    def test_load_env_files_sets_missing_values(self):
        with TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env.local"
            env_path.write_text(
                """
                # local settings
                AITTA_BASE_URL="https://aitta.example/openai/v1/"
                AITTA_MODEL=demo/model
                """
            )

            old_base_url = os.environ.pop("AITTA_BASE_URL", None)
            old_model = os.environ.pop("AITTA_MODEL", None)
            try:
                load_env_files([env_path])

                self.assertEqual(os.environ["AITTA_BASE_URL"], "https://aitta.example/openai/v1/")
                self.assertEqual(os.environ["AITTA_MODEL"], "demo/model")
            finally:
                os.environ.pop("AITTA_BASE_URL", None)
                os.environ.pop("AITTA_MODEL", None)
                if old_base_url is not None:
                    os.environ["AITTA_BASE_URL"] = old_base_url
                if old_model is not None:
                    os.environ["AITTA_MODEL"] = old_model
