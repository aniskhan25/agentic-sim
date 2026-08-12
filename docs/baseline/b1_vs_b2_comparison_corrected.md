# B1 vs. B2 Comparison (causal_only, corrected B2 config: max_num_seqs 64/128, gpu_memory_utilization 0.85 -- storm 15 reps, supply_chain 5 reps, B1 unchanged/reused)

| system | workload | b1_mean | b1_stdev | b1_count | b2_mean | b2_stdev | b2_count | relative_improvement | bands_overlap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lumi | storm | 4.6421 | 0.3444 | 15 | 4.9508 | 0.3905 | 15 | 0.0665 | True |
| roihu | storm | 19.0082 | 1.0444 | 15 | 21.8849 | 1.4706 | 15 | 0.1513 | False |
| lumi | supply_chain | 4.0542 | 0.2035 | 5 | 4.2567 | 0.3897 | 5 | 0.05 | True |
| roihu | supply_chain | 15.5483 | 0.5745 | 5 | 18.517 | 1.5374 | 5 | 0.1909 | False |
