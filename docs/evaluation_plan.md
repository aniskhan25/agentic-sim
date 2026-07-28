# Evaluation Plan: Portable Causal Execution

## Purpose

This document is the canonical experimental specification for the contribution described in [research_roadmap.md](research_roadmap.md). It separates semantic correctness, scheduling effects, and delivered-system performance so that infrastructure portability is not confused with an AMD-versus-NVIDIA hardware claim.

The primary empirical questions are:

1. Does causal-ready execution reduce end-to-end completion time relative to sequential execution while preserving the workload's declared observational semantics?
2. Do capability-constrained batching, provider-queue awareness, backpressure, and reusable-prefix grouping improve useful throughput beyond that generic causal-only baseline?

The architecture and semantic definitions used by the experiments are specified in [target_architecture.md](target_architecture.md).

## Evaluation Platforms

| System | GPU-node topology | Host and software ecosystem | Role |
| --- | --- | --- | --- |
| LUMI | 4 AMD MI250X modules, exposed as 8 GCDs with 64 GB HBM each | x86 AMD EPYC, ROCm, Slingshot | Controlled AMD/ROCm self-hosted inference |
| Roihu | 4 NVIDIA GH200 Grace Hopper superchips with 96 GiB GPU memory each | ARM Grace, CUDA, InfiniBand NDR | Controlled NVIDIA/CUDA self-hosted inference |

