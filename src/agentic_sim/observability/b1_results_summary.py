from __future__ import annotations

import math
from typing import Any

from agentic_sim.observability.b1_pilot import _relative_contrast

# The three prespecified contrasts b1_pilot.py itself computes -- reused
# here so per-device and node-total rows are evaluated identically.
_CONTRAST_PAIRS = (
    ("causal_only_vs_sequential", "sequential", "causal_only"),
    ("full_vs_causal_only", "causal_only", "full"),
    ("full_vs_sequential", "sequential", "full"),
)


def summarize_b1_results(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregates real b1_pilot.py result payloads (docs/baseline/b1_*.json)
    into flat rows + contrasts, honestly distinguishing two measurement
    kinds:

    - "per_device": a single-device run's own mean/stdev, passed through.
    - "node_total": several full-node replicas (same replica_group) summed.
      The summed mean is a real measurement (independent replicas' real
      throughput, added). The summed stdev is not fabricated -- it is
      properly propagated from each replica's own stdev via the standard
      independent-sum variance rule (Var(sum) = sum(Var(x_i))), which is
      what actually justifies treating it as a real error bar rather than
      a guess. per_replica_min/max are also reported as a plain, honest
      consistency check (do replicas roughly agree with each other).

    Each entry: {"system", "workload", "placement", "replica_group" (None
    for single-device), "payload" (parsed b1_pilot.py JSON)}.
    """
    single_device_entries = [e for e in entries if e["replica_group"] is None]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for e in entries:
        if e["replica_group"] is not None:
            grouped.setdefault(e["replica_group"], []).append(e)

    rows: list[dict[str, Any]] = []
    contrasts: list[dict[str, Any]] = []

    for e in single_device_entries:
        policies = e["payload"]["policies"]
        for policy_name, report in policies.items():
            stats = report["useful_agent_steps_per_second"]
            rows.append(
                {
                    "system": e["system"],
                    "workload": e["workload"],
                    "placement": e["placement"],
                    "policy": policy_name,
                    "capacity_type": "per_device",
                    "n_replicas": 1,
                    "mean": stats["mean"],
                    "stdev": stats["stdev"],
                    "count": stats["count"],
                    "per_replica_min": None,
                    "per_replica_max": None,
                    "source": e.get("source"),
                }
            )
        for contrast_name, baseline, comparison in _CONTRAST_PAIRS:
            contrasts.append(
                {
                    "system": e["system"],
                    "workload": e["workload"],
                    "placement": e["placement"],
                    "capacity_type": "per_device",
                    "contrast": contrast_name,
                    **_relative_contrast(policies, baseline, comparison),
                }
            )

    for group_key, group_entries in grouped.items():
        system = group_entries[0]["system"]
        workload = group_entries[0]["workload"]
        placement = group_entries[0]["placement"]
        n_replicas = len(group_entries)

        policy_names: set[str] = set()
        for e in group_entries:
            policy_names.update(e["payload"]["policies"].keys())

        node_total_reports: dict[str, Any] = {}
        for policy_name in sorted(policy_names):
            replica_stats = [
                e["payload"]["policies"][policy_name]["useful_agent_steps_per_second"]
                for e in group_entries
                if policy_name in e["payload"]["policies"]
            ]
            means = [s["mean"] for s in replica_stats if s["mean"] is not None]
            if len(means) != len(group_entries):
                # a replica is missing this policy entirely -- do not
                # silently sum a partial group as if it were the whole node.
                node_total_reports[policy_name] = {"useful_agent_steps_per_second": {"mean": None, "stdev": None}}
                rows.append(
                    {
                        "system": system,
                        "workload": workload,
                        "placement": placement,
                        "policy": policy_name,
                        "capacity_type": "node_total",
                        "n_replicas": n_replicas,
                        "mean": None,
                        "stdev": None,
                        "count": len(means),
                        "per_replica_min": None,
                        "per_replica_max": None,
                        "source": group_key,
                    }
                )
                continue

            variances = [s["stdev"] ** 2 for s in replica_stats]
            summed_mean = sum(means)
            summed_stdev = math.sqrt(sum(variances))
            node_total_reports[policy_name] = {
                "useful_agent_steps_per_second": {"mean": summed_mean, "stdev": summed_stdev}
            }
            rows.append(
                {
                    "system": system,
                    "workload": workload,
                    "placement": placement,
                    "policy": policy_name,
                    "capacity_type": "node_total",
                    "n_replicas": n_replicas,
                    "mean": summed_mean,
                    "stdev": summed_stdev,
                    "count": len(means),
                    "per_replica_min": min(means),
                    "per_replica_max": max(means),
                    "source": group_key,
                }
            )

        for contrast_name, baseline, comparison in _CONTRAST_PAIRS:
            contrasts.append(
                {
                    "system": system,
                    "workload": workload,
                    "placement": placement,
                    "capacity_type": "node_total",
                    "contrast": contrast_name,
                    **_relative_contrast(node_total_reports, baseline, comparison),
                }
            )

    return {"rows": rows, "contrasts": contrasts}
