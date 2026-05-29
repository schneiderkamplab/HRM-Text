# Current State

Last updated: 2026-05-28  
Confidence: high  
Scope: Local repo state and verified commands from this session.

## Environment

- Repo: `/work/dfm/HRM-Text`
- Active Python env observed earlier: `/home/ucloud/miniforge3/envs/hrm`
- GPU target: NVIDIA B200 / Blackwell
- CUDA toolkit: `/usr/local/cuda-13.2` installed by the user
- `uv`: upgraded in env to `0.11.15`

## Dependency State

- FlashAttention 3 was attempted but rejected for B200 because the Hopper FA3 path did not produce a viable Blackwell runtime.
- FlashAttention 4 from `Dao-AILab/flash-attention`, subdirectory `flash_attn/cute`, is installed and smoke-tested.
- `requirements.txt`, `docker/requirements/torch_extensions.txt`, `pyproject.toml`, and `uv.lock` were updated for FA4.

## Code Adaptation State

- `models/flash_attention_prefixlm_v2.py` now uses FA4 varlen APIs.
- `models/layers.py` now uses PyTorch SDPA for cache attention instead of FA3 kvcache.
- Py-compile and CUDA smoke tests passed earlier for PrefixLM attention and cache attention.

## Data State

Update on 2026-05-27:

- New DFM gated additions downloaded and converted:
  `laerebogen_with_followups`, `synquid_wiki_instruct_da`,
  `oliverkinch_instruct_bt`, `synquid_mt_da_deepseek`, and
  `synquid_wildchat_100k_qwen_messages`.
- `data_io/prefix_config_dfm.yaml` defines the DFM sampling policy and
  `config/data/dfm.yaml` points training at `data/sampled_dfm`.
- A subset tokenizer run against `data/converted_sources_dfm_new` pruned
  existing `data/tokenized_mixed` outputs because the Rust tokenizer removes
  output directories not present in its current input root. Recovery was started
  by running the tokenizer against the full `data/converted_sources` tree with
  one low-priority worker. A watcher will sample `data/sampled_dfm` only after
  the tokenizer log reports `Done.`.

Superseded context from earlier sessions:

- `data_io` is cloned under `/work/dfm/HRM-Text/data_io`.
- Downloads were run with:

```bash
python scripts/download_training_datasets.py --groups all --exclude-gated --download
```

- Because `--exclude-gated` was used, gated sources such as Laerebogen, Wiki Instruct DA, Instruct BT, and gated Synquid WildChat variants are not part of that run.
- `data/filtered_sources` was built with:

```bash
python scripts/build_filtered_source_tree.py --force
```

- The user reported the final filtered tree build:

```text
Allowed files:      1,525
Denied files:       4,073
Allowed bytes:      248,502,793,134
```

## Active Work

Update on 2026-05-27 20:45 Europe/Berlin:

- CP4 evaluation for `original_plus_mixed_danish_instruction_rich/L` completed.
  The queued scheduler reached `FINAL_MERGE_END`, with standard evals, MATH
  shards, DFM tasks, and IFEval-DA shards all finishing with status 0 and
  writing/syncing W&B logs under
  `logs/eval/original_plus_mixed_danish_instruction_rich_L_epoch4_queued_all`
  and
  `logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch4_queued_all`.
  Confidence: high.
- DFM data prep is not complete. The full-tree tokenizer recovery is still
  running as PID `1128417` with one low-priority worker against
  `data/converted_sources`; it has begun rebuilding `data/tokenized_mixed`.
  The sampling watcher PID `1135056` is still waiting and `data/sampled_dfm`
  has not been produced yet. Confidence: high.

Superseded by 2026-05-28 00:00 Europe/Berlin:

- The one-worker tokenizer PID `1128417` and watcher PID `1135056` were stopped
  deliberately and replaced by a two-worker full-tree tokenizer run. New
  tokenizer PID: `1941931`; new watcher PID: `1942797`. Command:

