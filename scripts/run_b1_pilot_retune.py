"""
Retune QueueAwareDispatchPolicy/FullDispatchPolicy's bounded in-flight cap
(roadmap item 19 follow-up) using real data: the confirmatory 7-rung B1
pilot (scripts/run_b1_pilot.py) found a real, statistically distinguishable
regression on both LUMI and Roihu starting at queue_aware, traced to its
default_max_in_flight=2 default -- an arbitrary illustrative value from
item 13, never tuned against real data.

This sweeps default_max_in_flight over {2, 4, 8} for queue_aware and full
(8 matches capability_aware's own uncapped max_workers, the natural upper
bound), keeping causal_only and capability_aware as fixed reference points.
This is exploratory tuning data (evaluation_plan.md's B2 vocabulary), not
confirmatory -- hence fewer repeats (5, not 10) than run_b1_pilot.py.

Usage (against a live server already started, e.g. via vllm serve):
    python3 scripts/run_b1_pilot_retune.py \
      --self-hosted-base-url http://localhost:8000/v1 \
      --self-hosted-model Qwen/Qwen2.5-7B-Instruct \
      --output b1_retune_sweep_result.json

Sanity check without any live server (mock backend):
    python3 scripts/run_b1_pilot_retune.py --backend mock --repeats 2
"""
from __future__ import annotations

import argparse
import json

from agentic_sim.observability.b1_pilot import run_b1_pilot
from agentic_sim.scenarios.storm import create_storm_engine
from agentic_sim.scheduling import CapabilityAwareDispatchPolicy, CausalOnlyDispatchPolicy
from agentic_sim.scheduling.dispatch_policy import FullDispatchPolicy, QueueAwareDispatchPolicy

_SWEEP_VALUES = (2, 4, 8)

# docs/b1_frozen_configuration.md's decoding parameters -- OpenAICompatibleExecutionBackend's
# own existing defaults, reused rather than re-decided.
_FROZEN_TEMPERATURE = 0.2
_FROZEN_TOP_P = 0.95
_FROZEN_MAX_COMPLETION_TOKENS = 256
_FROZEN_MAX_CONTEXT_TOKENS = 8192


def _sweep_policies() -> dict:
    policies = {
        "causal_only": CausalOnlyDispatchPolicy(),
        "capability_aware": CapabilityAwareDispatchPolicy(),
    }
    for n in _SWEEP_VALUES:
        policies[f"queue_aware_{n}"] = QueueAwareDispatchPolicy(default_max_in_flight=n)
        policies[f"full_{n}"] = FullDispatchPolicy(default_max_in_flight=n)
    return policies


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backend", choices=["mock", "self_hosted"], default="self_hosted")
    parser.add_argument("--self-hosted-base-url")
    parser.add_argument("--self-hosted-model")
    parser.add_argument("--self-hosted-timeout", type=float, default=60.0)
    parser.add_argument("--self-hosted-max-concurrency", type=int, default=8)
    parser.add_argument("--repeats", type=int, default=5)
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
            "self_hosted_max_concurrency": args.self_hosted_max_concurrency,
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
        dispatch_policies=_sweep_policies(),
        repeats=args.repeats,
        steps_per_repeat=args.steps_per_repeat,
        warmup_backend_step_count=args.warmup_backend_step_count,
        output_path=args.output,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
