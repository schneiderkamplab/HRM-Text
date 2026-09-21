---
type: Plan Record
title: Current DFM6 Evaluation Contract
description: 'Part of DFM6 Plan: Current DFM6 Evaluation Contract.'
tags:
- dfm6
- data
- training
- evaluation
status: stable
last_updated: 2026-09-21
confidence: high
part_of: /pages/dfm6-plan.md
---
# Current DFM6 Evaluation Contract

## Regex patch mismatch discovered 2026-09-21

Supersedes the June claim below that enabling `fix_mistral_regex` ensures
the intended training tokenization. It changes token IDs relative to the
actual raw Gemma tokenizer used by our data-preparation path. Do not infer
train/eval parity merely from this flag being present or the warning disappearing.

`scripts/tokenize_chat_template.py` loads `tokenizers.Tokenizer.from_file`
directly; DFM10/11 metadata names
`/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json`. Training reads
precomputed `tokens.npy`, not AutoTokenizer. The raw pre-tokenizer is a
space Split with MergedWithPrevious behavior, with no Mistral regex patch.
Conversely, `conversion/convert_to_hf.py` persists `fix_mistral_regex=true`.
The current 450K DFM11 XXL-wide export and XL 1650K export contain that flag.
Loading through hrm Transformers 5.12.1 inserts an additional regex Split.

CPU-only verification, no special tokens, input `Hello, world!  Test\nNext.`:
raw training tokenizer IDs were
`[9259,236764,1902,236888,138,3694,107,9272,236761]`;
patched export IDs were
`[9259,236764,236743,12392,236888,138,3694,107,9272,236761]`.
The latter also appeared using brainsurgery Transformers 5.10.0.dev0 on
the locally cached `schneiderkamplab/HRM-Mimir-v1` used by HRM-test and on
the local XL 1650K export. HRM-test's per-model server launcher does not
override the tokenizer. This confirms a training-versus-evaluation mismatch
for these Gemma-based checkpoints, but does not quantify metric impact.
Other HRM-test models may use different tokenizer settings.
No tokenizer files, training data, exports, evaluations, or model code were changed.

Part of [DFM6 Plan](/pages/dfm6-plan.md).

Last updated: 2026-06-24
Confidence: high
Scope: The current scheduler/evaluation convention for DFM6 checkpoint sweeps.

DFM6 checkpoint evaluations are scheduled through `eval_scheduler` as a DAG per
checkpoint. The intended checkpoint order is independent: a single scheduler
plan may contain multiple checkpoint subgraphs, each guarded by its own
`wait_checkpoint` row and using distinct export/log roots and port bases.

Per checkpoint, the sequence is:

1. `wait_checkpoint`: wait until `model_<tag>.safetensors` and all expected
   `carry_<tag>.<rank>.pt` files exist.
2. `export_hf`: export the EMA checkpoint to an HF/vLLM directory.
3. Run standard eval shards, DFM eval shards, DFM IFEval-DA shards, and
   EuroEval tasks. These can run as soon as the export is ready.
4. Merge rows run per task as soon as that task's shards are done.
5. Suite averages run as soon as their suite is complete:
   `standard-average`, `dfm-average`, and `euroeval-average` log to
   `suite_avg_v2/*`.
6. Section averages run as soon as their section producers are complete:
   `danish-average`, `english-average`, and `math-code-average` log to
   `headline_avg_v2/*`.
7. `headline-averages` logs `headline_avg_v2/overall` only after the three
   section averages and three suite averages are done.
8. The report job waits for `headline-averages`.

W&B x-axis policy:

- Raw standard metrics use the raw eval namespace, with `eval/epoch` and
  `eval/train_step` present.
- Raw DFM metrics use `dfm_eval/epoch` and `dfm_eval/train_step`.
- Raw EuroEval metrics use `euroeval/epoch` and `euroeval/train_step`.
- Clean section/headline averages use `headline_avg_v2/epoch` as the W&B step
  metric.
- Clean suite averages use `suite_avg_v2/epoch` as the W&B step metric.
- The old `avg/*`, `headline_avg/*`, and `suite_avg/*` namespaces are stale for
  DFM6 reporting and should not be used in panels.

Current vLLM/GPU settings while co-running with DFM6 XL-GAS2 training:

```text
standard_engine_backend: vllm
hrm_server_backend: vllm
hrm_vllm_native_proxy: true
hrm_vllm_gemma_bfcl_tools: true
hrm_vllm_gemma_bfcl_tool_mode: parser
vllm_extra_args: --enforce-eager --attention-backend FLASH_ATTN --chat-template /work/dfm/HRM-Text/evaluation/chat_templates/gemma4_native_chat.jinja
vllm_gpu_memory_utilization: 0.28
standard_batch: 64
dfm_batch: 32
ifeval_batch: 32
euroeval_batch: 32
euroeval_max_concurrent_calls: 32
judged_batch: 16
judged_max_connections: 16
judge_model: openai/gemma-4-e4b-judge
judge_server_model: unsloth/gemma-4-E4B-it
judged_vllm_gpu_memory_utilization: 0.18
govreport_max_report_chars: 9000
max_retries: 5
fixed_retry_batch: true
```

`generative_talemaader` is the only current task that starts a colocated local
judge server. Its batch and max-connections remain `16`; the working fix for
judge startup OOM is lowering only the judged-task HRM vLLM memory utilization
to `0.18`.

Known skip:

- `valeu-da` is marked `skipped` in DFM6 sweeps because the current EuroEval
  task can abort the whole run on invalid labels. It is excluded from
  `suite_avg_v2/euroeval` and `headline_avg_v2/danish`.

Update, 2026-06-23. Confidence: high from local plan inspection. A single
multi-checkpoint campaign plan was created for the next five 50K-spaced
checkpoints:

