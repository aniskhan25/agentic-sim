from __future__ import annotations

from datetime import datetime

from multiagent_demo.models import (
    EnvironmentAction,
    EnvironmentState,
    EnvironmentTransitionResult,
    Event,
    EventType,
)
from multiagent_demo.utils.time import utc_now


class StormEnvironment:
    """Deterministic storm-response environment for local simulation."""

    def __init__(self, regions: list[str] | None = None, severity_step: int = 1):
        self.regions = regions or ["helsinki", "oulu"]
        self.severity_step = severity_step

    def initialize(self) -> EnvironmentState:
        return EnvironmentState(
            scenario="storm",
            tick=0,
            updated_at=utc_now(),
            variables={
                "severity": 1,
                "regions": self.regions,
                "capacity": {region: 100 for region in self.regions},
                "last_summary": "storm watch initialized",
            },
        )

    def apply_actions(
        self, state: EnvironmentState, actions: list[EnvironmentAction]
    ) -> EnvironmentTransitionResult:
        variables = dict(state.variables)
        emitted: list[Event] = []
        for action in actions:
            if action.action_type == "update_summary":
                variables["last_summary"] = action.payload.get("summary", variables.get("last_summary", ""))
            elif action.action_type == "adjust_capacity":
                capacity = dict(variables.get("capacity", {}))
                region = action.payload["region"]
                capacity[region] = max(0, int(capacity.get(region, 100)) + int(action.payload["delta"]))
                variables["capacity"] = capacity
        return EnvironmentTransitionResult(
            state=EnvironmentState(
                scenario=state.scenario,
                tick=state.tick,
                updated_at=utc_now(),
                variables=variables,
            ),
            emitted_events=emitted,
        )

    def tick(self, state: EnvironmentState, now: datetime) -> EnvironmentTransitionResult:
        severity = int(state.variables.get("severity", 1)) + self.severity_step
        variables = dict(state.variables)
        variables["severity"] = severity
        variables["last_summary"] = f"storm severity increased to {severity}"
        next_state = EnvironmentState(
            scenario=state.scenario,
            tick=state.tick + 1,
            updated_at=now,
            variables=variables,
        )
        event = Event.create(
            EventType.ENVIRONMENT_UPDATE,
            source="environment:storm",
            target_scope={"roles": ["coordinator", "hospital", "utility", "forecaster"]},
            payload={
                "severity": severity,
                "regions": list(variables.get("regions", [])),
                "summary": variables["last_summary"],
                "coordinator_id": "agent_coordinator",
                "operator_ids": ["agent_hospital", "agent_utility"],
            },
            priority=severity,
            scheduled_for=now,
        )
        return EnvironmentTransitionResult(state=next_state, emitted_events=[event])
