# Current State

Last updated: 2026-06-01
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

Update on 2026-05-31:

- DFM3 data-prep scaffolding was added for English evaluation recovery. DFM3
  is DFM2 plus selected Common Pile raw-text objectives and raised caps for
  approved English/multilingual instruction data.
- New files:
  - `scripts/generate_dfm3_common_pile_tasks.py`
  - `scripts/build_tokenized_dfm3_tree.py`
  - `scripts/prepare_dfm3_english_recovery.sh`
  - `data_io/prefix_config_dfm3.yaml`
  - `config/data/dfm3.yaml`
- `scripts/download_training_datasets.py` now has an explicit `common_pile`
  group with selected filtered/public/open Common Pile components. A dry-run
  inventory resolved `480` selected files and `275.1 GB` compressed/download
  size.
- `scripts/convert_filtered_sources.py` now converts selected Common Pile
  `.json.gz`, `.jsonl.gz`, and Parquet rows with a `text` field into raw
  continuation rows.
- Validation passed:
  - `python -m py_compile` for modified/new Python scripts.
  - `bash -n scripts/prepare_dfm3_english_recovery.sh`.
  - `data_io/prefix_config_dfm3.yaml` parses as YAML with `84` rules.
- Later on 2026-05-31, the selected Common Pile download/filter/convert
  stages completed and DFM3 task generation finished. The generator wrote
  `2,862` Parquet task files under
  `data/converted_sources_dfm3_common_pile_tasks`, with approximately
  `19,043,38x` rows in each of the six DFM3 objective families:
  direct continuation, prefix continuation, denoising, and three span-fill
  variants. Confidence: high.
- DFM3 Common Pile tokenization was launched with one worker:

```bash
ionice -c2 -n7 nice -n 10 ./data_io/tokenizer/target/release/tokenizer \
  data/converted_sources_dfm3_common_pile_tasks \
  --tokenizer-path /work/dfm/HRM-Text/data_io/trained_tokenizers/bpe/tokenizer.json \
  --workers 1 \
  -o data/tokenized_dfm3_common_pile_tasks
```

  At `2026-05-31 12:07 CEST`, the reliable progress signal was `484 / 2862`
  completed tokenized task directories, measured by top-level output dirs or
  `metadata.json` files, and about `100G` written. Do not estimate tokenizer
  completion from raw file count under the output tree, because each completed
  tokenized task directory contains multiple array files. Confidence: high.

Update on 2026-06-01:

- DFM3 Common Pile tokenization completed: `2862 / 2862` generated task dirs
  have `metadata.json`, matching the `2862` generated Parquet inputs.
  `data/tokenized_dfm3_common_pile_tasks` is `448G`. Confidence: high.
- The DFM3 tokenized union was built at `data/tokenized_dfm3` with `4690`
  top-level symlinks. Confidence: high.
- DFM3 sampling completed at `data/sampled_dfm3`; it contains `metadata.json`
  and `tokens.npy` and is `1.2T`. `data/sampled_dfm3/metadata.json` reports
  `max_seq_len=4097` and `total_length=174,204,067,350`. The analytics file
  `data/show_analytics_dfm3.md` reports `192,508,795,135` unique sampled tokens
  out of `214,239,617,633` available unique tokens (`89.86%`). Confidence: high.
- DFM4 source downloads completed. No DFM4 downloader process remains. Local
  sizes are `436M` for `govreport_summarization`, `5.5G` for `wiki_cat_sum`,
  and `143G` for `laion_scientific_summaries`. The selected LAION arXiv slice
  has `4006` Parquet files plus selected repository docs, matching the `4008`
  selected-file inventory. GovReport has `2` train Parquet shards plus README;
  WikiCatSum has `3` train JSONL files plus README. Confidence: high.
- Superseded: the first DFM4 sample used four epochs and the original
  paragraph-reorder tokenization.
- Current DFM4 generation, tokenization, union build, and five-epoch sampling
  completed. The current union keeps the full DFM3 tree, regenerated DynaWord
  paragraph-window tasks, the previously complete Common Pile paragraph tasks,
  and DFM4 summarization tasks. `data/tokenized_dfm4/union_manifest.json`
  reports roots of `4689` DFM3 tasks, `25` regenerated DynaWord paragraph
  tasks, `425` Common Pile paragraph tasks, `4019` summarization tasks, and
  `9158` total tasks. Confidence: high.
- Current DFM4 sampling completed at `data/sampled_dfm4` with `epochs=5`.
  `metadata.json` reports `max_seq_len=4097` and
  `total_length=72,007,089,569` tokens per epoch. `tokens.npy` is
  `1,225,441,020,536` bytes. Per-epoch arrays exist under `epoch_0` through
  `epoch_4`; all epoch array files were rewritten at `20:32-20:33 CEST` on
  2026-06-01. `data/show_analytics_dfm4.md` reports
  `360,035,447,845` covered tokens across five epochs. Confidence: high.
- Superseded: before pulling `origin/main` on 2026-06-02, the local
  `global_batch_size` path had no gradient accumulation.
- Pull/merge update on 2026-06-02. Confidence: high. `main` was
  fast-forwarded to `origin/main` after a dry run in
  `/work/dfm/HRM-Text-pull-sim`. Local tracked changes were stashed,
  reapplied, and conflicts were resolved using the same resolutions as the temp
  worktree. Conflicted files were `config/cfg_pretrain.yaml`, `pretrain.py`,
  `wiki/pages/download-convert-tokenize.md`, and `wiki/pages/open-issues.md`.
  Validation passed with `python scripts/check_goldfish_loss.py`,
  `python -m py_compile pretrain.py models/lm_head.py models/goldfish_loss.py
  scripts/check_goldfish_loss.py`, and `git diff --check`.
- Current batch-size implementation after the pull, verified from
  `pretrain.py`, `dataset_new.py`, and `multipack_sampler.py` on 2026-06-02.
  Confidence: high. `global_batch_size` is now the effective optimizer token
  batch and `gradient_accumulation_steps` controls the physical microbatch:
  `local_batch_size = global_batch_size / (world_size *
  gradient_accumulation_steps)`. Each optimizer step accumulates that many
  microbatches before `optim.step()`, with loss scaled by supervised-token
  counts across the accumulated microbatches.

Update on 2026-05-30:

- DFM2 data preparation completed. `scripts/generate_dfm2_dynaword_tasks.py`
  produced DynaWord-derived self-supervised tasks, tokenized with one tokenizer
  worker into `data/tokenized_dfm2_dynaword_tasks`.
- `scripts/build_tokenized_dfm2_tree.py --force` built `data/tokenized_dfm2`
  as a symlink union with `1377` base mixed tasks plus `450` generated DFM2
  tasks, for `1827` total task dirs.
- DFM2 sampling completed at `data/sampled_dfm2`; `config/data/dfm2.yaml`
  points training at this sample.
- `data/sampled_dfm2/metadata.json` reports `total_length=42,317,252,803`
  tokens per epoch and `max_seq_len=4097`.
- `data/show_analytics_dfm2.md` reports generated DynaWord self-supervised
  additions of `56,253,792,196` covered tokens across four epochs, or
  `14,063,448,049` per epoch. The retained direct DynaWord slice is
  `2,813,942,923` covered tokens per epoch, so the generated additions are
  `4.998X`.
- DFM2 generated tasks do not use sampler `repeat: 2`; the generator creates
  unique variants instead.

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

Update on 2026-06-01:

- W&B native `_step` history cannot be repaired in-place after later eval/log
  rows have advanced the run step. An attempted same-run backfill of DFM L train
  rows into `Original Plus Mixed Danish Instruction Rich L/kgnbdmwf` was
  rejected by W&B for old `_step` values; a later custom-step replay polluted
  the visible train curves and should not be used as the clean comparison run.
  Confidence: high.
- A clean comparison run was created at
  `Original Plus Mixed Danish Instruction Rich L/dfmlfull0601`
  (`dfm-L-full-train-backfill`). It backfilled DFM L train history from
  `DFM L/kgnbdmwf` before adding eval metrics, preserving native train `_step`
  values. The train backfill logged `118,775` rows, source steps `5` through
  `592,395`; W&B summary verifies `train/source_step=592395`,
  `train/loss=1.1001414060592651`, and
  `train/accuracy=0.7316066026687622`. Confidence: high.
- The same clean run now has standard `eval/*` and Danish `dfm_eval/*` metrics
  for DFM L epochs `1`, `2`, and `3`, replayed from local merged metric JSONs.
  Each epoch logged `195` standard metrics and `74` DFM metrics using
  `eval/epoch` and `dfm_eval/epoch` as the W&B plot axes. Spot-checked summary
  values include `eval/MATH/acc/epoch_1=0.3854`,
  `eval/MATH/acc/epoch_2=0.45380217999999994`,
  `eval/MATH/acc/epoch_3=0.47639826`,
  `dfm_eval/ifeval-da/instruction_following/final_acc/epoch_1=0.393870787633715`,
  `dfm_eval/ifeval-da/instruction_following/final_acc/epoch_2=0.41204577082020327`,
  and
  `dfm_eval/ifeval-da/instruction_following/final_acc/epoch_3=0.4760777566757044`.
  Confidence: high.

