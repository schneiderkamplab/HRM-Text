# Script Entities

Last updated: 2026-06-19
Confidence: high
Scope: Local scripts added or used during data preparation.

## `eval_scheduler/`

Added on 2026-06-16. Confidence: high for local package compilation, Typer CLI
startup, smoke plan creation, status display, and pending batch-size editing;
medium for full end-to-end eval execution until a real checkpoint eval is run
through this new scheduler.

`eval_scheduler/` is a new self-contained Python package for a plan-first HRM
evaluation scheduler. It deliberately does not import
`scripts/schedule_checkpoint_evals.sh`; it owns its own job model, plan writer,
state/event files, retry policy, and Typer CLI. It still calls the repository's
existing evaluation entrypoints as external commands (`evaluation.main`,
`scripts/hrm_openai_server.py`, dfm-evals via `uv run`, merge scripts,
headline-average logging, and report generation).

Main files:

```text
eval_scheduler/README.md
eval_scheduler/pyproject.toml
eval_scheduler/eval_scheduler/cli.py
eval_scheduler/eval_scheduler/model.py
eval_scheduler/eval_scheduler/catalog.py
eval_scheduler/eval_scheduler/plan.py
eval_scheduler/eval_scheduler/runtime.py
eval_scheduler/eval_scheduler/monitor.py
```

The editable plan format is `plan.tsv` with header:

```text
job_id	action	family	name	shard	shards	deps	initial_batch	max_retries	gpu_policy	status	attempt	log_dir	metadata_json
```

The plan is intentionally more expressive than the old `jobs.tsv`. It includes
evaluation jobs plus merge, average, and report jobs as dependency-gated rows.
Pending rows can be edited directly, and `initial_batch` controls future
attempts. This avoids the previous workaround where synthetic telemetry rows
had to be injected to force future shards to use a lower batch size.

Current supported actions:

```text
wait_checkpoint
eval_standard
eval_dfm
eval_dfm_ifeval
eval_euroeval
merge_standard
merge_dfm
merge_ifeval
average
report
```

Checkpoint-wait update, 2026-06-16. Confidence: high for local plan smoke tests
and a missing-checkpoint runtime smoke test. Generated plans now include a
`wait_checkpoint` row by default. All eval rows for that checkpoint depend on
the wait row. The wait row completes only when either
`CKPT_PATH/fsdp2_<tag>/.metadata` or `CKPT_PATH/unsharded_<tag>.pt` exists and
all configured `carry_<tag>.<rank>.pt` files exist. Defaults are 8 carry ranks,
300 seconds between polls, and no maximum wait time. CLI controls:

```text
--include-checkpoint-wait / --no-include-checkpoint-wait
--checkpoint-carry-ranks 8
--checkpoint-wait-seconds 300
--checkpoint-wait-max-seconds 0
```

This makes it possible to queue evals before a checkpoint exists. When the wait
row becomes `done`, downstream eval shards become ready and can start on free
GPUs.

Multiple-checkpoint plan update, 2026-06-16. Confidence: high for local append
smoke test. `plan create --append` appends another checkpoint subgraph to an
existing `plan.tsv`. Job IDs and internal dependencies are rebased
automatically. A smoke plan with `step_300000` and appended `step_350000`
contained two independent `wait_checkpoint` rows:

```text
wait-00001  step_300000
wait-00191  step_350000
```

The first appended eval row for `step_350000` depended on `wait-00191`, not
the first checkpoint wait row.

The runner now has a small non-GPU worker pool for `wait_checkpoint`, merge,
average, and report jobs in addition to GPU worker slots. This prevents future
checkpoint wait rows from consuming GPU slots while still allowing multiple
upcoming checkpoints to be watched.

External-model evaluation update, 2026-06-16. Confidence: high for local source
inspection, `compileall`, generated plan inspection, and process/status
inspection. `eval_scheduler` supports external Hugging Face/vLLM models through
`plan create-external`. External standard evals, DFM evals, DFM IFEval-DA, and
EuroEval start one single-GPU vLLM OpenAI-compatible server per GPU worker/task,
run the client against that per-task server, then tear the server down. The
external standard path uses `evaluation.engines.OpenAIEngine`; dfm-evals and
EuroEval use OpenAI-compatible target URLs.

Operational notes for external vLLM jobs:

- Prefer a local snapshot path, e.g.
  `/home/ucloud/.cache/huggingface/hub/models--Qwen--Qwen3.5-2B/snapshots/<rev>`,
  instead of a remote model id when launching many concurrent per-task servers.
  The first Qwen3.5-2B attempt hit Hugging Face Hub `429 Too Many Requests`
  because every vLLM server queried the Hub.
- Each vLLM job now gets isolated cache directories under the job log directory
  via `VLLM_CACHE_ROOT`, `TORCHINDUCTOR_CACHE_DIR`, `TRITON_CACHE_DIR`, and
  `CUDA_CACHE_PATH`.
- vLLM startup now fails fast if the server process exits or logs an OOM while
  the scheduler waits for `/health`.
- For Qwen3.5-2B on this machine, `--vllm-extra-args "--enforce-eager"` avoids
  torch.compile/CUDAGraph startup fragility, with a speed tradeoff.
- Follow-up on 2026-06-16: after CUDA was installed in `/usr/local/cuda`, the
  scheduler-managed vLLM environment was changed to expose `CUDA_HOME`,
  `CUDA_PATH`, `PATH`, and `LD_LIBRARY_PATH` to each vLLM server when
  `/usr/local/cuda` exists. This allows vLLM's DeepGEMM warmup to import
  `deep_gemm` successfully. A single-GPU Qwen3.5-2B smoke on GPU0 reached
  `/health` with DeepGEMM enabled; the ordered Qwen/DFM5 scheduler was then
  relaunched and the first Qwen EuroEval jobs completed and synced.
- Follow-up on 2026-06-16: Qwen external standard evals initially failed on
  MATH because `evaluation.main` passed checkpoint-oriented Hydra keys such as
  `ckpt_path` into `OpenAIEngine`. `evaluation.engines.OpenAIEngine` now accepts
  and ignores extra keyword arguments, matching the external-model use case
  where checkpoint keys are scheduler metadata rather than engine arguments.
  The failed/running Qwen MATH rows in
  `logs/scheduler/qwen_then_dfm5_L_400k_450k_20260616/plan.tsv` were reset to
  pending and the scheduler was relaunched.
- Separate `eval_scheduler run` instances do not coordinate GPU leases. The
  Qwen plan `logs/scheduler/qwen35_2b_full_20260616` was stopped on 2026-06-16
  after the DFM5 checkpoint scheduler began running `step_400000` EuroEval jobs
  on GPUs 0 and 1. Its running rows were reset to pending so it can be resumed
  later on an explicitly non-conflicting GPU set.

Stop/resume update, 2026-06-16. Confidence: high for local smoke tests with a
missing-checkpoint wait row and a manual stale-`running` repair. The scheduler
now supports graceful stop and later resume:

```bash
cd /work/dfm/HRM-Text
python -m eval_scheduler stop \
  --plan-dir logs/scheduler/dfm5_L_step300000

python -m eval_scheduler run \
  --plan-dir logs/scheduler/dfm5_L_step300000 \
  --gpus 0,1,2,3,4,5,6,7
```

`stop` writes `PLAN_DIR/stop.request`. The runner observes this file between
job launches and stops claiming new jobs. Already running eval jobs are allowed
to finish normally. A running `wait_checkpoint` row exits with scheduler stop
status and is returned to `pending`, not failed. Starting `run` removes stale
`stop.request` at the beginning, so a later run continues the remaining
pending jobs.

For hard-killed schedulers, rows may be left as `running`. Repair them before
resuming:

```bash
python -m eval_scheduler plan reset-running \
  --plan-dir logs/scheduler/dfm5_L_step300000
```

`plan reset-running --increment-attempt` is also available if an interrupted
attempt should count against the retry budget.

Smoke commands verified locally:

```bash
cd /work/dfm/HRM-Text
python -m compileall -q eval_scheduler
python -m eval_scheduler --help

rm -rf /tmp/hrm-eval-scheduler-smoke
python -m eval_scheduler plan create \
  --plan-dir /tmp/hrm-eval-scheduler-smoke \
  --ckpt-path checkpoints/dfm5/L \
  --ckpt-tag step_300000 \
  --eval-epoch 1.6565307709311847 \
  --log-root logs/eval/smoke_new_scheduler \
  --dfm-log-root logs/dfm_evals/smoke_new_scheduler \
  --euroeval-log-root logs/euroeval/smoke_new_scheduler \
  --wandb-run-id oti1lisg \
  --wandb-run-name dfm5-L \
  --model-prefix hrm-dfm5-L \
  --run-euroeval \
  --queue-order euroeval-first \
  --standard-batch 64 \
  --dfm-batch 32 \
  --ifeval-batch 32 \
  --euroeval-batch 16

python -m eval_scheduler status --plan-dir /tmp/hrm-eval-scheduler-smoke
python -m eval_scheduler plan set-batch \
  --plan-dir /tmp/hrm-eval-scheduler-smoke \
  --family dfm_ifeval \
  --batch 16
python -m eval_scheduler plan list \
  --plan-dir /tmp/hrm-eval-scheduler-smoke \
  --family dfm_ifeval \
  --limit 5
```

The smoke plan produced 209 explicit jobs:

```text
eval_euroeval: 20
eval_dfm_ifeval: 32
eval_standard: 85
merge_standard: 8
eval_dfm: 51
merge_dfm: 10
merge_ifeval: 1
average: 1
report: 1
```

The batch edit command changed all 32 pending `dfm_ifeval` rows from batch
`32` to batch `16`.

Qwen GovReport retry update, 2026-06-16. Confidence: high for local source
inspection, shard logs, merge logs, and W&B API checks. The Qwen3.5-2B
GovReport failures in
`logs/scheduler/qwen_then_dfm5_L_400k_450k_20260616` were not OOM failures.
They were vLLM HTTP 400 context-length failures: long GovReport prompts plus
the requested generation length exceeded the model's 4096-token context. Batch
size retries could not fix this.

Fixes applied:

- `dfm-evals/dfm_evals/tasks/summarization.py` now lets `govreport()` accept
  `max_report_chars`; the default is `None`, so normal GovReport behavior is
  unchanged unless a caller opts in.
- `eval_scheduler/eval_scheduler/runtime.py` now passes DFM template overrides
  from job metadata, including `dfm_max_gen_toks` and arbitrary
  `dfm_task_args`.
- The Qwen GovReport plan rows were reset with `dfm_max_gen_toks=128` and
  `dfm_task_args=["max_report_chars=10000"]`.
- Client fatal logs such as OpenAI bad requests now terminate the paired vLLM
  server and fail the joint task attempt, instead of leaving an orphan server or
  treating the worker and server independently.

All 16 Qwen GovReport shards then completed, merged, and synced to W&B run
`peter-sk-sdu/DFM5/qwen35-2b-full`. Verified summary keys include:

```text
dfm_eval/govreport/chrf3pp/mean = 9.986128459008524
dfm_eval/govreport/bertscore_f1/mean = 0.8529781600554213
dfm_eval/govreport/rouge2/mean = 0.061699390782425347
```

Gemma 4 E2B external baseline update, 2026-06-17. Confidence: high for local
process inspection, vLLM logs, EuroEval logs, and scheduler status.

The Gemma baseline is queued in:

```text
logs/scheduler/gemma4_e2b_then_dfm5_L_500k_20260617
```

The first block evaluates local model:

```text
/work/dfm/brainsurgery/models/google/gemma-4-E2B-it
```

against the full standard, dfm, and EuroEval suite, then the same plan waits
for `checkpoints/dfm5/L` `step_500000` and evaluates it. The `step_500000`
wait row depends on the Gemma average row, so the 500K HRM eval block starts
after the Gemma baseline is averaged.

Gemma-specific vLLM notes:

- Loading the snapshot as its advertised `Gemma4ForConditionalGeneration`
  failed because the local snapshot has no `preprocessor_config.json`.
- For text-only evaluation, vLLM must be forced to
  `Gemma4ForCausalLM` with:

```text
--hf-overrides '{"architectures":["Gemma4ForCausalLM"]}'
```

- The local tokenizer has no `chat_template`, and vLLM chat completions fail
  without one. The scheduler plan therefore passes:

```text
--chat-template /work/dfm/HRM-Text/evaluation/chat_templates/gemma4_e2b_plain_chat.jinja
```

This is a conservative plain role-label template using `System:`, `User:`, and
`Assistant:` rather than Gemma-specific turn tokens, because the local
tokenizer did not expose `<start_of_turn>`/`<end_of_turn>` as normal tokens.

EuroEval-specific notes:

- Use the explicit HRM Python wrapper:

```text
/home/ucloud/miniforge3/envs/hrm/bin/python /work/dfm/HRM-Text/scripts/euroeval_api_no_flash_attn_guard.py
```

- Set `euroeval_generative_type=instruction_tuned`.
- Set `fixed_retry_batch=true` for the Gemma jobs so non-OOM retries do not
  halve the deliberately chosen baseline batches.

With these settings, the first Gemma EuroEval jobs reached real benchmarking
logs such as `Loading the model ...` and per-sample progress, and scheduler
status showed completed rows rather than the earlier `Model ... not found`
failures.

Gemma baseline repair, 2026-06-17. Confidence: high for local scheduler status,
plan edits, and successful rerun logs.

The initial Gemma baseline run later blocked before the `step_500000` wait row
because two DFM merge rows depended on failed shards:

```text
merge-00162 dfm:govreport
merge-00180 dfm:generative_talemaader
```

The failed `euroeval:valeu-en` row was not an average dependency and failed
because the model produced too many invalid labels; it was marked `skipped`
rather than retried indefinitely.

GovReport failed with vLLM context overflow: prompts near 3585 input tokens
plus 512 requested output tokens exceeded the 4096 context limit. The failed
Gemma GovReport rows were reset with:

```json
{
  "dfm_context_length": 3968,
  "dfm_max_gen_toks": 128,
  "dfm_task_args": ["max_report_chars=10000"]
}
```

All 16 repaired GovReport shards completed successfully and `merge-00162`
succeeded.

`generative_talemaader` failed because the DFM suite requires a judge model.
The failed Gemma rows were reset with:

```json
{
  "judge_model": "openai/gemma-4-e4b-judge",
  "judge_base_url": "http://127.0.0.1:8099/v1",
  "max_connections": 4
}
```

The judge server was already running as:

```text
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/transformers_openai_server.py unsloth/gemma-4-E4B-it --served-model-name gemma-4-e4b-judge --host 127.0.0.1 --port 8099 --dtype bfloat16 --attn-implementation sdpa --max-new-tokens 64
```

The same GovReport and judge metadata were also applied to the future
`step_500000` rows in the same plan so that the HRM 500K block does not repeat
the same failures.

Qwen EuroEval MultiWikiQA sync update, 2026-06-16. Confidence: high for local
metrics and W&B API checks. The local MultiWikiQA metric existed but initially
did not appear in the remote W&B summary/history. Re-running
`scripts/log_euroeval_to_wandb.py` against
`logs/euroeval/qwen35_2b_full_ordered_20260616/qwen35_2b/multi-wiki-qa-da/euroeval_benchmark_results.jsonl`
logged the metric to the same run. Verified key:

```text
euroeval/da/reading-comprehension/multi-wiki-qa-da/f1 = 73.03916213314417
```

Qwen GSM8K note, 2026-06-16. Confidence: high for local metric/log/source
inspection, medium for exact generation-format inference because standard evals
do not persist generated text. The Qwen3.5-2B full run logged
`eval/GSM8k/acc=0.0`, `eval/GSM8k/invalid=1.0`, and `eval/GSM8k/n=1319`.
All eight GSM8K shards under
`logs/eval/qwen35_2b_full_ordered_20260616/standard_shards/GSM8k/` had
`invalid=1.0`. The local GSM8K scorer in `evaluation/benchmarks.py` parses only
the whole generated string as a number unless `last_boxed_only_string` finds a
boxed answer. The standard config gives Qwen the raw GSM8K question with
`max_tokens=512` and no explicit final-answer-only or boxed-answer instruction.
Treat this as an extraction/prompt mismatch, not as evidence that Qwen solves
zero GSM8K. Any fixed rerun should save generations and use a new metric key or
clear suffix rather than silently replacing the old all-invalid metric.

Follow-up on 2026-06-16. Confidence: high for source inspection and local
synthetic extraction tests. `evaluation/benchmarks.py` now makes GSM8K answer
extraction more robust: boxed answers still win, bare numeric strings still
work, `####`, `final answer`, and `answer is` patterns are accepted, and the
fallback is the last standalone integer-valued number in the generation.
Non-integer floats remain invalid. This changes future GSM8K scoring and should
not be silently mixed with the earlier all-invalid Qwen GSM8K result.

Qwen clean-run backfill and GSM8K rerun, 2026-06-17. Confidence: high for local
scheduler status, local merged artifact, and W&B API checks. The old Qwen
metrics were backfilled to a new clean W&B run, excluding old GSM8K and all
headline averages:

```text
project: DFM5
run_id: qwen35-2b-full-clean
run_name: Qwen3.5 2B full clean
script: scripts/backfill_qwen35_clean_wandb.py
```

The backfill logged 444 keys from existing local standard, DFM, and EuroEval
artifacts. Verified remote summary had no `eval/GSM8k/*` keys and no `avg/*`
keys before the rerun. The corrected GSM8K rerun was inserted at the front of
`logs/scheduler/qwen_then_dfm5_L_400k_450k_20260616/plan.tsv` as eight
external standard-eval shards plus one merge row:

```text
eval-qwengsm-00000 .. eval-qwengsm-00007
merge-qwengsm-00008
log root: logs/eval/qwen35_2b_gsm8k_fixed_20260616
```

Final merged fixed GSM8K metrics, synced to `qwen35-2b-full-clean`:

```text
eval/GSM8k/acc = 0.6656600454890069
eval/GSM8k/invalid = 0.023508567096285068
eval/GSM8k/n = 1319
```

The clean run intentionally still has no headline averages; recompute them only
if the desired average definition should include the corrected Qwen GSM8K.

Follow-up on 2026-06-17. Confidence: high for local dry-run output, W&B sync
logs, and W&B API verification. Headline averages were added to the clean Qwen
run after creating a clean standard-eval root that symlinks all standard
artifacts from the original Qwen run except GSM8K, which points to the fixed
GSM8K rerun:

```text
logs/eval/qwen35_2b_clean_standard_20260617/standard_shards/GSM8k
  -> logs/eval/qwen35_2b_gsm8k_fixed_20260616/standard_shards/GSM8k
```

Command:

```bash
cd /work/dfm/HRM-Text
python scripts/log_dfm5_headline_averages.py \
  --project DFM5 \
  --run-id qwen35-2b-full-clean \
  --run-name 'Qwen3.5 2B full clean' \
  --metric-prefix avg \
  --item '0:0.0:logs/eval/qwen35_2b_clean_standard_20260617:logs/dfm_evals/qwen35_2b_full_ordered_20260616:logs/euroeval/qwen35_2b_full_ordered_20260616/qwen35_2b'
```

