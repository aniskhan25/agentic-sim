# An Infrastructure-Agnostic Runtime for Reproducible and Reliable LLM-Agent Simulations

**Status**: first draft, structural skeleton with substantive content. Not camera-ready. Numbers below are drawn directly from committed artifacts in `docs/baseline/`; every claim should be spot-checked against its cited file before submission. Sections marked `[TODO]` need material that does not exist yet (see §7, Limitations).

This draft follows the **fallback headline** from `docs/research_roadmap.md`'s preregistered contribution decision gate (item 14): the scheduler-led primary claim did not clear its own preregistered bar, so the paper is centered on the contract/provenance/reliability model and portability, with scheduling reported as a rigorously evaluated systems mechanism rather than claimed as a win. This is not a downgrade — it is the decision the roadmap itself committed to making *before* seeing results, and the honesty of that process is part of the paper's actual contribution (§5.3, §6).

---

## Abstract

`[TODO — write last, after §5 numbers are finalized]`

Draft pointers: (1) a provider-neutral runtime that makes model proposals, repair, policy completion, fallback, contract violations, and retained model autonomy explicitly measurable and comparable across heterogeneous LLM-agent simulation infrastructure; (2) validated on two real, independently operated HPC systems with different accelerator vendors (AMD MI250X / LUMI, NVIDIA GH200 / Roihu) running an identical model revision; (3) a capability-aware causal scheduler was built and evaluated against a preregistered decision gate — under real concurrent load, with three independent measurement confounds identified and corrected, it shows no measurable difference from a causal-only baseline on the one workload currently testable on real hardware, a result explained by the workload's lack of genuine multi-provider heterogeneity rather than a mechanism failure; (4) the same investigation reversed an initial "platform-tuned config is slower" finding into "ties on one system, real win on the other" once an analogous serving-configuration confound was found and fixed.

---

## 1. Introduction

### 1.1 Motivation

LLM-agent simulations increasingly run against real inference infrastructure — self-hosted model servers on HPC systems, managed API endpoints, heterogeneous accelerator vendors — rather than against a single fixed provider. Comparing scheduling or serving-configuration choices across such infrastructure is easy to get wrong in ways that look like a real finding: under-provisioned concurrency, uncorrected tie-break defaults, and silent client-side batching ceilings can each independently produce a confident, statistically "real" (non-overlapping) result that reverses once the actual bottleneck is found. This paper reports a runtime built to make that class of error visible and correctable, and a full worked example — three rounds of exactly this failure mode, each diagnosed and fixed — running through the same investigation.

### 1.2 Research questions

- **RQ1 (Portable semantics).** Can one simulation specification execute unchanged across heterogeneous inference and storage systems while preserving event dependencies, state transitions, and declared invariants?
- **RQ2 (Safe concurrency).** How much parallelism can be extracted without changing the workload's declared observation projection or required happens-before relationships?
- **RQ3 (Reliable generative execution).** How should the runtime distinguish model proposals from repaired, policy-completed, and fallback behavior, and how do those interventions affect reliability, autonomy, diversity, and cost?
- **RQ4 (Infrastructure sensitivity).** Which workload and provider-capability properties determine effective scheduling and serving configurations across local, managed, AMD/ROCm, and NVIDIA/CUDA execution?

### 1.3 Contribution hierarchy (as evaluated, not as hoped)

1. **Primary**: a provider-neutral activation, contract, and provenance model that makes model-generated vs. repaired vs. policy-completed vs. fallback behavior, and their effect on reliability and autonomy, explicit and measurable — validated on two real, heterogeneous HPC systems (§5.1).
2. **Enabling mechanisms**: the causal activation graph and verifier, the atomic idempotent commit protocol, and the provider-neutral execution/dispatch interfaces (§3).
3. **Evidence**: controlled, within-system workload measurements on both real systems, reported with explicit statistical criteria, including two full negative-result-then-correction investigations reported honestly rather than smoothed over (§5.2, §5.3).
4. **Evaluated, not claimed**: a capability-aware causal scheduler, tested against a decision gate preregistered before any real-load result existed. The gate is not cleared — full-ladder throughput is statistically tied to a causal-only baseline on both systems once three measurement confounds are corrected. We report why this is a workload-coverage limitation, not a negative finding about the mechanism (§5.3, §6).

