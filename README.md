# Agentic Simulation Runtime

A minimal event-driven runtime for multi-agent simulation experiments.

The repo includes deterministic storm-response and supply-chain simulations. They create agents, route events and messages between them, record state, and write traces. No LLM, vector database, distributed runtime, or external service is required.

The code is intentionally small so the simulation loop can be inspected and tested locally before real model-serving backends are added.

## What Runs Today

- A storm environment that increases severity over time.
- A supply-chain environment with demand, inventory, and shipment-delay pressure.
- A coordinator agent that asks operators for status.
- Hospital and utility agents that report local status.
- Forecaster agents that update the environment summary.
- Supplier, warehouse, transport, and retailer agents for logistics runs.
- In-memory storage for local runs.
- SQLite storage for persisted runs.
- Deterministic mock/rule execution backends.
- Optional Aitta/OpenAI-compatible chat-completions execution backend.

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

Run the supply-chain example:

```bash
PYTHONPATH=src python3 -m agentic_sim.cli run \
  --config configs/supply_chain_small.json
```

Persist a full run artifact with traces and the final environment snapshot:

```bash
PYTHONPATH=src python3 -m agentic_sim.cli run \
  --config configs/storm_scale.json \
  --output data/storm_scale_run.json
```

Write split run artifacts for inspection or dashboard use:

```bash
PYTHONPATH=src python3 -m agentic_sim.cli run \
  --config configs/storm_small.json \
  --output-dir data/runs/storm-small
```

The directory contains `metadata.json`, `config.json`, `summary.json`, `ticks.json`, `environment.json`, `traces.json`, and `backend_metrics.json`.

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
  --scenario storm \
  --steps 50 \
  --agent-replicas 128 \
  --max-batch-size 64
```

Use the Aitta backend through an OpenAI-compatible chat-completions endpoint:

```bash
cp .env.example .env.local
# Edit .env.local and set AITTA_API_KEY plus any model override.

PYTHONPATH=src python3 -m agentic_sim.cli check-aitta

# If Aitta needs to start the model-serving job, poll until it is ready.
PYTHONPATH=src python3 -m agentic_sim.cli check-aitta \
  --wait \
  --wait-timeout 900 \
  --wait-interval 30

PYTHONPATH=src python3 -m agentic_sim.cli run \
  --scenario storm \
  --backend aitta \
  --steps 1 \
  --max-batch-size 1
```

## Adding Scenarios

Scenarios are selected by name through the runtime registry. The current registered scenarios are `storm` and `supply_chain`.

Config files can select a scenario with either form:

```json
{
  "scenario": "storm"
}
```

or:

```json
{
  "scenario": {
    "name": "storm",
    "agent_replicas": 64,
    "parameters": {
      "severity_step": 2,
      "regions": ["helsinki", "oulu", "tampere"]
    }
  }
}
```

To add a new scenario:

1. Implement an environment with `initialize()`, `tick()`, and `apply_actions()`.
2. Define the agent profiles for that scenario.
3. Add a `create_<scenario>_engine()` factory.
4. Register it in `SCENARIOS` in `src/agentic_sim/scenarios/registry.py`.
5. Add a config file under `configs/`.

## Understanding Output

A run prints a compact JSON summary:

- `ticks`: engine loop results.
- `processed_events`: events consumed in that engine step.
- `activations`: agents selected to respond.
- `messages_emitted`: messages produced by agents.
- `traces_written`: trace records written for that engine step.
- `summary.environment_tick`: scenario environment tick.
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

When `--output-dir` is set, the same run data is split into stable JSON files for downstream tools and dashboards.

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
- `environment`: deterministic scenario rules.
- `scenarios`: scenario profiles, engine factories, and registry wiring.
- `engine`: the top-level simulation loop.
- `observability`: trace writing and run summaries.

Additional docs:

- [docs/architecture.md](docs/architecture.md): runtime design.
- [docs/execution_model.md](docs/execution_model.md): activation and execution flow.
- [docs/storage.md](docs/storage.md): storage boundary.
- [docs/scenario_storm.md](docs/scenario_storm.md): storm scenario details.
- [docs/scenario_supply_chain.md](docs/scenario_supply_chain.md): supply-chain scenario details.
- [docs/lumi.md](docs/lumi.md): LUMI batch runs.
- [docs/roadmap.md](docs/roadmap.md): next and future implementation plan.
- [docs/amd_vllm_lumi_tuning.md](docs/amd_vllm_lumi_tuning.md): future AMD/vLLM throughput knobs.

The engine treats reasoning as a pluggable backend behind a stable execution contract. That keeps the simulation inspectable and lets model serving be added later without changing the core loop.

## Current Scope

The current repo does not include:

- distributed execution
- production model-serving orchestration
- training
- vector databases
- real weather data
- dashboards or UI
- multi-node orchestration
