# XXL-Wide DFM11: 425K-450K After Cooldown

Latest logged step: 450000; bootstrap block: ~500 steps; draws: 100000.

## Interpretation

Descriptive, exploratory evidence only: these are different batches and changing weights, not paired held-out evaluations. Means weight logged steps equally, not individual tokens. Circular blocks preserve short-range dependence; nonstationarity, long correlation, gaps and LR/BP changes can invalidate nominal coverage. No spikes are removed. Confidence intervals are marginal percentile intervals. Adjacent-window bootstrap tests are approximate; Holm adjustment covers all metrics/comparisons in this report but not earlier repeated monitoring or alternative block-size runs. Very small p-values are limited by draw count. A star denotes Holm-adjusted p<0.05, not proven generalization or causality.

Accuracy values/deltas are percentages/percentage points; loss uses its logged units.

## Window Means and 95% Intervals

| Steps | N | Loss | Accuracy (%) | Exact (%) | Loss >2 | BP range |
|---|---:|---|---|---|---:|---|
| 420000-425000 | 1000 | 0.7978 [0.7943, 0.8012] | 80.7895 [80.7301, 80.8533] | 34.7979 [34.6906, 34.9153] | 0 | 8-8 |
| 425000-430000 | 1000 | 0.7937 [0.7898, 0.7976] | 80.8997 [80.8302, 80.9720] | 34.9940 [34.8532, 35.1286] | 0 | 8-8 |
| 430000-435000 | 1000 | 0.7931 [0.7893, 0.7967] | 80.8851 [80.8199, 80.9534] | 34.9891 [34.8877, 35.0806] | 0 | 8-8 |
| 435000-440000 | 1000 | 0.7912 [0.7881, 0.7944] | 80.9171 [80.8498, 80.9834] | 35.1435 [35.0603, 35.2272] | 0 | 8-8 |
| 440000-445000 | 1000 | 0.7938 [0.7898, 0.7981] | 80.8835 [80.8128, 80.9500] | 34.9952 [34.8673, 35.1238] | 0 | 8-8 |
| 445000-450000 | 1000 | 0.7922 [0.7891, 0.7956] | 80.8935 [80.8361, 80.9481] | 35.0853 [34.9440, 35.2044] | 0 | 8-8 |

## Whole-Run Means and Trailing Trends

Trailing 10000-step OLS trends use Bartlett/Newey-West HAC errors with ~500-step lag bandwidth, not bootstrap intervals. Slopes are per 10K steps. Stars use Holm correction jointly across adjacent comparisons and trends. Overlapping trends are not independent. Linear-model assumptions are especially questionable across early rapid learning, spikes and BP/LR changes.

| Window | Loss | Accuracy % | Exact % | Loss slope [95% CI] | Accuracy pp slope [95% CI] | Exact pp slope [95% CI] |
|---|---:|---:|---:|---|---|---|
| 420000-425000 | 0.7978 | 80.7895 | 34.7979 | -0.0111 [-0.0196, -0.0027] | +0.1622 [-0.0368, +0.3612] | +0.4028 [+0.1304, +0.6751] |
| 425000-430000 | 0.7937 | 80.8997 | 34.9940 | -0.0034 [-0.0148, +0.0080] | +0.1014 [-0.0840, +0.2869] | +0.2905 [-0.0550, +0.6361] |
| 430000-435000 | 0.7931 | 80.8851 | 34.9891 | +0.0038 [-0.0053, +0.0129] | -0.0980 [-0.2695, +0.0735] | -0.1411 [-0.4322, +0.1500] |
| 435000-440000 | 0.7912 | 80.9171 | 35.1435 | +0.0022 [-0.0053, +0.0097] | -0.0336 [-0.1795, +0.1123] | +0.2167 [-0.0316, +0.4649] |
| 440000-445000 | 0.7938 | 80.8835 | 34.9952 | +0.0033 [-0.0060, +0.0126] | -0.0458 [-0.2240, +0.1324] | -0.3130 [-0.5666, -0.0594] |
| 445000-450000 | 0.7922 | 80.8935 | 35.0853 | -0.0047 [-0.0137, +0.0043] | +0.0436 [-0.1057, +0.1928] | +0.1055 [-0.1516, +0.3626] |

## Changes From Previous Window

| Window | Metric | Delta [95% CI] | Bootstrap p | Holm p |
|---|---|---|---:|---:|
| 425000-430000 | train/loss | -0.0041 [-0.0093, +0.0011] | 0.12296 | 1 |
| 425000-430000 | train/accuracy | +0.1102 [+0.0157, +0.2043] | 0.02211 | 0.64118 |
| 425000-430000 | train/exact_accuracy | +0.1961 [+0.0148, +0.3698] | 0.02956 | 0.82767 |
| 430000-435000 | train/loss | -0.0006 [-0.0060, +0.0048] | 0.82988 | 1 |
| 430000-435000 | train/accuracy | -0.0146 [-0.1124, +0.0827] | 0.76855 | 1 |
| 430000-435000 | train/exact_accuracy | -0.0049 [-0.1730, +0.1634] | 0.9539 | 1 |
| 435000-440000 | train/loss | -0.0018 [-0.0067, +0.0031] | 0.46645 | 1 |
| 435000-440000 | train/accuracy | +0.0320 [-0.0635, +0.1253] | 0.50802 | 1 |
| 435000-440000 | train/exact_accuracy | +0.1544 [+0.0303, +0.2839] | 0.01735 | 0.52049 |
| 440000-445000 | train/loss | +0.0025 [-0.0026, +0.0079] | 0.34348 | 1 |
| 440000-445000 | train/accuracy | -0.0337 [-0.1303, +0.0612] | 0.49237 | 1 |
| 440000-445000 | train/exact_accuracy | -0.1483 [-0.3011, +0.0050] | 0.057519 | 1 |
| 445000-450000 | train/loss | -0.0015 [-0.0068, +0.0037] | 0.56722 | 1 |
| 445000-450000 | train/accuracy | +0.0100 [-0.0775, +0.1002] | 0.82715 | 1 |
| 445000-450000 | train/exact_accuracy | +0.0901 [-0.1001, +0.2668] | 0.33584 | 1 |

## Input Warnings

None.
