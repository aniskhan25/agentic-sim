"""
Run the B1 pilot (roadmap item 19): a bounded, real dispatch-policy
comparison (sequential vs. full) against a live self-hosted vLLM server,
using the storm workload and docs/b1_frozen_configuration.md's frozen B1
decoding/batching values.

This is a pilot, not the primary study -- see docs/b1_frozen_configuration.md
and docs/hpc_data_collection_procedures.md for the full frozen procedure this
does not yet run at full scale (10 repeats, all 7 policies, all workloads).

Usage (against a live server already started, e.g. via vllm serve):
    python3 scripts/run_b1_pilot.py \
      --self-hosted-base-url http://localhost:8000/v1 \
      --self-hosted-model Qwen/Qwen2.5-7B-Instruct \
      --repeats 3 --steps-per-repeat 5 \
      --output b1_pilot_result.json

Sanity check without any live server (mock backend):
    python3 scripts/run_b1_pilot.py --backend mock --repeats 2
"""
from __future__ import annotations

import argparse
import json

from agentic_sim.observability.b1_pilot import run_b1_pilot
from agentic_sim.scenarios.storm import create_storm_engine
from agentic_sim.scheduling import FullDispatchPolicy, SequentialDispatchPolicy

# docs/b1_frozen_configuration.md's decoding parameters -- OpenAICompatibleExecutionBackend's
# own existing defaults, reused rather than re-decided.
_FROZEN_TEMPERATURE = 0.2
_FROZEN_TOP_P = 0.95
_FROZEN_MAX_COMPLETION_TOKENS = 256
_FROZEN_MAX_CONTEXT_TOKENS = 8192


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backend", choices=["mock", "self_hosted"], default="self_hosted")
    parser.add_argument("--self-hosted-base-url")
    parser.add_argument("--self-hosted-model")
    parser.add_argument("--self-hosted-timeout", type=float, default=60.0)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--steps-per-repeat", type=int, default=5)
    parser.add_argument("--warmup-backend-step-count", type=int, default=20)
    parser.add_argument("--output", help="Write the full JSON result to this path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    backend_options = None
    if args.backend == "self_hosted":
        if not args.self_hosted_base_url or not args.self_hosted_model:
            raise SystemExit("--self-hosted-base-url and --self-hosted-model are required for --backend self_hosted")
        backend_options = {
            "self_hosted_base_url": args.self_hosted_base_url,
            "self_hosted_model": args.self_hosted_model,
            "self_hosted_timeout": args.self_hosted_timeout,
            "self_hosted_temperature": _FROZEN_TEMPERATURE,
            "self_hosted_top_p": _FROZEN_TOP_P,
            "self_hosted_max_completion_tokens": _FROZEN_MAX_COMPLETION_TOKENS,
            "self_hosted_enable_prefix_caching": True,
            "self_hosted_max_context_tokens": _FROZEN_MAX_CONTEXT_TOKENS,
        }

    def engine_factory():
        return create_storm_engine(backend_name=args.backend, backend_options=backend_options)

    result = run_b1_pilot(
        engine_factory=engine_factory,
        dispatch_policies={"sequential": SequentialDispatchPolicy(), "full": FullDispatchPolicy()},
        repeats=args.repeats,
        steps_per_repeat=args.steps_per_repeat,
        warmup_backend_step_count=args.warmup_backend_step_count,
        output_path=args.output,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
