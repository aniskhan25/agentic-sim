from __future__ import annotations

from multiagent_demo.models import Activation, AgentProfile, Event
from multiagent_demo.scheduling.base import SchedulerInput


class FIFOScheduler:
    """Priority-aware FIFO scheduler with one activation per agent per tick."""

    def __init__(self, max_activations_per_tick: int = 16):
        self.max_activations_per_tick = max_activations_per_tick

    def plan(self, snapshot: SchedulerInput) -> list[Activation]:
        profiles = {profile.agent_id: profile for profile in snapshot.agent_profiles}
        activations: list[Activation] = []
        activated_agents: set[str] = set()
        events = sorted(snapshot.events, key=lambda event: (-event.priority, event.created_at))

        for event in events:
            for profile in self._targets(event, list(profiles.values())):
                agent_key = str(profile.agent_id)
                if agent_key in activated_agents:
                    continue
                activations.append(
                    Activation.create(
                        agent_id=profile.agent_id,
                        trigger_event_id=event.event_id,
                        activation_reason=event.event_type.value,
                        priority=event.priority,
                        ready_at=snapshot.now,
                    )
                )
                activated_agents.add(agent_key)
                if len(activations) >= self.max_activations_per_tick:
                    return activations
        return activations

    def _targets(self, event: Event, profiles: list[AgentProfile]) -> list[AgentProfile]:
        agent_ids = set(event.target_scope.get("agent_ids", []))
        roles = set(event.target_scope.get("roles", []))
        if agent_ids:
            return [profile for profile in profiles if str(profile.agent_id) in agent_ids]
        if roles:
            return [profile for profile in profiles if profile.role in roles]
        return profiles
