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

When using Aitta, enable warm-up polling so the first request can trigger model startup and the simulation waits until the endpoint responds:

```bash
AITTA_WARMUP=1 \
AITTA_WARMUP_TIMEOUT=900 \
AITTA_WARMUP_INTERVAL=30 \
CONFIG=configs/storm_scale.json \
  sbatch scripts/run_lumi.sh
```

The warm-up uses `agentic-sim check-aitta --wait` and exits non-zero if the model does not become ready before the timeout.

## Slurm Array Sweeps

Use `scripts/run_lumi_array.sh` to run independent configs as separate Slurm array tasks:

```bash
mkdir -p /scratch/project_462000131/anisrahm/agentic-sim-runs/logs
ARTIFACT_ROOT=/scratch/project_462000131/anisrahm/agentic-sim-runs \
  sbatch scripts/run_lumi_array.sh
```

By default the array covers:

- `configs/storm_small.json`
- `configs/supply_chain_small.json`
- `configs/storm_scale.json`
- `configs/supply_chain_scale.json`

Override the sweep with a space-separated `CONFIG_LIST`:

```bash
CONFIG_LIST="configs/storm_small.json configs/supply_chain_small.json" \
STEPS=8 \
BACKEND=aitta \
AITTA_WARMUP=1 \
ARTIFACT_ROOT=/scratch/project_462000131/anisrahm/agentic-sim-runs \
  sbatch --array=0-1 scripts/run_lumi_array.sh
```

Each task writes:

- `${RUN_ROOT}/${SLURM_ARRAY_TASK_ID}_${CONFIG_NAME}/state.sqlite`
- `${RUN_ROOT}/${SLURM_ARRAY_TASK_ID}_${CONFIG_NAME}/run.json`
- `${RUN_ROOT}/${SLURM_ARRAY_TASK_ID}_${CONFIG_NAME}/artifacts/`

The array script refreshes `${RUN_ROOT}/aggregate.json` after each completed task. You can also aggregate manually:

```bash
scripts/aggregate_runs.sh /scratch/project_462000131/anisrahm/agentic-sim-runs/array_<job_id>
```

To choose a specific artifact location:

```bash
ARTIFACT_ROOT=/scratch/project_462000131/anisrahm/agentic-sim-runs \
  sbatch --output=/scratch/project_462000131/anisrahm/agentic-sim-runs/logs/%x-%j.out scripts/run_lumi.sh
```

Each run writes:

- `state.sqlite`: persisted agents, events, messages, environment state, and traces
- `run.json`: tick results, summary, final environment snapshot, and structured traces
- `artifacts/`: split metadata, config, summary, ticks, environment, traces, and backend metrics
- Slurm stdout under `/scratch/project_462000131/anisrahm/agentic-sim-%j.out`, or under the path passed with `sbatch --output`

The `simulation_tick` trace payload includes timing fields for event loading, scheduling, context building, batching, backend execution, result application, environment actions, event persistence, and total step time.

For future vLLM/ROCm serving integration, see `docs/amd_vllm_lumi_tuning.md`.
