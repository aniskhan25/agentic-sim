# B1 (Common-Denominator) Frozen Configuration

This closes the placeholder `docs/hpc_data_collection_procedures.md` explicitly left open ("no actual configuration values are selected or frozen for either system"). Everything below is a **decision made and verified live** on both LUMI and Roihu (2026-07-29), not a value invented from documentation — each item states exactly how it was confirmed. This covers B1 only; B2 (platform-tuned) configuration values remain open, since B2's own selection procedure requires running the actual sweep, which is separate primary-collection-adjacent work.

## Model

**`Qwen/Qwen2.5-7B-Instruct`, pinned to commit `a09a35458c702b33eeacc393d103063234e8bc28`.**

- Confirmed via the public Hugging Face API: `gated: false`, sharded BF16-native safetensors, 7B-class — satisfies `evaluation_plan.md`'s "at least one identical 7B/8B-class model that fits on one logical device" and B1's "identical model revision and tokenizer."
- Chosen over a gated alternative (e.g. Llama-3.1-8B-Instruct) specifically because no HF token/auth setup exists on either cluster — setting one up was out of scope for this prerequisite step.
- Downloaded to `/scratch/project_2014553/anisrahm/models/qwen2.5-7b-instruct` (Roihu) and `/scratch/project_462000131/anisrahm/models/qwen2.5-7b-instruct` (LUMI), both pinned to the exact revision above (~15 GB each, confirmed).
- **Confirmed to actually load** on both systems via a real `vllm serve` health check reaching `/v1/models` and returning this exact model path as `root` — not a claim of theoretical fit. LUMI: ~105s to healthy (1 MI250X GCD). Roihu: ~85s to healthy (1 GH200).

## Precision

`--dtype auto`, resolving to BF16 (the model's native weight dtype) on both systems — per B1's "BF16 as the primary common precision."

## Serving-runtime version (real divergence, explicitly paired)

No exact vLLM version match exists between the two systems' available deployments:

| System | Container | vLLM version |
|---|---|---|
| Roihu | `python-vllm/0.19.1` (CSC TYKKY module — only `0.18.0`/`0.19.1` available, nothing newer) | `0.19.1` |
| LUMI | `lumi-multitorch-u24r70f21m50t210-20260415_130625` (an older dated build, not `-latest`, which is `0.20.1`) | `0.19.0` |

**B1 uses this pairing** (`0.19.0` ROCm / `0.19.1` CUDA — one patch version apart) rather than either system's newest available build, invoking B1's own explicit escape clause: "the same serving-runtime revision **or explicitly paired compatible revisions**." No closer pairing exists in LUMI's container history (checked every dated `lumi-multitorch-*` build on disk: `0.11.0`, `0.12.0`, `0.14.0`, `0.15.1` ×2, `0.19.0`, `0.20.1` — `0.19.0` is the closest). B2 mode is explicitly permitted to use each system's independently best version instead (LUMI `0.20.1` / Roihu `0.19.1`), per B2's "tune ... serving-runtime revision independently" — record that as one of B2's expected divergences from B1 when B2 work begins.

## Feature-parity intersection

Per `docs/hpc_data_collection_procedures.md`'s frozen procedure ("intersect each system's stable serving features ... disable, on both systems, any feature not in that intersection"). Determined by actually running `vllm serve --help=all` on a real GPU node on each system for the paired B1 builds above — not from vLLM's changelog or assumed compatibility. (Plain `vllm serve --help`/`--version` cannot be run from either login node at all: vLLM performs device detection while building its argument parser, and fails outright with no GPU present — confirmed on both systems.)

| Feature | Roihu (`0.19.1`, CUDA) | LUMI (`0.19.0`, ROCm) | In B1 intersection? |
|---|---|---|---|
| `--enable-prefix-caching` | present | present | **Yes** — enable on both |
| `--structured-outputs-config` | present | present | **Yes** — enable on both |
| `--kv-cache-dtype` | `auto,bfloat16,float16,fp8,fp8_ds_mla,fp8_e4m3,fp8_e5m2,fp8_inc`; docstring: "CUDA 11.8+ supports fp8 (=fp8_e4m3) and fp8_e5m2" | same flag choices exposed; docstring: "ROCm (AMD GPU) supports fp8 (=fp8_e4m3)" | **`fp8_e4m3` only** — `fp8_e5m2` is CUDA-only per vLLM's own docstring, so it is *not* in the intersection and stays disabled for B1; `fp8_e4m3` (or `auto`/BF16) is the shared choice |

Both systems' CLI flag surfaces were essentially identical (expected: adjacent patch versions). The one real, documented divergence is the fp8 sub-variant, handled above per the frozen procedure's own rule ("disable ... any feature not in that intersection").

## Batching and context configuration

Confirmed workable on both systems (both real `vllm serve` invocations above used these exact flags and started successfully): `--max-model-len 8192`, `--max-num-batched-tokens 16384`, `--max-num-seqs 64`. These were the "starting point" values already sketched in both `docs/lumi_deployment_manifest.md` and `docs/roihu_deployment_manifest.md`'s common-denominator tables — now promoted from starting point to frozen, since they're confirmed to actually load the real B1 model on both systems' real hardware.

## Decoding parameters

`temperature=0.2`, `top_p=0.95`, `max_completion_tokens=256` — reusing `OpenAICompatibleExecutionBackend`'s existing constructor defaults (`src/agentic_sim/execution/openai_compatible_backend.py`) rather than inventing new values, since nothing in `evaluation_plan.md` requires different ones and this keeps the frozen configuration traceable to real, already-tested code.

## Operational finding: port collision on shared nodes

A real integrity risk, discovered live and worth recording for whoever runs the actual primary-collection jobs: **a fixed port (e.g. `8000`) is not private to one job on these shared partitions.** The first Roihu confirmation attempt used port `8000` and its health check returned a *different, unrelated user's* concurrently running vLLM server (`mistralai/Mistral-Small-4-119B-2603`) — a false positive that would have silently contaminated results had the response not been checked. Fixed by deriving a unique port per job (`PORT=$((20000 + (SLURM_JOB_ID % 20000)))`) and verifying the `/v1/models` response's `root` field matches the intended model path on every run, not just checking that *a* server responded. **Any future job script for the primary study must do the same** — a fixed port number must never be assumed safe on either system's shared GPU partitions.

## What remains open

- B2 (platform-tuned) configuration values — require running the actual sweep/selection procedure, not decided here.
- The primary 10-repetition data collection itself, for any workload, placement level, or scheduler policy.
- Whether the frozen `0.19.0`/`0.19.1` pairing remains available long-term — LUMI's dated container builds are maintained by another project group (`appl_laifs`), not this one, and could be removed; re-verify before primary collection begins.
