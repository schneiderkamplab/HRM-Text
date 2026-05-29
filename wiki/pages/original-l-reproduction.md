# Original L Reproduction

Last updated: 2026-05-27  
Confidence: high  
Scope: Reproduce the README L-size HRM-Text run with the original Sapient data mix.

## Goal

Run the README L-size reference recipe against an original-prefix-compatible Sapient-only sampled dataset.

Reference target:

```text
Model: HRM-Text L
Parameters: roughly 0.6B
Reference hardware: 8x H100
Reference time: about 50 hours
```

Local hardware:

```text
8x NVIDIA B200, 183GB each
```

## Data Separation

Keep this run separate from the filtered mixed corpus:

```text
Mixed corpus downloads:          data/downloads/datasets/*
Mixed corpus filter tree:        data/filtered_sources
Mixed corpus converted path:     data/converted_sources
Mixed corpus tokenized path:     data/tokenized_mixed
Mixed corpus sampled path:       data/sampled
Mixed corpus data config:        config/data/hlm.yaml

Original Sapient source roots:   data/downloads/datasets/sapient_cleaned/data_clustered
                                 data/downloads/datasets/sapient_cleaned/data
Original Sapient tokenized path: data/tokenized_original_sapient
Original Sapient sampled path:   data/sampled_original_sapient
Original Sapient data config:    config/data/original_sapient.yaml

Original plus mixed tokenized:   data/tokenized_original_plus_mixed
Original plus mixed sampled:     data/sampled_original_plus_mixed
Original plus mixed data config: config/data/original_plus_mixed.yaml
```

The original reproduction should not use `data/filtered_sources` or `data/converted_sources`, because those reflect our safer mixed-corpus policy and rewritten path prefixes. It should tokenize the original Sapient roots directly so `data_io/prefix_config.yaml` matches names like `openmathinstruct2__...`, `flan__...`, `tasksource__...`, and `Platypus__...`.

Do not overwrite `config/data/hlm.yaml` for the reproduction run. Keep `hlm.yaml` pointed at the mixed-corpus default `data/sampled`, and use `data=original_sapient` or `data.path=data/sampled_original_sapient` for the reproduction run.

The dedicated original data config is:

```yaml
path: data/sampled_original_sapient
target_only: true
```

The third `original ∪ mixed` dataset is intentionally separate from both. It uses a symlinked tokenized view of all original Sapient tasks plus non-Sapient mixed tasks. Mixed `sapient_cleaned__*` tokenized tasks are skipped because they are already represented in the full original Sapient tokenization under original-compatible task names.

Status, 2026-05-23: the `original ∪ mixed` tokenized view was rebuilt after mixed tokenization added more outputs. It now links `5,212` original Sapient task directories plus `226` non-Sapient mixed task directories and skips `1,139` mixed `sapient_cleaned__*` task directories. Sampling with `epochs=4` and `concat_workers=4` completed into `data/sampled_original_plus_mixed`; `metadata.json` reports `max_seq_len=4097`, `total_length=46,825,293,021`, and each epoch index has `111,058,569` rows. `data/show_analytics_original_plus_mixed.md` reports `73,008,641,849` unique sampled tokens out of `216,160,760,173` total tokenized tokens. Confidence: high.

## Command Ledger

The full command sequence for download, tokenization, verification, sampling, and training is recorded as a runnable script:

```bash
/work/dfm/HRM-Text/scripts/reproduce_original_sapient_l.sh --help
```

Use stages such as `download`, `tokenize`, `verify`, `sample`, and `train` to run individual steps.

## Current Process State

As of 2026-05-22, original Sapient tokenization completed with `5212` metadata files. The user reported that sampling was executed, inspected, and the L training run was launched.

The mixed-corpus tokenizer is a separate process writing to `data/tokenized_mixed`; it should not be used for the L reproduction run.

## Full Plan

1. Let original Sapient tokenization finish.
2. Verify tokenized file count and output size.
3. Sample original Sapient tokenized data with the original `data_io/prefix_config.yaml`.
4. Inspect `data/show_analytics_original_sapient.md`.
5. Launch the L reproduction run with `data=original_sapient`.
6. Save checkpoints under a reproduction-specific path.
7. Evaluate/export from that checkpoint path, not from mixed-corpus checkpoints.

## Tokenize

Command launched on 2026-05-21:

```bash
cd /work/dfm/HRM-Text/data_io/tokenizer
cargo run --release --bin tokenizer -- \
  /work/dfm/HRM-Text/data/downloads/datasets/sapient_cleaned/data_clustered \
  /work/dfm/HRM-Text/data/downloads/datasets/sapient_cleaned/data \
  --tokenizer-path /work/dfm/HRM-Text/data_io/trained_tokenizers/bpe/tokenizer.json \
  -o /work/dfm/HRM-Text/data/tokenized_original_sapient
```

Expected input files in the current download:

```text
5212 parquet/jsonl files
```

Verify completion:

```bash
find /work/dfm/HRM-Text/data/tokenized_original_sapient -name metadata.json | wc -l
du -sh /work/dfm/HRM-Text/data/tokenized_original_sapient
```

Expected metadata count is `5212`.

## Sample

After tokenization completes, sample with the original `data_io/prefix_config.yaml`:

```bash
cd /work/dfm/HRM-Text/data_io
python sample_tokenized.py \
  tokenized_path=../data/tokenized_original_sapient \
  output_path=../data/sampled_original_sapient \
  epochs=4 \
  > ../data/show_analytics_original_sapient.md
```

## Train L

Use the README L recipe with the dedicated data config:

```bash
cd /work/dfm/HRM-Text
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
torchrun --nproc_per_node=8 pretrain.py \
  data=original_sapient \
  arch/size@arch=L \
  lr=2.5e-4 \
  global_batch_size=172032 \
  +project_name="Original Sapient L HLM-torch" \
  +run_name=original-sapient-L \
  +checkpoint_path=checkpoints/original_sapient/L
```

Hydra note, verified locally on 2026-05-22: `project_name`, `run_name`, and `checkpoint_path` are fields on `PretrainConfig`, but they are not declared in `config/cfg_pretrain.yaml`. Use `+project_name=...`, `+run_name=...`, and `+checkpoint_path=...` so Hydra appends them during composition.

Logging note, verified locally on 2026-05-22: the training loop logs scalar metrics to W&B from rank 0 every `log_interval=5` steps. It does not print the scalar values to stdout; stdout mainly shows epoch banners, warnings, and the rank-0 `tqdm` progress bar. Expected W&B history keys include `train/loss`, `train/accuracy`, `train/exact_accuracy`, `train/lr`, and `bp_steps`.

Runtime memory note, verified locally on 2026-05-22: the L run intentionally ramps `bp_steps` during the first `20%` of total training. With `total_steps=326338`, `bp_min_steps=2`, `bp_max_steps=5`, and `bp_warmup_ratio=0.2`, the approximate thresholds are `bp_steps=2` through step `21754`, `bp_steps=3` through `43510`, `bp_steps=4` through `65266`, and `bp_steps=5` from step `65267` onward. GPU memory therefore rises during early training; at step `~84475`, after epoch 1 and with `bp_steps=5`, `nvidia-smi` showed about `93-97 GiB` used per B200. CPU RSS for DataLoader worker children can also look very large after epoch transitions, but inspection showed it was mostly shared/file-backed mapped data (`RssFile`/`Shared_Clean`) with no swap, not equivalent private anonymous RAM. Confidence: high.

NaN-loss note, 2026-05-22: the first L reproduction launches reported NaN loss in W&B. The sampled original data was checked for empty-supervision rows: `resp_len` had no zero entries across epochs, so the simple zero-divisor explanation was ruled out. The failure was reproduced locally with `scripts/debug_nan_training_step.py`: step 1 was finite, but step 2 produced non-finite gradients first at `model.H_level.core.layers.0.attn.gqkv_proj.weight` while loss and parameters were still finite. This localized the issue to FA4 PrefixLM attention backward, not data, W&B, or optimizer state. `models/flash_attention_prefixlm_v2.py` was changed to compact dense prefix and causal Q/K/V sequences separately, call FA4 without `seqused_*` holes or zero-length query entries, and scatter results back. Confidence: high.

Second NaN-loss note, 2026-05-22: local W&B run `wandb/run-20260522_071714-5l4tsw6k` also logged `train/loss: NaN`, `train/accuracy: 0`, and `train/exact_accuracy: 0` at `_step: 200`, then was interrupted. Its config still used `+run_name=original-sapient-L` and `+checkpoint_path=checkpoints/original_sapient/L`, so it did not use the planned `original-sapient-L-fa4-compact` run/checkpoint names. The checkpoint directory contained only `all_config.yaml`, `train_metadata.yaml`, and `hrm_nocarry_bp_warmup.py`; no epoch checkpoint was present. Confidence: high.

Post-fix diagnostics, 2026-05-22:

```bash
cd /work/dfm/HRM-Text
CUDA_VISIBLE_DEVICES=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
torchrun --nproc_per_node=1 scripts/debug_nan_training_step.py \
  --steps 12 \
  --compiled-train-batch \
  --override data=original_sapient \
  --override arch/size@arch=L \
  --override lr=2.5e-4 \
  --override global_batch_size=21504
```

Result: 12 one-GPU compiled steps had finite metric tensors and finite post-optimizer parameters.

```bash
cd /work/dfm/HRM-Text
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
torchrun --nproc_per_node=8 scripts/debug_nan_training_step.py \
  --steps 4 \
  --compiled-train-batch \
  --override data=original_sapient \
  --override arch/size@arch=L \
  --override lr=2.5e-4 \
  --override global_batch_size=172032
```

Result: 4 eight-GPU compiled steps at the production global batch size had finite metric tensors and finite post-optimizer parameters on every rank. A later 3-step one-GPU compiled check also stayed finite after marking the dynamic FA4 PrefixLM wrapper with `@torch.compiler.disable`.

Dry-run cleanup helper:

```bash
cd /work/dfm/HRM-Text
scripts/cleanup_failed_training_run.sh --original-l-latest
```