Verified summary values:

```text
avg/danish = 0.4471885859937283   (count 18)
avg/english = 0.5782765269227623  (count 15)
avg/math_code = 0.542416855396642 (count 4)
avg/overall = 0.5226273227710442
```

Scheduler average dependency fix, 2026-06-17. Confidence: high for local plan
inspection, log inspection, active-plan edit, and `compileall`. The
`step_450000` wait guard in
`logs/scheduler/qwen_then_dfm5_L_400k_450k_20260616` was present but blocked
behind the previous checkpoint's `average-00417` row. That average row depended
on `eval-00219` (`euroeval:valeu-da`), which had failed because EuroEval found
no candidate label for 1/53 samples and aborts ValEU-da when invalid outputs
are present. Since `valeu-*` metrics are excluded from headline averages, this
dependency was wrong.

Fixes applied:

- Removed all existing `valeu-*` EuroEval dependencies from active-plan average
  rows (`average-00208`, `average-00417`, `average-00626`).
- Updated `eval_scheduler/eval_scheduler/plan.py` so future generated average
  jobs include EuroEval dependencies except groups whose names start with
  `valeu-`.
- Restarted the scheduler. `average-00417` completed, `wait-00418` immediately
  saw `step_450000` as ready, and `step_450000` eval jobs started at
  `2026-06-17T06:24:17+02:00`.

DFM5 report update, 2026-06-17. Confidence: high for local artifact inspection
and regenerated Markdown. `scripts/generate_dfm5_l_eval_comparison_report.py`
now includes the DFM5-L `step_400000` full-eval artifacts and populates the
Qwen3.5 2B comparison column from the local clean Qwen artifacts where
available:

```text
DFM5 400K standard: logs/eval/dfm5_L_step400000_full_ordered_20260616
DFM5 400K DFM:      logs/dfm_evals/dfm5_L_step400000_full_ordered_20260616
DFM5 400K EuroEval: logs/euroeval/dfm5_L_step400000_full_ordered_20260616/step_400000
Qwen clean standard: logs/eval/qwen35_2b_clean_standard_20260617
Qwen DFM:            logs/dfm_evals/qwen35_2b_full_ordered_20260616
Qwen EuroEval:       logs/euroeval/qwen35_2b_full_ordered_20260616/qwen35_2b
```

The canonical report is `docs/dfm5.md`. Superseded, 2026-06-20: the former
compatibility symlink `docs/df5m.md -> dfm5.md` was deleted so the repo has only
one canonical DFM5 report path.
At 400K, DFM5-L beats local-clean Qwen3.5 2B on the Danish average
(`51.0` vs `44.7`) and slightly on the English average (`59.1` vs `57.8`), but
loses badly on Math & Code (`27.0` vs `54.2`).

DFM5 docs cleanup, 2026-06-20. Confidence: high for local filesystem
inspection and regenerated Markdown. The Slack paste-table files
`docs/dfm5_slack_tables.md` and `docs/dfm5_slack_tables/` were deleted, as was
the misnamed compatibility symlink `docs/df5m.md`. `docs/dfm5.md` is now the
only file under `docs/`, and it was regenerated with:

```bash
cd /work/dfm/HRM-Text
python scripts/generate_dfm5_l_eval_comparison_report.py
```

DFM5 450K report update, 2026-06-17. Confidence: high for local artifact
inspection and regenerated Markdown. `scripts/generate_dfm5_l_eval_comparison_report.py`
now also includes:

```text
DFM5 450K standard: logs/eval/dfm5_L_step450000_full_ordered_20260616
DFM5 450K DFM:      logs/dfm_evals/dfm5_L_step450000_full_ordered_20260616
DFM5 450K EuroEval: logs/euroeval/dfm5_L_step450000_full_ordered_20260616/step_450000
```

The regenerated `docs/dfm5.md` has DFM5-L 450K headline averages:
Danish `48.1`, English `60.1`, Math & Code `27.9`. Key Math & Code rows are
GSM8K `33.4`, MATH `47.1`, HumanEval `31.1`, and BFCL-v2 `0.0`.

Gemma 4 E2B external-baseline eval note, 2026-06-17. Confidence: high for
local path/config inspection and scheduler CLI inspection; medium for exact
batch sizes until run. A Qwen3.5-2B-style external eval can be scheduled for
the local Gemma 4 E2B instruct checkpoint without new scheduler code. The local
model path is:

```text
/work/dfm/brainsurgery/models/google/gemma-4-E2B-it
```

Its local `._param_count.json` reports `5,123,178,979` total parameters and
`config.json` advertises `Gemma4ForConditionalGeneration` with
`model_type="gemma4"`. Project decision after review: do not reduce batch sizes
below the Qwen3.5-2B external-eval defaults just because the total parameter
count is larger. Much of the total is non-text/image-side capacity, while the
effective text model is E2B-scale, and prior vLLM jobs had substantial GPU
headroom. The scheduler's `plan create-external` command already supports the
needed vLLM fields (`--model`, `--served-model-name`, `--vllm-extra-args`,
`--vllm-gpu-memory-utilization`, and batch defaults). Start with Qwen-style
batch sizes (`standard=64`, `dfm=32`, `ifeval=32`, `euroeval=16`) and rely on
the scheduler's OOM retry/halving path only if a specific task proves too large.
If vLLM text-only loading has issues, try the known Gemma text-only override:

```text
--vllm-extra-args '--enforce-eager --hf-overrides {"architectures":["Gemma4ForCausalLM"]}'
```

DFM6 data-mix note, 2026-06-17. Confidence: medium; this is a forward-looking
project decision informed by the 400K vs Qwen3.5 2B comparison. DFM6 should:

- include all new DFM post-training datasets;
- scale up Danish math and code datasets;
- scale up English math and code datasets.
- include Danish tool-calling data;
- include English tool-calling data.

Reason: DFM5-L at 400K is already competitive or better than local-clean
Qwen3.5 2B on the HRM-Text model-card standard eval average (`58.4` vs `49.3`)
and on Danish/English language-oriented averages, but remains substantially
behind on math/code (`27.0` vs `54.2` Math & Code average; GSM8K `31.5` vs
`66.6`, HumanEval `30.5` vs `47.6`, BFCL-v2 `0.0` vs `52.1`). The next data
mix should therefore not only add post-training breadth, but explicitly
increase math/code and tool-calling coverage in both Danish and English.

DFM6 tokenizer/instruction-format note, 2026-06-17. Confidence: medium; this is
a forward-looking architecture/data-format decision. For DFM6, replace the
current tokenizer with the Gemma 4 tokenizer and use the Gemma 4 chat template
for instruction-format data instead of the instruction format used for the
original Sapient and DFM5 corpora. This should be treated as a dataset
conversion and training-compatibility change, not a cosmetic tokenizer swap:
all instruction/post-training sources need to be rendered through the new chat
template, and evaluation/export paths should be checked for tokenizer/chat
template assumptions.

Expanded DFM6 checklist, 2026-06-17. Confidence: medium. The DFM6 direction is
solid, but the plan should explicitly cover these items before sampling or
training:

- Verify the exact Gemma 4 tokenizer artifact, license, vocabulary size,
  special tokens, and chat-template rendering; update model config and embedding
  sizes accordingly.
- Treat DFM6 as a fresh-tokenizer training run unless a deliberate
  retokenization/upcycling strategy is implemented; old DFM5 checkpoints are not
  directly resume-compatible after a tokenizer swap.
- Define canonical schemas for tool-calling data in both Danish and English,
  including tool/function JSON, multi-turn tool traces, invalid/tool-error
  cases, and final natural-language responses.
- Add dedicated eval coverage for tool calling in both languages, not only
  BFCL-v2 English; otherwise the data addition cannot be validated.
- Balance post-training data against pretraining/instruction data so Gemma
  chat-template formatting does not overfit short assistant-style replies.
- Rebuild all tokenized/sampled artifacts from source after the tokenizer
  change; do not mix old tokenizer outputs with Gemma-tokenized outputs.
- Check conversion/export/inference/eval paths for hard-coded tokenizer path,
  chat tokens, BOS/EOS handling, and generation stop tokens.
- Add explicit data-mix targets for math/code/tool calling rather than only
  "include more"; DFM5 showed that general language gains do not automatically
  close GSM8K/HumanEval/BFCL gaps.
- Add contamination and dedup checks for the expanded math/code/tool-calling
  sources, especially against held-out eval prompts and common benchmark
  training/test splits.
- Run at least one small end-to-end migration rehearsal before committing a
  large DFM6 run: convert a tiny Gemma-template sample, tokenize it, sample it,
  train for a short smoke run, export, serve, and run standard/DFM/EuroEval
  smoke evals.
- Keep an ablation trail for the main DFM6 additions. At minimum, record which
  source families are new relative to DFM5 and keep enough sampling metadata to
  compare base DFM6, math/code-scaled DFM6, and tool/post-training-enriched
  DFM6 rather than treating all changes as one opaque bundle.

Monitor update, 2026-06-16. Confidence: high for local log inspection and a
live monitor snapshot. External-model DFM jobs write the OpenAI-compatible
server log as `vllm.log`, while the monitor originally looked only for
`server.log`. This made active tasks such as Qwen `generative_talemaader`
display `progress unknown` even though the vLLM log contained successful
`POST /v1/chat/completions` lines. The monitor now falls back to `vllm.log`
when `server.log` is absent. It can therefore show request counts such as
`completion 63/? failed 0`.

Superseded caveat, 2026-06-18: ETA previously remained unknown for some DFM
tasks whose active shard had not yet written a sample total. The monitor now
also infers DFM shard totals from completed sibling shard logs for the same
task/checkpoint. This fixed `generative_talemaader` lines that looked like
`completion 51/? ... ETA unknown` once at least one sibling shard had emitted a
stable `(N samples)` task header. Confidence: high for local monitor snapshots
on the `dfm5_L_step550000_full_native_followup_20260617` campaign.

Follow-up, 2026-06-18. Confidence: high for local log inspection, code
compilation, and a live monitor snapshot on
`logs/scheduler/dfm5_L_step600000_full_simple_20260618_600k_simple`. Some
active DFM shards can keep `dfm-evals.log` empty until late in the run, so no
current sibling shard has a visible `(N samples)` header yet. The monitor now
falls back to older completed campaigns for the same DFM task and shard count,
preferring the exact same shard and using the most common historical total.
For `generative_talemaader` with `8` shards, local prior logs showed `101`
samples per shard, and the live monitor changed from
`completion 56/? ... ETA unknown` to `completion 59/101 ... ETA 5m20s` without
touching the running eval jobs.

Monitor checkpoint/model-label update, 2026-06-16. Confidence: high for local
compilation and a one-shot monitor snapshot. `eval_scheduler/eval_scheduler/monitor.py`
now includes the evaluated model/checkpoint label on active GPU lines and in the
`next ready` queue, using `external_served_model_name`, `model_prefix`,
`ckpt_tag`, and `no_ema` metadata. Example labels:
`qwen35-2b@qwen35_2b:ema`, `hrm-dfm5-L@step_400000:ema`, and
`hrm-dfm5-L@step_400000:noema`.

Locking update, 2026-06-16. Confidence: high for local smoke test. The
scheduler now uses an advisory `fcntl.flock` lock at `PLAN_DIR/plan.lock` for
plan reads and writes. Package commands that mutate or read `plan.tsv` acquire
this lock. The runner claims a job under the same interprocess lock and
re-checks that dependencies are still complete and the row is still pending.

Manual edit workflow:

```bash
cd /work/dfm/HRM-Text
python -m eval_scheduler plan edit \
  --plan-dir logs/scheduler/dfm5_L_step300000 \
  --editor "vim"
```

Explicit lock/unlock workflow for manual editing in another terminal:

```bash
cd /work/dfm/HRM-Text
python -m eval_scheduler plan lock \
  --plan-dir logs/scheduler/dfm5_L_step300000

vim logs/scheduler/dfm5_L_step300000/plan.tsv

python -m eval_scheduler plan unlock \
  --plan-dir logs/scheduler/dfm5_L_step300000
```

`plan lock` starts a background lock-holder process and writes
`PLAN_DIR/plan.lock.holder.json` with the holder PID. `plan unlock` terminates
that holder. A smoke test on `/tmp/hrm-eval-scheduler-smoke` verified that
`python -m eval_scheduler status` blocks while the holder owns the lock and
works again after `plan unlock`.

The root `pyproject.toml` now includes `typer` as a dependency so the scheduler
CLI is part of the normal repo environment.

Monitor update, 2026-06-16. Confidence: high for local compilation, CLI smoke
test, and parsing real EuroEval IFEval logs. The scheduler now has two status
views:

```bash
python -m eval_scheduler status --plan-dir logs/scheduler/dfm5_L_step300000
python -m eval_scheduler monitor --plan-dir logs/scheduler/dfm5_L_step300000 --gpus 0,1,2,3,4,5,6,7
```

`status` remains a terse plan/event summary. `monitor` is the operational view:
it reports total `done/running/ready/blocked_pending/failed/skipped`, one line
per GPU with memory/utilization, the active job on that GPU, shard, batch,
attempt, elapsed time, parsed progress, and ETA when the progress fraction is
known. It also lists the next ready jobs.

Progress parsers:

- standard evals: latest generation tqdm `done/total` from the shard log.
- dfm-evals: local server completion counts and server-batch tqdm when present;
  Inspect `logs.json` and dfm-evals task headers are used to infer sample
  totals when available. During model/metric setup before any task header or
  server request exists, progress may still be reported as unknown.
- dfm-evals failures: early configuration failures such as missing judge
  placeholders are surfaced directly in monitor output instead of showing only
  `progress unknown`.
- EuroEval: nested tqdm parsing. Single-benchmark setup bars like `1/1` are
  ignored when a sample loop is still running. Real multi-pass bars are reported
  as `pass x/y samples a/b`; e.g. a synthetic `3/10` pass bar plus `137/343`
  samples reports `pass 3/10 samples 137/343`.

Follow-up, 2026-06-18. Confidence: high for live monitor snapshots. Some
EuroEval tasks such as `cnn-dailymail` and `nordjylland-news` do not keep a
single monotonic tqdm counter; the per-sample bar resets for repeated scoring
passes. The monitor now groups those resets into pass loops and defaults to
10 passes when the plan row has no explicit `euroeval_passes` metadata. This
turns misleading ETA resets into lines such as
`pass 6/10 samples 118/157 ETA 25m42s`.

Follow-up, 2026-06-18. Confidence: high for live monitor snapshots. EuroEval
single-pass tasks such as `ifeval` and `ifeval-da` now also render with an
explicit pass denominator, e.g. `pass 1/1 samples 101/343`, instead of only
`samples 101/343`. Repeated-pass tasks still render as `pass X/10 samples Y/Z`.

Superseded in the same session for IFEval-like tasks: after the first IFEval
generation loop, EuroEval can emit smaller follow-up loops such as
`343 -> 131 -> 47 -> ...`. Those are variable-sized stages, not repeated
passes. The monitor now classifies loops with roughly stable denominators as
`pass X/10` and variable-denominator loops as `stage X/? samples Y/Z`; the
stage ETA is only for the current stage. Confidence: high for the live
`euroeval:ifeval` `step_550000` log.

Verified against the current real EuroEval logs:

```text
ifeval    samples 237/343
ifeval-da samples 282/343
```

EuroEval path fix, 2026-06-16. Confidence: high. `eval_scheduler` now resolves
relative `.py` `euroeval_bin` values to absolute paths in
`eval_scheduler/eval_scheduler/runtime.py` before calling
`scripts/run_euroeval_on_checkpoint.sh`. This is required because that wrapper
changes directory into the EuroEval log root before running `${EUROEVAL_BIN}`.
Without this, scheduler-created EuroEval jobs failed with status `127` and
`No such file or directory` for `scripts/euroeval_api_no_flash_attn_guard.py`.

EuroEval package wrapper fix, 2026-06-18. Confidence: high for failed-run log
inspection and resumed scheduler status. On the DFM5-L `step_600000` eval
campaign, EuroEval jobs failed after server health checks because the default
`euroeval_bin` invoked `scripts/euroeval_api_no_flash_attn_guard.py` directly
from the HRM environment, where `euroeval` was not importable. The scheduler
default now uses:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/uv run --no-project --with euroeval \
  /work/dfm/HRM-Text/scripts/euroeval_api_no_flash_attn_guard.py
