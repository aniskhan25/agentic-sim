from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class FixtureLoader:
    """Loads a JSON fixture file and exposes initial state overrides and per-tick replay data."""

    def __init__(self, path: str | Path) -> None:
        raw = json.loads(Path(path).read_text())
        if not isinstance(raw, dict):
            raise ValueError(f"Fixture must be a JSON object: {path}")
        if "ticks" not in raw:
            raise ValueError(f"Fixture missing required 'ticks' key: {path}")
        if not isinstance(raw["ticks"], list):
            raise ValueError(f"Fixture 'ticks' must be a list: {path}")
        self.path = Path(path)
        self.meta: dict[str, Any] = raw.get("meta", {})
        self.initial: dict[str, Any] = raw.get("initial", {})
        self.ticks: list[dict[str, Any]] = raw["ticks"]

    @classmethod
    def load_if_configured(cls, scenario_parameters: dict[str, Any]) -> FixtureLoader | None:
        fixture_path = scenario_parameters.get("fixture")
        if not fixture_path:
            return None
        return cls(fixture_path)