```text
plan_dir: logs/scheduler/dfm6_XL_gas2_steps300k_500k_vllm_main_20260623
checkpoints: step_300000, step_350000, step_400000, step_450000, step_500000
eval_epochs: 1.2518828862576779, 1.4605300339672909, 1.6691771816769039,
             1.8778243293865167, 2.0864714770961296
status after creation: pending=1080, skipped=5, total=1085
skipped rows: one valeu-da row per checkpoint
```

The plan validation showed `generative_talemaader` rows with
`initial_batch=16`, `max_connections=16`,
`vllm_gpu_memory_utilization=0.18`, and `fixed_retry_batch=true`. The average
rows use `suite_avg_v2` for suite averages and `headline_avg_v2` for section
and overall averages, with `headline-averages` depending on the six prior
average rows.

The campaign scheduler was launched in tmux:

```text
runner:  hrm-0:8  evald6x300500
monitor: hrm-0:9  mond6x300500
```

Initial live monitor state after launch: `done=0`, `running=4`, `ready=1`,
`blocked_pending=1075`, `failed=0`, `skipped=5`, `total=1085`. The running
jobs are checkpoint waits, not GPU eval jobs; at launch the local checkpoint
directories for `step_300000` through `step_500000` were not yet present.

Update, 2026-06-24. Confidence: high from local scheduler logs, plan state,
and code inspection. The 300K eval itself did not fail: `step_300000` exported
successfully at `2026-06-24T02:25:47+02:00`, all eval shards completed, and
the plan had no failed jobs. Progress stopped after the last 300K DFM eval
ended at `2026-06-24T04:05:27+02:00` because the scheduler's four generic
non-GPU slots were occupied by long-running future `wait_checkpoint` jobs for
350K, 400K, 450K, and 500K. Ready 300K merge/average rows also require
non-GPU slots, so they were starved behind sleeping checkpoint waits.

The runner process also left no normal `RUN_END`, `BLOCKED`, `STOPPED`, or
traceback entry at that time, so an exact process-exit reason was not recorded.
To prevent both problems going forward:

- `eval_scheduler/eval_scheduler/runtime.py` now gives `WAIT_CHECKPOINT` jobs
  their own checkpoint-wait slot pool
  (`EVAL_SCHEDULER_CHECKPOINT_WAIT_SLOTS`, default `8`) instead of consuming
  the generic merge/average/report non-GPU slots.
- Unexpected worker exceptions are now logged as `RUN_EXCEPTION <job_id> ...`
  in `status.tsv` and mark the affected job failed instead of taking down the
  whole runner and leaving stale `running` rows.

Operational repair performed on 2026-06-24:

```bash
cd /work/dfm/HRM-Text
/home/ucloud/miniforge3/envs/hrm/bin/python -m eval_scheduler plan reset-running \
  --plan-dir logs/scheduler/dfm6_XL_gas2_steps300k_500k_vllm_main_20260623

/home/ucloud/miniforge3/envs/hrm/bin/python -m eval_scheduler stop \
  --plan-dir logs/scheduler/dfm6_XL_gas2_steps300k_500k_vllm_main_20260623
```

The runner was then relaunched in `hrm-0:8` with the patched runtime. Verified
live state after relaunch: `done=216`, `running=4`, `ready=0`,
`blocked_pending=860`, `failed=0`, `skipped=5`, where the four running jobs
are checkpoint waits for 350K through 500K. 300K is complete through its report
row.

Update, 2026-06-24. Confidence: high from local config, export, and eval-log
inspection. DFM6 standard, DFM, and EuroEval vLLM evaluations are intended to
use the Gemma-native chat template consistently:

- Standard vLLM evals use `evaluation/config/dfm6_vllm_benchmarking.yaml`,
  `prompt_mode: gemma_chat`, and
  `evaluation/chat_templates/gemma4_native_chat.jinja`.
- DFM/EuroEval vLLM server jobs launch vLLM with
  `--chat-template /work/dfm/HRM-Text/evaluation/chat_templates/gemma4_native_chat.jinja`.
- `evaluation/chat_templates/gemma4_native_chat.jinja` and
  `data_io/chat_templates/gemma4_native_chat.jinja` are byte-identical
  (`sha256=33204f1acb5bd0002713e16a593847f24ceeafe711ed88bda2a352dc996a3373`).

However, the DFM6 HF export currently lacks usable EOS metadata for the Gemma
turn-end token. For `exports/dfm6_XL_gas2_step_300000_ema_hf`, Transformers
reports `eos_token=None`, while the Gemma tokenizer maps `<turn|>` to token id
`106`. The DFM6 training tokenizer path renders full assistant targets with
the assistant content followed by `<turn|>`, but vLLM is not automatically
stopping at token `106` unless the request/export supplies it as a stop token.

Observed symptom at 300K:

- DROP is a real low score, not a missing metric: `eval/DROP/f1=0.086625`
  versus DFM5-L 300K `eval/DROP/f1=0.74645`.
- DFM MultiWikiQA 300K has `f1/mean=0.354059...` but
  `exact_match/mean=0.000488...`.
- Raw MultiWikiQA predictions often start with the right short answer but then
  continue with newline-separated junk or alternative answers until
  `max_gen_toks=32`; nearly every sampled 300K MultiWikiQA output contained a
  newline. DFM5-L on the same samples usually stopped after the short answer.

Interpretation: the bad short-answer/extractive scores are not strong evidence
that the model cannot read the prompt or that the Gemma template is missing.
They are at least partly a serving/export stopping issue. Multiple-choice tasks
are less sensitive to this because their scoring usually extracts a choice,
whereas DROP and MultiWikiQA exact/F1 are punished heavily by trailing text.