Execute the cleanup only after inspection:

```bash
cd /work/dfm/HRM-Text
scripts/cleanup_failed_training_run.sh --original-l-latest --execute
```

Equivalent path-only override:

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
torchrun --nproc_per_node=8 pretrain.py \
  arch/size@arch=L \
  lr=2.5e-4 \
  global_batch_size=172032 \
  data.path=data/sampled_original_sapient \
  +project_name="Original Sapient L HLM-torch" \
  +run_name=original-sapient-L \
  +checkpoint_path=checkpoints/original_sapient/L
```

Effective batch shape on 8 GPUs:

```text
Global token slots per optimizer step: 172,032
Per-GPU token slots: 21,504
Gradient accumulation: none
```

## Evaluate Checkpoints

Original-plus-mixed checkpoint 3 standard-eval incremental sync, 2026-05-26: `MMLU` completed and was manually synced to W&B run `original-plus-mixed-danish-instruction-rich-L` (`es1od1in`) under `eval/*` at `eval/epoch=3`. The synced aggregate values were `eval/MMLU/acc=0.5012`, `eval/MMLU/invalid=0.0`, and `eval/MMLU/n=57`; per-subject `acc_*`, `invalid_*`, and `n_*` keys were also logged. The local sync log is `logs/eval/original_plus_mixed_danish_instruction_rich_L_epoch3_queued_all/sync_mmlu_20260526T143619.log`. Confidence: high.

Original-plus-mixed checkpoint 3 standard-eval incremental sync, 2026-05-26: `GSM8k` completed and was manually synced to the same W&B run under `eval/*` at `eval/epoch=3`. The synced values were `eval/GSM8k/acc=0.7703`, `eval/GSM8k/invalid=0.0190`, and `eval/GSM8k/n=1319`. The local sync log is `logs/eval/original_plus_mixed_danish_instruction_rich_L_epoch3_queued_all/sync_gsm8k_20260526T151211.log`. Confidence: high.

Original-plus-mixed checkpoint 3 partial sync, 2026-05-26: all completed CP3 results except IFEval-DA were manually synced while IFEval-DA shards were still running. The 8 MATH shards were merged and synced under `eval/MATH/*` at `eval/epoch=3`: `acc=0.4594`, `invalid=0.0872`, `n=5000`. The completed non-IFEval dfm-evals tasks were synced under `dfm_eval/*` at `dfm_eval/epoch=3`: `danish-citizen-tests`, `dala`, `gec_dala`, `wmt24pp-en-da`, `multi_wiki_qa`, `piqa`, and `generative-talemaader`. The local sync logs are `logs/eval/original_plus_mixed_danish_instruction_rich_L_epoch3_queued_all/sync_all_but_ifeval_20260526T164746.log` and `logs/eval/original_plus_mixed_danish_instruction_rich_L_epoch3_queued_all/sync_dfm_all_but_ifeval_20260526T164843.log`. Confidence: high.

Verified from `evaluation/main.py`, `evaluation/engines.py`, and `simple_inference_engine.py` on 2026-05-23: HRM evaluation uses `python -m evaluation.main`, loads `evaluation/config/hrm_benchmarking.yaml` by default, and evaluates the latest epoch if `ckpt_epoch` is omitted. To evaluate all four original-L checkpoints, pass `ckpt_epoch=1`, `2`, `3`, and `4` explicitly.

Run all default benchmarks sequentially on one visible GPU:

```bash
cd /work/dfm/HRM-Text
mkdir -p logs/eval/original_sapient_L
for epoch in 1 2 3 4; do
  CUDA_VISIBLE_DEVICES=0 python -m evaluation.main \
    ckpt_path="checkpoints/original_sapient/L" \
    ckpt_epoch="${epoch}" \
    2>&1 | tee "logs/eval/original_sapient_L/epoch_${epoch}.log"
done
```

Run all four epochs in parallel, one GPU per checkpoint:

```bash
cd /work/dfm/HRM-Text
GPUS=0,1,2,3 scripts/evaluate_original_sapient_l_checkpoints.sh
```

The script writes:

```text
logs/eval/original_sapient_L/epoch_1.log
logs/eval/original_sapient_L/epoch_2.log
logs/eval/original_sapient_L/epoch_3.log
logs/eval/original_sapient_L/epoch_4.log
```

Pass extra Hydra overrides through the script, for example:

```bash
GPUS=0,1,2,3 scripts/evaluate_original_sapient_l_checkpoints.sh generation_config.batch_size=16
```

Verified on 2026-05-25 from `logs/eval/original_sapient_L/epoch_{1,2,3,4}.log`: all four original Sapient L checkpoints completed the full standard eval suite with no tracebacks. Each checkpoint generated `45,648` samples: `1,319` GSM8k, `5,000` MATH, `9,536` DROP, `14,042` MMLU, `1,172` ARC, `10,042` HellaSwag, `1,267` Winogrande, and `3,270` BoolQ. The first grouped generation batch was `6,319` samples, which is `GSM8k + MATH`, so MATH did run on all `5,000` samples. Confidence: high.

## Standard Evals For Original Plus Mixed

Status, 2026-05-25: standard HRM evals for the active `original_plus_mixed_danish_instruction_rich` L run are run with one independent `evaluation.main` process per GPU and one benchmark per process. The active training job still occupies all eight GPUs, so eval processes share GPUs with training. Use `setsid` plus stdin redirected from `/dev/null` for detached eval jobs; a plain background `nohup` launch from the command runner can exit early with an empty log even though the same foreground command works. Confidence: high.

The checkpoint-1 standard eval fan-out uses:

```bash
cd /work/dfm/HRM-Text
CUDA_VISIBLE_DEVICES=<gpu> OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1 \
python -u -m evaluation.main \
  config=evaluation/config/hrm_benchmarking.yaml \
  ckpt_path=checkpoints/original_plus_mixed_danish_instruction_rich/L \
  ckpt_epoch=1 \
  'run_only=[<BENCHMARK>]' \
  generation_config.batch_size=8
```

Live log roots from the 2026-05-25 launch:

```text
CP1 GSM8k:        logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_direct_epoch1/GSM8k.log
CP1 Winogrande:   logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_direct_epoch1_probe/Winogrande_setsid.log
CP1 other tasks:  logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_direct_epoch1_setsid/*.log
CP2 follow-ons:   logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_direct_epoch2_setsid/*.log
Watcher status:   logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_watchers/status.tsv
```

The 2026-05-25 run uses eight lanes for `GSM8k`, `MATH`, `DROP`, `MMLU`, `ARC`, `HellaSwag`, `Winogrande`, and `BoolQ`. Watchers start the same benchmark on checkpoint 2 as soon as checkpoint 1 for that benchmark finishes and has an `EVALUATION SUMMARY`. Confidence: high.

Update, 2026-05-25: full unsharded MATH evals for checkpoint 1 and checkpoint 2 were stopped because MATH was the bottleneck. `evaluation.benchmarks.MATH` now supports `num_shards` and `shard_index` using the same modulo sharding strategy as `dfm-evals` IFEval-DA: a sample belongs to a shard when `index % num_shards == shard_index`. For 8 shards, local verification showed exactly `625` samples per shard and `5,000` total samples. Confidence: high.

MATH shard logs for the active run are under:

```text
logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_math_shards_v2/epoch_1/MATH_shard_<0-7>_of_8.log
logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_math_shards_v2/epoch_2/MATH_shard_<0-7>_of_8.log
```

Merge completed MATH shards with:

```bash
cd /work/dfm/HRM-Text
scripts/merge_standard_math_shards.py \
  logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_math_shards_v2/epoch_1/MATH_shard_*_of_8.log \
  --epoch 1 \
  --output logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_math_shards_v2/epoch_1/merged_math_metrics.json
```

Use `--log-wandb --project ... --run-id ... --run-name ...` to log the merged `eval/MATH/{n,acc,invalid}` row to W&B using `eval/epoch` as the step metric. Confidence: high.

Restrict benchmark names with `run_only=[GSM8k,MATH,DROP,MMLU,ARC,HellaSwag,Winogrande,BoolQ]` syntax. Lower `generation_config.batch_size` if a benchmark runs out of memory.

Runtime batch grouping, verified from `evaluation/main.py`, `evaluation/config/hrm_benchmarking.yaml`, and active logs on 2026-05-23: the default HRM benchmark config produces three generation groups per checkpoint, because benchmarks with identical generation kwargs are concatenated before generation. The groups are:

- `6319` prompts: `GSM8k` plus `MATH`, using the default `synth,cot`, `batch_size=33`, `max_context=3072`.
- `9536` prompts: `DROP`, using `direct`, `batch_size=33`, `max_context=3072`.
- `29793` prompts: `MMLU`, `ARC`, `HellaSwag`, `Winogrande`, and `BoolQ`, using `direct`, `batch_size=1`, `max_context=4096`, `max_tokens=1`.

Confidence: high.

Completed evaluation results from `logs/eval/original_sapient_L/epoch_{1..4}.log` on 2026-05-23:

| checkpoint | GSM8k acc | MATH acc | DROP EM | DROP F1 | MMLU acc | ARC acc | HellaSwag acc | Winogrande acc | BoolQ acc |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| epoch 1 | 0.5792 | 0.3462 | 0.5520 | 0.5865 | 0.4175 | 0.4582 | 0.3231 | 0.5422 | 0.7260 |
| epoch 2 | 0.7225 | 0.4524 | 0.6989 | 0.7358 | 0.5074 | 0.6288 | 0.4141 | 0.6417 | 0.8214 |
| epoch 3 | 0.7779 | 0.4792 | 0.7292 | 0.7641 | 0.5317 | 0.6962 | 0.4732 | 0.6654 | 0.8367 |
| epoch 4 | 0.7801 | 0.5012 | 0.7442 | 0.7824 | 0.5523 | 0.7278 | 0.5093 | 0.6669 | 0.8462 |

Confidence: high.

W&B eval backfill, verified on 2026-05-24: `scripts/log_original_l_eval_to_wandb.py` parses the completed eval logs and resumes the healthy original Sapient L W&B run `76sygh18` in project `Original Sapient L HLM-torch`. It logs clean history metrics such as `eval/GSM8k/acc`, `eval/MATH/acc`, `eval/DROP/f1`, and summary keys per epoch/final.

```bash
cd /work/dfm/HRM-Text
python scripts/log_original_l_eval_to_wandb.py --resume must
```

Confidence: high.

Local W&B history completeness, verified on 2026-05-24: the local history for run `76sygh18` is complete but split across three resumed W&B directories:

```text
wandb/run-20260522_073509-76sygh18/run-76sygh18.wandb
  training history: 65,186 history records, steps 0..325925, exit record present

wandb/run-20260524_084549-76sygh18/run-76sygh18.wandb
  first eval backfill: 4 history records, steps 325926..325929, contains 112 bad dotted eval keys

wandb/run-20260524_084613-76sygh18/run-76sygh18.wandb
  corrected eval backfill: 4 history records, steps 325930..325933, contains 196 clean eval keys and no bad dotted eval keys
```

The remote run state is `finished`; its summary `_step` is `325933`, matching training plus both local eval backfill attempts. Confidence: high.

Clean local W&B history merge, verified on 2026-05-24: `scripts/merge_original_l_wandb_history.py` merges the original training datastore and the corrected eval backfill datastore while omitting the first bad eval backfill. The output is local only:

```text
wandb/merged-20260524-76sygh18-clean/run-76sygh18-clean-merged.wandb
wandb/merged-20260524-76sygh18-clean/history.jsonl
wandb/merged-20260524-76sygh18-clean/manifest.json
```

Validation of the merged `.wandb` file showed `65,190` history records, steps `0..325933`, `196` clean eval keys, zero dotted eval keys, and an exit record. Syncing this local merged copy will not delete the already-synced bad history from the original remote run. Confidence: high.

A separate local copy was also prepared for upload into the ongoing mixed-run project:

```text
wandb/merged-20260524-76sygh18-clean-for-ongoing/run-origLclean.wandb
wandb/merged-20260524-76sygh18-clean-for-ongoing/history.jsonl
wandb/merged-20260524-76sygh18-clean-for-ongoing/files/*
wandb/merged-20260524-76sygh18-clean-for-ongoing/logs/*
```

This copy rewrites the local protobuf run metadata to `run_id=origLclean`, `project="Original Plus Mixed Danish Instruction Rich L"`, and `display_name=original-sapient-L-clean-history`. It includes the original run config, summaries, metric definitions, history, console output records, and copied local sidecar files/logs. The local `.wandb` file does not contain a full source-code artifact payload; it only has W&B's `_wandb.code_path` metadata for the original `source-Original_Sapient_L_HLM-torch-pretrain.py` source artifact. Confidence: high.

Upload command, executed and verified on 2026-05-24:

```bash
cd /work/dfm/HRM-Text
wandb sync --no-sync-tensorboard --no-mark-synced \
  --entity peter-sk-sdu \
  --project "Original Plus Mixed Danish Instruction Rich L" \
  --id "origLclean" \
  "/work/dfm/HRM-Text/wandb/merged-20260524-76sygh18-clean-for-ongoing/run-origLclean.wandb"
```

Remote URL:

```text
https://wandb.ai/peter-sk-sdu/Original%20Plus%20Mixed%20Danish%20Instruction%20Rich%20L/runs/origLclean
```

Post-sync verification showed `state=finished`, summary `_step=325933`, `train/loss=0.8746508359909058`, `eval/GSM8k/acc=0.7801`, `eval/MATH/acc=0.5012`, `eval/DROP/f1=0.7824`, and zero dotted eval summary keys. The local merge script was updated to drop `672` bad dotted eval summary updates from the corrected eval-backfill datastore before writing future merged copies. Confidence: high.

## dfm-evals

Prepared on 2026-05-24, not yet run end-to-end: `dfm-evals` was cloned from `https://github.com/danish-foundation-models/dfm-evals`, and three local scripts were added:

```text
scripts/hrm_openai_server.py
scripts/run_dfm_evals_on_checkpoints.sh
scripts/log_dfm_evals_to_wandb.py
```

The wrapper starts a local OpenAI-compatible HTTP shim for each checkpoint, runs dfm-evals through Inspect, exports Inspect logs to Every Eval Ever JSON, and logs numeric results to W&B under `dfm_eval/...` instead of `eval/...`.

The default suite is `config/dfm_evals_hrm.yaml:hrm_danish`, which includes Danish citizen tests, DaLA, GEC-DaLA, WMT24++ English-to-Danish, and MultiWikiQA. It intentionally avoids the upstream `fundamentals` suite's judge-only and long-context RULER tasks because the original HRM L checkpoints use a 4096-token context. Confidence: medium until a full run completes.

Runtime update, 2026-05-24: dfm-evals for the four original checkpoints was launched. The first attempt serialized OpenAI-compatible chat requests one at a time and was too slow. `scripts/hrm_openai_server.py` was updated to micro-batch concurrent requests, and `scripts/run_dfm_evals_on_checkpoints.sh` now defaults to `BATCH_SIZE=8`, `INSPECT_MAX_CONNECTIONS=8`, and `BATCH_TIMEOUT_MS=25`. The Danish citizen tests task is capped to `250` samples by the suite-level `--limit 250`; after restart, the server log showed batched generation groups of 4, confirming batching is active. Confidence: high.

Superseded on 2026-05-24: the suite-level `--limit 250` was removed from `config/dfm_evals_hrm.yaml` so task defaults are used. The public Danish citizen tests task selected `545` samples after its split/dedup logic. Epoch 1 completed that task and a manual partial W&B sync logged `dfm_eval/danish-citizen-tests/knowledge/accuracy=0.0055` and `dfm_eval/danish-citizen-tests/knowledge/dfm_evals_mcc=-0.01355` to run `origLclean`. Confidence: high.

Parallel dfm-evals launch, verified on 2026-05-24: epoch 1 remained active on GPU 0/port 8092. Epochs 2, 3, and 4 were launched independently with `setsid` on GPU 1/port 8093, GPU 2/port 8094, and GPU 3/port 8095. All four HRM shim processes passed health checks and began processing dfm-evals requests. The epoch 2-4 launcher logs are under `logs/dfm_evals/parallel_launch/epoch_{2,3,4}.setsid.log`. Confidence: high.

Manual dfm-evals sync, verified on 2026-05-24: completed Inspect logs were exported to Every Eval Ever JSON and logged to the clean W&B run `origLclean` in project `Original Plus Mixed Danish Instruction Rich L`. A `.eval` file is treated as complete only when the Inspect zip contains `header.json`, `summaries.json`, and `reductions.json`; partial files were not synced. Synced metrics currently include epoch 1 Danish citizen tests, DaLA, and GEC-DaLA, plus Danish citizen tests for epochs 2-4. WMT24++ epoch 1 and DaLA/GEC-DaLA for epochs 2-4 were still partial at the time of this sync. Confidence: high.

Runtime update, 2026-05-24 after the manual sync: DaLA and GEC-DaLA completed for epochs 2-4. These newly completed metrics were not part of the earlier manual sync yet. WMT24++ is active for epochs 1-4, with sample counts observed at epoch 1 `691/998`, epoch 2 `489/998`, epoch 3 `681/998`, and epoch 4 `603/998`; MultiWikiQA has not started yet. Confidence: high.

Second manual dfm-evals sync, verified on 2026-05-24: DaLA and GEC-DaLA for epochs 2-4 were exported from completed Inspect logs and logged to W&B run `origLclean` under the same `dfm_eval/...` prefix. WMT24++ remained partial and was not synced. Confidence: high.

Second manual sync results:

```text
epoch 2:
  dfm_eval/dala/linguistic-acceptability/dfm_evals_macro_f1 = 0.00388
  dfm_eval/dala/linguistic-acceptability/dfm_evals_mcc = 0.00418
  dfm_eval/gec_dala/exact_match/mean = 0.00000

epoch 3:
  dfm_eval/dala/linguistic-acceptability/dfm_evals_macro_f1 = 0.00097
  dfm_eval/dala/linguistic-acceptability/dfm_evals_mcc = 0.00000
  dfm_eval/gec_dala/exact_match/mean = 0.00000

epoch 4:
  dfm_eval/dala/linguistic-acceptability/dfm_evals_macro_f1 = 0.00388
  dfm_eval/dala/linguistic-acceptability/dfm_evals_mcc = 0.00000
  dfm_eval/gec_dala/exact_match/mean = 0.00000
```

Third manual dfm-evals sync, verified on 2026-05-24: completed WMT24++ and MultiWikiQA logs were exported and logged to W&B run `origLclean`. The sync included epoch 1 WMT24++, epoch 3 WMT24++ and MultiWikiQA, and epoch 4 WMT24++ and MultiWikiQA. A follow-up sync in the same turn added epoch 1 MultiWikiQA and epoch 2 WMT24++ after those files completed. Confidence: high.

Third/follow-up manual sync results:

```text
epoch 1:
  dfm_eval/wmt24pp-en-da/chrf3pp/mean = 0.19774
  dfm_eval/multi_wiki_qa/exact_match/mean = 0.00000
  dfm_eval/multi_wiki_qa/f1/mean = 0.00970

epoch 2:
  dfm_eval/wmt24pp-en-da/chrf3pp/mean = 0.22980

epoch 3:
  dfm_eval/wmt24pp-en-da/chrf3pp/mean = 0.23627
  dfm_eval/multi_wiki_qa/exact_match/mean = 0.04688
  dfm_eval/multi_wiki_qa/f1/mean = 0.10095

epoch 4:
  dfm_eval/wmt24pp-en-da/chrf3pp/mean = 0.24968
  dfm_eval/multi_wiki_qa/exact_match/mean = 0.09424
  dfm_eval/multi_wiki_qa/f1/mean = 0.17277
```

Incremental sync update, verified locally on 2026-05-24: `scripts/sync_completed_dfm_evals.py` was added and `scripts/run_dfm_evals_on_checkpoints.sh` now starts it by default with `INCREMENTAL_WANDB_SYNC=1`. It scans the Inspect log directory, treats `.eval` files as complete only when the zip contains `header.json`, `summaries.json`, and `reductions.json`, exports each completed test separately, and logs it to W&B immediately. `FINAL_WANDB_SYNC` now defaults to `0` to avoid logging the full epoch a second time after incremental sync; the wrapper still exports the full EEE directory for archival use. Confidence: high.

Process correction, verified on 2026-05-24: the original all-epoch dfm-evals wrapper advanced from epoch 1 to epoch 2 while the dedicated epoch 2 wrapper was already running. This created a duplicate epoch 2 dfm-evals process writing to the same Inspect directory and produced duplicate partial MultiWikiQA `.eval` files. The newer duplicate process was stopped, leaving the dedicated epoch 2 wrapper/server running. Confidence: high.

Current-run incremental watcher, verified on 2026-05-24: because the already-running epoch 2 wrapper predates the incremental-sync script change, a bounded watcher was started manually. It writes to `logs/dfm_evals/original_sapient_L/epoch_2/manual_incremental_sync_current`, has marker files for already-synced completed epoch 2 logs, and exits after the active epoch 2 eval process exits. Its purpose is to sync the remaining epoch 2 MultiWikiQA result if it completes. Confidence: high.

Completion update, verified on 2026-05-24: dfm-evals finished for all four original Sapient L checkpoints. No dfm-evals wrapper, shim, or sync watcher processes remained; only the unrelated ongoing mixed L training process was still running. Epoch 2 MultiWikiQA completed with `dfm_eval/multi_wiki_qa/exact_match/mean = 0.01074` and `dfm_eval/multi_wiki_qa/f1/mean = 0.04904`, and was manually synced to W&B run `origLclean`. A duplicate zero-sample partial epoch 2 MultiWikiQA `.eval` file remains from the stopped duplicate process and should be ignored. Confidence: high.

W&B workspace panel update, verified on 2026-05-24: the `dfm_eval` workspace section in project `Original Plus Mixed Danish Instruction Rich L` was updated so every non-axis dfm-eval line plot uses `dfm_eval/epoch` as its x-axis. The user had already changed `dfm_eval/wmt24pp-en-da/chrf3pp/mean`; the remaining panels were changed programmatically via the W&B workspace view spec after installing `wandb[workspaces]` in the `hrm` environment. Backup specs were written under `logs/wandb_workspace_specs/20260524T122220Z_before_nw-nwuserpetersk-w.json` and `logs/wandb_workspace_specs/20260524T122220Z_after_nw-nwuserpetersk-w.json`. Confidence: high.

Superseded/context update, 2026-05-24: W&B reported success when mutating the personal default workspace view, but the UI and a later API read showed only the user's manually changed WMT panel persisted. The public Workspace API also refuses personal user views. A new saved workspace view named `dfm_eval epoch x-axis` was created instead, with all non-axis `dfm_eval` panels keyed and set to `xAxis=dfm_eval/epoch`. URL: `https://wandb.ai/peter-sk-sdu/Original%20Plus%20Mixed%20Danish%20Instruction%20Rich%20L?nw=oi8yv6lpmkn`. Backup spec: `logs/wandb_workspace_specs/20260524T123312Z_saved_view_dfm_eval_epoch_axis.json`. Confidence: high.

W&B workspace cleanup, verified on 2026-05-26: deleting panels from the personal default workspace view again returned a successful `upsertView` response but readback showed the personal view unchanged. The requested cleanup was therefore materialized as a saved workspace view named `eval cleaned: no MMLU n/invalid`, with `96` panels removed from the `eval` section: `45` `eval/MMLU/n_*` panels and `51` `eval/MMLU/invalid_*` panels. API readback of the saved view shows `34` eval panels and `0` matching panels, but the user reported the URL still showed the old panels in the web UI. A follow-up attempt to use the separate `upsertUserProfileView` mutation for the personal view failed with a W&B HTTP 500. URL: `https://wandb.ai/peter-sk-sdu/Original%20Plus%20Mixed%20Danish%20Instruction%20Rich%20L?nw=boh5wwabbfc7`. Backup/spec files: `logs/wandb_workspace_specs/20260526T151707Z_before_delete_mmlu_n_invalid_nw-nwuserpetersk-w.json`, `logs/wandb_workspace_specs/20260526T151707Z_after_delete_mmlu_n_invalid_nw-nwuserpetersk-w.json`, and `logs/wandb_workspace_specs/20260526T151840Z_saved_view_delete_mmlu_n_invalid.json`. Confidence: high.

Additional dfm-evals task inventory, verified on 2026-05-24: local `dfm-evals` is at upstream `main` commit `9b6cf828ccffdbde54dd8ed2e4d06a37f979cd2a`. Registered local task names are `dfm_evals/bfcl-v1`, `dfm_evals/bfcl-v1-da`, `dfm_evals/dala`, `dfm_evals/danish-citizen-tests`, `dfm_evals/gec_dala`, `dfm_evals/generative-talemaader`, `dfm_evals/ifeval-da`, `dfm_evals/multi_wiki_qa`, `dfm_evals/piqa`, `dfm_evals/ruler`, and `dfm_evals/wmt24pp-en-da`. No task named `daisy` exists in this checkout. The HRM-compatible suite already ran the non-judge Danish tasks except `piqa` and `ifeval-da`; `generative-talemaader` requires a judge model, `ruler` needs a <=4096-token configuration for these checkpoints, and BFCL/agentic tasks need tool/calling behavior that the current simple HRM OpenAI shim is not expected to handle well. Confidence: high.

Suite update, verified on 2026-05-24: `config/dfm_evals_hrm.yaml:hrm_danish` now includes `dfm_evals/piqa`, `dfm_evals/ifeval-da`, and `dfm_evals/generative-talemaader` in the same suite as the existing Danish tasks. `uv sync --project dfm-evals --extra ifeval` was run successfully, installing `instruction-following-eval`, `nltk`, `langdetect`, `immutabledict`, and `joblib` for `ifeval-da`. `scripts/run_dfm_evals_on_checkpoints.sh` now accepts `JUDGE_MODEL` and `JUDGE_BASE_URL` and forwards them to `evals suite`; `JUDGE_MODEL` is required when running `generative-talemaader`, because that task uses a model-graded scorer. Confidence: high.

New-task dfm-evals run, verified on 2026-05-24: the three newly added tasks were run for all four original Sapient L checkpoints without rerunning the older dfm-evals tasks. A temporary suite file, `config/dfm_evals_hrm_new_tasks_only.yaml`, contains only `dfm_evals/piqa`, `dfm_evals/ifeval-da`, and `dfm_evals/generative-talemaader`. `generative-talemaader` used a local Transformers OpenAI-compatible server for `unsloth/gemma-4-E4B-it`, served as `openai/gemma-4-e4b-judge` at `http://127.0.0.1:8099/v1`. vLLM was not used for this judge because its Gemma 4 path required `flash_attn.ops`, which is absent in the local FA4/B200 environment. Completed Inspect logs and W&B sync markers exist for all three new tasks across epochs 1, 2, 3, and 4 under `logs/dfm_evals/original_sapient_L_new_tasks_gemma4_judge/epoch_{1..4}`. Confidence: high.

Single-task scheduling note, verified on 2026-05-24: `config/dfm_evals_hrm_single_tasks.yaml` defines one suite per `hrm_danish` task so future runs can schedule one eval task per GPU or run safe waves when training memory pressure is high. The suites are `hrm_danish_danish_citizen_tests`, `hrm_danish_dala`, `hrm_danish_gec_dala`, `hrm_danish_wmt24pp_en_da`, `hrm_danish_multi_wiki_qa`, `hrm_danish_piqa`, `hrm_danish_ifeval_da`, and `hrm_danish_generative_talemaader`. No original+mixed checkpoint eval worker was launched when this config was created; the user chose to wait until GPU pressure drops. Confidence: high.

Launch pattern used for the new-task-only run:

```bash
cd /work/dfm/HRM-Text
python scripts/transformers_openai_server.py \
  unsloth/gemma-4-E4B-it \
  --served-model-name gemma-4-e4b-judge \
  --host 127.0.0.1 \
  --port 8099 \
  --dtype bfloat16 \
  --attn-implementation sdpa \
  --max-new-tokens 512

for spec in 1:0 2:1 3:2 4:3; do
  epoch="${spec%%:*}"
  gpu="${spec##*:}"
  EPOCHS="${epoch}" \
  GPU="${gpu}" \
  PORT_BASE=8210 \
  SUITE_FILE=/work/dfm/HRM-Text/config/dfm_evals_hrm_new_tasks_only.yaml \
  SUITE=hrm_danish_new_tasks_only \
  LOG_ROOT=/work/dfm/HRM-Text/logs/dfm_evals/original_sapient_L_new_tasks_gemma4_judge \
  JUDGE_MODEL=openai/gemma-4-e4b-judge \
  JUDGE_BASE_URL=http://127.0.0.1:8099/v1 \
  INCREMENTAL_WANDB_SYNC=1 \
  SYNC_INTERVAL_SECONDS=30 \
  FINAL_WANDB_SYNC=0 \
  OPENAI_API_KEY=inspectai \
  scripts/run_dfm_evals_on_checkpoints.sh
done
```

Manual sync command pattern:

```bash
cd /work/dfm/HRM-Text
uv run --project dfm-evals evals eee inspect \
  --log-path logs/dfm_evals/original_sapient_L/epoch_${epoch}/manual_sync_completed_20260524_1216/eval_logs \
  --output-dir logs/dfm_evals/original_sapient_L/epoch_${epoch}/manual_sync_completed_20260524_1216/eee \
  --source-organization-name "schneiderkamplab" \
  --evaluator-relationship "first_party" \
  --inference-base-url "http://127.0.0.1:${port}/v1" \
  --inference-provider-name "hrm-openai-shim"

python scripts/log_dfm_evals_to_wandb.py \
  --eee-dir logs/dfm_evals/original_sapient_L/epoch_${epoch}/manual_sync_completed_20260524_1216/eee \
  --epoch "${epoch}" \
  --project "Original Plus Mixed Danish Instruction Rich L" \
  --run-id "origLclean" \
  --run-name "original-sapient-L-clean-history" \
  --prefix "dfm_eval"
```

Manual sync results:

```text
epoch 1:
  dfm_eval/danish-citizen-tests/knowledge/accuracy = 0.00550
  dfm_eval/danish-citizen-tests/knowledge/dfm_evals_mcc = -0.01355
  dfm_eval/dala/linguistic-acceptability/dfm_evals_macro_f1 = 0.03815
  dfm_eval/dala/linguistic-acceptability/dfm_evals_mcc = -0.01899
  dfm_eval/gec_dala/exact_match/mean = 0.00000

epoch 2:
  dfm_eval/danish-citizen-tests/knowledge/accuracy = 0.17615
  dfm_eval/danish-citizen-tests/knowledge/dfm_evals_mcc = 0.06919

epoch 3:
  dfm_eval/danish-citizen-tests/knowledge/accuracy = 0.15963
  dfm_eval/danish-citizen-tests/knowledge/dfm_evals_mcc = 0.00582

epoch 4:
  dfm_eval/danish-citizen-tests/knowledge/accuracy = 0.13028
  dfm_eval/danish-citizen-tests/knowledge/dfm_evals_mcc = 0.02170
```

Smoke command:

```bash
cd /work/dfm/HRM-Text
INSTALL=1 EPOCHS="4" scripts/run_dfm_evals_on_checkpoints.sh -- --limit 10
```

Full default command:

```bash
cd /work/dfm/HRM-Text
scripts/run_dfm_evals_on_checkpoints.sh
```

Original+mixed checkpoint eval launch, verified on 2026-05-25. Confidence: high.

The first checkpoint of the ongoing `original_plus_mixed_danish_instruction_rich` L run is available as `checkpoints/original_plus_mixed_danish_instruction_rich/L/fsdp2_epoch_1` plus `carry_epoch_1.{0..7}.pt`. Eight single-task dfm-evals jobs were launched in parallel, one per GPU, using `config/dfm_evals_hrm_single_tasks.yaml` and logging to the active W&B run id `es1od1in` in project `Original Plus Mixed Danish Instruction Rich L`.

Log root:

```text
logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch1_parallel
```

GPU/task mapping:

```text
GPU 0: hrm_danish_danish_citizen_tests, port 8411
GPU 1: hrm_danish_dala, port 8421
GPU 2: hrm_danish_gec_dala, port 8431
GPU 3: hrm_danish_wmt24pp_en_da, port 8441
GPU 4: hrm_danish_multi_wiki_qa, port 8451
GPU 5: hrm_danish_piqa, port 8461
GPU 6: hrm_danish_ifeval_da, port 8471
GPU 7: hrm_danish_generative_talemaader, port 8481
```

`generative_talemaader` requires a judge. The judge was launched on the same GPU 7:

```text
model: unsloth/gemma-4-E4B-it
served name: gemma-4-e4b-judge
base URL: http://127.0.0.1:8499/v1
log: logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch1_parallel/judge_gemma4_e4b_gpu7/server.log
```

At launch verification, all task wrappers were active except `piqa`, which had already completed successfully with `accuracy = 0.194`. The remaining HRM shim health ports responded; the judge health endpoint can time out during active generation on GPU 7, but it started successfully before the judged task was launched.

W&B sync caveat for active original+mixed run, verified on 2026-05-25. Confidence: high.

The per-task sidecar W&B sync processes reported successful `wandb.init(..., resume=...)` logging to active run id `es1od1in`, and local sidecar run directories contained the expected `dfm_eval/...` keys. However, the W&B public API initially showed no `dfm_eval/...` summary keys for that active run. The likely cause is concurrent sidecar resumes while the training process owns the same live run. DaLA and GEC-DaLA were patched into the online run summary directly with the W&B API:

```text
dfm_eval/dala/linguistic-acceptability/dfm_evals_macro_f1 = 0.06285135215101485
dfm_eval/dala/linguistic-acceptability/dfm_evals_mcc = -0.015338488073023071
dfm_eval/gec_dala/exact_match/mean = 0.1435546875
dfm_eval/epoch = 1
dfm_eval/last_epoch = 1
```

For future evals against a live training run, prefer either direct API summary updates or logging to a separate eval run and merging after training, rather than relying on multiple short-lived processes resuming the live training run.

Follow-up on 2026-05-25. Confidence: high. GEC-DaLA became visible in the UI, but DaLA did not. DaLA was re-logged with `wandb.log()` under both the original dfm-evals keys and simpler aliases:

```text
dfm_eval/dala/linguistic-acceptability/dfm_evals_macro_f1 = 0.06285135215101485
dfm_eval/dala/linguistic-acceptability/dfm_evals_mcc = -0.015338488073023071
dfm_eval/dala/macro_f1/mean = 0.06285135215101485
dfm_eval/dala/mcc/mean = -0.015338488073023071
```

The re-log process reported a successful W&B sync and run summary containing all four DaLA keys.

Superseded on 2026-05-25. Confidence: high. The user could see the correct original DaLA keys, so the simpler DaLA aliases were no longer wanted. The online W&B summary no longer contained the alias keys:

```text
dfm_eval/dala/macro_f1/mean
dfm_eval/dala/mcc/mean
dfm_eval/dala/f1/mean
```

W&B history rows are append-only, so alias keys that were logged once may still appear in the run's metric browser or auto-generated workspace panels. They should not be used for reporting; use only the original dfm-evals DaLA keys.

PIQA scorer correction, verified on 2026-05-25. Confidence: high.

The local `dfm-evals` checkout remotes are:

```text
origin:   https://github.com/schneiderkamplab/dfm-evals.git
upstream: https://github.com/danish-foundation-models/dfm-evals
```

`dfm_evals/tasks/piqa.py` was patched so PIQA outputs that contain both standalone `A` and standalone `B` are treated as invalid. Previously, the scorer searched for the first standalone `A` or `B` anywhere in the completion. This made prompt/instruction echoes like `Svar kun med A eller B.` score as `A`, which inflated scores because PIQA-da has a strong label skew toward `A`.

Existing PIQA EEE JSONL outputs were rescored without rerunning generation using:

```bash
cd /work/dfm/HRM-Text
python scripts/rescore_piqa_evals.py \
  logs/dfm_evals/original_sapient_L_new_tasks_gemma4_judge/epoch_1/eee/PIQA-da/openai/hrm-original-sapient-L-epoch-1/dfa50a05c3b23d8609cd.jsonl \
  logs/dfm_evals/original_sapient_L_new_tasks_gemma4_judge/epoch_2/eee/PIQA-da/openai/hrm-original-sapient-L-epoch-2/839f2ca592f63c907898.jsonl \
  logs/dfm_evals/original_sapient_L_new_tasks_gemma4_judge/epoch_3/eee/PIQA-da/openai/hrm-original-sapient-L-epoch-3/7c3e7067c63b3396c133.jsonl \
  logs/dfm_evals/original_sapient_L_new_tasks_gemma4_judge/epoch_4/eee/PIQA-da/openai/hrm-original-sapient-L-epoch-4/aa0255714ba09be35e8f.jsonl \
  logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch1_parallel/piqa/epoch_1/eee/PIQA-da/openai/hrm-original-plus-mixed-L-piqa-epoch-1/203b5a01f3cab150e4a7.jsonl \
  --output logs/dfm_evals/piqa_strict_rescore_20260525.json
```

Strict rescore results:

```text
original_sapient epoch 1: accuracy 0.0000, invalid 108/108
original_sapient epoch 2: accuracy 0.0000, invalid 108/108
original_sapient epoch 3: accuracy 0.0000, invalid 108/108
original_sapient epoch 4: accuracy 0.0000, invalid 106/108
original+mixed epoch 1:  accuracy 0.1667, invalid 3/108
```

The old original Sapient PIQA scores were therefore scorer artifacts, not genuine PIQA performance. The original+mixed checkpoint mostly predicted `B` on an `A`-skewed set and remains low under the stricter scorer.

W&B sync update, verified on 2026-05-25. Confidence: high. The strict original Sapient PIQA values were logged to run `origLclean` under:

```text
dfm_eval/piqa/piqa_scorer/accuracy
dfm_eval/piqa/piqa_scorer/invalid_rate
```

with `dfm_eval/epoch` values 1 through 4.

IFEval-DA sharding update, verified on 2026-05-25. Confidence: high.

The original single-GPU original+mixed IFEval-DA run was stopped at about `66/541` completed samples because it was dominated by multi-minute generations. `dfm-evals/dfm_evals/tasks/ifeval_da.py` now accepts:

```text
num_shards
shard_index
```

and filters samples by `index % num_shards == shard_index` after the normal dataset load/shuffle/limit path.

Eight shard suites were added in:

```text
config/dfm_evals_hrm_ifeval_da_shards.yaml
```

The safe merge path is:

```text
1. Run each shard as its own Inspect eval on one GPU.
2. Do not log per-shard metrics to W&B.
3. Merge completed shard `.eval` zip files by reading all `samples/*.json`.
4. Recompute IFEval metrics over the union of per-sample `instruction_following` scores.
5. Log only the merged metrics to W&B.
```

Merger script:

```text
scripts/merge_ifeval_da_shards.py
```

Shard launch root:

```text
logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch1_ifeval_da_sharded
```

Superseded on 2026-05-25: the first eight-shard launch used `BATCH_SIZE=8` and
`INSPECT_MAX_CONNECTIONS=8`. It started successfully but provided poor progress
behavior because a long sample could hold a whole batch open before Inspect
flushed any completed sample records. The run was stopped before metrics were
logged.

Current launch root:

```text
logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch1_ifeval_da_sharded_b1
```

Current launch mode:

```text
BATCH_SIZE=1
INSPECT_MAX_CONNECTIONS=1
INCREMENTAL_WANDB_SYNC=0
FINAL_WANDB_SYNC=0
```

This still uses one shard per GPU, but logs only the merged metrics after all
shards complete. While the original+mixed training job is active, each eval
server shares a GPU with one training rank, so throughput is expected to be
uneven and lower than a dedicated eval run. Confidence: high.

Completed on 2026-05-25 at 14:02 local time. All eight shards completed and
the merged metrics were logged to W&B run `es1od1in`. The merged union covered
541 samples. Metrics:

```text
dfm_eval/ifeval-da/instruction_following/final_acc: 0.3185721627463338
dfm_eval/ifeval-da/instruction_following/final_stderr: 0.015870416956780143
dfm_eval/ifeval-da/instruction_following/inst_loose_acc: 0.4073226544622426
dfm_eval/ifeval-da/instruction_following/inst_loose_stderr: 0.015647363066797922
dfm_eval/ifeval-da/instruction_following/inst_strict_acc: 0.39931350114416475
dfm_eval/ifeval-da/instruction_following/inst_strict_stderr: 0.01553497876043891
dfm_eval/ifeval-da/instruction_following/prompt_loose_acc: 0.2365988909426987
dfm_eval/ifeval-da/instruction_following/prompt_loose_stderr: 0.018288827582625598
dfm_eval/ifeval-da/instruction_following/prompt_strict_acc: 0.23105360443622922
dfm_eval/ifeval-da/instruction_following/prompt_strict_stderr: 0.018138757170523406
```

Confidence: high.

Original+mixed epoch-2 dfm-evals launch, verified on 2026-05-25. Confidence:
high.

Epoch 2 checkpoint files are present under:

```text
checkpoints/original_plus_mixed_danish_instruction_rich/L/fsdp2_epoch_2
checkpoints/original_plus_mixed_danish_instruction_rich/L/carry_epoch_2.{0..7}.pt
```

The seven non-IFEval Danish tasks were launched first, with GPU 7 reserved for
the Gemma judge:

```text
log root: logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch2_parallel_then_ifeval
judge: unsloth/gemma-4-E4B-it as openai/gemma-4-e4b-judge
judge URL: http://127.0.0.1:8799/v1
GPU 0: hrm_danish_danish_citizen_tests, port 8702
GPU 1: hrm_danish_dala, port 8712
GPU 2: hrm_danish_gec_dala, port 8722
GPU 3: hrm_danish_wmt24pp_en_da, port 8732
GPU 4: hrm_danish_multi_wiki_qa, port 8742
GPU 5: hrm_danish_piqa, port 8752
GPU 6: hrm_danish_generative_talemaader, port 8762
GPU 7: Gemma judge, port 8799
```

As non-IFEval tasks finish, IFEval-DA shards are scheduled onto freed GPUs with
`BATCH_SIZE=1`, `INSPECT_MAX_CONNECTIONS=1`, no per-shard W&B logging, and a
final merged W&B sync.

Correction note: the first scheduler version accidentally reused port `8872`
for shard 1 because a Bash local-assignment expression used a stale `shard`
variable while calculating `port_base`. The invalid shard-1 attempt was killed
and moved aside as:

```text
logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch2_parallel_then_ifeval/ifeval_shard_1_invalid_port_*
```

The valid shard layout is:

```text
shard 0: port 8872, launched before the correction
shard 1+: ports 8912, 8922, 8932, 8942, 8952, 8962, 8972 as scheduled by the corrected supervisor
```

Corrected supervisor log:

```text
logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch2_parallel_then_ifeval/supervisor_remaining.log
```

When all shards complete, the corrected supervisor merges:

```bash
cd /work/dfm/HRM-Text
python scripts/merge_ifeval_da_shards.py \
  logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch2_parallel_then_ifeval/ifeval_shard_{0,1,2,3,4,5,6,7}/epoch_2/inspect/*.eval \
  --epoch 2 \
  --output logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch2_parallel_then_ifeval/merged_ifeval_da_metrics.json \
  --log-wandb \
  --project "Original Plus Mixed Danish Instruction Rich L" \
  --run-id es1od1in \
  --run-name "original-plus-mixed-danish-instruction-rich-L"
```

Epoch-2 completion, verified locally and through W&B sync logs on 2026-05-25.
Confidence: high.

All seven non-IFEval tasks completed and were re-synced as one consolidated
CP2 W&B history row at `dfm_eval/epoch=2`. The eight IFEval-DA shards also
completed, were merged into `merged_ifeval_da_metrics.json`, and were re-synced
as part of the same consolidated CP2 row after the initial per-task summaries
did not reliably remain visible through the W&B API while the training run was
active.

```text
dfm_eval/danish-citizen-tests/knowledge/accuracy: 0.5229357798165137
dfm_eval/danish-citizen-tests/knowledge/dfm_evals_mcc: 0.32175001283952764
dfm_eval/dala/linguistic-acceptability/dfm_evals_macro_f1: 0.024884792626728113
dfm_eval/dala/linguistic-acceptability/dfm_evals_mcc: -0.012718920251333386
dfm_eval/gec_dala/exact_match/mean: 0.005859375
dfm_eval/wmt24pp-en-da/chrf3pp/mean: 0.4914474618118289
dfm_eval/multi_wiki_qa/exact_match/mean: 0.82763671875
dfm_eval/multi_wiki_qa/f1/mean: 0.9187239022284758
dfm_eval/piqa/piqa_scorer/accuracy: 0.46296296296296297
dfm_eval/generative-talemaader/model_graded_fact/accuracy: 0.050742574257425746
dfm_eval/ifeval-da/instruction_following/final_acc: 0.35019213931316273
dfm_eval/ifeval-da/instruction_following/final_stderr: 0.016554524344104274
dfm_eval/ifeval-da/instruction_following/inst_loose_acc: 0.4405034324942792
dfm_eval/ifeval-da/instruction_following/inst_loose_stderr: 0.015728631269252082
dfm_eval/ifeval-da/instruction_following/inst_strict_acc: 0.4279176201372998
dfm_eval/ifeval-da/instruction_following/inst_strict_stderr: 0.015753402406761055
dfm_eval/ifeval-da/instruction_following/prompt_loose_acc: 0.2698706099815157
dfm_eval/ifeval-da/instruction_following/prompt_loose_stderr: 0.019102087526494387
dfm_eval/ifeval-da/instruction_following/prompt_strict_acc: 0.26247689463955637
dfm_eval/ifeval-da/instruction_following/prompt_strict_stderr: 0.0189337428760446
```

Launched mapping:

```text
shard 0: GPU 0, port 8601
shard 1: GPU 1, port 8611
shard 2: GPU 2, port 8621
shard 3: GPU 3, port 8631
shard 4: GPU 4, port 8641
shard 5: GPU 5, port 8651
shard 6: GPU 6, port 8661
shard 7: GPU 7, port 8671
```

Merge command after all eight shards complete:

```bash
cd /work/dfm/HRM-Text
python scripts/merge_ifeval_da_shards.py \
  logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch1_ifeval_da_sharded_b1/shard_{0,1,2,3,4,5,6,7}/epoch_1/inspect/*.eval \
  --epoch 1 \
  --output logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch1_ifeval_da_sharded_b1/merged_ifeval_da_metrics.json \
  --log-wandb \
  --project "Original Plus Mixed Danish Instruction Rich L" \
  --run-id es1od1in \
  --run-name "original-plus-mixed-danish-instruction-rich-L"
```

Standard eval W&B sync, verified on 2026-05-25. Confidence: high.

The current original+mixed L run's standard HRM evals are logged under the
`eval/...` prefix, separate from the Danish `dfm_eval/...` suite. Because the
standard eval jobs were split across per-task logs and sharded MATH logs,
`scripts/log_original_plus_mixed_standard_eval_to_wandb.py` composes exactly:

```text
epoch 1: ARC, BoolQ, DROP, GSM8k, HellaSwag, MATH, MMLU, Winogrande
epoch 2: ARC, BoolQ, DROP, GSM8k, HellaSwag, MMLU, Winogrande
```

CP2 MATH is intentionally omitted until all epoch-2 MATH shards complete and
are merged.

Command used:

```bash
cd /work/dfm/HRM-Text
python scripts/log_original_plus_mixed_standard_eval_to_wandb.py
```

The sidecar W&B sync reported success for run `es1od1in`, but the active
training run again showed the known live-run sidecar issue where remote summary
keys did not appear through the public API immediately. The same parsed metrics
were therefore patched into the remote run summary through the W&B API. A
post-patch API check returned `777` `eval/*` summary keys, with:

```text
eval/standard_eval_last_synced_epoch: 2
eval/standard_eval_cp2_math_synced: False
eval/MATH/acc/epoch_1: 0.3658
eval/MATH/acc/epoch_2: <missing>
eval/GSM8k/acc/epoch_2: 0.7301
eval/Winogrande/acc/epoch_2: 0.5951
```

At that check, the only active standard eval work left was CP2 MATH shard 6
and shard 7. Confidence: high.

CP2 standard MATH completion, verified on 2026-05-26. Confidence: high.

All eight epoch-2 MATH shards completed and no standard-eval processes remained.
The shards were merged and synced with:

```bash
cd /work/dfm/HRM-Text
python scripts/merge_standard_math_shards.py \
  logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_math_shards_v2/epoch_2/MATH_shard_*_of_8.log \
  --epoch 2 \
  --output logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_math_shards_v2/epoch_2/merged_math_metrics.json \
  --log-wandb \
  --project "Original Plus Mixed Danish Instruction Rich L" \
  --run-id es1od1in \
  --run-name "original-plus-mixed-danish-instruction-rich-L"
```

Merged epoch-2 MATH metrics:

```text
eval/MATH/n: 5000
eval/MATH/acc: 0.4412
eval/MATH/invalid: 0.0928
```

The active training process continues to overwrite the remote W&B summary back
to a small training-only summary, so direct summary patching did not persist.
However, W&B history verification returned both standard MATH rows:

```text
epoch 1: eval/MATH/acc = 0.3658, eval/MATH/invalid = 0.1100, eval/MATH/n = 5000
epoch 2: eval/MATH/acc = 0.4412, eval/MATH/invalid = 0.0928, eval/MATH/n = 5000
```

Use `eval/epoch` as the x-axis for these plots. Confidence: high.

Original+mixed CP3 queued-eval scheduler, launched on 2026-05-26. Confidence:
high for local queue state; medium for runtime until jobs complete.

The user requested one 8-GPU queue covering all CP3 standard eval tasks, all
8 standard MATH shards, all Danish dfm-eval tasks, and 4 IFEval-DA shards. The
following files were added:

```text
scripts/schedule_original_plus_mixed_cp3_evals.sh
config/dfm_evals_hrm_ifeval_da_4_shards.yaml
```

The scheduler is detached and running as:

```text
PID: 2007215
log root: logs/eval/original_plus_mixed_danish_instruction_rich_L_epoch3_queued_all
dfm log root: logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch3_queued_all
status: logs/eval/original_plus_mixed_danish_instruction_rich_L_epoch3_queued_all/status.tsv
queue: logs/eval/original_plus_mixed_danish_instruction_rich_L_epoch3_queued_all/jobs.tsv
```

At launch, `fsdp2_epoch_3` and `carry_epoch_3.{0..7}.pt` were not yet visible
under `checkpoints/original_plus_mixed_danish_instruction_rich/L`, so the
scheduler is in `WAIT_CHECKPOINT` state and will not start workers until the
checkpoint files exist. The check interval is `CHECKPOINT_WAIT_SECONDS=300`.

Queued jobs, `26` total:

```text
standard: GSM8k, DROP, MMLU, ARC, HellaSwag, Winogrande, BoolQ
standard_math: shard 0..7 of 8
dfm: danish_citizen_tests, dala, gec_dala, wmt24pp_en_da, multi_wiki_qa, piqa, generative_talemaader
dfm_ifeval: shard 0..3 of 4
```

Each worker owns one GPU and takes the next job from the shared queue when its
current job exits. `generative_talemaader` starts the Gemma judge
`unsloth/gemma-4-E4B-it` as `openai/gemma-4-e4b-judge` on the same GPU as that
job. Standard MATH and IFEval-DA are merged and synced after all workers finish.

Monitor:

```bash
cd /work/dfm/HRM-Text
tail -f logs/eval/original_plus_mixed_danish_instruction_rich_L_epoch3_queued_all/status.tsv
```

Stop if needed:

```bash
cd /work/dfm/HRM-Text
kill "$(cat logs/eval/original_plus_mixed_danish_instruction_rich_L_epoch3_queued_all/scheduler.pid)"
```

Incremental CP3 standard eval sync, verified on 2026-05-26. Confidence: high.

After the CP3 scheduler started, the first completed standard evals were synced
to W&B run `es1od1in` at `eval/epoch=3`:

```text
eval/ARC/acc: 0.5904
eval/ARC/invalid: 0.0
eval/ARC/n: 1172
eval/BoolQ/acc: 0.8294
eval/BoolQ/invalid: 0.0
eval/BoolQ/n: 3270
eval/Winogrande/acc: 0.6464
eval/Winogrande/invalid: 0.0
eval/Winogrande/n: 1267
```

W&B history verification returned epoch-3 values for all three tasks. At that
time, no dfm-evals had completed and MATH was still partial. Confidence: high.

Original+mixed CP3 IFEval-DA completion, verified on 2026-05-26. Confidence:
high.

The four CP3 IFEval-DA shards completed, were merged, and were synced to W&B
run `es1od1in` at `dfm_eval/epoch=3`. Evidence:

```text
merged metrics: logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch3_queued_all/merged_ifeval_da_metrics.json
sync log: logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch3_queued_all/merge_ifeval_da_wandb.log
W&B log line: Synced 4 W&B file(s), 0 media file(s), 0 artifact file(s) and 0 other file(s)
```

Merged epoch-3 IFEval-DA metrics:

```text
num_samples: 541
dfm_eval/ifeval-da/instruction_following/final_acc: 0.35809184618703394
dfm_eval/ifeval-da/instruction_following/final_stderr: 0.016830669337024047
dfm_eval/ifeval-da/instruction_following/inst_loose_acc: 0.4462242562929062
dfm_eval/ifeval-da/instruction_following/inst_loose_stderr: 0.015684688759299244
dfm_eval/ifeval-da/instruction_following/inst_strict_acc: 0.4279176201372998
dfm_eval/ifeval-da/instruction_following/inst_strict_stderr: 0.015609094571451737
dfm_eval/ifeval-da/instruction_following/prompt_loose_acc: 0.2846580406654344
dfm_eval/ifeval-da/instruction_following/prompt_loose_stderr: 0.0194187691064861
dfm_eval/ifeval-da/instruction_following/prompt_strict_acc: 0.2735674676524954
dfm_eval/ifeval-da/instruction_following/prompt_strict_stderr: 0.019183727107392846
```

For future checkpoints, prefer 8 IFEval-DA shards instead of 4 to reduce the
tail runtime. Confidence: medium.

English summarization eval, added on 2026-05-27. Confidence: high for local
implementation and smoke tests; medium for source-card metadata.

`GovReport` was added to the standard `eval/*` path in
`evaluation/benchmarks.py` and `evaluation/config/hrm_benchmarking.yaml`.
It uses the parquet-converted Hugging Face dataset
`ccdv/govreport-summarization`, config `document`, split `test`, with `report`
as the source document and `summary` as the reference. The originally considered
`launch/gov_report` source is CC-BY-4.0 and has simple `document`/`summary`
fields, but local smoke testing showed it still includes a dataset script and
this environment's `datasets` version refuses script-backed datasets:
`RuntimeError: Dataset scripts are no longer supported, but found gov_report.py`.

`GovReport` generation overrides are `condition=direct`, `max_context=4096`,
`max_tokens=512`, and `batch_size=2`. Metrics are `n`, `rouge1`, `rouge2`,
`rougeL`, `rougeLsum`, `bleu`, `chrf3`, and `chrf3pp`. ROUGE uses
`rouge_score` F1; BLEU and chrF use `sacrebleu` corpus scores, with `chrf3`
using `beta=3, word_order=0` and `chrf3pp` using `beta=3, word_order=2`.
Local smoke tests verified that `GovReport(split="test[:2]")` loads, computes
all metrics as plain Python floats, and resolves through
`load_model_class("benchmarks@GovReport", prefix="evaluation.")`. Run with:

```bash
cd /work/dfm/HRM-Text
python -m evaluation.main ckpt_path="<CHECKPOINT_PATH>" "run_only=[GovReport]"
```

It is less obviously contaminated by the original Sapient/FLAN summarization
task set than CNN/DailyMail, XSum, SAMSum, Gigaword, BillSum, Reddit TIFU,
Multi-News, or EUR-Lex summarization, all of which appear by name in the
original Sapient analytics. Source pages:
https://huggingface.co/datasets/launch/gov_report and
https://huggingface.co/datasets/ccdv/govreport-summarization.

Danish summarization eval, added on 2026-05-27. Confidence: high.

`NordjyllandNews` was added to the standard `eval/*` path in
`evaluation/benchmarks.py` and `evaluation/config/hrm_benchmarking.yaml`. It
uses the local DynaWord parquet file:

```text
data/downloads/datasets/danish_dynaword/data/nordjyllandnews/nordjyllandnews.parquet
```

The source file has `75,215` rows with a single `text` field. The benchmark uses
the `37,522` rows that contain an explicit `Referat:` reference. If the source
starts with `Lav et referat af nedenstående tekst:\n\nTekst:\n`, that wrapper is
removed before prompting. By default the eval uses an evenly spaced `1,000`
example subset to keep runtime practical; pass `max_samples=null` only when a
full 37k-example run is intended.

`NordjyllandNews` generation overrides are `condition=direct`,
`max_context=4096`, `max_tokens=128`, and `batch_size=8`. It uses the same
summarization metrics as `GovReport`: `n`, ROUGE F1, BLEU, `chrf3`, and
`chrf3pp`. Local smoke tests verified `NordjyllandNews(max_samples=3)` loads and
computes all metrics as plain Python values. Run with:

```bash
cd /work/dfm/HRM-Text
python -m evaluation.main ckpt_path="<CHECKPOINT_PATH>" "run_only=[NordjyllandNews]"
```

Summarization eval scheduler launch, verified on 2026-05-27. Confidence: high.

`scripts/schedule_summarization_evals_all_checkpoints.sh` queues only the
English/Danish summarization benchmarks:

```text
GovReport
NordjyllandNews
```

Default checkpoint coverage:

```text
original_sapient: epochs 1,2,3,4 under checkpoints/original_sapient/L
original_plus_mixed_danish_instruction_rich: epochs 1,2,3 under checkpoints/original_plus_mixed_danish_instruction_rich/L
```

The scheduler uses eight GPU lanes by default (`GPUS=0,1,2,3,4,5,6,7`) and a
shared `jobs.tsv` protected by `flock`, so each lane takes one job at a time.
The 2026-05-27 launch queued `14` jobs and started all eight initial original
Sapient summarization jobs:

```text
log root: logs/eval/summarization_all_checkpoints_20260527T085348
scheduler PID: 480235
worker PIDs: 480243 480244 480245 480246 480247 480248 480249 480250
status: logs/eval/summarization_all_checkpoints_20260527T085348/status.tsv
```

Launch command:

```bash
cd /work/dfm/HRM-Text
LOG_ROOT="logs/eval/summarization_all_checkpoints_$(date +%Y%m%dT%H%M%S)"
mkdir -p "$LOG_ROOT"
setsid scripts/schedule_summarization_evals_all_checkpoints.sh \
  > "$LOG_ROOT/scheduler.log" 2>&1 < /dev/null &
echo $! > "$LOG_ROOT/scheduler.pid"
```

Generation retention for summarization vs translation evals, verified on
2026-05-27. Confidence: high.

The repo's standard `evaluation.main` path used for `eval/GovReport/*` and
`eval/NordjyllandNews/*` does not persist per-sample generations. It keeps
generated strings in memory, passes them into `benchmark.compute_metrics(...)`,
and prints only progress bars plus the final `EVALUATION SUMMARY` to stdout.
The summarization logs under
`logs/eval/summarization_all_checkpoints_20260527T085348/**/{GovReport,NordjyllandNews}.log`
therefore contain metrics but not prompt/prediction/reference triples.

The Danish translation evals run through `dfm-evals`/Inspect do persist
per-sample records. Each `wmt24pp-en-da` `.eval` zip contains `samples/*.json`
entries with `input`, `target`, `messages`, `output.completion`, `scores`, and
metadata. The Every Eval Ever exports also write `.json` and `.jsonl` copies
under each task's `eee/` directory.

BERTScore note, updated on 2026-05-27. Confidence: high for local dependency
state, inspected Inspect archives, and generation-retention caveat; medium for
metric usefulness by task. `bert-score` is installed in the main HRM environment
and in the nested `dfm-evals` environment, with `xlm-roberta-large` selected as
the shared multilingual scorer model.

BERTScore is appropriate as an auxiliary metric for tasks with natural-language
predictions and reference text: `wmt24pp-en-da`, `generative-talemaader`,
`gec_dala`, and the new dfm-evals summarization tasks `govreport` and
`nordjyllandnews`. It is less informative but possible for `multi_wiki_qa`
because many answers are only one to three words. It should not be used for
classification/constraint-only tasks such as `danish-citizen-tests`, `dala`,
`piqa`, or `ifeval-da`.

The already completed standard summarization evals cannot be rescored with
BERTScore unless they are rerun, because `evaluation.main` did not persist
prompt/prediction/reference triples. Translation and other dfm-evals tasks can
be rescored from stored Inspect samples because those archives contain
`output.completion` and references. IFEval-DA archives were inspected locally:
samples have an empty `target`, the output is the model's free-form constrained
response, and scoring records instruction-following booleans/counts
(`prompt_level_strict`, `inst_level_strict`, `prompt_level_loose`,
`inst_level_loose`, `num_instructions`) rather than reference similarity.

Stored-generation BERTScore run, verified on 2026-05-27. Confidence: high.

`scripts/score_stored_dfm_eval_bertscore.py` computes offline BERTScore from
stored Inspect `.eval` archives without rerunning model inference. It uses
`bert-score` with `xlm-roberta-large`, chooses the best reference by F1 when a
sample has multiple references, and deduplicates repeated archives by
`family/epoch/task`, keeping the complete archive with the largest sample
count/newest mtime. The full command was:

```bash
cd /work/dfm/HRM-Text
python scripts/score_stored_dfm_eval_bertscore.py \
  --batch-size 32 \
  --output logs/dfm_evals/bertscore_xlm_roberta_large/stored_metrics.json \
  2>&1 | tee logs/dfm_evals/bertscore_xlm_roberta_large/stored_metrics.log
```

The run completed for 28 stored checkpoint/eval combinations:

```text
original_sapient epoch 1: gec-dala 0.898468, generative-talemaader 0.839199, multi-wiki-qa 0.794420, wmt24pp-en-da 0.857832
original_sapient epoch 2: gec-dala 0.965995, generative-talemaader 0.841373, multi-wiki-qa 0.801824, wmt24pp-en-da 0.866615
original_sapient epoch 3: gec-dala 0.968691, generative-talemaader 0.844272, multi-wiki-qa 0.815243, wmt24pp-en-da 0.873644
original_sapient epoch 4: gec-dala 0.982645, generative-talemaader 0.839617, multi-wiki-qa 0.831438, wmt24pp-en-da 0.876078
original_plus_mixed_danish_instruction_rich epoch 1: gec-dala 0.971922, generative-talemaader 0.857760, multi-wiki-qa 0.988429, wmt24pp-en-da 0.934503
original_plus_mixed_danish_instruction_rich epoch 2: gec-dala 0.807852, generative-talemaader 0.858760, multi-wiki-qa 0.982432, wmt24pp-en-da 0.937346
original_plus_mixed_danish_instruction_rich epoch 3: gec-dala 0.862708, generative-talemaader 0.859533, multi-wiki-qa 0.978532, wmt24pp-en-da 0.939909
```

Stored-generation BERTScore W&B sync, verified on 2026-05-27. Confidence:
high for upload logs and original clean API summary visibility; medium for the
active original-plus-mixed run summary because that live run has repeatedly
overwritten sidecar summary values.

`scripts/log_stored_bertscore_to_wandb.py` logs
`logs/dfm_evals/bertscore_xlm_roberta_large/stored_metrics.json` to W&B under
metric keys such as:

```text
dfm_eval/wmt24pp-en-da/bertscore_xlm_roberta_large/f1
dfm_eval/gec-dala/bertscore_xlm_roberta_large/precision
dfm_eval/generative-talemaader/bertscore_xlm_roberta_large/recall
dfm_eval/multi-wiki-qa/bertscore_xlm_roberta_large/n
```

The sync command was:

```bash
cd /work/dfm/HRM-Text
python scripts/log_stored_bertscore_to_wandb.py \
  2>&1 | tee logs/dfm_evals/bertscore_xlm_roberta_large/wandb_sync.log
```

W&B reported upload success for `origLclean` with history steps `65227-65230`
and for `es1od1in`. The public API summary check confirmed representative
`origLclean` keys, for example
`dfm_eval/wmt24pp-en-da/bertscore_xlm_roberta_large/f1/epoch_1 =
0.857831776017944`. The active `es1od1in` run did not retain these values in
the public summary immediately after sync, matching prior active-run summary
overwrite behavior; the W&B client still reported a successful history upload.

Summarization under dfm-evals, added on 2026-05-27. Confidence: high for local
registration and shell/compile checks; medium until the full scheduler is run.

`dfm-evals/dfm_evals/tasks/summarization.py` adds `dfm_evals/govreport` and
`dfm_evals/nordjyllandnews` as Inspect tasks. They use the same data/prompt
policy as the standard `evaluation.main` summarization tasks but persist
per-sample generations in Inspect `.eval` archives. Their scorer logs ROUGE,
BLEU, chrF3, chrF3++, and BERTScore precision/recall/F1 with
`xlm-roberta-large` by default.

`config/dfm_evals_hrm_single_tasks.yaml` now exposes:

```text
hrm_summarization_govreport
hrm_summarization_nordjyllandnews
```

`scripts/schedule_dfm_summarization_bertscore_all_checkpoints.sh` queues the
two summarization tasks over the seven existing L checkpoints: original Sapient
epochs 1-4 and original-plus-mixed epochs 1-3. It runs up to 8 independent jobs
in parallel using `GPUS=0,1,2,3,4,5,6,7`; each job sets
`CUDA_VISIBLE_DEVICES` for both the HRM checkpoint server and the dfm-evals
process, so a single eval is not distributed across GPUs. The launch command is:

```bash
cd /work/dfm/HRM-Text
export LOG_ROOT="logs/dfm_evals/summarization_bertscore_all_checkpoints_$(date +%Y%m%dT%H%M%S)"
mkdir -p "$LOG_ROOT"
setsid scripts/schedule_dfm_summarization_bertscore_all_checkpoints.sh \
  > "$LOG_ROOT/scheduler.log" 2>&1 < /dev/null &
echo $! > "$LOG_ROOT/scheduler.pid"
```

To get BERTScore for the summarization tasks, rerun these CP x eval pairs under
dfm-evals because the previous standard `eval/*` summarization run did not store
generations:

```text
original_sapient epochs 1,2,3,4: govreport, nordjyllandnews
original_plus_mixed_danish_instruction_rich epochs 1,2,3: govreport, nordjyllandnews
```

Summarization W&B sync, verified on 2026-05-27. Confidence: high for W&B upload
logs and original clean summary visibility; medium for active-run summary
visibility because the live original+mixed training run has previously
overwritten sidecar summaries.

`scripts/log_summarization_evals_to_wandb.py` parses
`logs/eval/summarization_all_checkpoints_20260527T085348` and logs
`GovReport`/`NordjyllandNews` metrics under the standard `eval/*` prefix with
`eval/epoch` as the step metric. It maps:

```text
original_sapient -> project "Original Plus Mixed Danish Instruction Rich L", run "origLclean"
original_plus_mixed_danish_instruction_rich -> same project, run "es1od1in"
```

The sync command was:

```bash
cd /work/dfm/HRM-Text
python scripts/log_summarization_evals_to_wandb.py \
  2>&1 | tee logs/eval/summarization_all_checkpoints_20260527T085348/wandb_sync.log
```

W&B reported successful uploads for both runs. The original clean run API
summary shows `eval/summarization_last_synced_epoch=4`. The active
original+mixed sidecar run reported upload success for `history_lines=3` at
`status="200 OK"`, but its public summary did not retain the summarization keys,
matching the known active-run summary overwrite behavior.

## Caveat

This is a paper-faithful original-mix run, not the safer mixed-corpus policy. It includes Sapient sources we previously flagged for review when discussing licensing/provenance/GDPR risk.

## Separation Rules

- Do not run `scripts/build_filtered_source_tree.py` or `scripts/convert_filtered_sources.py` for the original reproduction path.
- Do not point original reproduction sampling at `data/tokenized_mixed`.
- Do not point mixed-corpus training at `data/sampled_original_sapient`.
- Keep original checkpoints under `checkpoints/original_sapient/L`.
- Keep future mixed-corpus checkpoints under a separate path, for example `checkpoints/mixed/<run-name>`.
- Keep analytics files separate:

```text
Mixed corpus analytics:          data/show_analytics.md
Original Sapient analytics:      data/show_analytics_original_sapient.md
```
