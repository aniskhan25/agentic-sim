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
- Next: record model latency, retry count, model name, and validation failures in traces at the simulation-tick level.

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
- Next: tune role prompts for higher-quality model-proposed content instead of relying on the guard for minimal required outputs.

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

Implementation:

- Build an artifact-based dashboard that does not participate in the simulation loop.
- Initial views: run list, summary, environment timeline, events per tick, agent activation counts, message graph, traces table, and backend latency/errors.
- Prefer a simple prototype stack first, such as Streamlit, unless the dashboard needs to become a deployed service.

### 6. Real-data fixtures

Goal: improve scenario realism without adding live API complexity too early.

Implementation:

- Start with replayable CSV or JSON fixtures.
- Storm candidates: weather observations, forecasts, warnings, grid disturbance signals, synthetic hospital capacity.
- Supply-chain candidates: inventory snapshots, lead times, demand time series, transport delays, port or shipment schedules.
- Add ingestion as scenario input fixtures before adding live API clients.

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

Start with the Aitta backend, prompt schemas, and artifact metadata. These unlock the model-serving workflow while preserving the current simulation engine design.