Next fix to test: make the DFM6 HF export and/or eval server requests treat
`<turn|>` token id `106` as the generation stop token, and rerun a small
DROP/MultiWikiQA smoke with saved generations before relogging full metrics.

Fix applied later on 2026-06-24. Confidence: high from local file edits and
export verification.

- `conversion/convert_to_hf.py` now recognizes DFM6/Gemma
  `template_mode: jinja_chat_template` metadata and writes
  `bos_token_id=2`, `eos_token_id=106`, and `pad_token_id=0` into
  `config.json`.
- The same converter now sets tokenizer special tokens to `<bos>`, `<turn|>`,
  and `<pad>`, and carries the configured Jinja chat template into the exported
  tokenizer when the template path is available.
- `evaluation/config/dfm6_vllm_benchmarking.yaml` now also passes
  `generation_config.stop_token_ids: [106]` so standard offline vLLM evals stop
  at Gemma `<turn|>` even if an old export is accidentally used.
- Existing local DFM6 exports for `step_50000`, `step_100000`, `step_150000`,
  `step_200000`, `step_250000`, and `step_300000` were refreshed with
  `conversion/convert_to_hf.py --config-only`; model weights were not rewritten.

Verification:

```text
AutoTokenizer.from_pretrained("exports/dfm6_XL_gas2_step_300000_ema_hf"):
  bos <bos> 2
  eos <turn|> 106
  pad <pad> 0
  chat_template True
config.json:
  bos_token_id 2
  eos_token_id 106
  pad_token_id 0
```

Affected-eval assessment:

- Highest-risk already-logged DFM6 metrics: tasks whose scorer consumes the
  full generated string or exact short answer, especially DROP, DFM
  MultiWikiQA, EuroEval `multi-wiki-qa-da`, EuroEval SQuAD-like reading
  comprehension, DFM/standard GovReport, DFM/standard NordjyllandNews, WMT24++
  en-da, GEC DALA, HumanEval/code generation, and other generative EuroEval
  summarization/QA tasks.
- Lower-risk but still exposed: single-label/classification/MCQ tasks such as
  MMLU, ARC, HellaSwag, Winogrande, BoolQ, PIQA, Danish citizen tests, DALA,
  and sentiment/NER-style EuroEval tasks. These usually use one-token outputs
  or label extraction, so missing EOS is less likely to dominate the score.

Additional export/eval fix on 2026-06-24. Confidence: high from local command
output and smoke tests. Transformers warned that the exported Gemma tokenizer
needed `fix_mistral_regex=True`; loading with and without the flag produced
different token IDs for a punctuation/spacing smoke string. `conversion/convert_to_hf.py`
now persists `fix_mistral_regex: true` into DFM6
`tokenizer_config.json` for `template_mode: jinja_chat_template` exports. The
existing 300K HF export was refreshed with:

```bash
cd /work/dfm/HRM-Text
/home/ucloud/miniforge3/envs/hrm/bin/python conversion/convert_to_hf.py \
  --ckpt_path checkpoints/dfm6/XL-gas2 \
  --ckpt_tag step_300000 \
  --ckpt_use_ema true \
  --out_dir exports/dfm6_XL_gas2_step_300000_ema_hf \
  --config-only
```

Verification after refresh:

```text
AutoTokenizer.from_pretrained("exports/dfm6_XL_gas2_step_300000_ema_hf"):
  bos_token_id=2 eos_token_id=106 pad_token_id=0 fix_mistral_regex=True
```

DFM6 eval contract smoke, 2026-06-24. Confidence: high from local smoke output.
Added `scripts/smoke_dfm6_eval_contracts.py`. It checks, before a full eval:

- exported tokenizer/config metadata: BOS `2`, EOS `<turn|>` id `106`, PAD
  `0`, `fix_mistral_regex=True`, and a present chat template;
- byte-identical eval/data Gemma templates and a rendered prompt ending at the
  `<|turn>model` generation marker;
- standard task set and task-specific generation limits in
  `evaluation/config/dfm6_vllm_benchmarking.yaml`;
- DFM task configs, DFM IFEval 32-shard config, GovReport truncation, and
  judged Talemaader settings;
- full scheduler plan contract for standard, DFM, and EuroEval jobs using vLLM,
  native proxy, Gemma BFCL parser mode, FlashAttention, EuroEval concurrency
  `32`, and the new `suite_avg_v2`/`headline_avg_v2` dependency ordering.

Smoke command:

```bash
cd /work/dfm/HRM-Text
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/smoke_dfm6_eval_contracts.py
```

Latest passing output:

```text
DFM6 eval smoke passed. Wrote /work/dfm/HRM-Text/logs/smoke/dfm6_eval_contracts_20260624_080712.json
Standard tasks: 10
DFM tasks: 10 + 32 IFEval shards
EuroEval groups: 20 (valeu-da skipped by plan)
```

Clean 300K stop-fix evaluation launch, 2026-06-24. Confidence: high from
created plan, spot-checked metadata, and live scheduler status. A separate
300K eval was launched into its own W&B run in project `DFM5`, leaving prior
possibly affected 300K metrics untouched:

```text
plan_dir:  logs/scheduler/dfm6_XL_gas2_step300000_stopfix_clean_20260624
standard:  logs/eval/dfm6_XL_gas2_step300000_stopfix_clean_20260624
dfm:       logs/dfm_evals/dfm6_XL_gas2_step300000_stopfix_clean_20260624
euroeval:  logs/euroeval/dfm6_XL_gas2_step300000_stopfix_clean_20260624
wandb:     project=DFM5 run_id=dfm6-xl-gas2-300k-stopfix-clean-20260624
tmux:      hrm-0:10 eval300stopfix, hrm-0:11 mon300stopfix
```

