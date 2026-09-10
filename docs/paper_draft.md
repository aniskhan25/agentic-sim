# An Infrastructure-Agnostic Runtime for Reproducible and Reliable LLM-Agent Simulations

**Status**: first draft, structural skeleton with substantive content. Not camera-ready. All quantitative claims are drawn directly from our own experimental logs and should be re-verified against those logs before submission. Sections marked `[TODO]` need material that does not yet exist (see §6, Limitations).

This draft follows the **fallback framing** from our project's preregistered contribution decision rule: the scheduler-led primary claim did not clear its own preregistered bar, so the paper is centered on the contract/provenance/reliability model and cross-infrastructure portability, with scheduling reported as a rigorously evaluated systems mechanism rather than claimed as a win. This is not a downgrade — it is the decision our own methodology committed to making *before* seeing results, and the honesty of that process is itself part of the paper's contribution (§4.3, §6).

---

## Abstract

`[TODO — write last, after §4 numbers are finalized]`

Draft pointers: (1) a provider-neutral runtime that makes model proposals, repair, policy completion, fallback, contract violations, and retained model autonomy explicitly measurable and comparable across heterogeneous large-scale agentic-simulation infrastructure; (2) validated on two real, independently operated HPC systems with different accelerator vendors (AMD MI250X, NVIDIA GH200) running an identical model revision; (3) a capability-aware causal scheduler was built and evaluated against a preregistered decision gate — under real concurrent load, with three independent measurement confounds identified and corrected, it shows no measurable difference from a causal-order-only baseline on the one workload currently testable on real hardware, a result explained by the workload's lack of genuine multi-provider heterogeneity rather than a mechanism failure; (4) the same investigation reversed an initial "platform-tuned configuration is slower" finding into "ties on one system, real win on the other" once an analogous serving-configuration confound was found and fixed.

---

## 1. Introduction

### 1.1 Motivation

Large-scale agentic simulations increasingly run against real inference infrastructure — self-hosted model servers on HPC systems, managed API endpoints, heterogeneous accelerator vendors — rather than against a single fixed provider. Comparing scheduling or serving-configuration choices across such infrastructure is easy to get wrong in ways that look like a genuine finding: under-provisioned concurrency, uncorrected tie-break defaults, and silent client-side batching ceilings can each independently produce a confident, statistically "real" (non-overlapping) result that reverses once the actual bottleneck is identified. This paper reports a runtime built to make that class of error visible and correctable, together with a full worked example — three independent instances of exactly this failure mode, each diagnosed and fixed within the same investigation.

### 1.2 Research questions

- **RQ1 (Portable semantics).** Can one simulation specification execute unchanged across heterogeneous inference and storage systems while preserving event dependencies, state transitions, and declared invariants?
- **RQ2 (Safe concurrency).** How much parallelism can be extracted without changing the workload's declared observation projection or required happens-before relationships?
- **RQ3 (Reliable generative execution).** How should a runtime distinguish model proposals from repaired, policy-completed, and fallback behavior, and how do those interventions affect reliability, autonomy, diversity, and cost?
- **RQ4 (Infrastructure sensitivity).** Which workload and provider-capability properties determine effective scheduling and serving configurations across local, managed, AMD, and NVIDIA execution?

### 1.3 Contribution hierarchy (as evaluated, not as hoped)

1. **Primary**: a provider-neutral activation, contract, and provenance model that makes model-generated vs. repaired vs. policy-completed vs. fallback behavior, and their effect on reliability and autonomy, explicit and measurable — validated on two real, heterogeneous HPC systems (§4.1).
2. **Enabling mechanisms**: a causal activation graph and verifier, an atomic idempotent commit protocol, and a provider-neutral execution and dispatch interface, given a formal treatment in §2.1 (§2).
3. **Evidence**: controlled, within-system workload measurements on both real systems, reported with explicit statistical criteria, including two full negative-result-then-correction investigations reported honestly rather than smoothed over (§4.2, §4.3).
4. **Evaluated, not claimed**: a capability-aware causal scheduler, tested against a decision gate preregistered before any real-load result existed. The gate is not cleared — full-strategy throughput is statistically tied to a causal-order-only baseline on both systems once three measurement confounds are corrected. We report why this is a workload-coverage limitation, not a negative finding about the mechanism (§4.3, §6).

