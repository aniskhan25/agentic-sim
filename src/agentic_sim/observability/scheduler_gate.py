from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Any

from agentic_sim.execution import SynchronousProviderAdapter
from agentic_sim.execution.capabilities import ProviderCapabilities
from agentic_sim.execution.latency_simulating_backend import LatencySimulatingBackend
from agentic_sim.models import (
    Activation,
    AgentId,
    AgentProfile,
    AgentState,
    EnvironmentState,
    Event,
    EventType,
    ExecutionRequest,
)
from agentic_sim.scheduling import (
    BarrierDispatchPolicy,
    CapabilityAwareDispatchPolicy,
    CausalOnlyDispatchPolicy,
    FullDispatchPolicy,
    NaiveConcurrentDispatchPolicy,
    QueueAwareDispatchPolicy,
    SequentialDispatchPolicy,
)
from agentic_sim.utils.time import utc_now

# Preregistered decision rule -- docs/scheduler_contribution_gate.md's numbers,
# verbatim. Written before this harness was ever run.
MIN_RELATIVE_IMPROVEMENT = 0.15
HETEROGENEITY_BEARING_VARIANTS = {"multi_provider", "multi_role_multi_provider"}
PRIMARY_CONTRAST = ("full", "causal_only")

_CAPABILITIES = ProviderCapabilities(
    supports_concurrency=True,
    supports_server_batching=False,
    supports_structured_output=False,
    supports_prefix_caching=False,
    max_context_tokens=0,
    observable_token_usage=False,
    observable_energy=False,
)


def _dispatch_policies() -> list:
    return [
        SequentialDispatchPolicy(),
        NaiveConcurrentDispatchPolicy(),
        BarrierDispatchPolicy(),
        CausalOnlyDispatchPolicy(),
        CapabilityAwareDispatchPolicy(),
        QueueAwareDispatchPolicy(),
        FullDispatchPolicy(),
    ]


def _build_request(agent_id: str, *, backend_hint: str, role: str) -> ExecutionRequest:
    now = utc_now()
    event = Event.create(EventType.SYNTHETIC_TRIGGER, source="scheduler_gate", priority=1)
    return ExecutionRequest(
        activation=Activation.create(
            agent_id=AgentId(agent_id),
            trigger_event_id=event.event_id,
            activation_reason=event.event_type.value,
            priority=event.priority,
            ready_at=now,
        ),
        agent_profile=AgentProfile(
            agent_id=AgentId(agent_id),
            role=role,
            name=agent_id,
            region="scheduler_gate",
            backend=backend_hint,
        ),
        agent_state=AgentState(agent_id=AgentId(agent_id)),
        inbox_messages=[],
        triggering_event=event,
        environment=EnvironmentState(scenario="scheduler_gate", tick=0, updated_at=now, variables={}),
        backend_hint=backend_hint,
    )


def _build_variant(
    name: str, *, provider_count: int, role_count: int, agents_per_group: int, delay: float
) -> tuple[str, list[ExecutionRequest], dict[str, float]]:
    requests: list[ExecutionRequest] = []
    delays: dict[str, float] = {}
    for provider_index in range(provider_count):
        for role_index in range(role_count):
            for agent_index in range(agents_per_group):
                agent_id = f"{name}_p{provider_index}_r{role_index}_a{agent_index}"
                requests.append(
                    _build_request(
                        agent_id, backend_hint=f"provider_{provider_index}", role=f"role_{role_index}"
                    )
                )
                delays[agent_id] = delay
    return name, requests, delays


def _build_workload_variants() -> list[tuple[str, list[ExecutionRequest], dict[str, float]]]:
    return [
        _build_variant("single_provider", provider_count=1, role_count=1, agents_per_group=6, delay=0.01),
        _build_variant("multi_provider", provider_count=3, role_count=1, agents_per_group=4, delay=0.01),
        _build_variant(
            "multi_role_multi_provider", provider_count=3, role_count=3, agents_per_group=2, delay=0.01
        ),
    ]


