from __future__ import annotations

import json
import platform
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
    backend_steps = 0

    for trace in traces:
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