Hardware details are refreshed when experiments begin and recorded in every platform manifest. Initial specifications come from the [LUMI-G hardware documentation](https://docs.lumi-supercomputer.eu/hardware/lumig/) and [Roihu system documentation](https://docs.csc.fi/computing/systems-roihu/).

These machines differ in accelerator generation, device count, memory, host architecture, network, software stack, and scheduler conditions. They are not a controlled single-variable vendor comparison. Primary performance conclusions use normalized effects relative to the sequential baseline within the same system, model, placement, serving mode, and workload.

## Required Substrates

1. local deterministic, rule, and response-replay execution;
2. controlled self-hosted inference on LUMI;
3. controlled self-hosted inference on Roihu.

Optional portability observations may include Aitta, a workstation model server, a cloud OpenAI-compatible endpoint, or another HPC system. Shared or managed endpoints are excluded from primary performance conclusions.

## Workload Suite

### Minimum kernel suite

The minimum suite is implemented before scheduler development and includes seeded:

- chains;
- fan-out trees;
- fork/join graphs;
- independent branches;
- mixed dependency graphs;
- conflicting state and environment writes.

It has deterministic expected causal graphs, conflict sets, invariants, and component-level timing. Its purpose is to validate semantics and expose scheduler overhead independently of LLM inference.

### Publication suite

The publication suite expands the kernel with:

1. **deterministic kernel:** scheduler, validation, commit, and storage overhead;
2. **storm coordination:** bursty, role-differentiated messaging and critical events;
3. **supply-chain coordination:** environment actions and conflicting writes;
4. **synthetic dependency graphs:** controlled depth, fan-out, joins, and conflicts;
5. **failure workloads:** invalid outputs, timeouts, duplicates, and provider interruption.

Dimensions include:

- agent count;
- event fan-out and causal depth;
- activation burst size;
- conflicting-write ratio;
- input and output length distributions;
- shared-prefix ratio;
- environment or tool delay;
- logical deadline tightness;
- invalid-output and timeout rates;
- retry, repair, policy-completion, and fallback policy.

Every workload definition contains a stable configuration, fixture or seeded generator, workload identity, expected invariants, execution-independent summary, scale parameters, and repetition rule.

## Experiment Layers

### Layer A: Runtime semantics

Use deterministic and response-replay execution on ordinary CPU resources to isolate runtime behavior from model serving.

Measure:

- observational equivalence of sequential strict and asynchronous strict execution;
- causal equivalence of sequential and causal policies;
- causal-graph and verifier overhead;
- scheduling and atomic-commit overhead;
- stale-read and conflict detection;
- deterministic and response replay;
- interruption recovery and duplicate suppression.

Layer A establishes correctness. It does not depend on LUMI or Roihu performance.

### Layer B: Controlled inference

Self-host the same open model on both systems using two explicitly different modes.

#### B1. Common-denominator mode

This mode tests portability and normalized scheduling effects using the largest stable shared feature set:

- identical model revision and tokenizer;
- BF16 as the primary common precision;
- identical prompt corpus and output-token limit;
- the same serving-runtime revision or explicitly paired compatible revisions;
- identical decoding parameters;
- matched batching, structured-output, and prefix-cache features, disabling unavailable features on both platforms;
- fixed warm-up, duration, and repetition rules;
- exclusive model-server allocations;
- recorded compiler, driver, ROCm or CUDA, Python, framework, container, and serving-runtime versions.

#### B2. Platform-tuned mode

This mode tests the best stable delivered performance available on each system:

- retain the same model revision, workload requests, decoding semantics, and output limits;
- tune tensor parallelism, batch limits, memory utilization, cache behavior, kernels, and serving-runtime revision independently;
- select configurations through a documented pre-experiment procedure;
- freeze the selected configurations before collecting primary results;
- record every divergence from common-denominator mode;
- report results as delivered-system observations rather than isolated hardware-vendor effects.

Use two placement levels in each mode where stable:

1. **single logical device:** one MI250X GCD and one GH200 GPU, reported as a practical device-level observation rather than equivalent silicon;
2. **full node:** eight MI250X GCDs on LUMI and four GH200 GPUs on Roihu, reported as delivered node capacity.

Use at least one identical 7B/8B-class model that fits on one logical device. A larger tensor-parallel model is included only when the same model and precision deploy reliably on both systems. Multi-node inference remains a stretch experiment.

### Scheduler baselines and ablations

Every end-to-end study uses the following policy ladder:

1. **sequential FIFO:** reference execution with no overlap;
2. **naive concurrent:** dispatch ready work without causal conflict protection;
3. **barrier batch:** batch only at explicit synchronization boundaries;
4. **causal-only:** use causal readiness and state conflicts but no provider-capability, queue, backpressure, or prefix optimization;
5. **capability-aware:** add capability-constrained placement and batching;
6. **queue-aware:** add provider-queue observations and bounded backpressure;
7. **full:** add reusable-prefix grouping.

The causal-only policy deliberately represents generic dependency-aware scheduling. Sequential versus causal-only measures the value of safe concurrency. Causal-only versus full is the primary contrast for the proposed scheduler contribution. Intermediate policies attribute any incremental effect to capability constraints, batching, queue awareness, backpressure, or prefix grouping rather than generic causal reordering.

### Layer C: End-to-end simulation

Run the publication workload suite through controlled self-hosted inference on both systems.

Factors:

- execution policy: the complete scheduler baseline and ablation ladder;
- agent scale: small, medium, saturation, and weak-scaling configurations;
- workload shape: chain, fan-out, fork/join, and mixed;
- failure mode: none, malformed output, timeout, duplicate response, interruption;
- model: small and, when feasible, large;
- placement: single device, full node, and optional multi-node;
- serving configuration: common denominator and platform tuned;
- prompt sharing: low and high shared-prefix workloads.

The two prespecified performance contrasts are:

1. causal-only versus sequential execution, measuring the benefit of safe causal concurrency;
2. full capability-aware scheduling versus causal-only execution, measuring the incremental contribution proposed as novel.

Both contrasts are within the same system, model, placement, serving mode, and workload. Secondary contrasts attribute effects to intermediate scheduler features, test whether normalized effects generalize across systems, and measure how platform tuning changes practical performance within each system.

## Metrics

### Correctness and reliability

- causal-verifier and commit violations;
- schema-valid and semantic-valid proposal rates;
- invariant-compliant committed-step rate;
- repair, policy-completion, fallback, and rejection rates;
- model autonomy and fully autonomous activation rates;
- divergence from the sequential or replay reference.

### Useful performance

- end-to-end completion time;
- useful agent steps per second;
- speedup over the matched sequential baseline;
- incremental full-scheduler effect relative to the matched causal-only baseline;
- GPU-hours and energy per useful agent step when observable;
- p50, p95, and p99 activation and tick latency;
- queue, inference, validation, scheduling, and commit time;
- prompt and generated tokens per second;
- strong and weak scaling where controlled.

A useful agent step is a committed activation satisfying its contracts. Useful throughput is always reported with autonomy, fallback, and correctness metrics.

### Model autonomy

A behavior atom is one normalized message, environment action, or state mutation. Let \(C\) be all committed behavior atoms and \(R\) be those retained unchanged in type, target, and normalized value from the original model proposal:

> **Model autonomy rate:** \(|R| / |C|\).

An empty \(C\) produces an unavailable rate plus an explicit zero count. Every committed atom has exactly one origin: model, repair, policy completion, or fallback. Proposal validity and rejected extra behavior are reported separately.

Current implementation coverage is narrower: `autonomy_rate` aggregates retained messages and environment actions, does not yet assign per-atom provenance to state mutations, and reports an empty committed set as `1.0`. Until the implementation reaches the target definition, artifacts and results label this value **message/action autonomy** and do not substitute it for the full behavior-atom metric.

### Platform telemetry

Use one provider-neutral schema populated by:

- ROCm and available `rocm-smi` or LUMI energy metrics;
- CUDA and available `nvidia-smi` or Roihu scheduler accounting;
- serving-runtime request and KV-cache metrics;
- application execution receipts.

Record GPU utilization, HBM use, KV-cache use, preemption, host utilization, queueing, and energy when observable. Missing telemetry is explicit rather than imputed.

## Statistical Design

- Freeze workloads, primary contrasts, and configuration-selection procedures before primary collection.
- Use a documented warm-up and a minimum repetition count per workload.
- Preserve raw per-run observations; do not report only aggregates.
- Report effect sizes and uncertainty intervals for normalized within-system contrasts.
- Treat system, model, placement, serving mode, workload family, and scale as explicit factors.
- Separate exploratory tuning data from confirmatory results.
- Before confirmatory scheduler experiments, preregister the minimum practically meaningful full-versus-causal-only effect, required workload coverage, and uncertainty criterion used by the paper contribution decision gate.
- Do not attribute absolute cross-system differences to GPU vendor alone.
- Report failed, interrupted, and invalid runs with prespecified exclusion rules.

## Hypotheses

### H1: Causal concurrency improves completion time

Causal scheduling reduces completion time relative to sequential FIFO for workloads with independent branches without increasing semantic, causal-verifier, or contract violations.

### H2: Naive concurrency can change observable behavior

Naive concurrent application produces stale reads, conflicting environment actions, or observation divergence for workloads with state dependencies, whereas causal scheduling prevents those violations.

### H3: Provider throughput does not predict useful throughput

Raw request or token throughput is an insufficient predictor of useful agent steps when schema failures, semantic failures, repair, policy completion, and fallback are included.

### H4: Workload shape changes the best policy

No batching or concurrency policy is optimal across dependency depth, fan-out, prefix sharing, conflict ratio, and output-length distributions.

### H5: Simulation specifications are portable, performance is not

The same workload, contracts, and observational semantics execute on LUMI and Roihu, but the best placement and serving configuration vary with platform capabilities and workload characteristics.

### H6: Capability awareness contributes beyond causal readiness

The full scheduler improves useful throughput relative to causal-only scheduling through capability-constrained batching, queue awareness, backpressure, or reusable-prefix grouping without adding correctness violations.

### H7: Scheduler effects generalize across accelerator ecosystems

The full-versus-causal-only effect is observable on both LUMI and Roihu, although its magnitude and the responsible features may differ.

## Required Outputs

- versioned workload definitions and expected invariants;
- separate ROCm/x86 and CUDA/ARM platform manifests;
- raw immutable artifacts and execution receipts;
- aggregation and plotting scripts;
- machine-readable result tables;
- documented commands for each paper table and figure;
- common-denominator and tuned results clearly labeled;
- sequential, causal-only, intermediate-feature, and full-scheduler ablation tables;
- the preregistered scheduler contribution gate and its outcome;
- recorded exclusions, failures, and unavailable metrics.

## Validity Boundaries

- LUMI and Roihu are delivered systems, not controlled vendor representatives.
- One MI250X GCD and one GH200 GPU are not equivalent hardware units.
- Shared managed endpoints demonstrate portability, not controlled performance.
- Fresh model generations are not expected to be textually identical.
- Toy scenarios test runtime properties, not real-world emergency or supply-chain validity.
- Unsupported or unstable platform features are reported and never silently replaced.
