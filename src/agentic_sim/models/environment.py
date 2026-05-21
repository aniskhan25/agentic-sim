from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class EnvironmentState:
    scenario: str
    tick: int
    updated_at: datetime
    variables: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EnvironmentAction:
    action_type: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EnvironmentTransitionResult:
    state: EnvironmentState
    emitted_events: list["Event"] = field(default_factory=list)