```

The active plan's failed EuroEval rows were reset to pending with this
metadata, and freed GPUs subsequently picked up EuroEval jobs before lower
priority shards.

DFM progress/failure monitor update, 2026-06-16. Confidence: high for local
monitor snapshots. `eval_scheduler/eval_scheduler/monitor.py` now reads
dfm-evals `inspect/logs.json` and task-header text such as `(120 samples)` to
show totals when possible. It also detects placeholder errors like missing
`--judge-model` for `{{judge_model}}`; this exposed that the 350K
`generative_talemaader` shards failed because no judge model/base URL was wired
into the new scheduler run.

DFM judge-task runtime update, 2026-06-16. Confidence: high for local direct
judge request, one-sample Inspect smoke test, and completed 350K
`generative_talemaader` shards. `eval_scheduler/eval_scheduler/runtime.py` now
passes optional per-row metadata fields `judge_model` and `judge_base_url` to
dfm-evals jobs, and `max_connections` can cap the Inspect client fanout
independently of the HRM server batch size. For judged Talemaader shards, the
working settings were:

```text
initial_batch: 16
metadata.max_connections: 4
metadata.judge_model: openai/gemma-4-e4b-judge
metadata.judge_base_url: http://127.0.0.1:8099/v1
```

The initial judge server became wedged: a direct OpenAI-compatible
`/v1/chat/completions` request asking for `GRADE: C` timed out. Restarting
`scripts/transformers_openai_server.py` with `--max-new-tokens 64` fixed the
endpoint; a direct request returned in `0.63s`, and a one-sample
`hrm_danish_generative_talemaader` Inspect run completed in `4s`. After that,
the 350K Talemaader shards completed and merged successfully.

## `scripts/generate_dfm5_l_eval_comparison_report.py`

Update, 2026-06-16. Confidence: high for local execution. Regenerates
`docs/dfm5.md` from local merged evaluation artifacts. It now writes only
`docs/dfm5.md`; the older duplicate outputs under `logs/reports/` were removed.

Checkpoint inclusion is controlled by the hard-coded `DFM5_CHECKPOINTS` list
near the top of the script. Each entry names the display label, checkpoint tag,
standard-eval root, dfm-evals root, and EuroEval root. To include a newly
completed checkpoint in `docs/dfm5.md`, add its roots to `DFM5_CHECKPOINTS` and
run:

```bash
cd /work/dfm/HRM-Text
python scripts/generate_dfm5_l_eval_comparison_report.py
```

## `scripts/synthesize_anonymized_sapient_exclusions.py`

Added on 2026-06-12. Confidence: high for local syntax, initialization, and
active 8-shard launch; medium for final synthetic quality until the generated
rows are audited after completion.

Builds synthetic anonymized replacements for the 321 original Sapient source
files excluded from DFM5. It reads
`logs/data_audits/dfm5_excluded_original_sapient_sources.tsv`, creates one
folder per excluded source under `synth/`, and writes only judge-accepted rows.
For sharded runs it writes one gzip per shard, e.g.
`data/train.shard00000of00008.jsonl.gz`, to avoid concurrent gzip append
corruption.

For each input row the script asks a local OpenAI-compatible teacher to
generate a substantially different anonymized version of the
`condition`/`instruction`/`response` row, then uses the same model as judge. A
row is kept only if the judge accepts it and local heuristics do not find
unchanged PII-like strings or high 5-gram overlap. Rejected attempts are kept
under `rejected/`, also split by shard for sharded runs.

Resume fix, 2026-06-12: the first 8-worker run wrote every shard into the same
`data/train.jsonl.gz` and `rejected/rejected.jsonl.gz`, which corrupted the
gzip stream under concurrent appends. Those legacy files for
`synth/Platypus_reclor.jsonl` were quarantined under
`synth/Platypus_reclor.jsonl/corrupt_20260612T214749/`. The script now writes
per-shard accepted/rejected gzip files and per-shard summaries. It also skips
unreadable gzip files when loading resume IDs instead of crashing.

Quality-gate tightening, 2026-06-12: accepted rows now require all judge
booleans to be true (`keep`, `substantially_different`, `pii_changed`,
`low_textual_overlap`, `task_preserved`, and `quality_ok`) in addition to the
local heuristic requiring at most `0.08` candidate 5-gram overlap and no
unchanged PII-like strings. Before resuming, the existing 469 accepted ReClor
rows were audited locally and all 469 passed this stricter condition.

Priority/concurrency update, 2026-06-13: the script now supports
`--source-priority high40`, an explicit 40-file high-priority campaign that
excludes the huge WMT/translation and broad review/sentiment sources. It also
supports `--concurrency N` per worker. The first batched run used concurrency
`8` and verified `Running: 8 reqs` per GPU server. It was then restarted with
`CONCURRENCY_PER_SHARD=32`; vLLM sustained `31-32` running requests per GPU
with no waiting queue, KV cache usage below about `30%`, and a measured
high40 throughput sample of about `1,206` rows/min.

Concurrency-128 update, 2026-06-13: the first `MAX_NUM_SEQS=128` launch failed
on one GPU during vLLM/TorchInductor autotuning with `CUDA driver error: file
not found`, likely from shared compile/cache races during simultaneous
multi-server startup. The launcher now sets per-GPU `VLLM_CACHE_ROOT`,
`TORCHINDUCTOR_CACHE_DIR`, and `TRITON_CACHE_DIR` under the run log root. The
second 128 launch succeeded. vLLM showed about `99-128` running requests per
GPU, but some GPUs reached `96-99.9%` KV cache usage and small waiting queues.
The first measured high40 row-throughput sample under the then-active sources
was about `614` rows/min.

Smoke/init commands:

```bash
cd /work/dfm/HRM-Text
python scripts/synthesize_anonymized_sapient_exclusions.py --init-only
python scripts/synthesize_anonymized_sapient_exclusions.py \
  --base-url http://127.0.0.1:8900/v1 \
  --model posttrain-gemma-teacher \
  --limit-sources 1 \
  --limit-rows-per-source 10
```

## `scripts/run_sapient_anonymization_vllm_8gpu.sh`

Added on 2026-06-12. Confidence: high for local launch and current active run.

Starts eight single-GPU vLLM servers for the fresh Gemma 4 31B IT teacher at
`data/models/google/gemma-4-31B-it-fresh-20260604`, waits for the OpenAI
`/v1/models` endpoints, and launches one
`scripts/synthesize_anonymized_sapient_exclusions.py` shard worker per GPU.
The default ports are `8900` through `8907`, and the default served model name
is `posttrain-gemma-teacher`.

The first launch on 2026-06-12 failed because vLLM tried to import DeepGEMM
and asserted that `CUDA_HOME` was missing. The launcher now disables DeepGEMM
by default for this run with `VLLM_USE_DEEP_GEMM=0` and
`VLLM_MOE_USE_DEEP_GEMM=0`.

Active full run:

```bash
cd /work/dfm/HRM-Text
tmux attach -t sapient_anonymization_8gpu
```

Current active log root after the priority/concurrency update:

```text
logs/sapient_anonymization_20260613T082639
```

## `scripts/prepare_posttrain_transform_refine.py`

Prepares the transformation-refinement post-training dataset.

Responsibilities:

- convert CoEdIT and filtered Super-NI rows;
- build synthetic request JSONL files;
- generate synthetic responses against an OpenAI-compatible teacher endpoint;
- convert accepted generated JSONL responses to Parquet;
- support explicit source-target language pairs for synthetic requests:
  `en:en`, `en:da`, `da:da`, `da:en`;
- use separate default English and Danish source roots;
- use special cross-lingual past-tense prompts for `en:da` and `da:en`;
- reject obvious Danish past-tense language leakage as `language_leak`.

Current source-target convention, 2026-06-05:

```text
task_en_en: English source, English answer
task_en_da: English source, Danish answer
task_da_da: Danish source, Danish answer
task_da_en: Danish source, English answer
```

## `scripts/run_posttrain_synthetic_generation_vllm.sh`

Starts one vLLM server per GPU and runs shard workers for synthetic generation.

Responsibilities:

- serve the configured Gemma teacher model over local OpenAI-compatible ports;
- claim request shards from `SHARD_ROOT/pending`;
- write generated JSONL responses to `GENERATED_ROOT`;
- pass `GENERATION_ENDPOINT=chat` to the generator by default;
- clean up vLLM servers on exit.

Update, 2026-06-05: vLLM servers are launched under `setsid`, and cleanup now
terminates the process group and escalates to `SIGKILL` if needed.

## `scripts/run_posttrain_transform_refine_v3_missing_generation.sh`

Launch helper for the next post-training synthetic generation run. It should be
started only when GPUs are free.

Responsibilities:

- use fresh Gemma 4 31B IT at
  `data/models/google/gemma-4-31B-it-fresh-20260604`;
- use `SHARD_ROOT=data/synthetic_request_shards_posttrain_transform_refine_v3_missing`;
- use `GENERATED_ROOT=data/generated_posttrain_transform_refine`;
- generate only the 550k missing/regenerated rows:
  `*_da_da`, `*_da_en`, and `past_tense_rewrite_en_da`.

Command:

```bash
cd /work/dfm/HRM-Text
scripts/run_posttrain_transform_refine_v3_missing_generation.sh
```

## `scripts/run_posttrain_transform_refine_to_1m_vllm.sh`

Added on 2026-06-08. Confidence: high for shell syntax and launch; medium for
end-to-end completion until the active run finishes.

All-8-GPU orchestration for reaching the `posttrain_transform_refine`
`1,000,000` synthetic instruction target with strict judge policy. It:

- starts one local vLLM Gemma 4 31B IT server per GPU;
- generates the pending `550,000` source-target-expanded rows with
  `JUDGE_QUALITY=1`;
- audits English-source generated rows in parallel across the eight servers;
- creates retry requests for every row marked `regenerate_required=true`;

## `export/transformations-*/recreate_dataset.py`

Updated on 2026-06-11. Confidence: high for local file inspection and
`py_compile`.

Each transformation export folder has a self-contained recreation script using
only Python standard-library modules. The script defaults to local
`seeds/source_texts.jsonl.gz`, reads `generation_config.json` for the
source/target language defaults, calls an OpenAI-compatible teacher endpoint,
and judges generated candidates by default. It writes only judge-accepted rows
unless `--no-judge` is explicitly passed for debugging.

Smoke command shape from inside a transformation export folder:

```bash
python recreate_dataset.py \
  --base-url http://127.0.0.1:8100/v1 \
  --model posttrain-gemma-teacher \
  --rows 1000 \
  --output generated/train.jsonl.gz
```

Exact recreation is not expected because teacher sampling and judge outcomes
can vary, but seed selection, prompt templates, and task order are deterministic
for a fixed `--seed`.
- generates judged replacement rows into a separate regeneration output root;
- keeps servers alive across phases and tears them down on script exit.

Default important paths:

```text
MISSING_SHARD_ROOT=data/synthetic_request_shards_posttrain_transform_refine_v3_missing
GENERATED_ROOT=data/generated_posttrain_transform_refine
AUDIT_ROOT=logs/posttrain_transform_refine_generation/audits_to_1m_<timestamp>
REGEN_REQUEST_ROOT=data/synthetic_requests_posttrain_transform_refine_regen_from_audit
REGEN_SHARD_ROOT=data/synthetic_request_shards_posttrain_transform_refine_regen_from_audit
REGEN_GENERATED_ROOT=data/generated_posttrain_transform_refine_regen_from_audit
```

Launched on 2026-06-08 in tmux session `posttrain_to_1m`.

## `scripts/resume_posttrain_transform_refine_to_1m_after_generation.sh`

Added on 2026-06-09. Confidence: high for local launch output.

Recovery helper for the already-completed phase-1 synthetic generation run. It
assumes the original vLLM teacher servers remain alive on ports `8100`-`8107`
and runs phases 2-4 directly:

- audit English-source generated rows from
  `data/generated_posttrain_transform_refine`;
- build regeneration requests for rows marked by the judge;
- shard and run judged regeneration without restarting the existing servers.

Verified active launch:

```bash
cd /work/dfm/HRM-Text
bash scripts/resume_posttrain_transform_refine_to_1m_after_generation.sh \
  2>&1 | tee logs/posttrain_transform_refine_to_1m_resume_20260609T083026.log
```

## `scripts/monitor_posttrain_to_1m_recovery.py`

Added on 2026-06-09. Confidence: high for local tmux output.

Live monitor for the posttrain transform/refine 1M recovery audit. It prints
one line per GPU with audited rows, current file progress, aggregate rate, audit
ETA, and GPU memory/utilization.

Active tmux window:

```bash
tmux attach -t hrm-1
# switch to window 7: posttrain-monitor
```

## `scripts/run_dfm4_xl_ddp_lite_eval_700k.sh`

Added on 2026-06-09. Confidence: high for local shell validation and launch.

Runs the DFM4 XL-DDP `step_700000` lite eval pair:

- no-EMA first, with `EVAL_PREFIX=lite_eval_noema` and
  `DFM_EVAL_PREFIX=lite_dfm_eval_noema`;
- EMA second, with `EVAL_PREFIX=lite_eval_ema` and
  `DFM_EVAL_PREFIX=lite_dfm_eval_ema`;
- syncs both to W&B run `dfm4xlddpclean` in project
  `Original Plus Mixed Danish Instruction Rich L`;
- uses all eight GPUs through `scripts/schedule_multiple_checkpoint_evals.sh`;
- uses the fractional epoch x-axis value `1.9112836727227056`.

Launched in tmux session `dfm4_lite_eval_700k`:

```bash
cd /work/dfm/HRM-Text
scripts/run_dfm4_xl_ddp_lite_eval_700k.sh \
  2>&1 | tee logs/dfm4_lite_eval_700k_20260609.log
```

## `scripts/build_expert_exports.py`

Added on 2026-06-10; export-root note updated on 2026-06-11. Confidence: high.

Builds the self-contained `export/` dataset export package. It creates one
upload-ready subfolder per non-superseded expert/post-training dataset family,
writes a `README.md` dataset card and standalone `recreate_dataset.py` into
each subfolder, and writes chat-template-ready compressed JSONL shards under
`data/*.jsonl.gz`. It does not create symlinks. The 2026-06-10 rebuild uses
file-level parallel Parquet conversion controlled by `EXPERT_EXPORT_WORKERS`
with default `16`.

Synthetic rows are filtered to accepted examples only. Base generated rows
whose `id` appears as a regenerated `original_id` are excluded, and accepted
regeneration rows are included as replacements. Synthetic transformation data
is exported as four source/target language-pair datasets:
`transformations-danish-danish`, `transformations-danish-english`,
`transformations-english-danish`, and `transformations-english-english`.

Validated output after the root rename:

```text
export/ contains 12 dataset folders
find export -type l | wc -l -> 0
find export -type f -name '*.jsonl.gz' | wc -l -> 4187
no export/*.parquet or plain export/*.jsonl files remain
all export/*/recreate_dataset.py files compile with py_compile
```

## `scripts/audit_reordering_datasets.py`

Added on 2026-06-10; prompt audited/revised on 2026-06-11. Confidence: high
for local syntax, row counting, and prompt design; medium until a judge run has
been executed.

Audits the two expert paragraph-reordering exports with an OpenAI-compatible
judge model:

```text
expert/danish-dynaword-paragraph-reordering: 939,361 rows
expert/common-pile-paragraph-reordering:     277,029 rows
```

The script is non-mutating. It reads chat `.jsonl.gz` rows, asks a judge whether
each row is a meaningful supervised paragraph-reordering example, and writes
`logs/expert_reordering_audit/reordering_judge.audit.jsonl` plus
`summary.json`. It rejects rows that are semantically arbitrary, index/catalog
fragments, bibliographies, metadata lists, OCR garbage, too fragmented, or
where the response does not restore the same source content.

Prompt audit result, 2026-06-11: the judge prompt now explicitly distinguishes
topic interest from discourse-ordering usefulness, requires inferable order
from chronology/argument/local coherence, rejects arbitrary alphabetical/list
ordering, and asks for `primary_failure_type` so later filtering can be
diagnosed.

Suggested first pass against a local OpenAI-compatible judge:

```bash
python scripts/audit_reordering_datasets.py \
  --base-url http://127.0.0.1:8100/v1 \
  --model posttrain-gemma-teacher \
  --sample-rate 0.01 \
  --concurrency 8 \
  --audit-root logs/expert_reordering_audit/sample_1pct \
  --force
```

If the sample looks sane, run with `--sample-rate 1.0` or without
`--sample-rate`.

Superseded for the upload export folders: use each dataset folder's
self-contained `recreate_dataset.py audit` / `recreate_dataset.py filter`
commands instead. The standalone reordering audit script remains useful for
local experiments.

## `scripts/run_export_audits_8gpu_vllm.sh`

Added on 2026-06-11. Confidence: high for shell syntax, local script wiring,
and successful 8-GPU audit startup; medium until the full 8-GPU audit
completes.

Runs the judge audit for the eight non-synthetic export datasets:

```text
common-pile-denoising
common-pile-paragraph-reordering
common-pile-prefix-continuation
common-pile-span-filling
danish-dynaword-denoising
danish-dynaword-paragraph-reordering
danish-dynaword-prefix-continuation
danish-dynaword-span-filling
```

It starts one single-GPU vLLM server per dataset/GPU using Gemma 4 31B IT and
then runs each folder's self-contained:

```bash
python recreate_dataset.py audit ...
```

Default model path is
`data/models/google/gemma-4-31B-it-fresh-20260604`, falling back to
`/work/dfm/brainsurgery/models/google/gemma-4-31B-it` if the fresh local copy is
not present. Default served model name is `posttrain-gemma-teacher`.

Example:

```bash
SAMPLE_RATE=1.0 CONCURRENCY=8 bash scripts/run_export_audits_8gpu_vllm.sh
```

Operational update on 2026-06-11: simultaneous startup of eight Gemma 4 31B IT
vLLM servers initially failed in two ways:

- normal vLLM compilation hit a `torch._inductor` autotune failure
  (`CUDA driver error: file not found`);
- eager startup then hit `deep_gemm` import/warmup failure because `CUDA_HOME`
  was not visible.

The runner now supports `VLLM_EXTRA_ARGS`, isolates
`TORCHINDUCTOR_CACHE_DIR`/`TRITON_CACHE_DIR` per GPU under the log root, and
defaults `VLLM_DEEP_GEMM_WARMUP=skip`. The successful launch used:

```bash
SAMPLE_RATE=1.0 \
CONCURRENCY=8 \
GPU_LIST='0 1 2 3 4 5 6 7' \
AUDIT_ROOT_NAME=audit_full \
VLLM_EXTRA_ARGS='--enforce-eager' \
DEEP_GEMM_WARMUP=skip \
bash scripts/run_export_audits_8gpu_vllm.sh
```

The first full-audit attempt also exposed that the exported
`recreate_dataset.py audit` implementation was not safe for large full
datasets: it built a full in-memory job list and submitted one future per row.
The eight folder-local recreate scripts were patched to stream audit jobs and
keep at most `--concurrency * --queue-factor` futures pending. The streamed
path also passes `path.name` rather than a `Path` object into audit rows, so
`json.dumps` succeeds.

Update later on 2026-06-11: the eight folder-local audit scripts also support
stable sharding and skip-existing behavior:

```bash
python recreate_dataset.py audit \
  --num-shards 4 \
  --shard-index 0 \
  --skip-audit audit_full/audit.jsonl \
  ...
```

The shard key is the stable `row_id` (`dataset/train-xxxxx.jsonl.gz:<line>`).
`--skip-audit` can be repeated and loads existing row ids before scanning, so a
rebalance worker can avoid rejudging rows already present in earlier audit
files. This is used by `scripts/rebalance_export_audits.py`.

Each dataset writes `audit_full/audit.jsonl` and `audit_full/summary.json`
inside its own export folder. To create filtered upload data, run inside each
dataset folder:

```bash
python recreate_dataset.py filter \
  --audit audit_full/audit.jsonl \
  --output-root audited \
  --force
```

Filtering keeps only `keep=true` rows. Negatively judged rows, judge errors,
and unaudited rows are excluded.

## `scripts/rebalance_export_audits.py`

Added on 2026-06-11. Confidence: high for syntax, status output, and manual
rebalance launches; medium until all target-token audit runs finish.

Conservative process-level controller for token-targeted export audits. It can:

- report per-dataset accepted-token estimates with `status`;
- watch for the first dataset to cross a token target;
- stop the current monolithic `export_audits_8gpu` tmux session;
- relaunch only unfinished datasets as stable hash shards across the available
  GPUs, with each shard using `--skip-audit` to avoid already-audited rows.

The active watch session was launched as:

```bash
python scripts/rebalance_export_audits.py watch \
  --target-tokens 100000000 \
  --interval-seconds 300 \
  --gpus 0,1,2,3,4,5,6,7
```

This avoids killing a single child audit worker under
`scripts/run_export_audits_8gpu_vllm.sh`, because that parent script owns all
vLLM servers and its cleanup trap would otherwise tear down the full run.

Operational update later on 2026-06-11: rebalance-launched vLLM servers and
audit workers must be started with `start_new_session=True`. Without that,
children from a short-lived controller process can disappear after the
controller exits. The script now detaches both vLLM and audit worker children.

Verified 100M-token rebalance command:

```bash
python scripts/rebalance_export_audits.py rebalance \
  --target-tokens 100000000 \
  --gpus 0,1,2,3,4,5,6,7 \
  --port-base 8600 \
  --stop-current
