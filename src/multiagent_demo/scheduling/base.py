from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from multiagent_demo.models import Activation, AgentProfile, Event


@dataclass(slots=True)
class SchedulerInput:
    now: datetime
    events: list[Event]
    agent_profiles: list[AgentProfile]


class Scheduler(Protocol):
    def plan(self, snapshot: SchedulerInput) -> list[Activation]: ...
