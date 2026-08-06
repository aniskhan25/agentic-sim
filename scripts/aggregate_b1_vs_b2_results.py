"""
Compare B1 (common-denominator) vs. B2 (platform-tuned) real confirmatory
results (roadmap item 19) -- the first real "does platform-tuning actually
help" evidence, now that both `docs/b1_frozen_configuration.md` and
`docs/b2_frozen_configuration.md` exist. `causal_only` policy only (isolating
the serving-config effect from the already-settled policy-ladder question),
`storm` + `supply_chain`, single-device -- see the approved plan for the full
scope statement.

Three variants are aggregated:
- 10 reps: the original confirmatory run -- found no statistically
  distinguishable difference anywhere.
- 30 reps: a follow-up rerun testing whether that was a real null result or
  just noise too large at n=10 to resolve -- confirmed it was real: every
  comparison converges to a small, non-significant difference at n=30.
- "highconcurrency": both null results turned out to be explained by the
  experiment never generating enough real concurrent backend load to
  stress either config's --max-num-seqs cap (32 for B2, 64 for B1) --
  confirmed by direct code reading (see the approved plan for the full
  three-layer explanation: default agent_replicas=1, SimulationEngine's
  max_events_per_tick=32 cap, and CausalOnlyDispatchPolicy's own
  max_workers=8 ThreadPoolExecutor, all compounding). Rerun with
  --agent-replicas/--max-events-per-tick/--dispatch-max-workers raised well
  above both caps (~58-78 real concurrent requests/tick, confirmed via
  backend_steps) reveals a real, mechanistically-explained effect: B2 is
  slower than B1 under genuine load (higher per-request latency from more
  queueing against its smaller cap), non-overlapping on 2 of 4 (system,
  workload) pairs at only 5 reps (exploratory scale).

Reuses `agentic_sim.observability.b1_pilot._relative_contrast` unmodified --
the exact same relative-improvement/bands-overlap math already used for
every other contrast this session, applied here to two serving configs
instead of two dispatch policies. Note the sign convention: baseline="b1",
comparison="b2", so a negative relative_improvement means B2 is slower.

The manifests below are hand-written and explicit, matching
`scripts/aggregate_b1_results.py`'s own precedent -- the JSON payloads carry
no system/workload/config metadata of their own.

Usage:
    python3 scripts/aggregate_b1_vs_b2_results.py

Regenerates:
    docs/baseline/b1_vs_b2_comparison.csv / .md (10 reps)
    docs/baseline/b1_vs_b2_comparison_30rep.csv / .md (30 reps)
    docs/baseline/b1_vs_b2_comparison_highconcurrency.csv / .md (5 reps, real concurrent load)
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from agentic_sim.observability.b1_pilot import _relative_contrast

_BASELINE_DIR = Path(__file__).resolve().parent.parent / "docs" / "baseline"


def _manifest_10rep() -> list[dict[str, str]]:
    return [
        {"system": "lumi", "workload": "storm",
         "b1_file": "b1_vs_b2_lumi_b1_storm_result.json", "b2_file": "b1_vs_b2_lumi_b2_storm_result.json"},
        {"system": "lumi", "workload": "supply_chain",
         "b1_file": "b1_vs_b2_lumi_b1_supply_chain_result.json", "b2_file": "b1_vs_b2_lumi_b2_supply_chain_result.json"},
        {"system": "roihu", "workload": "storm",
         "b1_file": "b1_vs_b2_roihu_b1_storm_result.json", "b2_file": "b1_vs_b2_roihu_b2_storm_result.json"},
        {"system": "roihu", "workload": "supply_chain",
         "b1_file": "b1_vs_b2_roihu_b1_supply_chain_result.json", "b2_file": "b1_vs_b2_roihu_b2_supply_chain_result.json"},
    ]


def _manifest_30rep() -> list[dict[str, str]]:
    return [
        {"system": item["system"], "workload": item["workload"],
         "b1_file": item["b1_file"].replace("_result.json", "_30rep_result.json"),
         "b2_file": item["b2_file"].replace("_result.json", "_30rep_result.json")}
        for item in _manifest_10rep()
    ]


def _manifest_highconcurrency() -> list[dict[str, str]]:
    return [
        {"system": item["system"], "workload": item["workload"],
         "b1_file": f"b1_vs_b2_highconcurrency_{item['system']}_b1_{item['workload']}_result.json",
         "b2_file": f"b1_vs_b2_highconcurrency_{item['system']}_b2_{item['workload']}_result.json"}
        for item in _manifest_10rep()
    ]


def _load_causal_only(filename: str) -> dict[str, Any]:
    payload = json.loads((_BASELINE_DIR / filename).read_text())
    return payload["policies"]["causal_only"]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown_table(path: Path, rows: list[dict[str, Any]], title: str) -> None:
    if not rows:
        path.write_text(f"# {title}\n\nNo rows.\n")
        return
    fieldnames = list(rows[0].keys())
    lines = [f"# {title}", "", "| " + " | ".join(fieldnames) + " |", "| " + " | ".join("---" for _ in fieldnames) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row[f]) for f in fieldnames) + " |")
    path.write_text("\n".join(lines) + "\n")


def _round(value: Any) -> Any:
    return round(value, 4) if isinstance(value, float) else value


def _build_rows(manifest: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in manifest:
        b1_report = _load_causal_only(item["b1_file"])
        b2_report = _load_causal_only(item["b2_file"])
        synthetic = {"b1": b1_report, "b2": b2_report}
        contrast = _relative_contrast(synthetic, "b1", "b2")
        b1_stats = b1_report["useful_agent_steps_per_second"]
        b2_stats = b2_report["useful_agent_steps_per_second"]
        rows.append(
            {
                "system": item["system"],
                "workload": item["workload"],
                "b1_mean": _round(b1_stats["mean"]),
                "b1_stdev": _round(b1_stats["stdev"]),
                "b1_count": b1_stats["count"],
                "b2_mean": _round(b2_stats["mean"]),
                "b2_stdev": _round(b2_stats["stdev"]),
                "b2_count": b2_stats["count"],
                "relative_improvement": _round(contrast.get("relative_improvement")),
                "bands_overlap": contrast.get("bands_overlap"),
            }
        )
    return rows


def main() -> int:
    rows_10rep = _build_rows(_manifest_10rep())
    _write_csv(_BASELINE_DIR / "b1_vs_b2_comparison.csv", rows_10rep)
    _write_markdown_table(_BASELINE_DIR / "b1_vs_b2_comparison.md", rows_10rep, "B1 vs. B2 Comparison (causal_only, 10 reps)")

    rows_30rep = _build_rows(_manifest_30rep())
    _write_csv(_BASELINE_DIR / "b1_vs_b2_comparison_30rep.csv", rows_30rep)
    _write_markdown_table(
        _BASELINE_DIR / "b1_vs_b2_comparison_30rep.md", rows_30rep, "B1 vs. B2 Comparison (causal_only, 30 reps)"
    )

    rows_highconcurrency = _build_rows(_manifest_highconcurrency())
    _write_csv(_BASELINE_DIR / "b1_vs_b2_comparison_highconcurrency.csv", rows_highconcurrency)
    _write_markdown_table(
        _BASELINE_DIR / "b1_vs_b2_comparison_highconcurrency.md", rows_highconcurrency,
        "B1 vs. B2 Comparison (causal_only, 5 reps, real concurrent load: ~58-78 requests/tick)",
    )

    print(
        f"wrote {len(rows_10rep)} 10-rep rows, {len(rows_30rep)} 30-rep rows, "
        f"{len(rows_highconcurrency)} highconcurrency rows"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