### 1.4 What this paper does not claim

Following `docs/research_roadmap.md`'s own positioning discipline: we do not claim an HTTP request from a batch scheduler is itself HPC-scale distributed computation; that provider portability alone is novel; that policy-completed behavior is model-generated; that a shared endpoint gives controlled hardware measurements; that one MI250X GCD and one GH200 GPU are equivalent, or that absolute cross-system differences isolate accelerator-vendor effects; or that the workloads studied establish real-world domain validity. Where we report a cross-system contrast, it is a within-system, normalized comparison, never an absolute cross-vendor ranking.

---

## 2. System Design

### 2.1 Observational semantics and activation identity

The runtime commits to an explicit observational-equivalence model (ADR 0001): a fixed activation representation (`Activation`, with `attempt_number` distinguishing retries), a fixed causal-parent chain over messages (`Message.origin_activation_id`, `Event.causal_parent_activation_id`), and monotonically versioned agent/environment state (`AgentState.version`, `EnvironmentState.version`). Two runs of the same specification are compared by their committed observation projection, not by wall-clock replay.

### 2.2 Provider-neutral execution interface

`ExecutionBackend` (a narrow Protocol: `run_batch`) is implemented identically by a deterministic mock backend, a rule-based backend, a synthetic-kernel backend, a managed-endpoint backend (Aitta), and a self-hosted OpenAI-compatible backend (`OpenAICompatibleExecutionBackend`, extracted from the Aitta backend's fully-generic request/response/repair/provenance logic — the two differ only in auth and prefix-caching/context-length defaults). All backends are exercised by one shared conformance test suite (`tests/test_async_provider_conformance.py`), not four independent, potentially-diverging implementations.

### 2.3 Contracts and per-atom provenance

Every proposed agent action passes through explicit contracts (`role_policy.py`): `must_not` (hard prohibitions), `bounded` (numeric deltas cannot be unbounded), `cardinality` (no silent duplicate application), and `allowed` (actions restricted to a declared set). Violations are counted per atom, not discarded. Every step produces an `ExecutionReceipt` carrying activation id, attempt number, provider/model identity, causal parents, state-version read and written, accelerator/serving-runtime identity, and `manifest_mode` (common-denominator vs. platform-tuned, §2.5) — but not yet a content hash of the request or response; those schema fields exist and are currently unpopulated (§7).

### 2.4 Causal verification and atomic commit

`observability/causal_verifier.py` checks the message-mediated causal chain for duplicates, missing parents, cycles, and stale-read conflicts — verified to report zero violations on real storm/supply-chain runs, and independently verified to detect each violation class when deliberately constructed. `RuntimeStore.commit()` applies one activation's state mutation, outgoing messages, and emitted events as a single atomic, idempotent unit (duplicate `activation_id` is a no-op; a stale expected state version is rejected), implemented identically by an in-memory store and a SQLite store and checked by one shared conformance suite. Environment-state mutation (shared across agents within a tick) remains outside this atomic boundary, applied as a separate batched step — a scoped, documented limitation, not an oversight (§7).

### 2.5 Common-denominator and platform-tuned modes

Every real evaluation run declares a `PlatformManifest.manifest_mode`: `common_denominator` (B1 — identical serving configuration on both systems, the feature-parity intersection of what both platforms actually support) or `platform_tuned` (B2 — independently selected per system via a frozen, preregistered selection procedure with a documented tie-break rule). This lets every reported effect be attributed to a labeled configuration choice, never silently conflated.

### 2.6 The dispatch-policy ladder

Seven dispatch policies, each strictly extending the causal-readiness guarantee of the one before it: `sequential`, `naive_concurrent`, `barrier`, `causal_only` (causal readiness and state-conflict avoidance, no further optimization), `capability_aware` (dispatches a group concurrently only if the backend declares `supports_concurrency`), `queue_aware` (adds a bounded per-provider in-flight cap), `full` (adds role/prefix-adjacent reordering). All seven share one `DispatchPolicy` Protocol; `SimulationEngine` requires no changes to add a new rung.

---

## 3. Evaluation Methodology

### 3.1 Systems

Two real, independently administered HPC systems: **LUMI** (AMD MI250X, ROCm, ~2026-04 container build) and **Roihu** (NVIDIA GH200, CUDA, CSC-provided `python-vllm/0.19.1` container). Both run `Qwen/Qwen2.5-7B-Instruct` at an identical pinned revision, confirmed to load and serve real traffic on both platforms via a live health check, not assumed compatible from documentation.

### 3.2 Workloads

`storm` (disaster-response coordination, 4 roles) and `supply_chain` (5 roles) are evaluated end-to-end against real self-hosted inference on both systems. Three further workload families specified by the evaluation plan — a deterministic minimum-DAG kernel, synthetic dependency-graph shapes, and deterministic failure injection — exist as real, tested code (`environment/synthetic_env.py`, `execution/failure_injecting_backend.py`, six parameterized kernel shapes with hand-derived invariants) but currently run only against a mock/rule backend; `create_synthetic_engine` explicitly rejects real backends today (§7).

### 3.3 Metrics

`useful_agent_steps_per_second` (throughput computed only from steps that pass all contracts, i.e. reliability-aware, not raw request rate), per-request latency, `message_action_autonomy_rate` (fraction of committed behavior that is genuinely model-generated rather than policy-completed), and per-atom contract-violation counts (`bounded`, `cardinality`, `must_not`, `state_mutation`).

### 3.4 Statistical criterion

Every contrast in this paper uses the same rule throughout: mean useful-throughput ± 1 stdev band overlap across repeated runs. Non-overlapping bands are reported as a real effect; overlapping bands are reported as statistically indistinguishable, never as "probably about the same." Where a serving- or scheduling-parameter choice must be made among statistically tied candidates, the smaller/simpler value wins by a rule fixed before any sweep was run.

---

## 4. Results

### 4.1 Reliability and provenance across heterogeneous infrastructure

`[TODO — pull the per-origin behavior breakdown (model-generated / repaired / policy-completed / fallback), autonomy rate, and contract-violation counts across the real B1 and corrected-B2 runs on both systems into a table here. This is the paper's actual headline evidence and has not yet been assembled into one comparative table — the raw numbers exist scattered across docs/baseline/*.json backend_metrics blocks.]`

### 4.2 Platform-tuned vs. common-denominator configuration: a confound, found and corrected

The B2 (platform-tuned) serving configuration was selected via a one-factor-at-a-time sweep against a live server (3 reps/candidate). Comparing B1 against B2 at confirmatory scale (10, then 30 reps) found **no statistically distinguishable difference** on either system, either workload (10-rep range: −6.6% to +59.7%; 30-rep: all four combinations converge to under ±1.5%, bands overlapping). Investigating *why* — not simply accepting a null result — found the comparison had never generated enough real concurrent backend load to stress either configuration's `max-num-seqs` cap: the pilot script defaulted to a 4-5 agent roster and a 32-events-per-tick engine cap, and the dispatch policy's own thread pool defaulted to 8 workers, regardless of the server's configured capacity.

Fixing all three (raising agent roster size, the engine's per-tick event cap, and the dispatch policy's worker cap) and rerunning under genuine concurrent load (~58–97 real concurrent requests/tick, confirmed via backend step counts) **reversed the finding**: B2 was now measurably *slower* than B1 on every combination, non-overlapping on 2 of 4 at exploratory scale (5 reps), confirmed non-overlapping on all 4 at confirmatory scale (15 reps: LUMI −18.2%, Roihu −22.0%).

Investigating this reversal in turn found the original OFAT sweep's `max_num_seqs` pick (32 on both systems) was itself measured under the same insufficient-concurrency regime and had never been tie-broken against real load. Re-sweeping `max_num_batched_tokens`, `max_num_seqs`, and `gpu_memory_utilization` under real concurrent load found `max_num_batched_tokens` re-confirms unchanged, but `max_num_seqs` corrects to **64 on LUMI** (matching B1's own value) and **128 on Roihu** (exceeding it) — a real, non-overlapping correction on both systems.

