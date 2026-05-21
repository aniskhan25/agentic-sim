from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from agentic_sim.config import load_config, merge_cli
from agentic_sim.engine import create_storm_engine
from agentic_sim.observability import RunSummaryBuilder
from agentic_sim.utils.serialization import to_jsonable


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentic-sim")
    subcommands = parser.add_subparsers(dest="command", required=True)

    run = subcommands.add_parser("run", help="Run the storm-response simulation")
    run.add_argument("--config", help="Path to a JSON runtime config")
    run.add_argument("--steps", type=int, help="Number of simulation steps")
    run.add_argument("--backend", choices=["mock", "rule"], help="Execution backend")
    run.add_argument("--storage-mode", choices=["memory", "sqlite"], help="State storage mode")
    run.add_argument("--sqlite-path", help="SQLite database path")
    run.add_argument("--max-activations-per-tick", type=int)
    run.add_argument("--max-batch-size", type=int)
    run.add_argument("--max-events-per-tick", type=int)
    run.add_argument("--agent-replicas", type=int)
    run.add_argument("--output", help="Write full run artifact JSON to this path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        return run_command(args)
    raise ValueError(args.command)


def run_command(args: argparse.Namespace) -> int:
    config = merge_cli(
        load_config(args.config),
        {
            "steps": args.steps,
            "backend": args.backend,
            "storage_mode": args.storage_mode,
            "sqlite_path": args.sqlite_path,
            "max_activations_per_tick": args.max_activations_per_tick,
            "max_batch_size": args.max_batch_size,
            "max_events_per_tick": args.max_events_per_tick,
            "agent_replicas": args.agent_replicas,
        },
    )
    engine = create_storm_engine(
        storage_mode=config.storage_mode,
        sqlite_path=config.sqlite_path,
        backend_name=config.backend,
        max_activations_per_tick=config.max_activations_per_tick,
        max_batch_size=config.max_batch_size,
        max_events_per_tick=config.max_events_per_tick,
        agent_replicas=config.agent_replicas,
    )
    tick_results = engine.run(config.steps)
    summary = RunSummaryBuilder().build(engine.store)
    payload = {
        "ticks": [to_jsonable(result) for result in tick_results],
        "summary": to_jsonable(asdict(summary)),
    }
    if args.output:
        artifact = {
            **payload,
            "environment": to_jsonable(engine.store.environment.get()),
            "traces": [to_jsonable(trace) for trace in engine.store.traces.list()],
        }
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
