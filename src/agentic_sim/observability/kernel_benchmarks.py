from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

from agentic_sim.observability.causal_verifier import verify
from agentic_sim.observability.kernel_invariants import graph_metrics
from agentic_sim.scenarios.synthetic import (
    create_synthetic_engine,
    expected_invariants,
    step_count_for,
)

KERNEL_SHAPES: list[tuple[str, dict[str, Any]]] = [
    ("chain", {"length": 4}),
    ("fan_out", {"width": 3}),
    ("fork_join", {"width": 3}),
    ("independent_branches", {"branch_count": 3, "length": 3}),
    ("mixed_dag", {"length": 3}),
    ("conflicting_write", {"writers": 3}),
]


def run_kernel_benchmarks(
    shapes: list[tuple[str, dict[str, Any]]] = KERNEL_SHAPES,
    repeats: int = 5,
    output_path: str | Path | None = "docs/baseline/component_benchmarks.json",
) -> dict[str, Any]:
    """Run each synthetic kernel shape `repeats` times, using every run as both
    a correctness gate (zero causal violations, graph metrics matching the
    shape's hand-derived invariants) and a component-level timing sample.

    Raises AssertionError if any run fails either gate -- this harness is a
    gate, not just a timing collector, so a broken kernel must not silently
    produce a benchmarks artifact.
    """
    shape_reports = []
    for shape, params in shapes:
        steps = step_count_for(shape, params)
        expected = expected_invariants(shape, params)
        timing_samples: dict[str, list[float]] = {}

        for _ in range(repeats):
            engine = create_synthetic_engine(scenario_parameters={"shape": shape, **params})
            engine.run(steps)
            traces = engine.store.traces.list()

            verification = verify(traces)
            if verification.violations:
                raise AssertionError(
                    f"synthetic kernel shape {shape!r} produced causal violations: "
                    f"{verification.violations}"
                )
            metrics = graph_metrics(traces)
            if metrics != expected:
                raise AssertionError(
                    f"synthetic kernel shape {shape!r} graph metrics {metrics} != "
                    f"expected {expected}"
                )

            for trace in traces:
                if trace.event_name == "simulation_tick":
                    for key, value in trace.payload["timing_ms"].items():
                        timing_samples.setdefault(key, []).append(value)

        shape_reports.append(
            {
                "shape": shape,
                "params": params,
                "steps": steps,
                "repeats": repeats,
                "graph_metrics": expected,
                "timing_ms": {key: _min_mean_max(values) for key, values in timing_samples.items()},
            }
        )

    payload = {"shapes": shape_reports}
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def _min_mean_max(values: list[float]) -> dict[str, float]:
    return {
        "count": len(values),
        "min": round(min(values), 3),
        "mean": round(statistics.mean(values), 3),
        "max": round(max(values), 3),
    }
