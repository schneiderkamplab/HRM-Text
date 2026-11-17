# SimpleStories prose judge ensemble comparison

2026-10-28. Accept only when every selected judge accepts both language and coherence.

Manual labels were frozen before inspecting judge outputs. Clear defects, borderline cases, and clean texts are separated.

The fresh sample contains 200 unique parent conversations, one intact assistant text each: 50 Danish, English, Hindi and Japanese. It is drawn from previously conversation-approved candidates, not the raw generation population. The old 20 were selected among Odin accepts. Do not pool these cohorts.

This is assistant manual review, not native-speaker certification. Source fidelity, instruction compliance and whole-conversation consistency are outside scope.

## current: 20 texts

{'bad': 2, 'clear': 14, 'borderline': 4}

| Judges | Accepted | Clear defects passed | Clean texts rejected | Borderlines passed | Unresolved |
|---|---:|---:|---:|---:|---:|
| odin | 20 | 2/2 | 0/14 | 4/4 | 0 |
| qwen27b | 13 | 2/2 | 5/14 | 2/4 | 0 |
| flash | 17 | 1/2 | 1/14 | 3/4 | 0 |
| odin+qwen27b | 13 | 2/2 | 5/14 | 2/4 | 0 |
| odin+flash | 17 | 1/2 | 1/14 | 3/4 | 0 |
| qwen27b+flash | 12 | 1/2 | 5/14 | 2/4 | 0 |
| odin+qwen27b+flash | 12 | 1/2 | 5/14 | 2/4 | 0 |

### Defects missed by all three

- C019 (ja): See prior accepted-text review.
## holdout: 200 texts

{'bad': 40, 'clear': 134, 'borderline': 26}

| Judges | Accepted | Clear defects passed | Clean texts rejected | Borderlines passed | Unresolved |
|---|---:|---:|---:|---:|---:|
| odin | 179 | 25/40 | 1/134 | 21/26 | 0 |
| qwen27b | 121 | 22/40 | 53/134 | 18/26 | 0 |
| flash | 164 | 20/40 | 10/134 | 20/26 | 0 |
| odin+qwen27b | 113 | 16/40 | 53/134 | 16/26 | 0 |
| odin+flash | 159 | 17/40 | 10/134 | 18/26 | 0 |
| qwen27b+flash | 104 | 11/40 | 57/134 | 16/26 | 0 |
| odin+qwen27b+flash | 102 | 10/40 | 57/134 | 15/26 | 0 |

### Defects missed by all three

- H003 (da): "Spøgelsen" should be "spøgelset".
- H007 (da): "lyset ... begyndte ... at dæmpe" missing required passive/reflexive construction.
- H027 (da): "venskab ... evig" lacks neuter agreement.
- H124 (hi): Curiosity is described as failing to prevent exploration, reversing its intended causal role.
- H127 (hi): "उस पल को" and "वह गलती ... जो मैं डर रहा था" malformed constructions.
- H128 (hi): "रसोई की काउंटर" wrong possessive agreement.
- H137 (hi): Clock-tower gender construction and corrupted "खाली हाँ" for empty-handed.
- H155 (ja): "彼の手は ... 磨かれていた" says his hands were polished, not the window he cleans.
- H176 (ja): Announced sweetness comparison is actually an expiry warning; action connection breaks.
- H190 (ja): "たとえ相手がバケツを宇宙服だとしても" is a malformed construction.

## Interpretation and reproducibility

An intersection mechanically cannot admit more bad texts than its constituent judges on the same fixed votes; the relevant question is how much it catches versus how many clean texts it loses. These judges share blind spots; Flash also generated this corpus, so errors are correlated.

Borderlines are excluded from both clear-defect and clean-text denominators. Their accepted count provides a sensitivity bound if a stricter policy considers them defective. Missing/invalid votes never count as accepts.

Remote Odin used concurrency 64; HTTP dispatch was reduced to 90 per 61 seconds after account 429 responses, below the 180/minute cap. Local judges used concurrency 128, non-thinking yes/no. No production admission policy or datasets were changed.

Manual label SHA256: `c121d7df6e67632bad81d8b72ac2fabd7034b2204adc46bb53a4285fb6e85fc0`.

Frozen inputs, raw audit journals, per-text votes and machine-readable summary: `data/dfm16/expansion-v1/stories/quality-v3-qwen/ensemble-study`.

Reproduce aggregation: `python -m scripts.analyze_dfm16_judge_ensemble`.

[Manual labels and explanations](odin-ensemble-manual-200-20261028.md).
