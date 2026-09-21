# XXL-Wide DFM11: 400K-425K Cooldown

Latest logged step: 450000; bootstrap block: ~500 steps; draws: 100000.

## Interpretation

Descriptive, exploratory evidence only: these are different batches and changing weights, not paired held-out evaluations. Means weight logged steps equally, not individual tokens. Circular blocks preserve short-range dependence; nonstationarity, long correlation, gaps and LR/BP changes can invalidate nominal coverage. No spikes are removed. Confidence intervals are marginal percentile intervals. Adjacent-window bootstrap tests are approximate; Holm adjustment covers all metrics/comparisons in this report but not earlier repeated monitoring or alternative block-size runs. Very small p-values are limited by draw count. A star denotes Holm-adjusted p<0.05, not proven generalization or causality.

Accuracy values/deltas are percentages/percentage points; loss uses its logged units.

## Window Means and 95% Intervals

| Steps | N | Loss | Accuracy (%) | Exact (%) | Loss >2 | BP range |
|---|---:|---|---|---|---:|---|
| 390000-395000 | 1000 | 0.8128 [0.8088, 0.8164] | 80.4772 [80.4100, 80.5519] | 34.0378 [33.9585, 34.1106] | 0 | 8-8 |
| 395000-400000 | 1000 | 0.8130 [0.8080, 0.8175] | 80.4846 [80.3994, 80.5768] | 33.9949 [33.8767, 34.1138] | 0 | 8-8 |
| 400000-405000 | 989 | 0.8088 [0.8059, 0.8115] | 80.5472 [80.4935, 80.6032] | 34.1098 [33.9883, 34.2281] | 0 | 8-8 |
| 405000-410000 | 1000 | 0.8137 [0.8101, 0.8171] | 80.4607 [80.3808, 80.5396] | 34.2480 [34.0958, 34.3939] | 0 | 8-8 |
| 410000-415000 | 1000 | 0.8099 [0.8062, 0.8140] | 80.5449 [80.4723, 80.6118] | 34.3394 [34.2250, 34.4572] | 0 | 8-8 |
| 415000-420000 | 1000 | 0.8032 [0.7992, 0.8069] | 80.7139 [80.6315, 80.8048] | 34.5887 [34.4871, 34.6883] | 0 | 8-8 |
| 420000-425000 | 1000 | 0.7978 [0.7943, 0.8013] | 80.7895 [80.7296, 80.8529] | 34.7979 [34.6901, 34.9146] | 0 | 8-8 |

## Whole-Run Means and Trailing Trends

Trailing 10000-step OLS trends use Bartlett/Newey-West HAC errors with ~500-step lag bandwidth, not bootstrap intervals. Slopes are per 10K steps. Stars use Holm correction jointly across adjacent comparisons and trends. Overlapping trends are not independent. Linear-model assumptions are especially questionable across early rapid learning, spikes and BP/LR changes.

| Window | Loss | Accuracy % | Exact % | Loss slope [95% CI] | Accuracy pp slope [95% CI] | Exact pp slope [95% CI] |
|---|---:|---:|---:|---|---|---|
| 390000-395000 | 0.8128 | 80.4772 | 34.0378 | -0.0047 [-0.0124, +0.0031] | +0.1158 [-0.0281, +0.2596] | -0.0719 [-0.3250, +0.1812] |
| 395000-400000 | 0.8130 | 80.4846 | 33.9949 | -0.0004 [-0.0131, +0.0122] | +0.0127 [-0.2254, +0.2507] | -0.1153 [-0.3296, +0.0991] |
| 400000-405000 | 0.8088 | 80.5472 | 34.1098 | -0.0108 [-0.0193, -0.0023] | +0.1748 [+0.0177, +0.3319] | +0.1527 [-0.1785, +0.4838] |
| 405000-410000 | 0.8137 | 80.4607 | 34.2480 | +0.0063 [-0.0006, +0.0131] | -0.1002 [-0.2519, +0.0516] | +0.2601 [-0.0750, +0.5952] |
| 410000-415000 | 0.8099 | 80.5449 | 34.3394 | -0.0066 [-0.0159, +0.0027] | +0.1517 [-0.0415, +0.3448] | +0.2204 [-0.0585, +0.4994] |
| 415000-420000 | 0.8032 | 80.7139 | 34.5887 | -0.0143 [-0.0231, -0.0055] | +0.3473 [+0.1717, +0.5229] * | +0.3485 [+0.0785, +0.6185] |
| 420000-425000 | 0.7978 | 80.7895 | 34.7979 | -0.0111 [-0.0196, -0.0027] | +0.1622 [-0.0368, +0.3612] | +0.4028 [+0.1304, +0.6751] |

## Changes From Previous Window

| Window | Metric | Delta [95% CI] | Bootstrap p | Holm p |
|---|---|---|---:|---:|
| 395000-400000 | train/loss | +0.0002 [-0.0060, +0.0062] | 0.95662 | 1 |
| 395000-400000 | train/accuracy | +0.0074 [-0.1055, +0.1218] | 0.89555 | 1 |
| 395000-400000 | train/exact_accuracy | -0.0428 [-0.1829, +0.0984] | 0.55534 | 1 |
| 400000-405000 | train/loss | -0.0042 [-0.0096, +0.0015] | 0.13789 | 1 |
| 400000-405000 | train/accuracy | +0.0626 [-0.0439, +0.1651] | 0.23919 | 1 |
| 400000-405000 | train/exact_accuracy | +0.1149 [-0.0559, +0.2830] | 0.18209 | 1 |
| 405000-410000 | train/loss | +0.0049 [+0.0004, +0.0093] | 0.03222 | 0.90215 |
| 405000-410000 | train/accuracy | -0.0865 [-0.1833, +0.0093] | 0.078059 | 1 |
| 405000-410000 | train/exact_accuracy | +0.1381 [-0.0534, +0.3294] | 0.15997 | 1 |
| 410000-415000 | train/loss | -0.0037 [-0.0089, +0.0016] | 0.16258 | 1 |
| 410000-415000 | train/accuracy | +0.0843 [-0.0224, +0.1878] | 0.11767 | 1 |
| 410000-415000 | train/exact_accuracy | +0.0914 [-0.0955, +0.2840] | 0.34449 | 1 |
| 415000-420000 | train/loss | -0.0068 [-0.0124, -0.0014] | 0.01591 | 0.4773 |
| 415000-420000 | train/accuracy | +0.1690 [+0.0618, +0.2842] | 0.00257 | 0.092519 |
| 415000-420000 | train/exact_accuracy | +0.2494 [+0.0948, +0.4013] | 0.0013 | 0.0494 * |
| 420000-425000 | train/loss | -0.0054 [-0.0105, -0.0001] | 0.0427 | 1 |
| 420000-425000 | train/accuracy | +0.0755 [-0.0330, +0.1799] | 0.16509 | 1 |
| 420000-425000 | train/exact_accuracy | +0.2092 [+0.0615, +0.3628] | 0.0060699 | 0.20638 |

## Input Warnings

None.