Update on 2026-05-31:

- Superseded: earlier on 2026-05-31, `pretrain.py` only saved checkpoints at
  epoch boundaries via `checkpoint_interval`.
- Step-based checkpointing is now implemented. `config/cfg_pretrain.yaml` has
  `checkpoint_step_interval: null` by default; setting it to a positive integer
  saves additional checkpoints during training at `fsdp2_step_{step}` and
  `carry_step_{step}.{rank}.pt`. Epoch checkpoints are still saved as
  `fsdp2_epoch_{epoch}` and `carry_epoch_{epoch}.{rank}.pt`. Confidence: high.
- Checkpoint loading now supports explicit tags. Standard/eval code can pass
  `ckpt_tag=step_10000` or `ckpt_tag=epoch_1`; the OpenAI shim accepts
  `--ckpt-tag step_10000`, and HF conversion accepts `--ckpt_tag step_10000`.
  Existing `ckpt_epoch=...` and `--ckpt-epoch ...` paths still work, and when no
  epoch/tag is passed, loading still defaults to the latest epoch checkpoint.
  Confidence: high.
- `scripts/schedule_checkpoint_evals.sh` now accepts `CKPT_TAG`, defaulting to
  `epoch_${EPOCH}`. For intra-epoch evals use, for example,
  `EPOCH=1 CKPT_TAG=step_10000 ... scripts/schedule_checkpoint_evals.sh`; the
  `EPOCH` value remains the W&B x-axis/merge epoch unless those logging scripts
  are extended separately. Confidence: high.
- Fractional eval epochs are now supported for intra-epoch checkpoints.
  `scripts/schedule_checkpoint_evals.sh` accepts `EVAL_EPOCH`, defaulting to
  `EPOCH`, and passes it to the standard/DFM/IFEval merge scripts. The merge
  and incremental DFM logging scripts parse `--epoch` as `float`, so W&B rows
  can use values such as `eval/epoch=1.234` and `dfm_eval/epoch=1.234`.
  Per-checkpoint summary aliases sanitize fractional labels with `p`, for
  example `epoch_1p234`, while integer epochs keep `epoch_1`. Confidence: high.
- Superseded: training resume was previously not implemented in `pretrain.py`.
  It is now implemented for current epoch checkpoints and new metadata-backed
  step checkpoints. `config/cfg_pretrain.yaml` exposes
  `wandb_run_id`, `wandb_resume`, `resume_checkpoint_path`,
  `resume_checkpoint_tag`, `resume_epoch`, `resume_step`, and
  `resume_batch_in_epoch`. `pretrain.py` loads DCP model and optimizer state
  from `fsdp2_{tag}`, loads rank-local carry from `carry_{tag}.{rank}.pt`,
  restores `train_state.step`, and calls `V1Dataset.set_epoch(...)` so epoch
  checkpoints continue on the next dataset epoch instead of replaying epoch 0.
  On resume, `num_params` is written to W&B summary rather than logged at step
  `0`, so a backfilled run can continue without violating W&B monotonic step
  ordering. Confidence: high.
- New checkpoints write sidecar metadata files named
  `checkpoint_state_{tag}.json` with `tag`, `step`, `epoch`,
  `batch_in_epoch`, `global_batch_size`, `data_path`, and `seed`. Step
  checkpoints such as `step_500000` use this metadata to resume inside an epoch
  by replay-skipping already completed batches. Existing old epoch checkpoints
  do not have sidecars; for them resume infers the step as
  `completed_epoch * total_steps // config.epochs`. Confidence: high.
- Example resume from an existing DFM epoch checkpoint:

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 torchrun --nproc_per_node=8 pretrain.py \
  data=dfm \
  arch/size@arch=L \
  lr=2.5e-4 \
  global_batch_size=172032 \
  project_name="DFM L" \
  run_name=dfm-L-resume-epoch3 \
  checkpoint_path=checkpoints/dfm/L-resume \
  resume_checkpoint_path=checkpoints/dfm/L \
  resume_checkpoint_tag=epoch_3
