import json
import tempfile
import unittest
from pathlib import Path

from agentic_sim.environment.storm_env import StormEnvironment
from agentic_sim.environment.supply_chain_env import SupplyChainEnvironment
from agentic_sim.scenarios.fixtures import FixtureLoader
from agentic_sim.utils.time import utc_now


def _write_fixture(tmp_dir: Path, data: dict) -> Path:
    path = tmp_dir / "fixture.json"
    path.write_text(json.dumps(data))
    return path


class FixtureLoaderTests(unittest.TestCase):
    def test_loads_meta_initial_and_ticks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_fixture(
                Path(tmp),
                {
                    "meta": {"description": "test"},
                    "initial": {"severity": 2},
                    "ticks": [{"severity": 3}],
                },
            )
            loader = FixtureLoader(path)
        self.assertEqual(loader.meta["description"], "test")
        self.assertEqual(loader.initial["severity"], 2)
        self.assertEqual(loader.ticks[0]["severity"], 3)

    def test_raises_on_missing_ticks_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_fixture(Path(tmp), {"initial": {}})
            with self.assertRaises(ValueError):
                FixtureLoader(path)

    def test_raises_on_non_object_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.json"
            path.write_text("[]")
            with self.assertRaises(ValueError):
                FixtureLoader(path)

    def test_load_if_configured_returns_none_when_no_fixture_param(self):
        result = FixtureLoader.load_if_configured({"steps": 4})
        self.assertIsNone(result)

    def test_load_if_configured_loads_when_fixture_param_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_fixture(Path(tmp), {"ticks": [{"severity": 3}]})
            loader = FixtureLoader.load_if_configured({"fixture": str(path)})
        self.assertIsNotNone(loader)
        self.assertEqual(loader.ticks[0]["severity"], 3)


class StormFixtureTests(unittest.TestCase):
    def _env(self, initial=None, ticks=None):
        return StormEnvironment(
            regions=["helsinki", "oulu"],
            initial_variables=initial,
            tick_data=ticks,
        )

    def test_initialize_uses_fixture_initial_severity(self):
        env = self._env(initial={"severity": 3, "last_summary": "fixture start"})
        state = env.initialize()
        self.assertEqual(state.variables["severity"], 3)
        self.assertEqual(state.variables["last_summary"], "fixture start")

    def test_initialize_uses_fixture_initial_capacity(self):
        env = self._env(initial={"capacity": {"helsinki": 80, "oulu": 90}})
        state = env.initialize()
        self.assertEqual(state.variables["capacity"]["helsinki"], 80)
        self.assertEqual(state.variables["capacity"]["oulu"], 90)

    def test_initialize_defaults_when_no_fixture(self):
        env = self._env()
        state = env.initialize()
        self.assertEqual(state.variables["severity"], 1)
        self.assertEqual(state.variables["capacity"]["helsinki"], 100)

    def test_tick_uses_fixture_severity(self):
        env = self._env(ticks=[{"severity": 4, "affected_region": "helsinki"}])
        state = env.initialize()
        result = env.tick(state, utc_now())
        self.assertEqual(result.state.variables["severity"], 4)

    def test_tick_uses_fixture_observation_as_summary(self):
        env = self._env(ticks=[{"severity": 3, "observation": "heavy snowfall in Oulu"}])
        state = env.initialize()
        result = env.tick(state, utc_now())
        self.assertEqual(result.state.variables["last_summary"], "heavy snowfall in Oulu")

    def test_tick_falls_back_to_computed_when_fixture_exhausted(self):
        env = self._env(ticks=[{"severity": 5}])
        state = env.initialize()
        state = env.tick(state, utc_now()).state   # tick 0 → uses fixture
        result = env.tick(state, utc_now())         # tick 1 → fixture exhausted, computed
        # Default severity_step=1, so severity should be 5+1=6
        self.assertEqual(result.state.variables["severity"], 6)

    def test_tick_emits_outage_event_at_high_fixture_severity(self):
        env = self._env(ticks=[{"severity": 5, "affected_region": "oulu"}])
        state = env.initialize()
        result = env.tick(state, utc_now())
        event_types = [e.event_type.value for e in result.emitted_events]
        self.assertIn("storm_outage", event_types)

    def test_tick_observation_falls_back_to_default_summary_when_empty(self):
        env = self._env(ticks=[{"severity": 2}])
        state = env.initialize()
        result = env.tick(state, utc_now())
        self.assertIn("2", result.state.variables["last_summary"])


