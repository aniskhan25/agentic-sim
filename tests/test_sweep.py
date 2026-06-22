import json
import tempfile
import unittest
from pathlib import Path

from agentic_sim.config import load_config
from agentic_sim.sweep import (
    SUPPORTED_KEYS,
    apply_override,
    generate_sweep,
    load_sweep_spec,
    sweep_combinations,
)


def _base_config() -> dict:
    return {
        "scenario": "storm",
        "steps": 4,
        "scheduler": {"policy": "fifo"},
        "execution": {"backend": "mock", "max_batch_size": 4},
        "storage": {"mode": "memory"},
    }


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data))


class LoadSweepSpecTests(unittest.TestCase):
    def test_raises_when_base_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "spec.json"
            _write_json(p, {"axes": {"steps": [4]}})
            with self.assertRaises(ValueError, msg="base"):
                load_sweep_spec(p)

    def test_raises_when_both_axes_and_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "spec.json"
            _write_json(p, {"base": "x.json", "axes": {}, "matrix": []})
            with self.assertRaises(ValueError):
                load_sweep_spec(p)

    def test_raises_when_neither_axes_nor_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "spec.json"
            _write_json(p, {"base": "x.json"})
            with self.assertRaises(ValueError):
                load_sweep_spec(p)

    def test_loads_valid_axes_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "spec.json"
            _write_json(p, {"base": "x.json", "axes": {"steps": [4, 8]}})
            spec = load_sweep_spec(p)
        self.assertEqual(spec["axes"]["steps"], [4, 8])


class SweepCombinationsTests(unittest.TestCase):
    def test_axes_generates_cross_product(self):
        spec = {"axes": {"steps": [4, 8], "agent_replicas": [1, 4]}}
        combos = sweep_combinations(spec)
        self.assertEqual(len(combos), 4)
        self.assertIn({"steps": 4, "agent_replicas": 1}, combos)
        self.assertIn({"steps": 8, "agent_replicas": 4}, combos)

    def test_matrix_returns_explicit_entries(self):
        spec = {"matrix": [{"steps": 4}, {"steps": 8, "agent_replicas": 4}]}
        combos = sweep_combinations(spec)
        self.assertEqual(len(combos), 2)
        self.assertEqual(combos[0], {"steps": 4})
        self.assertEqual(combos[1], {"steps": 8, "agent_replicas": 4})

    def test_single_value_axis_is_treated_as_list(self):
        spec = {"axes": {"steps": 4}}
        combos = sweep_combinations(spec)
        self.assertEqual(len(combos), 1)
        self.assertEqual(combos[0]["steps"], 4)


class ApplyOverrideTests(unittest.TestCase):
    def test_steps(self):
        cfg = _base_config()
        apply_override(cfg, "steps", 16)
        self.assertEqual(cfg["steps"], 16)

    def test_backend(self):
        cfg = _base_config()
        apply_override(cfg, "backend", "rule")
        self.assertEqual(cfg["execution"]["backend"], "rule")

    def test_max_batch_size(self):
        cfg = _base_config()
        apply_override(cfg, "max_batch_size", 32)
        self.assertEqual(cfg["execution"]["max_batch_size"], 32)

    def test_max_events_per_tick(self):
        cfg = _base_config()
        apply_override(cfg, "max_events_per_tick", 128)
        self.assertEqual(cfg["scheduler"]["max_events_per_tick"], 128)

    def test_storage_mode(self):
        cfg = _base_config()
        apply_override(cfg, "storage_mode", "sqlite")
        self.assertEqual(cfg["storage"]["mode"], "sqlite")

    def test_agent_replicas_on_string_scenario(self):
        cfg = _base_config()
        apply_override(cfg, "agent_replicas", 8)
        self.assertEqual(cfg["scenario"]["agent_replicas"], 8)
        self.assertEqual(cfg["scenario"]["name"], "storm")

    def test_agent_replicas_on_dict_scenario(self):
        cfg = _base_config()
        cfg["scenario"] = {"name": "storm", "agent_replicas": 1}
        apply_override(cfg, "agent_replicas", 16)
        self.assertEqual(cfg["scenario"]["agent_replicas"], 16)

    def test_fixture_on_string_scenario(self):
        cfg = _base_config()
        apply_override(cfg, "fixture", "data/fixtures/storm_helsinki_oulu.json")
        self.assertEqual(
            cfg["scenario"]["parameters"]["fixture"],
            "data/fixtures/storm_helsinki_oulu.json",
        )
        self.assertEqual(cfg["scenario"]["name"], "storm")

    def test_fixture_on_dict_scenario(self):
        cfg = _base_config()
        cfg["scenario"] = {"name": "storm", "parameters": {"regions": ["helsinki"]}}
        apply_override(cfg, "fixture", "data/fixtures/storm_helsinki_oulu.json")
        self.assertEqual(
            cfg["scenario"]["parameters"]["fixture"],
            "data/fixtures/storm_helsinki_oulu.json",
        )
        # Existing parameters preserved
        self.assertEqual(cfg["scenario"]["parameters"]["regions"], ["helsinki"])

    def test_scenario_replace(self):
        cfg = _base_config()
        apply_override(cfg, "scenario", "supply_chain")
        self.assertEqual(cfg["scenario"], "supply_chain")

    def test_unknown_key_raises(self):
        cfg = _base_config()
        with self.assertRaises(ValueError):
            apply_override(cfg, "unknown_key", 1)


