# Roihu Self-Hosted Deployment Manifest

This is the Roihu half of `docs/research_roadmap.md` item 17: "Create self-hosted deployment manifests for LUMI and Roihu." Its shape follows the same structure as `docs/lumi_deployment_manifest.md`, ADR 0005, and `docs/evaluation_plan.md`'s Evaluation Platforms table, B1 (common-denominator mode), B2 (platform-tuned mode), and Placement levels sections.

**Verification status, stated plainly**: unlike the LUMI manifest (drafted from public documentation only, since no working LUMI credentials existed at the time), most of this document's hardware and software-stack facts were confirmed via live, read-only SSH access to `roihu-gpu.csc.fi` on 2026-07-29 — `sinfo`/`scontrol show partition` for SLURM partitions, `lscpu`/`uname -m` for host architecture, and `module load python-vllm/0.19.1` plus an `apptainer exec` version probe for the serving-stack versions below. The one fact this document does *not* assert is the NVIDIA driver version itself, since `nvidia-smi` is not present on the login node (no GPU device there) — that remains deployment-time-only, exactly like LUMI's ROCm driver version.

## Hardware

- 4× NVIDIA GH200 Grace Hopper superchips per node, 96 GiB HBM3 each — matches `evaluation_plan.md`'s Evaluation Platforms table exactly.
- 72 ARM (Neoverse-V2) cores per GH200 module — confirmed via `sinfo`/`scontrol show partition` TRES accounting (`cpu=36288` across 126 nodes on `gpumedium`/`gpularge` ≈ 288 cores/node = 4 × 72).
- Host: ARM Grace (`aarch64`), InfiniBand NDR, aggregate 4×200 Gb/s (800 Gb/s) per node per the existing `lumi-apptainer-bench` benchmarking notes already present in this project's own Roihu workspace (see Serving stack, below).
- SLURM GPU partitions, confirmed live (not assumed from public docs):

  | Partition | Nodes | Time limit | GPUs/node |
  |---|---|---|---|
  | `gputest` | 4 | 00:15:00 | 4× GH200 |
  | `gpuinteractive` | 2 | 12:00:00 | 4× GH200 |
  | `gpumedium` | 126 | 1-12:00:00 | 4× GH200 (one node reports 3, likely a degraded node) |
  | `gpularge` | 126 | 1-12:00:00 | 4× GH200 (same node pool as `gpumedium`) |