```bash
ionice -c2 -n7 nice -n 10 ./data_io/tokenizer/target/release/tokenizer \
  data/converted_sources \
  --tokenizer-path /work/dfm/HRM-Text/data_io/trained_tokenizers/bpe/tokenizer.json \
  --workers 2 \
  -o data/tokenized_mixed
```

- The restarted tokenizer recognized `33` already completed tokenized dirs and
  reported `Processing 1344 files on 2 threads...`. The watcher now waits for
  PID `1941931` and samples `data/sampled_dfm` only if the tokenizer log
  contains `Done.` and more than 1000 tokenized dirs are present. Confidence:
  high.

Update on 2026-05-28 08:35 Europe/Berlin:

- CP4 metrics for `original_plus_mixed_danish_instruction_rich/L` were manually
  re-synced to W&B run `es1od1in` in project
  `Original Plus Mixed Danish Instruction Rich L`. The sync used the CP4
  standard logs, merged MATH metrics, DFM EEE exports, and merged IFEval-DA
  metrics, and reported `231` metrics synced. Log:
  `logs/eval/original_plus_mixed_danish_instruction_rich_L_epoch4_queued_all/wandb_sync_all_cp4_rerun.log`.
  Confidence: high.

Later update on 2026-05-28:

- GovReport and NordjyllandNews were removed from the standard original+mixed
  eval queues in `scripts/schedule_original_plus_mixed_cp3_evals.sh` and
  `scripts/evaluate_original_plus_mixed_standard_split.sh`; future runs should
  treat these as DFM summarization evals instead of standard `eval/*` tasks.
  Confidence: high.
- Original+mixed CP4 was evaluated on the DFM summarization tasks
  `dfm_evals/govreport` and `dfm_evals/nordjyllandnews`. Both tasks completed
  with status 0 and synced 10 metrics each to W&B run `es1od1in` under
  `dfm_eval/govreport/*` and `dfm_eval/nordjyllandnews/*`. Logs:
  `logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch4_summarization_dfm_eval`.
  Confidence: high.
- `scripts/schedule_dfm_summarization_bertscore_all_checkpoints.sh` now supports
  `SKIP_ORIGINAL=1` and `SKIP_ORIGINAL_PLUS_MIXED=1`, and its server cleanup
  guard tolerates an unset `server_pid`. This avoids accidental old-family jobs
  and spurious final status 1 after successful task completion. Confidence:
  high.
- A code-generation DFM eval was added as `dfm_evals/humaneval`, wrapping
  `inspect-evals` HumanEval with Docker sandbox execution by default. The HRM
  suite entry is `hrm_code_humaneval` in
  `config/dfm_evals_hrm_single_tasks.yaml`. A zero-sample CLI probe resolved the
  task and loaded the HumanEval dataset successfully:

```bash
OPENAI_API_KEY=inspectai uv run --project dfm-evals evals suite hrm_code_humaneval \
  --file config/dfm_evals_hrm_single_tasks.yaml \
  --target-model openai/dummy \
  --target-base-url http://127.0.0.1:9/v1 \
  --mode set -- --limit 0 --log-dir /tmp/hrm_humaneval_probe --log-dir-allow-dirty
```

  Confidence: high for registration; medium for full execution because a real
  run requires a working code sandbox.
- HumanEval was run on 2026-05-28 for all 8 available L checkpoints using GPUs
  `0,1,2,3` and the local sandbox fallback because Docker was not installed on
  the node. Logs are under
  `logs/dfm_evals/humaneval_all_checkpoints_20260528`. All eight W&B sync logs
  report successful sync of `dfm_eval/humaneval/verify/accuracy`.

  Results:

  - Original Sapient epochs 1-4: accuracy `0.000`, `0.000`, `0.000`, `0.000`.
  - Original+mixed Danish-rich epochs 1-4: accuracy `0.146`, `0.238`, `0.256`,
    `0.226`.

  Confidence: high.
