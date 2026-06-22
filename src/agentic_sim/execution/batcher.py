from __future__ import annotations

from collections import defaultdict

from agentic_sim.models import ExecutionRequest


class BatchBuilder:
    def __init__(self, max_batch_size: int = 8):
        self.max_batch_size = max_batch_size

    def group(self, requests: list[ExecutionRequest]) -> list[list[ExecutionRequest]]:
        grouped: dict[str, list[ExecutionRequest]] = defaultdict(list)
        for request in requests:
            grouped[request.backend_hint].append(request)
        batches: list[list[ExecutionRequest]] = []
        for group in grouped.values():
            for i in range(0, len(group), self.max_batch_size):
                batches.append(group[i : i + self.max_batch_size])
        return batches
