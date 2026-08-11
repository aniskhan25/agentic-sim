# B2 (Platform-Tuned) Frozen Configuration

This closes `docs/hpc_data_collection_procedures.md`'s Platform-tuned mode section's own remaining open item: the selection *procedure* was already frozen there, but no actual sweep had ever been run and no B2 configuration values existed for either system. Everything below is a **decision made and verified live** on both LUMI and Roihu (2026-08-03), via the frozen one-factor-at-a-time (OFAT) sweep and selection rule (`src/agentic_sim/observability/b2_selection.py`) -- not a value invented from documentation. Full per-candidate sweep-trace artifacts are committed alongside this doc (`docs/baseline/b2_sweep_{lumi,roihu}_trace.json`), so every number below can be checked against the real measurement it came from.

**Correction (2026-08-11)**: the original sweep's per-candidate measurements went through the same unfixed `run_b1_pilot.py` later found to never generate real concurrent backend load (roadmap item 19's B1-vs-B2 investigation). `max_num_seqs` and `gpu_memory_utilization` have since been re-swept under real concurrent load and their frozen values corrected -- see "Operational finding: re-swept under real concurrent load" below. The tables immediately below reflect the **corrected, current** values; the divergence table's effect-size column retains the original (low-concurrency) evidence for `max_num_batched_tokens` (unchanged) alongside the new evidence for the two corrected dimensions.

**Scope**: single-device placement only, `storm` workload, `causal_only` dispatch policy held fixed, 3 repetitions per candidate (see `docs/research_roadmap.md` item 19 and the approved B2 plan for the full rationale). This selects and freezes a serving configuration; it does not run B2's primary 10-repetition data collection, which is separate future work.

## Frozen configuration, both systems

