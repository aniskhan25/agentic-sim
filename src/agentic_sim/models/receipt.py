from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ExecutionReceipt:
    """Provider-neutral execution receipt (ADR 0001 / target_architecture.md).

    Fields with no current data source (request/response hashes, state
    versions, per-phase timing, provider cost, platform identifiers) default
    to None — never a fake 0 or placeholder string. They become real once the
    underlying capability exists (hashing utility, versioned store in Phase
    4/5, per-phase instrumentation, a real PlatformManifest wiring).
    """

    activation_id: str
    attempt_number: int = 0
    provider: str | None = None
    model: str | None = None
    model_revision: str | None = None
    request_hash: str | None = None
    prompt_hash: str | None = None
    raw_response_hash: str | None = None
    state_version_read: int | None = None
    commit_version_written: int | None = None
    causal_parents: list[str] = field(default_factory=list)
    dispatch_seconds: float | None = None
    queue_seconds: float | None = None
    inference_seconds: float | None = None
    validation_seconds: float | None = None
    commit_seconds: float | None = None
    total_latency_seconds: float | None = None
    token_usage: dict[str, Any] | None = None
    provider_cost: float | None = None
    accelerator: str | None = None
    host_architecture: str | None = None
    serving_runtime: str | None = None
    manifest_mode: str | None = None
    environment_id: str | None = None
    schema_valid: bool | None = None
    semantic_valid: bool | None = None
    repair_attempts: int = 0
    policy_completion_applied: bool = False
    fallback_used: bool = False
    commit_status: str = "unknown"
    error_reason: str | None = None
