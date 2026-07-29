# LUMI Self-Hosted Deployment Manifest

This is the LUMI half of `docs/research_roadmap.md` item 17: "Create self-hosted deployment manifests for LUMI and Roihu." It is a **frozen specification to build and deploy against**, not a description of something already running. Its shape follows ADR 0005 and `docs/evaluation_plan.md`'s Evaluation Platforms table, B1 (common-denominator mode), B2 (platform-tuned mode), and Placement levels sections — quoted and mapped below, not re-derived.

**What already exists today, reused here rather than duplicated:** `scripts/run_lumi.sh`/`run_lumi_array.sh` and `docs/lumi.md` run the simulation's CPU-only orchestration on LUMI's `small` (non-GPU) partition, calling out to **Aitta**, a managed OpenAI-compatible endpoint. Per `evaluation_plan.md`'s Required Substrates ("shared or managed endpoints are excluded from primary performance conclusions") and ADR 0005 (a run is primary evidence only when its `PlatformManifest.manifest_mode` is populated), **Aitta-backed LUMI runs remain an optional portability observation, never primary performance evidence** — this manifest describes the separate, not-yet-built self-hosted path that would produce primary evidence. `docs/amd_vllm_lumi_tuning.md` already collects the relevant vLLM/ROCm tuning knowledge in anticipation of this exact item; this document points to it rather than repeating it, and turns its example commands into concrete common-denominator/platform-tuned configurations.

## Hardware

From `evaluation_plan.md`'s Evaluation Platforms table and `docs/amd_vllm_lumi_tuning.md`:

- 4× AMD MI250X modules per LUMI-G node, each module exposing 2 Graphics Compute Dies (GCDs) — a full node presents as **8 visible GPU devices**.
- 64 GB HBM per GCD.
- Host: AMD EPYC (x86_64), ROCm, Slingshot interconnect.
- LUMI-G exposes only 56 job cores per node (not all physical cores are schedulable).
- Source: [LUMI-G hardware documentation](https://docs.lumi-supercomputer.eu/hardware/lumig/).

**Not fixed here**: exact ROCm/driver/firmware versions. `evaluation_plan.md`'s own wording is adopted directly — "Hardware details are refreshed when experiments begin and recorded in every platform manifest" — so this document does not assert a ROCm version as if permanently true; `PlatformManifest.for_lumi(...)` requires `driver_version` as a caller-supplied argument with no default, populated at actual deployment time.

## Serving stack

**vLLM on ROCm** — the only serving stack this repo currently has tuning knowledge for (`docs/amd_vllm_lumi_tuning.md`), reused here rather than re-derived. Model choice per `evaluation_plan.md`'s Placement levels requirement ("at least one identical 7B/8B-class model that fits on one logical device"): an 8B-class dense model is the baseline choice for the single-GCD placement level; a 70B-class model is the stretch case for the full-node placement level, per `amd_vllm_lumi_tuning.md`'s own suggested benchmark matrix.

## Common-denominator configuration

Per `evaluation_plan.md` B1 ("largest stable shared feature set"), every item mapped to a concrete value or an explicit deployment-time placeholder:

| B1 requirement | Concrete value for this manifest |
|---|---|
| identical model revision and tokenizer | one pinned 8B-class model checkpoint (exact revision recorded at deployment time — not invented here) |
| BF16 as primary common precision | `--dtype auto` resolving to BF16 (the model's native weight dtype on ROCm) |
| identical prompt corpus and output-token limit | the versioned synthetic-kernel/storm/supply-chain workload definitions already frozen by items 9/15, with a fixed `--max-model-len` sized to the actual agent-context requirement, per `amd_vllm_lumi_tuning.md`'s "do not leave this much larger than the workload requires" |
| same serving-runtime revision or paired compatible revisions | one pinned vLLM release, identical on both LUMI and Roihu where the same release supports both ROCm and CUDA; recorded in `PlatformManifest.serving_runtime_version` |
| identical decoding parameters | fixed temperature/top-p/max-tokens shared across both systems (values pinned once the model is chosen, not asserted here) |
| matched batching, structured-output, and prefix-cache features | `--max-num-batched-tokens` and `--max-num-seqs` set to identical values on both systems; structured-output/prefix-cache features disabled on whichever platform doesn't support them, per B1's "disabling unavailable features on both platforms" |
| fixed warm-up, duration, and repetition rule | frozen in `docs/hpc_data_collection_procedures.md` (item 18): 20 discarded warm-up requests (count-based, not time-based, so the rule stays identical across systems of different raw speed), 10 repetitions per workload/model/placement-level/mode combination, 30-minute per-configuration wall-clock budget — reusing `scripts/run_lumi.sh`'s existing `AITTA_WARMUP`-style warm-up-then-wait pattern, generalized to poll the self-hosted server's health endpoint instead of Aitta |
| exclusive model-server allocations | one `sbatch` job per experiment, exclusive node allocation (no co-scheduled jobs sharing GPUs) |
| recorded compiler, driver, ROCm, Python, framework, container, and serving-runtime versions | `PlatformManifest.for_lumi(...)`'s `driver_version`/`serving_runtime_version` fields, plus `framework_versions` (inherited from the base `PlatformManifest`) for PyTorch/ROCm-stack versions — all supplied at deployment time |

Starting point for the actual `vllm serve` invocation (single-GCD placement, adapted from `amd_vllm_lumi_tuning.md`'s smaller-model example):

```bash
export HIP_FORCE_DEV_KERNARG=1
export TORCH_BLAS_PREFER_HIPBLASLT=1
unset HIP_VISIBLE_DEVICES

CUDA_VISIBLE_DEVICES=0 vllm serve /path/to/model \
  --dtype auto \
  --gpu-memory-utilization 0.90 \
  --max-model-len 8192 \
  --max-num-batched-tokens 16384 \
  --max-num-seqs 64
```

## Platform-tuned configuration

Per `evaluation_plan.md` B2 ("best stable delivered performance available on each system"): retains the same model revision, workload, decoding semantics, and output limits as common-denominator mode, but independently tunes serving parameters using `amd_vllm_lumi_tuning.md`'s documented sweep space:

- `--max-num-batched-tokens`: sweep `8192`/`16384`/`32768`/`65536`.
- `--max-num-seqs`: sweep `32`/`64`/`128`/`256`.
- `--gpu-memory-utilization`: sweep `0.85`/`0.90`/`0.95`.
- Parallelism: independent replicas per GCD (dense 8B/14B-class models) vs. `--tensor-parallel-size 4` or `8` (70B-class models), per `amd_vllm_lumi_tuning.md`'s Parallelism Strategy section.
- Attention backend: baseline vs. `VLLM_ROCM_USE_AITER=1` vs. prefill/decode split — benchmarked, not assumed, since AMD's AITER guidance targets MI300/MI350-class hardware and LUMI is MI250X.
- KV-cache dtype: default vs. `fp8`, if the deployed vLLM/ROCm build and model support it.

Selection procedure: the full frozen rule (selection metric, disqualifying constraint, tie-breaking, freeze-timing commitment, divergence-recording requirement) lives in `docs/hpc_data_collection_procedures.md` (item 18) and is not repeated here — run the suggested benchmark matrix from `amd_vllm_lumi_tuning.md` (tokens/sec, completed agent-steps/sec, TTFT, inter-token latency, GPU utilization, KV-cache preemption count, failed/invalid structured-output rate) and apply that frozen rule to the results.

## Placement levels

Per `evaluation_plan.md`'s Placement levels section:

1. **Single logical device**: one MI250X GCD (`CUDA_VISIBLE_DEVICES=0`, i.e. one of the 8 visible devices per node) — `PlatformManifest.for_lumi(..., placement_level="single_device")`, `accelerator_count=1`.
2. **Full node**: all 8 MI250X GCDs — `PlatformManifest.for_lumi(..., placement_level="full_node")`, `accelerator_count=8`.

Multi-node inference remains a stretch experiment, per the roadmap's own scope (item 17/Phase 9 do not require it).

## Deployment procedure (specification, not yet implemented)

Extends `scripts/run_lumi.sh`'s existing pattern (env sourcing, module loading, `RUN_DIR`/`ARTIFACT_ROOT` conventions) with what self-hosted serving would add:

- **SLURM partition**: a GPU partition (LUMI's GPU partitions are typically named `standard-g`/`small-g`/`dev-g` — confirm the exact current name against LUMI's own documentation at deployment time, not assumed here) instead of `run_lumi.sh`'s current `--partition=small`, plus a `--gpus-per-node`/`--gres` request the current script does not make.
- **Server launch**: `vllm serve ...` (per the configurations above) started as a background step before the simulation's CLI invocation, with a health-check warm-up loop generalizing `run_lumi.sh`'s existing `AITTA_WARMUP`/`check-aitta --wait` pattern to poll the self-hosted server instead.
- **Backend wiring**: the simulation would need a self-hosted `ExecutionBackend` implementation (an OpenAI-compatible client pointed at the local vLLM server, structurally similar to `AittaExecutionBackend` but without Aitta-specific auth/base-URL assumptions) — **this does not exist in code today**; this manifest is what it would need to be deployed against, not a description of something already working.

## Explicit gaps

- No self-hosted `ExecutionBackend` implementation exists in code today — only `mock`/`rule`/`synthetic`/`aitta`. Building it is separate, larger, not-yet-scoped work.
- `scripts/run_lumi.sh`/`run_lumi_array.sh` today only request LUMI's CPU-only `small` partition and only call Aitta — they do not request a GPU partition or launch a server.
- Exact ROCm/driver/vLLM version numbers are not asserted anywhere in this document — they are recorded at actual deployment time via `PlatformManifest.for_lumi(...)`'s required `driver_version`/`serving_runtime_version` arguments, per `evaluation_plan.md`'s "refreshed when experiments begin" wording.
- The Roihu (NVIDIA/CUDA) half of item 17 does not exist yet — this document covers LUMI only.