| Parameter | B1 (common-denominator) | B2 LUMI | B2 Roihu |
|---|---|---|---|
| `--max-num-batched-tokens` | 16384 | **8192** | **8192** |
| `--max-num-seqs` | 64 | **64** (corrected from 32, see below) | **128** (corrected from 32, see below) |
| `--gpu-memory-utilization` | 0.90 | **0.85** (corrected from 0.90, see below) | **0.85** (re-confirmed) |
| Attention backend | baseline | baseline (unchanged) | baseline (unchanged) |
| `--kv-cache-dtype` | `fp8_e4m3` | `fp8_e4m3` (unchanged) | `fp8_e4m3` (unchanged) |
| Serving-runtime version | `0.19.0`/`0.19.1` pairing (B1's forced compromise) | independently best available, per B2's own permission (`docs/b1_frozen_configuration.md`) -- not re-verified here, since neither system's container inventory changed during this sweep | same |

## Divergence table vs. B1 (per `docs/hpc_data_collection_procedures.md`'s explicit requirement to record every B2 divergence from B1)

| Parameter | B1 value | B2 LUMI | B2 Roihu | Real effect size (from the sweep trace) |
|---|---|---|---|---|
| `max_num_batched_tokens` | 16384 | 8192 | 8192 | Tie-break pick, not a clear win on either system -- all 4 candidates' mean±1stdev bands overlapped at n=3 (LUMI: 0.337-0.369 range; Roihu: 1.17-1.59 range). The frozen tie-break rule (smaller value wins ties) resolved it, not a statistically distinguishable throughput difference. |
| `max_num_seqs` | 64 | 64 | 128 | **Superseded** -- at n=3 under low concurrency, all 4 candidates tied on both systems (LUMI: 0.387-0.418; Roihu: 1.28-1.53), a tie-break pick of 32. Re-swept under real concurrent load (see "Operational finding: re-swept under real concurrent load" below): 32 is a real, non-overlapping loser on both systems; corrected winners are 64 (LUMI) and 128 (Roihu). |
| `gpu_memory_utilization` | 0.90 | **0.85** | **0.85** | **LUMI superseded, Roihu re-confirmed.** Original (low concurrency): LUMI's 0.9 and 0.95 tied, 0.9 won the tie-break, 0.85 was a real loser (0.337 vs 0.407/0.482); Roihu's all 3 tied (1.28-1.53), 0.85 won as the smaller value. Re-swept under real load: LUMI's 0.85 is no longer a loser -- all 3 now tie (3.72-3.74), and 0.85 wins the tie-break, superseding 0.90. Roihu's all 3 remain tied (14.16-14.63) -- 0.85 re-confirmed. |
| Attention backend | baseline | baseline | baseline | **Both alternatives are confirmed available and functional** -- AITER (LUMI, `VLLM_ROCM_USE_AITER=1`) and FLASHINFER (Roihu, `VLLM_ATTENTION_BACKEND=FLASHINFER`) both started and served real traffic without error. LUMI: AITER tied with baseline (0.355 vs 0.356) -- no real difference. Roihu: FLASHINFER is a **clear, non-overlapping loss** (1.242 vs baseline's 1.525) -- a real finding, not a failure to run. |
| `kv_cache_dtype` | `fp8_e4m3` | `fp8_e4m3` | `fp8_e4m3` | **Real, clear, non-overlapping win on both systems** (LUMI: 0.413 vs 0.217, re-measured cleanly after the bug below; Roihu: 1.778 vs 0.850). B1's feature-parity choice and B2's performance-tuned choice agree here -- the only dimension with a real signal at n=3 on both systems. |

## Operational finding: OFAT tie-breaks dominate at n=3

Reading the divergence table plainly: **3 of 5 swept dimensions (batched tokens, num_seqs, gpu_memory_utilization) resolved via the frozen tie-break rule, not a clear measured win**, on both systems. At 3 repetitions per candidate, real differences in most of these dimensions are within noise for this workload/model/hardware combination -- only `kv_cache_dtype` (and, on Roihu, the attention-backend choice) showed a real, unambiguous effect. This is not a flaw in the procedure -- the frozen tie-break rule (prefer the smaller/simpler value) is doing exactly what it is supposed to do when the data doesn't distinguish candidates -- but it means B2's selected batching parameters should be read as "no worse than B1's, and simpler," not "measurably faster." A higher-repetition confirmatory sweep would be needed to know whether real differences exist in these three dimensions.

## Operational finding: an unrelated bug corrupted the first LUMI sweep attempt

The first LUMI sweep run (job `20628781`) hit two real bugs, both now fixed:

1. **A scripting bug in the sweep orchestration itself**: the candidate-JSON builder embedded bash's `true`/`false` directly into a Python snippet (`'had_preemption': $HAD_PREEMPTION`), where only `True`/`False` are valid -- every single candidate crashed with `NameError`, and the resulting blank "winner" then silently blanked out `max_num_batched_tokens` for the rest of the run, cascading into a full 2h30m timeout with nothing recovered. Fixed in the job scripts on both systems (a Python-safe `HAD_PREEMPTION_PY` variable), plus a defensive guard so a blank/invalid winner falls back to the current-best value with a loud warning instead of silently propagating.
2. **A real, pre-existing robustness gap in `storm_env.py`/`supply_chain_env.py`** (`src/agentic_sim/environment/`): `apply_actions` indexed `action.payload["region"]`/`action.payload["delta"]` directly, with no default -- unlike the `.get(..., default)` pattern already used one line above for the same dict. A real vLLM completion at `temperature=0.2` occasionally omits an expected field, and this uncaught `KeyError` during pilot warm-up (not wrapped in `run_b1_pilot`'s per-repetition try/except, which only guards the timed repetitions) killed the entire run rather than excluding one repetition. This is what actually crashed the `kv_cache_dtype=default` candidate specifically -- **not** a real finding about that serving parameter. Fixed (commit `dbd2a88`): a missing `region` is now a no-op, a missing `delta` defaults to 0, matching the existing defensive style in both files. Confirmed no other candidate in the corrupted run had any excluded repetitions, so only the `kv_cache_dtype` dimension needed re-measurement -- done via a small standalone re-run (`b2_sweep_lumi_kvcache_rerun.json`) holding dimensions 1-4 at their already-confirmed winners; the corrected numbers (`default`: 0.217, `fp8_e4m3`: 0.413) are what's reported in the divergence table above and replace the corrupted first attempt's misleading "all candidates disqualified" result for that dimension.

Roihu's rerun (after the same two fixes were applied, job `443514`) completed cleanly end-to-end with zero crashes or excluded repetitions on the first attempt.

## Operational finding: re-swept under real concurrent load, `max_num_seqs` corrected on both systems

The B1-vs-B2 confirmatory comparison (roadmap item 19) found the original sweep's low measured throughput never came close to stressing `max_num_seqs` at all: `run_b1_pilot.py` never set `agent_replicas` (4-5 agents), `SimulationEngine`'s `max_events_per_tick` capped activity at 32/tick, and `CausalOnlyDispatchPolicy`'s `ThreadPoolExecutor` defaulted to `max_workers=8` -- so every sweep candidate, regardless of its configured `max_num_seqs`, only ever saw 8 real concurrent requests. Three new `run_b1_pilot.py` flags (`--agent-replicas`, `--max-events-per-tick`, `--dispatch-max-workers`, already added for that investigation) fix this. `max_num_batched_tokens`, `max_num_seqs`, and `gpu_memory_utilization` -- the 3 of 5 dimensions whose original tie-break picks were not proven wins -- were re-swept with `--agent-replicas 48 --max-events-per-tick 128 --dispatch-max-workers 128` (the same settings that reversed the B1-vs-B2 null result), `storm`-only, 3 reps/candidate (matching the original sweep's own rep count for direct comparability). `kv_cache_dtype` and attention backend were **not** re-swept -- both already showed real, non-overlapping evidence, and concurrency level does not change a per-token compute/precision effect.

**Result**: `max_num_batched_tokens` re-confirms unchanged (8192 on both systems, still fully overlapping bands -- real load doesn't distinguish these candidates any better than low load did). `gpu_memory_utilization` re-confirms unchanged on Roihu (0.85, still fully overlapping). But `max_num_seqs` is a real, non-overlapping correction on **both** systems, and LUMI's `gpu_memory_utilization` shifts too:

| System | Dimension | Old winner (low concurrency) | New winner (real load) | Evidence |
|---|---|---|---|---|
| LUMI | `max_num_seqs` | 32 (tie-break, all 4 tied) | **64** | 32's band (3.80±0.16) no longer overlaps the best candidate's band (128: 4.96±0.43) -- a real, non-overlapping exclusion. 64/128/256 remain tied; 64 wins the tie-break as the smallest. |
| LUMI | `gpu_memory_utilization` | 0.90 (tie-break; 0.85 was a real loser under low load) | **0.85** | All 3 fully tied under real load (3.72-3.74 range) -- 0.85, previously a clear loser, is now statistically indistinguishable from 0.90/0.95 and wins the tie-break as the smallest. |
| Roihu | `max_num_seqs` | 32 (tie-break, all 4 tied) | **128** | 32 (14.24±0.75) and 64 (20.13±0.32) both fall outside the best candidate's band (256: 21.78±1.14) -- a real, non-overlapping exclusion of the original pick. 128/256 remain tied; 128 wins the tie-break. |

Read plainly: **the original `max_num_seqs=32` pick was wrong under real concurrent load on both systems** -- not a methodology flaw, but a direct consequence of the sweep never generating enough concurrent load to expose it, exactly as the B1-vs-B2 investigation predicted. The corrected values (64 on LUMI, matching B1's own value; 128 on Roihu, exceeding B1's 64) are real, non-overlapping, and evidence-backed, not tie-break guesses. Zero KV-cache preemption on any of the 22 real measurement cycles (11 candidates x 2 systems) across the whole re-sweep, checked directly in the server logs. Raw data: `docs/baseline/b2_concurrent_sweep_{lumi,roihu}_trace.json`.

**This does not retroactively validate or invalidate the B1-vs-B2 comparison's finding** (B2 measurably slower than B1 under real load, all 4 (system, workload) combinations, non-overlapping) -- that comparison used the *old*, now-superseded `max_num_seqs=32` value. Whether B2 with the corrected config still trails B1 is an open question, not yet tested (see below).

## What remains open

- Whether B2 with the corrected `max_num_seqs` (and, on LUMI, `gpu_memory_utilization`) still trails B1 under real load -- the B1-vs-B2 comparison's "B2 is slower" finding used the old, now-superseded config and has not been rerun against the correction.
- A higher-repetition confirmatory rerun of the corrected `max_num_seqs`/`gpu_memory_utilization` values specifically, since the re-sweep above matched the original's exploratory 3-rep scale, not a confirmatory one.
- `max_num_batched_tokens` still resolved via tie-break under both low and real concurrent load -- unresolved whether a real effect exists at all for this dimension, or whether it's genuinely inconsequential for this workload/model/hardware.
- B2's actual primary 10-repetition data collection using this frozen config, for any workload or placement level -- this step only selects and freezes the config.
- `supply_chain` or any other workload's B2 configuration -- this sweep used `storm` only, as a representative workload for config *selection*.
- Full-node placement's B2 configuration -- this sweep is single-device only, matching B1's own phasing.
