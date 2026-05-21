from __future__ import annotations

from agentic_sim.execution.mock_backend import MockExecutionBackend


class RuleExecutionBackend(MockExecutionBackend):
    """Rule backend placeholder with the same contract as model backends."""

    name = "rule"