Rerunning B1-vs-B2 with the corrected B2 configuration (B1 unchanged, reused directly) reverses the finding a third time: **LUMI is now a genuine statistical tie** (storm +6.7% at 15 reps, narrowing to +1.6% at 30 reps — converging toward zero, not away from it, confirming it is noise, not an under-powered real effect); **Roihu now measurably beats B1**, non-overlapping on both workloads (storm +15.1%, supply_chain +19.1%).

| System | Workload | Original (low-load) | Under real load, uncorrected config | Under real load, corrected config |
|---|---|---|---|---|
| LUMI | storm | +4.6% (overlap) | −18.2% (real) | +1.6% (overlap, 30 reps) |
| LUMI | supply_chain | +59.7% (overlap, noisy) | −21.4% (real) | +0.6% (overlap, 15 reps) |
| Roihu | storm | −6.6% (overlap) | −22.0% (real) | +15.1% (real) |
| Roihu | supply_chain | +10.9% (overlap) | −15.1% (real) | +19.1% (real) |

Zero KV-cache preemption across every one of these real runs, checked directly in server logs, not only by automated grep — the effect is a batching/queueing efficiency phenomenon, not the frozen procedure's hard disqualifier. Raw data: `docs/baseline/b1_vs_b2_comparison*.{csv,md}`, `docs/baseline/b1_vs_b2_highconcurrency*`, `docs/baseline/b2_concurrent_sweep_{lumi,roihu}_trace.json`.

