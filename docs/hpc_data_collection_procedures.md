# HPC Data Collection Procedures — Frozen Before Collection

This document is `docs/research_roadmap.md` item 18: "Freeze common-denominator and platform-tuning procedures before HPC data collection." Its wording, and `evaluation_plan.md`'s Statistical Design bullet ("Freeze workloads, primary contrasts, and configuration-selection **procedures** before primary collection") and B2 ("select configurations through a documented pre-experiment **procedure**" then "**freeze the selected configurations** before collecting primary results"), all draw the same distinction: freezing the *methodology* for choosing a configuration is a separate, earlier act than freezing the *configuration itself*. This document does the former. It is written before any self-hosted backend exists and before any real HPC data has been collected, precisely so the rule can't be quietly shaped by results it hasn't seen yet — the same discipline `docs/scheduler_contribution_gate.md` (item 14) already applied to the scheduler-effect decision gate, reused here rather than reinvented, for a different axis: B1/B2 serving-configuration selection, not scheduler-policy contrasts (those stay exactly as items 12-14 already defined them).

**Scope note, stated plainly**: this freezes *procedures*, not *values*. No self-hosted `ExecutionBackend` exists in code today and no HPC access has produced any data — the actual selected `--tensor-parallel-size`, attention backend, etc. for either system do not exist yet and are not invented here. `docs/lumi_deployment_manifest.md` covers LUMI's concrete B1 configuration and sweep space already; this document does not repeat it, only cross-references it. Roihu has no deployment manifest yet (item 17's open remainder) — where this document needs a Roihu-side sweep space to make the procedure genuinely system-agnostic, it is marked **provisional**, not final.

## Common-denominator mode — frozen procedure

### Feature-parity determination

Before any run: for each system, enumerate the serving-runtime features actually available and stable (structured output, prefix caching, a given batching mode, a given KV-cache dtype). Take the **intersection** across both systems. Disable, on both systems, any feature not in that intersection — never enable a feature on one system only "because it's available there." This is the literal operational meaning of B1's "largest stable shared feature set": a stable feature is only in-scope for common-denominator mode if it's confirmed available on *both* LUMI and Roihu at the time the intersection is computed, not assumed transferable from one platform's documentation to the other's.

### Statistical commitments (closing `docs/lumi_deployment_manifest.md`'s deferred placeholder)

- **Minimum repetition count: 10 runs** per (workload family × model × placement level × mode) combination — matching item 14's own precedent (`docs/scheduler_contribution_gate.md` used 10 repeats per policy per variant) rather than picking a new, unrelated number.
- **Warm-up rule: a fixed count of 20 discarded warm-up requests** per configuration before any timed measurement begins, generalizing `scripts/run_lumi.sh`'s existing `AITTA_WARMUP`/`check-aitta --wait` pattern (poll the self-hosted server's health endpoint until it's serving, then discard the first 20 completed requests). A **request-count** warm-up is used deliberately instead of a **time-based** one (e.g. "warm up for 60 seconds"): raw hardware speed differs between LUMI and Roihu, so a fixed duration would itself be a non-identical procedure between systems, while a fixed request count is not.
- **Per-configuration wall-clock budget: 30 minutes**, matching the existing precedent already in this repo's LUMI tooling (`scripts/run_lumi_array.sh`'s SLURM time limit, sized for comparable large-scale runs) — a configuration's measurement window ends at 10 repetitions completed or 30 minutes elapsed, whichever comes first; hitting the time budget before 10 repetitions complete is recorded as a partial-coverage exclusion (below), not silently treated as if the full count were reached.
- **Exclusion rule**: any repeat that errors, times out, or is interrupted is excluded from that configuration's statistics and logged with its cause — never silently dropped, matching item 14's exact precedent and `evaluation_plan.md`'s "Report failed, interrupted, and invalid runs with prespecified exclusion rules."

## Platform-tuned mode — frozen selection procedure

### Selection metric

**Primary metric: useful agent-steps per second** (already the metric `docs/lumi_deployment_manifest.md`'s sweep description names). **Hard disqualifying constraint: zero KV-cache preemption** during the measurement window — a configuration that preempts is disqualified from selection regardless of its raw throughput, not merely penalized. This makes both requirements binding rather than descriptive, closing the gap between `lumi_deployment_manifest.md`'s prose sketch ("select the configuration that maximizes useful agent-steps/sec without KV-cache preemption") and an actual frozen rule.

### Sweep space

**LUMI**: exactly the space already fixed in `docs/lumi_deployment_manifest.md`'s Platform-tuned configuration section (`--max-num-batched-tokens`, `--max-num-seqs`, `--gpu-memory-utilization`, parallelism strategy, attention backend, KV-cache dtype) — cross-referenced here, not restated.

**Roihu (provisional — no Roihu manifest exists yet, this is a placeholder sweep space to be superseded once one is drafted)**: the CUDA/vLLM-equivalent parameters, structurally mirroring LUMI's space so the two systems' tuning procedures stay comparable:
- `--max-num-batched-tokens`: same sweep values as LUMI (`8192`/`16384`/`32768`/`65536`) — vLLM's batching knob is identical across ROCm/CUDA builds.
- `--max-num-seqs`: same sweep values as LUMI (`32`/`64`/`128`/`256`).
- `--gpu-memory-utilization`: same sweep values as LUMI (`0.85`/`0.90`/`0.95`).
- Parallelism: independent replicas per GH200 GPU (dense 8B/14B-class models) vs. `--tensor-parallel-size` scaled to Roihu's 4-GPU-per-node topology (so `TP=2`/`TP=4`, not `TP=8` — Roihu has 4 GH200s per node, not 8 GCDs).
- Attention backend / quantization: CUDA-native equivalents (FlashAttention variants, FP8 KV-cache where supported) — benchmarked, not assumed transferable from AMD's AITER-specific guidance.

### Tie-breaking rule

If two or more non-disqualified configurations' useful-agent-steps/sec means have overlapping mean ± 1 stdev bands (the same non-overlapping-bands criterion item 14 used for the scheduler gate), they are treated as statistically indistinguishable, and the **simpler, lower-resource configuration wins**: prefer lower `--gpu-memory-utilization`, then simpler parallelism (independent replicas over tensor parallelism, lower `--tensor-parallel-size` over higher), in that order. This avoids selecting an artificially aggressive configuration whose apparent edge is noise, and keeps the choice explainable rather than arbitrary.

### Freeze-timing commitment

Select once, using the procedure above, **before** collecting any primary results. Do not re-tune after primary collection begins, even if a later configuration looks more promising — a new candidate discovered later is exploratory data for the *next* study, not a retroactive change to this one, per `evaluation_plan.md`'s "Separate exploratory tuning data from confirmatory results." Every parameter that differs between the frozen common-denominator configuration and the frozen platform-tuned configuration must be recorded in an explicit divergence table (parameter name, common-denominator value, platform-tuned value) — not just the final platform-tuned values in isolation — per B2's "record every divergence from common-denominator mode."

## What this does not freeze

- The actual selected configuration values for LUMI or Roihu — neither exists yet; no self-hosted `ExecutionBackend` and no HPC access exist today (see `docs/lumi_deployment_manifest.md`'s Explicit gaps section, unchanged).
- Roihu's deployment manifest — the sweep space above is provisional scaffolding for this procedure document only, not a substitute for item 17's still-open Roihu half.
- The scheduler-policy contrasts (sequential vs. causal-only, causal-only vs. full) — already frozen by items 12-14; unaffected by this document.
