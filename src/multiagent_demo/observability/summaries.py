from __future__ import annotations

from dataclasses import dataclass

from multiagent_demo.state.base import RuntimeStore


@dataclass(slots=True)
class RunSummary:
    environment_tick: int
    pending_events: int
    messages: int
    traces: int
    agent_activations: dict[str, int]


class RunSummaryBuilder:
    def build(self, store: RuntimeStore) -> RunSummary:
        agents = store.agents.list_profiles()
        return RunSummary(
            environment_tick=store.environment.get().tick,
            pending_events=store.events.count_pending(),
            messages=store.messages.count(),
            traces=len(store.traces.list()),
            agent_activations={
                str(profile.agent_id): int(
                    store.agents.get_state(profile.agent_id).metrics.get("activations", 0)
                )
                for profile in agents
            },
        )
