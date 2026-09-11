---
type: Experiment Report
title: MLP Energy Replay Layer Diagnostics
description: Remaining instability indicators in the baseline and 1e-4 shared-prefix replay.
tags: [training, diagnostics, stability, regularization]
status: draft
last_updated: 2026-09-09
confidence: medium
---
# MLP Energy Replay Layer Diagnostics

Context: [training stability and shared-prefix replay](training-stability-jacobian-and-residual-scaling.md).
Full report: [layer diagnostics](../../../docs/xxl_mlp_energy_layer_analysis_20260909.md).
CPU extraction: `scripts/analyze_mlp_replay_layers.py`; artifact:
`checkpoints/experiments/xxl_mlp_shared_prefix_20260908/layer_analysis.json`.

Across 20 matched-schedule CE shadow probes per branch, L cycle-3 block-0
median residual RMS fell 65.32 to 16.86 while its incoming post-attention stream
RMS fell 1.546 to 1.251: actual numerator reduction, not evidence of denominator
inflation at that location. Its median backward RMS gain still remained 25.95
(baseline 44.31). Maximum recurrent gains remained substantial (regularized L
cycle-3: 198 at 453850; H cycle-0: 145 at 453900).

L cycle-3 block-5 worsened on several measures: median MLP residual RMS rose
97.11 to 313.42, sigmoid-gate fraction above 0.99 rose 2.39% to 82.58%, and
aligned Q/K score proxy RMS rose 279.45 to 728.20. This suggests possible
redistribution/compensation, not proof of causality or softmax entropy collapse.
Gate values are not attention probabilities, and the Q/K proxy is not the full
attention matrix. Attention entropy would require additional instrumentation.

Sampled grouped weight RMS changed only roughly +/-2%, whereas optimizer
moments changed much more. No sampled nonfinite values were observed. Actual
per-layer adaptive update/weight ratios remain unmeasured and are a useful
next diagnostic. Probe ratios are directional gradient observations, not
Jacobian spectral norms. The new coefficient replay should be judged on these
local/worst-case signals as well as loss, before changing production.

Follow-up proposals and alternatives to arithmetic averaging are recorded in
[regularization experiments from 453K](mlp-energy-regularization-experiments.md).