### 4.3 The scheduler decision gate under real concurrent load

The scheduler-ladder decision gate (preregistered: ≥15% relative improvement of `full` over `causal_only`, non-overlapping, on heterogeneity-bearing workload variants) was first evaluated on a synthetic latency-simulating harness and, separately, on a real 7-rung pilot against live servers on both systems — both at an agent roster size of 1 replica per role. That real-hardware evidence showed `full` matching or exceeding every other rung (Roihu: highest of all seven, +80.2% over sequential; LUMI: in line with `causal_only`).

Given §4.2's finding that this exact measurement regime (roster size, per-tick event cap, dispatch-policy worker cap) hid or inverted a real effect elsewhere, we reran the ladder under the same real-load settings that reversed §4.2. **Result: `full` collapsed to a large, real regression** — Roihu −73.2%, LUMI −71.6%, both non-overlapping — the opposite of the earlier conclusion.

Diagnosing this found two further, independent, previously unknown confounds, neither related to roster size:

1. `BarrierDispatchPolicy`/`CapabilityAwareDispatchPolicy`/`QueueAwareDispatchPolicy`/`FullDispatchPolicy` all default to a batch-builder cap of 8 requests per dispatch round, independent of any concurrency-worker setting — forcing several sequential dispatch rounds per tick regardless of how large the worker pool is configured. Correcting this fully resolved `naive_concurrent`/`barrier`/`causal_only`/`capability_aware` into a tight, mutually indistinguishable cluster on both systems (previously ~3x apart).
2. `queue_aware`/`full`'s per-provider in-flight concurrency cap (4) was itself tuned under the same insufficient-load regime — the exact structural parallel to §4.2's `max_num_seqs` bug. Even with confound (1) fixed, `full` remained a large, real regression (LUMI −66.1%, Roihu −63.8%). A real sweep of the cap under genuine load found 4 a real, non-overlapping loser on both systems; 64 ties with 128 and wins the tie-break, closely matching `causal_only`'s own throughput.

With both confounds corrected, a final confirmatory rerun found **all six concurrent dispatch rungs statistically indistinguishable from one another on both systems** (`full` vs. `causal_only`: LUMI +1.1%, Roihu −0.3%, both overlapping). Zero preemption, zero excluded repetitions, across every real run in this investigation.

| Stage | LUMI (`full` vs. `causal_only`) | Roihu (`full` vs. `causal_only`) |
|---|---|---|
| Low concurrency (original) | tied / `full` recovers | tied / `full` highest of 7 |
| Real load, uncorrected | **−71.6%** (real) | **−73.2%** (real) |
| Real load, batch-cap fixed | −66.1% (real) | −63.8% (real) |
| Real load, both fixed | +1.1% (overlap) | −0.3% (overlap) |

