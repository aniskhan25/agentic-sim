from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from multiagent_demo.config import load_config, merge_cli
from multiagent_demo.engine import create_storm_engine
from multiagent_demo.observability import RunSummaryBuilder
from multiagent_demo.utils.serialization import to_jsonable


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="multiagent-demo")
    subcommands = parser.add_subparsers(dest="command", required=True)

    run = subcommands.add_parser("run", help="Run the storm-response simulation")
    run.add_argument("--config", help="Path to a JSON runtime config")
    run.add_argument("--steps", type=int, help="Number of simulation steps")
    run.add_argument("--backend", choices=["mock", "rule"], help="Execution backend")
    run.add_argument("--storage-mode", choices=["memory", "sqlite"], help="State storage mode")
    run.add_argument("--sqlite-path", help="SQLite database path")
    run.add_argument("--max-activations-per-tick", type=int)
    run.add_argument("--max-batch-size", type=int)
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
        },
    )
    engine = create_storm_engine(
        storage_mode=config.storage_mode,
        sqlite_path=config.sqlite_path,
        backend_name=config.backend,
        max_activations_per_tick=config.max_activations_per_tick,
        max_batch_size=config.max_batch_size,
    )
    tick_results = engine.run(config.steps)
    summary = RunSummaryBuilder().build(engine.store)
    print(
        json.dumps(
            {
                "ticks": [to_jsonable(result) for result in tick_results],
                "summary": to_jsonable(asdict(summary)),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