```

The 2026-06-11 rebalance log root
`logs/export_dataset_audits_rebalance_20260611T193116` launched all eight GPUs
against the six datasets still below the 100M accepted-token target:

```text
GPU4: common-pile-denoising
GPU0/GPU6: common-pile-paragraph-reordering shards 0/2 and 1/2
GPU3: common-pile-prefix-continuation
GPU5: common-pile-span-filling
GPU1/GPU7: danish-dynaword-paragraph-reordering shards 0/2 and 1/2
GPU2: danish-dynaword-prefix-continuation
```

`danish-dynaword-denoising` and `danish-dynaword-span-filling` were already
above 100M estimated accepted tokens and were excluded from that rebalance.

Update later on 2026-06-11: paragraph-reordering exports are capped at 50M
accepted tokens rather than 100M. This is encoded in
`TARGET_TOKENS_BY_DATASET`:

```text
common-pile-paragraph-reordering: 50M
danish-dynaword-paragraph-reordering: 50M
all other export audit datasets: 100M default
```

The `status`, `rebalance`, and `watch` commands use these per-dataset targets.
The watcher also records the initially complete set and only triggers a
rebalance when a newly complete dataset appears, so already-complete datasets
do not cause an immediate rebalance loop. Active cap watcher:

```bash
python scripts/rebalance_export_audits.py watch \
  --target-tokens 100000000 \
  --interval-seconds 300 \
  --gpus 0,1,2,3,4,5,6,7 \
  --port-base 8600
```

tmux session: `export_audit_cap_watch`
log: `logs/export_audit_cap_watch_20260611T214524.log`

Update on 2026-06-12: `scripts/rebalance_export_audits.py` also supports a
manual `--allocation` override in the form
`dataset:gpu,gpu;dataset:gpu`. This was added after
`common-pile-paragraph-reordering` exceeded its 50M cap while still occupying
two GPUs. The ETA-aware rebalance launched at
`logs/export_dataset_audits_rebalance_20260612T064232` with:

```bash
python scripts/rebalance_export_audits.py rebalance \
  --target-tokens 100000000 \
  --gpus 0,1,2,3,4,5,6,7 \
  --port-base 8700 \
  --stop-current \
  --allocation 'common-pile-denoising:0,1;common-pile-prefix-continuation:2,3,4;common-pile-span-filling:5;danish-dynaword-paragraph-reordering:6,7'
```

Resulting allocation:

```text
GPU0/GPU1: common-pile-denoising shards 0/2 and 1/2
GPU2/GPU3/GPU4: common-pile-prefix-continuation shards 0/3, 1/3, 2/3
GPU5: common-pile-span-filling shard 0/1
GPU6/GPU7: danish-dynaword-paragraph-reordering shards 0/2 and 1/2
```

The 2026-06-12 audit generation was stopped manually after the user asked to
pause it. The run is resumable because each dataset-local `audit.jsonl` contains
durable judged `row_id`s and future rebalance launches include all previous
audit files via repeated `--skip-audit`. The stopped log root is:

```text
logs/export_dataset_audits_rebalance_20260612T064232
```

To resume the same ETA-aware allocation later, rerun the same `rebalance`
command above with `--stop-current`; it will skip already-audited rows from
all earlier audit roots.

Debug update on 2026-06-12. Confidence: high for local single-GPU smoke test.
`--enforce-eager` is not required for single-GPU vLLM startup on this machine.
A non-eager Gemma 4 31B IT server on GPU0 successfully loaded, compiled, became
ready, and answered a chat-completions request when launched without
`CUDA_MODULE_LOADING=EAGER`.

The failed/stuck debug launches showed:

- setting `CUDA_MODULE_LOADING=EAGER` caused the EngineCore to spend minutes in
  `torch.cuda._lazy_init()` before model load;
- removing `CUDA_MODULE_LOADING=EAGER` allowed CUDA init, model load,
  `torch.compile`, CUDA graph capture, and API warmup to complete;
- the smoke response to a Danish one-sentence prompt was
  `København er en smuk by.`

Successful debug log root:

```text
logs/vllm_debug_single_gpu_20260612T091958_no_cuda_module_eager
```

Successful launch used GPU0 only, no `--enforce-eager`, and no
`VLLM_DEEP_GEMM_WARMUP=skip`. If scaling back up, use GPUs 0-3 first; GPUs 4-7
were occupied by unrelated HRM OpenAI eval servers during this debug session.

Operational restart on 2026-06-12. Confidence: high for local launch and
process/GPU verification. `scripts/rebalance_export_audits.py` now has a
Boolean `--enforce-eager/--no-enforce-eager` option; default remains
`--enforce-eager` for compatibility with previous runs. After the successful
single-GPU non-eager smoke test, the remaining export audits were restarted on
GPUs 0-3 only, leaving GPUs 4-7 to unrelated HRM eval servers:

```bash
python scripts/rebalance_export_audits.py rebalance \
  --target-tokens 100000000 \
  --gpus 0,1,2,3 \
  --port-base 8900 \
  --allocation 'danish-dynaword-paragraph-reordering:0;common-pile-denoising:1;common-pile-span-filling:2;common-pile-prefix-continuation:3' \
  --no-enforce-eager
```

Launch root:

```text
logs/export_dataset_audits_rebalance_20260612T093058
```

Verified active allocation:

```text
GPU0: danish-dynaword-paragraph-reordering shard 0/1
GPU1: common-pile-denoising shard 0/1
GPU2: common-pile-span-filling shard 0/1
GPU3: common-pile-prefix-continuation shard 0/1
```

## `scripts/filter_all_export_audits.py`

Added on 2026-06-11. Confidence: high for syntax.

Filters the eight export datasets using every `audit*/audit.jsonl` file inside
each dataset folder. This replaces the earlier `export_audit_filter_watch`
tmux watcher, which only knew about `audit_full` and would miss rebalance shard
audit roots.

Run after the desired audit target is reached:

```bash
python scripts/filter_all_export_audits.py
```

## `scripts/audit_dbc_article_datasets.py`

Added on 2026-06-11. Confidence: high for local syntax, schema inspection, and
row counts; medium until a judge run has been executed.

Non-mutating audit for DBC article/author instruction datasets. Defaults:

```text
data/converted_sources/dbc/dbc-farfatterweb.parquet: 2,831 rows
data/converted_sources/dbc/dbc-faktalink.parquet:    5,991 rows
```

The script reads converted Parquet rows with `instruction` and `response`,
then asks an OpenAI-compatible judge whether the row is useful Danish
article-section training data. The prompt is dataset-aware:

- Forfatterweb: response should be a plausible Danish section for the requested
  author/article heading.
- Faktalink: response should be a plausible Danish explanatory article section
  for the requested topic/heading.

It rejects wrong-language, empty, metadata-only, boilerplate, OCR-corrupted,
mostly-reference/URL, unrelated, too-fragmentary, or low-quality article prose.
It does not reject merely because the judge cannot externally verify every
factual claim.

Suggested first pass:

```bash
python scripts/audit_dbc_article_datasets.py \
  --base-url http://127.0.0.1:8100/v1 \
  --model posttrain-gemma-teacher \
  --sample-rate 0.1 \
  --concurrency 8 \
  --audit-root logs/dbc_article_audit/sample_10pct \
  --force
```

## `scripts/transformers_openai_server.py`

Small local OpenAI-compatible chat-completions server for Transformers models.

Responsibilities:

- serve `/health`, `/v1/models`, and `/v1/chat/completions`
- load text-capable image/text Transformers models with `AutoProcessor` and `AutoModelForImageTextToText`
- avoid vLLM when a model path depends on unavailable vLLM/FlashAttention APIs
- serialize generation through a process-local lock

Verified use, 2026-05-24: served `unsloth/gemma-4-E4B-it` as `gemma-4-e4b-judge` on `127.0.0.1:8099` for the `dfm_evals/generative-talemaader` judge model.

```bash
CUDA_VISIBLE_DEVICES=7 python scripts/transformers_openai_server.py \
  unsloth/gemma-4-E4B-it \
  --served-model-name gemma-4-e4b-judge \
  --host 127.0.0.1 \
  --port 8099 \
  --dtype bfloat16 \
  --attn-implementation sdpa \
  --max-new-tokens 512
```

## `scripts/download_training_datasets.py`

Manifest-driven Hugging Face downloader.

Responsibilities:

- download selected groups into `data/downloads/datasets`
- use `HF_TOKEN` from environment for gated datasets
- default dry-run inventory unless `--download` is passed
- groups include `danish`, `synquid`, `nemotron`, `dolci`, `allenai`, `sapient`, `raw`

Current policy:

- Common Pile removed.
- AllenAI WildChat removed.
- `raw` selects only DynaWord.
- Oliver Kinch Danish instruction/backtranslation, QA, summarization, and translation datasets were added on 2026-05-21.

## `scripts/build_filtered_source_tree.py`

Builds `data/filtered_sources` from `data/downloads/datasets`.

Responsibilities:

- apply `config/data/source_filter.yaml`
- create symlinks by default
- apply `allow_overrides` before `deny`
- update incrementally by default; `--force` still removes and rebuilds the output tree

## `scripts/convert_filtered_sources.py`

Converts filtered source files to HRM tokenizer schema.

Responsibilities:

- write `data/converted_sources`
- normalize mixed schemas to `condition/instruction/response`
- expand chat `messages` into one row per assistant turn
- convert DynaWord `text` to empty-instruction continuation chunks
- convert `prompt`/`target` backtranslation datasets to direct instruction rows
- convert Danish extractive QA `context`/`question`/`answers` rows to direct instruction rows
- convert Danish translation datasets bidirectionally from `danish` plus `english`, `ukrainian`, or `arabic`
- convert selected local DBC `.jsonl.gz` files:
  - `dbc-abstracts_*` to bibliographic abstract-writing rows
  - `dbc-reviews` to bibliographic review-writing rows
  - `dbc-faktalink` and `dbc-farfatterweb` to section-title/body article rows
- convert local LexDK articles to Danish encyclopedia-writing rows
- convert local OPUS Danish/English direct paired JSONL (`opus_da_en.jsonl.gz` with `da` and `en` fields) to bidirectional translation rows; older split-side `opus-da_*`/`opus-en_*` handling remains as a fallback
- parallelize by source file with `--workers`
- update incrementally by default; existing outputs are skipped when they are current, and new conversions write a `.convert_meta.json` sidecar
- legacy outputs created before `.convert_meta.json` existed are treated as current when the output mtime is newer than or equal to the source mtime

Recommended command:

```bash
python scripts/convert_filtered_sources.py --copy-ready --workers 32
```

Use `--force` only for an intentional full rebuild.

## `scripts/prepare_40b_sapient_plus_danish.py`

Earlier end-to-end preparation experiment for Sapient + DynaWord.

Status: partially superseded by the new download/filter/convert/tokenize pipeline. Keep as reference for token-budgeted Sapient/Danish selection logic.

## `scripts/reproduce_original_sapient_l.sh`

Runnable command ledger for the original Sapient HRM-Text L reproduction run.

Responsibilities:

- download the Sapient cleaned corpus with `scripts/download_training_datasets.py --groups sapient --download`
- tokenize `data/downloads/datasets/sapient_cleaned/data_clustered` and `data/downloads/datasets/sapient_cleaned/data` directly into `data/tokenized_original_sapient`
- verify the expected `5212` tokenized metadata files
- sample into `data/sampled_original_sapient` with `epochs=4`
- launch the L-size `torchrun` command with `data=original_sapient`, `arch/size@arch=L`, `global_batch_size=172032`, and checkpoints under `checkpoints/original_sapient/L`
- use Hydra append overrides for optional train fields: `+project_name=...`, `+run_name=...`, and `+checkpoint_path=...`

Usage:

```bash
scripts/reproduce_original_sapient_l.sh --help
scripts/reproduce_original_sapient_l.sh sample
scripts/reproduce_original_sapient_l.sh train
```

## `scripts/build_tokenized_original_plus_mixed_tree.py`

Builds the third tokenized dataset view, `data/tokenized_original_plus_mixed`, from existing tokenized outputs.

Responsibilities:

- symlink all task directories from `data/tokenized_original_sapient`
- symlink non-Sapient task directories from `data/tokenized_mixed`
- skip mixed `sapient_cleaned__*` task directories by default so the full original Sapient tokenization and the filtered mixed Sapient subset are not sampled twice
- write `data/tokenized_original_plus_mixed/union_manifest.json`
- refuse paths outside the repo

Verified command:

```bash
cd /work/dfm/HRM-Text
python scripts/build_tokenized_original_plus_mixed_tree.py --force
```

Verified 2026-05-23 output:

```text
Original tasks linked:       5,212
Mixed tasks linked:          226
Mixed Sapient tasks skipped: 1,139
Name collisions skipped:     0
```

## `scripts/generate_dfm2_dynaword_tasks.py`

Generates DFM2 self-supervised DynaWord task sources.

Responsibilities:

- read converted DynaWord continuation rows from `data/converted_sources/danish_dynaword`
- rechunk raw text to smaller task chunks, default `3000` chars
- write separate `condition/instruction/response` Parquet trees under `data/converted_sources_dfm2_dynaword_tasks`
- create two prefix-continuation variants, two denoising variants, and six span-fill variants
- cap rows per source file to the DFM2 sampling budget: `60k` for each prefix-continuation variant, `30k` for each denoising variant, and `30k` for each span-fill variant
- avoid sampler-level `repeat: 2` for generated task families; unique generated variants are used instead of duplicated sampled rows

Command:

```bash
cd /work/dfm/HRM-Text
python scripts/generate_dfm2_dynaword_tasks.py \
  --output-root data/converted_sources_dfm2_dynaword_tasks \
  --force
```

Verified 2026-05-30 full generation output: `450` Parquet files and `13G`.

## `scripts/build_tokenized_dfm2_tree.py`

Builds the DFM2 tokenized dataset view, `data/tokenized_dfm2`.

Responsibilities:

- symlink all task directories from `data/tokenized_mixed`
- symlink generated DFM2 task directories from `data/tokenized_dfm2_dynaword_tasks`
- write `data/tokenized_dfm2/union_manifest.json`

Command:

```bash
cd /work/dfm/HRM-Text
python scripts/build_tokenized_dfm2_tree.py --force
```

## `scripts/generate_dfm3_common_pile_tasks.py`

Generates DFM3 self-supervised English raw-text task sources from converted
Common Pile continuation rows.

Responsibilities:

- read converted Common Pile rows from `data/converted_sources/common_pile_*`
- rechunk raw text to smaller task chunks, default `3000` chars
- write `condition/instruction/response` Parquet trees under
  `data/converted_sources_dfm3_common_pile_tasks`
- create one direct-continuation category, one prefix-continuation category,
  one denoising category, and three span-fill variants
- use English instructions for generated tasks

Command:

```bash
cd /work/dfm/HRM-Text
python scripts/generate_dfm3_common_pile_tasks.py \
  --output-root data/converted_sources_dfm3_common_pile_tasks
```

Smoke test, 2026-05-31:

```bash
python scripts/generate_dfm3_common_pile_tasks.py \
  --limit-files 0 \
  --output-root /tmp/dfm3_common_pile_smoke \
  --force
```

returned `{}` and exited successfully.

## `scripts/build_tokenized_dfm3_tree.py`

Builds the DFM3 tokenized dataset view, `data/tokenized_dfm3`.

Responsibilities:

- symlink task dirs from `data/tokenized_mixed`
- symlink DFM2 generated DynaWord task dirs from
  `data/tokenized_dfm2_dynaword_tasks`
- symlink DFM3 generated Common Pile task dirs from
  `data/tokenized_dfm3_common_pile_tasks`
- write `data/tokenized_dfm3/union_manifest.json`

Command:

```bash
cd /work/dfm/HRM-Text
python scripts/build_tokenized_dfm3_tree.py --force
```

## `scripts/prepare_dfm3_english_recovery.sh`

Stage runner for the DFM3 English-recovery data pipeline.

Responsibilities:

- inventory/download selected Common Pile datasets
- run filtering and incremental conversion
- generate Common Pile self-supervised tasks
- tokenize generated DFM3 tasks with one worker
- build the DFM3 tokenized union
- sample `data/sampled_dfm3`

Validated on 2026-05-31 with `bash -n`.

## `scripts/generate_dfm4_tasks.py`

Generates additive DFM4 task sources.

Responsibilities:

- generate paragraph-reordering tasks from converted DynaWord and selected
  converted Common Pile rows
- generate arXiv paper-to-abstract summarization tasks from locally downloaded
  Common Pile arXiv paper JSON shards
- generate GovReport, WikiCatSum, and LAION Scientific-Summaries summarization
  tasks when those HF datasets are downloaded under `data/downloads/datasets`
- write PrefixLM-compatible `condition/instruction/response` Parquet trees
  under `data/converted_sources_dfm4_paragraph_reorder` and
  `data/converted_sources_dfm4_summarization`
- cap generation by rows per source file and by scanned rows per file so sparse
  paragraph sources cannot stall an entire generation pass
- support `--only {all,paragraph,summarization,laion}` for targeted
  regeneration, and `--laion-workers` for parallel LAION Scientific-Summaries
  conversion
- preserve response space for long summarization rows by using compact LAION
  fallbacks when full structured summaries do not fit the 4k-context training
  format
- for paragraph reordering, split the full document into paragraphs before
  trimming and sample deterministic contiguous paragraph windows instead of
  using only the beginning of long documents

Smoke test, 2026-06-01:

```bash
cd /work/dfm/HRM-Text
python scripts/generate_dfm4_tasks.py --force \
  --paragraph-output-root data/tmp_dfm4_paragraph_smoke \
  --summary-output-root data/tmp_dfm4_summary_smoke \
  --dynaword-rows-per-file 1 \
  --common-pile-rows-per-file 1 \
  --arxiv-summary-rows-per-file 1 \
  --laion-rows-per-file 1 \
  --max-rows-scanned-per-file 500 \
  --limit-files 1
```

This produced one DynaWord paragraph-reorder row and one arXiv summary row
from already downloaded local sources. GovReport, WikiCatSum, and LAION rows
were absent in the smoke test because those downloads had not yet been run.

Verified full LAION regeneration command, 2026-06-01:

```bash
cd /work/dfm/HRM-Text
python scripts/generate_dfm4_tasks.py --only laion --force --laion-workers 16
```

This wrote `4006` LAION task files and `2,288,807` rows under
`data/converted_sources_dfm4_summarization/dfm4_laion_scientific_summaries`.

## `scripts/build_tokenized_dfm4_tree.py`

Builds the DFM4 tokenized dataset view, `data/tokenized_dfm4`.

Responsibilities:

- symlink all task dirs from `data/tokenized_dfm3`
- symlink DFM4 paragraph-reordering task dirs from
  `data/tokenized_dfm4_paragraph_reorder`
- symlink DFM4 summarization task dirs from
  `data/tokenized_dfm4_summarization`
- write `data/tokenized_dfm4/union_manifest.json`
- traverse source roots with `os.walk(..., followlinks=True)`, because
  `data/tokenized_dfm3` is itself a symlink union. The initial `Path.rglob`
  implementation linked `0` DFM3 tasks from the symlinked root and was
  superseded on 2026-06-01.

Verified 2026-06-01 output:

```json
{
  "output": "data/tokenized_dfm4",
  "roots": [
    {"linked_tasks": 4689, "root": "data/tokenized_dfm3"},
    {"linked_tasks": 25, "root": "data/tokenized_dfm4_paragraph_reorder_dynaword_windows"},
    {"linked_tasks": 425, "root": "data/tokenized_dfm4_paragraph_reorder_common_existing"},
    {"linked_tasks": 4019, "root": "data/tokenized_dfm4_summarization"}
  ],
  "total_tasks": 9158
}
```

## `scripts/prepare_dfm4_paragraph_and_summarization.sh`

Stage runner for the DFM4 paragraph-reordering and summarization pipeline.

Responsibilities:

- inventory/download `govreport_summarization`, `wiki_cat_sum`, and
  `laion_scientific_summaries`
- generate DFM4 task sources
- tokenize DFM4 paragraph and summarization roots with one worker by default
- build the DFM4 tokenized union
- sample `data/sampled_dfm4` with `data_io/prefix_config_dfm4.yaml`

Validated on 2026-06-01 with `bash -n`.

## `data_io/sample_tokenized.py`

Samples tokenized task directories into HRM training data.

Local note, 2026-05-23: `concat_workers` is now a CLI config field. Use it to throttle the initial `tokens.npy` concatenation copy phase on shared storage, for example:

```bash
cd /work/dfm/HRM-Text/data_io
ionice -c2 -n7 nice -n 10 python sample_tokenized.py \
  tokenized_path=../data/tokenized_original_plus_mixed \
  output_path=../data/sampled_original_plus_mixed \
  epochs=4 \
  concat_workers=4 \
  > ../data/show_analytics_original_plus_mixed.md
