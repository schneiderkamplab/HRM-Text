---
type: Research
title: Baltic 31B Fresh Twelve Review
description: Independent full-content comparison of twelve fresh 31B Baltic examples with their historical 26B counterparts.
status: draft
confidence: medium
last_updated: 2026-10-03
tags: [dfm13, baltic, quality, synthetic]
---
# Baltic 31B Fresh Twelve Review

## Model Selection Scope

As clarified on 2026-10-03, these are bounded diagnostic comparisons, not
authorization to replace Gemma 4 26B-A4B as the bulk generation/audit model.
The reviewed evidence does not establish that 31B resolves the content defects.
Keep prompt, source-preservation and validation fixes model-independent; reserve
31B for targeted work with demonstrated benefit. The completed capacity test
`data/dfm13/gemma31-capacity-measurement-20261003-v1/measurement.json`
reports no request errors, OOMs or preemptions, but explicitly grants neither
capacity approval nor publication approval. Operational success is not a quality
verdict. Existing comparison outputs remain preserved for diagnosis.

CPU review of all12 cases in `data/dfm13/baltic/gemma31-fresh-comparison12-v3`
found2 good,4 partial and6 materially defective whole examples. These manual
categories include user text; they are not population estimates or admission.
Operational9 valid/5 automated keeps/3 invalid remains unchanged.

LT multi-turn grounding improved; both story translations remain defective.
LV math's correct boxed answer masks a garbled generated prompt. Numeric answers
and tool-call structures are CPU-assembled, so they do not demonstrate autonomous
model arithmetic/tool generation. Both mock-tool final answers are grounded;
LV has limited grammar regression. Three length failures copied source despite
an explicit prohibition and also have content concerns, not clean schema-only
false rejections. Some judge explanations contain unsupported translations or
date assumptions; conclusions are based on direct source/candidate reading.

The [full report](../../docs/reports/baltic-gemma31-fresh12-review-20261003/report.md)
contains all case IDs, exact evidence, comparison caveats and hash pins. Native
fluency is not certified. No source/outcome mutation, GPU call or automatic
approval occurred; the balanced234 run is separate.

## Balanced Accepted Extension

All10 Baltic automated keeps in grounded-instruct, summary-rewrite and multi-turn
from `gemma31-balanced-execution-20261003-v2/baltic` were independently read against
their sources (18 assistant turns). Disposition:6 good,3 partial,1 moderate-confidence
prompt-framing concern: LV funding culture versus cultural-sector financing.
Seven single-turn cases duplicate source text, a preparation/instruction defect,
not seven factual hallucinations. Most assistant content remains source-faithful;
minor grammar is distinguished from material issues. Other families belong to
Poincare. See the [casewise extension](../../docs/reports/baltic-gemma31-fresh12-review-20261003/balanced-accepted-review.md)
and its hash receipt. No calibration changes or automatic approval were made.
