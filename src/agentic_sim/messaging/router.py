from __future__ import annotations

from agentic_sim.models import Event, EventType, Message
from agentic_sim.state.base import RuntimeStore


class MessageRouter:
    """Filters messages to known recipients and derives their delivery events."""

    def route(self, messages: list[Message], store: RuntimeStore) -> tuple[list[Message], list[Event]]:
        """Pure: does not touch the store. Callers commit the result
        atomically alongside the sending agent's state (see
        SimulationEngine.step() and models/commit.py::CommitUnit).
        """
        known_agents = {str(profile.agent_id) for profile in store.agents.list_profiles()}
        deliverable: list[Message] = []
        events: list[Event] = []
        for message in messages:
            if str(message.recipient_id) not in known_agents:
                continue
            deliverable.append(message)
            events.append(
                Event.create(
                    EventType.MESSAGE_ARRIVED,
                    source=f"message:{message.sender_id}",
                    target_scope={"agent_ids": [str(message.recipient_id)]},
                    payload={
                        "message_id": message.message_id,
                        "message_type": message.message_type.value,
                        "sender_id": str(message.sender_id),
                    },
                    priority=message.priority,
                    correlation_id=message.correlation_id or message.message_id,
                    causal_parent_activation_id=message.origin_activation_id,
                )
            )
        return deliverable, events
