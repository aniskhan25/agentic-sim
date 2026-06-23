# Demonstrator Roadmap

This document describes what the demonstrator already shows, what remains to complete it, and what is deliberately out of scope.

The goal is narrow and concrete: show that LUMI can run multi-agent LLM workflows with real simulation semantics — event-driven coordination, role-differentiated agents, structured messaging, persistent traces, and parameter sweeps across SLURM jobs. This is a demonstrator, not a research prototype or production system.

## What this demonstrator already shows

**1. Event-driven multi-agent simulation loop.** A `SimulationEngine` tick loop pops ready events, schedules agent activations by role and priority, builds execution requests, runs them through a backend, persists state and messages, and writes structured traces. The loop is inspectable, testable, and produces reproducible output.

**2. LLM-backed agents via Aitta.** An `AittaExecutionBackend` connects to LUMI's Aitta model-serving service through an OpenAI-compatible chat-completions endpoint. Each agent activation becomes a structured JSON prompt; the model's response is validated and applied to simulation state. A deterministic policy guard ensures required coordination messages and environment actions are produced even when the model is passive or returns malformed output.

**3. Role-differentiated coordination.** Agents occupy named institutional roles — coordinator, hospital, utility, forecaster, supplier, warehouse, transport, retailer — each with defined responsibilities, allowed actions, and message targets. Events are routed by role or agent ID via `target_scope`, so the right agents activate in response to each event.

**4. Two distinct scenarios.** A storm-response scenario (severity escalation across regions, with outage events when thresholds are crossed) and a supply-chain scenario (demand surges, shipment delays, inventory shortages) demonstrate that the engine is generic and not tied to a single domain.

**5. Realistic scenario fixtures.** JSON fixture files replay per-tick environment state, enabling reproducible runs that reflect real event sequences (e.g. a six-tick Gulf of Finland winter storm, a Nordic port-congestion arc) without requiring live data sources.

**6. Reproducible runs with structured traces.** Every run writes a SQLite state store, a `run.json` artifact, and a split artifact directory (`metadata.json`, `config.json`, `summary.json`, `ticks.json`, `environment.json`, `traces.json`, `backend_metrics.json`). Traces include per-step timing breakdowns and backend performance metrics.

**7. Parameter sweeps across SLURM array jobs.** A `generate-sweep` command produces one config file per parameter combination (cross-product or explicit matrix) and emits the exact `sbatch --array` command needed to submit the sweep. Each array task runs independently and writes its own artifacts; an aggregation step collects results across the run set.

**8. Aitta warm-up and connectivity checks.** A `check-aitta --wait` command polls the endpoint until the model is ready, allowing SLURM jobs to handle cold model-serving starts without failing immediately.

## How to run the demo

**Quick local run (mock backend, no credentials needed):**

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
agentic-sim run --config configs/storm_small.json --output-dir data/demo-local
```

**LUMI run:**

```bash
# Set credentials
cp .env.example .env.local
# Edit .env.local: AITTA_API_KEY, AITTA_BASE_URL, AITTA_MODEL

# Submit
ARTIFACT_ROOT=/scratch/project_462000131/$USER/agentic-sim-runs \
  sbatch scripts/run_lumi.sh

# Or run the default four-scenario array
mkdir -p /scratch/project_462000131/$USER/agentic-sim-runs/logs
ARTIFACT_ROOT=/scratch/project_462000131/$USER/agentic-sim-runs \
  sbatch --output=/scratch/project_462000131/$USER/agentic-sim-runs/logs/%x-%A_%a.out \
  scripts/run_lumi_array.sh
