import unittest

from agentic_sim.environment import StormEnvironment
from agentic_sim.messaging import MessageRouter
from agentic_sim.models import AgentId, AgentProfile, EventType, Message, MessageType
from agentic_sim.state import InMemoryStateStore


class MessageRouterRouteTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryStateStore(StormEnvironment().initialize())
        self.store.agents.put_profile(
            AgentProfile(agent_id=AgentId("agent_known"), role="hospital", name="k", region="test")
        )
        self.router = MessageRouter()

    def test_filters_out_messages_to_unknown_recipients(self):
        known = Message.create(
            sender_id=AgentId("agent_known"),
            recipient_id=AgentId("agent_known"),
            message_type=MessageType.STATUS_UPDATE,
        )
        unknown = Message.create(
            sender_id=AgentId("agent_known"),
            recipient_id=AgentId("agent_ghost"),
            message_type=MessageType.STATUS_UPDATE,
        )

        deliverable, events = self.router.route([known, unknown], self.store)

        self.assertEqual(deliverable, [known])
        self.assertEqual(len(events), 1)
        self.assertEqual(self.store.messages.count(), 0)  # pure: nothing stored

    def test_derives_message_arrived_event_fields(self):
        message = Message.create(
            sender_id=AgentId("agent_known"),
            recipient_id=AgentId("agent_known"),
            message_type=MessageType.STATUS_UPDATE,
            origin_activation_id="act_1",
        )

        _, events = self.router.route([message], self.store)

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.event_type, EventType.MESSAGE_ARRIVED)
        self.assertEqual(event.target_scope, {"agent_ids": ["agent_known"]})
        self.assertEqual(event.payload["message_id"], message.message_id)
        self.assertEqual(event.causal_parent_activation_id, "act_1")


if __name__ == "__main__":
    unittest.main()
