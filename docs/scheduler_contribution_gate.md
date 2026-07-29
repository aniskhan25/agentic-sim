# Scheduler Contribution Decision Gate — Local Evaluation

This document is the preregistration and local evaluation of the decision gate named in `docs/research_roadmap.md`'s "Contribution Hierarchy and Decision Gate" section and `docs/evaluation_plan.md`'s Statistical Design section: "define a minimum practically meaningful improvement, required workload coverage, and uncertainty criterion for the full scheduler relative to the causal-only baseline... If the full scheduler clears that preregistered gate... retain the scheduler-led hierarchy... If it does not, do not claim generic causal scheduling as novel." Neither document specifies concrete numbers anywhere — defining and preregistering them is this document's job.

**Scope**: this is a *local* rehearsal (`docs/research_roadmap.md` item 14), run entirely on CPU with deterministic, simulated-latency backends — no LUMI/Roihu, no real LLM inference. It exercises the preregister-then-evaluate methodology and the measurement infrastructure end to end. It is explicitly **not** a substitute for Phase 9's real two-system HPC study (items 16-19), and no claim about real-world scheduling value should be drawn from its outcome alone.

## Preregistration

Written before any run of the harness described below, and before any numbers in the Results section exist.

**Primary contrast.** `FullDispatchPolicy` (rung 7) versus `CausalOnlyDispatchPolicy` (rung 4) mean throughput (completed requests ÷ dispatch wall-clock seconds), matching `evaluation_plan.md`'s own framing: "Causal-only versus full is the primary contrast for the proposed scheduler contribution."

**Minimum practically meaningful effect.** `full`'s mean throughput must exceed `causal_only`'s mean throughput by at least **15% relative improvement**. This is required only on the two workload variants that contain real heterogeneity for a capability/queue/prefix-aware policy to exploit (`multi_provider`, `multi_role_multi_provider`, defined below) — no effect is required on `single_provider`, a uniform control expected to show no meaningful difference between any of the seven policies, since there is no heterogeneity for any rung to exploit.

**Uncertainty criterion.** Across 10 repeats per policy per variant: the gate additionally requires `full`'s (mean − 1 stdev) to exceed `causal_only`'s (mean + 1 stdev) — a simple, honest non-overlapping-bands separation check appropriate for a small local rehearsal, not a formal hypothesis test. A normal-approximation 95% confidence interval (mean ± 1.96 × stdev / √n) is also reported per policy per variant for reference, labeled explicitly as an approximation.

**Required workload coverage.** All three preregistered variants must be reported. The gate is considered cleared only if both the effect-size and uncertainty criteria hold on **both** heterogeneity-bearing variants (`multi_provider` and `multi_role_multi_provider`).

**Exclusion rule.** Any repeat whose dispatch call raises an exception is excluded from that policy/variant's statistics and logged in the results payload's `excluded` list — never silently dropped without a record.

**A mechanistic expectation, stated honestly before running anything.** `QueueAwareDispatchPolicy`'s backpressure cap and `FullDispatchPolicy`'s role-based grouping are protective/optimization mechanisms for a real, capacity-constrained, prefix-cache-capable backend. No backend in this codebase today has a real concurrency ceiling or models any prefix-cache speedup (`supports_prefix_caching=False` everywhere, confirmed by inspection) — a purely local, infinite-capacity, non-caching simulated backend has no mechanism that would reward either feature with higher throughput; the honest mechanistic expectation is that they add overhead or are neutral here, not that they win. This expectation is recorded now, before running anything, precisely so the eventual outcome cannot be quietly rationalized after the fact in either direction.

## Method

**Backend.** `execution/latency_simulating_backend.py::LatencySimulatingBackend` — a minimal `ExecutionBackend` whose `run_batch` sleeps a configured per-agent delay then returns a trivial `ExecutionResult`. Constructed once per variant with `supports_concurrency=True` (without it every rung collapses to sequential dispatch, which would be a trivial, uninformative comparison).

**Workload variants** (`observability/scheduler_gate.py::WORKLOAD_VARIANTS`):
- **`single_provider`** — one `backend_hint`, one role, uniform delay. Control: no heterogeneity for any rung to exploit.
- **`multi_provider`** — several `backend_hint` groups, one role, per-request delay. Exercises `CapabilityAwareDispatchPolicy`/`QueueAwareDispatchPolicy`'s backend_hint grouping and backpressure cap.
- **`multi_role_multi_provider`** — several `backend_hint` groups × several roles. Additionally exercises `FullDispatchPolicy`'s role sub-grouping.

**Procedure.** For each of the 7 dispatch policies × 3 variants × 10 repeats: build the variant's `list[ExecutionRequest]` fresh, wrap the backend in `SynchronousProviderAdapter`, time `policy.dispatch(requests, adapter)` via `time.perf_counter()`, compute throughput = request count ÷ elapsed seconds. Summarize per policy per variant with mean/stdev (reusing the same summarization pattern as `observability/artifacts.py::_mean_stdev`) plus the 95% CI described above. Raw per-repeat throughput values are preserved in the output artifact, not just the aggregates.

