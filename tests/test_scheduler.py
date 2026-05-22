import unittest

from agentic_sim.models import AgentId, AgentProfile, Event, EventType
from agentic_sim.scheduling import FIFOScheduler, SchedulerInput
from agentic_sim.utils.time import utc_now


class SchedulerTests(unittest.TestCase):
    def test_fifo_scheduler_targets_roles_once_per_tick(self):
        now = utc_now()
        profiles = [
            AgentProfile(AgentId("agent_a"), "coordinator", "A", "north"),
            AgentProfile(AgentId("agent_b"), "hospital", "B", "south"),
        ]
        event = Event.create(
            EventType.ENVIRONMENT_UPDATE,
            source="test",
            target_scope={"roles": ["hospital"]},
            priority=3,
            scheduled_for=now,
        )

        activations = FIFOScheduler().plan(
            SchedulerInput(now=now, events=[event], agent_profiles=profiles)
        )

        self.assertEqual(len(activations), 1)
        self.assertEqual(activations[0].agent_id, AgentId("agent_b"))
        self.assertEqual(activations[0].priority, 3)

    def test_fifo_scheduler_activates_every_targeted_agent(self):
        now = utc_now()
        profiles = [
            AgentProfile(AgentId("agent_a"), "coordinator", "A", "north"),
            AgentProfile(AgentId("agent_b"), "hospital", "B", "south"),
            AgentProfile(AgentId("agent_c"), "utility", "C", "south"),
        ]
        event = Event.create(
            EventType.ENVIRONMENT_UPDATE,
            source="test",
            target_scope={"roles": ["coordinator", "hospital", "utility"]},
            scheduled_for=now,
        )

        activations = FIFOScheduler().plan(
            SchedulerInput(now=now, events=[event], agent_profiles=profiles)
        )

        self.assertEqual(
            [activation.agent_id for activation in activations],
            [AgentId("agent_a"), AgentId("agent_b"), AgentId("agent_c")],
        )
