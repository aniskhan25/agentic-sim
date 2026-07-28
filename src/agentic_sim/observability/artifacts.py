from __future__ import annotations

import json
import platform
import statistics
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

from agentic_sim.config import RuntimeConfig
from agentic_sim.models import SimulationTickResult
from agentic_sim.observability.summaries import RunSummary
from agentic_sim.state.base import RuntimeStore
from agentic_sim.utils.ids import new_id
from agentic_sim.utils.serialization import to_jsonable
from agentic_sim.utils.time import to_iso, utc_now


def write_run_artifacts(
    output_dir: str | Path,
    *,
    config: RuntimeConfig,
    tick_results: list[SimulationTickResult],
    summary: RunSummary,
    store: RuntimeStore,
) -> dict[str, Any]:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)

    traces = store.traces.list()
    metadata = build_run_metadata(config=config, store=store)
    files = {
        "metadata": path / "metadata.json",
        "config": path / "config.json",
        "summary": path / "summary.json",
        "ticks": path / "ticks.json",
        "environment": path / "environment.json",
        "traces": path / "traces.json",
        "backend_metrics": path / "backend_metrics.json",
    }
    _write_json(files["metadata"], metadata)
    _write_json(files["config"], _config_snapshot(config))
    _write_json(files["summary"], to_jsonable(asdict(summary)))
    _write_json(files["ticks"], [to_jsonable(result) for result in tick_results])
    _write_json(files["environment"], to_jsonable(store.environment.get()))
    _write_json(files["traces"], [to_jsonable(trace) for trace in traces])
    _write_json(files["backend_metrics"], _backend_metrics(traces))
    return {"run_id": metadata["run_id"], "output_dir": str(path)}


def aggregate_run_artifacts(root_dir: str | Path, output_path: str | Path | None = None) -> dict[str, Any]:
    root = Path(root_dir)
    runs = []
    for metadata_path in sorted(root.glob("**/metadata.json")):
        run_dir = metadata_path.parent
        runs.append(
            {
                "run_dir": str(run_dir),
                "metadata": _read_json(metadata_path),
                "summary": _read_optional_json(run_dir / "summary.json"),
                "backend_metrics": _read_optional_json(run_dir / "backend_metrics.json"),
            }
        )
    payload = {"root_dir": str(root), "runs": runs, "run_count": len(runs)}
    if output_path is not None:
        _write_json(Path(output_path), payload)
    return payload


def aggregate_run_stats(root_dir: str | Path, output_path: str | Path | None = None) -> dict[str, Any]:
    """Group runs by config (minus seed) and compute mean/stdev of key metrics across repeats.

    Grouping is done on config.json rather than metadata.json because config.json carries
    scenario_parameters (e.g. fixture) and backend_options (e.g. aitta_model) in full, so
    runs with a different model or fixture never land in the same group.
    """
    root = Path(root_dir)
    groups: dict[str, list[dict[str, Any]]] = {}
    for config_path in sorted(root.glob("**/config.json")):
        run_dir = config_path.parent
        config_snapshot = _read_json(config_path)
        seed = config_snapshot.pop("seed", None)
        key = json.dumps(config_snapshot, sort_keys=True)
        groups.setdefault(key, []).append(
            {
                "seed": seed,
                "run_dir": str(run_dir),
                "backend_metrics": _read_optional_json(run_dir / "backend_metrics.json") or {},
            }
        )

    def rate_stats(runs: list[dict[str, Any]], numerator_key: str) -> dict[str, Any]:
        rates = [
            run["backend_metrics"].get(numerator_key, 0) / run["backend_metrics"]["backend_steps"]
            for run in runs
            if run["backend_metrics"].get("backend_steps", 0) > 0
        ]
        return _mean_stdev(rates)

    stats_groups = []
    for key, runs in groups.items():
        latency_means = [
            run["backend_metrics"].get("latency_seconds", {}).get("avg")
            for run in runs
            if run["backend_metrics"].get("latency_seconds", {}).get("avg") is not None
        ]
        autonomy_means = [
            run["backend_metrics"].get("autonomy_rate", {}).get("avg")
            for run in runs
            if run["backend_metrics"].get("autonomy_rate", {}).get("avg") is not None
        ]
        useful_throughputs = [
            run["backend_metrics"].get("useful_agent_steps_per_second")
            for run in runs
            if run["backend_metrics"].get("useful_agent_steps_per_second") is not None
        ]
        stats_groups.append(
            {
                "group_key": key,
                "run_count": len(runs),
                "seeds": sorted((run["seed"] for run in runs), key=lambda s: (s is None, s)),
                "invalid_model_output_rate": rate_stats(runs, "invalid_model_outputs"),
                "policy_guard_added_message_rate": rate_stats(runs, "policy_guard_added_messages"),
                "policy_guard_added_action_rate": rate_stats(runs, "policy_guard_added_actions"),
                "must_not_violation_rate": rate_stats(runs, "must_not_violations"),
                "semantic_valid_rate": rate_stats(runs, "semantic_valid_count"),
                "latency_seconds_mean": _mean_stdev(latency_means),
                "autonomy_rate_mean": _mean_stdev(autonomy_means),
                "useful_agent_steps_per_second_mean": _mean_stdev(useful_throughputs),
                "runs": [run["run_dir"] for run in runs],
            }
        )

    payload = {"root_dir": str(root), "groups": stats_groups, "group_count": len(stats_groups)}
    if output_path is not None:
        _write_json(Path(output_path), payload)
    return payload


