from __future__ import annotations

from agentic_sim.models import Activation, Event, ExecutionRequest
from agentic_sim.state.base import RuntimeStore


class ContextBuilder:
    def __init__(self, inbox_limit: int = 5):
        self.inbox_limit = inbox_limit

    def build(
        self,
        activation: Activation,
        triggering_event: Event,
        store: RuntimeStore,
    ) -> ExecutionRequest:
        profile = store.agents.get_profile(activation.agent_id)
        state = store.agents.get_state(activation.agent_id)
        return ExecutionRequest(
            activation=activation,
            agent_profile=profile,
            agent_state=state,
            inbox_messages=store.messages.inbox(activation.agent_id, limit=self.inbox_limit),
            triggering_event=triggering_event,
            environment=store.environment.get(),
            backend_hint=profile.backend,
        )