class SupplyChainFixtureTests(unittest.TestCase):
    def _env(self, initial=None, ticks=None):
        return SupplyChainEnvironment(
            regions=["helsinki", "oulu"],
            initial_variables=initial,
            tick_data=ticks,
        )

    def test_initialize_uses_fixture_initial_demand_and_inventory(self):
        env = self._env(
            initial={
                "demand": 95,
                "inventory": {"helsinki": 130, "oulu": 115},
                "delayed_shipments": 2,
            }
        )
        state = env.initialize()
        self.assertEqual(state.variables["demand"], 95)
        self.assertEqual(state.variables["inventory"]["helsinki"], 130)
        self.assertEqual(state.variables["delayed_shipments"], 2)

    def test_initialize_defaults_when_no_fixture(self):
        env = self._env()
        state = env.initialize()
        self.assertEqual(state.variables["demand"], 100)
        self.assertEqual(state.variables["inventory"]["helsinki"], 120)

    def test_tick_uses_fixture_demand_and_inventory(self):
        env = self._env(
            ticks=[{"demand": 165, "delayed_shipments": 18, "inventory": {"helsinki": 78, "oulu": 72}}]
        )
        state = env.initialize()
        result = env.tick(state, utc_now())
        self.assertEqual(result.state.variables["demand"], 165)
        self.assertEqual(result.state.variables["inventory"]["helsinki"], 78)
        self.assertEqual(result.state.variables["delayed_shipments"], 18)

    def test_tick_uses_fixture_observation_as_summary(self):
        env = self._env(ticks=[{"demand": 150, "delayed_shipments": 5, "observation": "port delays clearing"}])
        state = env.initialize()
        result = env.tick(state, utc_now())
        self.assertEqual(result.state.variables["last_summary"], "port delays clearing")

    def test_tick_falls_back_to_computed_when_fixture_exhausted(self):
        env = self._env(ticks=[{"demand": 110, "delayed_shipments": 6}])
        state = env.initialize()
        state = env.tick(state, utc_now()).state   # tick 0 → uses fixture
        result = env.tick(state, utc_now())         # tick 1 → computed
        self.assertEqual(result.state.variables["demand"], 110 + 10)  # demand_step=10

    def test_tick_derives_risk_level_from_fixture_values(self):
        env = self._env(
            ticks=[{"demand": 185, "delayed_shipments": 24, "inventory": {"helsinki": 55, "oulu": 60}}]
        )
        state = env.initialize()
        result = env.tick(state, utc_now())
        # demand=185, inventory well below demand//2=92 → shortage → high risk
        self.assertEqual(result.state.variables["risk_level"], "high")

    def test_tick_emits_shortage_event_when_fixture_drives_low_inventory(self):
        env = self._env(
            ticks=[{"demand": 185, "delayed_shipments": 5, "inventory": {"helsinki": 30, "oulu": 30}}]
        )
        state = env.initialize()
        result = env.tick(state, utc_now())
        event_types = [e.event_type.value for e in result.emitted_events]
        self.assertIn("inventory_shortage", event_types)


class FixtureIntegrationTests(unittest.TestCase):
    def test_storm_scenario_factory_loads_fixture_from_scenario_parameters(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_fixture(
                Path(tmp),
                {
                    "initial": {"severity": 3},
                    "ticks": [{"severity": 4, "affected_region": "helsinki"}],
                },
            )
            from agentic_sim.scenarios.storm import create_storm_engine
            engine = create_storm_engine(scenario_parameters={"fixture": str(path)})
        state = engine.store.environment.get()
        self.assertEqual(state.variables["severity"], 3)

    def test_supply_chain_scenario_factory_loads_fixture_from_scenario_parameters(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_fixture(
                Path(tmp),
                {
                    "initial": {"demand": 95, "inventory": {"helsinki": 130, "oulu": 115}, "delayed_shipments": 2},
                    "ticks": [{"demand": 110, "delayed_shipments": 6, "inventory": {"helsinki": 122, "oulu": 108}}],
                },
            )
            from agentic_sim.scenarios.supply_chain import create_supply_chain_engine
            engine = create_supply_chain_engine(scenario_parameters={"fixture": str(path)})
        state = engine.store.environment.get()
        self.assertEqual(state.variables["demand"], 95)
        self.assertEqual(state.variables["inventory"]["helsinki"], 130)
