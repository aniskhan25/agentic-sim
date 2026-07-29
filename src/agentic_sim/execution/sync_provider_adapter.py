from __future__ import annotations

from agentic_sim.execution.base import ExecutionBackend
from agentic_sim.execution.errors import ProviderError, ProviderTimeoutError
from agentic_sim.models import DispatchOutcome, DispatchStatus, DispatchTicket, ExecutionRequest
from agentic_sim.utils.ids import new_id


class SynchronousProviderAdapter:
    """Wraps any synchronous ExecutionBackend (run_batch-based) to satisfy
    AsyncExecutionBackend's submit/poll/cancel contract -- "asynchronous
    execution with a synchronous adapter" (target_architecture.md /
    research_roadmap.md Phase 5). submit() actually runs the request to
    completion synchronously and blocks the caller; poll() and cancel()
    exist so callers can be written against the async contract uniformly,
    ready for a genuinely non-blocking adapter later.

    Because submit() always finishes before it returns, DispatchStatus.PENDING
    is never observed through this adapter and cancel() can never actually
    stop anything (nothing is ever in flight by the time cancel() could be
    called) -- both are honest, documented limitations of this adapter, not
    simulated behavior.
    """

    def __init__(self, backend: ExecutionBackend):
        self.backend = backend
        self.name = backend.name
        self.capabilities = backend.capabilities
        self._outcomes: dict[str, DispatchOutcome] = {}

    def submit(self, request: ExecutionRequest) -> DispatchTicket:
        ticket = DispatchTicket(
            ticket_id=new_id("dispatch"), activation_id=request.activation.activation_id
        )
        try:
            result = self.backend.run_batch([request])[0]
            outcome = DispatchOutcome(status=DispatchStatus.COMPLETED, result=result)
        except TimeoutError as exc:
            outcome = DispatchOutcome(
                status=DispatchStatus.FAILED, error=ProviderTimeoutError(str(exc))
            )
        except Exception as exc:
            outcome = DispatchOutcome(status=DispatchStatus.FAILED, error=ProviderError(str(exc)))
        self._outcomes[ticket.ticket_id] = outcome
        return ticket

    def poll(self, ticket: DispatchTicket) -> DispatchOutcome:
        return self._outcomes[ticket.ticket_id]

    def cancel(self, ticket: DispatchTicket) -> bool:
        return False
