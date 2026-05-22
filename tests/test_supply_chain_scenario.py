import unittest

from agentic_sim.environment import SupplyChainEnvironment
from agentic_sim.models import EnvironmentAction, EventType
from agentic_sim.utils.time import utc_now


class SupplyChainScenarioTests(unittest.TestCase):
    def test_supply_chain_environment_emits_delay_and_shortage_events(self):
        environment = SupplyChainEnvironment(demand_step=250, delay_step=12)
        state = environment.initialize()

        transition = environment.tick(state, utc_now())

        event_types = [event.event_type for event in transition.emitted_events]
        self.assertIn(EventType.SUPPLY_CHAIN_UPDATE, event_types)
        self.assertIn(EventType.SHIPMENT_DELAY, event_types)
        self.assertIn(EventType.INVENTORY_SHORTAGE, event_types)
        self.assertEqual(transition.state.variables["risk_level"], "high")

    def test_supply_chain_actions_adjust_environment_state(self):
        environment = SupplyChainEnvironment()
        state = environment.initialize()

        transition = environment.apply_actions(
            state,
            [
                EnvironmentAction(
                    action_type="adjust_inventory",
                    payload={"region": "helsinki", "delta": -25},
                )
            ],
        )

        self.assertEqual(transition.state.variables["inventory"]["helsinki"], 95)
