---
type: Incident
title: DFM8 XXL Step 150.7K Loss Excursion
description: Evidence and operational interpretation of the self-recovering DFM8 XXL loss spike near step 150700.
tags: [training, dfm8, xxl, stability, optimizer]
status: stable
last_updated: 2026-08-26
confidence: high
---
# DFM8 XXL Step 150.7K Loss Excursion

The `DFM5/40j5y877` run (`dfm8-XXL-1epoch`) experienced one severe but
self-recovering loss excursion between steps 150655 and 150875. Loss rose from
approximately `1.1` to a maximum of `7.2855` at step 150685, exact accuracy
fell to zero, and both recovered without changing the learning rate or BP-step
schedule. Loss was back near its earlier range by step 150875 and remained
healthy after the step-151000 resume.

This was not a W&B visualization artifact. It was also not a checkpoint-resume
boundary: the run resumed at step 150000 and the excursion began approximately
655 optimizer steps later. Throughout the event, `train/lr=4e-4` and
`bp_steps=5`.

## Data Attribution

### Slope-adjusted recovery review, 2026-09-08

Full-history follow-up: [all 44 spike groups](../../../docs/xxl-loss-spikes.md) are
listed through step 487500, with CSV and JSON companions. Reproduce using
`scripts/analyze_xxl_loss_spikes.py` (read-only W&B access). This uses loss >2
after 10K, grouping observations separated by at most 1K steps, deduplicates
optimizer-step observations, fits the preceding 10K in 500-step bins, and
uses the same post-window for every event: 1K--6K after its last >2 point.
Ten events have clean baselines and complete post-windows; only the 410785
event is below its extrapolated trend (-0.00582). Seven of these ten still
have additional spikes in their post-windows. The 215170 and 427055 events
have clean post-windows but are respectively +0.00106 and +0.00965 above
trend. The 150665 event is +0.00252 in this earlier standardized window;
the improvement against trend quoted below used a later window. Results
therefore depend on recovery horizon and do not establish a causal benefit.

The [exact-accuracy companion](../../../docs/xxl-spike-exact-accuracy.md)
uses the identical saved 44 loss events and cutoff, with CSV/JSON companions
and `scripts/analyze_xxl_spike_exact_accuracy.py` for reproduction. Of the ten
clean-baseline events with complete post-windows, only 410785 exceeded its
projected exact-accuracy trend, by 0.0153 percentage points (29.3323% actual,
29.3170% predicted). This is too small to establish a meaningful benefit.
At 215170 and 427055, exact accuracy exceeded the old mean slightly but was
respectively 0.2671 and 0.0716 percentage points below trend. The other seven
post-windows include renewed loss spikes and larger exact-accuracy deficits.

The [training-accuracy companion](../../../docs/xxl-spike-training-accuracy.md)
uses the same events/windows via the same script with `--metric accuracy`.
Again only 410785 of the ten clean-baseline, complete-window events exceeded
trend: 77.7518% observed versus 77.6553% predicted (+0.0965 percentage points).
The clean post-windows at 215170 and 427055 were respectively 0.0240 and
0.1871 percentage points below trend. All three metrics therefore agree on
the direction of the residual for these ten events, with no established
causal benefit from instability.

Remote history was fitted with linear regressions on equally weighted
500-step mean losses over the 10K steps before each major excursion.
Before step 150655, mean loss was 1.08941 and slope was +0.000800 per 1K
steps. At 155875--160875, actual mean was 1.09072 versus extrapolated
1.09962: below the rising trend by 0.00890, but not below the pre-spike mean.
Before step 171080, mean was 1.09203 and slope -0.000268 per 1K steps.
At 190000--200000, actual mean was 1.08967 versus extrapolated 1.08427:
slightly better than the old mean but 0.00540 worse than the projected trend.
These extrapolations are descriptive baselines, not causal counterfactuals.

The earlier two-episode description is incomplete: additional groups of losses
above 2 occurred at 173110--173555 (51 logged points) and 177990--178715
(27 points). Their preceding 10K windows already contain earlier spikes:
means 1.38291 and 1.52209, slopes +0.11499 and -0.04589 per 1K. Treating
those contaminated slopes as normal learning trends produces misleading
recovery comparisons. Treat 171K--179K as a cluster for baseline assessment.
Slope estimates also depend on window length: the pre-171080 5K slope was
-0.00603 per 1K versus -0.000268 over 10K, so long extrapolations are fragile.


[`scripts/analyze_sampled_step_sources.py`](/scripts/analyze_sampled_step_sources.py)
reproduces Multipack allocation from a checkpoint's saved global row cursor and
maps sampled token offsets back to DFM8 source tasks. The retained report is
`logs/training/dfm8_XXL_1epoch/step_150500_spike_sources.json`.

The baseline, onset, peak/recovery, and recovered windows have effectively the
same sequence-length and source-family distributions:

| Window | Median length | P95 | P99 | DMMath row share |
|---|---:|---:|---:|---:|
| 150500-150650 | 143 | 1121 | 2823 | 23.04% |
| 150651-150685 | 146 | 1148 | 2863 | 22.94% |
| 150686-150760 | 143 | 1095 | 2807 | 23.07% |
| 150900-151000 | 140 | 1112 | 2803 | 23.20% |

The other dominant families are similarly stable. No source or length cohort
is sufficiently overrepresented to explain the excursion. Since DFM8 rows are
globally Philox-shuffled before Multipack allocation, a long contiguous source
run is not expected.

## Interpretation

The strongest current interpretation is a transient model/optimizer
instability at a constant, aggressive `4e-4` learning rate, possibly initiated
by one or a few unusually influential updates. It is not currently attributable
to a sampled-source distribution shift. The training path does not log gradient
or update norms and does not clip gradients, so the precise initiating update
cannot be reconstructed from existing telemetry. AdamATan2 bounds/scales
updates through `atan2`, so conventional global gradient clipping is not by
itself a complete explanation or guaranteed remedy.

The recovered step-151000 checkpoint is suitable for continued training. Do
not roll back solely because of this isolated event. If it recurs, capture
gradient norm, parameter/update norm, and non-finite counts before changing the
optimizer; repeated excursions would justify lowering LR or adding a guarded
rollback policy.