```

## `scripts/cleanup_failed_training_run.sh`

Dry-run-by-default helper for removing local artifacts from failed training runs.

Responsibilities:

- remove a selected local W&B run directory
- remove W&B convenience symlinks only when they point at the selected run
- remove a selected checkpoint directory
- refuse paths outside `REPO_ROOT`
- refuse `data/` and `data_io/` paths

Current known failed original-L target:

```bash
scripts/cleanup_failed_training_run.sh --original-l-latest
scripts/cleanup_failed_training_run.sh --original-l-latest --execute
```

## `scripts/debug_nan_training_step.py`

Short distributed diagnostic for NaN training failures.

Responsibilities:

- compose the normal Hydra training config
- initialize distributed/FSDP training through `pretrain.py`
- run a bounded number of real data batches without W&B or checkpoints
- optionally use the production `pretrain.train_batch` compiled path with `--compiled-train-batch`
- report supervised token counts and finite checks for metrics, gradients, parameters, and post-optimizer parameters

Known useful command:

```bash
CUDA_VISIBLE_DEVICES=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
torchrun --nproc_per_node=1 scripts/debug_nan_training_step.py \
  --steps 12 \
  --compiled-train-batch \
  --override data=original_sapient \
  --override arch/size@arch=L \
  --override lr=2.5e-4 \
  --override global_batch_size=21504
```

## `scripts/merge_original_l_wandb_history.py`

Local-only W&B datastore merge helper for the original Sapient L run.

Responsibilities:

- read the original training W&B datastore for run `76sygh18`
- read the corrected eval backfill datastore for the same run
- omit the first bad eval backfill datastore with dotted metric keys
- write a merged local `.wandb` datastore and an inspection-friendly `history.jsonl`
- copy local `files/` and `logs/` sidecars from the original training run
- optionally rewrite local run id, project, and display name for a separate upload
- drop bad dotted eval summary updates from the corrected eval-backfill datastore before writing the merged copy
- avoid mutating or deleting any original W&B run directory

Verified command:

```bash
cd /work/dfm/HRM-Text
scripts/merge_original_l_wandb_history.py --force
```

Prepare a separate local copy for the ongoing mixed-run project:

```bash
scripts/merge_original_l_wandb_history.py \
  --output-dir wandb/merged-20260524-76sygh18-clean-for-ongoing \
  --target-project "Original Plus Mixed Danish Instruction Rich L" \
  --target-run-id origLclean \
  --target-run-name original-sapient-L-clean-history \
  --force
```

Verified output:

```text
wandb/merged-20260524-76sygh18-clean/run-76sygh18-clean-merged.wandb
wandb/merged-20260524-76sygh18-clean/history.jsonl
wandb/merged-20260524-76sygh18-clean/manifest.json
wandb/merged-20260524-76sygh18-clean-for-ongoing/run-origLclean.wandb
```

## `scripts/hrm_openai_server.py`

OpenAI-compatible HTTP shim for one HRM checkpoint.

Responsibilities:

- load one HRM checkpoint epoch with `evaluation.engines.SimpleEngine`
- expose `/health`, `/v1/models`, `/v1/chat/completions`, and `/v1/completions`
- micro-batch concurrent OpenAI-compatible requests with `--batch-size` and `--batch-timeout-ms`
- trim returned text on OpenAI-style stop strings

Dependency note: `fastapi` and `uvicorn` were added to `pyproject.toml` for this shim. Confidence: high.

Verified syntax:

```bash
python -m py_compile scripts/hrm_openai_server.py
```

2026-06-12 EuroEval compatibility update. Confidence: high for local source
inspection and syntax check. EuroEval/LiteLLM sends OpenAI-style
`max_completion_tokens` for generation length limits; EuroEval's task configs
set short limits for classification/multiple-choice tasks and larger limits
for summarization, translation, instruction following, etc. The HRM
OpenAI-compatible server previously only read `max_tokens`, so
`max_completion_tokens` was silently ignored by Pydantic and missing requests
fell back to the server `--max-context` cap. `scripts/hrm_openai_server.py` now
accepts both `max_tokens` and `max_completion_tokens`, preferring
`max_tokens` if both are supplied. Verification:

```bash
cd /work/dfm/HRM-Text
PYTHONDONTWRITEBYTECODE=1 python -m py_compile scripts/hrm_openai_server.py
```

## `scripts/log_dfm_evals_to_wandb.py`

Logs dfm-evals Every Eval Ever JSON exports to W&B under a non-`eval` prefix.

Responsibilities:

- read `.json` records under an EEE export directory
- collect numeric `evaluation_results[].score_details.score` values
- log metrics as `<prefix>/<task>/<scorer>/<metric>`, defaulting to `dfm_eval/...`
- resume W&B run `origLclean` in project `Original Plus Mixed Danish Instruction Rich L` by default

Verified syntax:

```bash
python -m py_compile scripts/log_dfm_evals_to_wandb.py
```

## `scripts/sync_completed_dfm_evals.py`

Incremental dfm-evals W&B sync helper.

Responsibilities:

- scan an Inspect log directory for completed `.eval` zip files
- require `header.json`, `summaries.json`, and `reductions.json` before treating a log as complete
- export each completed test to a per-test Every Eval Ever directory
- call `scripts/log_dfm_evals_to_wandb.py` so completed tests are logged to W&B before the full epoch finishes
- write `.synced/*.done` marker files under the chosen sync root to avoid duplicate incremental logging

Verified syntax:

```bash
python -m py_compile scripts/sync_completed_dfm_evals.py
```

## `scripts/run_dfm_evals_on_checkpoints.sh`

DFM eval runner for HRM checkpoints.

Current task note, 2026-05-28:

- `hrm_code_humaneval` is available in `config/dfm_evals_hrm_single_tasks.yaml`.
- It routes to `dfm_evals/humaneval`, which uses `inspect-evals` HumanEval and
  executes generated Python in a Docker sandbox by default.

Example command shape:

```bash
cd /work/dfm/HRM-Text
CKPT_PATH=checkpoints/original_plus_mixed_danish_instruction_rich/L \
EPOCHS="4" \
GPU=0 \
MODEL_PREFIX=hrm-original-plus-mixed-L \
SUITE_FILE=config/dfm_evals_hrm_single_tasks.yaml \
SUITE=hrm_code_humaneval \
LOG_ROOT=logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_humaneval \
WANDB_RUN_ID=es1od1in \
WANDB_RUN_NAME=original-plus-mixed-danish-instruction-rich-L \
FINAL_WANDB_SYNC=1 \
scripts/run_dfm_evals_on_checkpoints.sh
```

Confidence: high for registration and command shape; medium for full execution
until Docker/sandbox availability is verified on the target node.

End-to-end wrapper for dfm-evals on HRM checkpoints.

Responsibilities:

- use or clone `dfm-evals`
- start `scripts/hrm_openai_server.py` for each requested checkpoint epoch
- run a dfm-evals suite against the shim as an `openai/<model>` endpoint
- pass `--max-connections` to Inspect so concurrent sample requests can be micro-batched by the shim
- export Inspect logs to Every Eval Ever JSON
- start `scripts/sync_completed_dfm_evals.py` by default so each completed test is exported and logged to W&B under `dfm_eval/...`
- export full Inspect logs to Every Eval Ever JSON at the end for archival use

Default suite:

```text
config/dfm_evals_hrm.yaml: hrm_danish
```

This suite intentionally avoids judge-only and long-context dfm-evals tasks. The original HRM L checkpoints expose a 4096-token context, while the upstream `fundamentals` suite includes RULER 8192/32768 tasks and judge-dependent tasks. Confidence: high for script behavior; medium until a full dfm-evals run completes.

Runtime note, 2026-05-24: the dfm-evals registry in the cloned checkout exposed task ids as `dfm_evals/...`, so `config/dfm_evals_hrm.yaml` uses names like `dfm_evals/danish-citizen-tests`. The local dfm-evals checkout was patched for the public Danish citizen tests dataset schema (`option_a`, `option_b`, `option_c`) and for anonymous HF fallback when no token is present. Confidence: high.

Superseded batching note, 2026-05-24: Danish citizen tests was initially capped to `250` samples by a suite-level `--limit 250`.

Current batching and sync note, 2026-05-24: the suite-level limit was removed so task defaults are used. The wrapper default is `BATCH_SIZE=8`, `INSPECT_MAX_CONNECTIONS=8`, and `BATCH_TIMEOUT_MS=25`, allowing the server to coalesce concurrent Inspect requests into HRM generation batches. The wrapper also defaults to `INCREMENTAL_WANDB_SYNC=1`, `SYNC_INTERVAL_SECONDS=30`, and `FINAL_WANDB_SYNC=0`; this logs each completed test during the run and avoids re-logging the whole epoch at the end. Confidence: high.

Judge note, 2026-05-24: `config/dfm_evals_hrm.yaml:hrm_danish` includes `dfm_evals/generative-talemaader`, which requires a judge model. The wrapper accepts `JUDGE_MODEL` and `JUDGE_BASE_URL` and forwards them as dfm-evals suite placeholders. If `JUDGE_MODEL` is omitted, the suite should fail early instead of silently using an implicit judge. Confidence: high.

Example smoke command:

```bash
cd /work/dfm/HRM-Text
INSTALL=1 EPOCHS="4" scripts/run_dfm_evals_on_checkpoints.sh -- --limit 10
```

Full default command:

```bash
cd /work/dfm/HRM-Text
scripts/run_dfm_evals_on_checkpoints.sh
```

## `scripts/report_eval_progress.py`

Added on 2026-05-29. Confidence: high for standard eval tqdm parsing; medium
for queued-job ETA because it uses historical runtime weights.

Estimates progress for the active queued checkpoint eval scheduler from:

- `logs/eval/dfm_L_epoch1_queued_all/status.tsv`
- `logs/eval/dfm_L_epoch1_queued_all/jobs.tsv`
- standard shard log tqdm counters such as `generation ... 93/165`

It reports completed/active/queued job counts, active job progress and per-job
ETA, plus a full-evaluation ETA using an 8-lane greedy simulation. DFM/Inspect
active job progress is currently estimated from elapsed time and historical
weights unless the task writes a machine-readable progress counter.

Command:

```bash
cd /work/dfm/HRM-Text
python scripts/report_eval_progress.py
```

Verified immediately after DFM CP1 scheduler launch:

- parsed 8 active GSM8k shards,
- read live tqdm counters such as `93/165`,
- reported `completed=0`, `active=8`, `queued=104`, `total_visible=112`,
- estimated full ETA around `2h57m` from 2026-05-29 15:50 Europe/Berlin.

## `scripts/prepare_posttrain_transform_refine.py`

Added on 2026-06-04. Confidence: high for local conversion/request-generation
execution; medium for later teacher-model generation until run.

Prepares the `posttrain_transform_refine` dataset family. Subcommands:

- `convert-existing`: converts `grammarly/coedit` and a filtered
  transformation-style subset of `Muennighoff/natural-instructions` into ready
  `condition/instruction/response` Parquet.
- `make-synthetic-requests`: builds teacher-model request JSONL files for five
  transformation tasks in Danish and English.
- `export-seed-texts`: writes the English and Danish source-text pools used for
  synthetic request generation to JSONL plus a manifest.
- `shard-synthetic-requests`: splits request JSONL files into small queue
  shards for multi-GPU teacher generation.
- `generate-synthetic`: calls an OpenAI-compatible teacher model endpoint,
  intended for Gemma 4 31B or 26B-A3.
- `audit-generated`: rejudges accepted generated JSONL rows through an
  OpenAI-compatible judge endpoint and writes non-mutating audit JSONL plus a
  summary.
- `convert-generated`: writes accepted synthetic generations to ready Parquet.

Verified local outputs:

```text
posttrain_coedit rows: 70,783
posttrain_superni_filtered rows: 500,000 across 64 tasks
synthetic request files: 10 x 50,000 requests
synthetic request shards: 500 x 1,000 requests
seed export: 1,119,746 English rows and 99,538 Danish rows
```

The audit/regeneration policy is audit-first: generate the remaining pending
rows with `--judge-quality`, then audit the old accepted rows. Any row with an
unhappy judge must be dropped and regenerated; judge-failed rows should not be
converted into the post-training data.

## `scripts/build_tokenized_posttrain_transform_refine_tree.py`

Added on 2026-06-04. Confidence: high.

Builds a filtered tokenized union for post-training. It links only allowlisted
task prefixes from:

```text
data/tokenized_dfm4
data/tokenized_posttrain_transform_refine_existing
data/tokenized_posttrain_transform_refine_synthetic
```

This is necessary because `data_io/sample_tokenized.py` samples unmatched tasks
fully by default; the post-training mix must therefore avoid pointing directly
at the full DFM4 tokenized tree. Verified local manifest linked `4,117` tasks:
`4,115` selected existing DFM4/relevant tasks plus `2` new post-training tasks.

## `scripts/prepare_posttrain_transform_refine.sh`

Added on 2026-06-04. Confidence: high.

Stage runner for the post-training transformation-refine pipeline. Key stages:

```bash
scripts/prepare_posttrain_transform_refine.sh inventory
scripts/prepare_posttrain_transform_refine.sh download-existing
scripts/prepare_posttrain_transform_refine.sh convert-existing
scripts/prepare_posttrain_transform_refine.sh make-synthetic-requests
scripts/prepare_posttrain_transform_refine.sh shard-synthetic-requests
scripts/prepare_posttrain_transform_refine.sh generate-synthetic
scripts/prepare_posttrain_transform_refine.sh convert-synthetic
scripts/prepare_posttrain_transform_refine.sh tokenize-existing
scripts/prepare_posttrain_transform_refine.sh tokenize-synthetic
scripts/prepare_posttrain_transform_refine.sh build-tokenized-tree
scripts/prepare_posttrain_transform_refine.sh sample
```

## `scripts/run_posttrain_synthetic_generation_vllm.sh`

Added on 2026-06-04. Confidence: high for shell syntax and queue design;
medium for full execution until Gemma model path is provided.

Starts one vLLM OpenAI-compatible API server per GPU and runs one shard worker
per GPU. Default queue:

```text
data/synthetic_request_shards_posttrain_transform_refine/pending
```

Default behavior:

- `GPU_LIST=0,1,2,3,4,5,6,7`
- ports `8100..8107`
- `--tensor-parallel-size 1`
- `CLIENT_CONCURRENCY=32` per GPU worker
- atomically claims one shard at a time from `pending`
- writes generated JSONL rows to `data/generated_posttrain_transform_refine`
- moves completed shards to `done` and failed shards to `failed`

Command shape:

```bash
cd /work/dfm/HRM-Text
GEMMA_MODEL_PATH=<hf-id-or-local-path> \
SERVED_MODEL_NAME=posttrain-gemma-teacher \
scripts/run_posttrain_synthetic_generation_vllm.sh
```

## `scripts/run_posttrain_transform_refine_v3_missing_generation.sh`

Added on 2026-06-05. Confidence: high.

Convenience wrapper for generating the remaining source-target-expanded
`posttrain_transform_refine` shards. It uses the fresh local Gemma 4 31B IT
model, the `chat` endpoint, `CLIENT_CONCURRENCY=32`, `JUDGE_QUALITY=1`,
`JUDGE_RETRIES=2`, and writes into:

```text
data/generated_posttrain_transform_refine
```

The queued shard root is:

```text
data/synthetic_request_shards_posttrain_transform_refine_v3_missing
```

## `scripts/report_posttrain_synthetic_generation_progress.py`

Added on 2026-06-04. Confidence: high.

Reports sharded synthetic-generation queue state, generated-row count, and
worker log summaries. Command:

```bash
cd /work/dfm/HRM-Text
python scripts/report_posttrain_synthetic_generation_progress.py
```

## `scripts/schedule_checkpoint_evals.sh`

Updated on 2026-06-06. Confidence: high.

Queues standard HRM evals and dfm-evals onto a GPU worker pool. It supports
lite mode, no-EMA mode, sharded standard/DFM tasks, final merge, and W&B
logging.

Retry behavior now adapts batch size. On the first attempt, the scheduler uses
the highest configured batch size unless telemetry has already shown an OOM for
that task at the current-or-better free-memory level. Successful telemetry at
the same task and lower-or-equal free memory is treated as evidence that the
recorded batch size is safe. If no telemetry exists, the configured batch size
is used rather than falling back to batch size `1`.

On retry attempt `n`, the effective batch size is halved `n` times with a floor
of `1`:

- standard evals: `STANDARD_BATCH_SIZE`
- dfm-evals OpenAI shim server and `--max-connections`: `DFM_BATCH_SIZE`
- IFEval-DA shim server and `--max-connections`: `IFEVAL_BATCH_SIZE`

This means an OOM at batch size `8` will retry at `4`, then `2`, then `1`
within the existing `MAX_RETRIES` limit.

The scheduler also records per-attempt telemetry for future placement decisions
in:

```text
${LOG_ROOT}/eval_attempts.tsv
```

Each row records checkpoint tag, task/shard, GPU, attempt, effective batch
size, status, OOM flag, GPU free/used/total MiB before and after the attempt,
and the primary task log path. This is intended to build a table of highest
non-OOM-proven batch sizes by task and memory headroom.

Operational note from 2026-06-06. Confidence: high. During DFM4 XL-DDP
`step_400000` EMA lite eval, `ARC` first failed on GPU4 at about `6.4 GiB`
free above training even with batch size `1`. Retrying on GPU0 at about
`16.6 GiB` free succeeded at batch size `1`. The subsequent `MMLU` retry was
started on GPU0 at batch size `8` because no telemetry yet showed batch-size
OOM at that free-memory level.

Operational note from 2026-06-07. Confidence: high. Manual one-job retry
commands can still override the scheduler's adaptive first-attempt choice by
setting `DFM_BATCH_SIZE` or `IFEVAL_BATCH_SIZE` directly. During DFM4 XL-DDP
`step_400000` EMA DFM-lite cleanup, WMT24++ en-da was deliberately forced to
`DFM_BATCH_SIZE=1` after batch 2 had OOMed on low-headroom GPUs. GovReport
succeeded at batch 2 on GPU0, where about `16.6 GiB` was free above training.
The adaptive telemetry logic should be treated as the default path for queued
future runs; forced single-job retries are manual finish-the-run decisions.

Updated on 2026-06-08. Confidence: high. `scripts/schedule_multiple_checkpoint_evals.sh`
now supports attaching additional workers to an already-running shared queue:

```text
RESUME_EXISTING_QUEUE=1
SKIP_FINAL_MERGE=1
```

`RESUME_EXISTING_QUEUE=1` preserves the existing `jobs.tsv` and `status.tsv`
instead of rebuilding/truncating them. `SKIP_FINAL_MERGE=1` lets the extra
workers consume queued jobs while leaving final merge to the original scheduler
process. This was added to attach GPU1/GPU4 to the active DFM4 XL-DDP
`step_600000` no-EMA lite eval after the conservative initial launch used only
GPU0/GPU2/GPU7.

Updated on 2026-06-10. Confidence: high. `scripts/schedule_eval_campaign.sh`
adds a TSV-defined campaign queue for mixed eval variants. It delegates each
queued shard to `scripts/schedule_checkpoint_evals.sh` with
`SKIP_FINAL_MERGE=1`, so existing task definitions, retry/OOM-halving,
batch-size overrides, server launch code, and telemetry remain the source of
truth. After all shard jobs finish, it runs `FINAL_MERGE_ONLY=1` once per TSV
variant so each checkpoint/mode uses the intended `NO_EMA`, `LITE_EVAL`,
`EVAL_PREFIX`, and `DFM_EVAL_PREFIX` settings.

The campaign TSV columns are:

```text
variant_id ckpt_tag eval_epoch lite_eval no_ema eval_prefix dfm_eval_prefix log_root dfm_log_root
```

This helper fills the gap left by `scripts/schedule_multiple_checkpoint_evals.sh`,
where EMA/no-EMA, lite/full, and metric prefixes are process-wide settings and
therefore cannot be mixed in one queue.

Updated on 2026-06-10. Confidence: high. `scripts/watch_eval_campaign_progress.py`
monitors a campaign root from `scripts/schedule_eval_campaign.sh`. It prints
queue counts, one active-job line per GPU ordered by GPU id, elapsed active-job
time, live GPU memory/utilization, and the latest scheduler status rows.

## `scripts/summarize_eval_attempt_telemetry.py`

Added on 2026-06-06. Confidence: high.

Summarizes one or more scheduler telemetry TSVs by task, including successes,
OOMs, highest successful batch size, and memory-free statistics:

```bash
cd /work/dfm/HRM-Text
python scripts/summarize_eval_attempt_telemetry.py logs/eval/*/eval_attempts.tsv
```

## EuroEval Local Checkpoint Evaluation

Added on 2026-06-12. Confidence: high for local syntax checks and dry-runs;
medium until a full EuroEval run completes against a checkpoint.

`scripts/run_euroeval_on_checkpoint.sh` runs EuroEval against a local HRM
checkpoint through `scripts/hrm_openai_server.py`. The requested default scope
is Danish and English only:

```text
EUROEVAL_LANGUAGES=da,en
```

The wrapper intentionally does not override EuroEval's standard evaluation
policy by default. In particular, it leaves few-shot/zero-shot choice,
`num_iterations`, and `generative_type` unset unless the corresponding
environment variables are explicitly provided. EuroEval's upstream CLI default
is few-shot with 10 iterations, with internal zero-shot fallback for tasks that
require zero-shot evaluation. The wrapper still passes the local API endpoint,
API key, cache directory, max context length, `--save-results`, and the
requested language filters.

Outputs per checkpoint:

```text
logs/euroeval/.../<CKPT_TAG>/server.log
logs/euroeval/.../<CKPT_TAG>/euroeval.log
logs/euroeval/.../<CKPT_TAG>/euroeval_benchmark_results.jsonl
logs/euroeval/.../<CKPT_TAG>/merged_metrics.json
logs/euroeval/.../<CKPT_TAG>/merge_and_wandb_sync.log
```

`scripts/log_euroeval_to_wandb.py` flattens EuroEval JSONL results to W&B
metrics under `euroeval/<lang>/<task>/<dataset>/...` and records
`euroeval/epoch` as the step metric. It filters to `da` and `en` in the
checkpoint wrapper.

Operational update on 2026-06-12. Confidence: high. Installing EuroEval into
the `hrm` conda environment was done directly because editable install of the
repo extra failed under setuptools' flat-layout package discovery:

```bash
uv pip install euroeval
```

This installed `euroeval==17.3.0` and downgraded `scikit-learn` from `1.8.0`
to `1.6.1`. EuroEval's import guard refuses any visible top-level
`flash_attn` package on non-ROCm builds. This conflicts with the local FA4
install, which provides top-level `flash_attn` from the `flash-attn-4`
distribution. For API-only EuroEval, use
`scripts/euroeval_api_no_flash_attn_guard.py`; it hides `flash_attn` only from
EuroEval's import guard in the EuroEval process. The HRM server process still
runs normally with FA4 visible.

Concurrency update on 2026-06-12. Confidence: high for local source inspection
and syntax check. EuroEval 17.3.0's LiteLLM backend hard-codes
`max_concurrent_calls = 20`. `scripts/euroeval_api_no_flash_attn_guard.py` now
supports `EUROEVAL_MAX_CONCURRENT_CALLS`; when set, it monkeypatches
`LiteLLMModel.__init__` after construction to override
`self.buffer["max_concurrent_calls"]`.

Verification:

```bash
cd /work/dfm/HRM-Text
PYTHONDONTWRITEBYTECODE=1 python -m py_compile scripts/euroeval_api_no_flash_attn_guard.py
```

Example launch using larger server and EuroEval concurrency:

```bash
cd /work/dfm/HRM-Text
EUROEVAL_BATCH_SIZE=32 EUROEVAL_MAX_CONCURRENT_CALLS=32 \
  scripts/run_original_sapient_l_euroeval_epochs.sh