The plan has `216` pending rows plus one skipped `valeu-da` row at creation:
`85` standard shards, `51` DFM shards, `32` DFM IFEval shards, `20` EuroEval
rows including two batched IFEval rows, merges, suite averages, section
averages, overall headline average, and report generation. At startup,
checkpoint wait and HF export completed immediately, then the first eight
EuroEval jobs started with batch `32` and no failures.

Clean 300K stop-fix W&B repair, 2026-06-24. Confidence: high from local
scheduler status, merged metric files, and W&B API history queries. Supersedes
the earlier same-day diagnosis that focused on train-step axes. The DFM5
workspace eval and average panels use epoch axes, so `*/epoch` must remain the
canonical W&B step metric. `*/train_step` is useful metadata, but must not
replace `*/epoch` as the default metric axis. The
`dfm6-XL-gas2 300K stopfix clean eval` scheduler finished cleanly:
`done=216`, `failed=0`, `skipped=1`. Missing W&B chart points for Danish
headline average, GEC DaLA exact match, EuroEval ScaLA-da macro F1, and BoolQ
accuracy were not missing local eval results. They were W&B history-row issues:
some repair attempts updated summary values or axis-only rows without creating
plottable rows containing both the metric value and the relevant `*/epoch`.

Local verified values:

```text
headline_avg_v2/danish = 0.5102304507375527
dfm_eval/gec_dala/exact_match/mean = 0.4345703125
euroeval/da/linguistic-acceptability/scala-da/macro_f1 = 51.702315412643784
eval/BoolQ/acc = 0.8495
```

The 300K clean run was repaired with:

```bash
cd /work/dfm/HRM-Text
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/backfill_external_eval_to_wandb.py \
  --project DFM5 \
  --run-id dfm6-xl-gas2-300k-stopfix-clean-20260624 \
  --run-name 'dfm6-XL-gas2 300K stopfix clean eval' \
  --standard-root logs/eval/dfm6_XL_gas2_step300000_stopfix_clean_20260624 \
  --dfm-root logs/dfm_evals/dfm6_XL_gas2_step300000_stopfix_clean_20260624 \
  --euroeval-root logs/euroeval/dfm6_XL_gas2_step300000_stopfix_clean_20260624/step_300000 \
  --epoch 1.2518828862576779 \
  --step 300000

/home/ucloud/miniforge3/envs/hrm/bin/python scripts/backfill_external_eval_to_wandb.py \
  --project DFM5 \
  --run-id dfm6-xl-gas2-300k-stopfix-clean-20260624 \
  --run-name 'dfm6-XL-gas2 300K stopfix clean eval' \
  --standard-root logs/eval/dfm6_XL_gas2_step300000_stopfix_clean_20260624 \
  --dfm-root logs/dfm_evals/dfm6_XL_gas2_step300000_stopfix_clean_20260624 \
  --euroeval-root logs/euroeval/dfm6_XL_gas2_step300000_stopfix_clean_20260624/step_300000 \
  --epoch 1.2518828862576779 \
  --step 300000 \
  --log-averages \
  --averages-only \
  --average-prefix headline_avg_v2 \
  --average-scope sections

/home/ucloud/miniforge3/envs/hrm/bin/python scripts/backfill_external_eval_to_wandb.py \
  --project DFM5 \
  --run-id dfm6-xl-gas2-300k-stopfix-clean-20260624 \
  --run-name 'dfm6-XL-gas2 300K stopfix clean eval' \
  --standard-root logs/eval/dfm6_XL_gas2_step300000_stopfix_clean_20260624 \
  --dfm-root logs/dfm_evals/dfm6_XL_gas2_step300000_stopfix_clean_20260624 \
  --euroeval-root logs/euroeval/dfm6_XL_gas2_step300000_stopfix_clean_20260624/step_300000 \
  --epoch 1.2518828862576779 \
  --step 300000 \
  --log-averages \
  --averages-only \
  --average-prefix suite_avg_v2 \
  --average-scope suites
```

Future-proofing patch, 2026-06-24. Confidence: high from local `py_compile`
and `bash -n` validation. The merge/log path now carries explicit train-step
metadata while keeping epoch as the canonical W&B plotting axis:

- `scripts/merge_standard_eval_shards.py` accepts `--step`, logs
  `eval/train_step`, and still defines raw `eval/*` metrics against
  `eval/epoch`.
- `scripts/merge_dfm_eval_shards.py` accepts `--step`, logs
  `dfm_eval/train_step`, and still defines raw `dfm_eval/*` metrics against
  `dfm_eval/epoch`.
- `scripts/merge_ifeval_da_shards.py` accepts `--step`, logs
  `dfm_eval/train_step`, and still defines raw DFM IFEval metrics against
  `dfm_eval/epoch`.
- `scripts/log_euroeval_to_wandb.py` accepts `--step`, logs
  `euroeval/train_step`, and still defines EuroEval metrics against
  `euroeval/epoch`.
- `eval_scheduler/eval_scheduler/runtime.py` infers the eval step from
  `metadata.eval_step` or `ckpt_tag=step_N` and passes it to all merge/log
  jobs, including shell-run EuroEval jobs through `EVAL_STEP`.
- `scripts/run_euroeval_on_checkpoint.sh` and
  `scripts/run_batched_ifeval_on_checkpoint.sh` pass `EVAL_STEP` through to
  `log_euroeval_to_wandb.py`.

Manual 300K stop-fix repair rows, 2026-06-24. Confidence: high from W&B API
`scan_history`. The four missing panels were repaired by appending small,
explicit epoch-based rows to run
`dfm6-xl-gas2-300k-stopfix-clean-20260624`. W&B history now contains rows with
the metric and its epoch:

