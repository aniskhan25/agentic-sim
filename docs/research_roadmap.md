# Research Roadmap: Portable Causal Execution for Agent Simulations

## Purpose

The demonstrator established that an event-driven multi-agent simulation can run through a managed LLM service from a Slurm job and produce persistent, inspectable artifacts. The research phase turns that implementation into an infrastructure-agnostic system.

The primary research contribution is:

> A provider-neutral, capability-aware causal scheduler that exposes safe concurrency in event-driven LLM-agent simulations while preserving an explicit observational semantics across heterogeneous inference infrastructures.

The common activation representation, causal verifier, contract and provenance model, and atomic commit protocol are enabling mechanisms needed to state and test that contribution. AMD MI250X-based LUMI and NVIDIA GH200-based Roihu are controlled evaluation substrates, not the contribution itself.

The implementation must also be a maintainable reference artifact: explicit module boundaries, isolated infrastructure adapters, understandable control flow, typed contracts, testable components, and measured performance. These are engineering and artifact-quality requirements rather than separate novelty claims.

Canonical companion specifications:

- [target_architecture.md](target_architecture.md) owns component boundaries, observational semantics, atomic commit, and delivery gates;
- [evaluation_plan.md](evaluation_plan.md) owns workloads, hypotheses, experimental controls, metrics, and statistical comparisons;
- [adr/](adr/) contains binding architecture decisions.

## Research Questions

### RQ1: Portable semantics

Can one simulation specification execute unchanged across heterogeneous inference and storage systems while preserving event dependencies, state transitions, and declared invariants?

### RQ2: Safe concurrency

How much parallelism can be extracted without changing the workload's declared observation projection or required `happens-before` relationships?

### RQ3: Reliable generative execution

How should the runtime distinguish model proposals from repaired, policy-completed, and fallback behavior, and how do those interventions affect reliability, autonomy, diversity, and cost?

### RQ4: Infrastructure sensitivity

Which workload and provider-capability properties determine effective scheduling and serving configurations across local, managed, AMD/ROCm, and NVIDIA/CUDA execution?

## Contribution Hierarchy and Decision Gate

The first paper should present one central claim, but the headline remains a testable working hypothesis until the scheduler ablations are complete:

> A provider-neutral scheduler that combines causal readiness with provider capabilities, queue state, and reusable-prefix grouping improves useful throughput relative to a generic causal-ready scheduler while preserving declared observational semantics across local, AMD/ROCm, and NVIDIA/CUDA inference infrastructures.

The contribution hierarchy is:

1. **Primary contribution:** the capability-aware causal scheduling policy and its semantics-preservation argument.
2. **Enabling mechanisms:** the activation representation, causal verifier, contract and provenance model, and atomic idempotent commit.
3. **Evidence:** controlled workload ablations and normalized within-system results on LUMI and Roihu.
4. **Artifact quality:** maintainable boundaries, conformance suites, reproducible manifests, and understandable extension points.

Portability, contracts, and architecture support the scheduling claim; they are not presented as unrelated contributions of equal novelty.

Before Phase 6 confirmatory experiments, define a minimum practically meaningful improvement, required workload coverage, and uncertainty criterion for the full scheduler relative to the causal-only baseline.

- If the full scheduler clears that preregistered gate without additional correctness violations, retain the scheduler-led hierarchy above.
- If it does not, do not claim generic causal scheduling as novel. Reframe the first paper around explicit observational semantics and measurable reliability intervention across heterogeneous infrastructure, with scheduling as an evaluated systems mechanism.

The fallback headline would be:

> A provider-neutral contract and provenance model makes model proposals, repair, policy completion, fallback, invariant compliance, and retained model autonomy explicitly comparable across heterogeneous LLM-agent simulation infrastructures.

This decision gate keeps the headline evidence-led while preserving one coherent paper in either outcome.

Possible titles:

- *Portable Causal Execution for Event-Driven LLM-Agent Simulation*
- *An Infrastructure-Agnostic Runtime for Reproducible and Reliable LLM-Agent Simulations*
- *Useful Agent Steps: Semantics-Preserving Scheduling Across Heterogeneous LLM Infrastructure*

## Engineering Objective

A reader should be able to locate and answer:

- what the simulation semantics are;
- what makes an activation causally ready;
- which execution policy selected and placed it;
- which provider executed it;
- which behavior originated from the model, repair, policy completion, or fallback;
- where and under which state version it committed;
- which component caused observed latency or failure.

Maintainability is evaluated through dependency conformance, component tests, reproducible examples, and change isolation. Performance is evaluated through separate benchmarks; abstraction is never assumed free.

## Design Principles

1. **Simulation semantics are independent of inference transport.**
2. **Logical time is independent of wall-clock time.**
3. **Generated and enforced behavior remain distinguishable.**
4. **Scheduling consumes capabilities rather than provider names.**
5. **Every applied result is reproducible or auditable.**
6. **Performance is measured as useful, contract-satisfying work.**
7. **Single-process causal scheduling precedes distributed state.**
8. **Cross-system claims use matched controls and normalized effects.**
9. **Dependencies point toward semantics.**
10. **One atomic commit boundary owns all state mutation.**
11. **Abstractions must earn their complexity and performance cost.**

## Architecture Summary

The canonical design is specified in [target_architecture.md](target_architecture.md). Its stable execution path is:

```text
scenario and environment
        -> activation specification
        -> capability-aware causal plan
        -> provider-neutral execution
        -> proposal validation and intervention
        -> atomic idempotent commit
        -> execution receipt
```

Four architecture invariants are non-negotiable:

1. scenario and domain code never select infrastructure;
2. schedulers plan but do not execute or mutate;
3. adapters translate but do not define simulation policy;
4. state transitions, messages, events, causal-frontier advancement, idempotency, provenance, and the receipt commit atomically.

The observation projection and strict, causal, and relaxed equivalence modes are defined in the architecture specification before asynchronous execution begins. Fresh-model runs preserve causal and contract invariants but report divergence rather than claiming textual equality.

## Delivery Phases

Each phase is complete only when its tests, artifacts, documentation, architecture gates, and performance gates are present.

### Phase 0: Freeze the demonstrator baseline

**Goal:** Preserve the current system as a reproducible reference.

Work:

- version representative storm and supply-chain configurations;
- preserve sequential FIFO as the reference policy;
- export representative deterministic and Aitta traces;
- define event, activation, proposal, validated result, commit, policy completion, fallback, and useful agent step;
- record repository revision, test inventory, configuration, fixture, and expected summaries in a baseline manifest.

Exit criteria:

- all tests captured by the versioned baseline manifest remain green;
- deterministic behavior signatures are committed;
- baseline runs reproduce from documented commands.

### Phase 1: Establish architecture decisions and boundaries

**Goal:** Settle semantics and dependency direction before substantial scheduler work.

Work:

- accept ADR 0001 covering observation equivalence, activation identity, receipt ownership, and atomic commit;
- define provider-neutral proposal, validation result, activation, execution receipt, and platform-manifest types;
- define narrow execution, state-store, clock, and telemetry ports;
- record and automate the dependency rules from [target_architecture.md](target_architecture.md);
- retain compatibility shims while modules migrate one vertical boundary at a time.

Exit criteria:

- the first ADR is accepted;
- public boundary types are typed and covered by contract tests;
- automated checks reject provider or platform imports in domain and runtime policy;
- deterministic baseline behavior remains unchanged.

### Phase 2: Separate provider transport from simulation policy

**Goal:** Remove Aitta-specific coupling from behavioral semantics.

Work:

- extract role, scenario, repair, policy-completion, and fallback behavior from `AittaExecutionBackend`;
- retain Aitta as one OpenAI-compatible adapter;
- replace `aitta_*` scheduling assumptions with generic capabilities and connection configuration;
- route deterministic, rule, and LLM proposals through the same validation pipeline;
- normalize provider failures and preserve configuration compatibility during migration.

Exit criteria:

- no scenario-specific policy remains in provider transport;
- adding a simulated OpenAI-compatible adapter requires no scenario or validation changes;
- shared proposal and adapter conformance suites pass;
- traces distinguish model, repair, policy-completion, and fallback origins.

### Phase 3: Define contracts and useful-work metrics

**Goal:** Make reliability requirements declarative and measurable.

Initial contract forms:

- `must` and `must_not`;
- `bounded` and `allowed`;
- logical-time `deadline`;
- output `cardinality`.

Work:

- define contracts outside prompts and provider code;
- separate schema validation, semantic validation, repair, policy completion, rejection, and fallback;
- inject malformed JSON, missing outputs, prohibited actions, timeouts, and duplicate results;
- record one origin for every committed behavior atom.

