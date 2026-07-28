from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Proposal:
    """A backend's pre-validation claim about what an agent should do.

    Message/action/event lists stay plain dicts: they are the model's raw claims,
    not yet validated. Turning them into typed Message/EnvironmentAction objects
    is what _messages/_environment_actions already do downstream.
    """

    raw_content: str
    current_goal: str | None = None
    working_memory: dict[str, Any] = field(default_factory=dict)
    outgoing_messages: list[dict[str, Any]] = field(default_factory=list)
    environment_actions: list[dict[str, Any]] = field(default_factory=list)
    emitted_events: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    is_valid: bool = True
    parse_error: str | None = None
