# XXL-Wide Training-Log Uncertainty

Latest logged step: 321910; bootstrap block: ~500 steps; draws: 10000.

## Interpretation

Descriptive, exploratory evidence only: these are different batches and changing weights, not paired held-out evaluations. Means weight logged steps equally, not individual tokens. Circular blocks preserve short-range dependence; nonstationarity, long correlation, gaps and LR/BP changes can invalidate nominal coverage. No spikes are removed. Confidence intervals are marginal percentile intervals. Adjacent-window bootstrap tests are approximate; Holm adjustment covers all metrics/comparisons in this report but not earlier repeated monitoring or alternative block-size runs. Very small p-values are limited by draw count. A star denotes Holm-adjusted p<0.05, not proven generalization or causality.

Accuracy values/deltas are percentages/percentage points; loss uses its logged units.

## Window Means and 95% Intervals

| Steps | N | Loss | Accuracy (%) | Exact (%) | Loss >2 |
|---|---:|---|---|---|---:|
| 300000-305000 | 990 | 0.8501 [0.8459, 0.8543] | 79.9611 [79.8844, 80.0367] | 32.3210 [32.2126, 32.4392] | 0 |
| 315000-320000 | 973 | 0.8420 [0.8384, 0.8452] | 80.1005 [80.0462, 80.1546] | 32.7048 [32.6105, 32.8090] | 0 |

## Changes From Previous Window

| Window | Metric | Delta [95% CI] | Bootstrap p | Holm p |
|---|---|---|---:|---:|
| 315000-320000 | train/loss | -0.0082 [-0.0136, -0.0029] | 0.0029997 | 0.0059994 * |
| 315000-320000 | train/accuracy | +0.1395 [+0.0482, +0.2318] | 0.0034997 | 0.0059994 * |
| 315000-320000 | train/exact_accuracy | +0.3838 [+0.2313, +0.5328] | 9.999e-05 | 0.00029997 * |

## Input Warnings

None.