A behavior atom is one normalized message, environment action, or state mutation. If \(C\) is the multiset of committed atoms and \(R\) contains atoms retained unchanged in type, target, and value from the original proposal:

> **Model autonomy rate:** \(|R| / |C|\).

An empty \(C\) produces an unavailable rate and explicit zero count. Fully autonomous activation rate, proposal validity, repair, policy completion, fallback, rejection, and invariant compliance remain separate metrics.

The primary systems metric is:

> **Useful agent steps per second:** committed activations satisfying their contracts, reported with autonomy, fallback, and correctness.

Exit criteria:

- existing scenarios have provider-independent contracts;
- fault injection covers every validation outcome;
- artifacts reconstruct autonomy numerator, denominator, and per-origin counts;
- rules-only and invalid-model runs remain distinguishable even when final state matches.

### Phase 4: Build causal semantics and the minimum workload kernel

**Goal:** Make ordering constraints explicit and establish representative workloads before concurrency.

Work:

- add causal parents and version agent and environment state;
- define `happens-before` for triggers, messages, environment actions and reads, repeated agent activations, and barriers;
- define conservative read/write conflicts;
- implement causal-graph artifacts and a verifier for missing parents, conflicts, stale reads, duplicates, and cycles;
- implement seeded chain, fan-out, fork/join, independent-branch, mixed-DAG, and conflicting-write workloads;
- record component-level scheduler, validation, commit, storage, serialization, and tracing baselines.

Execution modes:

- **strict:** identical canonical committed trace to the sequential reference;
- **causal:** equivalent observation projection and required partial order, allowing independent topological reorderings;
- **relaxed:** only workload-declared bounded divergence.

Exit criteria:

- strict deterministic runs retain the baseline signature;
- the verifier detects injected violations and accepts normal runs;
- the minimum kernel reproduces expected graphs, conflicts, and invariants;
- component costs are measured before asynchronous scheduling.

### Phase 5: Introduce asynchronous provider execution

**Goal:** Put concurrency control in the runtime rather than individual providers.

Work:

- define runtime submit/poll or asynchronous execution with a synchronous adapter;
- add cancellation, timeout, retry, backpressure, and bounded queues;
- separate dispatch completion from commit;
- implement the atomic state-store commit unit and idempotent result application;
- expose dispatch, queue, validation, and commit timing.

Baseline policies:

1. sequential FIFO;
2. naive concurrent dispatch;
3. barrier-based batching;
4. causal concurrent dispatch.

Exit criteria:

- provider and store conformance suites pass;
- duplicate, late, interrupted, or partially written results cannot commit twice;
- sequential execution reproduces the deterministic baseline;
- naive and causal concurrency run identical workloads.

### Phase 6: Implement capability-aware causal scheduling

**Goal:** Determine whether capability-aware scheduling contributes beyond generic causal-ready execution.

Inputs may include:

- causal readiness and state conflicts;
- priority and logical deadline;
- prefix or role similarity;
- predicted input and output length;
- context, batch, and concurrency limits;
- provider queue depth;
- recent validation rates;
- retry and fallback budgets.

Start with an explainable full heuristic:

1. select causally ready, non-conflicting activations;
2. order critical work by priority and deadline;
3. group remaining work by provider requirement and reusable prefix;
4. respect capability and queue snapshots;
5. apply bounded backpressure.

Learned scheduling is deferred until the heuristic and its ablations are understood.

Required policy ladder:

1. sequential FIFO;
2. naive concurrent dispatch;
3. barrier-based batching;
4. **causal-only:** causal readiness and state conflicts, with no provider-capability, queue, or prefix optimization;
5. causal plus capability-constrained placement and batching;
6. causal plus provider-queue awareness and backpressure;
7. full scheduler with reusable-prefix grouping.

The causal-only policy is the generic scheduling baseline. Sequential FIFO measures the total value of concurrency; causal-only versus full scheduling measures the incremental contribution being considered for novelty.

Exit criteria:

- decisions are recorded and explainable;
- causal scheduling produces no verifier failures on the kernel or scenario workloads;
- ablations separately measure causal reordering, capability constraints, batching, provider-queue awareness, backpressure, and prefix grouping;
- scheduler overhead is reported and does not dominate short deterministic runs.
- the preregistered contribution gate is evaluated and the paper hierarchy is retained or reframed accordingly.

### Phase 7: Add portable replay and recovery

**Goal:** Reproduce analysis and resume safely across failures and providers.

Work:

- support deterministic, response, fresh-model, and recovery replay;
- store requests and responses content-addressably;
- checkpoint the committed causal frontier;
- resume across termination and wall-time boundaries;
- record provider and model drift.

Exit criteria:

- killed runs resume without duplicate state transitions, messages, or events;
- response replay reproduces the committed observation projection;
- fresh-model replay preserves workload identity and reports divergence.

### Phase 8: Complete the publication workload suite

**Goal:** Expand the minimum kernel into controlled workload families.

The canonical workload dimensions and required artifacts are in [evaluation_plan.md](evaluation_plan.md). The publication suite includes deterministic kernels, storm, supply chain, synthetic DAGs, and injected-failure workloads.

Exit criteria:

- every family runs through deterministic and OpenAI-compatible adapters;
- workload characteristics are reported before provider results;
- raw per-run artifacts and aggregates are generated by one documented workflow;
- workload identity and expected invariants are versioned.

### Phase 9: Evaluate LUMI and Roihu

**Goal:** Test semantic portability and normalized scheduler effects across AMD/ROCm and NVIDIA/CUDA HPC systems without unsupported vendor claims.

The canonical methodology is in [evaluation_plan.md](evaluation_plan.md). It has three layers:

1. deterministic and response-replay runtime semantics;
2. controlled self-hosted inference;
3. end-to-end simulation.

Controlled inference has two separately reported modes:

- **common denominator:** identical model, BF16, decoding, workload, and largest stable shared serving feature set;
- **platform tuned:** identical model and workload semantics with independently tuned stable serving configurations selected before primary collection.

The prespecified contrasts are causal-only versus sequential execution for the value of safe concurrency, and full capability-aware versus causal-only execution for the proposed incremental contribution. Both are measured within the same system, model, placement, serving mode, and workload. Absolute cross-system measurements are delivered-system observations and are not attributed to accelerator vendor alone.

Exit criteria:

- LUMI and Roihu run the same versioned workload and scenario definitions;
- at least one identical model revision runs in BF16 on both;
- sequential, causal-only, full capability-aware, and the required intermediate ablations run on both;
- common-denominator and tuned modes are labeled separately;
- results report uncertainty together with reliability, autonomy, and causal correctness;
- platform manifests record all material differences;
- controlled results remain separate from shared-service observations.

### Phase 10: Paper and artifact release

**Goal:** Produce a reviewable and reproducible research artifact.

Paper structure:

1. motivation and problem;
2. observational and causal semantics;
3. activation representation, contracts, and atomic commit;
4. capability-aware causal scheduler;
5. implementation;
6. benchmark methodology;
7. cross-infrastructure evaluation;
8. limitations and validity threats.

Artifact requirements:

- tagged source revision and environment locks or containers;
- ROCm/x86 and CUDA/ARM deployment manifests;
- accepted ADRs and dependency reports;
- public extension examples for providers, scenarios, contracts, and stores;
- versioned workloads and fixtures;
- raw immutable runs, aggregation scripts, and machine-readable tables;
- documented commands for every figure and table;
- causal-verifier, atomic-commit, and adapter-conformance tests.

Exit criteria:

- every result is reproducible from referenced raw artifacts and scripts;
- the minimum artifact runs without proprietary or managed services;
- archived traces make managed and HPC results inspectable when rerunning is unavailable.

## Minimum Publishable Scope

Required:

- explicit observational semantics;
- provider-neutral activation and execution interfaces;
- contracts and per-atom provenance;
- causal activation graph and verifier;
- sequential, naive-concurrent, barrier, causal-only, and full capability-aware execution;
- atomic idempotent commit and receipts;
- enforced dependency boundaries and conformance suites;
- deterministic, storm, supply-chain, synthetic-DAG, and failure workloads;
- deterministic/replay evaluation and controlled LUMI/Roihu evaluation;
- one identical model revision and common precision on both systems;
- common-denominator results and separately labeled tuned results;
- reliability-aware useful-work metrics;
- raw artifacts and aggregation scripts.

Deferred:

- distributed state across nodes;
- learned scheduling;
- live external data;
- model training or fine-tuning;
- broad application-domain collections;
- production authentication and tenancy;
- a new inference server.

## Positioning and Non-Claims

Do not claim that:

