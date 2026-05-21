from __future__ import annotations

from datetime import datetime
from typing import Protocol

from agentic_sim.models import EnvironmentAction, EnvironmentState, EnvironmentTransitionResult, Event


class Environment(Protocol):
    def initialize(self) -> EnvironmentState: ...
    def apply_actions(
        self, state: EnvironmentState, actions: list[EnvironmentAction]
    ) -> EnvironmentTransitionResult: ...
    def tick(self, state: EnvironmentState, now: datetime) -> EnvironmentTransitionResult: ...
