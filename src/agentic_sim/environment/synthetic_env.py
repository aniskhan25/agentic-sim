from __future__ import annotations

from datetime import datetime
from typing import Any

from agentic_sim.models import (
    EnvironmentAction,
    EnvironmentState,
    EnvironmentTransitionResult,
    Event,
    EventType,
)
from agentic_sim.utils.time import utc_now


class SyntheticEnvironment:
    """Deterministic, domain-agnostic environment for the minimum DAG kernel.

    Emits exactly one root-triggering event at tick 0 (fanned out to every
    listed root agent by the scheduler); later ticks emit nothing. Actions
    are a generic key/value variable set, last-write-wins -- enough to
    express the conflicting_write shape without any domain-specific logic.
    """

    def __init__(self, root_agent_ids: list[str]):
        self.root_agent_ids = root_agent_ids

    def initialize(self) -> EnvironmentState:
        return EnvironmentState(scenario="synthetic", tick=0, updated_at=utc_now(), variables={})

    def apply_actions(
        self, state: EnvironmentState, actions: list[EnvironmentAction]
    ) -> EnvironmentTransitionResult:
        variables = dict(state.variables)
        for action in actions:
            if action.action_type == "set_variable":
                variables[action.payload["key"]] = action.payload["value"]
        return EnvironmentTransitionResult(
            state=EnvironmentState(
                scenario=state.scenario,
                tick=state.tick,
                updated_at=utc_now(),
                variables=variables,
                version=state.version + 1,
            ),
            emitted_events=[],
        )

    def tick(self, state: EnvironmentState, now: datetime) -> EnvironmentTransitionResult:
        next_state = EnvironmentState(
            scenario=state.scenario,
            tick=state.tick + 1,
            updated_at=now,
            variables=dict(state.variables),
            version=state.version + 1,
        )
        emitted: list[Event] = []
        if state.tick == 0:
            emitted.append(
                Event.create(
                    EventType.SYNTHETIC_TRIGGER,
                    source="environment:synthetic",
                    target_scope={"agent_ids": list(self.root_agent_ids)},
                    payload={},
                    priority=1,
                    scheduled_for=now,
                )
            )
        return EnvironmentTransitionResult(state=next_state, emitted_events=emitted)