**Artifact.** `docs/baseline/scheduler_contribution_gate_results.json`, following the existing `docs/baseline/*.json` convention (e.g. `component_benchmarks.json` from item 9).

## Results

Run via `run_scheduler_contribution_gate(repeats=10)`; full raw data (including all per-policy stats and the empty `excluded` list — no repeat raised) in `docs/baseline/scheduler_contribution_gate_results.json`. Mean throughput in requests/second, with 1-stdev band and 95% CI:

**`single_provider`** (control, 6 requests, 1 provider, 1 role):

| policy | mean | stdev | 95% CI |
|---|---|---|---|
| sequential | 82.14 | 2.55 | [80.55, 83.72] |
| naive_concurrent | 447.67 | 20.92 | [434.71, 460.64] |
| barrier | 429.65 | 14.87 | [420.43, 438.87] |
| causal_only | 419.21 | 8.80 | [413.76, 424.66] |
| capability_aware | 430.50 | 13.08 | [422.39, 438.60] |
| queue_aware | 161.22 | 6.84 | [156.98, 165.46] |
| full | 157.90 | 3.78 | [155.56, 160.24] |

**`multi_provider`** (12 requests, 3 providers, 1 role) — primary contrast: **full vs causal_only relative improvement = −65.7%** (effect-size criterion not met; bands not separated):

| policy | mean | stdev | 95% CI |
|---|---|---|---|
| sequential | 82.05 | 1.51 | [81.11, 82.98] |
| naive_concurrent | 463.62 | 17.04 | [453.06, 474.18] |
| barrier | 298.32 | 11.29 | [291.33, 305.32] |
| causal_only | 461.05 | 11.81 | [453.74, 468.37] |
| capability_aware | 291.96 | 10.28 | [285.58, 298.33] |
| queue_aware | 158.35 | 2.79 | [156.63, 160.08] |
| full | 158.20 | 4.55 | [155.38, 161.02] |

**`multi_role_multi_provider`** (18 requests, 3 providers, 3 roles) — primary contrast: **full vs causal_only relative improvement = −68.2%** (effect-size criterion not met; bands not separated):

| policy | mean | stdev | 95% CI |
|---|---|---|---|
| sequential | 82.38 | 0.90 | [81.82, 82.94] |
| naive_concurrent | 475.98 | 14.33 | [467.10, 484.86] |
| barrier | 421.52 | 13.70 | [413.03, 430.01] |
| causal_only | 474.11 | 12.13 | [466.59, 481.63] |
| capability_aware | 424.14 | 23.88 | [409.34, 438.94] |
| queue_aware | 157.00 | 1.57 | [156.02, 157.97] |
| full | 150.70 | 2.68 | [149.04, 152.36] |

No repeats were excluded on any variant/policy (`excluded: []`).

## Outcome

**The gate is not cleared.** `full` did not exceed `causal_only`'s mean throughput by the preregistered 15% on either heterogeneity-bearing variant — it was substantially *slower* on both (−65.7% on `multi_provider`, −68.2% on `multi_role_multi_provider`), and the uncertainty bands are not separated in `full`'s favor either.

This matches the mechanistic expectation recorded in the Preregistration section above, before any of these numbers existed: `QueueAwareDispatchPolicy`'s bounded-in-flight cap (default 2) is what actually drives the throughput drop — visible already at rung 6, not just rung 7 — because it limits concurrency for every `backend_hint` group regardless of whether the group has ready capacity, and `LatencySimulatingBackend` has no real concurrency ceiling for that cap to protect against. `FullDispatchPolicy`'s added role-based sub-grouping does not offset this, since no backend in this codebase models any reusable-prefix speedup for adjacent same-role requests (`supports_prefix_caching=False` everywhere). `capability_aware` (rung 5) and `barrier` show a smaller, similar-shaped drop relative to `naive_concurrent`/`causal_only` on the two heterogeneity-bearing variants, from the same `backend_hint`-group-serialization structure (barrier and capability-aware both wait for one `backend_hint` group before starting the next, which costs more when there are multiple groups to serialize across than it does in `single_provider`'s single group).

**This is a legitimate, expected, useful local finding, not a failure of this item's work.** Per `docs/research_roadmap.md`'s own decision-gate framing: "If it does not [clear the gate], do not claim generic causal scheduling as novel. Reframe the first paper around explicit observational semantics and measurable reliability intervention..." — this local rehearsal did exactly what it was preregistered to do: it ran the methodology end to end (define the rule blind → measure → evaluate against the rule as written, without adjusting either after seeing results) and surfaced a real, mechanistically-explained result.

**Scope caveat, restated plainly.** This outcome says nothing about whether capability-aware/queue-aware/prefix-grouping scheduling would help on a *real* inference backend with genuine capacity limits and prefix-cache reuse (Phase 9's actual point). It says only that, in a local CPU-only rehearsal against an infinite-capacity, non-caching simulated backend, the protective/optimization mechanisms these rungs implement have no matching benefit to earn back the overhead they add — which is the mechanistically correct, honestly-predicted result for *this* environment, not evidence about real serving infrastructure. Phase 9's real two-system HPC study (items 16-19) is still required before any research conclusion about the scheduler's actual value can be drawn.