```text
eval/BoolQ/acc + eval/epoch
dfm_eval/gec_dala/exact_match/mean + dfm_eval/epoch
euroeval/da/linguistic-acceptability/scala-da/macro_f1 + euroeval/epoch
headline_avg_v2/danish + headline_avg_v2/epoch
```

Clean 300K BFCL and Talemaader diagnosis, 2026-06-24. Confidence: high for
local metric values and logs; medium for capability interpretation. The low
BFCL-v2 score is not currently an obvious scheduler/proxy failure. The
EuroEval BFCL job used the vLLM native proxy with Gemma-native BFCL tools
enabled. `proxy_payloads.jsonl` showed 257 requests, 242 adapted responses,
and many requests with OpenAI tool schemas. The merged metric was:

```text
euroeval/en/tool-calling/bfcl-v2/tool_calling_accuracy = 0.92
```

EuroEval reports this on its usual 0-100 scale, so this is about `0.92%`.
There were no failed instances in `raw_results`. The likely cause is model
capability at 300K: BFCL requires exact function choice, JSON argument
extraction, and sometimes multi-call planning. Earlier smoke tests showed the
parser route can choose a function but may produce empty or incomplete args.

Talemaader was also locally complete but scored:

```text
dfm_eval/generative-talemaader/model_graded_fact/accuracy = 0.0
```

The 808 outputs were fluent Danish but often literal, generic, or only
partially correct idiom explanations. Example failure modes included treating
`være høj i hatten` as literally high/proud, explaining
`danse efter nogens pibe` as merely following an example, and giving vague
paraphrases. Some near-correct answers, such as `der er ugler i mosen`, may be
judge false negatives because the model judge is strict, but the sample review
does not support a pure judging/plumbing explanation for `0/808`.

DFM6 XL-GAS2 clean stop-fix backfill scheduler, 2026-06-24. Confidence: high
from local scheduler status and inspected `plan.tsv` metadata. The active
main-run 300K-500K scheduler was stopped so earlier DFM6 checkpoints could be
evaluated into the clean stop-fix W&B run
`dfm6-xl-gas2-300k-stopfix-clean-20260624`. A first combined 50K-500K plan was
discarded because 300K had an existing HF export and began running immediately,
which did not match the intended prepend semantics. The corrected plan excludes
300K, since the clean 300K eval already exists, and schedules:

```text
50K, 100K, 150K, 200K, 250K, then 350K, 400K, 450K, 500K
```

Plan directory:

```text
logs/scheduler/dfm6_XL_gas2_steps50k_250k_then350k_500k_stopfix_clean_20260624
```

The later checkpoint waits for 350K-500K are explicitly gated on
`report-01085`, the 250K report job, so the prepended 50K-250K evals finish
before the remaining later checkpoints start. The plan logs to the clean run
and uses the established DFM6 vLLM settings: `vllm_gpu_memory_utilization=0.28`,
EuroEval batch/concurrency `32`, Gemma-native BFCL tool parser mode enabled,
ValEU-da skipped, `govreport_max_report_chars=9000`, and epoch-based W&B axes
with `train_step` as auxiliary metadata.

Launch commands:

```bash
cd /work/dfm/HRM-Text
/home/ucloud/miniforge3/envs/hrm/bin/python -m eval_scheduler run \
  --plan-dir logs/scheduler/dfm6_XL_gas2_steps50k_250k_then350k_500k_stopfix_clean_20260624 \
  --gpus 0,1,2,3,4,5,6,7

/home/ucloud/miniforge3/envs/hrm/bin/python -m eval_scheduler monitor \
  --plan-dir logs/scheduler/dfm6_XL_gas2_steps50k_250k_then350k_500k_stopfix_clean_20260624 \
  --gpus 0,1,2,3,4,5,6,7 \
  --interval 30
```

As launched, the scheduler is in tmux pane `hrm-0:8` and the monitor in
`hrm-0:9`. Initial status after launch was `pending=1926`, `running=8`,
`done=10`, `failed=0`, `skipped=9`, with the first 50K EuroEval wave active.

DFM6 judged-task scheduler trap, 2026-06-24. Confidence: high from
`dfm-evals.log` tracebacks and inspected plan metadata. The 50K-250K then
350K-500K clean backfill scheduler exited with `RUN_END` because it reached a
blocked state, not because the scheduler process crashed. All `40` failures
were `generative_talemaader` shards for 50K, 100K, 150K, 200K, and 250K after
retries. The common traceback was:

```text
ValueError: Placeholder `{{judge_model}}` in `tasks[0].args[1]` for suite
`hrm_danish_generative_talemaader` requires `--judge-model`.
```

Root cause: the replacement plan was created without the known-good judged
task settings. For DFM6 plans that include `generative_talemaader`, always pass
the judge settings at plan creation time:

```bash
--judge-model openai/gemma-4-e4b-judge \
--judge-server-model unsloth/gemma-4-E4B-it \
--judge-server-dtype bfloat16 \
--judge-server-attn-implementation sdpa \
--judge-server-max-new-tokens 64 \
--judged-batch 16 \
--judged-vllm-gpu-memory-utilization 0.18
```

These match the working 300K stop-fix plan. Do not rely on scheduler defaults
for this: `runtime.py` has a fallback judge model for some code paths, but
`dfm-evals` suite placeholder resolution requires an explicit `judge_model` in
the job metadata before the eval command starts.

Superseded 2026-06-27: older notes said to use `--judged-batch none` and
`--judged-vllm-gpu-memory-utilization none`. The current CLI rejects
`--judged-batch none`; local inspection of the successful `step_500000`
Talemaader rows showed the actual working values were batch `16` and
per-judged-task vLLM utilization `0.18`. Use those explicit values for future
DFM6 plans. Confidence: high from the successful 500K plan metadata and the
failed local CLI invocation.

