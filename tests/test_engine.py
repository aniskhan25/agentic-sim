import unittest

from agentic_sim.engine import create_storm_engine


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