```

## `scripts/queue_epoch_euroevals_on_free_gpus.sh`

Added on 2026-06-12. Confidence: high for local syntax check and launch.

EuroEval-only queue for epoch checkpoints. It watches GPUs 4-7 by default and
launches one `scripts/run_euroeval_on_checkpoint.sh` job whenever a watched GPU
has no active NVIDIA compute process. This lets follow-up EuroEval jobs start
as soon as individual GPUs are freed by an earlier evaluation campaign, without
waiting for every GPU in the old campaign to finish.

Default queued jobs:

```text
checkpoints/dfm/L epoch_1..epoch_4
checkpoints/dfm4/XL-ddp epoch_1..epoch_2
```

Default runtime settings:

```text
GPUS=4,5,6,7
EUROEVAL_BATCH_SIZE=32
EUROEVAL_MAX_CONCURRENT_CALLS=32
EUROEVAL_LANGUAGES=da,en
```

DFM L results sync to W&B project `DFM L`, run id `kgnbdmwf`, run name
`dfm-L`. DFM4 XL results sync to project
`Original Plus Mixed Danish Instruction Rich L`, run id
`dfm4xlddpcleanfixed2`, run name `dfm4-XL-ddp clean corrected history v2`.

Launch command:

```bash
cd /work/dfm/HRM-Text
tmux new-session -d -s queued_dfm_euroevals \
  'cd /work/dfm/HRM-Text && scripts/queue_epoch_euroevals_on_free_gpus.sh'
```

## `scripts/queue_valeu_da_rerun_then_dfm4.sh`

Added on 2026-06-12. Confidence: high for local syntax check and launch.

Priority EuroEval queue used after original Sapient L `epoch_2` completed only
19/20 EuroEval tasks. Local inspection showed the missing result row was
`valeu-da`; `euroeval.log` ended with `Completed 19 benchmarks, and errored 1
benchmarks`. The script watches GPUs 4-7 and runs:

```text
1. original_sapient/L epoch_2, dataset valeu-da only, separate log dir
2. dfm4/XL-ddp epoch_1
3. dfm4/XL-ddp epoch_2
```

The `valeu-da` rerun writes to:

```text
logs/euroeval/original_sapient_L/epoch_2_valeu_da_rerun
```

It intentionally sets `WANDB_SYNC=0` for the one-dataset rerun and does not
modify `logs/euroeval/original_sapient_L/epoch_2/euroeval_benchmark_results.jsonl`.
The row should be inspected and merged separately after success. DFM4 XL jobs
use the same W&B target as the normal queue.

Launch command:

```bash
cd /work/dfm/HRM-Text
tmux new-session -d -s priority_valeu_da_then_dfm4 \
  'cd /work/dfm/HRM-Text && scripts/queue_valeu_da_rerun_then_dfm4.sh'
```

`scripts/run_original_sapient_l_euroeval_epochs.sh` launches the four original
Sapient L epoch checkpoints on GPUs 4-7:

```bash
cd /work/dfm/HRM-Text
tmux new-session -d -s orig_sapient_l_euroeval \
  'cd /work/dfm/HRM-Text && scripts/run_original_sapient_l_euroeval_epochs.sh'
```

Defaults:

```text
CKPT_PATH=checkpoints/original_sapient/L
epochs: epoch_1, epoch_2, epoch_3, epoch_4
GPUs:   4, 5, 6, 7
EUROEVAL_LANGUAGES=da,en
WANDB_PROJECT=Original Plus Mixed Danish Instruction Rich L
WANDB_RUN_ID=origLclean
WANDB_RUN_NAME=original-sapient-L-clean-history
```

The launch does not set `EUROEVAL_FEW_SHOT`, `EUROEVAL_NUM_ITERATIONS`, or
`EUROEVAL_GENERATIVE_TYPE`, so EuroEval uses its standard defaults. Initial
logs showed EuroEval running few-shot and reporting `1/20 benchmarks`, with
all four HRM servers healthy on ports `9741`-`9744`.

`scripts/schedule_checkpoint_evals.sh` and
`scripts/schedule_multiple_checkpoint_evals.sh` support opt-in EuroEval jobs:

```bash
cd /work/dfm/HRM-Text
RUN_EUROEVAL=1 scripts/schedule_checkpoint_evals.sh
```

If EuroEval is not installed in the active environment, either install the repo
extra or use an explicit command:

```bash
uv pip install -e '.[euroeval]'
EUROEVAL_BIN='uv run --no-project --with euroeval euroeval' RUN_EUROEVAL=1 scripts/schedule_checkpoint_evals.sh
```

## `scripts/rebalance_export_audits.py`

Operational update on 2026-06-12. Confidence: high.

The export audit/generation run is currently guarded by an automatic watcher
that scans every 10 minutes and rebalances only after a currently open dataset
first reaches its token target. The current generation uses non-eager vLLM on
GPUs 0-3 only.

Active run root:

```text
logs/export_dataset_audits_rebalance_20260612T093058
```

Active allocation:

```text
GPU0: danish-dynaword-paragraph-reordering
GPU1: common-pile-denoising
GPU2: common-pile-span-filling
GPU3: common-pile-prefix-continuation
```

Watcher command:

```bash
cd /work/dfm/HRM-Text
setsid bash -lc 'exec python scripts/rebalance_export_audits.py watch \
  --target-tokens 100000000 \
  --gpus 0,1,2,3 \
  --port-base 8900 \
  --interval-seconds 600 \
  --no-enforce-eager \
  >> logs/export_dataset_audits_watch_20260612T102445_gpus0123.log 2>&1' \
  </dev/null >/dev/null 2>&1 &
echo $! > logs/export_dataset_audits_watch_20260612T102445_gpus0123.pid
```

Superseded: an attempted 8-GPU rebalance was started when GPUs 4-7 appeared
free. The user clarified that export audit generation must use only GPUs 0-3.
The 8-GPU attempt was stopped before any persistent 9000-series audit workers
remained, GPU 4-7 HRM EuroEval servers were terminated, and the watcher was
restarted with `--gpus 0,1,2,3` only.

Initial watcher status:

```text
complete: common-pile-paragraph-reordering, danish-dynaword-denoising,
          danish-dynaword-prefix-continuation, danish-dynaword-span-filling
open:     common-pile-denoising, common-pile-prefix-continuation,
          common-pile-span-filling, danish-dynaword-paragraph-reordering
```

Most recent full status before watcher launch:

```text
common-pile-denoising                          72.1M/100.0M open
common-pile-prefix-continuation                63.4M/100.0M open
common-pile-span-filling                       71.9M/100.0M open
danish-dynaword-paragraph-reordering           41.8M/50.0M  open
```

The full `status` command is filesystem-heavy because it rereads all historical
audit JSONL files. Use it sparingly while the WEKA filesystem is under load.

Manual denoising speed-up on 2026-06-12. Confidence: high.

The user explicitly authorized using GPUs 6 and 7 to speed up only
`common-pile-denoising`. The previous single denoising client on GPU1 was
stopped, the 0-3 watcher was paused to avoid conflicting process control, and
`common-pile-denoising` was relaunched as three hash shards:

```text
GPU1: shard 0/3, existing vLLM server on port 8900
GPU6: shard 1/3, new vLLM server on port 8916
GPU7: shard 2/3, new vLLM server on port 8917
```

Run root:

```text
logs/export_denoising_gpus167_20260612T131403
```

The GPU6/GPU7 servers were started without `--enforce-eager` and became
healthy. Initial verification showed GPU1/GPU6/GPU7 at 100% utilization and
GPU6/GPU7 generation throughput around 275-290 tokens/s.

Operational note on 2026-06-12. Confidence: high.

`danish-dynaword-paragraph-reordering` can appear stuck near `49.8M/50M`
accepted estimated tokens even while the worker is healthy. At 13:39 local
time the audit log was still advancing (`judged 38400`), the audit file mtime
was current, and the GPU0 vLLM server was serving at roughly 430-455 generation
tokens/s. The accepted-token total was flat because recent rows were rejected,
with the latest inspected rows marked `wrong_language`.

Manual span-filling speed-up on 2026-06-12. Confidence: high.

After `danish-dynaword-paragraph-reordering` exceeded its 50M target, the user
asked to stop that audit and reuse GPU0 for `common-pile-span-filling`. The
Danish paragraph audit client was stopped, its vLLM server on GPU0/port 8903
was kept alive, the previous single span-filling client on GPU2 was stopped,
and `common-pile-span-filling` was relaunched as two hash shards:

```text
GPU2: shard 0/2, existing vLLM server on port 8902
GPU0: shard 1/2, existing vLLM server on port 8903
```

Run root:

```text
logs/export_span_gpus02_20260612T140630
```

Initial verification showed GPU0 and GPU2 at 100% utilization, both span
shards reaching `judged 100`, and server throughput around 200-305 generation
tokens/s.

Gemma 4 E2B external-baseline metric caveat, 2026-06-17. Confidence: high for
local merged metrics and source inspection; medium for exact model-behavior
interpretation because the standard eval logs do not persist generated text.

The completed Gemma 4 E2B baseline under:

```text
logs/eval/gemma4_e2b_full_20260617
logs/dfm_evals/gemma4_e2b_full_20260617
logs/euroeval/gemma4_e2b_full_20260617
```

shows a split pattern: several EuroEval tasks produce plausible nonzero scores
(`bfcl-v2` tool accuracy `37.4`, `cnn-dailymail` chrF++ `36.0`,
`conll-en` micro-F1 `55.7`, `sst5` macro-F1 `49.4`), while many standard
HRM-Text evals are dominated by invalid parsing. Examples:

```text
eval/BoolQ/acc=0.5,     eval/BoolQ/invalid=1.0
eval/MATH/acc=0.0034,   eval/MATH/invalid=1.0
eval/GSM8k/acc=0.0076,  eval/GSM8k/invalid=0.7650
eval/HellaSwag/acc=0.2566, eval/HellaSwag/invalid=0.8813
eval/Winogrande/acc=0.5036, eval/Winogrande/invalid=0.6504
```

This should be treated as an evaluation-harness compatibility problem before
being treated as a model-quality result. The standard external path uses
`evaluation.engines.OpenAIEngine`, which sends the benchmark prompt as one chat
`user` message, while `evaluation/benchmarks.py` applies strict HRM-oriented
extractors. Standard MCQ benchmarks require an exact single-letter response
after `max_tokens=1`; MATH requires a boxed answer for non-invalid scoring; and
GSM8K only became reliable for Qwen after the scorer was repaired to accept
explicit final-answer patterns and final standalone integers. The earlier Qwen
full run had `eval/GSM8k/invalid=1.0`; the corrected Qwen GSM8K rerun reached
`eval/GSM8k/acc=0.66566` and `eval/GSM8k/invalid=0.0235`, demonstrating that
prompt/extraction can dominate the external standard metrics.

Additional Gemma-specific caveat: the local snapshot advertises
`Gemma4ForConditionalGeneration`, but text-only vLLM serving had to force
`Gemma4ForCausalLM`; the tokenizer snapshot has no `chat_template`, so the plan
used the local fallback template
`evaluation/chat_templates/gemma4_e2b_plain_chat.jinja`. Do not cite the
current Gemma standard scores as official or fair until at least a small
diagnostic rerun saves generations and uses task-specific external-model
prompts/extractors.

Related external-eval code caveat: `OpenAIEngine.generate()` currently ignores
`max_context`, and `_generate_one()` returns an empty string for HTTP 400. This
can turn context-length/server request failures into normal-looking invalid
answers unless the vLLM logs are inspected. A quick search of the Gemma BoolQ
vLLM log showed ordinary `200 OK` responses, so BoolQ's all-invalid result is
more likely answer-format/template mismatch than context overflow; nevertheless
the silent-empty 400 behavior should be fixed before relying on external
baseline standard metrics.

Gemma clean external diagnostic preparation, 2026-06-17. Confidence: high for
local code inspection, `compileall`, and generated-plan inspection. The next
Gemma 4 E2B baseline should run through a separate diagnostic plan after the
current DFM5-L `step_500000` eval finishes:

```bash
cd /work/dfm/HRM-Text
python -m eval_scheduler run \
  --plan-dir logs/scheduler/gemma4_e2b_clean_external_after_500k \
  --gpus 0,1,2,3,4,5,6,7
```

Monitor:

```bash
python -m eval_scheduler monitor \
  --plan-dir logs/scheduler/gemma4_e2b_clean_external_after_500k \
  --interval 30
```

The plan was created by:

```bash
PLAN_DIR=logs/scheduler/gemma4_e2b_clean_external_after_500k \
  bash scripts/create_gemma4_e2b_clean_external_eval_plan.sh