- an HTTP request from Slurm is itself HPC scaling;
- Slurm arrays distribute one simulation;
- provider portability alone is novel;
- policy-completed behavior is model-generated;
- raw activations or messages prove validity;
- a shared endpoint provides controlled hardware measurements;
- absolute LUMI-versus-Roihu differences isolate GPU-vendor effects;
- one MI250X GCD and one GH200 GPU are equivalent;
- toy scenarios establish real-world domain validity.

When supported, claim that:

- one execution representation spans heterogeneous providers;
- the scheduler exposes concurrency while preserving declared observations;
- contracts and interventions are explicit and measurable;
- normalized scheduler effects can be tested across accelerator ecosystems;
- workload and provider capabilities affect useful throughput;
- the artifact makes those conclusions reproducible.

## Principal Risks

### Contribution appears to be framework integration

Center the paper on the decision-gate path supported by evidence: either incremental capability-aware scheduling effects or explicit reliability intervention and provenance. In both cases, use observational semantics, atomic commit, controlled baselines, and ablations to distinguish the contribution from framework APIs.

### Scheduler resembles generic dataflow or conflict-aware execution

Do not claim dependency tracking, topological readiness, or conflict detection as novel by themselves. Evaluate the full scheduler against a causal-only baseline that has the same dependency and conflict information but none of the capability, batching, queue, backpressure, or prefix optimizations. Report the incremental effect of each feature in the required policy ladder. If those effects do not clear the preregistered contribution gate, use the reliability-and-semantics-led paper framing instead.

### Architecture work displaces research

Implement only boundaries required to test scheduling, semantics, contracts, portability, and recovery. Defer speculative plugin systems and repository-wide rewrites.

### Abstraction harms clarity or performance

Keep ports narrow, retain an explicit pipeline, require a real test boundary or second implementation, and measure hot-path costs.

### Contracts conceal loss of model agency

Report per-origin behavior, autonomy, repair, policy-completion, fallback, validity, and rules-only baselines together.

### Platform comparison is confounded

Use within-system primary contrasts, distinguish common-denominator from tuned modes, freeze selection procedures, and record complete manifests.

### Software maturity dominates hardware behavior

Record supported kernels and serving features. Treat instability or unsupported functionality as a result, not something to hide through post hoc substitutions.

### Scope expands into a distributed system

Complete provider separation, semantics, atomic commit, verification, and single-process scheduling before distributed state.

## Immediate Next Actions

Verified foundations already present in the repository:

- role-policy definitions and policy-completion helpers have been extracted into `execution/role_policy.py`;
- storm and supply-chain `must` requirements and initial `must_not` enforcement exist;
- aggregate autonomy for retained messages and environment actions is recorded and covered by tests.

The current autonomy implementation does not yet attach provenance to every atom, include state mutations, or represent the empty-commit case as unavailable. Until that work is complete, it should be described as **message/action autonomy**, not the full behavior-atom metric.

Execute the next cycle in this order:

1. ~~Freeze baseline artifacts, terminology, test inventory, and performance signatures.~~ **Done** — `docs/baseline/manifest.json` (repository revision, test inventory, config hashes, storm and supply-chain behavior signatures, reproduction commands) and `docs/glossary.md` (event, activation, proposal, validated result, commit, policy completion, fallback, useful agent step).
2. ~~Write and accept ADR 0001 for observational equivalence, activation identity, receipt ownership, and atomic commit.~~ **Done** — `docs/adr/0001-observational-semantics-and-commit.md`, status `Accepted`.
3. ~~Define proposal, validation result, activation, receipt, and platform-manifest types.~~ **Done** — `models/proposal.py`, `validation.py`, `receipt.py`, `platform_manifest.py`, `Activation.attempt_number`, `execution/capabilities.py`, wired additively into `AittaExecutionBackend._result_from_proposal`.
4. ~~Define narrow execution, store, clock, and telemetry ports.~~ **Done** — execution (`execution/base.py`'s `ExecutionBackend`) and store (`state/base.py`'s `RuntimeStore`/sub-protocols) already existed and were already the types `SimulationEngine` depended on; this round added the two real gaps: `Clock` (`engine/clock.py`) and `Telemetry`/`LocalTelemetry` (`observability/base.py`), both wired into `SimulationEngine` with zero behavior change to the default path.
5. ~~Record the target dependency rule and add lightweight automated boundary checks.~~ **Done** — `target_architecture.md`'s new "Current-Layout Dependency Mapping" section maps target layers onto current files and states the one rule enforced today (domain packages `models/`/`utils/` never import outer layers), checked by `tests/test_architecture_boundaries.py`. The known deviation (`scenarios/` selecting concrete adapters directly) is documented, not fixed — that's a real migration, out of scope here.
6. ~~Complete provider-neutral contract schemas and per-atom provenance for messages, environment actions, and state mutations.~~ **Done** — `bounded` (`role_policy.enforce_bounded`) and `cardinality` (`role_policy.enforce_cardinality`) contracts added; both close real correctness bugs, not just metrics gaps (unbounded model-proposed deltas could corrupt environment state; duplicate model-proposed actions were double-applied, e.g. inventory `+10` twice instead of once — verified fixed end-to-end, not just counted). State-mutation provenance now tracked (`ValidationResult.state_mutation_provenance`) and the system-managed `working_memory` keys (`last_event_type`, `last_environment_tick`) can no longer be silently overwritten by a model proposal. `allowed` confirmed already satisfied by the existing `allowed_environment_actions`/`action_outside_allowed_set` mechanism (documented, no new code). `deadline` explicitly deferred — no async/multi-tick execution exists yet to make a "late" case possible, so it would be untestable dead code until Phase 4/5.
7. ~~Align empty-commit autonomy reporting with the target definition and retain a separately labeled message/action-only compatibility metric if needed.~~ **Done** — renamed `autonomy_rate` to `message_action_autonomy_rate` everywhere (field, metadata, `backend_metrics.json`, `aggregate_run_stats` output), matching `evaluation_plan.md`'s existing instruction to label it distinctly from the full behavior-atom metric. Empty commits now report `None` (unavailable) instead of a fake `1.0`, plus an explicit `message_action_committed_atom_count`. No second/full metric was built — folding in item 6's new state-mutation provenance would only inflate the rate with no real signal, since state mutations have no policy-completion counterpart to contrast against (documented reasoning in `evaluation_plan.md`).
8. ~~Add causal parents, state versions, and the causal verifier.~~ **Done** — `Message.origin_activation_id`/`Event.causal_parent_activation_id` track the message-mediated causal chain; `AgentState.version`/`EnvironmentState.version` are real, monotonically incremented fields (this surfaced and fixed a real latent bug: both `aitta_backend.py::_updated_state` and `mock_backend.py::_update_state` silently dropped the incremented version when rebuilding the next `AgentState`). `observability/causal_verifier.py` implements four checks — duplicates, missing parents, cycles, stale-reads/conflicts — scoped to the message-mediated chain only (not yet event-level, since events have a legitimate root case — environment ticks — that the trace log can't yet distinguish from a derived event without carrying `EventType`; documented as a known, deliberate scope limit, not an oversight). Verified zero violations on real mock-backend runs and that each check independently fires on a hand-built synthetic violation. A new `causal_verification.json` run artifact records the result.
9. ~~Build the seeded minimum DAG kernel and component-level measurement harness.~~ **Done** — new domain-agnostic `synthetic` scenario (`environment/synthetic_env.py`, `execution/synthetic_backend.py`, `scenarios/synthetic.py`, registered in `scenarios/registry.py`) generates six deterministic, parameterized shapes (`chain`, `fan_out`, `fork_join`, `independent_branches`, `mixed_dag`, `conflicting_write`) with hand-derived expected graph invariants (`expected_invariants`) verified against actual runs — no RNG involved anywhere in this codebase, "seeded" means deterministic and parameterized, not random. Fork/join required no new model fields: `ContextBuilder.build()` already reads every unread inbox message per activation, so a join node's single activation naturally receives all branch messages, and item 8's `causal_parents` already captures them. `role_policy.py` and the storm/supply-chain domain logic are completely untouched; `create_synthetic_engine` explicitly rejects `backend_name="aitta"` rather than silently running a deterministic-by-design kernel through a real LLM. Added a reusable `observability/kernel_invariants.py::graph_metrics` (built on a `build_message_edges` helper extracted from `causal_verifier.py`, identical behavior, now shared) as a separate structural reader alongside `causal_verifier.verify()` — one checks correctness, the other describes shape. Split `simulation_engine.py`'s bundled `result_application_ms` timing into `state_commit_ms`, `message_delivery_ms`, `tracing_ms` (additive instrumentation only, regression-guarded in `test_engine.py`), giving component-level timing for scheduler/context-construction/batching/commit/message-delivery/tracing; validation and serialization costs are legitimately absent from this path (no LLM validation on the kernel; serialization is an end-of-run artifact cost, not per-tick) and are noted as out of scope rather than silently dropped. New `observability/kernel_benchmarks.py::run_kernel_benchmarks` runs every shape as both a correctness gate (zero causal violations, exact invariant match) and a timing sample (min/mean/max per component per shape), writing `docs/baseline/component_benchmarks.json`. One deliberate, explicitly recorded gap: `conflicting_write` proves the scenario can produce a real environment-variable write conflict, but the verifier does not yet detect environment-level conflicts (only per-agent state-version conflicts) — that remains future work, not invented here; the corresponding test asserts determinism across repeated runs rather than a hand-predicted value.
10. ~~Implement the atomic state-store commit conformance contract.~~ **Done** — new `models/commit.py` (`CommitStatus`, `CommitUnit`, `CommitReceipt`) and `RuntimeStore.commit()` (`state/base.py`), implemented identically by both `InMemoryStateStore` and `SQLiteStateStore`: an activation's state mutation, messages, and emitted events now apply all-or-nothing, guarded by an idempotency check (duplicate `activation_id` → no-op) and an optimistic state-version conflict check (stale `expected_state_version` → rejected, nothing applied). For SQLite this is a real `with self.conn:` transaction, not just a convention. `MessageRouter.deliver` (which mutated the store itself) became a pure `route()`; `SimulationEngine.step()` now builds one `CommitUnit` per activation and commits it through the store instead of four independent, unguarded calls. New `tests/test_commit_conformance.py` establishes the repo's first shared conformance-suite pattern (a mixin run against both backends), matching ADR 0001's stated bar: "no duplicate, late, or partial commit can occur." A real, previously undetected bug surfaced while researching this item and was fixed as a prerequisite: `SQLiteStateStore`'s read-reconstruction helpers predated item 8's versioning/causal fields and silently dropped `AgentState.version`, `EnvironmentState.version`, `Event.causal_parent_activation_id`, and `Message.origin_activation_id` back to their defaults on every read — meaning item 8's entire causal-verifier/state-versioning story was silently broken whenever `storage_mode="sqlite"` was used instead of the in-memory default. Fixed and regression-tested (`tests/test_state_store.py::test_sqlite_store_round_trips_version_and_causal_fields`). One deliberate, explicitly recorded scope decision: the atomic unit covers agent state + that activation's messages/events only — environment mutation stays a separate, already-existing tick-level batched step, since folding it in would require rearchitecting how all three environments (storm/supply_chain/synthetic) reduce a batch of actions from multiple agents, with no current forcing function (no concurrency exists yet). Left as explicit future work for whichever of items 11/12 introduces concurrent dispatch.
11. ~~Define the asynchronous provider conformance interface.~~ **Done** — new `AsyncExecutionBackend` Protocol (`execution/async_backend.py`: `submit`/`poll`/`cancel`, per-request granularity) plus `models/dispatch.py` (`DispatchStatus`, `DispatchTicket`, `DispatchOutcome`) define the "runtime submit/poll ... with a synchronous adapter" shape Phase 5 specifies. `SynchronousProviderAdapter` (`execution/sync_provider_adapter.py`) is the one reference adapter, wrapping any existing `ExecutionBackend.run_batch`-based backend (all four — mock, rule, synthetic, Aitta — verified) so every backend satisfies the new port immediately with zero changes to its internals; `SimulationEngine.step()`, `BatchBuilder`, and `run_batch` itself are completely untouched — this item defines the interface only, exactly mirroring item 10's scope. Provider errors are normalized per Architectural Rule 9 (`execution/errors.py`'s `ProviderError` taxonomy), surfaced via `DispatchOutcome.error` rather than raised from `submit()`/`poll()`; only `ProviderTimeoutError` and the generic catch-all are actually exercised by classification logic today (the taxonomy's other categories — capacity, malformed response, unsupported capability — are defined for completeness but nothing in today's backends triggers them). New `tests/test_async_provider_conformance.py` establishes the repo's second cross-backend conformance-suite mixin (after item 10's), run against all four backends. Two contract properties are structurally unreachable via the synchronous adapter and are flagged rather than faked: `DispatchStatus.PENDING` is never observed (submit() always runs to completion before returning) and `cancel()` can never actually stop anything (nothing is ever in flight) — both are reserved for a future genuinely non-blocking adapter, which is not built here. Building the real dispatcher (sequential/naive-concurrent/barrier/causal baselines) that uses this port is item 12's job.
12. ~~Add sequential, naive-concurrent, barrier, and causal-only baselines.~~ **Done** — new `DispatchPolicy` Protocol (`scheduling/dispatch_policy.py`) plus four implementations, all built on item 11's `AsyncExecutionBackend.submit()`/`poll()`: `SequentialDispatchPolicy` (one request at a time — proven mechanically equivalent to the pre-item-12 `run_batch` path), `NaiveConcurrentDispatchPolicy` (a real `concurrent.futures.ThreadPoolExecutor`, no conflict protection, completion-ordered via `as_completed()` — the negative control), `BarrierDispatchPolicy` (concurrent within each existing `BatchBuilder` backend-hint group, serialized between groups), `CausalOnlyDispatchPolicy` (concurrent within message-causally-independent waves computed from `Message.origin_activation_id`/`Event.causal_parent_activation_id`, waves themselves strictly ordered). Real thread-level concurrency is used throughout, not simulated — the same stdlib mechanism `AittaExecutionBackend` already used internally, now moved to the runtime as Phase 5 intends: with a dispatch policy active, every backend's own `run_batch` only ever sees single-request lists, so Aitta's internal `ThreadPoolExecutor`/`max_concurrency` becomes inert, "putting concurrency control in the runtime rather than individual providers." `SimulationEngine` gained an optional `dispatch_policy` constructor/instance attribute (`None` by default, preserving the exact original `run_batch` loop with zero behavior change); when set, dispatch bypasses `BatchBuilder`'s pre-split batches entirely and hands the full tick's requests to the policy, which does its own grouping. Verified: `SequentialDispatchPolicy` reproduces the exact deterministic behavior signature of the default path on the storm scenario; all four policies (plus the default) produce identical `graph_metrics`/zero causal-verifier violations across all five non-conflict synthetic kernel shapes, satisfying "sequential execution reproduces the deterministic baseline" and "naive and causal concurrency run identical workloads." Two scope decisions recorded honestly: (1) these policies dispatch requests already produced by the unmodified `FIFOScheduler` (still one activation per agent per tick) — lifting that constraint would require adding `activation_id` to `ExecutionResult` and restructuring `simulation_engine.py`'s agent-keyed request/result pairing, a separate, larger effort with no forcing function yet, so a genuine same-tick same-agent `CommitStatus.CONFLICT` remains reachable only by direct unit construction, exactly as it already was after item 10; (2) `CausalOnlyDispatchPolicy` is scoped to message-mediated causal ordering only (matching `causal_verifier.py`'s existing scope) and provides no protection against the `conflicting_write` shape's shared-`EnvironmentState` race, the same already-recorded environment-conflict-detection gap from items 8-10. A further, genuinely notable finding surfaced while building this: because a message sent during tick N can only be read starting tick N+1 at the earliest, no request within one tick's dispatch batch ever causally depends on another request in that same batch — so causal-only and naive-concurrent produce identical (single-wave) behavior on every scenario that exists today. The wave-building logic is nonetheless correct and independently verified via direct construction of an artificial in-batch dependency; it becomes load-bearing only once a future scheduler produces causally-chained activations within one tick.
13. ~~Implement the capability, queue-awareness, backpressure, and prefix-grouping ablation ladder.~~ **Done** — three new `DispatchPolicy` implementations complete the 7-rung policy ladder on top of item 12's `CausalOnlyDispatchPolicy` (rung 4): `CapabilityAwareDispatchPolicy` (rung 5) groups each causal wave by `backend_hint` and dispatches a group concurrently only if `backend.capabilities.supports_concurrency` is true, otherwise sequentially — closing a real gap, since rungs 1-4 all used `ThreadPoolExecutor` regardless of what the backend declared; `QueueAwareDispatchPolicy` (rung 6, extends rung 5) adds a genuine, bounded backpressure control, capping each group's concurrency at a configurable per-`backend_hint` max-in-flight limit instead of dispatching every ready request at once; `FullDispatchPolicy` (rung 7, extends rung 6) adds a role-based sub-grouping pass before dispatch. `CausalOnlyDispatchPolicy._build_waves` was extracted to a module-level `build_causal_waves()`, shared by all three new rungs (pure refactor, item 12's existing direct test of it kept working unchanged). All three conform to the existing `DispatchPolicy` Protocol, so **zero changes were needed to `SimulationEngine`** — a direct payoff of item 12's Protocol-based design. Three scope decisions recorded honestly, since no document specifies concrete definitions for these concepts: (1) "capability-constrained batching" is scoped to respecting `supports_concurrency` only, not server-side merged-batch submission — no backend declares `supports_server_batching=True` today, so that mechanism would be untestable dead code; (2) "reusable-prefix grouping" is approximated by `AgentProfile.role` (Phase 6's own heuristic wording accepts "prefix **or role** similarity" as an input) rather than real prompt/token-level prefix hashing, since no backend declares `supports_prefix_caching=True` to exploit it; (3) no `deadline` field was added to `Activation` — none of the three required rungs depend on it, and priority ordering already falls out of `FIFOScheduler`'s existing event sort with no new code needed. As already found in item 12, every existing scenario uses a single `backend_hint`/role uniformly within one tick, so all seven rungs collapse to identical behavior on every real scenario today; each new rung's distinguishing mechanism (capability-gated concurrency, the backpressure cap, role-based sub-grouping) is nonetheless correct and independently verified via hand-built heterogeneous test fixtures, matching item 12's own established pattern for exactly this kind of gap. No benchmark artifact or statistical ablation study was built here (matching items 10-12's precedent) — that comparative-measurement work is item 14's job.

**Retuned against real data (item 19 follow-up)**: `QueueAwareDispatchPolicy`'s `default_max_in_flight` was originally `2`, an arbitrary illustrative value picked when this item was built, never tuned against real data. Item 19's real 7-rung B1 pilot found this caused a statistically real throughput regression on both LUMI and Roihu (`queue_aware`/`full` collapsing well below `capability_aware`). A follow-up sweep over `{2, 4, 8}` (`docs/baseline/b1_retune_sweep_{lumi,roihu}_result.json`) found `4` is the smallest value whose useful-agent-steps/sec band overlaps `capability_aware`'s on *both* systems (`2` does not; `4` and `8` both do) — per `docs/hpc_data_collection_procedures.md`'s tie-break rule, the smaller of two statistically-indistinguishable options wins. The default is now `4`, confirmed via a full re-run of the confirmatory pilot: `queue_aware` fully recovers to `causal_only`/`capability_aware` levels on both systems (Roihu: 1.482 vs. causal_only's 1.411; LUMI: 0.394 vs. causal_only's 0.375). `FullDispatchPolicy` (which inherits this default) did **not** recover — the same sweep showed no improvement for `full` at any tested value, and the re-run confirms `full` is still real, statistically distinguishably worse than `causal_only` on both systems (Roihu: -38.6%; LUMI: -33.5%) — its bottleneck is a separate mechanism (its own sequential role-group-by-role-group dispatch), not the in-flight cap.

**`FullDispatchPolicy` itself fixed, also confirmed on real hardware**: `dispatch()` called `NaiveConcurrentDispatchPolicy` once per role group in a plain `for` loop — each call blocks until its own `ThreadPoolExecutor` fully drains, so role group 2 couldn't start until role group 1 finished. Pathological whenever a role has few concurrent requests per wave (this session's `storm` pilots use one agent per role, `agent_replicas=1`), collapsing every role group to a no-op "concurrent" dispatch of size 1, serialized end to end — exactly matching the observed near-sequential throughput. Fixed by reordering requests role-by-role and dispatching the whole group as **one** concurrent batch (the same mechanism `QueueAwareDispatchPolicy` uses), preserving role-adjacent submission order without blocking between roles; `dispatch()`'s override was deleted entirely (now inherits `CapabilityAwareDispatchPolicy.dispatch()` via `QueueAwareDispatchPolicy`), only `_dispatch_group` differs. `tests/test_dispatch_policies.py`'s `test_role_groups_dispatch_one_after_the_other` (which asserted the old, harmful serialization as correct) was rewritten to prove cross-role concurrency instead. Re-confirmed via the same 7-rung/10-rep pilot on both systems: `full` is now **fully recovered** — Roihu 1.530 (the *highest* of all 7 policies, above `causal_only`'s 1.333, `full_vs_sequential` +80.2% real), LUMI 0.371 (in line with `causal_only`'s 0.385/`queue_aware`'s 0.388, `full_vs_sequential` +49.2% real, `full_vs_causal_only` only -3.7% and bands overlap — no longer a real regression). Both mechanisms found by this real pilot (the `max_concurrency` confound, the in-flight-cap tuning, and this role-grouping serialization bug) are now fixed and confirmed on real hardware on both systems.
14. ~~Preregister and evaluate the scheduler contribution decision gate locally.~~ **Done** — `docs/scheduler_contribution_gate.md` preregisters, before any results existed, a concrete decision rule that no prior document specified numerically: primary contrast `FullDispatchPolicy` vs `CausalOnlyDispatchPolicy` mean throughput; minimum practically meaningful effect of 15% relative improvement, required only on two heterogeneity-bearing workload variants; an uncertainty criterion (non-overlapping mean±1-stdev bands, plus a reported normal-approximation 95% CI); required coverage of three preregistered workload variants (`single_provider` control, `multi_provider`, `multi_role_multi_provider`); and an exclusion rule for any repeat that raises. New `execution/latency_simulating_backend.py::LatencySimulatingBackend` (a real backend, not a test-only stub) and `observability/scheduler_gate.py::run_scheduler_contribution_gate` implement it, reusing `DispatchPolicy.dispatch()` directly (no engine/scenario changes needed) and writing raw + summarized results to `docs/baseline/scheduler_contribution_gate_results.json`. **Result: the gate is not cleared** — `full` was substantially slower than `causal_only` on both heterogeneity-bearing variants (−65.7% and −68.2% relative "improvement," i.e. a regression), not faster. This matches the mechanistic expectation recorded in the preregistration *before* the harness was ever run: `QueueAwareDispatchPolicy`'s bounded-in-flight cap (and `FullDispatchPolicy`, which inherits it) constrains concurrency with no real capacity limit to protect against and no modeled prefix-cache speedup to offset the cost, since no backend in this codebase has either property. Per the roadmap's own decision-gate framing, this is treated as a legitimate, informative outcome, not a failure of the item: it exercised the full preregister-then-evaluate methodology honestly (rule fixed blind to results, never adjusted afterward) and confirms Phase 9's real HPC study — with genuine capacity constraints and real prefix-caching-capable serving software — is still required before any research conclusion about the scheduler's actual value can be drawn; this local result says nothing about that. Also fixed in passing: `docs/baseline/manifest.json`'s `reference_execution_policy` field was stale since items 12-13 (claimed "no concurrency exists yet"), corrected to note the dispatch-policy ladder exists as an opt-in path and the frozen signatures cover only the unchanged default path.
15. ~~Expand the publication workload suite.~~ **Done** — of `evaluation_plan.md`'s five required families, **failure workloads** was the one missing entirely from the codebase; new `execution/failure_injecting_backend.py::FailureInjectingBackend` fills it, deterministically injecting `timeout`/`malformed`/`interruption` failures (no RNG, matching this codebase's "seeded means deterministic" convention) and reusing items 10/11's already-built-but-not-integration-tested machinery end to end for the first time: `ProviderTimeoutError`/`ProviderError` classification (item 11) and the `model_output_invalid` fallback convention (Phase 3). Wired into `create_synthetic_engine` via an optional `scenario_parameters["failure_injection"]` config. Confirmed only meaningfully non-crashing through the dispatch-policy path — `SimulationEngine.step()`'s default `run_batch` path has no try/except, so a raised failure crashes the run exactly like any real failing backend would; this is documented explicitly, not silently assumed. Two new continuous dimensions added to the synthetic kernel, both proven behavior-inert at their defaults and provably inert to simulation semantics in general: `conflict_ratio` on `conflicting_write` (partial conflicts — only a fraction of writers race on the shared key, the rest write to their own unique key; conflict is an environment-write property so `expected_invariants` is unaffected regardless of ratio) and `provider_count`/`role_count` (round-robin `backend_hint`/role heterogeneity across every shape's roster, closing the exact gap items 12-14 kept independently rediscovering — `SyntheticExecutionBackend` branches only on `agent_id`, never on these labels, so heterogeneity only affects dispatch-policy *grouping*, never correctness, verified by the same `graph_metrics`/`verify()` equivalence tests used throughout). Two new representative entries added to `kernel_benchmarks.py`'s `KERNEL_SHAPES`. Deliberately not built: input/output length distributions and logical deadline tightness (no field for either exists anywhere and neither would have a consumer yet — same discipline items 6/13 already applied to `deadline`), a seeded/invariant-checked kernel-ification of storm/supply-chain (a separately-scoped, much larger effort on already-stable code), and "duplicate response" failure injection (already directly tested by item 10's commit conformance suite, not reimplemented here).
16. ~~Add provider-neutral telemetry with ROCm and CUDA collectors.~~ **Done** — `models/platform_telemetry.py::PlatformTelemetrySample` is a new provider-neutral schema (GPU utilization, HBM used/total, GPU power, energy, host CPU utilization, plus `kv_cache_used_percent`/`preemption_count`/`queue_depth` fields left unpopulated by design pending a future serving-runtime collector), every field defaulting to `None` per `evaluation_plan.md`'s "missing telemetry is explicit rather than imputed." A new `TelemetryCollector` port (`observability/base.py`, `collect() -> list[PlatformTelemetrySample]`) is kept deliberately separate from the existing `Telemetry` sink port; `RocmTelemetryCollector`/`CudaTelemetryCollector` (`observability/rocm_collector.py`/`cuda_collector.py`) shell out to `rocm-smi`/`nvidia-smi` through an injectable `CommandRunner` seam, tested entirely against fixture text and fake runners (no ROCm/CUDA hardware exists in this session — collection failures become an explicit `error`-bearing sample, never a crash). `SimulationEngine` gained an optional `telemetry_collector` constructor arg, defaulting to `None` (zero behavior change for every existing caller), polled once per tick alongside the existing `simulation_tick` event. `observability/artifacts.py` gained a `_platform_telemetry` aggregator mirroring `_backend_metrics`'s exact shape, wired into a new `platform_telemetry.json` per-run artifact and into `aggregate_run_stats`'s cross-run means. Selectable via `--platform-telemetry {rocm,cuda}` / `"execution": {"platform_telemetry": "rocm"}`. `docs/adr/0002-runtime-owned-telemetry-collection-port.md` (drafted, status Proposed) records the port split, the shared-schema decision, and the engine-wiring/Rule-6 conformance. Explicitly not built: a serving-runtime (vLLM `/metrics`) collector, and LUMI job-energy/Roihu scheduler-accounting collectors — both deferred as documented future work; neither collector has run against real hardware, only fixtures and fakes.
17. ~~Create self-hosted deployment manifests for LUMI and Roihu.~~ **Done** — both halves now exist. `docs/lumi_deployment_manifest.md` maps every item in `evaluation_plan.md`'s B1 (common-denominator)/B2 (platform-tuned) requirements and Placement-levels section onto concrete configuration values, reusing the already-existing `docs/amd_vllm_lumi_tuning.md` tuning knowledge and `scripts/run_lumi.sh` conventions rather than re-deriving them; it was drafted from public documentation only, since no working LUMI credentials existed at the time. `docs/roihu_deployment_manifest.md` does the same for Roihu, but — SSH access to `roihu-gpu.csc.fi` having since started working — most of its hardware and software-stack facts were confirmed live rather than assumed: SLURM GPU partitions (`gputest`/`gpuinteractive`/`gpumedium`/`gpularge`, each granting `gpu:gh200:4`) via `sinfo`/`scontrol`, host architecture via `lscpu`/`uname -m`, and the serving stack via `module load python-vllm/0.19.1` (a CSC-provided TYKKY/Apptainer container, confirmed Python 3.12.12/PyTorch 2.10.0+cu129/vLLM 0.19.1) plus this project's own preexisting `lumi-apptainer-bench` benchmarking workspace on Roihu's scratch, which already demonstrated the exact `apptainer exec --bind="$(csc-common-bind)" "$SIF" ...` execution pattern this manifest reuses. `docs/adr/0005-platform-manifest-and-telemetry-normalization.md` (drafted, status Proposed — not yet accepted) formalizes the manifest's field shape and, as a binding decision, the self-hosted-vs-managed-endpoint boundary: a run counts as primary performance evidence only when its `PlatformManifest.manifest_mode` is populated, so today's Aitta-backed LUMI runs (`scripts/run_lumi.sh` on the CPU-only `small` partition) remain an optional portability observation, never primary evidence. `models/platform_manifest.py::PlatformManifest` gained generic (LUMI-or-Roihu) fields for accelerator count/memory, driver/serving-runtime version, interconnect, placement level, and manifest mode, all defaulting to `None`, plus `for_lumi(...)`/`for_roihu(...)` constructors that fill each platform's fixed hardware constants but require version fields as caller-supplied arguments with no default — never invented. Explicitly not built: any Roihu-specific `ExecutionBackend` code — none is needed, since `execution/self_hosted_backend.py::SelfHostedExecutionBackend` (item 19) is a plain OpenAI-compatible HTTP client with no host-architecture/accelerator-vendor assumptions and already works against either platform's server unmodified. `docs/roihu_deployment_manifest.md`'s Explicit gaps section also flags one still-open coordination item: whether LUMI's manually built ROCm vLLM stack can be pinned to the same `0.19.1` release Roihu ships as a fixed container, needed for B1's "same serving-runtime revision" requirement.
18. ~~Freeze common-denominator and platform-tuning procedures before HPC data collection.~~ **Done** — `docs/hpc_data_collection_procedures.md` freezes the *methodology*, matching the roadmap's and `evaluation_plan.md`'s own consistent wording ("procedures," never "configurations"/"values" — B2 itself treats "select through a documented procedure" and "freeze the selected configurations" as two separate, sequential acts). Common-denominator mode: a concrete feature-parity determination procedure (intersect each system's stable serving features, disable whatever isn't in the intersection on both) plus the statistical commitments `docs/lumi_deployment_manifest.md` had explicitly deferred here — 10 repetitions per workload/model/placement-level/mode combination (matching item 14's own precedent), a 20-request count-based warm-up (count-based rather than time-based specifically so the rule stays identical across systems of different raw speed), a 30-minute per-configuration wall-clock budget, and the same exclusion rule item 14 used (errors/timeouts logged and excluded, never silently dropped). Platform-tuned mode: a binding selection metric (useful agent-steps/second, primary) plus a hard disqualifying constraint (any KV-cache preemption disqualifies regardless of throughput), LUMI's sweep space cross-referenced from `docs/lumi_deployment_manifest.md`, a provisional Roihu-side sweep space (explicitly flagged as provisional pending Roihu's still-open manifest), a tie-breaking rule (overlapping mean±1-stdev bands favor the simpler/lower-resource configuration), and a freeze-timing commitment (select once before primary collection, never re-tune afterward, every divergence from common-denominator mode recorded in a table). `docs/lumi_deployment_manifest.md`'s dangling forward-reference to this item is now closed with a concrete cross-reference. Explicitly not done: no actual configuration values are selected or frozen for either system — no self-hosted backend or HPC access exists yet to run this procedure against; and Roihu's deployment manifest itself remains item 17's open remainder. No code changed — this item is documentation-only by design, since there's no runnable backend yet for a "frozen repetition count" constant to attach to without becoming unexercised dead code.
19. Run the matched two-system study and produce artifact-backed tables and figures. **Partially done** — the biggest missing prerequisite now exists: `execution/self_hosted_backend.py::SelfHostedExecutionBackend`, a real OpenAI-compatible client for a self-hosted server (vLLM on LUMI/Roihu), the thing `docs/lumi_deployment_manifest.md` said "does not exist in code today." Built by extracting `AittaExecutionBackend`'s fully-generic request/response/repair/role-policy/receipt logic (confirmed, by direct line-by-line reading, to have zero Aitta-specific assumptions) into a new shared base, `execution/openai_compatible_backend.py::OpenAICompatibleExecutionBackend` — `AittaExecutionBackend` became a thin subclass with its existing test suite (30 tests) passing completely unchanged, proving the extraction behavior-preserving. The new backend differs from Aitta in exactly the two things that genuinely differ for self-hosted deployment: no required API key, and configurable `enable_prefix_caching`/`max_context_tokens` instead of Aitta's hardcoded-safe defaults. Fully wired: `backend_factory.py`, CLI (`--backend self_hosted`, `check-self-hosted --wait`), config (`self_hosted_*` keys), and a new `configs/demo_self_hosted.json`. Also closes ADR 0005's stated gap for the first time — an optional `platform_manifest` on the shared base means every receipt this backend produces can carry `manifest_mode` (marking primary-evidence status) plus the three previously-dormant `accelerator`/`host_architecture`/`serving_runtime` receipt fields; a new `ExecutionReceipt.manifest_mode` field was added to carry it. Verified composing cleanly with items 11-13's async dispatch machinery with zero special-casing. **First live run since, on Roihu**: `SelfHostedExecutionBackend` has now run against a real vLLM server on real GH200 hardware for the first time — an honest smoke test, not the matched study. A fresh `agentic-sim` checkout was set up on Roihu's scratch (`/scratch/project_2014553/anisrahm/agentic-sim`, installed via the CSC-provided `python-vllm/0.19.1` TYKKY container's own Python 3.12, since Roihu's login-node system Python is only 3.9 and no other 3.11+ interpreter exists there yet), and `TinyLlama/TinyLlama-1.1B-Chat-v1.0` (an ungated, ~2.1 GB stand-in model, not the real study's 8B/70B choice) was downloaded into scratch. A single `srun --partition=gputest --gres=gpu:gh200:1` job (SLURM job 374508, `COMPLETED`, exit code 0, elapsed 00:01:15, well inside `gputest`'s 15-minute cap) started `vllm serve` inside the container, health-checked it, then ran `agentic-sim run --backend self_hosted --scenario storm --steps 2` against it. Result: real inference confirmed, not a fallback stub — `backend_metrics.json` shows 7,037 real tokens exchanged (5,245 prompt + 1,792 completion), latencies of 0.4-1.4s consistent with genuine GPU inference, `invalid_model_outputs: 0`, and `semantic_valid_count: 7/7`. One honest, informative finding: `message_action_autonomy_rate` was `0.0` — TinyLlama-1.1B's raw proposals needed `json_repair_attempts: 3` and were entirely backfilled by policy completion (`policy_guard_added_messages: 6`, `policy_guard_added_actions: 3`); a model this small evidently cannot reliably produce this task's structured output unassisted. That is a property of the stand-in model, not a pipeline defect, and is exactly the kind of signal `evaluation_plan.md`'s autonomy-rate metric exists to surface. LUMI was not attempted this round (its self-hosted path requires manually building vLLM from source per `docs/amd_vllm_lumi_tuning.md`, a larger undertaking than Roihu's ready-made container) — that remains open. **LUMI, immediately after**: the same smoke test was repeated on LUMI, closing what looked like a real gap — `docs/lumi_deployment_manifest.md`/`docs/amd_vllm_lumi_tuning.md` assumed vLLM would need to be manually built from source on ROCm, since no `vllm` module or apptainer/singularity container was known to exist. A pre-built, ready-to-use container **does** exist: `/appl/local/laifs/containers/lumi-multitorch-latest.sif` (maintained by another LUMI project under the shared `appl_laifs` group, discovered via a working example the user pointed at, https://github.com/aniskhan25/LUMI-AI-Guide), confirmed to already include vLLM 0.20.1 and PyTorch 2.10.0+rocm7.0. One real wrinkle specific to LUMI's `singularity` (not `apptainer`, and not Roihu's `--bind` pattern): environment variables must be prefixed `SINGULARITYENV_` to pass through into the container at all — a plain `PYTHONPATH=... singularity exec ...` silently has no effect, discovered by the import failing on the first attempt. Same job shape as Roihu: `agentic-sim` set up on LUMI's existing scratch checkout (installed via the container's own Python 3.12, since no other 3.11+ interpreter is confirmed there either), `TinyLlama-1.1B-Chat-v1.0` downloaded, one `srun --partition=dev-g --gpus-per-node=1` job (job 20399986, `COMPLETED`, exit 0, elapsed 00:01:45) started `vllm serve`, health-checked it, and ran the same `agentic-sim run --backend self_hosted --scenario storm --steps 2`. Result: real inference confirmed again — 6,431 real tokens exchanged, latencies 0.7-4.7s (higher than Roihu's 0.4-1.4s, consistent with a single MI250X GCD's generally lower per-GPU throughput versus a GH200, matching the existing `lumi-apptainer-bench` GEMM benchmark's ~4x GH200 advantage), `invalid_model_outputs: 0`, `semantic_valid_count: 7/7`. Both systems now have one honest, real, artifact-backed data point proving the pipeline works end to end.

**B1 blocking gaps resolved next, before attempting the full study**: asked to start the full matched two-system study, three genuine gaps were resolved first rather than spending large compute immediately (per the user's explicit choice). Real 8B-class model picked and confirmed, not assumed: `Qwen/Qwen2.5-7B-Instruct` @ `a09a35458c702b33eeacc393d103063234e8bc28` (ungated, confirmed via the HF API), downloaded on both systems (~15 GB each) and confirmed to actually load via a real `vllm serve` health check on each (LUMI ~105s, Roihu ~85s to healthy). The vLLM version divergence between systems (Roihu fixed at `0.19.1`; LUMI's `-latest` container is `0.20.1`) was resolved by checking every dated LUMI container build still on disk — `lumi-multitorch-u24r70f21m50t210-20260415_130625` ships vLLM `0.19.0`, one patch version from Roihu's, the closest pairing available; B1 now pairs these two builds explicitly (B1's own "paired compatible revisions" escape clause), while B2 remains free to use each system's independently-best version. The common-denominator feature-parity intersection was actually run (not assumed): `vllm serve --help`/`--version` cannot run at all from either login node (both perform device detection while building their argument parser and fail without a GPU present) — a brief real GPU job on each system captured `vllm serve --help=all` output instead, confirming prefix caching and structured outputs are available on both, and that KV-cache dtype's real intersection is `fp8_e4m3` only (`fp8_e5m2` is CUDA-only per vLLM's own documented behavior, so it's excluded). All of this is recorded in a new `docs/b1_frozen_configuration.md`, finally closing `docs/hpc_data_collection_procedures.md`'s explicitly-deferred "no actual configuration values are selected or frozen" statement for B1. One additional real finding surfaced along the way and is now documented as a required practice for any future job: a fixed port is not private to one job on either system's shared GPU partitions — a health check on port 8000 during the first Roihu confirmation attempt returned a *different, unrelated user's* concurrently running vLLM server (`mistralai/Mistral-Small-4-119B-2603`), a false positive caught only by checking the response body's model path, not just that a server answered. Every job going forward must use a unique, job-ID-derived port and verify the responding model, not assume port isolation. **Still fully open**: B2's configuration values (require running the actual sweep), and the entire primary 10-repetition data collection across the full workload/placement/mode/policy matrix on both systems — this was prerequisite resolution, not primary evidence collection.

**First real pilot, both systems**: asked to move ahead with the study, a small bounded pilot ran first rather than the full multi-day matrix — `storm` workload (the deterministic-kernel scenario was ruled out for this: `create_synthetic_engine` hard-rejects any real backend and its agents carry no natural-language prompts, so a real LLM has nothing to respond to; making it real-LLM-compatible is separate future work), single-device placement, B1 config, `sequential` vs. `full` dispatch policy (the two extremes of the 7-rung ladder), 3 repetitions, both systems. New `observability/b1_pilot.py::run_b1_pilot` (tested, `tests/test_b1_pilot.py`) is the real harness this needed — `scheduler_gate.py`'s existing gate (item 14) turned out not to be reusable for this: it hardcodes a simulated backend and bypasses `SimulationEngine`/scenarios entirely, so it was only usable as a design pattern (its exclusion-handling/summary-stat approach), not a callable. `run_b1_pilot` instead takes an injected `engine_factory`, works identically against a mock backend (tests) or a real `SelfHostedExecutionBackend` (the pilot), and adds a count-based warm-up (discards a throwaway engine's state entirely — 20 real backend calls before any timed repetition) since nothing count-based existed anywhere in `src/` before. `scripts/run_b1_pilot.py` is the thin driver that actually ran on both clusters, using `docs/b1_frozen_configuration.md`'s frozen decoding/batching values and each job's unique-port/model-verification safeguard.

**Initial 3-rep/2-policy result, then scaled up**: the first pass (3 reps, `sequential` vs. `full` only) found the two systems disagreeing in sign — LUMI showed `full` 10.3% slower than `sequential` (bands didn't overlap, real), Roihu showed `full` 12.2% faster (bands overlapped, not distinguishable from noise). Asked to scale up, the run was widened to 10 repetitions across the full 7-rung policy ladder on both systems (`scripts/run_b1_pilot.py` already supported this — just widening `dispatch_policies` and `repeats`, no new code needed for the widening itself).

**A real confound was found and fixed before trusting the scaled-up result**: the first 7-rung run showed `capability_aware`, `queue_aware`, and `full` all collapsing to near-`sequential` throughput on *both* systems — `CapabilityAwareDispatchPolicy` (and everything built on it) dispatches sequentially whenever `backend.capabilities.supports_concurrency` is `False`, and `SelfHostedExecutionBackend` derives that as `self.max_concurrency > 1` (`self_hosted_backend.py:100`). `scripts/run_b1_pilot.py` never set `self_hosted_max_concurrency`, so it defaulted to `1`, silently forcing those three rungs into sequential-equivalent dispatch regardless of real causal readiness — discarding the entire concurrency benefit the other rungs proved was genuinely available. Fixed with a new `--self-hosted-max-concurrency` flag (default `8`, matching `CapabilityAwareDispatchPolicy`'s own `max_workers` default), and both systems were re-run.

**Corrected result, both systems now show the same coherent, deconfounded story** (10 reps, all 7 rungs, zero excluded repetitions on either system):

| policy | Roihu useful-steps/s | LUMI useful-steps/s |
|---|---|---|
| sequential | 0.794 | 0.246 |
| naive_concurrent | 1.542 | 0.396 |
| barrier | 1.527 | 0.378 |
| causal_only | 1.454 | 0.400 |
| capability_aware | 1.602 | 0.390 |
| queue_aware | 1.263 | 0.315 |
| full | 0.828 | 0.241 |

`causal_only_vs_sequential`: **+83.0% (Roihu)**, **+62.4% (LUMI)**, both real (bands don't overlap) — concurrency genuinely helps a lot on real hardware, on both systems, and `capability_aware` now correctly captures that benefit (the bug previously masked this entirely). But `full_vs_causal_only`: **-43.0% (Roihu)**, **-39.8% (LUMI)**, both real (bands don't overlap) — a *consistent, cross-system, statistically distinguishable regression* from `queue_aware`'s bounded in-flight cap (default 2) onward. This matches item 14's original mechanistic prediction almost exactly, now demonstrated on real hardware on both systems rather than a local simulation: the backpressure cap constrains concurrency with no real capacity limit on this dedicated, single-tenant server to justify it, and role-based prefix-grouping (`full`'s addition on top) has no real prefix-caching backend to exploit — so both mechanisms add pure overhead with no offsetting benefit at this scale. This is directly relevant to H6 ("the full scheduler improves useful throughput relative to causal-only scheduling") — this pilot's real data argues against it as currently tuned, at least for this workload/placement/model, while simultaneously confirming the more basic claim that *some* concurrency (up through `capability_aware`) helps substantially. Raw results committed as real artifacts (superseded again below): `docs/baseline/b1_pilot_lumi_result.json`, `docs/baseline/b1_pilot_roihu_result.json`.

**Retuned and re-confirmed**: asked to retune before continuing further, `QueueAwareDispatchPolicy`'s `default_max_in_flight` (`scheduling/dispatch_policy.py`, was `2`) was swept over `{2, 4, 8}` on both systems (new `scripts/run_b1_pilot_retune.py`, reusing `run_b1_pilot` unchanged — it already accepted an arbitrary `dispatch_policies` dict; 5 reps, exploratory tuning data per `evaluation_plan.md`'s own B1-confirmatory/B2-exploratory distinction, not confirmatory). Both systems agreed: `queue_aware_4`'s band is the smallest that overlaps `capability_aware`'s (`queue_aware_2` does not, on either system) — per the already-frozen tie-break rule, `4` wins. The class default was changed from `2` to `4` (see item 13's entry for the full evidence trail), and the confirmatory 7-rung/10-rep pilot was re-run on both systems to verify the fix, not just trust the smaller sweep's own numbers. Result: `queue_aware` is **fully fixed** on both systems — Roihu 1.482 (now above `causal_only`'s 1.411), LUMI 0.394 (in line with `causal_only`'s 0.375), regression closed. `full` is **not** fixed — Roihu 0.867 (still -38.6% vs. `causal_only`), LUMI 0.249 (still -33.5% vs. `causal_only`, bands don't overlap on either system) — exactly as the sweep predicted (`full_2`/`full_4`/`full_8` showed no improvement with a larger cap on either system), confirming `full`'s bottleneck is its own separate sequential role-group-by-role-group dispatch, not the in-flight cap. This was a well-evidenced, scoped-down open question (fix `full`'s role-grouping mechanism specifically) rather than a vague "the scheduler underperforms" finding — and it's now fixed too (see item 13's entry for the mechanism and full re-confirmation numbers): `full` recovered to the highest throughput of all 7 policies on Roihu (1.530) and back in line with `causal_only`/`queue_aware` on LUMI (0.371), on the same 7-rung/10-rep pilot, real GPU time, both systems. Raw data: `docs/baseline/b1_retune_sweep_{lumi,roihu}_result.json` (the sweep), `docs/baseline/b1_pilot_{lumi,roihu}_result.json` (final re-confirmed state, overwritten three times over the course of this investigation — each overwrite is a real, re-run confirmation, not just an edit). **Still fully open**: the actual 10-repetition primary study across both placement levels, all five workload families, and B2 mode — this pilot covered 1 of 5 workloads × 1 of 2 placements, on B1 only.

**Expanded to a second workload, both systems (`supply_chain`)**: asked to run the full study across all workloads and placements, three genuine blockers were found and reported honestly first: (1) `deterministic_kernel`/`synthetic dependency graphs`/`failure workloads` (3 of the 5 required families) all run through `create_synthetic_engine`, which hard-rejects any real backend and whose agents carry no natural-language prompts — a separate, unresolved prerequisite, not something to improvise; (2) full-node placement (8 MI250X GCDs / 4 GH200s) has never been attempted on either system — only unverified sweep-space prose exists in the deployment manifests, no real tensor-parallel or multi-replica serving; (3) the full frozen matrix (5 workloads × 2 placements × 7 policies × 10 reps × 2 systems, B1 alone) is on the order of thousands of runs — days of real GPU time, not a single job. Asked to scope down, the feasible slice was run instead: `storm` + `supply_chain` (the two workload families that already work against a real backend, `create_supply_chain_engine` sharing `create_storm_engine`'s exact `backend_name`/`backend_options` signature — a straightforward `--scenario` flag added to `scripts/run_b1_pilot.py`, no other changes needed), single-device placement, B1, all 7 policies, 10 reps, both systems — 280 real measured repetitions total, one job per system running both workloads sequentially against the same live server.

**Result: a remarkably consistent, coherent story across all four (workload × system) combinations**, all confirmed post-fix (both the `max_concurrency` and `FullDispatchPolicy` fixes above):

| | Roihu `storm` | Roihu `supply_chain` | LUMI `storm` | LUMI `supply_chain` |
|---|---|---|---|---|
| sequential | 0.856 | 0.763 | 0.255 | 0.284 |
| causal_only | 1.484 | 1.712 | 0.371 | 0.495 |
| full | 1.495 | 1.832 | 0.363 | 0.492 |
| causal_only vs. sequential | +73.5% (real) | +124.3% (real) | +45.3% (real) | +74.4% (real) |
| full vs. causal_only | +0.7% (overlap) | +7.0% (overlap) | -2.1% (overlap) | -0.5% (overlap) |

Every single combination shows the same two things, both real: concurrency (`causal_only` and beyond) delivers a large, statistically distinguishable improvement over `sequential` (+45% to +124%), and `full` is now statistically indistinguishable from `causal_only` in all four cases (bands overlap every time — never a regression, but also not a clearly separate additional gain in this particular configuration). This is directly relevant to H6: with both known bugs fixed, `full`'s scheduling mechanism no longer hurts, but this pilot's data doesn't yet show it delivering a benefit *beyond* `causal_only` either, at single-device placement with one agent per role — whether a config exists where `full`'s prefix-grouping/backpressure genuinely adds value (e.g. higher `agent_replicas`, more concurrent same-role requests) is now a concrete, well-scoped question for the actual primary study, not a vague one. Zero excluded repetitions across all four runs. Raw data: `docs/baseline/b1_study_{lumi,roihu}_{storm,supply_chain}_result.json`. **Still fully open**: `deterministic_kernel`/`synthetic dependency graphs`/`failure workloads` (real-LLM support unresolved), full-node placement (untested on either system), B2 mode, and the full 10-repetition matrix at that complete scope — this expanded pilot covers 2 of 5 workloads × 1 of 2 placements, B1 only, still not the primary study evaluation_plan.md specifies.

`docs/lumi_deployment_manifest.md`'s Serving stack section is updated with this real container path and the `SINGULARITYENV_` gotcha. **Still explicitly open**: the actual matched two-system study (both systems, the real 8B/70B model, the frozen 10-repetition `docs/hpc_data_collection_procedures.md` procedure, common-denominator/platform-tuned configurations, artifact-backed tables/figures) has not started — these were two small, ad hoc, unrepeated runs proving the wiring works end to end on each system, not primary evidence collection.
