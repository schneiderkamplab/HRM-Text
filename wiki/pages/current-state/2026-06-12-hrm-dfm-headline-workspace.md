---
type: Operational Record
title: 2026-06-12 HRM DFM Headline Workspace
description: 'Part of Current State: 2026-06-12 HRM DFM Headline Workspace.'
tags:
- operations
- training
- evaluation
- runtime
status: stable
last_updated: 2026-09-30
confidence: high
part_of: /pages/current-state.md
---
# 2026-06-12 HRM DFM Headline Workspace

## Semantic DALA Opt-In, 2026-09-30

The legacy average builders now recognize exact prefixes
`headline_avg_semantic_v1` and `suite_avg_semantic_v1`. Only these namespaces
replace strict Danish DALA membership with
`dfm_eval/dala/semantic_v1/macro_f1`. Danish and overall headline averages and
the DFM suite therefore use semantic acceptability; existing prefixes retain
strict membership and unchanged values. Superseding the initial partial-average
policy for semantic namespaces: missing or invalid semantic DALA suppresses
the Danish, overall and DFM-suite averages entirely, retaining coverage counts
and unaffected averages. It never substitutes strict DALA or silently reduces
the denominator of an affected average. Legacy partial-average behavior remains
unchanged.

For existing atomic-v3 scheduler jobs, keep `average_prefix=headline_avg_v3`
and `atomic_v3_averages=true`, and opt in with
`extra_average_prefixes=[headline_avg_semantic_v1,suite_avg_semantic_v1]`.
Both new namespaces are explicitly registered and committed together with the
unchanged legacy v3 row. Non-atomic jobs may use either new prefix directly
with the existing `average_scope`. No scheduler runtime change is required.
The chosen additive-plan integration instead uses separate clones with
`average_prefix=headline_avg_semantic_v1`,
`extra_average_prefixes=[suite_avg_semantic_v1]`,
`atomic_v3_averages=false`, `average_scope=all`, and `--averages-only` (already
supplied by the scheduler runtime). This emits only new semantic namespaces:
headline sections/overall under the headline prefix and suites under the suite
prefix, with no raw metrics or legacy average keys. Existing v3 jobs remain
unchanged. The exact clone path is covered by a fake-W&B regression test.
Implementation tests use a fake W&B module only; no live plan, population
registry, manifest or W&B data was changed for this addition.

Part of [Current State](/pages/current-state.md).

Confidence: high for saved W&B view creation and local manifest.

Superseded: the first saved view used `eval/train_step` as x-axis. A second
view used `eval/epoch` but could still appear to show only the newest 10 panel
runs. A third view set panel `max_runs_to_show=50` but the run sidebar still
used the hidden W&B `runFeed.pageSize=10`, so only 10 run names were visible at
a time. The final corrected saved W&B project view uses three sections:
Danish, English, and Math & Code. It uses the common relogged `eval/epoch`
x-axis, sets `max_runs_to_show=50` on every panel, sets
`runFeed.pageSize=50`, and orders runs by ascending creation time.

```text
name: HRM DFM headline metrics
url:  https://wandb.ai/peter-sk-sdu/HRM%20DFM?nw=dzjdkrcni52
x:    eval/epoch
max:  50 runs per panel
feed: 50 runs in sidebar page
order: CreatedTimestamp ascending
```

The workspace is intentionally grouped by task/language area rather than by
old `standard` versus `dfm_eval` origin. GovReport is treated as an English
summarization metric. DROP is treated as English reading comprehension.
HumanEval, GSM8k, and MATH are placed in the Math & Code section. HumanEval uses the compatibility alias
`eval/humaneval/verify/accuracy`; local HumanEval scoring also had a canonical
`verify_sanitized` key before aliasing.

Sections:

```text
Danish Headline Metrics:
  eval/dala/linguistic-acceptability/dfm_evals_macro_f1
  eval/danish-citizen-tests/knowledge/accuracy
  eval/gec_dala/exact_match/mean
  eval/generative-talemaader/model_graded_fact/accuracy
  eval/ifeval-da/instruction_following/final_acc
  eval/multi_wiki_qa/f1/mean
  eval/nordjyllandnews/rouge2/mean
  eval/piqa/piqa_scorer/accuracy
  eval/wmt24pp-en-da/chrf3pp/mean

English Headline Metrics:
  eval/ARC/acc
  eval/BoolQ/acc
  eval/DROP/f1
  eval/HellaSwag/acc
  eval/MMLU/acc
  eval/Winogrande/acc
  eval/govreport/rouge2/mean

Math & Code Headline Metrics:
  eval/GSM8k/acc
  eval/MATH/acc
  eval/humaneval/verify/accuracy
```

Script and manifest:

```text
scripts/create_hrm_dfm_headline_workspace.py
logs/wandb_workspace_specs/hrm_dfm_headline_metrics_by_language.json
logs/wandb_create_hrm_dfm_headline_workspace_20260612.log
logs/wandb_create_hrm_dfm_headline_workspace_epoch_axis_20260612.log
logs/wandb_create_hrm_dfm_headline_workspace_all_runs_20260612.log
logs/wandb_create_hrm_dfm_headline_workspace_pagesize_20260612.log
logs/wandb_create_hrm_dfm_headline_workspace_three_sections_20260612.log
logs/wandb_create_hrm_dfm_headline_workspace_two_sections_20260612.log
logs/wandb_create_hrm_dfm_headline_workspace_three_sections_final_20260612.log
logs/wandb_create_hrm_dfm_headline_workspace_drop_english_20260612.log
```

Visibility note verified on `2026-06-12`: W&B API lists
`original-sapient-L-full-ema` in project `HRM DFM` even if the saved
workspace run sidebar does not always show it clearly:

```text
run id:   original-sapient-L-full-ema
name:     original Sapient L full EMA
url:      https://wandb.ai/peter-sk-sdu/HRM%20DFM/runs/original-sapient-L-full-ema
state:    finished
created:  2026-06-12T09:22:52Z
```

The source is the old standard full-eval log root
`logs/eval/original_sapient_L/epoch_{1,2,3,4}.log`; the clean relog manifest
contains four checkpoints with 195 parsed metrics each. This run covers the
older English standard suite (`ARC`, `BoolQ`, `DROP`, `GSM8k`, `HellaSwag`,
`MATH`, `MMLU`, `Winogrande`). It does not populate GovReport, HumanEval, or
Danish headline panels. Separate original Sapient L Danish Inspect artifacts
exist under `logs/dfm_evals/original_sapient_L*`, but they were not ingested
into `HRM DFM` because those roots lack `merged*_metrics.json` files.