The live plan was repaired in place by patching every
`family=dfm`, `name=generative_talemaader`, `action=eval_dfm` row to include:

```json
{
  "judge_model": "openai/gemma-4-e4b-judge",
  "judge_server_model": "unsloth/gemma-4-E4B-it",
  "judge_server_dtype": "bfloat16",
  "judge_server_attn_implementation": "sdpa",
  "judge_server_max_new_tokens": 64
}
```

Then only the failed Talemaader rows were reset to `pending` with `attempt=0`.
The repair backup is:

```text
logs/scheduler/dfm6_XL_gas2_steps50k_250k_then350k_500k_stopfix_clean_20260624/plan.tsv.bak_judge_fix_20260624
```

After the repair, status was `done=1015`, `pending=929`, `failed=0`,
`skipped=9`, and all Talemaader eval rows had explicit judge metadata.

Evaluation startup-overhead analysis, 2026-06-26. Confidence: high from local
`plan.tsv`, `status.tsv`, and per-job eval logs for the clean stopfix scheduler.
The last three completed full evaluations in
`logs/scheduler/dfm6_XL_gas2_steps50k_250k_then350k_500k_stopfix_clean_20260624`
were `step_350000`, `step_400000`, and `step_450000`. A common-denominator
per-job aggregation across `standard`, `dfm`, and `euroeval` jobs was written to:

```text
logs/analysis/eval_startup_common_last3_dfm6_stopfix.csv
logs/analysis/eval_startup_common_last3_dfm6_stopfix_summary.tsv
```

The aggregation uses scheduler START/END as the common duration source and a
best-effort startup proxy from scheduler START to first observable vLLM
generation/API work. DFM and EuroEval server jobs have explicit lifecycle
markers; standard eval jobs use in-process vLLM markers, so this is suitable
for comparative bottleneck analysis but should not be treated as a perfect
server-ready metric.

Observed post-export full-eval wall time was stable: `step_350000` took about
`76.3` minutes, `step_400000` about `75.3` minutes, and `step_450000` about
`75.5` minutes. Per checkpoint, standard evals span about `46` minutes, DFM
evals about `70` minutes, and EuroEval about `11` minutes, with suites
overlapping under the scheduler. Startup/load overhead is a large fraction of
many short DFM and EuroEval jobs, but MATH dominates total standard GPU time
despite lower per-job startup fraction.

DFM6 XL-GAS2 550K/600K eval scheduler, 2026-06-27. Confidence: high from local
plan creation and scheduler status. Server reuse was considered but not pursued
because the expected wall-clock saving was only about `8-12` minutes per
checkpoint. A separate scheduler plan was created for `step_550000` and
`step_600000` using the same clean DFM6 vLLM settings as the completed 500K
run.

Plan directory:

```text
logs/scheduler/dfm6_XL_gas2_steps550k_600k_stopfix_clean_20260627
```

The plan logs to the existing clean W&B run
`dfm6-xl-gas2-300k-stopfix-clean-20260624` / `dfm6-XL-gas2 300K stopfix clean
eval`, includes checkpoint waits and HF export rows, uses vLLM + FA4 with the
Gemma-native chat template, logs epoch x-axis values, and keeps the known-good
judged Talemaader settings: batch `16`, judge `openai/gemma-4-e4b-judge`,
local judge server `unsloth/gemma-4-E4B-it`, and judged-task vLLM utilization
`0.18`.

Checkpoint epoch values:

```text
step_550000 -> eval_epoch 2.2951186248057427
step_600000 -> eval_epoch 2.5037657725153557
```

Plan creation summary:

```text
average                      14
eval_dfm                    102
eval_dfm_ifeval              64
eval_euroeval                36
eval_euroeval_batched_ifeval  4
eval_standard               170
export_hf                     2
merge_dfm                    20
merge_ifeval                  2
merge_standard               16
report                        2
wait_checkpoint               2
status:pending              432
status:skipped                2
```

Launch commands:

```bash
cd /work/dfm/HRM-Text
/home/ucloud/miniforge3/envs/hrm/bin/python -m eval_scheduler run \
  --plan-dir logs/scheduler/dfm6_XL_gas2_steps550k_600k_stopfix_clean_20260627 \
  --gpus 0,1,2,3,4,5,6,7

/home/ucloud/miniforge3/envs/hrm/bin/python -m eval_scheduler monitor \
  --plan-dir logs/scheduler/dfm6_XL_gas2_steps550k_600k_stopfix_clean_20260627 \
  --gpus 0,1,2,3,4,5,6,7 \
  --interval 30
```

DFM6 XL-GAS2 650K/700K/750K eval scheduler extension, 2026-06-28. Confidence:
high from local `plan.tsv` inspection and `eval_scheduler status`. The existing
live scheduler plan
`logs/scheduler/dfm6_XL_gas2_steps550k_600k_stopfix_clean_20260627` was
extended in place with full checkpoint subgraphs for `step_650000`,
`step_700000`, and `step_750000`. The extension duplicated the tuned
`step_600000` subgraph instead of using `plan create --append`, because the
existing plan has per-task batch settings that are more specific than the
uniform CLI defaults. Statuses and attempts were reset for the copied jobs;
the known skipped `valeu-da` rows remain skipped.

Added epoch x-axis values:

```text
step_650000 -> eval_epoch 2.7124129202249687
step_700000 -> eval_epoch 2.9210600679345817
step_750000 -> eval_epoch 3.1297072156441947
```

Post-extension scheduler status showed `1085` total jobs:

```text
pending=860 running=4 done=216 failed=0 skipped=5
active waits:
  step_600000
  step_650000
  step_700000
  step_750000
```

