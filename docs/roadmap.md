# Implementation Roadmap

This plan separates near-term prototype work from future work. Keep it updated when the workflow, LUMI assumptions, or scenario priorities change.

## Next Tasks

These tasks are suitable for the next implementation phase.

### 1. Aitta-backed execution backend

Goal: use LUMI's Aitta model serving service for selected agent decisions while keeping the simulation engine unchanged.

Status: initial backend implemented. It posts to the OpenAI-compatible `/chat/completions` endpoint, requests JSON mode, reads Aitta settings from config or environment variables, parses structured JSON proposals, validates messages/actions/events, and records backend metadata on `ExecutionResult`.

Reference:

- `aniskhan25/lumi-aitta-demo-suite` uses Aitta through an OpenAI-compatible chat completions interface.
- Environment variables used there: `AITTA_API_KEY`, `AITTA_BASE_URL`, `AITTA_MODEL`, and `AITTA_REQUEST_TIMEOUT`.
- Example endpoint shape: `https://api-staging-aitta.2.rahtiapp.fi/openai/v1/`.
- Example model: `TinyLlama/TinyLlama-1.1B-Chat-v1.0`.
- The recorded TinyLlama benchmark treats `concurrency=1` as the only reasonable operating assumption on that path; `concurrency=2` had a large p95 latency jump. Start conservative and make concurrency configurable.

Implementation:

- Done: add an `AittaExecutionBackend` behind the existing `ExecutionBackend` protocol.
- Done: use the OpenAI-compatible chat completions API.
- Done: add config fields for backend name, base URL, model, timeout, retries, and concurrency.
- Done: read credentials from environment variables, with config/CLI override support for non-secret settings.
- Done: convert each `ExecutionRequest` into a compact prompt or chat payload.
- Done: require structured JSON output that maps back to `ExecutionResult`.
- Done: validate model output before applying state changes, messages, events, or environment actions.
- Done: record model latency, retry count, model name, and validation failures in traces at the simulation-tick level. The `agent_step` trace carries `latency_seconds`, `retry_count`, and `model`; the `simulation_tick` trace carries an aggregated `backend` summary (total latency, retry count, validation failures, agent steps).

Open information needed:

- Confirm production vs staging base URL for the target LUMI environment.
- Confirm available model names and any project-specific limits.
- Confirm whether Aitta supports response-format/schema constraints; otherwise use prompt-only JSON plus local validation.

### 2. Prompt and policy schemas

Goal: define stable model-facing contracts per scenario and role.

Status: initial role policies implemented in the Aitta backend. Prompts now include per-scenario and per-role requirements, and a deterministic policy guard fills missing required coordination messages/actions when the model is passive or returns malformed JSON.

Implementation:

- Done: add role-policy prompt context for storm coordinator, storm operators, forecaster, and supply-chain roles.
- Done: define allowed message types and environment actions per role.
- Done: keep deterministic validators and policy guards for model-proposed or missing actions.
- Done: add tests with fixed model responses to prove parsing, validation, and passive-model fallback behavior.
- Done: tune role prompts for higher-quality model-proposed content. Three changes: (1) system prompt no longer suppresses payload content; (2) `response_shape` is now built dynamically per role and scenario, showing a concrete example with actual environment values (severity, regions, risk level, demand); (3) each role requirement carries `payload_guidance` specifying which context fields to include.

### 3. Run metadata and operational artifacts

Goal: make each prototype run reproducible and easy to inspect.

Status: implemented for local and LUMI runs through `--output-dir`.

Implementation:

- Done: generate a run ID for artifact-directory runs.
- Done: write a per-run output directory when `--output-dir` is provided.
- Done: save config snapshot, git commit hash, run summary, traces, final environment state, and backend metrics.
- Done: keep the existing single-file `--output` path for compatibility.
- Done: add a small Aitta connectivity check command after the backend exists.
- Done: add Aitta warm-up polling for cold starts before LUMI simulations.

### 4. LUMI prototype runner

Goal: scale by running many independent simulations, not by distributing one simulation run.

Status: implemented as a SLURM array runner plus artifact aggregation.

Implementation:

- Done: add a SLURM array script for config sweeps.
- Done: keep one process per simulation run.
- Done: write one artifact directory per array task.
- Done: add aggregation support that reads completed run summaries and backend metrics.
- Next: add seed/parameter matrix generation if configs alone are not enough for sweeps.

