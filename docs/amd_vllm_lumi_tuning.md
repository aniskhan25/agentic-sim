# AMD/vLLM Throughput Knobs for LUMI

This note collects throughput knobs to evaluate when adding a real vLLM backend to the simulation runtime. The current repo still uses mock/rule execution; these settings are for the next model-serving integration.

## LUMI Hardware Constraints

LUMI-G nodes have 4 AMD MI250X modules. Each module exposes 2 Graphics Compute Dies, so Slurm and HIP see a full node as 8 GPUs. Each GCD has its own 64 GB HBM slice.

This matters for vLLM:

- Treat a full LUMI-G node as 8 visible GPU devices.
- Avoid assuming MI300X guidance transfers directly to MI250X.
- Keep model placement inside one node first; multi-node serving adds Slingshot/RCCL overhead and should only be used after single-node saturation is understood.
- Pay attention to CPU/GPU binding. LUMI-G exposes only 56 job cores, and GPU numbering is not the same as NUMA numbering.

## Highest-Value vLLM Knobs

Start with these before trying lower-level ROCm tuning.

### Request Shape

Fix a representative prompt/output distribution before benchmarking.

- input sequence length: agent context + messages + environment snapshot
- output sequence length: expected structured JSON result
- request concurrency: number of simultaneous active agents
- total prompts: enough to amortize startup and graph capture

For this simulation, throughput should be measured as useful completed agent steps per second and tokens per second.

### Batching and KV Cache

The main vLLM throughput/latency tradeoff knobs are:

- `--max-num-batched-tokens`: increase for throughput; sweep around `8192`, `16384`, `32768`, `65536`.
- `--max-num-seqs`: increase until GPU utilization improves or KV-cache preemption appears.
- `--gpu-memory-utilization`: increase toward `0.90`-`0.95` if there is headroom; reduce if startup or runtime OOMs.
- `--max-model-len`: set to the actual maximum agent context needed. Do not leave this much larger than the workload requires.
- `--kv-cache-dtype fp8`: candidate if the vLLM/ROCm build and model support it; it can increase concurrency by reducing KV-cache memory.

Watch logs for KV-cache preemption. If preemption appears, reduce `--max-num-seqs` or `--max-num-batched-tokens`, increase `--gpu-memory-utilization`, shorten context, or use more tensor parallelism.

### Chunked Prefill

vLLM V1 enables chunked prefill when possible. Tune it primarily through `--max-num-batched-tokens`.

- Lower values favor inter-token latency.
- Higher values favor throughput and time-to-first-token for prompt-heavy batches.
- For offline/batch agent simulation, start at `16384` or `32768`, then sweep upward.

### Parallelism Strategy

Pick the strategy from the model size and the goal:

- Model fits one GCD: run multiple independent vLLM instances or use vLLM data parallelism for throughput.
- Model needs multiple GCDs: use tensor parallelism inside one node first.
- Model is too large for one node: add pipeline parallelism across nodes only after single-node TP is understood.
- Dense models: independent replicas behind a lightweight client-side router can avoid DP coordination overhead.
- MoE models: evaluate expert parallelism only if the chosen model actually has MoE layers.

On LUMI, useful first sweeps:

- 8B/14B model: `TP=1`, independent replicas per GCD or DP.
- 70B-class model: test `TP=4` and `TP=8`.
- Long-context workloads: test `TP=8` if KV cache, not weights, is the limiter.

## ROCm/AMD Knobs to Benchmark

These should be treated as benchmark candidates on LUMI MI250X, not guaranteed defaults.

### Environment Variables

- `HIP_FORCE_DEV_KERNARG=1`: AMD recommends this for vLLM kernel launch performance on newer Instinct guidance.
- `TORCH_BLAS_PREFER_HIPBLASLT=1`: candidate for GEMM-heavy linear layers.
- `NCCL_MIN_NCHANNELS=112`: candidate only for multi-GPU TP/PP runs. Benchmark on MI250X before keeping it.
- `VLLM_ALL2ALL_BACKEND=allgather_reducescatter`: AMD recommends this for ROCm data parallelism.

