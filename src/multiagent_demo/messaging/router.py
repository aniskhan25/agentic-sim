from __future__ import annotations

from multiagent_demo.models import Event, EventType, Message
from multiagent_demo.state.base import RuntimeStore


class MessageRouter:
    """Stores structured messages and emits delivery events."""

    def deliver(self, messages: list[Message], store: RuntimeStore) -> list[Event]:
        events: list[Event] = []
        known_agents = {str(profile.agent_id) for profile in store.agents.list_profiles()}
        for message in messages:
            if str(message.recipient_id) not in known_agents:
                continue
            store.messages.put(message)
            events.append(
                Event.create(
                    EventType.MESSAGE_ARRIVED,
                    source=f"message:{message.sender_id}",
                    target_scope={"agent_ids": [str(message.recipient_id)]},
                    payload={
                        "message_id": message.message_id,
                        "message_type": message.message_type.value,
                        "coordinator_id": "agent_coordinator",
                    },
                    priority=message.priority,
                    correlation_id=message.correlation_id or message.message_id,
                )
            )
        store.events.put_many(events)
        return events
