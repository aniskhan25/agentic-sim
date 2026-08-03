# B2 (Platform-Tuned) Frozen Configuration

This closes `docs/hpc_data_collection_procedures.md`'s Platform-tuned mode section's own remaining open item: the selection *procedure* was already frozen there, but no actual sweep had ever been run and no B2 configuration values existed for either system. Everything below is a **decision made and verified live** on both LUMI and Roihu (2026-08-03), via the frozen one-factor-at-a-time (OFAT) sweep and selection rule (`src/agentic_sim/observability/b2_selection.py`) -- not a value invented from documentation. Full per-candidate sweep-trace artifacts are committed alongside this doc (`docs/baseline/b2_sweep_{lumi,roihu}_trace.json`), so every number below can be checked against the real measurement it came from.

**Scope**: single-device placement only, `storm` workload, `causal_only` dispatch policy held fixed, 3 repetitions per candidate (see `docs/research_roadmap.md` item 19 and the approved B2 plan for the full rationale). This selects and freezes a serving configuration; it does not run B2's primary 10-repetition data collection, which is separate future work.

## Frozen configuration, both systems

| Parameter | B1 (common-denominator) | B2 LUMI | B2 Roihu |
|---|---|---|---|
| `--max-num-batched-tokens` | 16384 | **8192** | **8192** |
| `--max-num-seqs` | 64 | **32** | **32** |
| `--gpu-memory-utilization` | 0.90 | 0.90 (unchanged) | **0.85** |
| Attention backend | baseline | baseline (unchanged) | baseline (unchanged) |
| `--kv-cache-dtype` | `fp8_e4m3` | `fp8_e4m3` (unchanged) | `fp8_e4m3` (unchanged) |
| Serving-runtime version | `0.19.0`/`0.19.1` pairing (B1's forced compromise) | independently best available, per B2's own permission (`docs/b1_frozen_configuration.md`) -- not re-verified here, since neither system's container inventory changed during this sweep | same |

## Divergence table vs. B1 (per `docs/hpc_data_collection_procedures.md`'s explicit requirement to record every B2 divergence from B1)

| Parameter | B1 value | B2 LUMI | B2 Roihu | Real effect size (from the sweep trace) |
|---|---|---|---|---|
| `max_num_batched_tokens` | 16384 | 8192 | 8192 | Tie-break pick, not a clear win on either system -- all 4 candidates' mean±1stdev bands overlapped at n=3 (LUMI: 0.337-0.369 range; Roihu: 1.17-1.59 range). The frozen tie-break rule (smaller value wins ties) resolved it, not a statistically distinguishable throughput difference. |
| `max_num_seqs` | 64 | 32 | 32 | Same pattern: all 4 candidates tied on both systems (LUMI: 0.387-0.418; Roihu: 1.28-1.53). Tie-break, not a real signal at this sample size. |
| `gpu_memory_utilization` | 0.90 | 0.90 | **0.85** | LUMI: 0.9 and 0.95 tied for best, 0.9 won the tie-break; 0.85 was a real loser (0.337 vs 0.407/0.482). Roihu: all 3 tied (1.28-1.53) -- 0.85 won purely on being the smaller value, a genuine per-system divergence in the *selected* value even though neither system shows a real preference at n=3. |
| Attention backend | baseline | baseline | baseline | **Both alternatives are confirmed available and functional** -- AITER (LUMI, `VLLM_ROCM_USE_AITER=1`) and FLASHINFER (Roihu, `VLLM_ATTENTION_BACKEND=FLASHINFER`) both started and served real traffic without error. LUMI: AITER tied with baseline (0.355 vs 0.356) -- no real difference. Roihu: FLASHINFER is a **clear, non-overlapping loss** (1.242 vs baseline's 1.525) -- a real finding, not a failure to run. |
| `kv_cache_dtype` | `fp8_e4m3` | `fp8_e4m3` | `fp8_e4m3` | **Real, clear, non-overlapping win on both systems** (LUMI: 0.413 vs 0.217, re-measured cleanly after the bug below; Roihu: 1.778 vs 0.850). B1's feature-parity choice and B2's performance-tuned choice agree here -- the only dimension with a real signal at n=3 on both systems. |

## Operational finding: OFAT tie-breaks dominate at n=3

Reading the divergence table plainly: **3 of 5 swept dimensions (batched tokens, num_seqs, gpu_memory_utilization) resolved via the frozen tie-break rule, not a clear measured win**, on both systems. At 3 repetitions per candidate, real differences in most of these dimensions are within noise for this workload/model/hardware combination -- only `kv_cache_dtype` (and, on Roihu, the attention-backend choice) showed a real, unambiguous effect. This is not a flaw in the procedure -- the frozen tie-break rule (prefer the smaller/simpler value) is doing exactly what it is supposed to do when the data doesn't distinguish candidates -- but it means B2's selected batching parameters should be read as "no worse than B1's, and simpler," not "measurably faster." A higher-repetition confirmatory sweep would be needed to know whether real differences exist in these three dimensions.

## Operational finding: an unrelated bug corrupted the first LUMI sweep attempt

The first LUMI sweep run (job `20628781`) hit two real bugs, both now fixed:

1. **A scripting bug in the sweep orchestration itself**: the candidate-JSON builder embedded bash's `true`/`false` directly into a Python snippet (`'had_preemption': $HAD_PREEMPTION`), where only `True`/`False` are valid -- every single candidate crashed with `NameError`, and the resulting blank "winner" then silently blanked out `max_num_batched_tokens` for the rest of the run, cascading into a full 2h30m timeout with nothing recovered. Fixed in the job scripts on both systems (a Python-safe `HAD_PREEMPTION_PY` variable), plus a defensive guard so a blank/invalid winner falls back to the current-best value with a loud warning instead of silently propagating.
2. **A real, pre-existing robustness gap in `storm_env.py`/`supply_chain_env.py`** (`src/agentic_sim/environment/`): `apply_actions` indexed `action.payload["region"]`/`action.payload["delta"]` directly, with no default -- unlike the `.get(..., default)` pattern already used one line above for the same dict. A real vLLM completion at `temperature=0.2` occasionally omits an expected field, and this uncaught `KeyError` during pilot warm-up (not wrapped in `run_b1_pilot`'s per-repetition try/except, which only guards the timed repetitions) killed the entire run rather than excluding one repetition. This is what actually crashed the `kv_cache_dtype=default` candidate specifically -- **not** a real finding about that serving parameter. Fixed (commit `dbd2a88`): a missing `region` is now a no-op, a missing `delta` defaults to 0, matching the existing defensive style in both files. Confirmed no other candidate in the corrupted run had any excluded repetitions, so only the `kv_cache_dtype` dimension needed re-measurement -- done via a small standalone re-run (`b2_sweep_lumi_kvcache_rerun.json`) holding dimensions 1-4 at their already-confirmed winners; the corrected numbers (`default`: 0.217, `fp8_e4m3`: 0.413) are what's reported in the divergence table above and replace the corrupted first attempt's misleading "all candidates disqualified" result for that dimension.

Roihu's rerun (after the same two fixes were applied, job `443514`) completed cleanly end-to-end with zero crashes or excluded repetitions on the first attempt.

## What remains open

- A higher-repetition confirmatory B2 sweep, to distinguish real effects from tie-break noise in the three dimensions flagged above.
- B2's actual primary 10-repetition data collection using this frozen config, for any workload or placement level -- this step only selects and freezes the config.
- `supply_chain` or any other workload's B2 configuration -- this sweep used `storm` only, as a representative workload for config *selection*.
- Full-node placement's B2 configuration -- this sweep is single-device only, matching B1's own phasing.
