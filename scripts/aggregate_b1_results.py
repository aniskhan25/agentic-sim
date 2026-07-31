"""
Aggregate every real B1 result file collected this session (docs/baseline/
b1_*.json) into committed, machine-readable summary tables -- closing
evaluation_plan.md's "aggregation... scripts" / "machine-readable result
tables" Required Output for B1 (plotting/figures are a separate, not-yet-built
follow-up).

The manifest below is hand-written and explicit, not inferred from filenames:
the JSON payloads carry no system/workload/placement metadata of their own,
so guessing from filename patterns risked silently mis-tagging a file. Each
line here is a reviewable, verifiable classification.

Usage:
    python3 scripts/aggregate_b1_results.py

Regenerates:
    docs/baseline/b1_summary.csv / .md
    docs/baseline/b1_contrasts_summary.csv / .md
    docs/baseline/b1_retune_sweep_summary.csv / .md
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from agentic_sim.observability.b1_results_summary import summarize_b1_results

_BASELINE_DIR = Path(__file__).resolve().parent.parent / "docs" / "baseline"

# Confirmatory B1 results: single-device (replica_group=None) and full-node
# (replica_group shared by every replica of the same system+workload run).
_MANIFEST: list[dict[str, Any]] = [
    # -- single-device, storm --
    {"file": "b1_pilot_lumi_result.json", "system": "lumi", "workload": "storm",
     "placement": "single_device", "replica_group": None},
    {"file": "b1_pilot_roihu_result.json", "system": "roihu", "workload": "storm",
     "placement": "single_device", "replica_group": None},
    {"file": "b1_study_lumi_storm_result.json", "system": "lumi", "workload": "storm",
     "placement": "single_device", "replica_group": None},
    {"file": "b1_study_roihu_storm_result.json", "system": "roihu", "workload": "storm",
     "placement": "single_device", "replica_group": None},
    # -- single-device, supply_chain --
    {"file": "b1_study_lumi_supply_chain_result.json", "system": "lumi", "workload": "supply_chain",
     "placement": "single_device", "replica_group": None},
    {"file": "b1_study_roihu_supply_chain_result.json", "system": "roihu", "workload": "supply_chain",
     "placement": "single_device", "replica_group": None},
    # -- full-node, storm (LUMI: 8 replicas, Roihu: 4 replicas) --
    *[
        {"file": f"b1_fullnode_lumi_replica{i}_result.json", "system": "lumi", "workload": "storm",
         "placement": "full_node", "replica_group": "lumi|storm"}
        for i in range(8)
    ],
    *[
        {"file": f"b1_fullnode_roihu_replica{i}_result.json", "system": "roihu", "workload": "storm",
         "placement": "full_node", "replica_group": "roihu|storm"}
        for i in range(4)
    ],
    # -- full-node, supply_chain --
    *[
        {"file": f"b1_fullnode_supplychain_lumi_replica{i}_result.json", "system": "lumi",
         "workload": "supply_chain", "placement": "full_node", "replica_group": "lumi|supply_chain"}
        for i in range(8)
    ],
    *[
        {"file": f"b1_fullnode_supplychain_roihu_replica{i}_result.json", "system": "roihu",
         "workload": "supply_chain", "placement": "full_node", "replica_group": "roihu|supply_chain"}
        for i in range(4)
    ],
]

# Exploratory retune sweep: different policy names (queue_aware_2/4/8,
# full_2/4/8) than the standard 7-rung ladder -- kept in its own output,
# not forced into the main manifest/schema.
_RETUNE_SWEEP_FILES = {
    "lumi": "b1_retune_sweep_lumi_result.json",
    "roihu": "b1_retune_sweep_roihu_result.json",
}


def _load_entries() -> list[dict[str, Any]]:
    entries = []
    for item in _MANIFEST:
        path = _BASELINE_DIR / item["file"]
        payload = json.loads(path.read_text())
        entries.append(
            {
                "system": item["system"],
                "workload": item["workload"],
                "placement": item["placement"],
                "replica_group": item["replica_group"],
                "source": item["file"],
                "payload": payload,
            }
        )
    return entries


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


def _round_floats(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rounded = []
    for row in rows:
        rounded.append({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()})
    return rounded


def main() -> int:
    entries = _load_entries()
    summary = summarize_b1_results(entries)
    rows = _round_floats(summary["rows"])
    contrasts = _round_floats(summary["contrasts"])

    _write_csv(_BASELINE_DIR / "b1_summary.csv", rows)
    _write_markdown_table(_BASELINE_DIR / "b1_summary.md", rows, "B1 Results Summary")
    _write_csv(_BASELINE_DIR / "b1_contrasts_summary.csv", contrasts)
    _write_markdown_table(_BASELINE_DIR / "b1_contrasts_summary.md", contrasts, "B1 Contrasts Summary")

    # Retune sweep: its own, separate summary (different policy set).
    sweep_rows = []
    for system, filename in _RETUNE_SWEEP_FILES.items():
        payload = json.loads((_BASELINE_DIR / filename).read_text())
        for policy_name, report in payload["policies"].items():
            stats = report["useful_agent_steps_per_second"]
            sweep_rows.append(
                {
                    "system": system,
                    "policy": policy_name,
                    "mean": stats["mean"],
                    "stdev": stats["stdev"],
                    "count": stats["count"],
                    "source": filename,
                }
            )
    sweep_rows = _round_floats(sweep_rows)
    _write_csv(_BASELINE_DIR / "b1_retune_sweep_summary.csv", sweep_rows)
    _write_markdown_table(_BASELINE_DIR / "b1_retune_sweep_summary.md", sweep_rows, "B1 Retune Sweep Summary")

    print(f"wrote {len(rows)} rows, {len(contrasts)} contrasts, {len(sweep_rows)} sweep rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
