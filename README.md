# Agentic Simulation Runtime

This repository is a minimal event-driven simulation runtime for multi-agent experiments. It keeps simulation state, scheduling, execution backends, messaging, environment dynamics, and traces separated so the runtime can be tested locally before adding real model-serving integrations.

The first scenario is a small storm-response simulation with deterministic mock/rule backends. No LLM, vector database, distributed runtime, or external service is required.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
agentic-sim run --steps 4
pytest
```

You can also run without installing the package:

```bash
PYTHONPATH=src python3 -m agentic_sim.cli run --steps 4
```

To persist a full run artifact with traces and the final environment snapshot:

```bash
PYTHONPATH=src python3 -m agentic_sim.cli run --steps 4 --output data/run.json
```

## Architecture

The runtime is organized around explicit boundaries:

- `models`: dataclass schemas for agents, events, messages, execution requests/results, environment state, and traces.
- `state`: swappable persistence interfaces plus in-memory and SQLite implementations.
- `scheduling`: FIFO activation planning from ready events.
- `execution`: context building, simple batching, and deterministic backends.
- `messaging`: structured message delivery and follow-up event creation.
- `environment`: deterministic storm scenario rules.
- `engine`: the top-level simulation loop.
- `observability`: trace writing and run summaries.

For LUMI-oriented batch runs, see [docs/lumi.md](docs/lumi.md) and `scripts/run_lumi.sh`. For AMD/vLLM throughput knobs, see [docs/amd_vllm_lumi_tuning.md](docs/amd_vllm_lumi_tuning.md).

The engine treats reasoning as a pluggable backend behind a stable execution contract. That keeps the simulation inspectable and lets model serving be added later without changing the core loop.

## Intentionally Out of Scope

- distributed execution
- remote LLM serving
- training
- vector databases
- real weather data
- dashboards or UI
- multi-node orchestration
