# Agentic Simulation Runtime

A minimal event-driven runtime for multi-agent simulation experiments.

The current scenario is a deterministic storm-response simulation. It creates coordinator, hospital, utility, and forecaster agents, routes events and messages between them, records state, and writes traces. No LLM, vector database, distributed runtime, or external service is required.

The code is intentionally small so the simulation loop can be inspected and tested locally before real model-serving backends are added.

## What Runs Today

- A storm environment that increases severity over time.
- A coordinator agent that asks operators for status.
- Hospital and utility agents that report local status.
- Forecaster agents that update the environment summary.
- In-memory storage for local runs.
- SQLite storage for persisted runs.
- Deterministic mock/rule execution backends.

## Quick Start

Create a local environment, install the package, run a small simulation, and run tests:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

agentic-sim run --steps 4
pytest
```

You can also run directly from source without installing the package:

```bash
PYTHONPATH=src python3 -m agentic_sim.cli run --steps 4
```

If `pytest` is not available, the tests can also run with the standard library:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

## Run Examples

Run the small config:

```bash
PYTHONPATH=src python3 -m agentic_sim.cli run \
  --config configs/storm_small.json
```

Run the scale smoke-test config:

```bash
PYTHONPATH=src python3 -m agentic_sim.cli run \
  --config configs/storm_scale.json
```

Persist a full run artifact with traces and the final environment snapshot:

```bash
PYTHONPATH=src python3 -m agentic_sim.cli run \
  --config configs/storm_scale.json \
  --output data/storm_scale_run.json
```

Use SQLite storage explicitly:

```bash
PYTHONPATH=src python3 -m agentic_sim.cli run \
  --config configs/storm_scale.json \
  --storage-mode sqlite \
  --sqlite-path data/storm_scale.sqlite \
  --output data/storm_scale_run.json
```

Useful CLI overrides:

```bash
PYTHONPATH=src python3 -m agentic_sim.cli run \
  --config configs/storm_scale.json \
  --steps 50 \
  --agent-replicas 128 \
  --max-batch-size 64
```

## Understanding Output

A run prints a compact JSON summary:

- `ticks`: engine loop results.
- `processed_events`: events consumed in that engine step.
- `activations`: agents selected to respond.
- `messages_emitted`: messages produced by agents.
- `traces_written`: trace records written for that engine step.
- `summary.environment_tick`: storm environment tick.
- `summary.pending_events`: events still queued after the run.
- `summary.messages`: total persisted messages.
- `summary.traces`: total persisted traces.
- `summary.agent_activations`: activation count by agent.

Engine steps and environment ticks are different. Several engine steps may drain message events before the storm environment advances again, so repeated `tick` values are expected.

When `--output` is set, the artifact includes:

- `ticks`: the compact per-step results.
- `summary`: final run summary.
- `environment`: final environment state.
- `traces`: structured trace records, including `simulation_tick` timing fields.

## LUMI

For LUMI-oriented batch runs, see [docs/lumi.md](docs/lumi.md) and `scripts/run_lumi.sh`.

Minimal submission:

```bash
sbatch scripts/run_lumi.sh
```

Submit with explicit scratch artifacts:

```bash
mkdir -p /scratch/project_462000131/anisrahm/agentic-sim-runs/logs
ARTIFACT_ROOT=/scratch/project_462000131/anisrahm/agentic-sim-runs \
  sbatch --output=/scratch/project_462000131/anisrahm/agentic-sim-runs/logs/%x-%j.out scripts/run_lumi.sh
```

## Project Layout

The runtime is organized around explicit boundaries:

- `models`: dataclass schemas for agents, events, messages, execution requests/results, environment state, and traces.
- `state`: swappable persistence interfaces plus in-memory and SQLite implementations.
- `scheduling`: FIFO activation planning from ready events.
- `execution`: context building, simple batching, and deterministic backends.
- `messaging`: structured message delivery and follow-up event creation.
- `environment`: deterministic storm scenario rules.
- `engine`: the top-level simulation loop.
- `observability`: trace writing and run summaries.

Additional docs:

- [docs/architecture.md](docs/architecture.md): runtime design.
- [docs/execution_model.md](docs/execution_model.md): activation and execution flow.
- [docs/storage.md](docs/storage.md): storage boundary.
- [docs/scenario_storm.md](docs/scenario_storm.md): storm scenario details.
- [docs/lumi.md](docs/lumi.md): LUMI batch runs.
- [docs/amd_vllm_lumi_tuning.md](docs/amd_vllm_lumi_tuning.md): future AMD/vLLM throughput knobs.

The engine treats reasoning as a pluggable backend behind a stable execution contract. That keeps the simulation inspectable and lets model serving be added later without changing the core loop.

## Current Scope

The current repo does not include:

- distributed execution
- remote LLM serving
- training
- vector databases
- real weather data
- dashboards or UI
- multi-node orchestration