**Interpretation.** The decision gate is not cleared. This is not evidence that capability-aware/queue-aware/prefix-grouping scheduling is ineffective — it is evidence that the one workload currently testable on real hardware (`storm`) provides no genuine multi-provider heterogeneity: every real agent in every real run this study performed routes to the same single serving endpoint, so `capability_aware`'s per-provider capability gate and `queue_aware`'s per-provider backpressure budget have literally nothing to differentiate. The mechanism has never been tested under the condition it is designed for. §6 and §7 discuss what that test requires.

### 4.4 Cross-system portability

The same simulation specification, unmodified, executes on both AMD/ROCm and NVIDIA/CUDA infrastructure, producing zero causal-verifier violations and identical structural invariants on every real run reported above. All cross-system comparisons in this paper are within-system, normalized effect sizes (§3.4); we do not report or interpret absolute LUMI-vs-Roihu throughput ratios as isolating accelerator-vendor effects (§1.4).

---

## 5. Discussion

`[TODO — expand]`. Draft points:
- The confound-discovery methodology (§4.2, §4.3) is itself a transferable finding for anyone benchmarking LLM-serving or agent-scheduling configurations: a null or a confidently "real" result measured under insufficient concurrent load cannot be trusted without first confirming the load level actually stresses the parameter under test. Three independent instances of exactly this failure mode were found and corrected in one investigation arc, each via the same diagnostic pattern (trace the call path to the true binding constraint, not the parameter that was intended to bind).
- A preregistered decision gate with a stated fallback framing let this paper report a non-cleared gate as a workload-coverage finding rather than as pressure to reframe the contribution after the fact.

---

## 6. Limitations and Threats to Validity

- **No genuine multi-provider heterogeneity has been tested.** `capability_aware`/`queue_aware`'s core mechanisms are keyed on a per-request provider label; every real-hardware run in this paper uses exactly one. Testing them properly requires a routing layer over multiple concurrently live backend instances with genuinely different capacity/capability, and a scenario that actually assigns different agents to different providers — not yet built (§4.3).
- **Full-node placement evidence predates these fixes.** The only full-node measurements available were collected before the roster-size/batch-cap/in-flight-cap corrections above were known to matter, and have not yet been rerun under corrected settings; they are not cited as confirmatory in this draft.
- **Three of five specified workload families cannot yet run on real inference.** The deterministic-kernel, synthetic-dependency-graph, and failure-injection families exist as tested, real code, but the harness that runs them (`create_synthetic_engine`) currently accepts only a mock/rule backend by design; extending it to a real backend is unresolved.
- **Content-addressable provenance is defined but not populated.** `ExecutionReceipt` reserves `request_hash`/`prompt_hash`/`raw_response_hash` fields; no code path currently computes them. Provenance in this paper is by identity, version, and timing, not by content hash.
- **Replay and recovery (checkpoint, resume-after-termination, response replay) is unimplemented.** What exists today is determinism (two independent runs of the same specification produce identical trace signatures), which is a narrower guarantee.
- **Atomic commit does not cover environment-state mutation.** The commit boundary covers one activation's agent-state update, outgoing messages, and emitted events; environment state (shared across agents within a tick) is applied as a separate, non-transactional batched step.
- **Single model, single revision, 7-8B parameter class.** This is not a model-scaling study; conclusions about reliability/autonomy/scheduling are scoped to this model class until repeated at other scales.
- Every non-claim in §1.4 applies throughout.

---

## 7. Conclusion

`[TODO]`

---

## Reproducibility

All results cited above are backed by committed, raw JSON artifacts under `docs/baseline/`, reproducible via `scripts/run_b1_pilot.py` and the aggregation scripts in `scripts/`. Frozen serving configurations and their full evidence trails are recorded in `docs/b1_frozen_configuration.md` and `docs/b2_frozen_configuration.md`. The complete chronological investigation log, including every superseded finding and why it was superseded, is preserved in `docs/research_roadmap.md` rather than silently overwritten.