For vLLM on ROCm, AMD notes that vLLM reads `CUDA_VISIBLE_DEVICES`. Keep `HIP_VISIBLE_DEVICES` unset to avoid conflicts. On LUMI, be careful if also using `ROCR_VISIBLE_DEVICES` wrappers for per-rank GPU binding.

### Attention Backend / AITER

AMD recommends `VLLM_ROCM_USE_AITER=1` for many MI300/MI350-class workloads. LUMI is MI250X, so this should be tested, not assumed.

Candidate sweep:

- baseline: no AITER env vars
- `VLLM_ROCM_USE_AITER=1`
- for short-input cases: `VLLM_V1_USE_PREFILL_DECODE_ATTENTION=1`

Check vLLM startup logs to confirm which attention backend was selected.

### Quantization

Use quantization to increase batch/concurrency, not only to fit the model.

Candidates:

- pre-quantized AWQ/GPTQ models if supported for the chosen architecture
- `VLLM_USE_TRITON_AWQ=1` for AWQ on ROCm
- `--kv-cache-dtype fp8 --calculate-kv-scales` if supported by the deployed vLLM/ROCm stack

AMD’s strongest FP8/Quark recommendations target MI300-class hardware. On MI250X, validate model quality and throughput before relying on them.

### GEMM Tuning

AMD documents vLLM GEMM tuning via:

- collect shapes with `VLLM_TUNE_GEMM=1`
- tune the collected GEMM CSV for the chosen tensor-parallel size
- run with `VLLM_TUNE_FILE=<tuned-file>`

Only do this after model, TP size, dtype, and sequence lengths are stable. GEMM tuning is specific to the tensor-parallel setup.

## Suggested Benchmark Matrix

Keep the first sweep small:

| Sweep | Values |
| --- | --- |
| `--max-num-batched-tokens` | `8192`, `16384`, `32768`, `65536` |
| `--max-num-seqs` | `32`, `64`, `128`, `256` |
| `--gpu-memory-utilization` | `0.85`, `0.90`, `0.95` |
| parallelism | independent replicas, `TP=4`, `TP=8` |
| attention | baseline, AITER, prefill/decode split |
| KV cache | default, `fp8` |

Measure:

- tokens/sec
- completed agent steps/sec
- TTFT and inter-token latency
- GPU utilization
- KV-cache preemption count
- failed/invalid structured outputs

## Practical Starting Commands

Single 8-GCD node, 70B-class dense model:

```bash
export HIP_FORCE_DEV_KERNARG=1
export TORCH_BLAS_PREFER_HIPBLASLT=1
unset HIP_VISIBLE_DEVICES
export CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7

vllm serve /path/to/model \
  --dtype auto \
  --tensor-parallel-size 8 \
  --gpu-memory-utilization 0.90 \
  --max-model-len 8192 \
  --max-num-batched-tokens 32768 \
  --max-num-seqs 128
```

Smaller dense model, independent replicas:

```bash
export HIP_FORCE_DEV_KERNARG=1
export TORCH_BLAS_PREFER_HIPBLASLT=1
unset HIP_VISIBLE_DEVICES

CUDA_VISIBLE_DEVICES=0 vllm serve /path/to/model --port 8000 --dtype auto --gpu-memory-utilization 0.90 &
CUDA_VISIBLE_DEVICES=1 vllm serve /path/to/model --port 8001 --dtype auto --gpu-memory-utilization 0.90 &
CUDA_VISIBLE_DEVICES=2 vllm serve /path/to/model --port 8002 --dtype auto --gpu-memory-utilization 0.90 &
CUDA_VISIBLE_DEVICES=3 vllm serve /path/to/model --port 8003 --dtype auto --gpu-memory-utilization 0.90 &
wait
```

The independent-replica pattern is likely attractive for this project because agent activations are naturally independent and can be load-balanced across model replicas.

