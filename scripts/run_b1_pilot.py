"""
Run the B1 pilot (roadmap item 19): a bounded, real comparison across the
full 7-rung dispatch-policy ladder against a live self-hosted vLLM server,
using the storm or supply_chain workload and docs/b1_frozen_configuration.md's
frozen B1 decoding/batching values. deterministic_kernel/synthetic dependency
graphs/failure workloads are not selectable here -- create_synthetic_engine
hard-rejects any real backend and its agents carry no natural-language
prompts, a separate unresolved prerequisite (see docs/research_roadmap.md
item 19).

This is a pilot, not the primary study -- see docs/b1_frozen_configuration.md
and docs/hpc_data_collection_procedures.md for the full frozen procedure this
does not yet run at full scale (all five workload families, both placement
levels, B2 mode).

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
from agentic_sim.scenarios.supply_chain import create_supply_chain_engine
from agentic_sim.scheduling import (
    BarrierDispatchPolicy,
    CapabilityAwareDispatchPolicy,
    CausalOnlyDispatchPolicy,
    FullDispatchPolicy,
    NaiveConcurrentDispatchPolicy,
    QueueAwareDispatchPolicy,
    SequentialDispatchPolicy,
)

# The full 7-rung policy ladder (research_roadmap.md items 12-13), in ladder order.
_ALL_DISPATCH_POLICIES = {
    "sequential": SequentialDispatchPolicy(),
    "naive_concurrent": NaiveConcurrentDispatchPolicy(),
    "barrier": BarrierDispatchPolicy(),
    "causal_only": CausalOnlyDispatchPolicy(),
    "capability_aware": CapabilityAwareDispatchPolicy(),
    "queue_aware": QueueAwareDispatchPolicy(),
    "full": FullDispatchPolicy(),
}

# docs/b1_frozen_configuration.md's decoding parameters -- OpenAICompatibleExecutionBackend's
# own existing defaults, reused rather than re-decided.
_FROZEN_TEMPERATURE = 0.2
_FROZEN_TOP_P = 0.95
_FROZEN_MAX_COMPLETION_TOKENS = 256
_FROZEN_MAX_CONTEXT_TOKENS = 8192


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backend", choices=["mock", "self_hosted"], default="self_hosted")
    parser.add_argument("--scenario", choices=["storm", "supply_chain"], default="storm")
    parser.add_argument("--self-hosted-base-url")
    parser.add_argument("--self-hosted-model")
    parser.add_argument("--self-hosted-timeout", type=float, default=60.0)
    parser.add_argument(
        "--self-hosted-max-concurrency",
        type=int,
        default=8,
        help=(
            "Backend-declared concurrent-request capacity -- SelfHostedExecutionBackend derives "
            "capabilities.supports_concurrency as max_concurrency > 1, and CapabilityAwareDispatchPolicy "
            "(and everything built on it: queue_aware, full) dispatch sequentially whenever that's False, "
            "silently discarding any real concurrency benefit. Must be > 1 for those rungs to mean anything; "
            "8 matches CapabilityAwareDispatchPolicy's own default max_workers."
        ),
    )
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--steps-per-repeat", type=int, default=5)
    parser.add_argument("--warmup-backend-step-count", type=int, default=20)
    parser.add_argument(
        "--agent-replicas",
        type=int,
        default=1,
        help=(
            "Passed through to create_storm_engine/create_supply_chain_engine's agent_replicas "
            "(1 coordinator + this many copies of the other roles). The default of 1 gives storm "
            "only 4 agents and supply_chain only 5 -- far too few to stress a serving config's "
            "--max-num-seqs; raise this to actually generate real concurrent backend load."
        ),
    )
    parser.add_argument(
        "--max-events-per-tick",
        type=int,
        default=32,
        help=(
            "Passed through to the scenario factory's max_events_per_tick (SimulationEngine's own "
            "default is 32) -- a hard per-tick cap on events popped before scheduling/dispatch even "
            "happens. Must be raised alongside --agent-replicas or it becomes the binding ceiling "
            "regardless of roster size."
        ),
    )
    parser.add_argument(
        "--dispatch-max-workers",
        type=int,
        default=None,
        help=(
            "Overrides causal_only's ThreadPoolExecutor max_workers (CausalOnlyDispatchPolicy's own "
            "default is 8, hardcoded here otherwise) -- the real, binding client-side concurrency "
            "ceiling for causal_only (--self-hosted-max-concurrency only gates run_batch's internal "
            "pool, which causal_only's submit()/poll() path never reaches with more than one request "
            "at a time). Only affects causal_only; default (unset) leaves every policy unchanged."
        ),
    )
    parser.add_argument(
        "--policies",
        help=(
            "Comma-separated subset of the 7-rung ladder to run (default: all 7). "
            f"Choices: {', '.join(_ALL_DISPATCH_POLICIES)}. E.g. --policies causal_only "
            "for a B2 serving-config sweep, which holds the scheduling policy fixed."
        ),
    )
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

    scenario_factory = create_storm_engine if args.scenario == "storm" else create_supply_chain_engine

    def engine_factory():
        return scenario_factory(
            backend_name=args.backend,
            backend_options=backend_options,
            agent_replicas=args.agent_replicas,
            max_events_per_tick=args.max_events_per_tick,
        )

    if args.policies:
        requested = [name.strip() for name in args.policies.split(",")]
        unknown = [name for name in requested if name not in _ALL_DISPATCH_POLICIES]
        if unknown:
            raise SystemExit(f"unknown --policies value(s) {unknown}; choices: {list(_ALL_DISPATCH_POLICIES)}")
        dispatch_policies = {name: _ALL_DISPATCH_POLICIES[name] for name in requested}
    else:
        dispatch_policies = dict(_ALL_DISPATCH_POLICIES)

    if args.dispatch_max_workers is not None and "causal_only" in dispatch_policies:
        dispatch_policies["causal_only"] = CausalOnlyDispatchPolicy(max_workers=args.dispatch_max_workers)

    result = run_b1_pilot(
        engine_factory=engine_factory,
        dispatch_policies=dispatch_policies,
        repeats=args.repeats,
        steps_per_repeat=args.steps_per_repeat,
        warmup_backend_step_count=args.warmup_backend_step_count,
        output_path=args.output,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