The appended jobs preserve the same W&B target
`DFM5/dfm6-xl-gas2-300k-stopfix-clean-20260624`, vLLM + FA4 settings, Gemma
native chat template, local judge settings, and tuned batches as `step_600000`.
The plan directory name still says `steps550k_600k`; it is now logically the
550K-750K scheduler.

DFM6 XL-GAS2 math invalid investigation, 2026-06-27. Confidence: high from
local tokenizer inspection, saved-generation probes, and merged metrics. The
DFM6 Gemma export has `eos_token='<turn|>'` and `eos_token_id=106`, so the
standard eval setting `stop_token_ids: [106]` matches the exported tokenizer.
The Gemma-native eval template renders ordinary non-thinking prompts as:

```text
<bos><|turn>user
...prompt...<turn|>
<|turn>model
```

It does not inject a prompt-side thinking marker when `enable_thinking=False`.
The explicit Gemma thinking token `<|think|>` is token id `98`, while the model
often emits plain XML-like `<think>` as three normal tokens (`<`, `think`, `>`).

The completed `step_500000` standard eval reported:

```text
eval/MATH/acc     = 0.32640034
eval/MATH/invalid = 0.21579308
eval/GSM8k/acc    = 0.83775504
eval/GSM8k/invalid= 0.05761782
eval/MMLU/acc     = 0.5423
eval/MMLU/invalid = 0.046975
```

MATH invalids mean `evaluation/benchmarks.py::MATH.compute_metrics` did not
find `\boxed{...}` in the scored generation. The scorer still tries
`math_verify` on the whole text, so `invalid` is primarily a formatting/completion
flag, not necessarily mathematical wrongness.

A saved-generation MATH probe at `step_500000` with the production Gemma chat
template and stop id but a shorter cap (`max_tokens=512`, 8 samples) produced
`acc=0.25`, `invalid=0.50`. The invalid examples were mostly cut off
mid-reasoning before a boxed final answer. The generations did not contain
`<turn|>` leakage, and the prompt did not include thinking markers. Some valid
generations nevertheless emitted learned `</think><answer>...` sections before
the final boxed answer. Probe artifacts:

```text
logs/analysis/dfm6_step500000_math_invalid_probe/math_probe_512.yaml
logs/analysis/dfm6_step500000_math_invalid_probe/generations_512/MATH.generations.jsonl
```

For MMLU, invalids are a different issue. `MMLU` inherits the standard MCQ
generation override `max_tokens=1`, and `MMLU.compute_metrics` accepts only an
exact stripped `A/B/C/D`. The high-invalid math/logical subjects are caused by
the model beginning a reasoning trace instead of the letter. In a probe of 12
examples per subject using the same Gemma chat template:

```text
abstract_algebra          inv1=12/12, 4-token prefix always "<think>\n"
college_mathematics       inv1=12/12, 4-token prefix always "<think>\n"
high_school_mathematics   inv1=11/12, 4-token prefix usually "<think>\n"
formal_logic              inv1= 6/12, mixed "<think>\n" and "Let's ..."
elementary_mathematics    inv1= 0/12
college_physics           inv1= 1/12
```

Adding a strict user-prefix instruction (`Answer with exactly one letter...
Do not write reasoning. Do not write <think>.`) helped formal logic but did not
solve the harder math subjects:

```text
abstract_algebra          inv1=8/8
college_mathematics       inv1=6/8
high_school_mathematics   inv1=5/8
formal_logic              inv1=1/8
```

Probe artifacts:

```text
logs/analysis/dfm6_step500000_math_invalid_probe/run_mmlu_probe.py
logs/analysis/dfm6_step500000_math_invalid_probe/mmlu_probe/mmlu_math_probe.jsonl
logs/analysis/dfm6_step500000_math_invalid_probe/run_mmlu_prompt_variant_probe.py
logs/analysis/dfm6_step500000_math_invalid_probe/mmlu_probe/mmlu_prompt_variant_probe.jsonl
```

Working interpretation: the MATH freeform invalids are mostly long reasoning
that fails to terminate with a boxed answer before the token cap. The MMLU
math-subset invalids are caused by a learned `<think>`/reasoning-output habit
under Gemma chat prompting, which conflicts with the one-token MCQ evaluator.
This is related to the Gemma-template migration in the sense that DFM6 uses the
Gemma chat prompt path, but the immediate issue is not a wrong EOS token or
template-injected thinking token. Future fixes to test separately from official
score reporting: add a task-specific answer-format instruction for MATH, allow
MCQ math subsets enough tokens to finish a short reasoning trace and extract the
final letter, or add a logits/grammar constraint for MCQ tasks if we want a pure
direct-answer evaluation. Confidence: high for the local observations; medium
for the proposed fixes until full-checkpoint reruns compare scores.

DFM6 XL-GAS2 step-600000 EuroEval IFEval recovery, 2026-06-29.
Confidence: high from local plan/log inspection and NLTK verification. Two
EuroEval batched IFEval rows failed after generation during local scoring, not
because of vLLM, FA4, CUDA, or OOM:

```text
eval-00228 euroeval:ifeval-da shard 8/20
eval-00237 euroeval:ifeval    shard 17/20
```

Both logs failed in `scripts/run_ifeval_batched_openai.py` while EuroEval's
IFEval scorer called `nltk.tokenize.word_tokenize`; the missing resource was
`tokenizers/punkt_tab/english/`. Fixed in the HRM environment with:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python - <<'PY'
import nltk
for pkg in ['punkt_tab', 'punkt']:
    nltk.download(pkg, download_dir='/home/ucloud/nltk_data')
