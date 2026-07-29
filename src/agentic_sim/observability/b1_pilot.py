from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from agentic_sim.observability.artifacts import _backend_metrics, _mean_stdev
from agentic_sim.scheduling.dispatch_policy import DispatchPolicy

EngineFactory = Callable[[], Any]


def _warm_up(engine_factory: EngineFactory, *, warmup_backend_step_count: int, max_ticks: int = 50) -> int:
    """Runs a throwaway engine until warmup_backend_step_count real backend
    calls have completed, per docs/hpc_data_collection_procedures.md's
    count-based warm-up rule. Runs once total, not once per policy/repeat --
    its purpose is server-side readiness (KV-cache, connection warm-up), not
    a workload-specific effect. The warmed-up engine and its state are
    discarded entirely; every timed repetition builds a fresh engine.
    """
    engine = engine_factory()
    backend_steps = 0
    ticks = 0
    while backend_steps < warmup_backend_step_count and ticks < max_ticks:
        engine.run(1)
        backend_steps = _backend_metrics(engine.store.traces.list())["backend_steps"]
        ticks += 1
    return backend_steps


def _run_repetition(engine_factory: EngineFactory, policy: DispatchPolicy, steps_per_repeat: int) -> dict[str, Any]:
    engine = engine_factory()
    engine.dispatch_policy = policy
    engine.run(steps_per_repeat)
    return _backend_metrics(engine.store.traces.list())


def run_b1_pilot(
    *,
    engine_factory: EngineFactory,
    dispatch_policies: dict[str, DispatchPolicy],
    repeats: int = 10,
    steps_per_repeat: int = 5,
    warmup_backend_step_count: int = 20,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Runs a real, repeated dispatch-policy comparison against whatever
    engine `engine_factory` builds -- a real self-hosted backend in the B1
    pilot, a mock backend in tests, with no code difference between the two.

    Unlike scheduler_gate.py::run_scheduler_contribution_gate (which hardcodes
    a simulated backend and hand-built ExecutionRequests, bypassing
    SimulationEngine/scenarios entirely), this drives real SimulationEngine
    runs through a real scenario, so it actually exercises the workload, not
    just the dispatch mechanism in isolation.
    """
    warmup_backend_steps_observed = _warm_up(
        engine_factory, warmup_backend_step_count=warmup_backend_step_count
    )

    excluded: list[dict[str, Any]] = []
    policy_reports: dict[str, Any] = {}

    for policy_name, policy in dispatch_policies.items():
        useful_throughputs: list[float] = []
        latency_avgs: list[float] = []
        raw_reps: list[dict[str, Any]] = []
        for repeat_index in range(repeats):
            try:
                metrics = _run_repetition(engine_factory, policy, steps_per_repeat)
            except Exception as exc:  # noqa: BLE001 - any failing repeat is excluded, not raised
                excluded.append({"policy": policy_name, "repeat": repeat_index, "error": str(exc)})
                continue
            raw_reps.append(metrics)
            if metrics["useful_agent_steps_per_second"] is not None:
                useful_throughputs.append(metrics["useful_agent_steps_per_second"])
            if metrics["latency_seconds"]["avg"] is not None:
                latency_avgs.append(metrics["latency_seconds"]["avg"])

        policy_reports[policy_name] = {
            "repeats_completed": len(raw_reps),
            "raw_repetitions": raw_reps,
            "useful_agent_steps_per_second": _mean_stdev(useful_throughputs),
            "latency_seconds": _mean_stdev(latency_avgs),
        }

    # evaluation_plan.md's two prespecified contrasts ("causal-only versus
    # sequential", "full ... versus causal-only"), plus full-vs-sequential
    # for continuity with this pilot's original 2-policy comparison.
    contrasts = {
        "causal_only_vs_sequential": _relative_contrast(policy_reports, "sequential", "causal_only"),
        "full_vs_causal_only": _relative_contrast(policy_reports, "causal_only", "full"),
        "full_vs_sequential": _relative_contrast(policy_reports, "sequential", "full"),
    }

    payload = {
        "warmup_backend_step_count": warmup_backend_step_count,
        "warmup_backend_steps_observed": warmup_backend_steps_observed,
        "repeats": repeats,
        "steps_per_repeat": steps_per_repeat,
        "policies": policy_reports,
        "excluded": excluded,
        "contrasts": contrasts,
    }

    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def _relative_contrast(policy_reports: dict[str, Any], baseline_name: str, comparison_name: str) -> dict[str, Any]:
    if baseline_name not in policy_reports or comparison_name not in policy_reports:
        return {"applicable": False, "reason": f"requires both {baseline_name!r} and {comparison_name!r} policy keys"}

    baseline = policy_reports[baseline_name]["useful_agent_steps_per_second"]
    comparison = policy_reports[comparison_name]["useful_agent_steps_per_second"]
    if baseline["mean"] is None or comparison["mean"] is None or baseline["mean"] == 0:
        return {"applicable": True, "reason": "insufficient data", "relative_improvement": None}

    relative_improvement = (comparison["mean"] - baseline["mean"]) / baseline["mean"]
    bands_overlap = not (
        (comparison["mean"] - comparison["stdev"]) > (baseline["mean"] + baseline["stdev"])
        or (baseline["mean"] - baseline["stdev"]) > (comparison["mean"] + comparison["stdev"])
    )
    return {
        "applicable": True,
        "relative_improvement": round(relative_improvement, 4),
        "bands_overlap": bands_overlap,
    }
