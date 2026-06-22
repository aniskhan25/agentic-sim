"""Sweep matrix generation for SLURM array runs.

A sweep spec is a JSON file with either an `axes` dict (cross-product) or an
explicit `matrix` list, plus a `base` config path and optional `fixed` overrides.

Supported flat override keys
-----------------------------
steps            → config top-level "steps"
agent_replicas   → config "scenario.agent_replicas"
backend          → config "execution.backend"
max_batch_size   → config "execution.max_batch_size"
max_events_per_tick → config "scheduler.max_events_per_tick"
storage_mode     → config "storage.mode"
fixture          → config "scenario.parameters.fixture"
scenario         → replaces the entire "scenario" field

Axes example (cross-product)::

    {
      "base": "configs/storm_small.json",
      "axes": {"steps": [4, 8], "agent_replicas": [1, 4]},
      "fixed": {"storage_mode": "sqlite"}
    }

Matrix example (explicit combinations)::

    {
      "base": "configs/supply_chain_small.json",
      "matrix": [
        {"steps": 6, "fixture": "data/fixtures/supply_chain_nordic.json"},
        {"steps": 4}
      ]
    }
"""
from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path
from typing import Any

from agentic_sim.utils.ids import new_id
from agentic_sim.utils.time import to_iso, utc_now

SUPPORTED_KEYS: frozenset[str] = frozenset(
    {
        "steps",
        "agent_replicas",
        "backend",
        "max_batch_size",
        "max_events_per_tick",
        "storage_mode",
        "fixture",
        "scenario",
    }
)


def load_sweep_spec(path: str | Path) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"Sweep spec must be a JSON object: {path}")
    if "base" not in raw:
        raise ValueError(f"Sweep spec missing required 'base' key: {path}")
    has_axes = "axes" in raw
    has_matrix = "matrix" in raw
    if has_axes and has_matrix:
        raise ValueError(f"Sweep spec must define 'axes' or 'matrix', not both: {path}")
    if not has_axes and not has_matrix:
        raise ValueError(f"Sweep spec must define either 'axes' or 'matrix': {path}")
    return raw


def sweep_combinations(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the list of override dicts, one per run."""
    if "matrix" in spec:
        return [dict(entry) for entry in spec["matrix"]]
    axes = spec["axes"]
    keys = list(axes.keys())
    values = [v if isinstance(v, list) else [v] for v in axes.values()]
    return [dict(zip(keys, combo)) for combo in itertools.product(*values)]


def apply_override(config: dict[str, Any], key: str, value: Any) -> None:
    """Apply one flat override key to a raw config dict in-place."""
    if key not in SUPPORTED_KEYS:
        raise ValueError(
            f"Unknown sweep override key: {key!r}. "
            f"Supported keys: {', '.join(sorted(SUPPORTED_KEYS))}"
        )
    if key == "steps":
        config["steps"] = value
    elif key == "agent_replicas":
        scenario = config.get("scenario", "storm")
        if isinstance(scenario, str):
            config["scenario"] = {"name": scenario, "agent_replicas": int(value)}
        else:
            config.setdefault("scenario", {})["agent_replicas"] = int(value)
    elif key == "backend":
        config.setdefault("execution", {})["backend"] = str(value)
    elif key == "max_batch_size":
        config.setdefault("execution", {})["max_batch_size"] = int(value)
    elif key == "max_events_per_tick":
        config.setdefault("scheduler", {})["max_events_per_tick"] = int(value)
    elif key == "storage_mode":
        config.setdefault("storage", {})["mode"] = str(value)
    elif key == "fixture":
        scenario = config.get("scenario", "storm")
        if isinstance(scenario, str):
            config["scenario"] = {"name": scenario, "parameters": {"fixture": str(value)}}
        else:
            s = dict(config["scenario"])
            s.setdefault("parameters", {})["fixture"] = str(value)
            config["scenario"] = s
    elif key == "scenario":
        config["scenario"] = value


def _entry_label(overrides: dict[str, Any]) -> str:
    short = {
        "steps": "steps",
        "agent_replicas": "replicas",
        "backend": "backend",
        "max_batch_size": "batch",
        "max_events_per_tick": "evts",
        "storage_mode": "storage",
        "fixture": "fixture",
        "scenario": "scenario",
    }
    parts = []
    for k, v in overrides.items():
        label_v = Path(str(v)).stem if k == "fixture" else str(v)
        parts.append(f"{short.get(k, k)}-{label_v}")
    return "_".join(parts) if parts else "default"


def generate_sweep(
    spec_path: str | Path,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Generate one config file per sweep combination and write a manifest.

    Returns the manifest dict (also written to output_dir/sweep_manifest.json).
    """
    spec_path = Path(spec_path)
    spec = load_sweep_spec(spec_path)
    base_config = json.loads(Path(spec["base"]).read_text())
    fixed: dict[str, Any] = spec.get("fixed", {})
    combinations = sweep_combinations(spec)

    sweep_id = new_id("swp")
    if output_dir is None:
        output_dir = Path("data") / "sweeps" / sweep_id
    output_dir = Path(output_dir)
    configs_dir = output_dir / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)

    generated: list[str] = []
    for idx, overrides in enumerate(combinations):
        config = copy.deepcopy(base_config)
        # Fixed first so per-entry overrides take precedence
        for k, v in {**fixed, **overrides}.items():
            apply_override(config, k, v)
        label = _entry_label(overrides)
        config_path = configs_dir / f"{idx:02d}_{label}.json"
        config_path.write_text(json.dumps(config, indent=2) + "\n")
        generated.append(str(config_path))

    manifest: dict[str, Any] = {
        "sweep_id": sweep_id,
        "created_at": to_iso(utc_now()),
        "spec_path": str(spec_path),
        "base": spec["base"],
        "total": len(generated),
        "configs": generated,
    }
    (output_dir / "sweep_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