def _mean_stdev(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "mean": None, "stdev": None}
    return {
        "count": len(values),
        "mean": round(statistics.mean(values), 6),
        "stdev": round(statistics.stdev(values), 6) if len(values) > 1 else 0.0,
    }


def build_run_metadata(*, config: RuntimeConfig, store: RuntimeStore) -> dict[str, Any]:
    traces = store.traces.list()
    return {
        "run_id": new_id("run"),
        "created_at": to_iso(utc_now()),
        "scenario": config.scenario,
        "backend": config.backend,
        "steps": config.steps,
        "storage_mode": config.storage_mode,
        "sqlite_path": config.sqlite_path,
        "agent_replicas": config.agent_replicas,
        "max_batch_size": config.max_batch_size,
        "max_events_per_tick": config.max_events_per_tick,
        "seed": config.seed,
        "git_commit": _git_commit(),
        "python_version": platform.python_version(),
        "backend_metrics": _backend_metrics(traces),
    }


def _config_snapshot(config: RuntimeConfig) -> dict[str, Any]:
    snapshot = to_jsonable(asdict(config))
    snapshot["backend_options"] = {
        key: value
        for key, value in snapshot.get("backend_options", {}).items()
        if key != "aitta_api_key"
    }
    return snapshot


def _backend_metrics(traces: list[Any]) -> dict[str, Any]:
    latencies = []
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    invalid_outputs = 0
    guard_added_messages = 0
    guard_added_actions = 0
    json_repair_attempts = 0
    must_not_violations = 0
    semantic_valid_count = 0
    useful_steps = 0
    autonomy_rates: list[float] = []
    backend_steps = 0
    backend_execution_wall_seconds = 0.0

    for trace in traces:
        if trace.event_name == "simulation_tick":
            timing = trace.payload.get("timing_ms") or {}
            backend_ms = timing.get("backend_execution_ms")
            if isinstance(backend_ms, (int, float)):
                backend_execution_wall_seconds += float(backend_ms) / 1000.0
            continue
        if trace.event_name != "agent_step":
            continue
        metadata = trace.payload.get("metadata", {})
        if not metadata:
            continue
        backend_steps += 1
        latency = metadata.get("latency_seconds")
        if isinstance(latency, (int, float)):
            latencies.append(float(latency))
        step_usage = metadata.get("usage") or {}
        for key in usage:
            usage[key] += int(step_usage.get(key, 0) or 0)
        invalid_outputs += int(bool(metadata.get("model_output_invalid")))
        guard_added_messages += int(metadata.get("policy_guard_added_messages", 0) or 0)
        guard_added_actions += int(metadata.get("policy_guard_added_actions", 0) or 0)
        json_repair_attempts += int(metadata.get("json_repair_attempts", 0) or 0)
        must_not_violations += int(metadata.get("must_not_violations", 0) or 0)
        if metadata.get("semantic_valid"):
            semantic_valid_count += 1
        if metadata.get("useful_step"):
            useful_steps += 1
        autonomy_rate = metadata.get("autonomy_rate")
        if isinstance(autonomy_rate, (int, float)):
            autonomy_rates.append(float(autonomy_rate))

    useful_agent_steps_per_second = (
        round(useful_steps / backend_execution_wall_seconds, 6)
        if backend_execution_wall_seconds > 0
        else None
    )

    return {
        "backend_steps": backend_steps,
        "latency_seconds": {
            "count": len(latencies),
            "min": min(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
            "avg": round(sum(latencies) / len(latencies), 3) if latencies else None,
        },
        "usage": usage,
        "invalid_model_outputs": invalid_outputs,
        "policy_guard_added_messages": guard_added_messages,
        "policy_guard_added_actions": guard_added_actions,
        "json_repair_attempts": json_repair_attempts,
        "must_not_violations": must_not_violations,
        "semantic_valid_count": semantic_valid_count,
        "autonomy_rate": {
            "count": len(autonomy_rates),
            "min": min(autonomy_rates) if autonomy_rates else None,
            "max": max(autonomy_rates) if autonomy_rates else None,
            "avg": round(sum(autonomy_rates) / len(autonomy_rates), 6) if autonomy_rates else None,
        },
        "useful_steps": useful_steps,
        "backend_execution_wall_seconds": round(backend_execution_wall_seconds, 6),
        "useful_agent_steps_per_second": useful_agent_steps_per_second,
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return _read_json(path)


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None
