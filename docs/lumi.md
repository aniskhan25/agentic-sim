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

Useful overrides:

```bash
CONFIG=configs/storm_scale.json STEPS=50 AGENT_REPLICAS=128 sbatch scripts/run_lumi.sh
```

Each run writes:

- `state.sqlite`: persisted agents, events, messages, environment state, and traces
- `run.json`: tick results, summary, final environment snapshot, and structured traces
- Slurm stdout under `logs/`

The `simulation_tick` trace payload includes timing fields for event loading, scheduling, context building, batching, backend execution, result application, environment actions, event persistence, and total step time.

For future vLLM/ROCm serving integration, see `docs/amd_vllm_lumi_tuning.md`.
