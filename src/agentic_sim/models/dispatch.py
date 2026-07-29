from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from agentic_sim.models.execution import ExecutionResult


class DispatchStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True, frozen=True)
class DispatchTicket:
    ticket_id: str
    activation_id: str


@dataclass(slots=True)
class DispatchOutcome:
    """Result of polling a DispatchTicket. `error` is typed as a plain
    Exception (not the execution-layer ProviderError hierarchy) because
    models/ may not import from execution/ -- see execution/errors.py and
    execution/sync_provider_adapter.py, which tie the two together.
    """

    status: DispatchStatus
    result: ExecutionResult | None = None
    error: Exception | None = None
