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


class StormEnvironment:
    """Deterministic storm-response environment for local simulation."""

    def __init__(
        self,
        regions: list[str] | None = None,
        severity_step: int = 1,
        coordinator_id: str = "agent_coordinator",
        operator_ids: list[str] | None = None,
        utility_operator_ids: list[str] | None = None,
        initial_variables: dict[str, Any] | None = None,
        tick_data: list[dict[str, Any]] | None = None,
    ):
        self.regions = regions or ["helsinki", "oulu"]
        self.severity_step = severity_step
        self.coordinator_id = coordinator_id
        self.operator_ids = operator_ids or ["agent_hospital", "agent_utility"]
        self.utility_operator_ids = utility_operator_ids or ["agent_utility"]
        self._initial_variables: dict[str, Any] = initial_variables or {}
        self._tick_data: list[dict[str, Any]] = tick_data or []

    def initialize(self) -> EnvironmentState:
        init = self._initial_variables
        return EnvironmentState(
            scenario="storm",
            tick=0,
            updated_at=utc_now(),
            variables={
                "severity": int(init.get("severity", 1)),
                "regions": self.regions,
                "capacity": dict(init.get("capacity", {region: 100 for region in self.regions})),
                "last_summary": str(init.get("last_summary", "storm watch initialized")),
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
        tick_entry = self._tick_data[state.tick] if state.tick < len(self._tick_data) else {}
        severity = int(
            tick_entry.get("severity", int(state.variables.get("severity", 1)) + self.severity_step)
        )
        affected_region = str(
            tick_entry.get("affected_region", self.regions[(state.tick + 1) % len(self.regions)])
        )
        observation = str(tick_entry.get("observation", ""))
        variables = dict(state.variables)
        variables["severity"] = severity
        variables["last_summary"] = observation or f"storm severity increased to {severity}"
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
                "coordinator_id": self.coordinator_id,
                "operator_ids": self.operator_ids,
            },
            priority=severity,
            scheduled_for=now,
        )
        emitted = [event]
        if severity >= 3:
            emitted.append(
                Event.create(
                    EventType.STORM_OUTAGE,
                    source="environment:storm",
                    target_scope={"roles": ["coordinator", "utility"]},
                    payload={
                        "severity": severity,
                        "region": affected_region,
                        "outage_level": "major" if severity >= 5 else "localized",
                        "coordinator_id": self.coordinator_id,
                        "operator_ids": self.utility_operator_ids,
                        "summary": f"grid outage risk in {affected_region}",
                    },
                    priority=severity + 1,
                    scheduled_for=now,
                )
            )
        return EnvironmentTransitionResult(state=next_state, emitted_events=emitted)
