import unittest

from agentic_sim.engine import (
    SCENARIOS,
    create_engine,
    create_storm_engine,
    create_supply_chain_engine,
)


class EngineTests(unittest.TestCase):
    def test_storm_engine_runs_and_records_traces(self):
        engine = create_storm_engine()

        results = engine.run(3)

        self.assertEqual(len(results), 3)
        self.assertGreaterEqual(engine.store.environment.get().tick, 1)
        self.assertGreaterEqual(len(engine.store.traces.list()), 3)
        coordinator = engine.store.agents.get_state("agent_coordinator")
        self.assertGreaterEqual(coordinator.metrics["activations"], 1)

    def test_engine_records_tick_timing_metrics(self):
        engine = create_storm_engine(agent_replicas=2, max_batch_size=2)

        engine.run(1)

        tick_traces = [
            trace for trace in engine.store.traces.list() if trace.event_name == "simulation_tick"
        ]
        timing = tick_traces[-1].payload["timing_ms"]
        self.assertIn("scheduling_ms", timing)
        self.assertIn("backend_execution_ms", timing)
        self.assertIn("total_ms", timing)
        self.assertEqual(tick_traces[-1].payload["batches"], 4)

    def test_engine_factory_selects_registered_scenario(self):
        engine = create_engine(scenario="storm")

        self.assertEqual(engine.store.environment.get().scenario, "storm")
        self.assertIn("storm", SCENARIOS)

    def test_engine_factory_selects_supply_chain_scenario(self):
        engine = create_engine(
            scenario="supply_chain",
            scenario_parameters={"demand_step": 15, "regions": ["helsinki", "oulu", "tampere"]},
        )

        environment = engine.store.environment.get()
        self.assertEqual(environment.scenario, "supply_chain")
        self.assertEqual(environment.variables["regions"], ["helsinki", "oulu", "tampere"])
        self.assertIn("supply_chain", SCENARIOS)

    def test_supply_chain_engine_runs_and_records_messages(self):
        engine = create_supply_chain_engine()

        engine.run(4)

        self.assertEqual(engine.store.environment.get().scenario, "supply_chain")
        self.assertGreaterEqual(len(engine.store.messages.list()), 2)
        self.assertGreaterEqual(engine.store.environment.get().variables["demand"], 110)

    def test_engine_factory_rejects_unknown_scenario(self):
        with self.assertRaisesRegex(ValueError, "unsupported scenario"):
            create_engine(scenario="unknown")
