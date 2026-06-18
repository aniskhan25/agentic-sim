from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

from agentic_sim.config import load_config, merge_cli
from agentic_sim.engine import create_engine
from agentic_sim.execution import check_aitta_connection
from agentic_sim.observability import (
    RunSummaryBuilder,
    aggregate_run_artifacts,
    write_run_artifacts,
)
from agentic_sim.sweep import generate_sweep
from agentic_sim.utils.env import load_env_files
from agentic_sim.utils.serialization import to_jsonable


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentic-sim")
    subcommands = parser.add_subparsers(dest="command", required=True)

    run = subcommands.add_parser("run", help="Run a simulation scenario")
    run.add_argument("--config", help="Path to a JSON runtime config")
    run.add_argument("--scenario", help="Scenario name")
    run.add_argument("--steps", type=int, help="Number of simulation steps")
    run.add_argument("--backend", choices=["mock", "rule", "aitta"], help="Execution backend")
    run.add_argument("--storage-mode", choices=["memory", "sqlite"], help="State storage mode")
    run.add_argument("--sqlite-path", help="SQLite database path")
    run.add_argument("--max-batch-size", type=int)
    run.add_argument("--max-events-per-tick", type=int)
    run.add_argument("--agent-replicas", type=int)
    run.add_argument("--aitta-base-url", help="OpenAI-compatible Aitta base URL")
    run.add_argument("--aitta-model", help="Aitta model name")
    run.add_argument("--aitta-timeout", type=float, help="Aitta request timeout in seconds")
    run.add_argument("--aitta-max-retries", type=int, help="Aitta request retry count")
    run.add_argument("--aitta-max-concurrency", type=int, help="Aitta request concurrency")
    run.add_argument("--aitta-temperature", type=float, help="Aitta sampling temperature")
    run.add_argument("--aitta-top-p", type=float, help="Aitta nucleus sampling value")
    run.add_argument(
        "--aitta-max-completion-tokens",
        type=int,
        help="Aitta max completion tokens per agent step",
    )
    run.add_argument("--output", help="Write full run artifact JSON to this path")
    run.add_argument("--output-dir", help="Write split run artifacts to this directory")

    check_aitta = subcommands.add_parser(
        "check-aitta",
        help="Check Aitta OpenAI-compatible chat-completions connectivity",
    )
    check_aitta.add_argument("--aitta-base-url", help="OpenAI-compatible Aitta base URL")
    check_aitta.add_argument("--aitta-model", help="Aitta model name")
    check_aitta.add_argument("--aitta-timeout", type=float, help="Aitta request timeout in seconds")
    check_aitta.add_argument("--aitta-max-retries", type=int, help="Aitta request retry count")
    check_aitta.add_argument(
        "--wait",
        action="store_true",
        help="Poll until Aitta responds or the warm-up timeout expires",
    )
    check_aitta.add_argument(
        "--wait-timeout",
        type=float,
        default=900,
        help="Maximum seconds to wait when --wait is set",
    )
    check_aitta.add_argument(
        "--wait-interval",
        type=float,
        default=30,
        help="Seconds between probes when --wait is set",
    )

    aggregate = subcommands.add_parser(
        "aggregate-runs",
        help="Aggregate split run artifacts under a root directory",
    )
    aggregate.add_argument("root_dir", help="Directory containing run artifact subdirectories")
    aggregate.add_argument("--output", help="Write aggregate JSON to this path")

    sweep = subcommands.add_parser(
        "generate-sweep",
        help="Generate a config file per sweep combination from a sweep spec",
    )
    sweep.add_argument("spec", help="Path to the sweep spec JSON file")
    sweep.add_argument(
        "--output-dir",
        help="Directory to write generated configs and manifest (default: data/sweeps/<sweep_id>)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    load_env_files([".env.local", ".env"])
    args = build_parser().parse_args(argv)
    if args.command == "run":
        return run_command(args)
    if args.command == "check-aitta":
        return check_aitta_command(args)
    if args.command == "aggregate-runs":
        return aggregate_runs_command(args)
    if args.command == "generate-sweep":
        return generate_sweep_command(args)
    raise ValueError(args.command)


def run_command(args: argparse.Namespace) -> int:
    config = merge_cli(
        load_config(args.config),
        {
            "scenario": args.scenario,
            "steps": args.steps,
            "backend": args.backend,
            "storage_mode": args.storage_mode,
            "sqlite_path": args.sqlite_path,
            "max_batch_size": args.max_batch_size,
            "max_events_per_tick": args.max_events_per_tick,
            "agent_replicas": args.agent_replicas,
        },
    )
    config.backend_options.update(_aitta_cli_options(args))
    engine = create_engine(
        scenario=config.scenario,
        scenario_parameters=config.scenario_parameters,
        storage_mode=config.storage_mode,
        sqlite_path=config.sqlite_path or f"data/{config.scenario}.sqlite",
        backend_name=config.backend,
        max_batch_size=config.max_batch_size,
        max_events_per_tick=config.max_events_per_tick,
        agent_replicas=config.agent_replicas,
        backend_options=config.backend_options,
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
    if args.output_dir:
        payload["artifacts"] = write_run_artifacts(
            args.output_dir,
            config=config,
            tick_results=tick_results,
            summary=summary,
            store=engine.store,
        )
    print(json.dumps(payload, indent=2))
    return 0


def _aitta_cli_options(args: argparse.Namespace) -> dict[str, object]:
    return {
        key: value
        for key, value in {
            "aitta_base_url": getattr(args, "aitta_base_url", None),
            "aitta_model": getattr(args, "aitta_model", None),
            "aitta_timeout": getattr(args, "aitta_timeout", None),
            "aitta_max_retries": getattr(args, "aitta_max_retries", None),
            "aitta_max_concurrency": getattr(args, "aitta_max_concurrency", None),
            "aitta_temperature": getattr(args, "aitta_temperature", None),
            "aitta_top_p": getattr(args, "aitta_top_p", None),
            "aitta_max_completion_tokens": getattr(args, "aitta_max_completion_tokens", None),
        }.items()
        if value is not None
    }


def check_aitta_command(args: argparse.Namespace) -> int:
    started = time.monotonic()
    attempts = 0
    last_error = ""
    wait_timeout = max(0, args.wait_timeout)
    wait_interval = max(0, args.wait_interval)

    try:
        while True:
            attempts += 1
            try:
                result = check_aitta_connection(
                    base_url=args.aitta_base_url,
                    model_name=args.aitta_model,
                    timeout_seconds=args.aitta_timeout,
                    max_retries=args.aitta_max_retries or 0,
                )
            except Exception as exc:
                last_error = str(exc)
                if not args.wait or time.monotonic() - started >= wait_timeout:
                    raise
                time.sleep(wait_interval)
                continue
            result["attempts"] = attempts
            result["elapsed_seconds"] = round(time.monotonic() - started, 3)
            print(json.dumps(result, indent=2))
            return 0
    except Exception:
        print(
            json.dumps(
                {
                    "ok": False,
                    "attempts": attempts,
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                    "error": last_error,
                },
                indent=2,
            )
        )
        return 1


def aggregate_runs_command(args: argparse.Namespace) -> int:
    payload = aggregate_run_artifacts(args.root_dir, args.output)
    print(json.dumps(payload, indent=2))
    return 0


def generate_sweep_command(args: argparse.Namespace) -> int:
    from pathlib import Path as _Path

    manifest = generate_sweep(args.spec, output_dir=getattr(args, "output_dir", None))
    print(json.dumps(manifest, indent=2))
    n = manifest["total"]
    manifest_path = str(_Path(manifest["configs"][0]).parent.parent / "sweep_manifest.json")
    config_list = " ".join(manifest["configs"])
    print(f"\n# {n} config(s) generated. To submit on LUMI:")
    print(f"# Option A — pass config list directly:")
    print(f'CONFIG_LIST="{config_list}" sbatch --array=0-{n - 1} scripts/run_lumi_array.sh')
    print(f"# Option B — pass sweep manifest:")
    print(f'SWEEP_MANIFEST="{manifest_path}" sbatch --array=0-{n - 1} scripts/run_lumi_array.sh')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
