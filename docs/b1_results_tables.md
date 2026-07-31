# B1 Results Tables

Closes `evaluation_plan.md`'s Required Output for B1: "aggregation and plotting scripts," "machine-readable result tables," and "documented commands for each paper table and figure" — the tables half. Plotting/figures are not built here; a separate, later step once these tables exist to plot from.

## Regenerating

```bash
python3 scripts/aggregate_b1_results.py
```

Reads every real result file listed in `scripts/aggregate_b1_results.py`'s hand-written manifest (not inferred from filenames — the JSON payloads carry no `system`/`workload`/`placement` metadata of their own, so every classification is an explicit, reviewable line of code) and regenerates:

- `docs/baseline/b1_summary.csv` / `.md` — one row per (system, workload, placement, policy).
- `docs/baseline/b1_contrasts_summary.csv` / `.md` — the three prespecified contrasts (`causal_only_vs_sequential`, `full_vs_causal_only`, `full_vs_sequential`) per (system, workload, placement).
- `docs/baseline/b1_retune_sweep_summary.csv` / `.md` — the exploratory `default_max_in_flight` sweep, kept separate since its policy names (`queue_aware_2/4/8`, `full_2/4/8`) don't match the standard 7-rung ladder.

## Reading the tables

`capacity_type` distinguishes two honestly-different kinds of row:

- **`per_device`**: a single-device run's own measured mean/stdev, passed through directly from `docs/baseline/b1_pilot_*`/`b1_study_*` JSON.
- **`node_total`**: several full-node replicas (`n_replicas` of them) summed. `mean` is a real measurement (independent replicas' real throughput, added). `stdev` is **not fabricated** — it is properly propagated from each replica's own stdev via the standard independent-sum variance rule (`Var(sum) = sum(Var(x_i))`), which is what actually justifies treating it as a real error bar. `per_replica_min`/`per_replica_max` are also reported as a plain consistency check (do replicas roughly agree with each other, or is there real host contention).

`source` traces every row back to the exact file(s) it came from — a filename for `per_device` rows, the `system|workload` replica-group key for `node_total` rows (see the manifest for which files that key covers).

## What building this surfaced

Two independent single-device `storm` measurements exist per system (`b1_pilot_*` and `b1_study_*_storm`, run at different points in this session) — both kept as separate rows rather than merged, since they're genuinely separate real runs, not duplicates.

Proper stdev propagation for `node_total` contrasts (rather than eyeballing point estimates, as earlier chat summaries did) sharpened one finding: **LUMI's `supply_chain` full-node `full_vs_causal_only` is `bands_overlap: False`** (-10.7%, a real, statistically distinguishable regression) — unlike the other three full-node `full_vs_causal_only` comparisons (LUMI `storm`, Roihu `storm`, Roihu `supply_chain`), which all still show `bands_overlap: True` at this 3-repeat/replica scale. This refines (doesn't overturn) the earlier, more cautious "likely noise, not yet statistically tested" framing for full-node `full` vs. `causal_only` — one of the four combinations already clears real statistical significance even at pilot scale; the other three would need more repetitions to say either way.

## Explicit gaps

- No plotting/figure generation — tables only.
- No B2 (platform-tuned) results exist yet to summarize.
- No results for `deterministic_kernel`/`synthetic dependency graphs`/`failure workloads` — those workload families still can't run against a real backend (see `docs/research_roadmap.md` item 19).
- Full-node rows are all at 3-repetitions-per-replica pilot scale, not the 10-repetition confirmatory scale single-device rows reached.
