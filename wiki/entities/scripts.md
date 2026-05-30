# Script Entities

Last updated: 2026-05-24  
Confidence: high  
Scope: Local scripts added or used during data preparation.

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
