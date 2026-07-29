from __future__ import annotations

from typing import Protocol

from agentic_sim.execution.capabilities import ProviderCapabilities
from agentic_sim.models import DispatchOutcome, DispatchTicket, ExecutionRequest


class AsyncExecutionBackend(Protocol):
    """Submit/poll provider port (target_architecture.md / research_roadmap.md
    Phase 5: "define runtime submit/poll or asynchronous execution with a
    synchronous adapter"). Per-request granularity, not per-batch -- this is
    what lets a future dispatcher submit N requests immediately and poll
    them independently for naive/causal concurrent dispatch (item 12),
    without needing new batch-level API. ExecutionBackend/run_batch/
    BatchBuilder are untouched and remain the synchronous path.

    poll() is non-consuming (repeated polls return the same recorded
    outcome) and never raises for provider-side failures -- those surface
    as DispatchOutcome(status=FAILED, error=...). poll() on an unrecognized
    ticket raises KeyError, matching get_profile/get_state's existing
    convention in both state-store backends.
    """

    name: str
    capabilities: ProviderCapabilities

    def submit(self, request: ExecutionRequest) -> DispatchTicket: ...

    def poll(self, ticket: DispatchTicket) -> DispatchOutcome: ...

    def cancel(self, ticket: DispatchTicket) -> bool: ...
