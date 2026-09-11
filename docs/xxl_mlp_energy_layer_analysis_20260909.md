# XXL Relative-MLP-Energy Replay: Layer Diagnostics

Compared baseline with coefficient 1e-4 from the identical 453000 checkpoint
through 454000. This report concerns the completed pair, not the new 1e-3 run.

## Method and Limits

Each branch has 20 layer/cycle shadow probes at 50-step intervals. They use
CE-only backwards, complete leading sequences with nominal 1024-token budget
per microbatch, and bounded tensor-statistic sampling. The component-gradient
probes use only the first selected microbatch per rank. All four component
probe input hashes match across branches.

Values below are medians across the 20 probes unless marked as maxima. These
RMS ratios are not the auxiliary objective itself: that objective averages
per-token squared ratios over supervised tokens, whereas these diagnostics
include prompt positions and also inspect no-grad forward cycles. Backward
gain means observed input-gradient RMS divided by output-gradient RMS, not a
Jacobian spectral norm. The probes cannot establish the timing of every burst.

## The Intended Intervention Worked Locally

L block 0, cycle 3 (zero-based):

| Diagnostic | Baseline | Extra loss |
|---|---:|---:|
| Incoming post-attention stream RMS | 1.546 | 1.251 |
| MLP residual RMS | 65.32 | 16.86 |
| MLP residual / stream RMS ratio | 42.04 | 13.45 |
| Observed backward gain | 44.31 | 25.95 |

The MLP numerator shrank substantially; the denominator did not inflate.
This argues against denominator inflation being the main explanation for the
measured improvement at this block. But the branch still adds a residual many
times larger than its incoming stream and still amplifies backward signals.

Across probes, the median largest L-block backward gain fell from 64.25 to
38.96; its maximum fell from 630.19 to 188.82. L block 0 remains the dominant
median-gain location in both runs, especially differentiable cycles 3-5.

## Other Locations Worsened

L block 5, cycle 3:

| Diagnostic | Baseline | Extra loss |
|---|---:|---:|
| Post-attention stream RMS | 90.50 | 101.87 |
| MLP residual RMS | 97.11 | 313.42 |
| Attention gate elements above 0.99 | 2.39% | 82.58% |
| Aligned Q/K score proxy RMS | 279.45 | 728.20 |

In the last 500 steps, median MLP residual RMS at this location was 131.45
versus 514.41. The regularizer did not make all blocks smaller or healthier.
This is consistent with compensation or redistribution toward other blocks,
but differing trajectories and inputs to downstream blocks prevent a causal
claim from this pair alone. The change is already visible in the first half,
not only after the final deterioration.

The gates are elementwise sigmoid output gates, not attention probabilities.
The Q/K statistic is the same-position dot product divided by sqrt(head_dim),
not the full attention matrix. Therefore these data do NOT demonstrate
softmax attention collapse or low attention entropy. Extreme gate saturation
and changing Q/K scale are nevertheless useful follow-up targets.

## Recurrent Amplification Remains

The largest observed full recurrent-block backward gain was 39,221 in
baseline versus 198 in the regularized branch. The latter is much better but
not uniformly close to one: at 453850 the L cycle-3 gain was 198, and at 453900
the H cycle-0 gain was 145. The regularized branch's L-block gain maxima rose
again in the second half, reaching 189. This aligns with its late degradation;
it does not prove which operation initiated the bursts.

Forward final-normalization RMS remains approximately one for every H/L
cycle in both branches. That does not guarantee a well-conditioned backward
path through the preceding transformer. The median maximum recurrent injection
ratio was almost unchanged, 1.239 in both branches; these diagnostics provide
no new evidence that increasing injection magnitude alone explains the change.

## Optimizer State and Weight Magnitude

Sampled grouped parameter RMS changed only about -1.01% to +1.02% in baseline
and -1.74% to +0.91% in the regularized run between the first and final probes.
Global weight-magnitude growth is not an obvious explanation for the very
large behavioral changes. Grouped sampled RMS does not measure singular
values, weight rotation, or every parameter independently.

Optimizer moments changed more dramatically. For example, baseline L block 0
exp_avg_sq RMS increased from 1.07e-10 to 1.18e-5; the regularized counterpart
went from 2.61e-6 to 1.12e-5. These endpoints start at 453050, after 50 branch
updates, so they are NOT measurements of the identical initial optimizer
state. Large relative factors starting from tiny values do not establish an
optimizer bug. They do show why residual reduction need not immediately undo
the effects of previous updates. Actual optimizer update/weight ratios were
not recorded and would be more informative than moment magnitudes alone.

No sampled nonfinite activation, gradient, parameter, or optimizer statistic
was observed. This points toward finite dynamical amplification rather than
an observed NaN/Inf failure, without ruling out unobserved events between probes.

## What Deserves Attention Next

1. Evaluate whether coefficient 1e-3 suppresses L block-0 backward amplification
   without further enlarging block-5 residuals or gate saturation. Look at
   local maxima and late behavior, not just the mean auxiliary loss.
2. Measure actual AdamATan2 update RMS and update/weight ratios per physical
   block during a subsequent replay. Gradient clipping alone does not bound
   these adaptive updates to the same numerical threshold.
3. If gate/QK behavior remains suspicious, measure actual masked attention
   entropy, maximum probabilities, and score distributions on bounded samples
   before designing an attention penalty.
4. Consider a more targeted or less easily averaged-away residual objective
   only after the coefficient comparison: e.g. separate layer/cycle reporting
   and smooth emphasis on unusually large token/block ratios. Avoid combining
   this with attention penalties in the same first test.
5. Prompt-only positions and no-grad recurrent calls have no direct auxiliary
   supervision. Shared weights affect them indirectly; assess these slices
   explicitly rather than assuming the supervised-token objective covers all
   forward states.

Bottom line: the penalty reduced the intended local problem and improved the
replay, but residual and recurrent amplification persisted and some downstream
signals worsened. Do not infer that merely increasing the coefficient is a
complete stability solution. Production settings were not changed by this analysis.

## Artifacts

- Raw logs: `checkpoints/experiments/xxl_mlp_shared_prefix_20260908/{baseline,regularized}/layers.jsonl`
- Extracted statistics: `checkpoints/experiments/xxl_mlp_shared_prefix_20260908/layer_analysis.json`
- Reproduce extraction: `python scripts/analyze_mlp_replay_layers.py checkpoints/experiments/xxl_mlp_shared_prefix_20260908`