WORKLOAD_VARIANTS = _build_workload_variants()


def _summarize(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "mean": None, "stdev": None, "ci95": None}
    mean = statistics.mean(values)
    stdev = statistics.stdev(values) if len(values) > 1 else 0.0
    margin = 1.96 * stdev / (len(values) ** 0.5)
    return {
        "count": len(values),
        "mean": round(mean, 3),
        "stdev": round(stdev, 3),
        "ci95": [round(mean - margin, 3), round(mean + margin, 3)],
    }


def _evaluate_gate(variant_name: str, policy_stats: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if variant_name not in HETEROGENEITY_BEARING_VARIANTS:
        return {
            "applicable": False,
            "cleared": True,
            "reason": "control variant -- no heterogeneity for any rung to exploit, no effect required",
        }

    full_name, causal_name = PRIMARY_CONTRAST
    full = policy_stats[full_name]
    causal = policy_stats[causal_name]
    if full["mean"] is None or causal["mean"] is None or causal["mean"] == 0:
        return {"applicable": True, "cleared": False, "reason": "insufficient data"}

    relative_improvement = (full["mean"] - causal["mean"]) / causal["mean"]
    effect_size_ok = relative_improvement >= MIN_RELATIVE_IMPROVEMENT
    bands_separated = (full["mean"] - full["stdev"]) > (causal["mean"] + causal["stdev"])

    return {
        "applicable": True,
        "cleared": bool(effect_size_ok and bands_separated),
        "relative_improvement": round(relative_improvement, 4),
        "effect_size_ok": effect_size_ok,
        "bands_separated": bands_separated,
    }


def run_scheduler_contribution_gate(
    repeats: int = 10,
    output_path: str | Path | None = "docs/baseline/scheduler_contribution_gate_results.json",
) -> dict[str, Any]:
    """Runs the full 7-rung dispatch-policy ladder against each preregistered
    workload variant, `repeats` times each, and evaluates the preregistered
    scheduler contribution decision gate (docs/scheduler_contribution_gate.md)
    against `full` versus `causal_only` throughput.
    """
    excluded: list[dict[str, Any]] = []
    variant_reports = []

    for variant_name, requests, delays in WORKLOAD_VARIANTS:
        backend = LatencySimulatingBackend(capabilities=_CAPABILITIES, delays=delays)
        adapter = SynchronousProviderAdapter(backend)

        policy_stats: dict[str, dict[str, Any]] = {}
        for policy in _dispatch_policies():
            throughputs = []
            for repeat_index in range(repeats):
                try:
                    started = time.perf_counter()
                    policy.dispatch(requests, adapter)
                    elapsed = time.perf_counter() - started
                except Exception as exc:
                    excluded.append(
                        {
                            "variant": variant_name,
                            "policy": policy.name,
                            "repeat": repeat_index,
                            "error": str(exc),
                        }
                    )
                    continue
                if elapsed > 0:
                    throughputs.append(len(requests) / elapsed)
            policy_stats[policy.name] = _summarize(throughputs)

        variant_reports.append(
            {
                "variant": variant_name,
                "request_count": len(requests),
                "repeats": repeats,
                "throughput_requests_per_second": policy_stats,
                "gate": _evaluate_gate(variant_name, policy_stats),
            }
        )

    overall_gate_cleared = all(
        report["gate"]["cleared"]
        for report in variant_reports
        if report["variant"] in HETEROGENEITY_BEARING_VARIANTS
    )
    payload = {
        "min_relative_improvement": MIN_RELATIVE_IMPROVEMENT,
        "heterogeneity_bearing_variants": sorted(HETEROGENEITY_BEARING_VARIANTS),
        "primary_contrast": list(PRIMARY_CONTRAST),
        "variants": variant_reports,
        "excluded": excluded,
        "overall_gate_cleared": overall_gate_cleared,
    }

    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
