from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from agentic_sim.utils.time import utc_now


class Clock(Protocol):
    now: datetime

    def advance(self) -> datetime: ...


@dataclass(slots=True)
class SimulationClock:
    now: datetime
    step_size: timedelta = timedelta(minutes=5)

    @classmethod
    def start(cls) -> "SimulationClock":
        return cls(now=utc_now())

    def advance(self) -> datetime:
        self.now = self.now + self.step_size
        return self.now