- Source: [Roihu system documentation](https://docs.csc.fi/computing/systems-roihu/), cross-checked live.

**Not fixed here**: the exact NVIDIA driver version. Matching `evaluation_plan.md`'s own wording ("Hardware details are refreshed when experiments begin and recorded in every platform manifest"), this document does not assert a driver version as if permanently true — `PlatformManifest.for_roihu(...)` requires `driver_version` as a caller-supplied argument with no default, to be filled in from `nvidia-smi` on an actual GPU compute node (not the login node) at deployment time.

## Serving stack

**vLLM via CSC's TYKKY container module** — a materially different delivery mechanism than LUMI's manually-built-and-tuned stack. Confirmed live: `module load python-vllm/0.19.1` (default; `0.18.0` also available) sets `$SIF` (an Apptainer image path) and `APPTAINER_NV=true`; the module is documented at [docs.csc.fi/apps/vllm](https://docs.csc.fi/apps/vllm/). Inside the `0.19.1` container: Python `3.12.12`, PyTorch `2.10.0+cu129` (CUDA 12.9 toolkit), vLLM `0.19.1` — all confirmed via a direct version probe, not assumed.

**Execution pattern**: `apptainer exec --bind="$(csc-common-bind)" "$SIF" <command>`, where `csc-common-bind` (a standalone binary at `/appl/soft/manual/general/aarch64/csc-tools/bin/csc-common-bind`, no module needed) computes the correct bind-mount paths for CSC's storage layout. This is not invented for this manifest — this project's own existing Roihu workspace (`/scratch/project_2014553/anisrahm/lumi-apptainer-bench`) already uses exactly this pattern (`srun ... apptainer exec --bind="$CSC_BIND" "$SIF" ...`) for JAX allreduce/DDP benchmarking, predating this session. That work also confirms GH200 delivers roughly 4-5x the single-GPU GEMM throughput of LUMI's MI250X in bfloat16 (530.9 vs. 120.6 TFLOPS on a 4096×4096 GEMM) — a useful sanity reference for interpreting future serving-throughput numbers, not a substitute for this manifest's own inference-serving measurements.

Model choice: the same pinned 8B-class dense model as `docs/lumi_deployment_manifest.md`'s baseline (identical revision required by B1), with the same 70B-class stretch case for the full-node placement level.

## Common-denominator configuration

Per `evaluation_plan.md` B1, every item mapped to a concrete value or an explicit deployment-time placeholder:

| B1 requirement | Concrete value for this manifest |
|---|---|
| identical model revision and tokenizer | the same pinned 8B-class checkpoint as `docs/lumi_deployment_manifest.md` (one revision, shared across both platform manifests) |
| BF16 as primary common precision | `--dtype auto` resolving to BF16 (GH200's Hopper architecture natively supports BF16, same as the model's native weight dtype) |
| identical prompt corpus and output-token limit | the same versioned synthetic-kernel/storm/supply-chain workload definitions as LUMI, with the same fixed `--max-model-len` (a B1 requirement is that this value be identical across systems, not independently chosen) |
| same serving-runtime revision or paired compatible revisions | **open coordination item, not yet closed**: Roihu's vLLM is CSC-delivered at a fixed `0.19.1`/`0.18.0`; LUMI's is manually built per `docs/amd_vllm_lumi_tuning.md` with no version pinned yet. Whichever team runs the actual B1 collection must confirm LUMI's ROCm build can target the same `0.19.1` (or record the paired-compatible-revisions exception explicitly) before results are compared — not asserted as already resolved here. |
| identical decoding parameters | fixed temperature/top-p/max-tokens shared across both systems (same values as LUMI's manifest, pinned once the model is chosen) |
| matched batching, structured-output, and prefix-cache features | `--max-num-batched-tokens` and `--max-num-seqs` set to the same values as LUMI; structured-output/prefix-cache features disabled on whichever platform doesn't support them, per the feature-parity intersection procedure `docs/hpc_data_collection_procedures.md` freezes |
| fixed warm-up, duration, and repetition rule | the same frozen rule as LUMI: `docs/hpc_data_collection_procedures.md` (item 18) — 20 discarded warm-up requests, 10 repetitions per workload/model/placement-level/mode combination, 30-minute per-configuration wall-clock budget |
| exclusive model-server allocations | one `sbatch`/`srun` job per experiment, requesting an exclusive `--gres=gpu:gh200:N` allocation (SLURM's GPU generic-resource accounting prevents another job from sharing the same GPUs) |
| recorded compiler, driver, ROCm or CUDA, Python, framework, container, and serving-runtime versions | `PlatformManifest.for_roihu(...)`'s `driver_version`/`serving_runtime_version` fields, plus `framework_versions` for the PyTorch/CUDA-stack versions confirmed above — all supplied at deployment time, with today's confirmed container versions (Python 3.12.12, PyTorch 2.10.0+cu129, vLLM 0.19.1) as the current starting point |

Starting point for the actual `vllm serve` invocation (single-GPU placement):

```bash
module load python-vllm/0.19.1

srun --partition=gpuinteractive --account=project_2014553 \
  --gres=gpu:gh200:1 --cpus-per-task=72 --time=00:30:00 \
  apptainer exec --bind="$(/appl/soft/manual/general/aarch64/csc-tools/bin/csc-common-bind)" "$SIF" \
  vllm serve /path/to/model \
    --dtype auto \
    --gpu-memory-utilization 0.90 \
    --max-model-len 8192 \
    --max-num-batched-tokens 16384 \
    --max-num-seqs 64
```

## Platform-tuned configuration

Per `evaluation_plan.md` B2: retains the same model revision, workload, decoding semantics, and output limits as common-denominator mode, but independently tunes serving parameters. This is now the authoritative sweep space — it supersedes the provisional placeholder `docs/hpc_data_collection_procedures.md` (item 18) marked as pending this manifest:

- `--max-num-batched-tokens`: sweep `8192`/`16384`/`32768`/`65536` (identical sweep values to LUMI — vLLM's batching knob is version-consistent across ROCm/CUDA builds).
- `--max-num-seqs`: sweep `32`/`64`/`128`/`256`.
- `--gpu-memory-utilization`: sweep `0.85`/`0.90`/`0.95`.
- Parallelism: independent replicas per GH200 GPU (dense 8B/14B-class models) vs. `--tensor-parallel-size 2` or `4` (70B-class models) — **not** `TP=8` like LUMI's full-node sweep, since a Roihu node has 4 GH200s, not 8 GCDs.
- Attention backend: vLLM's default FlashAttention-family backend on Hopper vs. CUDA-graph capture on/off — benchmarked, not assumed transferable from LUMI's AMD-specific AITER guidance.
- KV-cache dtype: default vs. `fp8`, if the deployed vLLM/CUDA build and model support it.

Selection procedure: the full frozen rule (selection metric, disqualifying constraint, tie-breaking, freeze-timing commitment, divergence-recording requirement) lives in `docs/hpc_data_collection_procedures.md` (item 18) and is not repeated here — run the equivalent benchmark matrix (tokens/sec, completed agent-steps/sec, TTFT, inter-token latency, GPU utilization, KV-cache preemption count, failed/invalid structured-output rate) and apply that frozen rule to the results.

## Placement levels

Per `evaluation_plan.md`'s Placement levels section:

1. **Single logical device**: one GH200 GPU (`--gres=gpu:gh200:1`) — `PlatformManifest.for_roihu(..., placement_level="single_device")`, `accelerator_count=1`.
2. **Full node**: all 4 GH200 GPUs (`--gres=gpu:gh200:4`) — `PlatformManifest.for_roihu(..., placement_level="full_node")`, `accelerator_count=4`.

Multi-node inference remains a stretch experiment, per the roadmap's own scope (item 17/Phase 9 do not require it).

## Deployment procedure (specification, not yet implemented)

- **SLURM partition/allocation**: `gpuinteractive` for short interactive tuning runs (12h limit), `gpumedium`/`gpularge` for longer primary-collection runs (1d12h limit) — all confirmed live via `sinfo`, unlike LUMI's manifest which had to defer partition-name confirmation to deployment time. `--account=project_2014553` (this project's Roihu allocation, distinct from LUMI's `project_462000131` — CSC uses separate numbering conventions per system).
- **Server launch**: `module load python-vllm/<version>` (sets `$SIF`/`APPTAINER_NV`), then `apptainer exec --bind="$(csc-common-bind)" "$SIF" vllm serve ...` as a background step before the simulation's CLI invocation, with a health-check warm-up loop using the same `check-self-hosted --wait` pattern named in `docs/lumi_deployment_manifest.md`.
- **Backend wiring**: no new backend code is needed. `execution/self_hosted_backend.py::SelfHostedExecutionBackend` (item 19) is an OpenAI-compatible HTTP client — it has no host-architecture or accelerator-vendor assumptions, so the same class already used for LUMI works unmodified against a Roihu-hosted vLLM server. This is a direct payoff of extracting `OpenAICompatibleExecutionBackend` as a shared base rather than writing per-platform backends.
- **Storage**: `/scratch/project_2014553/anisrahm` already exists on Roihu (confirmed live, currently holding unrelated prior JAX/DDP benchmarking work under `lumi-apptainer-bench`) — a future `agentic-sim` checkout belongs alongside it, not under `$HOME`, mirroring `docs/lumi.md`'s "First-Time Setup" convention for LUMI. Unlike LUMI, Roihu's Python/vLLM stack is delivered entirely through the TYKKY container (`$SIF`) rather than a manually built venv — there is no equivalent `python3 -m venv` step for the serving stack itself; a checkout would only need its own lightweight venv for the `agentic-sim` CLI/orchestration code, which calls out to the containerized vLLM server over HTTP rather than importing it directly.

## Explicit gaps

- `SelfHostedExecutionBackend` has never been run against a real vLLM server on Roihu — no live deployment exists yet, same as LUMI.
- No `run_roihu.sh`/`run_roihu_array.sh` SLURM job script exists yet to launch `vllm serve` and orchestrate a run — future work, mirroring `scripts/run_lumi.sh`'s current CPU-only, Aitta-only state.
- The exact NVIDIA driver version is not asserted anywhere in this document — `nvidia-smi` is unavailable on the login node (no GPU device there); it must be recorded from an actual GPU compute node via `PlatformManifest.for_roihu(...)`'s required `driver_version` argument at deployment time.
- Whether LUMI's manually-built ROCm vLLM stack can be pinned to the same `0.19.1` release Roihu ships as a fixed CSC module is an open coordination item (see the common-denominator table's "same serving-runtime revision" row) — not resolved by this document.