class GenerateSweepTests(unittest.TestCase):
    def _make_base(self, tmp: str) -> Path:
        base = Path(tmp) / "base.json"
        _write_json(base, _base_config())
        return base

    def test_axes_generates_correct_number_of_configs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self._make_base(tmp)
            spec = Path(tmp) / "spec.json"
            _write_json(spec, {
                "base": str(base),
                "axes": {"steps": [4, 8], "agent_replicas": [1, 4]},
            })
            out = Path(tmp) / "out"
            manifest = generate_sweep(spec, output_dir=out)
        self.assertEqual(manifest["total"], 4)
        self.assertEqual(len(manifest["configs"]), 4)

    def test_matrix_generates_correct_number_of_configs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self._make_base(tmp)
            spec = Path(tmp) / "spec.json"
            _write_json(spec, {
                "base": str(base),
                "matrix": [{"steps": 4}, {"steps": 8}, {"steps": 16}],
            })
            out = Path(tmp) / "out"
            manifest = generate_sweep(spec, output_dir=out)
        self.assertEqual(manifest["total"], 3)

    def test_fixed_overrides_applied_to_all_configs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self._make_base(tmp)
            spec = Path(tmp) / "spec.json"
            _write_json(spec, {
                "base": str(base),
                "axes": {"steps": [4, 8]},
                "fixed": {"storage_mode": "sqlite"},
            })
            out = Path(tmp) / "out"
            manifest = generate_sweep(spec, output_dir=out)
            for config_path in manifest["configs"]:
                cfg = json.loads(Path(config_path).read_text())
                self.assertEqual(cfg["storage"]["mode"], "sqlite")

    def test_entry_overrides_take_precedence_over_fixed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self._make_base(tmp)
            spec = Path(tmp) / "spec.json"
            _write_json(spec, {
                "base": str(base),
                "matrix": [{"steps": 8}],
                "fixed": {"steps": 4},
            })
            out = Path(tmp) / "out"
            manifest = generate_sweep(spec, output_dir=out)
            cfg = json.loads(Path(manifest["configs"][0]).read_text())
            self.assertEqual(cfg["steps"], 8)

    def test_manifest_written_to_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self._make_base(tmp)
            spec = Path(tmp) / "spec.json"
            _write_json(spec, {"base": str(base), "axes": {"steps": [4]}})
            out = Path(tmp) / "out"
            generate_sweep(spec, output_dir=out)
            self.assertTrue((out / "sweep_manifest.json").exists())

    def test_generated_configs_are_loadable_by_load_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self._make_base(tmp)
            spec = Path(tmp) / "spec.json"
            _write_json(spec, {
                "base": str(base),
                "axes": {"steps": [4, 8], "agent_replicas": [1, 2]},
                "fixed": {"storage_mode": "sqlite"},
            })
            out = Path(tmp) / "out"
            manifest = generate_sweep(spec, output_dir=out)
            for config_path in manifest["configs"]:
                cfg = load_config(config_path)
                self.assertIn(cfg.steps, [4, 8])
                self.assertIn(cfg.agent_replicas, [1, 2])
                self.assertEqual(cfg.storage_mode, "sqlite")

    def test_config_filenames_contain_override_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self._make_base(tmp)
            spec = Path(tmp) / "spec.json"
            _write_json(spec, {"base": str(base), "axes": {"steps": [16]}})
            out = Path(tmp) / "out"
            manifest = generate_sweep(spec, output_dir=out)
        self.assertIn("16", Path(manifest["configs"][0]).name)
