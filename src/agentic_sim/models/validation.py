from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ValidationResult:
    """Formalizes the ad-hoc validation metadata fields aitta_backend.py has
    computed since the JSON-repair and role_policy contract work: schema
    validity, semantic validity (role_policy.semantic_violations), repair and
    policy-completion counts, and the resulting model autonomy rate.

    violation_reasons holds the FINAL (post-guard) violation list, matching
    what useful_step reflects — not the pre-guard list, which is transient.
    """

    semantic_valid: bool
    model_output_invalid: bool = False
    model_output_error: str | None = None
    json_repair_attempts: int = 0
    must_not_violations: int = 0
    violation_reasons: list[str] = field(default_factory=list)
    bounded_violations: int = 0
    cardinality_violations: int = 0
    state_mutation_violations: int = 0
    state_mutation_provenance: dict[str, str] = field(default_factory=dict)
    policy_guard_added_messages: int = 0
    policy_guard_added_actions: int = 0
    autonomy_rate: float = 1.0
    useful_step: bool = True