PY
```

Then only the two failed plan rows were reset to `pending`, `attempt=0`, while
preserving `vllm_gpu_memory_utilization=0.25`. The running scheduler picked
them up immediately, leaving `failed=0`; downstream EuroEval/Danish/English
averages were pending only on these two rows.

DFM6 BFCL tool-call data/eval contract investigation, 2026-06-30.
Confidence: high from local code inspection, rendered training examples, vLLM
parser tests, and EuroEval proxy logs. The low BFCL score is plausibly caused
in part by a mismatch between the dominant tool-call training syntax and the
evaluation serving/parser contract.

Verified facts:

- DFM6 data and eval Gemma templates are byte-identical:
  `data_io/chat_templates/gemma4_native_chat.jinja` and
  `evaluation/chat_templates/gemma4_native_chat.jinja` have SHA-256
  `33204f1acb5bd0002713e16a593847f24ceeafe711ed88bda2a352dc996a3373`.
- BFCL eval uses the vLLM native proxy with OpenAI `tools` and vLLM's Gemma4
  parser: `--enable-auto-tool-choice --tool-call-parser gemma4`.
- The vLLM Gemma4 parser expects Gemma argument syntax like
  `q:<|"|>Paris<|"|>,days:5`. Local parser tests showed it returns `{}` for
  DOLCI-style `q="Paris", days=5` or `quantity=2, from_unit="pounds"`.
- DOLCI tool-use rows retain system instructions saying functions are inside
  `<functions></functions>` and assistant calls should be inside
  `<function_calls></function_calls>`, while our Jinja renderer also injects
  Gemma-native `<|tool>declaration:...<tool|>` blocks. The resulting prompt is
  therefore mixed: XML/function-call instructions plus Gemma-native tools.
- `scripts/tokenize_chat_template.py::normalize_tool_calls()` converts
  `tool_name(args)` strings to `tool_calls`, but leaves the argument substring
  as a raw string. The rendered supervised target for a DOLCI row is therefore
  e.g.:

```text
<|tool_call>call:weather.forecast_weather_api{q="Paris", days=5}<tool_call|>
```

  not the canonical parser-compatible:

```text
<|tool_call>call:weather.forecast_weather_api{q:<|"|>Paris<|"|>,days:5}<tool_call|>
```

- In the first sampled `20,002` DOLCI tool-use assistant-call messages,
  `33,313` rendered calls had string arguments and `32,932` contained `=`.
  DOLCI tool-use-SA similarly had `2,938/2,938` string-argument calls with `=`.
- Recent BFCL proxy logs show the proxy is active and adapts most responses
  (`step_700000`: `234/250` BFCL responses adapted), so the low score is not
  simply a no-call or disabled-parser failure. It is more consistent with exact
  function/argument mismatches after parsing.

Interpretation: the output-side special tokens are broadly aligned, but a large
part of the tool-call supervision teaches raw Python/function-call argument
syntax and XML-style prompt instructions, whereas BFCL scoring goes through the
OpenAI tools -> vLLM Gemma parser path and requires parser-compatible, exact
JSON arguments. For future data preparation, normalize `tool_name(args)` source
arguments into mappings before rendering, strip or rewrite XML
`<functions>/<function_calls>` instructions when Gemma-native tool declarations
are injected, and add a small contract test that renders a training tool-call
row then feeds the target through vLLM's Gemma4 parser expecting non-empty
arguments. No main code was changed during this investigation.

DFM6 epoch-boundary data replacement/resume plan, 2026-06-30.
Confidence: high from local inspection of `pretrain.py`, `dataset_new.py`, and
`config/data/dfm6.yaml`. If the DFM6 run needs corrected data after the
tool-call contract fix, the safe intervention point is a fully written epoch
checkpoint, not an intra-epoch step or ephemeral checkpoint.

Relevant mechanics:

- `resolve_resume_state()` treats `resume_checkpoint_tag=epoch_N` as
  `start_epoch=N+1` and `skip_batches=0`.
- The main training loop calls `train_loader.dataset.set_epoch(start_epoch - 1)`
  before iterating. Therefore resuming from `epoch_3` starts training epoch 4
  from sampled data directory `epoch_3` in the replacement dataset.
- Step and ephemeral checkpoints carry `batch_in_epoch` or row-cursor resume
  state. Those references are tied to the old epoch ordering and should not be
  used after changing the sampled data.
- `init_train()` recomputes `total_steps` from the new dataset metadata:
  `config.epochs * int(train_metadata.total_length // global_batch_size)`.
  The loaded checkpoint step stays exact if checkpoint metadata contains
  `step`, but future LR/progress scheduling uses the new total length.

Recommended operational pattern:

1. Wait until all rank checkpoint artifacts for `epoch_3` exist and the write
   is complete (`fsdp2_epoch_3` or equivalent, all `carry_epoch_3.*.pt`, and
   `checkpoint_state_epoch_3.json`).
2. Stop training only after that checkpoint is complete.
3. Build the corrected data in a new sampled directory, e.g.
   `data/sampled_dfm6_toolfix`, rather than overwriting `data/sampled_dfm6`.
4. Add a new Hydra data config such as `config/data/dfm6_toolfix.yaml` pointing
   to that directory. Keep the tokenizer/vocab and max-sequence metadata
   compatible with the model.
5. Resume from `resume_checkpoint_tag=epoch_3`, with `data=dfm6_toolfix`.
   If `epochs=5`, the loop will train epochs 4 and 5 on the corrected data.

This is a clean training continuation mechanically, but analytically it is a
data intervention: the first three epochs were trained on the old data
contract. For reproducibility, keep the original sampled dataset immutable,
store the new config separately, and label the W&B run/checkpoint path so the
epoch-4 data switch is visible.

Forward-looking math answer-format and direct-vs-CoT prompt-contract notes were
moved to `wiki/pages/dfm7-plan.md` on 2026-06-30. Keep this DFM6 page focused
on the active DFM6 intervention and checkpoint-resume mechanics.
