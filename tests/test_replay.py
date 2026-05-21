import unittest
from dataclasses import asdict

from multiagent_demo.engine import create_storm_engine
from multiagent_demo.observability import RunSummaryBuilder
from multiagent_demo.utils.serialization import to_jsonable


class ReplayTests(unittest.TestCase):
    def test_storm_run_has_deterministic_behavior_signature(self):
        first = self._run_signature()
        second = self._run_signature()

        self.assertEqual(first, second)

    def _run_signature(self):
        engine = create_storm_engine()
        ticks = engine.run(5)
        summary = RunSummaryBuilder().build(engine.store)
        traces = engine.store.traces.list()
        return {
            "ticks": [to_jsonable(tick) for tick in ticks],
            "summary": to_jsonable(asdict(summary)),
            "trace_events": [trace.event_name for trace in traces],
            "final_severity": engine.store.environment.get().variables["severity"],
        }