```

  For new step checkpoints, use `resume_checkpoint_tag=step_500000`; if the
  sidecar JSON is missing, also provide `resume_epoch`, `resume_step`, and
  `resume_batch_in_epoch`. Confidence: high.
- The original DFM L epoch checkpoints were reconstructed with exact step
  sidecars by comparing raw local W&B train history timestamps from
  `wandb/run-20260528_234406-kgnbdmwf/run-kgnbdmwf.wandb` against checkpoint
  mtimes. The verified last logged train steps before checkpoint writes are:
  `epoch_1=164670`, `epoch_2=329380`, and `epoch_3=494080`. Sidecars
  `checkpoints/dfm/L/checkpoint_state_epoch_{1,2,3}.json` were written with
  those steps, so `resume_checkpoint_tag=epoch_3` now resolves to
  `step=494080`, `start_epoch=4`, and `skip_batches=0`. Confidence: high.
  The terminal progress-bar lines around `20840` at epoch transitions are not a
  reliable global W&B step boundary by themselves.
- W&B run `Original Plus Mixed Danish Instruction Rich L/dfm-l-resume-epoch3`
  was prepared for resuming DFM L from `epoch_3`. It contains `98,816` train
  rows backfilled from local DFM L history through step `494080`, plus standard
  `eval/*` and Danish `dfm_eval/*` metrics for epochs `1`, `2`, and `3`.
  Verified summary values include `resume_prepared_max_train_step=494080`,
  `train/loss=1.1266595125198364`, `train/accuracy=0.7248556613922119`,
  `eval/MATH/acc/epoch_3=0.47639826`, and
  `dfm_eval/ifeval-da/instruction_following/final_acc/epoch_3=0.4760777566757044`.
  Resume training should use `wandb_run_id=dfm-l-resume-epoch3` and
  `wandb_resume=allow` so it appends step `494085+` train metrics to the
  prepared run. Confidence: high.
- Caveat observed after launching the resumed run: because eval and dfm_eval
  rows were logged after the train backfill, W&B advanced the internal run step
  a few steps beyond `494080` before training resumed. The first resumed train
  log at step `494085` was warned/dropped because W&B's current internal step
  was `494087`. Subsequent train logs above that point are accepted; W&B API
  showed the run as `running` and train summary values updating. For future
  prepared resume runs, either log eval rows with explicit non-advancing/merged
  steps or expect the first one or two train logs after resume to be skipped.
  Confidence: high.
- The first DFM L epoch-3 resume attempt failed at `step_500000` while saving
  the step checkpoint because `save_train_checkpoint()` still referenced an
  old global `RANK` variable. `pretrain.py` was fixed to pass `rank` explicitly
  into checkpoint save helpers. The DCP model/optimizer checkpoint
  `checkpoints/dfm/L/fsdp2_step_500000` had already been written before the
  crash. Because `baselines.hrm_nocarry_bp_warmup` has `initial_carry() -> None`,
  the missing carry files were safely recovered as `torch.save(None, ...)` for
  ranks `0..7`, and `checkpoint_state_step_500000.json` was written with
  `step=500000`, `epoch=4`, and `batch_in_epoch=5920`. Resume now resolves
  `step_500000` to `ResumeState(tag='step_500000', step=500000, start_epoch=4,
  skip_batches=5920)`. Confidence: high.
- Goldfish loss integration assessment, 2026-06-01. Goldfish loss is a
  label-masking modification to next-token cross entropy: drop a deterministic
  or randomized subset of target tokens from loss computation by setting labels
  to the ignore index before CE. In this repo the correct integration point is
  `models/lm_head.py`, immediately before `F.cross_entropy(...)`, because
  `dataset_new.py` already emits packed `labels` with `IGNORE_LABEL_ID` and
  `LMHead` already computes masks, CE, and metrics centrally. A minimal optional
  implementation needs config fields on `LMHeadConfig`/arch config such as
  `goldfish_strategy`, `goldfish_k`, `goldfish_start_position`, and
  `goldfish_context_width`; default `goldfish_strategy: null` preserves current
  behavior. Confidence: high for integration point; medium for preferred
  strategy defaults.
- Goldfish loss is now implemented behind an explicit opt-in. Main code lives
  in `models/goldfish_loss.py`; `models/lm_head.py` applies it only when
  `arch.goldfish_strategy` is set. `config/arch/net/hrm.yaml` defaults to
  `goldfish_strategy: null`, `goldfish_k: 50`, `goldfish_context_width: 50`,
  and `goldfish_seed: 0`, so existing runs are unchanged unless the option is
  enabled. Enable Apertus-style settings with
  `arch.goldfish_strategy=hash arch.goldfish_k=50 arch.goldfish_context_width=50`.
  Validation passed with `python scripts/check_goldfish_loss.py`,
  `python -m py_compile`, and Hydra composition of the Goldfish overrides.
  Confidence: high.
- Hydra override compatibility for the resume command was fixed on 2026-06-01.
  `config/cfg_pretrain.yaml` now declares `project_name`, `run_name`,
  `checkpoint_path`, `seed`, `log_interval`, `fwd_bwd_dtype`,
  `checkpoint_step_interval`, W&B resume fields, and checkpoint resume fields.
  `config/data/dfm.yaml` now declares `target_only: true`. The DFM L
  epoch-3 resume command was checked with `python pretrain.py --cfg job ...`
  and composes without `Could not override ...` errors. Confidence: high.

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

MPS branch update on 2026-05-25:

- Repo path: `/Users/petersk/Nobackup/HRM-Text-mps`.
- After stopping a still-running background Sapient downloader, the partial Sapient download has `490` completed `.parquet`/`.jsonl` inputs under `data/downloads/datasets/sapient_cleaned` and `1` incomplete cache file.
- Completed local inputs were tokenized into `data/tokenized_original_sapient_partial`.
- Verification: `490` tokenized `metadata.json` files, about `83G`; a final tokenizer validation scan reported `Processing 0 files`.
- A small symlinked tokenized view was built at `data/tokenized_original_sapient_partial_smoke`.
- Sampling produced `data/sampled_original_sapient_partial_smoke`, about `519M`, with `metadata.total_length=21,359,878`.
- Two MPS debug training steps against this smoke sample passed with finite loss, metrics, gradients, parameters, and post-optimizer parameters.
- Gradient accumulation is implemented with `global_batch_size` as the effective optimizer token batch. Verified B-size MPS diagnostic: `global_batch_size=131072`, `gradient_accumulation_steps=8`, derived `local_microbatch_size=16384`, one optimizer step finite. Because epochs drop their own partial final effective batch, the smoke sample runs `162` optimizer steps per epoch, or `648` steps for `epochs=4`.

See [[original-l-reproduction]] and [[download-convert-tokenize]] for commands. Confidence: high.

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

## DFM L CP1 Evaluation Queue

Updated on 2026-05-29. Confidence: high.

`scripts/schedule_checkpoint_evals.sh` is a generic 8-GPU checkpoint eval
scheduler derived from the original+mixed CP3/CP4 scheduler. For DFM L CP1 it
targets:

- `CKPT_PATH=checkpoints/dfm/L`
- `EPOCH=1`
- `WANDB_PROJECT="DFM L"`
- `WANDB_RUN_ID=kgnbdmwf`
- `WANDB_RUN_NAME=dfm-L`

Superseded on 2026-05-29: the initial dry-run used 16 MATH shards and 16
IFEval-DA shards.

Current sharding policy on 2026-05-29. Confidence: high for implemented
standard and DFM behavior.

Runtime buckets:

- `<10m`: 1 shard.
- `10-20m`: 2 shards.
- `20-40m`: 4 shards.
- `40-80m`: 8 shards.
- `80-160m`: 16 shards.
- `160-320m`: 32 shards.

Implemented in `scripts/schedule_checkpoint_evals.sh`:

- Standard evals are generically shardable through `evaluation/main.py`, which
  now accepts `num_shards` and `shard_index` in each benchmark config and slices
  prompts/targets after benchmark construction.
- Standard shard metrics are merged with `scripts/merge_standard_eval_shards.py`
  before W&B logging.
- IFEval-DA defaults to 32 shards via
  `config/dfm_evals_hrm_ifeval_da_32_shards.yaml`.
- DFM eval tasks now accept `num_shards` and `shard_index` through a shared
  `dfm-evals/dfm_evals/tasks/_sharding.py` helper.
- Sharded DFM task metrics are merged from Inspect `.eval` sample records with
  `scripts/merge_dfm_eval_shards.py` before W&B logging. Shards do not log
  partial metrics as full metrics.

Superseded on 2026-05-29: the DFM CP1 dry-run queue had `112` jobs with
`MATH` split into `8` shards. Observed CP1 MATH shard runtime was about an hour
or more for `625` samples, which violates the target of roughly ten minutes per
shard.

Current future-run queue policy on 2026-05-29. Confidence: high.

- `GSM8k`: 8 shards.
- `DROP`: 4 shards.
- `MMLU`: 4 shards.
- `ARC`: 1 shard.
- `HellaSwag`: 2 shards.
- `Winogrande`: 1 shard.
- `BoolQ`: 1 shard.
- `MATH`: 64 shards.
- `danish_citizen_tests`: 1 shard.
- `dala`: 1 shard.
- `gec_dala`: 2 shards.
- `wmt24pp_en_da`: 8 shards.
- `multi_wiki_qa`: 2 shards.
- `piqa`: 1 shard.
- `generative_talemaader`: 8 shards.
- `govreport`: 16 shards.
- `nordjyllandnews`: 8 shards.
- `humaneval`: 4 shards.
- `ifeval-da`: 32 shards.

Prior status logs show the longest tails were IFEval-DA, MATH, GSM8k,
WMT24++ en-da, generative-talemaader, and summarization tasks with BERTScore.

Validation:

- `python -m py_compile` passed for the scheduler helpers and patched eval
  task files.
- `bash -n scripts/schedule_checkpoint_evals.sh` passed.
- `DRY_RUN=1 ... scripts/schedule_checkpoint_evals.sh` produced the 112-job
  CP1 queue.
- A zero-sample Inspect probe for `hrm_danish_multi_wiki_qa` with
  `-T num_shards=2 -T shard_index=0` resolved to
  `dataset: MultiWikiQA-da-shard-0-of-2`.
- A zero-sample Inspect probe for `hrm_code_humaneval_local` with
  `-T num_shards=4 -T shard_index=0` resolved to
  `dataset: humaneval-shard-0-of-4`.
- A dry run after the MATH adjustment confirmed that
  `scripts/schedule_checkpoint_evals.sh` queues `64` standard `MATH` shards.

Launch state on 2026-05-29. Confidence: high.

Superseded: the DFM L CP1 112-job eval scheduler was initially queued behind a
watcher because the active DFM L training run still occupied all 8 GPUs with
high utilization.

Updated later on 2026-05-29: the user confirmed the GPUs had enough headroom,
so the watcher was stopped and the scheduler was launched immediately while the
DFM L training run was still active. Command:

```bash
EPOCH=1 CKPT_PATH=checkpoints/dfm/L GPUS=0,1,2,3,4,5,6,7 \
LOG_ROOT=logs/eval/dfm_L_epoch1_queued_all \
DFM_LOG_ROOT=logs/dfm_evals/dfm_L_epoch1_queued_all \
WANDB_PROJECT="DFM L" WANDB_RUN_ID=kgnbdmwf WANDB_RUN_NAME=dfm-L \
MODEL_PREFIX=hrm-dfm-L scripts/schedule_checkpoint_evals.sh
```

Files:

- Scheduler PID file: `logs/eval/dfm_L_epoch1_queued_all/scheduler.pid`
- Launcher log: `logs/eval/dfm_L_epoch1_queued_all.launcher.log`
- Status log: `logs/eval/dfm_L_epoch1_queued_all/status.tsv`
- Queue file: `logs/eval/dfm_L_epoch1_queued_all/jobs.tsv`

Verified immediately after launch:

- Scheduler PID: `2285914`.
- Queue: `112` jobs.
- Checkpoint readiness passed for `checkpoints/dfm/L` epoch 1.
- Workers started, with staggered first jobs beginning on `GSM8k` shards.

Completion inspection on 2026-05-29. Confidence: high.

The DFM L CP1 scheduler exited after all `112` queued jobs reached `END`
status, but final aggregation reported two failures:

```text
FINAL_MERGE_STANDARD_MATH_FAILED
FINAL_MERGE_DFM_generative_talemaader_FAILED
FINAL_MERGE_END
```

Successful synced aggregates include standard `ARC`, `BoolQ`, `DROP`,
`GSM8k`, `HellaSwag`, `MMLU`, and `Winogrande`, plus DFM `dala`,
`danish_citizen_tests`, `gec_dala`, `govreport`, `humaneval`,
`multi_wiki_qa`, `nordjyllandnews`, `piqa`, `wmt24pp_en_da`, and merged
`ifeval-da`. The merged IFEval-DA file is
`logs/dfm_evals/dfm_L_epoch1_queued_all/merged_ifeval_da_metrics.json` and
contains `541` samples with
`dfm_eval/ifeval-da/instruction_following/final_acc=0.393870787633715`.

`MATH` failed only for shard `4` of `8`. Its log is
`logs/eval/dfm_L_epoch1_queued_all/standard_shards/MATH/MATH_shard_4_of_8.log`
and shows an HF Hub `504 Gateway Time-out` while loading
`EleutherAI/hendrycks_math` `precalculus`; the scheduler correctly recorded
`END standard MATH shard_4_of_8 gpu_0 status_1`. The other seven MATH shards
have summaries and do not need to be rerun.

`generative_talemaader` failed at merge time because the wrapper task did not
forward `num_shards` and `shard_index`; each of the eight launched jobs ran the
full `808` samples and therefore produced duplicate sample IDs such as `dtm_0`.
`dfm-evals/dfm_evals/tasks/talemaader/task.py` was patched so
`generative_talemaader()` accepts and forwards `num_shards` and `shard_index`.
`python -m py_compile` passes, and a zero-sample probe now resolves to
`dataset: generative-talemaader-shard-0-of-8` without unused-parameter
warnings:

```bash
OPENAI_API_KEY=inspectai uv run --project dfm-evals evals suite hrm_danish_generative_talemaader \
  --file config/dfm_evals_hrm_single_tasks.yaml \
  --target-model openai/dummy \
  --target-base-url http://127.0.0.1:9/v1 \
  --judge-model openai/dummy \
  --judge-base-url http://127.0.0.1:9/v1 \
  --mode set -- -T num_shards=8 -T shard_index=0 --limit 0 \
  --log-dir /tmp/hrm_talemaader_shard_probe --log-dir-allow-dirty
```

The already completed `generative_talemaader` shard `0` is actually a full run
over all `808` samples, so it can be logged as the full CP1 talemaader result
without rerunning judge inference. Verified local merge from only that `.eval`
produces
`dfm_eval/generative-talemaader/model_graded_fact/accuracy=0.07920792079207921`,
`accuracy_stderr=0.008161235917216217`, and `n=808`.

Repair update on 2026-05-29. Confidence: high.

The complete `generative_talemaader` shard `0` `.eval` was merged and synced to
W&B run `kgnbdmwf` in project `DFM L` using:

```bash
python scripts/merge_dfm_eval_shards.py \
  logs/dfm_evals/dfm_L_epoch1_queued_all/generative_talemaader/shard_0_of_8/epoch_1/inspect/*.eval \
  --task generative_talemaader \
  --epoch 1 \
  --output logs/dfm_evals/dfm_L_epoch1_queued_all/generative_talemaader/merged_metrics.json \
  --log-wandb \
  --project "DFM L" \
  --run-id kgnbdmwf \
  --run-name dfm-L
```

Future scheduler runs are guarded against the same talemaader failure mode:
`scripts/schedule_checkpoint_evals.sh` now checks each dfm-evals shard log for
Inspect warnings that `num_shards` or `shard_index` were not used and fails that
job instead of treating it as valid shard output. The scheduler also defaults to
`MAX_RETRIES=3`, meaning each failed job can be attempted four total times, and
DFM/IFEval shard output directories are cleared before each attempt so partial
failed `.eval` files do not contaminate the final merge.

`MATH` shard `4` of `8` was restarted manually on GPU `0` with:

```bash
CUDA_VISIBLE_DEVICES=0 PYTHONUNBUFFERED=1 python -u -m evaluation.main \
  config=evaluation/config/hrm_benchmarking.yaml \
  ckpt_path=checkpoints/dfm/L \
  ckpt_epoch=1 \
  "benchmarks=[{name: MATH, num_shards: 8, shard_index: 4}]" \
  generation_config.batch_size=8 \
  > logs/eval/dfm_L_epoch1_queued_all/standard_shards/MATH/MATH_shard_4_of_8.log 2>&1
```

For this already-started CP1 repair, keep the running `shard_4_of_8` and merge
it with the seven completed `of_8` shard logs. Switching CP1 repair to `64`
shards would require either rerunning all MATH under the new layout or adding a
one-off range slicer for only the missing eighth.

Final CP1 eval repair result on 2026-05-29. Confidence: high.

The restarted `MATH` shard `4` finished successfully with `n=625`,
`acc=0.3952`, and `invalid=0.1200`. All eight `MATH` shards were then merged
and synced to W&B run `kgnbdmwf` in project `DFM L`:

```text
eval/MATH/acc: 0.3854
eval/MATH/invalid: 0.1106
eval/MATH/n: 5000
```

The final local aggregate is
`logs/eval/dfm_L_epoch1_queued_all/standard_shards/MATH/merged_metrics.json`.
The sync log is
`logs/eval/dfm_L_epoch1_queued_all/standard_shards/MATH/merge_and_wandb_sync.log`.

A final scan of CP1 merge logs showed `OK` for all standard merge/sync logs,
all DFM task merge/sync logs, and `merge_ifeval_da_wandb.log`; no remaining
failed aggregate logs were found.

Cross-project W&B sync note, 2026-05-29. Confidence: high.

Syncing only the original active training directory does not include all later
manual eval metrics:

```bash
wandb sync --include-online --no-mark-synced \
  --project "Original Plus Mixed Danish Instruction Rich L" \
  wandb/run-20260528_234406-kgnbdmwf
```

The eval merge scripts resumed run id `kgnbdmwf` and created separate local
W&B directories such as `wandb/run-20260529_221506-kgnbdmwf` and
`wandb/run-20260529_233116-kgnbdmwf`. A multi-directory `wandb sync` reported
success, but the target project summary still lacked the new keys when checked
through the W&B API. The reliable repair was to backfill the merged aggregate
JSON/logs directly into the target project run with `wandb.init(project=...,
id="kgnbdmwf", resume="allow")` by rerunning the local merge scripts with:

```bash
--project "Original Plus Mixed Danish Instruction Rich L" \
--run-id kgnbdmwf \
--run-name dfm-L \
--log-wandb
```

The backfill log is
`logs/wandb_backfill_kgnbdmwf_to_original_plus_mixed_20260529T234727.log`.
W&B API verification after the backfill showed the target project run contains
representative new metrics:

```text
eval/MATH/acc: 0.3854
eval/MATH/invalid: 0.1106
eval/MATH/n: 5000
dfm_eval/generative-talemaader/model_graded_fact/accuracy: 0.07920792079207921
dfm_eval/generative-talemaader/model_graded_fact/n: 808
dfm_eval/nordjyllandnews/rougeL/mean: 0.22148837256342324
dfm_eval/ifeval-da/instruction_following/final_acc: 0.393870787633715
```

DALA metric-name compatibility note, 2026-05-30. Confidence: high.

Earlier DALA runs logged the linguistic-acceptability macro-F1 and MCC metrics
with flattened scorer names:

```text
dfm_eval/dala/linguistic-acceptability/dfm_evals_macro_f1
dfm_eval/dala/linguistic-acceptability/dfm_evals_mcc
```

The first DFM L CP1 merge emitted slash-form keys
`dfm_eval/dala/linguistic-acceptability/dfm_evals/macro_f1` and
`dfm_eval/dala/linguistic-acceptability/dfm_evals/mcc`, which did not line up
with older W&B panels. The target run `kgnbdmwf` in project
`Original Plus Mixed Danish Instruction Rich L` was backfilled with the
flattened aliases:

```text
dfm_eval/dala/linguistic-acceptability/dfm_evals_macro_f1: 0.4906548270682793
dfm_eval/dala/linguistic-acceptability/dfm_evals_mcc: 0.03368421246821112
dfm_eval/dala/linguistic-acceptability/n: 2048
```

`scripts/merge_dfm_eval_shards.py` now emits the flattened DALA key names for
future runs. A local probe against the CP1 DALA `.eval` confirmed the updated
merge output.

## DFM L CP2 Evaluation Queue

Updated on 2026-05-30. Confidence: high.

CP2 exists locally under `checkpoints/dfm/L`: `fsdp2_epoch_2/.metadata` and all
eight `carry_epoch_2.{0..7}.pt` files were present before scheduling.

The CP2 all-evals scheduler was launched on all eight GPUs with:

```bash
EPOCH=2 CKPT_PATH=checkpoints/dfm/L GPUS=0,1,2,3,4,5,6,7 \
LOG_ROOT=logs/eval/dfm_L_epoch2_queued_all \
DFM_LOG_ROOT=logs/dfm_evals/dfm_L_epoch2_queued_all \
WANDB_PROJECT="DFM L" WANDB_RUN_ID=kgnbdmwf WANDB_RUN_NAME=dfm-L \
MODEL_PREFIX=hrm-dfm-L MAX_RETRIES=3 scripts/schedule_checkpoint_evals.sh
```

Launcher PID:

```text
3530318
```

Files:

- Scheduler PID file: `logs/eval/dfm_L_epoch2_queued_all/scheduler.pid`
- Launcher log: `logs/eval/dfm_L_epoch2_queued_all.launcher.log`
- Status log: `logs/eval/dfm_L_epoch2_queued_all/status.tsv`
- Queue file: `logs/eval/dfm_L_epoch2_queued_all/jobs.tsv`

Dry run and launch both reported `168` jobs. Current future-run sharding is in
effect, including `MATH=64` shards and `IFEval-DA=32` shards. The scheduler
started with all eight `GSM8k` shards across GPUs `0..7`.

`scripts/report_eval_progress.py` was patched on 2026-05-30 so CP2 progress
reports infer the epoch from `--log-root` and scale the MATH ETA from the old
8-shard measurement to the current 64-shard schedule. Use:

```bash
python scripts/report_eval_progress.py \
  --log-root logs/eval/dfm_L_epoch2_queued_all \
  --dfm-log-root logs/dfm_evals/dfm_L_epoch2_queued_all
```

Initial progress report at `2026-05-30T15:04:23+02:00` showed
`completed=0`, `active=8`, `queued=160`, `total_visible=168`, with an early
full ETA of about `3h03m`.

CP2 partial sync and cross-project backfill, 2026-05-30. Confidence: high.

While CP2 IFEval-DA was still running, all completed CP2 standard evals and
non-IFEval DFM tasks were merged and synced. The first direct backfill into
`DFM L` wrote local W&B summaries, but the remote `DFM L` run did not expose the
new keys through the API while the active training writer was still online. A
second explicit backfill from the merged JSON files fixed this; W&B API
verification showed representative keys in `DFM L`:

```text
eval/MATH/acc: 0.45380217999999994
dfm_eval/dala/linguistic-acceptability/dfm_evals_macro_f1: 0.3776531672364676
dfm_eval/humaneval/verify/accuracy: 0.14634146341463414
dfm_eval/ifeval-da/instruction_following/final_acc: 0.393870787633715
```

The IFEval-DA value above is the already-completed CP1 value; CP2 IFEval-DA was
not yet complete at the time of this sync. The CP2 backfill log explicitly
reported:

```text
epoch 2 project DFM L dfm ifeval-da skipped: 16/32 eval files available
epoch 2 project Original Plus Mixed Danish Instruction Rich L dfm ifeval-da skipped: 16/32 eval files available
```

CP2 was also backfilled to project
`Original Plus Mixed Danish Instruction Rich L`. W&B API verification showed:

```text
eval/MATH/acc: 0.45380217999999994
dfm_eval/dala/linguistic-acceptability/dfm_evals_macro_f1: 0.3776531672364676
dfm_eval/humaneval/verify/accuracy: 0.14634146341463414
dfm_eval/ifeval-da/instruction_following/final_acc: None
```

Backfill log:

```text
logs/eval/dfm_L_backfill_cp1_cp2_to_projects_20260530T181143.log
```

The second DFM-L visibility repair read merged JSON files and logged CP1/CP2
aggregate rows in one W&B run session. It skipped
`logs/dfm_evals/dfm_L_epoch2_queued_all/merged_ifeval_da_metrics.json` because
that file did not exist yet.

Final CP2 completion/sync, 2026-05-30. Confidence: high.

CP2 IFEval-DA finished all `32/32` shards and the scheduler reached
`FINAL_MERGE_END` at `2026-05-30T20:05:50+02:00`. All CP2 merge/sync logs under
`logs/eval/dfm_L_epoch2_queued_all` and
`logs/dfm_evals/dfm_L_epoch2_queued_all` were scanned and reported `OK`.

Merged CP2 IFEval-DA metrics:

```text
dfm_eval/ifeval-da/instruction_following/final_acc: 0.41158366361133086
dfm_eval/ifeval-da/instruction_following/final_stderr: 0.017495304869788196
dfm_eval/ifeval-da/instruction_following/inst_loose_acc: 0.5045766590389016
dfm_eval/ifeval-da/instruction_following/inst_strict_acc: 0.4874141876430206
dfm_eval/ifeval-da/instruction_following/prompt_loose_acc: 0.3345656192236599
dfm_eval/ifeval-da/instruction_following/prompt_strict_acc: 0.3197781885397412
```

The final merged file is
`logs/dfm_evals/dfm_L_epoch2_queued_all/merged_ifeval_da_metrics.json`.
The scheduler's merge log is
`logs/dfm_evals/dfm_L_epoch2_queued_all/merge_ifeval_da_wandb.log`.

The CP2 IFEval-DA aggregate was backfilled to both W&B projects:
`DFM L` and `Original Plus Mixed Danish Instruction Rich L`, run id
`kgnbdmwf`. The `Original Plus Mixed Danish Instruction Rich L` project exposed
the values through the normal W&B API immediately. For `DFM L`, the active
training writer again hid/overwrote the summary keys, so the run summary was
patched directly through the W&B API. Verification after the direct summary
patch showed:

```text
DFM L :: dfm_eval/ifeval-da/instruction_following/final_acc = 0.41158366361133086
DFM L :: dfm_eval/ifeval-da/instruction_following/inst_strict_acc = 0.4874141876430206
DFM L :: dfm_eval/ifeval-da/instruction_following/prompt_strict_acc = 0.3197781885397412
```

CP2 heavy-first rerun, 2026-05-31. Confidence: high.

`scripts/schedule_checkpoint_evals.sh` now supports `QUEUE_ORDER=heavy_first`.
That queue order starts with IFEval-DA shards, then MATH shards, then the other
longer shard groups before the short single-shard tasks. A dry run with
`QUEUE_ORDER=heavy_first` queued `168` jobs and showed the expected leading
tasks.

The first CP2 heavy-first background launch at
`logs/eval/dfm_L_epoch2_heavy_first_20260531T1059` exited before workers
started, leaving an empty status log and a partial queue. It was superseded by a
detached `setsid` launch.

Active launch:

```bash
EPOCH=2 EVAL_EPOCH=2 CKPT_TAG=epoch_2 CKPT_PATH=checkpoints/dfm/L \
GPUS=0,1,2,3,4,5,6,7 QUEUE_ORDER=heavy_first \
LOG_ROOT=logs/eval/dfm_L_epoch2_heavy_first_20260531T1102 \
DFM_LOG_ROOT=logs/dfm_evals/dfm_L_epoch2_heavy_first_20260531T1102 \
WANDB_PROJECT="DFM L" WANDB_RUN_ID=kgnbdmwf WANDB_RUN_NAME=dfm-L \
MODEL_PREFIX=hrm-dfm-L MAX_RETRIES=3 scripts/schedule_checkpoint_evals.sh
```

Scheduler PID: `2557293`.

Files:

- Scheduler PID file:
  `logs/eval/dfm_L_epoch2_heavy_first_20260531T1102/scheduler.pid`
- Launcher log:
  `logs/eval/dfm_L_epoch2_heavy_first_20260531T1102.launcher.log`
- Status log:
  `logs/eval/dfm_L_epoch2_heavy_first_20260531T1102/status.tsv`
- DFM log root:
  `logs/dfm_evals/dfm_L_epoch2_heavy_first_20260531T1102`

Initial verification showed checkpoint readiness for `epoch_2`, all eight
workers started on IFEval-DA shards `0..7`, and `nvidia-smi` reported all eight
GPUs at `100%` utilization with roughly `101-125 GB` memory in use. Confidence:
high.

Final heavy-first CP2 sync, 2026-05-31. Confidence: high.

The heavy-first CP2 scheduler completed all `168/168` jobs and reached
`FINAL_MERGE_END` at `2026-05-31T15:52:04+02:00`. The built-in final merge
synced the aggregates to project `DFM L`, run id `kgnbdmwf`.

The same merged aggregates were then backfilled to project
`Original Plus Mixed Danish Instruction Rich L`, run id `kgnbdmwf`, run name
`dfm-L`. The successful backfill log is:

```text
logs/eval/dfm_L_epoch2_heavy_first_backfill_to_original_plus_mixed_20260531T174752.log
```

It logged `195` standard `eval/*` metrics from `8` merged standard files and
`74` `dfm_eval/*` metrics from `11` merged DFM files. W&B API verification
against
`https://wandb.ai/peter-sk-sdu/Original%20Plus%20Mixed%20Danish%20Instruction%20Rich%20L/runs/kgnbdmwf`
returned representative values:

```text
eval/MATH/acc = 0.45380217999999994
eval/GSM8k/acc = 0.7665051554207735
eval/MMLU/acc = 0.33975000000000005
dfm_eval/ifeval-da/instruction_following/final_acc = 0.41204577082020327
dfm_eval/generative-talemaader/model_graded_fact/accuracy = 0.13923267326732677
dfm_eval/humaneval/verify/accuracy = 0.14634146341463414
dfm_eval/nordjyllandnews/rougeL/mean = 0.20810562203119595
```

Follow-up visibility check on 2026-05-31. Confidence: high.

The CP2 heavy-first metrics are present in W&B history, not only in summary.
API checks with one metric family at a time returned history rows for run
`kgnbdmwf` in project `Original Plus Mixed Danish Instruction Rich L`,
including:

```text
eval/MATH/acc at _step 900103 with eval/epoch = 2
dfm_eval/ifeval-da/instruction_following/final_acc at _step 900104 with dfm_eval/epoch = 2
```

If the W&B UI does not show them, likely causes are workspace/run filters that
exclude the `dfm-L` run, stale panel state, or plots using `_step` as x-axis.
For standard eval panels use `eval/epoch` as x-axis; for DFM eval panels use
`dfm_eval/epoch`.

DFM L CP3 full eval launch, 2026-05-31. Confidence: high.

Before scheduling CP3, W&B history for run `kgnbdmwf` in project
`Original Plus Mixed Danish Instruction Rich L` was checked for
`eval/MATH/acc` and contained only DFM CP1/CP2 rows. The local DFM CP3
checkpoint was complete under `checkpoints/dfm/L` with `fsdp2_epoch_3` and all
eight `carry_epoch_3.{0..7}.pt` files.

CP3 full evals were launched with heavy-first ordering:

```bash
EPOCH=3 EVAL_EPOCH=3 CKPT_TAG=epoch_3 CKPT_PATH=checkpoints/dfm/L \
GPUS=0,1,2,3,4,5,6,7 QUEUE_ORDER=heavy_first \
LOG_ROOT=logs/eval/dfm_L_epoch3_heavy_first_20260531T2227 \
DFM_LOG_ROOT=logs/dfm_evals/dfm_L_epoch3_heavy_first_20260531T2227 \
WANDB_PROJECT="DFM L" WANDB_RUN_ID=kgnbdmwf WANDB_RUN_NAME=dfm-L \
MODEL_PREFIX=hrm-dfm-L MAX_RETRIES=3 scripts/schedule_checkpoint_evals.sh
```

Scheduler PID: `3527439`.

Files:

- Scheduler PID file:
  `logs/eval/dfm_L_epoch3_heavy_first_20260531T2227/scheduler.pid`
- Launcher log:
  `logs/eval/dfm_L_epoch3_heavy_first_20260531T2227.launcher.log`
- Status log:
  `logs/eval/dfm_L_epoch3_heavy_first_20260531T2227/status.tsv`
- DFM log root:
  `logs/dfm_evals/dfm_L_epoch3_heavy_first_20260531T2227`

Initial verification showed `168` jobs queued, checkpoint readiness for
`epoch_3`, workers started on IFEval-DA shards, and all eight GPUs active.

DFM L CP3 eval resume/GovReport recovery, 2026-06-01. Confidence: high.

The CP3 scheduler was later stopped and resumed from
`logs/eval/dfm_L_epoch3_heavy_first_20260531T2227` with
`RESUME_EXISTING_QUEUE=1`. The resumed queue reached the GovReport shards after
finishing the standard eval shards. GovReport initially left all GPUs idle
because `scripts/hrm_openai_server.py` model-server processes were crashing
before serving `/health`, while dfm-evals clients waited on localhost ports.
Two import issues were fixed:

- `scripts/hrm_openai_server.py` now inserts the repo root into `sys.path`
  before importing repo modules.
- `utils/__init__.py` was added so `from utils.functions import ...` resolves
  to the repo-local utility package instead of colliding with other `utils`
  namespace/package paths.

A scheduler cleanup bug was also fixed in `scripts/schedule_checkpoint_evals.sh`:
the DFM and IFEval `RETURN` cleanup traps now read `${server_pid:-}` and
`${judge_pid:-}` into local temporaries before testing/killing them. Without
this, `set -u` could terminate a worker later with an unbound local variable
after a DFM task returned.

When launching a long resume from Codex/tool-managed shells, use `setsid -f`
rather than plain background `nohup`; plain background launches were observed
to be torn down after the launcher command returned. The working detached
resume pattern was:

```bash
setsid -f bash -c 'exec env \
  EPOCH=3 EVAL_EPOCH=3 CKPT_TAG=epoch_3 CKPT_PATH=checkpoints/dfm/L \
  GPUS=0,1,2,3,4,5,6,7 QUEUE_ORDER=heavy_first RESUME_EXISTING_QUEUE=1 \
  LOG_ROOT="logs/eval/dfm_L_epoch3_heavy_first_20260531T2227" \
  DFM_LOG_ROOT="logs/dfm_evals/dfm_L_epoch3_heavy_first_20260531T2227" \
  WANDB_PROJECT="DFM L" WANDB_RUN_ID=kgnbdmwf WANDB_RUN_NAME=dfm-L \
  MODEL_PREFIX=hrm-dfm-L MAX_RETRIES=3 STARTUP_STAGGER_SECONDS=10 \
  scripts/schedule_checkpoint_evals.sh \
  >> "logs/eval/dfm_L_epoch3_heavy_first_20260531T2227.resume6.setsid.log" 2>&1' \
  </dev/null
```

After the `setsid` relaunch, GovReport shards resumed successfully: status
showed shards `0..7` starting, several ending with status `0`, later shards
starting, `11` GovReport shard eval files written, and the remaining queue
down to `38` jobs. Confidence: high.

Final CP3 eval status update, 2026-06-01. Confidence: high.

The resumed CP3 scheduler consumed the full queue: `jobs.tsv` reached `0`
lines, all eval workers/server processes exited, and the last eval job
(`dfm humaneval shard_3_of_4`) ended with status `0` at
`2026-06-01T13:35:39+02:00`. The scheduler then entered `FINAL_MERGE_START`
and reached `FINAL_MERGE_END` at `2026-06-01T13:35:56+02:00`.

However, every final merge-and-W&B-sync command logged `FAILED` because W&B was
not authenticated in the detached scheduler environment:

```text
wandb.errors.errors.UsageError: No API key configured. Use `wandb login` to log in.
```

The eval artifacts are present locally, including HumanEval shard inspect and
EEE outputs. The next operational step is to rerun merge/sync with a valid W&B
login or `WANDB_API_KEY` in the environment; the eval computations themselves
do not need to be rerun for this failure.

Superseded by later 2026-06-01 update: W&B was authenticated and all CP3
merge/sync commands were rerun successfully. Confidence: high.

After `wandb login`, the standard eval, IFEval-DA, and DFM eval merge/sync
commands were rerun manually against:

- `logs/eval/dfm_L_epoch3_heavy_first_20260531T2227`
- `logs/dfm_evals/dfm_L_epoch3_heavy_first_20260531T2227`

The rerun wrote `*.rerun.log` merge logs and printed successful sync completion
for all standard eval tasks, IFEval-DA, and DFM tasks through HumanEval.
W&B API summary verification for project `DFM L`, run id `kgnbdmwf`, found
representative CP3 metrics including:

```text
eval/MATH/acc/epoch_3 = 0.47639826
eval/GSM8k/acc/epoch_3 = 0.793018726307809
dfm_eval/ifeval-da/instruction_following/final_acc/epoch_3 = 0.4760777566757044
dfm_eval/govreport/rougeL/mean/epoch_3 = 0.019145910006355467
dfm_eval/nordjyllandnews/rougeL/mean/epoch_3 = 0.18987313066472783
dfm_eval/humaneval/verify/accuracy/epoch_3 = 0.2195121951219512
```

Later correction on 2026-06-01. Confidence: high.

The initial verification above was for project `DFM L`. The same CP3 merged
metrics were then explicitly backfilled to project
`Original Plus Mixed Danish Instruction Rich L`, run id `kgnbdmwf`, because
that project initially showed only CP1 and CP2. Backfill log:

```text
logs/eval/dfm_L_epoch3_heavy_first_20260531T2227/backfill_cp3_to_original_plus_mixed_20260601T134813.log
```

W&B API summary verification against
`peter-sk-sdu/Original Plus Mixed Danish Instruction Rich L/kgnbdmwf` found:

```text
eval/MATH/acc/epoch_3 = 0.47639826
eval/GSM8k/acc/epoch_3 = 0.793018726307809
dfm_eval/ifeval-da/instruction_following/final_acc/epoch_3 = 0.4760777566757044
dfm_eval/govreport/rougeL/mean/epoch_3 = 0.019145910006355467
dfm_eval/nordjyllandnews/rougeL/mean/epoch_3 = 0.18987313066472783
dfm_eval/humaneval/verify/accuracy/epoch_3 = 0.2195121951219512
```

DFM L train-history backfill to Original Plus Mixed project, 2026-06-01.
Confidence: high.

The target project `Original Plus Mixed Danish Instruction Rich L`, run
`kgnbdmwf`, initially had only partial DFM L `train/*` history when sampled via
the W&B API: visible train rows reached about step `302575`, while the source
project `DFM L`, run `kgnbdmwf`, reached about step `592395`.

Attempted direct full-file sync from the local full run:

```bash
wandb sync --include-online --no-mark-synced \
  --project "Original Plus Mixed Danish Instruction Rich L" \
  wandb/run-20260528_234406-kgnbdmwf
```

This completed and updated summary state, but the target run still lacked
high-step `train/*` history above `500k`.

A direct API replay with `wandb.log(..., step=<source_step>)` was also attempted
and then stopped. It failed conceptually because eval backfills had already
advanced W&B's internal `_step` to about `900124`; W&B rejected later train
rows at `_step` values `302k..592k` as non-monotonic.

Superseded by the clean-run solution recorded above on 2026-06-01: replay the full DFM L train history into the target run using
W&B's monotonic internal step, while storing the original training step in
`train/source_step` and defining it as the step metric for train curves. The
successful replay logged `118,775` source train points from source step `5` to
`592395` into `Original Plus Mixed Danish Instruction Rich L/kgnbdmwf`.

Verification after replay:

```text
train/source_step = 592395
train/loss = 1.1001414060592651
train/accuracy = 0.7316066026687622
train/exact_accuracy = 0.1923076957464218
train/lr = 0.00025
train/dfm_loss = 1.1001414060592651
train/dfm_accuracy = 0.7316066026687622
train/dfm_exact_accuracy = 0.1923076957464218
train/dfm_lr = 0.00025
```

This same-run replay polluted the original target run and should not be used
for clean train plots. For the clean comparison, use
`Original Plus Mixed Danish Instruction Rich L/dfmlfull0601`; it has native
train `_step` values plus eval and dfm_eval metrics. The
`train/dfm_*` metrics are duplicated aliases intended to make the DFM L
backfilled train curves easy to distinguish from any older partial `train/*`
history in the target project.

Checkpoint format update on 2026-06-02. Confidence: high.

`pretrain.py` now has an explicit `checkpoint_format` config field with
default `sharded`. The default path is intentionally the existing FSDP2/PyTorch
DCP checkpointing path and writes model/optimizer state under `fsdp2_{tag}` plus
rank-local carry files named `carry_{tag}.{rank}.pt`. This is the path to use
for current FSDP training unless a specific experiment needs otherwise.

An opt-in `checkpoint_format=unsharded` path was added. It writes a full
model/optimizer checkpoint from global rank 0 to `unsharded_{tag}.pt`, while
still writing rank-local carry files for every rank. In distributed/FSDP runs it
uses `StateDictOptions(full_state_dict=True, cpu_offload=True)` when saving and
`broadcast_from_rank0=True` when loading, so it is multi-node aware in the sense
that only global rank 0 owns the serialized full checkpoint and all ranks load
through the distributed state-dict API. This path is not the default and may
have much higher CPU RAM and filesystem pressure than the sharded DCP path.

Checkpoint sidecar metadata now records `checkpoint_format` alongside `tag`,
`step`, `epoch`, `batch_in_epoch`, `global_batch_size`, `data_path`, and
`seed`. Validation performed after the change: `python -m py_compile
pretrain.py`, `git diff --check`, and loading `config/cfg_pretrain.yaml` to
verify that the default is `sharded`.

DDP benchmark path update on 2026-06-02. Confidence: high.

`pretrain.py` now has `distributed_strategy` with default `fsdp`. The default
FSDP behavior is unchanged. An opt-in `distributed_strategy=ddp` wraps the model
in `torch.nn.parallel.DistributedDataParallel` after construction and before
optimizer creation. This path is intended for memory/speed experiments on
large-memory GPUs, not as the default training path. Custom model methods used
by the loop are called through a small unwrap helper so DDP-wrapped models can
still provide `compute_train_extra_args`.

For a DDP L-size DFM4 memory/speed probe, use `data=dfm4`,
`arch/size@arch=L`, `distributed_strategy=ddp`, and strongly consider
`checkpoint_format=unsharded` with a separate checkpoint directory. DDP keeps a
full model, gradients, optimizer state, and EMA state on every GPU, so it is
expected to use far more memory than the FSDP sharded path. Validation performed
after the change: `python -m py_compile pretrain.py` and loading
`config/cfg_pretrain.yaml` verified defaults of `distributed_strategy=fsdp` and
`checkpoint_format=sharded`.

DDP benchmark failure/fix on 2026-06-02. Confidence: high.

The first `dfm4-L-ddp` launch failed before completing the first step with FA4:

```text
AssertionError: inputs must be float16, bfloat16, fp8 e4m3fn, or fp8 e5m2
```

The cause was that the new DDP path left the model in fp32. The FSDP path uses
FSDP mixed precision to provide bf16 parameters/activations, but DDP has no such
policy here. The DDP branch in `create_model_and_carry` now casts the model to
`fwd_bwd_dtype` before wrapping it in `DistributedDataParallel` and before
creating AdamATan2. Validation after the fix: `python -m py_compile
pretrain.py` and `git diff --check`.

Second DDP benchmark failure/fix on 2026-06-02. Confidence: high.

After the dtype fix, DDP failed with:

```text
RuntimeError: Expected to have finished reduction in the prior iteration before starting a new one.
Parameter indices which did not receive grad for rank 0: 96
```

This is expected for HRM BP warmup/control flow: early steps deliberately run
only a subset of H/L cycles under grad, so some parameters are unused on a given
iteration. `pretrain.py` now exposes `ddp_find_unused_parameters`, defaulting to
`true`, and passes it to `DistributedDataParallel(...)`. The flag only affects
`distributed_strategy=ddp`; FSDP remains the default and is unchanged.
Validation after the fix: `python -m py_compile pretrain.py`, `git diff
--check`, and loading `config/cfg_pretrain.yaml` showed
`ddp_find_unused_parameters: true`.

DDP XL memory observation on 2026-06-02. Confidence: high.

The user reported, and local `nvidia-smi` confirmed, that an HRM XL DDP run on
DFM4 fits on 8 B200 GPUs at roughly `78-81GB` used per GPU with active GPU
utilization around `89-91%`. This is after the DDP bf16 cast and
`find_unused_parameters=True` fixes. The observed memory is much lower than the
earlier worst-case expectation for full DDP state, so DDP is a viable benchmark
path for at least XL on these 180GB GPUs. Current live query showed:

```text
GPU0 77696 MiB, GPU1 78348 MiB, GPU2 80778 MiB, GPU3 81224 MiB,
GPU4 81030 MiB, GPU5 81358 MiB, GPU6 79026 MiB, GPU7 81364 MiB
```

This observation is hardware/config specific and should not be generalized to
H100-80 without a separate run.

DFM L epoch 4 eval queue on 2026-06-02. Confidence: high.

The completed DFM L checkpoint `checkpoints/dfm/L/fsdp2_epoch_4` plus
`carry_epoch_4.{0..7}.pt` is present locally. A full eval queue for epoch 4 was
prepared with `scripts/schedule_checkpoint_evals.sh` using all 8 GPUs,
`QUEUE_ORDER=heavy_first`, `MAX_RETRIES=3`, project `DFM L`, and run id
`kgnbdmwf`. The dry-run queue contained `168` jobs:

- `32` DFM IFEval-DA shards
- `64` MATH shards
- sharded GSM8k, DROP, MMLU, HellaSwag, GovReport, WMT24++ EN-DA,
  generative-talemaader, NordjyllandNews, HumanEval, GEC-DALA, Multi Wiki QA
- single ARC, Winogrande, BoolQ, Danish citizen tests, DALA, and PIQA jobs

Superseded: Because all GPUs were occupied by the DDP XL run at launch time, a
tmux watcher was started in `hrm-1:7` (`dfmL-cp4-evals`) to wait until all GPUs
dropped below `20GB` used.

The user then requested immediate launch despite GPU occupancy. A fresh tmux
window `hrm-1:7` (`dfmL-cp4-evals-now`) launched the scheduler immediately at
`2026-06-02T13:27:03+02:00`. It queued `168` jobs, confirmed checkpoint
readiness for `epoch_4`, and started 8 worker processes:
`3767743 3767744 3767745 3767746 3767747 3767748 3767749 3767750`.
The command was:

```bash
EPOCH=4 CKPT_TAG=epoch_4 CKPT_PATH=checkpoints/dfm/L \
GPUS=0,1,2,3,4,5,6,7 \
WANDB_PROJECT="DFM L" WANDB_RUN_ID=kgnbdmwf WANDB_RUN_NAME=dfm-L \
LOG_ROOT=logs/eval/dfm_L_epoch4_queued_all \
DFM_LOG_ROOT=logs/dfm_evals/dfm_L_epoch4_queued_all \
QUEUE_ORDER=heavy_first MAX_RETRIES=3 \
scripts/schedule_checkpoint_evals.sh
```

A live progress monitor was added at `scripts/watch_eval_progress.py`.
Confidence: high. It periodically scans scheduler status plus standard/DFM eval
logs, normalizes tqdm carriage-return output, prints aggregate scheduler counts,
GPU memory/utilization, recent scheduler events, and the latest progress-like
lines from active logs. It intentionally ignores binary Inspect `.eval` archives.

The monitor was launched as a split pane in the scheduler window:

```text
hrm-1:7.1  scheduler
hrm-1:7.2  python scripts/watch_eval_progress.py ...
```

Command:

```bash
python scripts/watch_eval_progress.py \
  --log-root logs/eval/dfm_L_epoch4_queued_all \
  --dfm-log-root logs/dfm_evals/dfm_L_epoch4_queued_all \
  --interval 10 \
  --max-logs 24
```

Monitor refinement on 2026-06-02. Confidence: high. The first monitor version
showed misleading IFEval lines such as `generation: 0% ... 0/1` because the HRM
OpenAI shim emits a fresh one-request tqdm bar for each request. The monitor now
suppresses reset-only `generation: 0/1` lines and, for `server.log`, reports
compact completion counters by counting chat-completion HTTP responses. For
IFEval-DA it verifies the HF train split length as `541` and combines that with
the shard args in `inspect/eval-set.json`, so 32-way shards show counters like
`completion=11/17 failed=0` instead of raw tqdm output.

Later refinement on 2026-06-02. Confidence: high. The monitor now parses
`START`/`END` scheduler status lines to infer the active job per GPU and prints
a GPU-ordered table such as `GPU0: ifeval-da shard 0 13/17 ETA 4.6m`. ETA is
estimated from elapsed wall time since the job's scheduler `START` and the
current completed/total request count when a denominator is known.

DFM L epoch 4 eval completion/sync on 2026-06-02. Confidence: high.

All `168` CP4 eval jobs completed. One `generative_talemaader` shard initially
stalled after a port collision (`127.0.0.1:9602` already in use), was forced
through the scheduler retry path, and then completed successfully:

```text
2026-06-02T20:58:33+02:00 RETRY dfm generative_talemaader shard_4_of_8 gpu_1 status_2 next_attempt_2
2026-06-02T20:58:43+02:00 START dfm generative_talemaader shard_4_of_8 gpu_1 attempt_2_of_4
2026-06-02T21:05:38+02:00 END dfm generative_talemaader shard_4_of_8 gpu_1 status_0
```

The user asked to stop scheduler/monitor processes just as final merge started.
The eval computation itself was already complete. The final merge/W&B sync was
then rerun with `RESUME_EXISTING_QUEUE=1`, reaching:

```text
2026-06-02T21:09:37+02:00 FINAL_MERGE_START
2026-06-02T21:11:28+02:00 FINAL_MERGE_END
```

Local merged metrics were present for representative standard/DFM tasks,
including MATH, IFEval-DA, and generative-talemaader. W&B API verification for
`peter-sk-sdu/DFM L/kgnbdmwf` found representative CP4 metrics:

```text
eval/MATH/acc/epoch_4 = 0.48119616
eval/GSM8k/acc/epoch_4 = 0.7998448066717211
dfm_eval/ifeval-da/instruction_following/final_acc/epoch_4 = 0.46285377109091136
dfm_eval/generative-talemaader/model_graded_fact/accuracy/epoch_4 = 0.08168316831683169
dfm_eval/wmt24pp-en-da/chrf3pp/mean/epoch_4 = 0.5068738652893814
```

Superseded: the CP4 metrics above were synced to the wrong W&B target for the
comparison view. The intended target is
`peter-sk-sdu/Original Plus Mixed Danish Instruction Rich L/dfm-l-resume-epoch3`.
Confidence: high.

Corrected CP4 eval sync on 2026-06-02. Confidence: high.

The same local merged CP4 artifacts under
`logs/eval/dfm_L_epoch4_queued_all` and
`logs/dfm_evals/dfm_L_epoch4_queued_all` were resynced with:

```bash
EPOCH=4 CKPT_TAG=epoch_4 CKPT_PATH=checkpoints/dfm/L \
GPUS=0,1,2,3,4,5,6,7 \
WANDB_PROJECT="Original Plus Mixed Danish Instruction Rich L" \
WANDB_RUN_ID=dfm-l-resume-epoch3 \
WANDB_RUN_NAME=dfm-L-resume-epoch3 \
LOG_ROOT=logs/eval/dfm_L_epoch4_queued_all \
DFM_LOG_ROOT=logs/dfm_evals/dfm_L_epoch4_queued_all \
QUEUE_ORDER=heavy_first MAX_RETRIES=3 RESUME_EXISTING_QUEUE=1 \
scripts/schedule_checkpoint_evals.sh
```

This reached:

```text
2026-06-02T21:19:46+02:00 FINAL_MERGE_START
2026-06-02T21:24:52+02:00 FINAL_MERGE_END
```

W&B API verification for
`peter-sk-sdu/Original Plus Mixed Danish Instruction Rich L/dfm-l-resume-epoch3`
found representative CP4 metrics:

```text
eval/MATH/acc/epoch_4 = 0.48119616
eval/GSM8k/acc/epoch_4 = 0.7998448066717211
eval/MMLU/acc/epoch_4 = 0.28052499999999997
dfm_eval/ifeval-da/instruction_following/final_acc/epoch_4 = 0.46285377109091136
dfm_eval/generative-talemaader/model_graded_fact/accuracy/epoch_4 = 0.08168316831683169
dfm_eval/wmt24pp-en-da/chrf3pp/mean/epoch_4 = 0.5068738652893814
dfm_eval/humaneval/verify/accuracy/epoch_4 = 0.2195121951219512
```

Superseded: Unsharded checkpoint compatibility check on 2026-06-02. Confidence: high.

The current eval/export path does not yet load `checkpoint_format=unsharded`
checkpoints. `evaluation/engines.py`, `scripts/hrm_openai_server.py`, and
`conversion/convert_to_hf.py` all go through `simple_inference_engine.py`.
That loader currently resolves latest checkpoints by scanning
`fsdp2_epoch_*`, checks for `fsdp2_{tag}` plus `carry_{tag}.0.pt`, and calls
`torch.distributed.checkpoint.load(...)` on `fsdp2_{tag}`. Therefore standard
evals and HF export currently require sharded `fsdp2_{tag}` checkpoints unless
`simple_inference_engine.py` is extended to detect/load `unsharded_{tag}.pt`.

Unsharded eval/export support update on 2026-06-02. Confidence: high.

`simple_inference_engine.py` now supports both checkpoint layouts:

- sharded: `fsdp2_{tag}` plus `carry_{tag}.0.pt`
- unsharded: `unsharded_{tag}.pt` plus `carry_{tag}.0.pt`

This shared loader is used by standard evals (`evaluation/engines.py`), the
OpenAI-compatible HRM server (`scripts/hrm_openai_server.py`), and HF export
(`conversion/convert_to_hf.py`), so those paths can now load unsharded
checkpoints. Latest-checkpoint auto-detection scans both `fsdp2_epoch_*` and
`unsharded_epoch_*.pt`; explicit tags may be passed as `epoch_1`,
`fsdp2_epoch_1`, `unsharded_epoch_1`, or `unsharded_epoch_1.pt`.

The generic eval scheduler `scripts/schedule_checkpoint_evals.sh` now also
accepts either `fsdp2_${CKPT_TAG}` or `unsharded_${CKPT_TAG}.pt` when waiting
for a checkpoint. It still requires `carry_${CKPT_TAG}.{0..7}.pt` because the
training code stores carry state rank-locally. Validation performed after the
change: `python -m py_compile simple_inference_engine.py
conversion/convert_to_hf.py evaluation/engines.py`, `bash -n
scripts/schedule_checkpoint_evals.sh`, `git diff --check`, and a toy
state-dict smoke test confirming that model weights and AdamATan2 EMA optimizer
state restore through the unsharded `set_state_dict` path.

Carry state with FSDP vs DDP, 2026-06-02. Confidence: high.

Carry is not managed by FSDP or DDP. It is explicit `TrainState.carry` owned by
each process. The model receives it on every forward pass and returns the next
carry via `train_state.carry, loss, metrics = model(...)`. Checkpointing saves
it separately as `carry_{tag}.{rank}.pt` on every rank and resume reloads the
file matching the current global rank. This is the same mechanism for FSDP and
DDP; only the model/optimizer checkpoint format differs.

For current L-size HRM runs using `baselines.hrm_nocarry_bp_warmup`,
`initial_carry(...)` returns `None`, so the carry files are effectively saved
`None` placeholders. For any future carryful model, resuming should preserve
the same world-size/rank mapping and physical local batch shape unless the carry
implementation is explicitly made reshapeable or reinitializable.
