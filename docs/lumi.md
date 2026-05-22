# LUMI Runs

The runtime is still single-process by design. The LUMI preparation here is for reproducible batch runs, trace capture, and scale smoke tests before adding model-serving backends.

## Local Scale Smoke Test

```bash
PYTHONPATH=src python3 -m agentic_sim.cli run \
  --config configs/storm_scale.json \
  --output data/storm_scale_run.json
```

## Slurm Submission

```bash
sbatch scripts/run_lumi.sh
```

By default, Slurm stdout goes to `/scratch/project_462000131/anisrahm/agentic-sim-%j.out`.
To put stdout under a dedicated logs directory:

```bash
mkdir -p /scratch/project_462000131/anisrahm/agentic-sim-runs/logs
ARTIFACT_ROOT=/scratch/project_462000131/anisrahm/agentic-sim-runs \
  sbatch --output=/scratch/project_462000131/anisrahm/agentic-sim-runs/logs/%x-%j.out scripts/run_lumi.sh
```

Useful overrides:

```bash
CONFIG=configs/storm_scale.json STEPS=50 AGENT_REPLICAS=128 sbatch scripts/run_lumi.sh
```

To choose a specific artifact location:

```bash
ARTIFACT_ROOT=/scratch/project_462000131/anisrahm/agentic-sim-runs \
  sbatch --output=/scratch/project_462000131/anisrahm/agentic-sim-runs/logs/%x-%j.out scripts/run_lumi.sh
```

Each run writes:

- `state.sqlite`: persisted agents, events, messages, environment state, and traces
- `run.json`: tick results, summary, final environment snapshot, and structured traces
- Slurm stdout under `/scratch/project_462000131/anisrahm/agentic-sim-%j.out`, or under the path passed with `sbatch --output`

The `simulation_tick` trace payload includes timing fields for event loading, scheduling, context building, batching, backend execution, result application, environment actions, event persistence, and total step time.

For future vLLM/ROCm serving integration, see `docs/amd_vllm_lumi_tuning.md`.