- Tokenization was restarted again on 2026-05-28 after two-worker resume attempts
  exited without `Done.`. The active stable fallback is one worker:
  tokenizer PID `3661868`, watcher PID `3662969`, log
  `logs/tokenize/dfm_full_recovery_tokenizer_workers1_resume5.log`. It reported
  `Processing 930 files on 1 threads...` after recognizing `447` completed
  tokenized dirs. Confidence: high.
- The one-worker tokenizer finished rebuilding the expected `1377` tokenized
  dirs, but its log did not contain `Done.`, so the strict watcher refused to
  start sampling. The one unmatched source file was
  `data/converted_sources/nemotron_swe/data/swe.parquet.unsplit`, the parked
  unsplit SWE file, not an expected tokenizer output. DFM sampling was started
  manually with `data_io/sample_tokenized.py` and is writing
  `data/sampled_dfm`. Confidence: high.

- Mixed-corpus tokenization is active at `data/tokenized_mixed`; it was previously at `1316/1317` files with the final tail in `nemotron_swe/data/swe.parquet`.
- Original Sapient-only tokenization for the L reproduction run has been launched into `data/tokenized_original_sapient`.
- The original Sapient tokenization command scans `5212` source files from:

```text
data/downloads/datasets/sapient_cleaned/data_clustered
data/downloads/datasets/sapient_cleaned/data
```

See [[original-l-reproduction]] for the run plan.

Update on 2026-05-24:

- The active L run uses `data=original_plus_mixed_danish_instruction_rich`.
- `config/data/original_plus_mixed_danish_instruction_rich.yaml` points to `data/sampled_original_plus_mixed_danish_instruction_rich`.
- This sample preserves the original Sapient covered-token budget essentially exactly:
  - Original Sapient sample: `56,140,714,711` covered tokens across 4 epochs.
  - Original portion inside Danish-rich sample: `56,140,181,363` covered tokens across 4 epochs.
  - Difference: `-533,348` tokens, about `0.00095%`.
- All `5212 / 5212` original Sapient tokenized tasks are present; no original tasks are missing.
- The Danish-rich sample adds mixed/Danish content on top, with `110,736,199,356` global covered tokens across 4 epochs.

See [[data-mix-policy]] for the per-category and task-level comparison.

Later update on 2026-05-24:

- Mixed-only filtered sampling with the default prefix config completed at `data/sampled_mixed_english_danish_filtered`, but it was too large: `70,644,435,216` tokens per epoch.
- Cause: the default prefix caps did not match `sapient_cleaned__...` task names in `data/tokenized_mixed`.
- A capped config was added at `data_io/prefix_config_mixed_2x_original.yaml`.
- Dry-run estimate with PrefixLM truncation/filtering: `24,630,898,966` tokens per epoch, about `1.755x` the original Sapient per-epoch size and below the requested `2x` ceiling.
- The capped sampling run completed. Final `metadata.total_length` is `24,630,436,020` tokens per epoch, also about `1.755x` original and below the requested `2x` ceiling.
- Outputs:
  - `data/sampled_mixed_english_danish_filtered_2x_original`
  - `data/show_analytics_mixed_english_danish_filtered_2x_original.md`
  - `logs/sample_mixed_english_danish_filtered_2x_original.err`
- Hydra data config: `config/data/mixed_english_danish_filtered_2x_original.yaml`
- Note: the output directory is still about `625G` because `sample_tokenized.py` copies the full source token bank into `tokens.npy`; only the epoch indices are capped.

Update on 2026-05-21:

- The mixed corpus now has `1326` converted source files after splitting `nemotron_swe/data/swe.parquet` into `swe_part_00.parquet` through `swe_part_09.parquet`.
- A detached `tmux` tokenizer session `hrm_tok_mixed` is running one effective worker on the full `data/converted_sources` tree. It reported `Processing 10 files on 1 threads...`, corresponding to the missing split SWE shards.
- A detached `tmux` tokenizer session `hrm_tok_original` is running one effective worker on the original Sapient roots. It reported `Processing 77 files on 1 threads...`.
- Logs:
  - `logs/tokenizer_mixed_swe_resume.log`
  - `logs/tokenizer_original_resume.log`

Monitor commands:

```bash
tmux capture-pane -pt hrm_tok_mixed -S -40
tmux capture-pane -pt hrm_tok_original -S -40
find /work/dfm/HRM-Text/data/tokenized_mixed -name metadata.json | wc -l
find /work/dfm/HRM-Text/data/tokenized_original_sapient -name metadata.json | wc -l
```

Later update on 2026-05-21:

- `hrm_tok_mixed` was stopped and restarted after incremental conversion added new mixed sources.
- At restart, `data/converted_sources` had `1340` tokenizable files and `data/tokenized_mixed` had `1317` completed metadata files.
- The restarted mixed tokenizer reported `Processing 23 files on 1 threads...`.
- `hrm_tok_original` was left running.

Later update on 2026-05-21:

- The mixed tokenizer began reading the accidentally restored unsplit `data/converted_sources/nemotron_swe/data/swe.parquet`.
- `hrm_tok_mixed` was stopped, `swe.parquet` and its stale `swe.parquet.convert_meta.json` sidecar were removed, and the mixed tokenizer was restarted.
- After cleanup, `data/converted_sources` had `1339` tokenizable files, `data/tokenized_mixed` had `1318` completed metadata files, and the restarted mixed tokenizer reported `Processing 21 files on 1 threads...`.

## Filesystem / Scratch State

Verified on 2026-05-21:

- `/work` and `/work/dfm` are WEKA (`wekafs`) mounts.
- `/tmp`, `/var/tmp`, `/mnt`, `/opt`, and `/var/lib` resolve to the container root overlay, not to a separate clean local scratch mount.
- `/dev/shm` is tmpfs with about `2.8T` available; avoid using it for this pipeline unless explicitly chosen, because it consumes RAM-backed memory.
- `/etc/ucloud` and `/opt/ucloud` are local XFS empty-dir mounts but only about `46G`, too small for the tokenizer staging experiments.
- The node exposes NVMe block devices (`nvme0n1` and `nvme1n1`), but no large directly mounted writable NVMe scratch path is visible inside the container.

Operational consequence: the failed `/tmp/tokenize` staging attempt was not a good test of a clean local disk. Until a real local NVMe scratch mount is provided by UCloud/admin, run tokenization from `/work/dfm/HRM-Text` with a small worker count and `nice`/`ionice`.

## Possible `data_io` Relocation

Verified on 2026-05-24. Confidence: high.

`data_io` is currently an untracked nested git checkout at `/work/dfm/HRM-Text/data_io`. Moving it to `/work/dfm/HRM-Text/external/data_io` is mostly a path refactor. Required updates include:

- root docs and agent notes that say `data_io/tokenizer` must be run from `data_io/tokenizer`;
- runnable scripts with hard-coded `REPO_ROOT / "data_io"` or `${REPO_ROOT}/data_io`, especially `scripts/prepare_40b_sapient_plus_danish.py` and `scripts/reproduce_original_sapient_l.sh`;
- cleanup safety guards in `scripts/cleanup_failed_training_run.sh`;
- wiki commands under `wiki/pages/*` and `wiki/entities/*`;
- any shell commands copied from prior notes that reference `data_io/trained_tokenizers/bpe/tokenizer.json`, `data_io/tokenizer`, or `data_io/sample_tokenized.py`.

Prefer adding one canonical variable such as `DATA_IO_DIR=${DATA_IO_DIR:-${REPO_ROOT}/external/data_io}` in scripts rather than scattering the new path.