```

It has `207` pending jobs and deliberately uses `log_wandb=false`, so local
artifacts can be inspected before any clean W&B run is created. Important
prepared changes:

- `evaluation/config/external_chat_benchmarking.yaml` defines explicit
  chat-model prompts for the standard evals: MCQ tasks return only an option
  letter, GSM8K ends with `Final answer: <integer>`, and MATH boxes the final
  answer.
- `evaluation/main.py` supports `save_generations_dir=...`; external standard
  scheduler jobs now write per-shard `*.generations.jsonl` files containing
  prompt, generation, and sanitized ground truth.
- `evaluation/benchmarks.py` now accepts conservative MCQ final-answer forms
  (`A`, `A.`, `(A)`, `Answer: A`, `The answer is A`) instead of only exact raw
  letters. This should not change exact-letter HRM outputs, but makes chat-model
  external baselines less brittle.
- `evaluation/engines.py` no longer converts HTTP 400 responses into empty
  strings; bad OpenAI-compatible requests now fail visibly.
- `eval_scheduler plan create-external` accepts `--standard-config`, and the
  scheduler supports `--no-log-wandb` for diagnostic runs.
- `scripts/backfill_external_eval_to_wandb.py` can later log a clean W&B run
  from local merged artifacts once the diagnostic values and saved generations
  look credible.

The generated plan uses the local model
`/work/dfm/brainsurgery/models/google/gemma-4-E2B-it`, served as
`gemma4-e2b-it-clean`, with the same text-only Gemma vLLM overrides:
`--enforce-eager`, `--hf-overrides '{"architectures":["Gemma4ForCausalLM"]}'`,
and `--chat-template evaluation/chat_templates/gemma4_e2b_plain_chat.jinja`.
It also keeps the previous GovReport caps (`dfm_context_length=3968`,
`dfm_max_gen_toks=128`, `max_report_chars=10000`) and
`euroeval_generative_type=instruction_tuned`.

Scoring smoke follow-up, 2026-06-17. Confidence: high for local smoke tests on
cached benchmark rows. The clean external scoring changes were smoke-tested
without using GPUs:

- Conservative MCQ extraction accepts `A`, `A.`, `(B)`, `Answer: C`,
  `Final answer is D`, and `The answer is A`, while rejecting prose such as
  `I think A`.
- Data-backed MCQ smoke on the first 12 rows of `BoolQ`, `Winogrande`, and
  `ARC` with generations of the form `Answer: <gold>` produced `acc=1.0` and
  `invalid=0.0`.
- Data-backed GSM8K smoke on the first 12 cached rows with generations ending
  `Final answer: <gold>` produced `acc=1.0` and `invalid=0.0`.
- Data-backed MATH smoke on the first 12 rows of shard `0/64` with boxed gold
  answers produced `acc=1.0` and `invalid=0.0`.

The smoke exposed and fixed two launch/scoring issues before the Gemma clean
run:

- `evaluation/config/external_chat_benchmarking.yaml` had to escape literal
  braces in the MATH prompt as `\boxed{{}}`; otherwise Python `.format()` treats
  `\boxed{}` as an empty replacement field.
- MATH scoring normalized `\dfrac` and `\tfrac` to `\frac` before calling
  `math_verify.parse()`. Without this, an exact boxed answer such as
  `\boxed{\dfrac{3}{2}}` could be marked wrong because both the ground truth and
  answer parsed to empty lists.

`python -m compileall -q evaluation eval_scheduler
scripts/backfill_external_eval_to_wandb.py` passed after these changes.

Tiny live Gemma standard-smoke preparation, 2026-06-17. Confidence: high for
local config/script syntax and GPU-state inspection; the live smoke itself was
not launched because all GPUs were at 100% utilization and active 500K eval
jobs were already retrying after OOMs.

Prepared files:

```text
evaluation/config/external_chat_smoke.yaml
scripts/run_gemma4_e2b_standard_smoke.sh
```

The smoke uses the clean external-chat standard prompts on only:

```text
BoolQ  20 rows
GSM8K  20 rows
MATH   20 rows from shard 0/64
```

It starts a single local Gemma 4 E2B vLLM server with the same text-only
overrides as the clean full plan, runs `evaluation.main`, and writes
`evaluation.log`, `vllm.log`, and generation JSONL files under
`logs/eval/gemma4_e2b_clean_standard_smoke_<timestamp>/`. Launch once a GPU is
really free:

```bash
cd /work/dfm/HRM-Text
GPU=0 bash scripts/run_gemma4_e2b_standard_smoke.sh
```

Use `VLLM_GPU_MEMORY_UTILIZATION=...` only when deliberately testing on a
partially occupied GPU; default is `0.9`, which is appropriate when the GPU is
free.

Impact note for HRM checkpoint evals. Confidence: high for source inspection.
The clean external prompt config affects only runs that explicitly use
`evaluation/config/external_chat_benchmarking.yaml` or
`evaluation/config/external_chat_smoke.yaml`. `save_generations_dir` and
`max_samples` are inert unless set. The conservative MCQ extraction change can
affect future standard MCQ metrics if an evaluated model emits `Answer: A`,
`(A)`, etc.; existing HRM checkpoint standard evals usually generated exactly
one token for MCQ tasks, so they should be unchanged in practice. The MATH
`\dfrac`/`\tfrac` normalization can affect all future MATH evals slightly by
fixing exact boxed answers that previously parsed to empty lists. The HTTP-400
change affects only `OpenAIEngine` external baselines, not `SimpleEngine` HRM
checkpoint evals. Existing W&B/local metrics are not retroactively changed.

Gemma 4 E2B live standard smoke with batch size 1, 2026-06-17. Confidence:
high for local command output and saved generation inspection. The first
attempt used:

```bash
GPU=3 SMOKE_BATCH_SIZE=1 VLLM_GPU_MEMORY_UTILIZATION=0.25 \
  LOG_ROOT=logs/eval/gemma4_e2b_clean_standard_smoke_bs1_$(date +%Y%m%d_%H%M%S) \
  bash scripts/run_gemma4_e2b_standard_smoke.sh
```

It failed during vLLM startup because GPU3 had only `16.16/178.34 GiB` free,
less than the requested 25% vLLM memory budget. A second attempt succeeded:

```bash
GPU=5 SMOKE_BATCH_SIZE=1 VLLM_GPU_MEMORY_UTILIZATION=0.08 PORT=18645 \
  LOG_ROOT=logs/eval/gemma4_e2b_clean_standard_smoke_bs1_$(date +%Y%m%d_%H%M%S) \
  bash scripts/run_gemma4_e2b_standard_smoke.sh
```

Output directory:

```text
logs/eval/gemma4_e2b_clean_standard_smoke_bs1_20260617_175531
```

Scores:

```text
BoolQ   n=20  acc=0.5000  invalid=1.0000
GSM8K   n=20  acc=0.0000  invalid=0.8000
MATH    n=20  acc=0.0000  invalid=1.0000
```

Saved generations indicate a model serving/prompt-template problem rather than
a scorer-only problem. BoolQ produced 20/20 empty generations. GSM8K had 6/20
empty generations, 7/20 literal placeholder generations such as
`Final answer: <integer>`, and one `Final answer:` loop. MATH had 1/20 empty
generations and 10/20 `Assistant:` label loops. Do not run or backfill the full
Gemma 4 E2B clean external evaluation until the Gemma serving/template path is
fixed and a fresh smoke produces structurally valid outputs.

Gemma 4 native chat-template fix, 2026-06-17. Confidence: high for local
tokenizer rendering and batch-size-1 live smoke. The local E2B snapshot has no
`chat_template` in `tokenizer_config.json`; the previous fallback
`User:`/`Assistant:` template was wrong for Gemma 4. A native Gemma 4 template
from the installed E4B snapshot was copied into:

```text
evaluation/chat_templates/gemma4_native_chat.jinja
```

The template renders prompts as Gemma 4 turns, e.g.:

```text
<bos><|turn>user
...
<turn|>
<|turn>model
```

`scripts/run_gemma4_e2b_standard_smoke.sh`,
`scripts/create_gemma4_e2b_clean_external_eval_plan.sh`, and the two existing
Gemma scheduler plans were updated to reference this native template instead of
`gemma4_e2b_plain_chat.jinja`. The already-completed
`logs/scheduler/gemma4_e2b_then_dfm5_L_500k_20260617` artifacts were produced
before this fix and should be considered stale unless reset and rerun.

Live smoke command:

```bash
cd /work/dfm/HRM-Text
GPU=6 SMOKE_BATCH_SIZE=1 VLLM_GPU_MEMORY_UTILIZATION=0.08 PORT=18646 \
  LOG_ROOT=logs/eval/gemma4_e2b_native_standard_smoke_bs1_$(date +%Y%m%d_%H%M%S) \
  bash scripts/run_gemma4_e2b_standard_smoke.sh
```

Output directory:

```text
logs/eval/gemma4_e2b_native_standard_smoke_bs1_20260617_202216
```

Scores:

```text
BoolQ   n=20  acc=0.6500  invalid=0.0000
GSM8K   n=20  acc=0.7000  invalid=0.0000
MATH    n=20  acc=0.7000  invalid=0.9500
```

Saved generations are now structurally sane: BoolQ generations are single
letters, GSM8K generations are step-by-step answers, and MATH generations are
real derivations rather than empty strings or role-label loops. The remaining
high MATH invalid rate is a scorer/answer-extraction issue to inspect
separately, not the previous Gemma serving-template failure.

Scoring-diff minimization for Gemma external evals, 2026-06-17. Confidence:
high for local `git diff --exit-code -- evaluation/benchmarks.py`, compile
check, and smoke output. Temporary edits to shared benchmark scoring were
removed to avoid changing DFM5-L comparability. `evaluation/benchmarks.py` is
clean relative to HEAD again. Removed temporary changes were:

- lenient GSM8K extraction from final-answer prose or last number
- `\dfrac`/`\tfrac` normalization in MATH
- lenient MCQ parsing of `Answer: A`, `(A)`, etc.

The retained changes are non-scoring support for external diagnostics:
`OpenAIEngine`, `max_samples`, and optional generation JSONL saving. For Gemma
external standard evals, strict scorer compatibility is handled by prompt
templates in `evaluation/config/external_chat_smoke.yaml` and
`evaluation/config/external_chat_benchmarking.yaml`, not by changing the shared
scorers.

Strict-scoring Gemma smoke command:

```bash
cd /work/dfm/HRM-Text
GPU=1 SMOKE_BATCH_SIZE=1 VLLM_GPU_MEMORY_UTILIZATION=0.08 PORT=18647 \
  LOG_ROOT=logs/eval/gemma4_e2b_native_strict_prompt_smoke_bs1_$(date +%Y%m%d_%H%M%S) \
  bash scripts/run_gemma4_e2b_standard_smoke.sh
```

Output directory:

```text
logs/eval/gemma4_e2b_native_strict_prompt_smoke_bs1_20260617_205021
```

Scores under the original strict shared scorers:

```text
BoolQ   n=20  acc=0.6500  invalid=0.0000
GSM8K   n=20  acc=0.1000  invalid=0.0000
MATH    n=20  acc=0.7000  invalid=0.2000
```

The prompt-only fix made GSM8K structurally valid but low on the 20-row smoke
sample; MATH still often emits derivations despite instructions to return only
`\boxed{...}`, but strict invalid rate fell from 95% to 20%.

Step-by-step external scoring without shared scorer changes, 2026-06-17.
Confidence: high for local implementation, compile check, saved generation
inspection, and smoke output. To let instruction-tuned external baselines solve
GSM8K step by step without changing DFM5-L comparability, `evaluation.main`
now supports an opt-in per-benchmark field:

```yaml
score_extractor: final_integer
```

This is not a benchmark scorer change. `evaluation/benchmarks.py` remains clean
relative to HEAD. The extractor is applied only when a config requests it. Raw
generations are still saved; when `save_generations_dir` is enabled, JSONL rows
also include `scoring_generation` and `score_extractor` so the exact scored
text is auditable.

External Gemma GSM8K prompts were changed back to step-by-step reasoning with a
required final marker:

```text
Solve the problem step by step.
End your response with a separate line exactly like:
Final answer: <integer>
```

Fresh smoke command:

```bash
cd /work/dfm/HRM-Text
GPU=2 SMOKE_BATCH_SIZE=1 VLLM_GPU_MEMORY_UTILIZATION=0.08 PORT=18648 \
  LOG_ROOT=logs/eval/gemma4_e2b_native_stepwise_extract_smoke_bs1_$(date +%Y%m%d_%H%M%S) \
  bash scripts/run_gemma4_e2b_standard_smoke.sh
```

Output directory:

```text
logs/eval/gemma4_e2b_native_stepwise_extract_smoke_bs1_20260617_215137
```

Scores:

```text
BoolQ   n=20  acc=0.6500  invalid=0.0000
GSM8K   n=20  acc=0.6500  invalid=0.2500
MATH    n=20  acc=0.7000  invalid=0.2000
```

The remaining GSM8K invalids are not shared-scorer failures; they are rows
where Gemma omitted the requested final-answer marker, so the extractor
deliberately left the raw generation untouched and the strict original GSM8K
scorer marked it invalid.

Gemma 4 E2B native rerun plus DFM5-L 550K scheduler, 2026-06-17.
Confidence: high for local plan inspection, pane/process inspection, patched
runtime behavior, and completed first EuroEval shards.

Combined scheduler plan:

```text
logs/scheduler/gemma4_e2b_native_then_dfm5_L_550k_20260617_222323
```

This plan first runs the corrected Gemma 4 E2B instruct external eval with the
native Gemma 4 chat template, then waits for the fully written DFM5-L
`step_550000` checkpoint before launching the DFM5-L full eval. W&B targets:

```text
Gemma 4 E2B: project=DFM5 run_id=gemma4-e2b-it-native-full
DFM5-L:      project=DFM5 run_id=oti1lisg run_name=dfm5-L
```

The DFM5-L wait row is deliberately gated on Gemma completion:

```text
average-00208  tag=gemma4_e2b_it_native
wait-00209     tag=step_550000  deps=average-00208
```

Pane 9 in tmux session `hrm-0` was repointed to this plan:

```bash
cd /work/dfm/HRM-Text
/home/ucloud/miniforge3/envs/hrm/bin/python -m eval_scheduler run \
  --plan-dir logs/scheduler/gemma4_e2b_native_then_dfm5_L_550k_20260617_222323 \
  --gpus 0,1,2,3,4,5,6,7

/home/ucloud/miniforge3/envs/hrm/bin/python -m eval_scheduler monitor \
  --plan-dir logs/scheduler/gemma4_e2b_native_then_dfm5_L_550k_20260617_222323 \
  --gpus 0,1,2,3,4,5,6,7 \
  --interval 30
```

Two scheduler/runtime issues were fixed while launching this plan:

- External Gemma vLLM extra args must quote the JSON override for shlex:
  `--hf-overrides '{"architectures":["Gemma4ForCausalLM"]}'`.
- `eval_scheduler/eval_scheduler/runtime.py` now normalizes `euroeval_bin`
  only when it is a single script path. Multi-token commands such as
  `/home/ucloud/miniforge3/envs/hrm/bin/uv run --no-project --with euroeval
  /work/dfm/HRM-Text/scripts/euroeval_api_no_flash_attn_guard.py` must not be
  treated as one relative `.py` path.

The first corrected launch reached real EuroEval execution. At the first
verified status snapshot, 8 Gemma EuroEval jobs were done, 8 were running, and
0 were failed.

DFM5-L 550K failed-row repair, 2026-06-18. Confidence: high for local plan
inspection, failed logs, process arguments, and scheduler status. The combined
plan later stopped blocked with 28 failed `step_550000` rows:

- 20 EuroEval rows failed because the appended DFM5-L block still used
  `scripts/euroeval_api_no_flash_attn_guard.py` directly, producing
  `ModuleNotFoundError: No module named 'euroeval'`.
- 8 `dfm/generative_talemaader` rows failed because the appended DFM5-L block
  lacked `judge_model` and `judge_base_url`; dfm-evals raised
  `Placeholder {{judge_model}} ... requires --judge-model`.

The repair reset only those failed rows to `pending` with `attempt=0`. EuroEval
rows now use:

```text
/home/ucloud/miniforge3/envs/hrm/bin/uv run --no-project --with euroeval /work/dfm/HRM-Text/scripts/euroeval_api_no_flash_attn_guard.py
```

`generative_talemaader` rows now use:

```text
judge_model=openai/gemma-4-e4b-judge
judge_base_url=http://127.0.0.1:8099/v1
judged_max_connections=4
```

The judge server was already running on port 8099. After restarting pane 9,
the scheduler immediately picked up `eval-00210` through `eval-00217`; live
process arguments confirmed the repaired EuroEval jobs were running through
`uv run --no-project --with euroeval`.

Monitor progress fixes, 2026-06-18. Confidence: high for local monitor output
and log inspection. `eval_scheduler/eval_scheduler/monitor.py` now has two
additional progress fallbacks:

- DFM tasks can infer an active shard's denominator from completed sibling
  shard logs for the same task/checkpoint. This fixes
  `completion X/?` on `dfm/generative_talemaader`; the step-550000 shards show
  `101/101` once sibling shard headers are available.
- EuroEval progress groups repeated sample tqdm loops and reports them as
  `pass X/10 samples Y/Z`. This avoids misleading resets such as
  `cnn-dailymail` dropping from `118/165` to `1/157` when EuroEval starts the
  next pass.

At the time of the fix, `euroeval:valeu-da` for DFM5-L `step_550000` had
failed because EuroEval aborted on invalid labels in 3/53 samples. VaLEU is
excluded from the headline averages, so no synthetic value was created for
that failed task.

Qwen final-extract GSM8K repair, 2026-06-18. Confidence: high for local vLLM
logs, package reinstall output, and a one-GPU health smoke test. The appended
`qwen-finalextract-gsm-*` standard-eval rows initially failed with status 71
before extraction/scoring could run. The root cause was vLLM server startup
failure for Qwen3.5-2B on Blackwell:

```text
FlashInfer Blackwell GDN requires an intact nvidia-cutlass-dsl-libs-cu13 install ...
terminate called after throwing an instance of 'nanobind::builtin_exception'
what(): Expected an MLIR object ...
RuntimeError: Engine core initialization failed.
```

The package repair command was:

```bash
cd /work/dfm/HRM-Text
/home/ucloud/miniforge3/envs/hrm/bin/uv pip install \
  --force-reinstall --no-deps nvidia-cutlass-dsl-libs-cu13
