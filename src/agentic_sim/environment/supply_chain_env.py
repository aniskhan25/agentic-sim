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


class SupplyChainEnvironment:
    """Deterministic supply-chain environment for local simulation."""

    def __init__(
        self,
        regions: list[str] | None = None,
        demand_step: int = 10,
        delay_step: int = 4,
        coordinator_id: str = "agent_coordinator",
        operator_ids: list[str] | None = None,
        initial_variables: dict[str, Any] | None = None,
        tick_data: list[dict[str, Any]] | None = None,
    ):
        self.regions = regions or ["helsinki", "oulu"]
        self.demand_step = demand_step
        self.delay_step = delay_step
        self.coordinator_id = coordinator_id
        self.operator_ids = operator_ids or [
            "agent_supplier",
            "agent_warehouse",
            "agent_transport",
            "agent_retailer",
        ]
        self._initial_variables: dict[str, Any] = initial_variables or {}
        self._tick_data: list[dict[str, Any]] = tick_data or []

    def initialize(self) -> EnvironmentState:
        init = self._initial_variables
        return EnvironmentState(
            scenario="supply_chain",
            tick=0,
            updated_at=utc_now(),
            variables={
                "demand": int(init.get("demand", 100)),
                "inventory": dict(init.get("inventory", {region: 120 for region in self.regions})),
                "delayed_shipments": int(init.get("delayed_shipments", 0)),
                "transport_capacity": int(init.get("transport_capacity", 100)),
                "risk_level": str(init.get("risk_level", "normal")),
                "regions": self.regions,
                "last_summary": str(init.get("last_summary", "supply chain initialized")),
            },
        )

    def apply_actions(
        self, state: EnvironmentState, actions: list[EnvironmentAction]
    ) -> EnvironmentTransitionResult:
        variables = dict(state.variables)
        emitted: list[Event] = []
        for action in actions:
            if action.action_type == "update_summary":
                variables["last_summary"] = action.payload.get(
                    "summary", variables.get("last_summary", "")
                )
            elif action.action_type == "adjust_inventory":
                inventory = dict(variables.get("inventory", {}))
                region = action.payload["region"]
                inventory[region] = max(
                    0, int(inventory.get(region, 0)) + int(action.payload["delta"])
                )
                variables["inventory"] = inventory
            elif action.action_type == "adjust_transport_capacity":
                variables["transport_capacity"] = max(
                    0,
                    int(variables.get("transport_capacity", 0)) + int(action.payload["delta"]),
                )
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
        variables = dict(state.variables)
        tick_entry = self._tick_data[state.tick] if state.tick < len(self._tick_data) else {}
        demand = int(tick_entry.get("demand", int(variables.get("demand", 100)) + self.demand_step))
        delayed_shipments = int(
            tick_entry.get("delayed_shipments", int(variables.get("delayed_shipments", 0)) + self.delay_step)
        )
        region = str(tick_entry.get("affected_region", self.regions[(state.tick + 1) % len(self.regions)]))
        observation = str(tick_entry.get("observation", ""))
        if "inventory" in tick_entry:
            inventory = {k: int(v) for k, v in tick_entry["inventory"].items()}
        else:
            inventory = dict(variables.get("inventory", {}))
            inventory[region] = max(0, int(inventory.get(region, 0)) - max(1, demand // 20))

        shortage_regions = [
            name for name, value in inventory.items() if int(value) < max(20, demand // 2)
        ]
        if shortage_regions or delayed_shipments >= 12:
            risk_level = "high"
        elif demand >= 120 or delayed_shipments >= 8:
            risk_level = "elevated"
        else:
            risk_level = "normal"

        variables.update(
            {
                "demand": demand,
                "delayed_shipments": delayed_shipments,
                "inventory": inventory,
                "risk_level": risk_level,
                "last_summary": observation or f"demand {demand}, delays {delayed_shipments}, risk {risk_level}",
            }
        )
        next_state = EnvironmentState(
            scenario=state.scenario,
            tick=state.tick + 1,
            updated_at=now,
            variables=variables,
        )
        payload = {
            "demand": demand,
            "delayed_shipments": delayed_shipments,
            "inventory": inventory,
            "risk_level": risk_level,
            "region": region,
            "shortage_regions": shortage_regions,
            "coordinator_id": self.coordinator_id,
            "operator_ids": self.operator_ids,
            "summary": variables["last_summary"],
        }
        emitted = [
            Event.create(
                EventType.SUPPLY_CHAIN_UPDATE,
                source="environment:supply_chain",
                target_scope={"roles": ["coordinator", "supplier", "warehouse", "transport", "retailer"]},
                payload=payload,
                priority=1 if risk_level == "normal" else 2,
                scheduled_for=now,
            )
        ]
        if delayed_shipments >= 12:
            emitted.append(
                Event.create(
                    EventType.SHIPMENT_DELAY,
                    source="environment:supply_chain",
                    target_scope={"roles": ["coordinator", "transport", "warehouse"]},
                    payload=payload,
                    priority=3,
                    scheduled_for=now,
                )
            )
        if shortage_regions:
            emitted.append(
                Event.create(
                    EventType.INVENTORY_SHORTAGE,
                    source="environment:supply_chain",
                    target_scope={"roles": ["coordinator", "supplier", "warehouse", "retailer"]},
                    payload=payload,
                    priority=4,
                    scheduled_for=now,
                )
            )
        return EnvironmentTransitionResult(state=next_state, emitted_events=emitted)
