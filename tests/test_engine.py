import unittest

from agentic_sim.engine import (
    SCENARIOS,
    create_engine,
    create_storm_engine,
    create_supply_chain_engine,
)
from agentic_sim.utils.time import utc_now


class FakeClock:
    """Structurally satisfies the Clock port with no inheritance needed."""

    def __init__(self):
        self.now = utc_now()
        self.advance_calls = 0

    def advance(self):
        self.advance_calls += 1
        return self.now


class FakeTelemetry:
    """Structurally satisfies the Telemetry port; records events in memory
    instead of writing to a trace store."""

    def __init__(self):
        self.events = []

    def record_event(self, event_name, payload):
        self.events.append((event_name, payload))


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

    def test_engine_splits_result_application_timing_into_components(self):
        engine = create_storm_engine(agent_replicas=2, max_batch_size=2)

        engine.run(1)

        tick_traces = [
            trace for trace in engine.store.traces.list() if trace.event_name == "simulation_tick"
        ]
        timing = tick_traces[-1].payload["timing_ms"]
        self.assertIn("state_commit_ms", timing)
        self.assertIn("message_delivery_ms", timing)
        self.assertIn("tracing_ms", timing)
        self.assertNotIn("result_application_ms", timing)
        for key in ("state_commit_ms", "message_delivery_ms", "tracing_ms"):
            self.assertGreaterEqual(timing[key], 0.0)

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

    def test_clock_port_can_be_substituted(self):
        engine = create_storm_engine()
        fake_clock = FakeClock()
        engine.clock = fake_clock

        engine.step()

        self.assertEqual(fake_clock.advance_calls, 1)

    def test_telemetry_port_can_be_substituted(self):
        engine = create_storm_engine()
        fake_telemetry = FakeTelemetry()
        engine.telemetry = fake_telemetry

        engine.run(2)

        event_names = [name for name, _ in fake_telemetry.events]
        self.assertIn("agent_step", event_names)
        self.assertEqual(event_names.count("simulation_tick"), 2)
        # nothing went to the real trace store once telemetry was substituted
        self.assertEqual(len(engine.store.traces.list()), 0)

    def test_local_telemetry_default_path_matches_pre_port_behavior(self):
        engine = create_storm_engine()

        engine.run(1)

        event_names = [trace.event_name for trace in engine.store.traces.list()]
        self.assertIn("agent_step", event_names)
        self.assertIn("simulation_tick", event_names)

    def test_agent_step_trace_carries_causal_and_version_fields(self):
        engine = create_storm_engine()

        engine.run(1)

        agent_steps = [
            trace.payload for trace in engine.store.traces.list() if trace.event_name == "agent_step"
        ]
        self.assertGreater(len(agent_steps), 0)
        for payload in agent_steps:
            self.assertIn("activation_id", payload)
            self.assertIn("trigger_event_id", payload)
            self.assertIsInstance(payload["causal_parents"], list)
            self.assertIn(payload["trigger_event_id"], payload["causal_parents"])
            self.assertEqual(payload["state_version_read"], 0)
            self.assertEqual(payload["commit_version_written"], 1)
            self.assertIsInstance(payload["outgoing_message_ids"], list)