### 5. Dashboard prototype

Goal: provide a read-only view of run artifacts.

Status: implemented as a Streamlit app at `scripts/dashboard.py`. Install deps with `pip install "agentic-sim[dashboard]"`, launch with `streamlit run scripts/dashboard.py -- --root-dir /path/to/output`. Supports both split artifact directories (`--output-dir`) and monolithic `run.json` files (`--output`).

Implementation:

- Done: build an artifact-based dashboard that does not participate in the simulation loop.
- Done: Summary tab — agent activation bar chart and messages-sent-per-agent.
- Done: Tick timeline tab — events/activations/messages line chart; per-tick backend latency and summary table.
- Done: Backend tab — latency min/avg/max, token usage, invalid outputs, policy-guard additions, per-step latency table for Aitta runs.
- Done: Traces tab — filterable dataframe by event type with raw JSON expander.
- Done: Config & environment tab — final environment state, run config, run metadata.
- Done: All runs tab — multi-run comparison table with avg latency and error counts.
- Next: add message graph (requires sender→recipient pairs in traces; currently traces record message count only).

### 6. Real-data fixtures

Goal: improve scenario realism without adding live API complexity too early.

Status: implemented as replayable JSON fixtures with per-tick replay sequences for both scenarios.

Implementation:

- Done: add `FixtureLoader` (`scenarios/fixtures.py`) that reads and validates fixture JSON, exposing `initial` state overrides and a `ticks` replay list. `FixtureLoader.load_if_configured()` activates when `scenario_parameters["fixture"]` is set.
- Done: add `initial_variables` and `tick_data` optional params to `StormEnvironment` and `SupplyChainEnvironment`. `initialize()` merges initial overrides; `tick()` reads fixture entry at `state.tick`, falls back to computed progression when exhausted. All changes are backward-compatible.
- Done: update scenario factories to load the fixture and pass initial/tick data to the environment.
- Done: storm fixture `data/fixtures/storm_helsinki_oulu.json` — 6-tick Gulf of Finland winter storm (severity 2→3→4→5→4→3), per-tick affected region and weather observation.
- Done: supply-chain fixture `data/fixtures/supply_chain_nordic.json` — 6-tick Nordic port-congestion and demand-surge with absolute demand, delayed_shipments, and inventory snapshots (shortage peak and recovery arc).
- Done: `configs/storm_fixture.json` and `configs/supply_chain_fixture.json` for ready-to-use runs.
- Next: add more fixture variants (different severities, multi-region storms, longer supply-chain disruptions) as scenario coverage needs grow.
- Next: add live API client ingestion once fixture schemas are stable.

## Future Tasks

These are useful, but should wait until the next tasks expose a concrete need.

### Distributed simulation execution

Do not distribute a single run initially. Aitta should own distributed model serving, and SLURM arrays should handle many independent simulation runs.

Revisit only if one simulation tick has too many activations for a single process to dispatch efficiently. A later design would use one driver process to own state transitions and worker processes to produce `ExecutionResult` objects.

### Training or fine-tuning

Not needed for the current workflow if pretrained models served by Aitta produce valid and useful decisions.

Revisit only if prompting, validation, and retrieval cannot achieve reliable structured decisions, or if traces are intentionally collected for policy imitation and evaluation.

### Vector DB or RAG

Not needed for the current deterministic scenarios.

Revisit when agents need large or frequently changing external documents, such as response playbooks, hospital surge procedures, utility restoration manuals, supplier contracts, procurement policies, or incident reports. Try simple file or keyword retrieval before adding a vector database.

### Live real-data integrations

Do not start with live APIs. Fixture replay is easier to test and reproduce.

Revisit live integrations after scenario behavior and fixture schemas are stable.

### Production operational tooling

Initial tooling should stay artifact-based. Avoid workflow engines, distributed databases, service registries, or production monitoring stacks until the prototype has repeated runs and clear operational pain.

## Current Recommendation

Tasks 1–6 are complete. The remaining near-term work is:

- **Task 4** (one item): add seed/parameter matrix generation for SLURM sweeps if config files alone are not flexible enough.
- **Task 5 follow-on**: message graph view in the dashboard once sender→recipient pairs are recorded in traces.
- **Task 6 follow-on**: add more fixture variants and eventually live API ingestion once fixture schemas are stable.