## `dfm-evals` Location

Verified on 2026-05-24. Confidence: high.

`dfm-evals` is an untracked nested git checkout at `/work/dfm/HRM-Text/dfm-evals`. It was moved from `/work/dfm/HRM-Text/external/dfm-evals` with its local `.venv` intact. The nested checkout's git status remained unchanged by the move; it still has local task patches in `dfm_evals/tasks/danish_citizen_tests.py` and `dfm_evals/tasks/talemaader/task.py`.

The main runnable reference is `scripts/run_dfm_evals_on_checkpoints.sh`, whose default is:

```bash
DFM_EVALS_DIR="${DFM_EVALS_DIR:-${REPO_ROOT}/dfm-evals}"
```

No model training configs depend on the path directly. Existing logs under `logs/dfm_evals/...` remain where they are.

## Mixed Corpus Next Commands

Convert filtered sources:

```bash
cd /work/dfm/HRM-Text
python scripts/convert_filtered_sources.py --force --copy-ready --workers 32
```

Tokenize converted sources:

```bash
cd /work/dfm/HRM-Text/data_io/tokenizer
cargo run --release --bin tokenizer -- \
  /work/dfm/HRM-Text/data/converted_sources \
  --tokenizer-path /work/dfm/HRM-Text/data_io/trained_tokenizers/bpe/tokenizer.json \
  -o /work/dfm/HRM-Text/data/tokenized_mixed
```

Sample tokenized data:

```bash
cd /work/dfm/HRM-Text/data_io
python sample_tokenized.py \
  tokenized_path=../data/tokenized_mixed \
  output_path=../data/sampled \
  epochs=4 \
  > ../data/show_analytics.md
```

## DFM Mix Sampling

Updated on 2026-05-28. Confidence: high.

The DFM mix was sampled successfully from `data/tokenized_mixed` into `data/sampled_dfm` using `data_io/sample_tokenized.py`. The manual sampler process finished after writing tokens, generating four epoch index directories, and generating the analytics report.

Command used from the repo root:

```bash
setsid bash -c 'cd /work/dfm/HRM-Text/data_io && ionice -c2 -n7 nice -n 10 python sample_tokenized.py tokenized_path=../data/tokenized_mixed output_path=../data/sampled_dfm epochs=4 concat_workers=4 prefix_config_path=prefix_config_dfm.yaml > ../data/show_analytics_dfm.md 2> ../logs/tokenize/dfm_sample_stderr.log' > logs/tokenize/dfm_sample_stdout.log 2>&1 &
```

Verified outputs:

- `data/sampled_dfm/tokens.npy`: about `630G`.
- `data/sampled_dfm/epoch_0` through `data/sampled_dfm/epoch_3`.
- `data/sampled_dfm/metadata.json`.
- `data/show_analytics_dfm.md`: analytics report.
- Metadata reports `total_length=28254014835`, `max_seq_len=4097`, and tokenizer path `/work/dfm/HRM-Text/data_io/trained_tokenizers/bpe/tokenizer.json`.

## DFM L Training

Updated on 2026-05-29. Confidence: high.

The active DFM L training run was launched with:

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 torchrun --nproc_per_node=8 pretrain.py data=dfm arch/size@arch=L lr=2.5e-4 global_batch_size=172032 +project_name="DFM L" +run_name=dfm-L +checkpoint_path=checkpoints/dfm/L
```

The local W&B run directory is `wandb/run-20260528_234406-kgnbdmwf`. While the run was still active, it was manually synced into the original+mixed W&B project as a second project view with:

```bash
wandb sync --include-online --no-mark-synced --project "Original Plus Mixed Danish Instruction Rich L" wandb/run-20260528_234406-kgnbdmwf
```

W&B reported the target as `peter-sk-sdu/Original Plus Mixed Danish Instruction Rich L/runs/kgnbdmwf` and completed with `done.`.
