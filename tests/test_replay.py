import unittest
from dataclasses import asdict

from agentic_sim.engine import create_storm_engine, create_supply_chain_engine
from agentic_sim.observability import build_run_summary
from agentic_sim.utils.serialization import to_jsonable


class ReplayTests(unittest.TestCase):
    def test_storm_run_has_deterministic_behavior_signature(self):
        first = self._storm_signature()
        second = self._storm_signature()

        self.assertEqual(first, second)

    def test_supply_chain_run_has_deterministic_behavior_signature(self):
        first = self._supply_chain_signature()
        second = self._supply_chain_signature()

        self.assertEqual(first, second)

    def _storm_signature(self):
        engine = create_storm_engine()
        ticks = engine.run(5)
        summary = build_run_summary(engine.store)
        traces = engine.store.traces.list()
        return {
            "ticks": [to_jsonable(tick) for tick in ticks],
            "summary": to_jsonable(asdict(summary)),
            "trace_events": [trace.event_name for trace in traces],
            "final_severity": engine.store.environment.get().variables["severity"],
        }

    def _supply_chain_signature(self):
        engine = create_supply_chain_engine()
        ticks = engine.run(5)
        summary = build_run_summary(engine.store)
        traces = engine.store.traces.list()
        return {
            "ticks": [to_jsonable(tick) for tick in ticks],
            "summary": to_jsonable(asdict(summary)),
            "trace_events": [trace.event_name for trace in traces],
            "final_risk_level": engine.store.environment.get().variables["risk_level"],
        }
