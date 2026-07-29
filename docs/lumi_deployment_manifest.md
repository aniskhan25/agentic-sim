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

**vLLM on ROCm.** Two deployment paths are now known, not one: `docs/amd_vllm_lumi_tuning.md`'s manually-built-from-source path (still the reference for tuning knowledge, sweep space, and attention-backend guidance below), and a ready-made container confirmed live during item 19's first smoke test: `/appl/local/laifs/containers/lumi-multitorch-latest.sif`, maintained under the shared `appl_laifs` project group (discovered via a working example, https://github.com/aniskhan25/LUMI-AI-Guide/blob/main/1-quickstart/run_vit.sh), confirmed to already include **vLLM 0.20.1** and **PyTorch 2.10.0+rocm7.0** — no build step needed. Loading it requires `module use /appl/local/laifs/modules && module load lumi-aif-singularity-bindings` (LUMI's bind-mount setup, analogous to Roihu's `csc-common-bind`) and referencing the container at `/appl/local/laifs/containers/lumi-multitorch-latest.sif`; `singularity` is the tool (not `apptainer`, which is absent on LUMI's login nodes), and — a real, non-obvious gotcha confirmed by a failed first attempt — environment variables only reach the container's process if prefixed `SINGULARITYENV_` (e.g. `SINGULARITYENV_PYTHONPATH=...`); a plain `PYTHONPATH=... singularity exec ...` is silently dropped. This container is not owned or version-pinned by this project — its path is a live filesystem location maintained by another group, not a versioned artifact this repo controls, so a real B1/B2 study should still record its exact resolved `.sif` filename (it's a symlink to a dated build) via `PlatformManifest.for_lumi(...)`'s `serving_runtime_version`, same as any other deployment-time fact. Model choice per `evaluation_plan.md`'s Placement levels requirement ("at least one identical 7B/8B-class model that fits on one logical device"): an 8B-class dense model is the baseline choice for the single-GCD placement level; a 70B-class model is the stretch case for the full-node placement level, per `amd_vllm_lumi_tuning.md`'s own suggested benchmark matrix. The smoke test itself used a much smaller stand-in (`TinyLlama-1.1B-Chat-v1.0`), not this baseline — see `docs/research_roadmap.md` item 19.

## Common-denominator configuration

Per `evaluation_plan.md` B1 ("largest stable shared feature set"), every item mapped to a concrete value. **All rows below are now frozen, not placeholders** — see `docs/b1_frozen_configuration.md` for the full record and how each value was actually confirmed live on both systems:

| B1 requirement | Concrete value for this manifest |
|---|---|
| identical model revision and tokenizer | `Qwen/Qwen2.5-7B-Instruct` @ `a09a35458c702b33eeacc393d103063234e8bc28` — ungated, confirmed to load on both systems via a real `vllm serve` health check |
| BF16 as primary common precision | `--dtype auto` resolving to BF16 (the model's native weight dtype on ROCm) |
| identical prompt corpus and output-token limit | the versioned synthetic-kernel/storm/supply-chain workload definitions already frozen by items 9/15, with `--max-model-len 8192` — confirmed workable on both systems |
| same serving-runtime revision or paired compatible revisions | **paired, not identical**: LUMI's `lumi-multitorch-u24r70f21m50t210-20260415_130625` container (vLLM `0.19.0`) paired with Roihu's `python-vllm/0.19.1` — the closest pairing available in LUMI's container history; see `docs/b1_frozen_configuration.md` for why no exact match exists |
| identical decoding parameters | `temperature=0.2`, `top_p=0.95`, `max_completion_tokens=256` — reusing `OpenAICompatibleExecutionBackend`'s existing defaults |
| matched batching, structured-output, and prefix-cache features | `--max-num-batched-tokens 16384`, `--max-num-seqs 64` on both systems; `--enable-prefix-caching` and `--structured-outputs-config` enabled on both (confirmed present in both systems' `vllm serve --help=all` output); `--kv-cache-dtype fp8_e4m3` (not bare `fp8` — ROCm doesn't support the `fp8_e5m2` variant CUDA does, so the intersection is narrower than either system's full support) |
| fixed warm-up, duration, and repetition rule | frozen in `docs/hpc_data_collection_procedures.md` (item 18): 20 discarded warm-up requests (count-based, not time-based, so the rule stays identical across systems of different raw speed), 10 repetitions per workload/model/placement-level/mode combination, 30-minute per-configuration wall-clock budget — reusing `scripts/run_lumi.sh`'s existing `AITTA_WARMUP`-style warm-up-then-wait pattern, generalized to poll the self-hosted server's health endpoint instead of Aitta |
| exclusive model-server allocations | one `sbatch`/`srun` job per experiment — **with a real caveat discovered live**: a fixed port is not private to one job on these shared partitions (confirmed: a health check on a fixed port once returned a different, unrelated user's concurrent server). Every job must use a unique port (e.g. derived from `$SLURM_JOB_ID`) and verify the responding server's model path matches, not just that a server responded — see `docs/b1_frozen_configuration.md`'s Operational finding |
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
- **Backend wiring**: `execution/self_hosted_backend.py::SelfHostedExecutionBackend` (item 19) — an OpenAI-compatible client pointed at the local server, sharing all request/response/repair/role-policy/receipt logic with `AittaExecutionBackend` via the extracted `OpenAICompatibleExecutionBackend` base class, but without Aitta's required-API-key assumption (`SELF_HOSTED_API_KEY` is optional, matching most self-hosted vLLM deployments running with no `--api-key`) or its hardcoded `supports_prefix_caching=False` (configurable via `enable_prefix_caching`, since a real deployment knows its own `vllm serve` flags). Selectable via `--backend self_hosted`/`"execution": {"backend": "self_hosted"}` (see `configs/demo_self_hosted.json`), with a `check-self-hosted --wait` health-check command mirroring `check-aitta --wait`. **This exists in code and is tested (`tests/test_self_hosted_backend.py`) but has never run against a real server** — no live LUMI/Roihu vLLM deployment exists yet to point it at.

## Explicit gaps

- `SelfHostedExecutionBackend` has now run against a real vLLM server on real LUMI hardware (item 19's first smoke test, and again for the B1 model-load confirmation above) — but only ad hoc `srun` invocations so far, not the actual 10-repetition primary study.
- `scripts/run_lumi.sh`/`run_lumi_array.sh` today only request LUMI's CPU-only `small` partition and only call Aitta — they do not request a GPU partition or launch a server. A proper GPU-enabled job script (mirroring the ad hoc job scripts used for the smoke test and B1 confirmation) remains future work.
- vLLM version is now pinned for B1 (see the table above and `docs/b1_frozen_configuration.md`); the ROCm/driver version itself is still not asserted anywhere in this document — recorded at actual deployment time via `PlatformManifest.for_lumi(...)`'s required `driver_version` argument, per `evaluation_plan.md`'s "refreshed when experiments begin" wording.
- The Roihu (NVIDIA/CUDA) half of item 17 now exists (`docs/roihu_deployment_manifest.md`).
