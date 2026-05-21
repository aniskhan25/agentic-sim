from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from multiagent_demo.utils.time import utc_now


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