### 1.4 What this paper does not claim

We do not claim that a single job submitted to a batch scheduler is itself HPC-scale distributed computation; that provider portability alone is novel; that policy-completed behavior is model-generated; that a shared endpoint gives controlled hardware measurements; that one accelerator die and one whole accelerator are equivalent, or that absolute cross-system differences isolate accelerator-vendor effects; or that the two workloads studied establish real-world domain validity on their own. Where we report a cross-system contrast, it is a within-system, normalized comparison, never an absolute cross-vendor ranking.

---

## 2. System Design

### 2.1 Formal model

We fix notation used throughout the rest of the paper. It describes precisely what the runtime computes; propositions below are labeled either *immediate* (true by construction of the scheduling algorithm) or *empirically verified* (checked by repeated real and synthetic execution, not proved).

**Events, activations, and agent state.** Let $\mathcal{Ag}$ be the set of agents. Agent $a \in \mathcal{Ag}$ has state $s_a^{(v)} \in \Sigma_a$ at version $v \in \mathbb{N}$, incremented monotonically on every applied mutation. An **event** $e \in \mathcal{E}$ (an environment tick, a delivered message, or an emitted side effect) triggers zero or more **activations**. An activation is a tuple
$$\alpha = \langle a,\ e,\ r,\ p,\ k \rangle \in \mathcal{Ag} \times \mathcal{E} \times \mathrm{Reason} \times \mathbb{N} \times \mathbb{N},$$
identified uniquely, with attempt number $k$ distinguishing a retry of the same logical activation from a new one. Executing $\alpha$ against a provider yields an **execution result**: a proposed state transition $s_a^{(v)} \to s_a^{(v+1)}$, a set of outgoing messages $M(\alpha) \subseteq \mathcal{M}$, and a set of emitted events $\mathrm{Ev}(\alpha) \subseteq \mathcal{E}$.

**Causal order.** Define $\prec$ ("happens-before") as the smallest transitive relation on activations such that $\alpha \prec \alpha'$ whenever either (i) some $m \in M(\alpha)$ triggers $\alpha'$ (a message-mediated dependency), or (ii) some $e' \in \mathrm{Ev}(\alpha)$ triggers $\alpha'$ (an event-mediated dependency). Two activations are **causally independent**, written $\alpha_1 \parallel \alpha_2$, iff neither $\alpha_1 \prec \alpha_2$ nor $\alpha_2 \prec \alpha_1$.

**Causal readiness and wave decomposition.** At tick $t$, an activation is *causally ready* iff its triggering event has occurred and every $\alpha'$ with $\alpha' \prec \alpha$ has already committed. Let $R_t$ be the set of activations ready for dispatch at $t$, and let $\prec_{R_t}$ be $\prec$ restricted to pairs both in $R_t$ (a same-tick dependency can only arise from a message or event produced *within* $R_t$ itself, since any cross-tick parent has already committed and imposes no further wait). A **wave decomposition** of $R_t$ is the topological layering of $(R_t, \prec_{R_t})$: $W_0 = \{\alpha \in R_t : \nexists\, \alpha' \in R_t,\ \alpha' \prec \alpha\}$, and $W_i = \{\alpha \in R_t \setminus \bigcup_{j<i} W_j : \forall\, \alpha' \prec \alpha,\ \alpha' \in \bigcup_{j<i} W_j\}$. By construction, $\forall\, \alpha_1, \alpha_2 \in W_i,\ \alpha_1 \parallel \alpha_2$ — a scheduling strategy may run every activation in one wave concurrently without violating $\prec$, and must complete wave $W_i$ before starting $W_{i+1}$.

