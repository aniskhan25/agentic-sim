"""
Thin CLI wrapper around observability/b2_selection.py::select_best_candidate
(roadmap item 19, B2 platform-tuned mode).

The actual sweep orchestration (starting/stopping a real vllm serve process
per candidate, health-checking, grepping its log for KV-cache preemption)
reuses the exact bash patterns already proven across every prior real job
this session (b1_pilot_job.sh/b1_fullnode_job.sh) rather than a fresh,
untested Python subprocess orchestrator -- see the per-system b2_sweep_job.sh
written directly to each system's scratch. This script is what that bash
loop calls once per dimension, after collecting every candidate's real
measurement, to apply the frozen selection rule and print the winner.

Usage:
    python3 scripts/run_b2_sweep.py --candidates candidates.json

candidates.json: a JSON list of {"value": ..., "useful_agent_steps_per_second":
{"mean": float|None, "stdev": float|None}, "had_preemption": bool}, exactly
matching observability/b2_selection.py::select_best_candidate's input shape.
"""
from __future__ import annotations

import argparse
import json

from agentic_sim.observability.b2_selection import select_best_candidate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--candidates", required=True, help="Path to a JSON file of candidates")
    parser.add_argument("--output", help="Write the full JSON result to this path (in addition to stdout)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    candidates = json.loads(open(args.candidates).read())
    result = select_best_candidate(candidates)
    print(json.dumps(result, indent=2))
    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
            f.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