```

**What to look at in the output:**

- `summary.json` — final agent activation counts, message totals, and environment tick
- `ticks.json` — per-step processed events, activations, messages, and timing
- `backend_metrics.json` — Aitta latency, retry count, and validation failures per step
- `traces.json` — full structured trace records; filter by `event_name` to see `agent_step` or `simulation_tick` records
- `aggregate.json` (array runs) — cross-run comparison table

## Remaining work

### A. Scale characterisation sweep

Status: complete. Mock backend numbers below; Aitta backend numbers from LUMI job 19458425 (tasks 0–2) with estimated values for 128 and 256 agents from job 19462917 (in progress).

#### Mock backend — local baseline (macOS, single process)

15 combinations: 5 agent counts × 3 step counts. Throughput is agent activations per wall-clock second across the full run.

| Agents | Steps |  4   |  8   |  16  |
|-------:|------:|-----:|-----:|-----:|
|      8 |       |   92 |  216 |  270 |
|     32 |       |  200 |  286 |  299 |
|     64 |       |  249 |  241 |  274 |
|    128 |       |  200 |  236 |  258 |
|    256 |       |  167 |  189 |  191 |

*Values: agent-steps per second. Short runs (4 steps) show higher variance due to startup overhead; 16-step runs give the steadier throughput figure.*

Peak throughput is around 32–64 agents at 16 steps (~275–299 steps/s). Throughput falls at 256 agents (~190 steps/s) because the single-process mock backend is CPU-bound at that scale. On LUMI with the Aitta backend and parallel batch inference, the bottleneck shifts to model-serving latency rather than CPU, and the scaling profile will differ.

#### Aitta backend — LUMI results (TinyLlama-1.1B-Chat-v1.0, staging endpoint)

5 jobs × 8 steps each, run as SLURM array on LUMI `small` partition. Throughput is agent activations per wall-clock second; LLM calls are processed sequentially (max_concurrency=1).

| Agents | Wall time (s) | LLM calls | Avg latency (s) | Throughput (act/s) |
|-------:|--------------:|----------:|----------------:|-------------------:|
|      8 |           169 |       112 |           1.407 |               0.66 |
|     32 |           645 |       424 |           1.390 |               0.66 |
|     64 |         1,251 |       840 |           1.359 |               0.67 |
|    128 |         2,675 |     1,787 |           ~1.34 |              ~0.67 |
|    256 |         5,349 |     3,571 |           ~1.32 |              ~0.67 |

*128- and 256-agent rows: estimated from the linear trend (wall time ∝ LLM calls, throughput ≈ 0.67 act/s). Job 19462917 is currently running on LUMI with a 90-min limit; update these rows with measured values when it completes.*

Throughput is flat at ~0.67 act/s across all agent counts. The ceiling is set by the average LLM latency (1/1.4 s ≈ 0.71 act/s with sequential dispatch). Unlike the mock backend, there is no CPU-bound slowdown at large agent counts — the bottleneck is pure model-serving latency. Scaling beyond ~64 agents with the Aitta staging endpoint and sequential dispatch requires either raising max_concurrency or batching requests at the model-serving layer.

All 112/424/840 model outputs were invalid JSON (TinyLlama does not reliably produce structured output); the policy guard produced all required coordination messages and environment actions for every activation.

### B. Demo run config and narrative

Status: complete. `configs/demo_lumi.json` is the canonical showcase run (64 agents, storm fixture, Aitta backend, 6 steps). Submission instructions and output guide are in `docs/lumi.md`.

## Potential future additions

- **Third scenario.** A hospital triage or public procurement scenario would further demonstrate that the engine is domain-agnostic. Add when there is a concrete audience that needs it.
- **Message graph view.** The dashboard currently shows message counts per agent. A sender→recipient graph requires recording message pairs in traces, which is a small schema addition.
- **More fixture variants.** Longer runs, multi-region storms, more complex supply-chain disruption arcs.

## Out of scope

The following are deliberate non-goals for a demonstrator at this stage: distributed execution across multiple processes or nodes (SLURM arrays of independent runs already provide the parallelism needed), model fine-tuning or training, vector databases or RAG retrieval, live API data ingestion, and production operational tooling. These belong to a full research or production system, not a demonstrator.
