# Original L Reproduction

Last updated: 2026-05-26  
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

## Download Status

On 2026-05-25, Hugging Face metadata for `sapientinc/HRM-Text-data-io-cleaned-20260515` showed `5,213` files matching the original Sapient allow patterns, with total size about `347.79 GB` / `323.90 GiB`. The current checkout resumed this download into:

```text
data/downloads/datasets/sapient_cleaned
```

The downloader was restarted with one worker as a soft bandwidth limiter:

```bash
conda run -n hrm python scripts/download_training_datasets.py --groups sapient --download --max-workers 1
```

This is not a hard bytes-per-second cap; it only limits concurrent Hugging Face transfers. Verified local progress after restart: the partial tree moved from about `30G` to `31G`, while incomplete cache files dropped from `30` to `21`, so the one-worker resume path is working. Confidence: high.

Status, 2026-05-26: the resumed download completed locally. Verification commands reported:

```text
du -sh data/downloads/datasets/sapient_cleaned                           -> 324G
find data/downloads/datasets/sapient_cleaned -name "*.incomplete" | wc -l -> 0
find data/downloads/datasets/sapient_cleaned/data \
     data/downloads/datasets/sapient_cleaned/data_clustered -type f | wc -l -> 5212
```

The downloader's own final summary reported `325.9 GB`, `5222 files`, and scanned `5213` selected Hugging Face files. Confidence: high.

MPS branch partial-data note, 2026-05-25: after stopping a still-running background Sapient downloader, the local partial tree in `/Users/petersk/Nobackup/HRM-Text-mps/data/downloads/datasets/sapient_cleaned` contained `490` completed `.parquet`/`.jsonl` inputs under the original Sapient data roots and `1` incomplete Hugging Face cache file. The completed inputs were tokenized separately into:

```text
data/tokenized_original_sapient_partial
```

Verified output: `490` tokenized metadata files, about `83G` on disk. A final tokenizer validation scan reported `Processing 0 files on 11 threads...`. This is not the full original Sapient reproduction dataset; it is a partial snapshot of the completed files available after the interrupted download. Confidence: high.

The tokenizer was run from the repo root with the already-built release binary:

```bash
cd /Users/petersk/Nobackup/HRM-Text-mps
data_io/tokenizer/target/release/tokenizer \
  data/downloads/datasets/sapient_cleaned/data_clustered \
  data/downloads/datasets/sapient_cleaned/data \
  --tokenizer-path data_io/trained_tokenizers/bpe/tokenizer.json \
  -o data/tokenized_original_sapient_partial \
  --workers 12
```

Operational note: the tokenizer is resumable for completed outputs. Restarting the same command with a higher worker count skipped directories that already had matching metadata and reported only the remaining files. On the M2 Max machine, the 12-worker run used about `6.1G` RSS during the large pass and completed the partial 490-file set. Confidence: high.

Small smoke sample built from three completed tokenized SYNTH shards:

```text
Tokenized subset view: data/tokenized_original_sapient_partial_smoke
Sampled smoke data:   data/sampled_original_sapient_partial_smoke
```

Sampler command:

```bash
cd /Users/petersk/Nobackup/HRM-Text-mps/data_io
conda run -n hrm python sample_tokenized.py \
  tokenized_path=../data/tokenized_original_sapient_partial_smoke \
  output_path=../data/sampled_original_sapient_partial_smoke \
  epochs=1 \
  concat_workers=2
```

Verified smoke sample metadata: `max_seq_len=4097`, `total_length=21,359,878`, output size about `519M`. The sampler covered `60,000` rows from `SYNTH__synth_175.parquet`, `SYNTH__synth_176.parquet`, and `SYNTH__synth_230.parquet`. Confidence: high.

MPS smoke training against that sampled dataset passed two steps outside the sandbox:

```bash
cd /Users/petersk/Nobackup/HRM-Text-mps
conda run -n hrm python scripts/debug_nan_training_step.py \
  --steps 2 \
  --override data.path=data/sampled_original_sapient_partial_smoke \
  --override accelerator_type=mps \
  --override compile_train_batch=false \
  --override fwd_bwd_dtype=float32 \
  --override global_batch_size=64 \
  --override epochs=1 \
  --override lr_warmup_steps=1 \
  --override ema=null \
  --override arch.n_layers=2 \
  --override arch.hidden_size=64 \
  --override arch.num_heads=4 \
  --override arch.expansion=2 \
  --override arch.half_layers=false \
  --override arch.H_cycles=1 \
  --override arch.L_cycles=1 \
  --override +arch.bp_min_steps=1 \
  --override arch.bp_max_steps=1
```

Result: both steps had finite loss, metrics, gradients, parameters, and post-optimizer parameters. Confidence: high.

## Current Process State

As of 2026-05-26 in the MPS checkout, original Sapient tokenization and sampling completed locally:

```text
Tokenized path: data/tokenized_original_sapient
Tokenized metadata files: 5212 / 5212
Tokenized size: 681G

Sampled path: data/sampled_original_sapient
Sampled size: 669G
Analytics: data/show_analytics_original_sapient.md
```

`data/sampled_original_sapient/metadata.json` reports `max_seq_len=4097` and `total_length=14,035,178,678` tokens per epoch. The four generated epoch directories therefore cover about `56,140,714,712` sampled tokens total, matching the previously recorded original Sapient reference total to rounding. The sampler emitted known prefix-overlap warnings for `flan__cot_*` tasks and then completed successfully. Confidence: high.

A full-distribution smoke dataset was derived from `data/sampled_original_sapient` on 2026-05-26:

```text
Path: data/sampled_original_sapient_smoke2
Target tokens across 4 epochs: 56,000,000
Actual tokens across 4 epochs: 56,001,530
metadata.total_length: 14,000,382
On-disk size: 6.5M plus a symlinked tokens.npy
tokens.npy -> ../sampled_original_sapient/tokens.npy
```

It was created by `scripts/create_smoke_from_sampled.py`, taking prefixes from the already shuffled full sampled epoch indices, so it preserves the full sampled dataset distribution in expectation without re-sampling from tokenized shards. `V1Dataset` successfully loaded a batch from this dataset. Confidence: high.

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

Prepared on 2026-05-24, not yet run end-to-end: `external/dfm-evals` was cloned from `https://github.com/danish-foundation-models/dfm-evals`, and three local scripts were added:

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

Additional dfm-evals task inventory, verified on 2026-05-24: local `external/dfm-evals` is at upstream `main` commit `9b6cf828ccffdbde54dd8ed2e4d06a37f979cd2a`. Registered local task names are `dfm_evals/bfcl-v1`, `dfm_evals/bfcl-v1-da`, `dfm_evals/dala`, `dfm_evals/danish-citizen-tests`, `dfm_evals/gec_dala`, `dfm_evals/generative-talemaader`, `dfm_evals/ifeval-da`, `dfm_evals/multi_wiki_qa`, `dfm_evals/piqa`, `dfm_evals/ruler`, and `dfm_evals/wmt24pp-en-da`. No task named `daisy` exists in this checkout. The HRM-compatible suite already ran the non-judge Danish tasks except `piqa` and `ifeval-da`; `generative-talemaader` requires a judge model, `ruler` needs a <=4096-token configuration for these checkpoints, and BFCL/agentic tasks need tool/calling behavior that the current simple HRM OpenAI shim is not expected to handle well. Confidence: high.

Suite update, verified on 2026-05-24: `config/dfm_evals_hrm.yaml:hrm_danish` now includes `dfm_evals/piqa`, `dfm_evals/ifeval-da`, and `dfm_evals/generative-talemaader` in the same suite as the existing Danish tasks. `uv sync --project external/dfm-evals --extra ifeval` was run successfully, installing `instruction-following-eval`, `nltk`, `langdetect`, `immutabledict`, and `joblib` for `ifeval-da`. `scripts/run_dfm_evals_on_checkpoints.sh` now accepts `JUDGE_MODEL` and `JUDGE_BASE_URL` and forwards them to `evals suite`; `JUDGE_MODEL` is required when running `generative-talemaader`, because that task uses a model-graded scorer. Confidence: high.

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
uv run --project external/dfm-evals evals eee inspect \
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
