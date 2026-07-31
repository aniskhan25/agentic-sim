from __future__ import annotations

from typing import Any


def select_best_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Implements docs/hpc_data_collection_procedures.md's frozen B2
    (platform-tuned) selection rule for one swept dimension's candidates:

    - Primary metric: useful agent-steps/sec.
    - Hard disqualifier: any candidate with had_preemption=True is dropped
      outright, regardless of raw throughput -- never merely penalized.
    - Tie-break: if the best candidate's mean+-1stdev band overlaps another
      eligible candidate's, they're statistically indistinguishable and the
      simpler/lower-resource one wins. The frozen rule's literal wording
      ("prefer lower --gpu-memory-utilization, then simpler parallelism")
      only names those two dimensions explicitly; for the other dimensions
      swept here this generalizes its stated principle to "prefer the
      smaller/simpler value" -- numeric values sort ascending, non-numeric
      values (e.g. an attention-backend name) fall back to whichever was
      listed first in the candidate list (the sweep always lists the
      baseline value first). This is a reasoned extrapolation of the frozen
      rule's spirit, not a literally-specified case -- stated here plainly,
      not quoted as if it were verbatim.

    Each candidate: {"value": Any, "useful_agent_steps_per_second":
    {"mean": float | None, "stdev": float | None}, "had_preemption": bool}.
    """
    if not candidates:
        return {"winner": None, "reason": "no candidates", "disqualified": [], "eligible": [], "tied": []}

    disqualified = [c["value"] for c in candidates if c["had_preemption"]]
    eligible = [
        c
        for c in candidates
        if not c["had_preemption"] and c["useful_agent_steps_per_second"]["mean"] is not None
    ]

    if not eligible:
        return {
            "winner": None,
            "reason": "all candidates disqualified (preemption) or lacked throughput data",
            "disqualified": disqualified,
            "eligible": [],
            "tied": [],
        }

    best = max(eligible, key=lambda c: c["useful_agent_steps_per_second"]["mean"])
    best_mean = best["useful_agent_steps_per_second"]["mean"]
    best_stdev = best["useful_agent_steps_per_second"]["stdev"] or 0.0

    tied = [
        c
        for c in eligible
        if _bands_overlap(
            c["useful_agent_steps_per_second"]["mean"],
            c["useful_agent_steps_per_second"]["stdev"] or 0.0,
            best_mean,
            best_stdev,
        )
    ]

    if len(tied) > 1:
        winner_candidate = min(tied, key=lambda c: _tie_break_key(c, candidates))
        reason = "tie-break: overlapping bands with the best candidate, chose the simpler/smaller value"
    else:
        winner_candidate = best
        reason = "clear winner: highest mean, no overlapping bands"

    return {
        "winner": winner_candidate["value"],
        "reason": reason,
        "disqualified": disqualified,
        "eligible": [c["value"] for c in eligible],
        "tied": [c["value"] for c in tied] if len(tied) > 1 else [],
    }


def _bands_overlap(mean_a: float, stdev_a: float, mean_b: float, stdev_b: float) -> bool:
    return not (mean_a + stdev_a < mean_b - stdev_b or mean_a - stdev_a > mean_b + stdev_b)


def _tie_break_key(candidate: dict[str, Any], all_candidates: list[dict[str, Any]]) -> tuple:
    value = candidate["value"]
    order_index = all_candidates.index(candidate)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (0, value, order_index)
    return (1, 0, order_index)