```

A one-GPU smoke server then reached `/health`, with vLLM using
`Using FlashInfer GDN prefill kernel`. The eight Qwen GSM rows were reset to
`pending`, the scheduler stop request was cleared, and pane 9 was restarted.
After restart, all eight Qwen GSM shards launched at batch 64 and began
processing samples.

DFM5-L `step_600000` full eval launch, 2026-06-18. Confidence: high for local
checkpoint inspection, scheduler status, and process inspection. The
`checkpoints/dfm5/L` `step_600000` checkpoint exists as
`fsdp2_step_600000/.metadata` plus `carry_step_600000.{0..7}.pt`. Its W&B
epoch x-value is `3.3130615418623695`, using the established DFM5-L mapping
`181101.374791` steps per epoch.

The full standard + DFM + EuroEval campaign was scheduled with the default
HRM simple-server path, not external/vLLM standard evals. Process inspection
confirmed launched jobs run `scripts/hrm_openai_server.py --ckpt-path
checkpoints/dfm5/L --ckpt-tag step_600000`.

```bash
cd /work/dfm/HRM-Text
python -m eval_scheduler plan create \
  --plan-dir logs/scheduler/dfm5_L_step600000_full_simple_20260618_600k_simple \
  --ckpt-path checkpoints/dfm5/L \
  --ckpt-tag step_600000 \
  --eval-epoch 3.3130615418623695 \
  --log-root logs/eval/dfm5_L_step600000_full_simple_20260618_600k_simple \
  --dfm-log-root logs/dfm_evals/dfm5_L_step600000_full_simple_20260618_600k_simple \
  --euroeval-log-root logs/euroeval/dfm5_L_step600000_full_simple_20260618_600k_simple \
  --wandb-project DFM5 \
  --wandb-run-id oti1lisg \
  --wandb-run-name dfm5-L \
  --model-prefix hrm-dfm5-L \
  --run-euroeval \
  --queue-order euroeval-first \
  --standard-batch 64 \
  --dfm-batch 32 \
  --ifeval-batch 32 \
  --euroeval-batch 16 \
  --max-retries 5 \
  --port-base 22000 \
  --judge-model openai/gemma-4-e4b-judge \
  --judge-base-url http://127.0.0.1:8099/v1 \
  --judged-max-connections 4 \
  --force
```

The plan contains 210 jobs: 1 checkpoint wait, 20 EuroEval jobs, 85 standard
eval shards, 51 DFM task shards, 32 DFM IFEval-DA shards, merge rows, an
average row, and a report row. Pane 9 in tmux session `hrm-0` now runs:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m eval_scheduler run \
  --plan-dir logs/scheduler/dfm5_L_step600000_full_simple_20260618_600k_simple \
  --gpus 0,1,2,3,4,5,6,7

/home/ucloud/miniforge3/envs/hrm/bin/python -m eval_scheduler monitor \
  --plan-dir logs/scheduler/dfm5_L_step600000_full_simple_20260618_600k_simple \
  --gpus 0,1,2,3,4,5,6,7 \
  --interval 30
```

Initial status after launch: wait row completed, 8 EuroEval jobs running, 180
jobs ready, 21 blocked on dependencies, and no failures.

DFM5-L clean W&B backfill, 2026-06-19. Confidence: high for local audit files,
W&B sync logs, and W&B API summary readback. A new run was backfilled in
project `peter-sk-sdu/DFM5` with display name `dfm5-L clean`. It uses the
main DFM5-L run `oti1lisg` as source for training and non-650K history, but
uses the clean W&B run
`dfm5-l-vllm-clean-650k-700k-20260618` as the source for 650K eval metrics.

Correct synced run:

```text
https://wandb.ai/peter-sk-sdu/DFM5/runs/dfm5-l-clean-20260619-v2
```

Important pitfall: the main DFM5-L source history did not only contain 650K
eval-like values at W&B `_step=650000`. It also had a later row at internal
step `673992` with `avg/train_step=650000`, which overwrote the clean 650K
average after the first attempted backfill. The corrected sanitizer removes
eval-like keys from any source row whose own `eval/train_step`,
`dfm_eval/train_step`, `euroeval/train_step`, or `avg/train_step` equals the
replacement step, regardless of the W&B internal `_step`.

Verified sanitized audit:

```text
logs/backfill_dfm5_l_clean_rows_wandb_summary650_sanitized.jsonl
```

The sanitized audit contains no non-650000 row with `*/train_step=650000`; the
650K row has the replacement values from the clean vLLM W&B run, including:

```text
eval/MMLU/acc = 0.536375
eval/GSM8k/acc = 0.3760511751326763
avg/overall = 0.4565571277762064
dfm_eval/generative-talemaader/model_graded_fact/accuracy = 0
euroeval/da/sentiment-classification/angry-tweets/macro_f1 = 65.04088348514136
```

Online `wandb.init` timed out repeatedly for this large backfill, so the
working path was to create an offline run and then `wandb sync` it:

```bash
cd /work/dfm/HRM-Text
python scripts/backfill_dfm5_l_clean_wandb.py \
  --use-existing-audit \
  --wandb-mode offline \
  --dest-run-name 'dfm5-L clean' \
  --dest-run-id dfm5-l-clean-20260619-v2 \
  --audit-jsonl logs/backfill_dfm5_l_clean_rows_wandb_summary650_sanitized.jsonl

wandb sync --entity peter-sk-sdu --project DFM5 \
  wandb/offline-run-20260619_090701-dfm5-l-clean-20260619-v2
```

The sync log is:

```text
logs/backfill_dfm5_l_clean_v2_offline_sync_20260619.log
```

DFM5-L clean append, 2026-06-19. Confidence: high for local audit files,
offline W&B sync output, and W&B API summary readback. After the clean run was
created, the live source run `oti1lisg` advanced beyond the clean run. The
append-only backfill script:

```text
scripts/append_dfm5_l_clean_from_source_wandb.py
```

was used to append source rows with W&B `_step > 735320` into the existing
clean run `dfm5-l-clean-20260619-v2`. This added missing training rows and the
750K eval/average rows from the main DFM5-L source run.

Audit and logs:

```text
logs/append_dfm5_l_clean_from_oti1lisg_after735320_20260619.jsonl
logs/append_dfm5_l_clean_from_oti1lisg_after735320_offline_create_20260619.log
logs/append_dfm5_l_clean_from_oti1lisg_after735320_sync_20260619.log
```

The dry-run found `4083` rows to append, including `38` eval-like rows, covering
internal W&B steps `735325..755545`. The append was done offline and synced:

```bash
cd /work/dfm/HRM-Text
python scripts/append_dfm5_l_clean_from_source_wandb.py \
  --use-existing-audit \
  --audit-jsonl logs/append_dfm5_l_clean_from_oti1lisg_after735320_20260619.jsonl \
  --wandb-mode offline

wandb sync --entity peter-sk-sdu --project DFM5 \
  wandb/offline-run-20260619_115118-dfm5-l-clean-20260619-v2
```

W&B API readback after sync showed the clean run at `_step=755545` with:

```text
avg/train_step = 750000
avg/overall = 0.5236963639147983
avg/danish = 0.5194176019991262
avg/english = 0.6620535778037574
avg/math_code = 0.3896179119415115
eval/MMLU/acc = 0.5478999999999999
eval/GSM8k/acc = 0.36922160727824105
dfm_eval/generative-talemaader/model_graded_fact/accuracy = 0.0012376237623762376
euroeval/da/sentiment-classification/angry-tweets/macro_f1 = 66.17822158112952
```

DFM5-L clean append to 800K, 2026-06-19. Confidence: high for local audit
files, offline W&B sync output, and W&B API summary readback. The same
append-only script was used again after the clean run had reached
`_step=755545`:

```bash
cd /work/dfm/HRM-Text
python scripts/append_dfm5_l_clean_from_source_wandb.py \
  --dry-run \
  --audit-jsonl logs/append_dfm5_l_clean_from_oti1lisg_after755545_20260619.jsonl

python scripts/append_dfm5_l_clean_from_source_wandb.py \
  --use-existing-audit \
  --audit-jsonl logs/append_dfm5_l_clean_from_oti1lisg_after755545_20260619.jsonl \
  --wandb-mode offline

wandb sync --entity peter-sk-sdu --project DFM5 \
  wandb/offline-run-20260619_192323-dfm5-l-clean-20260619-v2
```

Audit and logs:

```text
logs/append_dfm5_l_clean_from_oti1lisg_after755545_20260619.jsonl
logs/append_dfm5_l_clean_from_oti1lisg_after755545_dryrun_20260619.log
logs/append_dfm5_l_clean_from_oti1lisg_after755545_offline_create_20260619.log
logs/append_dfm5_l_clean_from_oti1lisg_after755545_sync_20260619.log
```

The dry-run found `11232` rows to append, including `36` eval-like rows,
covering internal W&B steps `755550..811530`. W&B API readback after sync
showed the clean run at `_step=811530` with:

```text
avg/train_step = 800000
avg/overall = 0.4941255723568704
avg/danish = 0.5140386857991142
avg/english = 0.6653983714808205
avg/math_code = 0.3029396597906766
avg/epoch = 4.417415389149824
eval/MMLU/acc = 0.54305
eval/GSM8k/acc = 0.3767944655041698
eval/BoolQ/acc = 0.8471
dfm_eval/generative-talemaader/model_graded_fact/accuracy = 0
dfm_eval/nordjyllandnews/chrf3pp/mean = 36.063069175646135
euroeval/da/sentiment-classification/angry-tweets/macro_f1 = 72.50525327604699
```

Superseded, 2026-06-19: the `dfm5-l-clean-20260619-v2` clean run was deleted.
It still allowed stale source eval rows at the 650K epoch to survive for some
standard eval metrics such as ARC, because the sanitizer only stripped rows by
`*/train_step=650000` or W&B `_step=650000`. Some source eval rows only carried
`*/epoch=3.5891500036842338`, so they could overwrite the clean rerun values.

DFM5-L clean v3 backfill, 2026-06-19. Confidence: high for local audit diff,
offline W&B sync output, W&B summary readback, and remote ARC row readback. The
corrected script:

```text
scripts/backfill_dfm5_l_clean_wandb.py
```

now defaults to `--replacement-source history`, which streams all non-null
eval-like rows from the rerun W&B history rather than copying only the rerun
summary. It also strips source eval-like rows when they target either
`650000` via `*/train_step` or the replacement epoch
`3.5891500036842338` via `*/epoch`. The script no longer writes replacement
metric values directly to `run.summary` after logging the full history; this
keeps the final summary at the latest logged checkpoint.

The corrected clean run is:

```text
https://wandb.ai/peter-sk-sdu/DFM5/runs/dfm5-l-clean-20260619-v3
```

Commands used:

```bash
cd /work/dfm/HRM-Text
python scripts/backfill_dfm5_l_clean_wandb.py \
  --dry-run \
  --wandb-mode offline \
  --dest-run-id dfm5-l-clean-20260619-v3 \
  --dest-run-name 'dfm5-L clean' \
  --audit-jsonl logs/backfill_dfm5_l_clean_rows_v3_history650_20260619.jsonl

python scripts/backfill_dfm5_l_clean_wandb.py \
  --sanitize-existing-audit \
  --dry-run \
  --wandb-mode offline \
  --dest-run-id dfm5-l-clean-20260619-v3 \
  --dest-run-name 'dfm5-L clean' \
  --audit-jsonl logs/backfill_dfm5_l_clean_rows_v3_history650_20260619.jsonl

python scripts/backfill_dfm5_l_clean_wandb.py \
  --use-existing-audit \
  --wandb-mode offline \
  --dest-run-id dfm5-l-clean-20260619-v3 \
  --dest-run-name 'dfm5-L clean' \
  --audit-jsonl logs/backfill_dfm5_l_clean_rows_v3_history650_20260619.jsonl

wandb sync --entity peter-sk-sdu --project DFM5 \
  wandb/offline-run-20260619_203345-dfm5-l-clean-20260619-v3
```

Audit and logs:

```text
logs/backfill_dfm5_l_clean_rows_v3_history650_20260619.jsonl
logs/backfill_dfm5_l_clean_v3_history650_dryrun_20260619.log
logs/backfill_dfm5_l_clean_v3_history650_sanitize_20260619.log
logs/backfill_dfm5_l_clean_v3_history650_offline_create_20260619.log
logs/backfill_dfm5_l_clean_v3_history650_sync_20260619.log
```

The strict local audit diff against the rerun W&B run
`dfm5-l-vllm-clean-650k-700k-20260618` showed `447` expected replacement keys,
`447` actual 650K audit keys, and zero missing, extra, or differing values.
Spot-checked replacement values:

```text
eval/ARC/acc = 0.6954
eval/ARC/n = 1172
eval/ARC/invalid = 0
eval/MMLU/acc = 0.536375
eval/GSM8k/acc = 0.3760511751326763
eval/BoolQ/acc = 0.8416
avg/overall = 0.45655712777620644
avg/train_step = 650000
avg/epoch = 3.589150003684234
```

W&B summary readback after sync showed the v3 clean run at `_step=820565`, with
latest summary values from 800K:

```text
avg/train_step = 800000
avg/epoch = 4.417415389149824
avg/overall = 0.4941255723568704
avg/danish = 0.5140386857991142
avg/english = 0.6653983714808205
avg/math_code = 0.3029396597906766
eval/MMLU/acc = 0.54305
eval/GSM8k/acc = 0.3767944655041698
eval/ARC/acc = 0.7099
eval/BoolQ/acc = 0.8471
```

A remote sparse-history spot check found the 650K ARC row at W&B `_step=650023`
with `eval/ARC/acc=0.6954`, `eval/train_step=650000`, and
`eval/epoch=3.589150003684234`.

DFM5-L clean v3 append to 900K, 2026-06-20. Confidence: high for local append
audit, offline W&B sync output, W&B API summary readback, and regenerated
`docs/dfm5.md`. After the v3 clean run had reached `_step=820565`, the
append-only script was used to add missing training rows plus the 850K and 900K
eval/average rows from the source DFM5-L run `oti1lisg`:

```bash
cd /work/dfm/HRM-Text
python scripts/append_dfm5_l_clean_from_source_wandb.py \
  --dry-run \
  --dest-run-id dfm5-l-clean-20260619-v3 \
  --audit-jsonl logs/append_dfm5_l_clean_from_oti1lisg_after820565_20260620.jsonl

python scripts/append_dfm5_l_clean_from_source_wandb.py \
  --use-existing-audit \
  --dest-run-id dfm5-l-clean-20260619-v3 \
  --audit-jsonl logs/append_dfm5_l_clean_from_oti1lisg_after820565_20260620.jsonl \
  --wandb-mode offline

wandb sync --entity peter-sk-sdu --project DFM5 \
  wandb/offline-run-20260620_092234-dfm5-l-clean-20260619-v3
```

Audit and logs:

```text
logs/append_dfm5_l_clean_from_oti1lisg_after820565_20260620.jsonl
logs/append_dfm5_l_clean_from_oti1lisg_after820565_dryrun_20260620.log
logs/append_dfm5_l_clean_from_oti1lisg_after820565_offline_create_20260620.log
logs/append_dfm5_l_clean_from_oti1lisg_after820565_sync_20260620.log
```

The dry-run found `17243` rows to append, including `73` eval-like rows,
covering W&B steps `820570..906456`. It included 850K at
`avg/epoch=4.693503850971687` and 900K at `avg/epoch=4.96959231279355`.
W&B API readback after sync showed the v3 clean run at `_step=906456` with:

```text
avg/train_step = 900000
avg/epoch = 4.96959231279355
avg/overall = 0.49627485017703776
avg/danish = 0.5110413263920152
avg/english = 0.6661624442926698
avg/math_code = 0.3116207798464284
eval/ARC/acc = 0.7159
eval/MMLU/acc = 0.55125
eval/GSM8k/acc = 0.3874275208491281
eval/BoolQ/acc = 0.8599
dfm_eval/nordjyllandnews/chrf3pp/mean = 35.676897848564714
euroeval/da/sentiment-classification/angry-tweets/macro_f1 = 70.41063419555583
```

The DFM5 comparison report generator:

```text
scripts/generate_dfm5_l_eval_comparison_report.py
```

was updated to include local artifacts for `DFM5-L 800K`, `DFM5-L 850K`, and
`DFM5-L 900K`. Running it regenerated:

```text
docs/dfm5.md
```

DFM5-L clean v3 850K/900K visible-history repair, 2026-06-20. Confidence:
high for W&B API summary readback and sparse-history row readback. The first
append to 900K updated the run summary but the newly appended rows were not
visible through W&B's normal history scan/workspace panels. In addition, the
source eval rows had `*/epoch` but many rows lacked the matching
`*/train_step` field required by the metric definitions.

The repair script:

```text
scripts/relog_dfm5_l_clean_eval_rows.py
```

reads the append audit, selects the 850K/900K eval rows, injects explicit
`eval/train_step`, `dfm_eval/train_step`, `euroeval/train_step`, or
`avg/train_step` for each row's prefix, and logs the repaired rows at fresh
W&B internal steps. The offline repair sync again updated summary but did not
make rows visible through `scan_history`, so the successful repair was the
online run:

```bash
cd /work/dfm/HRM-Text
python scripts/relog_dfm5_l_clean_eval_rows.py \
  --audit-jsonl logs/append_dfm5_l_clean_from_oti1lisg_after820565_20260620.jsonl \
  --output-jsonl logs/relog_dfm5_l_clean_850k_900k_explicit_train_step_online_20260620.jsonl \
  --target 850000:4.693503850971687 \
  --target 900000:4.96959231279355 \
  --base-step 920000 \
  --wandb-mode online
```

Logs and repaired audit:

```text
logs/relog_dfm5_l_clean_850k_900k_explicit_train_step_online_20260620.jsonl
logs/relog_dfm5_l_clean_850k_900k_explicit_train_step_online_20260620.log
```

Remote W&B sparse-history readback showed the repaired average rows:

```text
_step=920036 avg/train_step=850000 avg/epoch=4.693503850971687 avg/overall=0.49205879573912314
_step=920072 avg/train_step=900000 avg/epoch=4.96959231279355 avg/overall=0.49627485017703776
```

It also showed repaired standard eval rows, for example:

```text
_step=920023 eval/train_step=850000 eval/epoch=4.693503850971687 eval/ARC/acc=0.721
_step=920024 eval/train_step=850000 eval/epoch=4.693503850971687 eval/MMLU/acc=0.5447500000000001
```

## `scripts/smoke_dfm6_eval_contracts.py`

Last updated: 2026-06-24
Confidence: high
Scope: DFM6 eval preflight/smoke test.

This script is a contract smoke test for DFM6 checkpoint evaluations. It does
not run model generations. Instead it checks the eval/export plumbing that can
silently invalidate metrics:

- DFM6 HF export tokenizer/config metadata: BOS `2`, EOS `<turn|>` id `106`,
  PAD `0`, `fix_mistral_regex=True`, and a present Gemma chat template.
- Evaluation and data-prep Gemma template files have identical SHA-256 hashes.
- A rendered Gemma prompt contains the user turn and ends at
  `<|turn>model`.
- `evaluation/config/dfm6_vllm_benchmarking.yaml` contains the expected
  standard benchmark set, per-task generation limits, and
  `stop_token_ids: [106]`.
- DFM single-task and 32-way IFEval configs contain the expected tasks,
  shard arguments, GovReport truncation, and max-generation settings.
- A generated in-memory scheduler plan routes standard, DFM, and EuroEval jobs
  through vLLM/native-proxy with Gemma BFCL parser mode, the intended
  utilization/batch settings, `suite_avg_v2`/`headline_avg_v2` average prefixes,
  and the correct average dependencies.

Run before launching a DFM6 full eval:

```bash
cd /work/dfm/HRM-Text
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/smoke_dfm6_eval_contracts.py
```

Latest verified output on 2026-06-24:

```text
DFM6 eval smoke passed. Wrote /work/dfm/HRM-Text/logs/smoke/dfm6_eval_contracts_20260624_080712.json
Standard tasks: 10
DFM tasks: 10 + 32 IFEval shards
EuroEval groups: 20 (valeu-da skipped by plan)
```