*Proposition 1 (wave-safety, immediate).* Any scheduling strategy that dispatches concurrently only within a wave $W_i$, in wave order, preserves $\prec$ regardless of real execution latency variance — no ordering violation is possible because, by construction, no two members of $W_i$ are $\prec$-comparable.

*Proposition 2 (single-wave collapse on today's workloads, empirically verified).* On every workload evaluated in this paper, a message sent during tick $t$ can only be read starting tick $t+1$ at the earliest, so no activation in $R_t$ ever depends on another activation in $R_t$: $\forall\, t,\ W_0 = R_t$ (one wave). Consequently the *Causal-Order-Only* and *Naive-Concurrent* strategies (§2.7) are observationally equivalent (Def. below) on both evaluated workloads today — they are distinguished only on a workload with genuine intra-tick dependencies, which neither evaluated here has (§6).

**Observational equivalence.** Two executions $\pi_1, \pi_2$ of the same specification are observationally equivalent, $\pi_1 \sim \pi_2$, iff there is a bijection between their committed activations that preserves $\prec$, every agent-visible message's content, and every agent's final state version. $\sim$, not wall-clock replay, is the notion this paper uses as its target of comparison — agreement on the committed causal graph up to reordering of $\parallel$-related activations.

*Proposition 3 (scheduling-strategy equivalence under no write-conflict, empirically verified).* If no two causally independent activations write-conflict on shared environment state, then execution under the *Sequential* strategy and execution under any wave-respecting concurrent strategy are observationally equivalent: $\pi_{\text{sequential}} \sim \pi_{\text{concurrent}}$. Checked directly (not merely asserted) on every non-conflict synthetic workload shape and on both real workloads: every scheduling strategy produces identical structural graph invariants and zero causal-verification violations.

**Atomic commit.** A commit unit for activation $\alpha$ is $C(\alpha) = \langle \Delta s_a,\ M(\alpha),\ \mathrm{Ev}(\alpha),\ v_{\text{expected}} \rangle$. The commit transition $\mathrm{commit}: \Sigma \times C \to \Sigma \times \{\textsc{committed}, \textsc{duplicate}, \textsc{conflict}\}$ satisfies:
- **idempotence**: if the activation was already committed, $\mathrm{commit}(\sigma, C(\alpha)) = (\sigma, \textsc{duplicate})$ — re-application is a no-op, not a re-apply;
- **optimistic version safety**: if $v_{\text{expected}} \ne$ agent $a$'s current version in $\sigma$, $\mathrm{commit}(\sigma, C(\alpha)) = (\sigma, \textsc{conflict})$ — $\sigma$ unchanged;
- **all-or-nothing**: otherwise, $\Delta s_a$, $M(\alpha)$, and $\mathrm{Ev}(\alpha)$ are applied together or not at all.

This scope is $\langle \Delta s_a, M(\alpha), \mathrm{Ev}(\alpha)\rangle$ only — shared environment-state mutation is *not* part of $C(\alpha)$ in the current implementation (§6).

**Contracts.** A contract is a predicate over a proposed action, checked before commit: $\mathrm{bounded}_B(\delta) \equiv |\delta| \le B$; $\mathrm{cardinality}(\mathrm{acts}) \equiv$ no (agent, action-type, target) triple is applied more than once per activation; $\mathrm{must\_not}(\mathrm{act}, \Phi) \equiv \mathrm{act} \notin \Phi$ for a declared forbidden set $\Phi$. A step is *semantically valid* iff its parsed proposal is well-formed and every active contract holds.

**Reliability metrics.** For a run with committed activations $A$, retained autonomy is $\rho = \frac{1}{|A|}\sum_{\alpha \in A} \mathbb{1}[\text{committed atoms of } \alpha \text{ are all genuinely model-proposed}]$ (§4.1's "model autonomy rate"); usefulness is $u(\alpha) = \mathbb{1}[\alpha\text{'s commit succeeded and its result was semantically valid}]$, and throughput is $\frac{\sum_{\alpha \in A} u(\alpha)}{T_{\text{wall}}}$ (§3.3's useful-throughput metric).

### 2.2 Observational semantics and activation identity

The runtime commits to the $\sim$-equivalence model above at the implementation level: a fixed activation representation with an explicit attempt number (formalized as $k$ above), a fixed causal-parent chain over messages and events (formalizing $\prec$), and monotonically versioned agent and environment state (formalizing $v$). Two runs of the same specification are compared by $\sim$, not by wall-clock replay.

### 2.3 Provider-neutral execution interface

A narrow execution interface (a single batched-execution entry point) is implemented identically by a deterministic simulated provider, a rule-based provider, a synthetic-workload provider, and two real inference providers — one managed API endpoint and one self-hosted, OpenAI-API-compatible server, the latter derived from the former's fully generic request/response/repair/provenance logic and differing only in authentication and prefix-caching/context-length defaults. All providers are exercised by one shared conformance test suite, not several independently maintained, potentially diverging implementations.

### 2.4 Contracts and per-atom provenance

Every proposed agent action passes through the contracts defined in §2.1: a hard-prohibition contract, a boundedness contract, a cardinality contract, and an allowed-action-set contract. Violations are counted per atom, not discarded. Every step produces a provenance record carrying activation identity, attempt number $k$, provider and model identity, causal parents, the state version read and written ($v \to v+1$), accelerator and serving-runtime identity, and an explicit configuration-mode label (common-denominator vs. platform-tuned, §2.6) — but not yet a content hash of the request or response; that field is reserved in the provenance schema but currently unpopulated (§6).

### 2.5 Causal verification and atomic commit

An independent verification pass checks the message-mediated $\prec$-chain for duplicate activations, missing causal parents, cycles, and stale-read conflicts — verified to report zero violations on real executions of both workloads, and independently verified to detect each violation class when deliberately constructed. The state store implements the commit transition of §2.1 identically across two independent storage backends, checked by one shared conformance suite. Environment-state mutation remains outside $C(\alpha)$'s boundary, applied as a separate batched step — a scoped, documented limitation, not an oversight (§6).

### 2.6 Common-denominator and platform-tuned modes

Every real evaluation run declares an explicit configuration-mode label: common-denominator (identical serving configuration on both systems, the feature-parity intersection of what both platforms actually support) or platform-tuned (independently selected per system via a frozen, preregistered selection procedure with a documented tie-break rule). This lets every reported effect be attributed to a labeled configuration choice, never silently conflated.

### 2.7 The scheduling-strategy ladder

Seven scheduling strategies, each strictly extending the wave-safety guarantee (Proposition 1) of the one before it with a further optimization: *Sequential* (one activation at a time), *Naive-Concurrent* (all of $R_t$ concurrent, no wave decomposition), *Barrier* (waves as batching boundaries only), *Causal-Order-Only* (waves as defined in §2.1, no further optimization), *Capability-Aware* (dispatches a wave's group concurrently only if the target provider declares concurrency support), *Queue-Aware* (adds a bounded per-provider in-flight cap $\kappa$), *Full* (adds role/prefix-adjacent reordering within a group). All seven strategies conform to one common scheduling interface; the simulation engine requires no changes to add a new strategy.

---

## 3. Evaluation Methodology

### 3.1 Systems

Two real, independently administered HPC systems with different accelerator vendors: one AMD-accelerator system (ROCm software stack) and one NVIDIA-accelerator system (CUDA software stack), each provisioning a single accelerator per evaluation job. Both run an identical, pinned instruction-tuned model revision at the 7-8B parameter scale, confirmed to load and serve real traffic on both platforms via a live health check, not assumed compatible from documentation.

### 3.2 Workloads

Two multi-role agentic coordination workloads — a disaster-response coordination task (4 roles) and a supply-chain coordination task (5 roles) — are evaluated end-to-end against real self-hosted inference on both systems. Three further workload families specified by our evaluation plan — a deterministic minimum-dependency-graph kernel, synthetic dependency-graph shapes, and deterministic failure injection — exist as tested implementations with hand-derived structural invariants, but currently run only against simulated providers; the harness that runs them does not yet accept a real inference provider (§6).

### 3.3 Metrics

A reliability-aware useful-throughput metric (computed only from steps that pass all contracts, not raw request rate), per-request latency, a retained-autonomy rate (the fraction of committed behavior that is genuinely model-generated rather than policy-completed), and per-atom contract-violation counts across all four contract classes.

### 3.4 Statistical criterion

Every contrast in this paper uses the same rule throughout: mean useful-throughput ± 1 standard deviation band overlap across repeated runs. Non-overlapping bands are reported as a real effect; overlapping bands are reported as statistically indistinguishable, never as "probably about the same." Where a serving- or scheduling-parameter choice must be made among statistically tied candidates, the smaller/simpler value wins by a rule fixed before any sweep was run.

---

## 4. Results

### 4.1 Reliability and provenance across heterogeneous infrastructure

We report the per-origin behavior breakdown, retained model autonomy, and contract-violation counts for the same eight real runs used in §4.2 (common-denominator and corrected platform-tuned configurations, both workloads, both systems, real concurrent load, most-solid available repetition count per combination). The "invalid after repair" figure reflects a proposal's validity *after* the pipeline's own repair-retry budget is exhausted, not the model's raw first-pass output — so it measures how often repair alone fails to recover a usable structured output, not raw generation quality.

| System | Workload | Mode | Steps | Invalid after repair | Repair attempted | Semantic-valid | Guard-added msgs/step | Guard-added actions/step | Model autonomy rate | Violations (must-not / bounded / cardinality / state) |
|---|---|---|---|---|---|---|---|---|---|---|
| A (AMD) | disaster-response | common-denominator | 11,655 | 64.8% | 82.1% | 35.2% | 1.11 | 0.26 | 0.02% | 0 / 0 / 0 / 1 |
| A (AMD) | disaster-response | platform-tuned (corrected) | 11,663 | 65.2% | 81.5% | 34.8% | 1.11 | 0.26 | 0.01% | 0 / 0 / 0 / 2 |
| A (AMD) | supply-chain | common-denominator | 4,393 | 59.8% | 75.8% | 40.2% | 1.47 | 0.017 | 0.00% | 1 / 0 / 0 / 0 |
| A (AMD) | supply-chain | platform-tuned (corrected) | 4,395 | 59.9% | 74.0% | 40.1% | 1.47 | 0.017 | 0.00% | 0 / 0 / 0 / 0 |
| B (NVIDIA) | disaster-response | common-denominator | 5,832 | 48.9% | 58.6% | 51.1% | 1.11 | 0.26 | 0.00% | 0 / 0 / 0 / 0 |
| B (NVIDIA) | disaster-response | platform-tuned (corrected) | 5,835 | 47.4% | 57.8% | 52.6% | 1.11 | 0.26 | 0.00% | 0 / 0 / 0 / 0 |
| B (NVIDIA) | supply-chain | common-denominator | 1,464 | 56.6% | 63.7% | 43.4% | 1.48 | 0.016 | 0.00% | 0 / 0 / 0 / 0 |
| B (NVIDIA) | supply-chain | platform-tuned (corrected) | 1,464 | 58.5% | 64.3% | 41.5% | 1.48 | 0.016 | 0.00% | 0 / 0 / 0 / 0 |

**Three findings, in order of importance.**

First, and most consequential for RQ3: **retained model autonomy is effectively zero across every system, workload, and configuration** (0.00–0.02%, i.e. indistinguishable from zero at this precision). Despite a real 7-8B instruct model producing genuinely variable free-text completions, essentially none of the runtime's committed messages or actions in this dataset trace back to a raw, unmodified model proposal — the runtime's policy-completion layer supplies the committed behavior in practically every step. Yet **useful-step coverage is 99.99%** (11,654 of 11,655 steps on the largest run) — the simulation keeps producing contract-satisfying, committed behavior throughout, but that reliability is achieved by the scaffolding around the model, not by the model. This is exactly the distinction RQ3 asks a runtime to make explicit and measurable, and exactly the risk that contracts can conceal a loss of model agency if not reported this way — here it does not, because the metric is reported plainly rather than folded into an undifferentiated throughput number.

Second, **raw model output is invalid, even after in-loop repair, roughly half the time** (47–65% across combinations), with repair attempted on 58–82% of steps. Repair attempts and final invalidity move together, not inversely — attempting repair more often does not correspond to a lower final-invalid rate across these rows, suggesting the repair loop's fixed retry budget recovers a minority of malformed completions rather than reliably rescuing them; policy completion, not repair, is what keeps useful-step coverage near 100%.

Third, **the two configuration modes are nearly identical on every reliability metric within a system/workload pair** (e.g., System A disaster-response invalid rate 64.8% vs. 65.2%; System B disaster-response semantic-valid 51.1% vs. 52.6%). This is expected and serves as an internal check: the two configurations differ only in serving parameters (batching and concurrency limits, with precision already fixed identically), never in model weights or scenario logic, so reliability behavior should — and does — stay stable across the throughput reversal reported in §4.2. Contract violations are rare on both systems (4 total across 46,701 combined steps: 3 state-mutation and 1 must-not, all on System A) and are reported exactly as observed rather than rounded to zero.

The one cross-system pattern worth flagging cautiously, not over-interpreting: System B's invalid-output rate is consistently lower than System A's on the disaster-response workload (~48% vs. ~65%) despite an identical model revision, identical numeric precision for cached attention state, and near-identical decoding parameters. Per §1.4, we do not claim this isolates an accelerator-vendor effect — the two systems also differ by one minor release of the serving software and in the underlying attention-kernel implementation actually exercised, either of which could plausibly explain a generation-quality difference of this size. This is exactly the kind of software-maturity confound anticipated in §6, reported as an open observation rather than resolved into a hardware claim.

### 4.2 Platform-tuned vs. common-denominator configuration: a confound, found and corrected

The platform-tuned serving configuration was selected via a one-factor-at-a-time sweep against a live server (3 repetitions per candidate). Comparing the common-denominator configuration against it at confirmatory scale (10, then 30 repetitions) found **no statistically distinguishable difference** on either system, either workload (10-repetition range: −6.6% to +59.7%; 30-repetition: all four combinations converge to under ±1.5%, bands overlapping). Investigating *why* — not simply accepting a null result — found the comparison had never generated enough real concurrent backend load to stress either configuration's concurrent-sequence limit: the evaluation harness defaulted to a 4-5 agent roster and a low per-tick event-processing cap, and the scheduling strategy's own internal worker pool defaulted to a small fixed size, regardless of the server's configured capacity.

Fixing all three (raising agent roster size, the per-tick event cap, and the scheduling strategy's worker-pool size) and rerunning under genuine concurrent load (dozens of real concurrent requests per tick, confirmed via provider-side step counts) **reversed the finding**: the platform-tuned configuration was now measurably *slower* than common-denominator on every combination, non-overlapping on 2 of 4 at exploratory scale (5 repetitions), confirmed non-overlapping on all 4 at confirmatory scale (15 repetitions: System A −18.2%, System B −22.0%).

Investigating this reversal in turn found the original sweep's concurrent-sequence-limit pick (the same modest value on both systems) had itself been measured under the same insufficient-concurrency regime and had never been tie-broken against real load. Re-sweeping the three tied-at-selection-time serving parameters under real concurrent load found the token-batching limit re-confirms unchanged, but the concurrent-sequence limit corrects to a substantially larger value on System A (matching the common-denominator configuration's own value) and a value exceeding it on System B — a real, non-overlapping correction on both systems.

Rerunning the comparison with the corrected configuration (the common-denominator side unchanged, reused directly) reverses the finding a third time: **System A is now a genuine statistical tie** (disaster-response +6.7% at 15 repetitions, narrowing to +1.6% at 30 repetitions — converging toward zero, not away from it, confirming it is noise, not an under-powered real effect); **System B now measurably beats the common-denominator baseline**, non-overlapping on both workloads (disaster-response +15.1%, supply-chain +19.1%).

| System | Workload | Original (low-load) | Under real load, uncorrected configuration | Under real load, corrected configuration |
|---|---|---|---|---|
| A | disaster-response | +4.6% (overlap) | −18.2% (real) | +1.6% (overlap, 30 reps) |
| A | supply-chain | +59.7% (overlap, noisy) | −21.4% (real) | +0.6% (overlap, 15 reps) |
| B | disaster-response | −6.6% (overlap) | −22.0% (real) | +15.1% (real) |
| B | supply-chain | +10.9% (overlap) | −15.1% (real) | +19.1% (real) |

Zero cache-eviction preemption across every one of these real runs, checked directly in server logs, not only by automated pattern matching — the effect is a batching/queueing efficiency phenomenon, not the frozen procedure's hard disqualifier.

### 4.3 The scheduling decision gate under real concurrent load

The scheduling-strategy decision gate (preregistered: at least 15% relative improvement of the *Full* strategy over *Causal-Order-Only*, non-overlapping, on heterogeneity-bearing workload variants) was first evaluated on a synthetic latency-simulating harness and, separately, on a real full-ladder pilot against live servers on both systems — both at an agent roster size of one replica per role. That real-hardware evidence showed *Full* matching or exceeding every other strategy (System B: highest of all seven, +80.2% over *Sequential*; System A: in line with *Causal-Order-Only*).

Given §4.2's finding that this exact measurement regime (roster size, per-tick event cap, scheduling worker-pool cap) hid or inverted a real effect elsewhere, we reran the full ladder under the same real-load settings that reversed §4.2. **Result: *Full* collapsed to a large, real regression** — System B −73.2%, System A −71.6%, both non-overlapping — the opposite of the earlier conclusion.

Diagnosing this found two further, independent, previously unknown confounds, neither related to roster size:

1. Four of the seven strategies (*Barrier*, *Capability-Aware*, *Queue-Aware*, *Full*) all defaulted to an internal per-round batching cap of 8 requests, independent of any worker-pool setting — forcing several sequential dispatch rounds per tick regardless of how large the worker pool was configured. Correcting this fully resolved *Naive-Concurrent*/*Barrier*/*Causal-Order-Only*/*Capability-Aware* into a tight, mutually indistinguishable cluster on both systems (previously ~3x apart).
2. *Queue-Aware*/*Full*'s per-provider in-flight concurrency cap (4) had itself been tuned under the same insufficient-load regime — the exact structural parallel to §4.2's serving-parameter bug. Even with confound (1) fixed, *Full* remained a large, real regression (System A −66.1%, System B −63.8%). A real sweep of the cap under genuine load found 4 a real, non-overlapping loser on both systems; 64 ties with 128 and wins the tie-break, closely matching *Causal-Order-Only*'s own throughput.

With both confounds corrected, a final confirmatory rerun found **all six concurrent scheduling strategies statistically indistinguishable from one another on both systems** (*Full* vs. *Causal-Order-Only*: System A +1.1%, System B −0.3%, both overlapping). Zero preemption, zero excluded repetitions, across every real run in this investigation.

| Stage | System A (*Full* vs. *Causal-Order-Only*) | System B (*Full* vs. *Causal-Order-Only*) |
|---|---|---|
| Low concurrency (original) | tied / *Full* recovers | tied / *Full* highest of 7 |
| Real load, uncorrected | **−71.6%** (real) | **−73.2%** (real) |
| Real load, batch-cap fixed | −66.1% (real) | −63.8% (real) |
| Real load, both fixed | +1.1% (overlap) | −0.3% (overlap) |

**Interpretation.** The decision gate is not cleared. This is not evidence that capability-aware, queue-aware, or prefix-grouping scheduling is ineffective — it is evidence that the one workload currently testable on real hardware provides no genuine multi-provider heterogeneity: every real agent in every real run in this study routes to the same single serving endpoint, so the capability-aware strategy's per-provider capability gate and the queue-aware strategy's per-provider backpressure budget have literally nothing to differentiate. The mechanism has never been tested under the condition it is designed for. §6 discusses what that test requires.

### 4.4 Cross-system portability

The same simulation specification, unmodified, executes on both accelerator ecosystems, producing zero causal-verification violations and identical structural invariants on every real run reported above. All cross-system comparisons in this paper are within-system, normalized effect sizes (§3.4); we do not report or interpret absolute cross-system throughput ratios as isolating accelerator-vendor effects (§1.4).

---

## 5. Discussion

`[TODO — expand]`. Draft points:
- The confound-discovery methodology (§4.2, §4.3) is itself a transferable finding for anyone benchmarking LLM-serving or agent-scheduling configurations: a null or a confidently "real" result measured under insufficient concurrent load cannot be trusted without first confirming the load level actually stresses the parameter under test. Three independent instances of exactly this failure mode were found and corrected in one investigation arc, each via the same diagnostic pattern — trace the call path to the true binding constraint, not the parameter that was intended to bind.
- A preregistered decision gate with a stated fallback framing let this paper report a non-cleared gate as a workload-coverage finding rather than as pressure to reframe the contribution after the fact.

---

## 6. Limitations and Threats to Validity

- **No genuine multi-provider heterogeneity has been tested.** The capability-aware and queue-aware strategies' core mechanisms are keyed on a per-request provider label; every real-hardware run in this paper uses exactly one provider. Testing them properly requires a routing layer over multiple concurrently live provider instances with genuinely different capacity/capability, and a scenario that actually assigns different agents to different providers — not yet built (§4.3).
- **Full-node placement evidence predates these fixes.** The only full-node measurements available were collected before the roster-size, batch-cap, and in-flight-cap corrections above were known to matter, and have not yet been rerun under corrected settings; they are not cited as confirmatory in this draft.
- **Three of five specified workload families cannot yet run on real inference.** The deterministic-kernel, synthetic-dependency-graph, and failure-injection families exist as tested, real implementations, but the harness that runs them currently accepts only a simulated provider by design; extending it to a real provider is unresolved.
- **Content-addressable provenance is defined but not populated.** The provenance schema reserves fields for request, prompt, and response content hashes; no code path currently computes them. Provenance in this paper is by identity, version, and timing, not by content hash.
- **Replay and recovery (checkpoint, resume-after-termination, response replay) is unimplemented.** What exists today is determinism (two independent runs of the same specification produce identical trace signatures), which is a narrower guarantee.
- **Atomic commit does not cover environment-state mutation.** The commit boundary covers one activation's agent-state update, outgoing messages, and emitted events; environment state (shared across agents within a tick) is applied as a separate, non-transactional batched step.
- **Single model, single revision, 7-8B parameter class.** This is not a model-scaling study; conclusions about reliability, autonomy, and scheduling are scoped to this model class until repeated at other scales.
- Every non-claim in §1.4 applies throughout.

---

## 7. Conclusion

`[TODO]`

---

## Reproducibility

Every quantitative claim in this paper is backed by raw, versioned experimental logs and reproducible via a documented, re-runnable evaluation pipeline: each result derives from a scripted harness invocation against a live server, and every aggregation is produced by a deterministic script over those raw logs rather than a one-off analysis. Frozen serving configurations, their full evidence trails, and the complete chronological investigation log — including every superseded finding and why it was superseded, never silently overwritten — are maintained as part of the project's release artifact.
