from __future__ import annotations

from typing import Any

from agentic_sim.execution.aitta_backend import AittaExecutionBackend
from agentic_sim.execution.base import ExecutionBackend
from agentic_sim.execution.mock_backend import MockExecutionBackend
from agentic_sim.execution.self_hosted_backend import SelfHostedExecutionBackend
from agentic_sim.execution.supply_chain_backend import SupplyChainRuleBackend


def create_execution_backend(
    backend_name: str,
    *,
    scenario: str,
    backend_options: dict[str, Any] | None = None,
) -> ExecutionBackend:
    options = backend_options or {}
    if backend_name == "aitta":
        return AittaExecutionBackend(
            api_key=options.get("aitta_api_key"),
            base_url=options.get("aitta_base_url"),
            model_name=options.get("aitta_model"),
            timeout_seconds=options.get("aitta_timeout"),
            max_retries=int(options.get("aitta_max_retries", 3)),
            max_json_repair_attempts=int(options.get("aitta_max_json_repair_attempts", 1)),
            max_concurrency=int(options.get("aitta_max_concurrency", 1)),
            temperature=float(options.get("aitta_temperature", 0.2)),
            top_p=float(options.get("aitta_top_p", 0.95)),
            max_completion_tokens=options.get("aitta_max_completion_tokens"),
        )
    if backend_name == "self_hosted":
        return SelfHostedExecutionBackend(
            api_key=options.get("self_hosted_api_key"),
            base_url=options.get("self_hosted_base_url"),
            model_name=options.get("self_hosted_model"),
            timeout_seconds=options.get("self_hosted_timeout"),
            max_retries=int(options.get("self_hosted_max_retries", 3)),
            max_json_repair_attempts=int(options.get("self_hosted_max_json_repair_attempts", 1)),
            max_concurrency=int(options.get("self_hosted_max_concurrency", 1)),
            temperature=float(options.get("self_hosted_temperature", 0.2)),
            top_p=float(options.get("self_hosted_top_p", 0.95)),
            max_completion_tokens=options.get("self_hosted_max_completion_tokens"),
            max_context_tokens=options.get("self_hosted_max_context_tokens"),
            enable_prefix_caching=bool(options.get("self_hosted_enable_prefix_caching", False)),
        )
    if scenario == "supply_chain" and backend_name in {"mock", "rule"}:
        return SupplyChainRuleBackend(name=backend_name)
    if scenario == "storm" and backend_name in {"mock", "rule"}:
        return MockExecutionBackend()
    raise ValueError(f"unsupported backend {backend_name!r}")
