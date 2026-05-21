from __future__ import annotations

from collections import defaultdict

from multiagent_demo.models import ExecutionRequest


class BatchBuilder:
    def __init__(self, max_batch_size: int = 8):
        self.max_batch_size = max_batch_size

    def group(self, requests: list[ExecutionRequest]) -> list[list[ExecutionRequest]]:
        grouped: dict[tuple[str, str], list[ExecutionRequest]] = defaultdict(list)
        for request in requests:
            key = (request.backend_hint, request.agent_profile.role)
            grouped[key].append(request)

        batches: list[list[ExecutionRequest]] = []
        for group in grouped.values():
            for index in range(0, len(group), self.max_batch_size):
                batches.append(group[index : index + self.max_batch_size])
        return batches
