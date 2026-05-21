from __future__ import annotations

from typing import Protocol

from agentic_sim.models import ExecutionRequest, ExecutionResult


class ExecutionBackend(Protocol):
    name: str

    def run_batch(self, requests: list[ExecutionRequest]) -> list[ExecutionResult]: ...
