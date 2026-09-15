---
type: Runbook
title: DFM11 Portability and Bootstrap
description: Transfer and reproducible-rebuild requirements for using DFM11 on another machine.
tags: [dfm11, portability, bootstrap, training-data]
status: draft
last_updated: 2026-09-14
confidence: high
---
# DFM11 Portability and Bootstrap

## XXL Epoch Three Campaign (2026-09-14)

The existing plan `logs/scheduler/dfm8_XXL_1epoch_steps50k_100k_persistent_vllm_20260725`
is extended by `scripts/schedule_dfm11_epoch3.py append --plan-dir <plan> --apply`.
It waits for the current DFM10 epoch two evaluation release, then resumes the
complete `checkpoints/dfm10/XXL-from-520000-half-lr/epoch_2` checkpoint on
`data=dfm11`, `epochs=3` (dataset index `epoch_2`). New checkpoints go to
`checkpoints/dfm11/XXL-from-dfm10-epoch2`. W&B remains project DFM5,
run `xxl-restart520k-20260910`; no new run is created.

Retain BP8, GAS8, global batch 262144, FP32 FSDP parameters, BF16 compute,
no-sync accumulation, no forward resharding, and clip norm 1.0. The new
epoch keeps the prior cooldown's final base LR 3.75e-5 with `lr_auto=true`
and `lr_min_ratio=1`; clear `lr_cooldown_checkpoint` because its anchor
belongs to DFM10. H/L/embedding-head rates are 1.875e-5/6.25e-6/3.75e-5.

Training pauses for full EMA standard, DFM, and EuroEval suites at 650K,
then every 50K. The plan reserves boundaries through 1100K as a conservative
upper bound, not an asserted epoch length. The segment wrapper verifies
checkpoint completeness after torchrun exits, updates fractional evaluation
epochs from the DFM11 row cursor, and atomically skips remaining boundaries
if epoch three has ended. Final `epoch_3` evaluation follows the last actual
boundary release (or the final training segment if no boundary was reached).
Its epoch coordinate is exactly 3.0. Later training uses terminal eval barriers,
so failed evaluations/merges do not strand training. Existing per-task batch,
judge, native proxy, persistent-server, merge, sync and v3 average settings
are retained, including 0.95 non-judged / 0.85 judged utilization.

The wrapper is a single-node campaign entry point; do not convert these rows
to the SSH launcher without preserving its post-training finalization.
Do not remove it while pending rows reference it. Plan changes use `PlanLock`
and preserve the pre-extension TSV in `plan.before-dfm11-epoch3.tsv`.

## Transfer to /work/mimir Started (2026-09-13)

Completed, verified on 2026-09-14: `logs/dfm11_transfer/complete.json` exists
and `data/sampled_dfm11` is published. All ten epochs have 235520711 index
entries; metadata total_length is 103214604702 tokens/epoch. Transfer took
about 77.5 minutes. Structural checks and tokenizer vocabulary validation
passed. The allocation scan measured 10229370482688 bytes (9.30 TiB) while
transfer was in progress; even adding the full 0.88 TiB transfer leaves ample
space within the user-confirmed 50 TiB allocation.

Storage limit: the user confirms this instance has a 50 TiB allocation.
`df` reports shared-filesystem free space (281 TiB at this check), not that
allocation's remaining quota. Use measured allocation usage against 50 TiB;
the DFM11 transfer requires approximately 0.88 TiB. The `quota` command is
not installed on this node.

SSH access to `ucloud@ssh.cloud.sdu.dk` port 6977 now works. The authoritative
`/work/dfm/HRM-Text/data/sampled_dfm11` contains ten epochs, about 904 GiB,
and metadata total_length 103214604702. `scripts/transfer_sampled_dfm11.py`
copies it with one resumable rsync stream capped at 200 MiB/s, running in a
detached tmux window `dfm11-transfer`. Log: `logs/dfm11_transfer/transfer.log`.

Destination is initially `data/sampled_dfm11.incoming`; after rsync completes,
NPY headers/file sizes/epoch row counts and tokenizer vocabulary are checked.
The script copies the exact source tokenizer and chat template to
`data/dfm11_tokenizer`, preserves source metadata in the transfer log directory,
and changes only the two local asset paths. It then renames the staged dataset
to `data/sampled_dfm11` and writes `logs/dfm11_transfer/complete.json`.
Do not infer completion from the staging directory's existence.

This is the training-ready handoff, not a reconstruction-source transfer:
the source `tokenized_dfm11` is a symlink tree pointing into multiple older
corpora. Copying those links alone would not make a usable local union.
The sampled token array and indices are self-contained and avoid duplicating
all those backing stores. Existing DFM10 training data is untouched.

Git carries the code, configs, documentation, and pinned submodule commits; it
does not carry the prepared corpus under `data/`. As of 2026-09-08, this host
has the completed 44 GB `data/tokenized_dfm11_additions` store, but it does not
have the required `data/tokenized_dfm10` base, a built
`data/tokenized_dfm11` union, or `data/sampled_dfm11`. DFM11 is therefore not
yet portable as a training-ready Git checkout.

## Preferred handoff

### B200 rebuild started 2026-09-08

The missing-base statement above describes the other `/work/mimir` host.
On `/work/dfm/HRM-Text`, the DFM10 tokenized base exists but the DFM11
packages and additions were absent. `scripts/tokenize_dfm11_from_hub.py`
now downloads all eleven pinned training packages, reproduces the English
FineInstructions controlled-plus-source-balanced-legacy selection, admits
only chats from the Danish release, and tokenizes the common staged tree
with 64 CPU workers. It reuses the DFM10 tokenizer/template at 4096 tokens
and preserves package-prefixed task names. It does not sample epochs.

The detached preparation/tokenization process logs to
`logs/dfm11/tokenize_from_hub.log`; its output is
`data/tokenized_dfm11_additions`. Publication metadata and FineInstructions
pair rows are not tokenizer inputs. Downloads were observed progressing;
completion must be checked in the log before constructing the union.

The authorized follow-on `scripts/sample_dfm11_when_ready.py --epochs 10`
waits for the atomic completion receipt, verifies all task array shapes and
index bounds, writes per-family sample/token/byte totals to
`logs/dfm11/additions_size.json`, builds the DFM10-plus-additions union, then
samples ten epoch index sets into `data/sampled_dfm11`. Ten matches the
existing DFM10 epoch inventory. Its detached log is `logs/dfm11/sample.log`.
The 64-worker request applies to tokenization; token concatenation uses the
sampler's existing 32-worker default. No existing sampled DFM10 data is altered.

After DFM11 has been finalized, transfer `data/sampled_dfm11` and the exact
Gemma 4 tokenizer/template artifacts named by its `metadata.json`. This is
sufficient for training with `data=dfm11`; retain the sampled metadata and
epoch directories unchanged.

Clone or update the code and pinned submodules with:

```bash
git clone --recurse-submodules <HRM-TEXT-REMOTE>
cd HRM-Text
git submodule sync --recursive
git submodule update --init --recursive
```

Use `rsync -a --info=progress2` or an equivalent integrity-preserving transfer
for the sampled corpus. Verify metadata, byte sizes, and hashes before training.

## Reproducible rebuild

### 2026-09-08 sampling policy regression

The completed local 10-epoch sample has 144,718,216,812 tokens per epoch,
versus 92,658,813,451 in sampled DFM10. Do not treat this as an approved
DFM10-plus-additions build. The claim that `prefix_config_dfm11.yaml` inherits
the current DFM10 policy unchanged is superseded: comparison found stale
baseline rules, missing repaired-source caps, and re-enabled superseded raw
sources. Examples include raw OpenMathInstruct2 and Nemotron SWE alongside
their repaired counterparts, uncapped repaired scientific summaries, and
removed Folketing caps. Restore current DFM10 rules plus explicit DFM11
overrides and resample before training. Existing output is diagnostic only.
Evidence: `logs/dfm11/sample.log`, both `data_io/prefix_config_dfm{10,11}.yaml`
files, and sampled metadata. No policy correction was applied during this
diagnosis.

Correction later on 2026-09-08: restored the complete current DFM10 rule
sequence verbatim after explicit DFM11 additions and the replacement
Folketing error-correction cap. Added
`scripts/validate_dfm11_sampling_policy.py`, invoked by the preparation script,
to reject inherited rule or order drift. Deleted the invalid epoch indices and
metadata (metadata receipt retained under `logs/dfm11/invalid_sampling_metadata.json`).
Started all 10 epochs again with `reuse_tokens=true`; the token union and
backing-file ordering are unchanged. Corrected sampling log:
`logs/dfm11/sample_corrected.log`. The 144.72B figure remains invalid; await
the new metadata for the corrected total.

Corrected sampling completed on 2026-09-08: metadata records
103,214,604,702 tokens per epoch (103.21B), versus DFM10's
92,658,813,451 (+10.56B, +11.39%). All ten epoch directories contain
four readable, matching-length index arrays, each with 235,520,711 entries.
The sampler exited after producing its final report. This completion
supersedes the pending status above and the invalid 144.72B sample.

If the target machine must rebuild rather than receive the sampled corpus:

1. transfer the exact finalized `data/tokenized_dfm10` snapshot, including
   agreement-backed inputs that cannot be reconstructed from public Hub repos;
2. transfer `data/tokenized_dfm11_additions`, or reconstruct it from the pinned
   DFM11 Hugging Face releases and validate row/token receipts;
3. run `python scripts/build_tokenized_dfm11_tree.py --force`;
4. from `data_io/`, run `sample_tokenized.py` with
   `tokenized_path=../data/tokenized_dfm11`,
   `output_path=../data/sampled_dfm11`, and
   `prefix_config_path=prefix_config_dfm11.yaml` for the intended epoch count;
5. compare `tokenizer_info.json`, the union manifest, sampled metadata, byte
   sizes, and hashes with the authoritative build before training.

For example:

```bash
python scripts/build_tokenized_dfm11_tree.py --force

cd data_io
python sample_tokenized.py \
  tokenized_path=../data/tokenized_dfm11 \
  output_path=../data/sampled_dfm11 \
  prefix_config_path=prefix_config_dfm11.yaml \
  epochs=<INTENDED_EPOCH_COUNT>
```

Do not rebuild only from public Hub datasets and call it equivalent DFM11: the
DFM10 base includes non-public/agreement-backed material. Do not sample from
`data/tokenized_dfm11_additions` alone. The tokenizer/template must match the
authoritative build; copying a machine-specific tokenizer path without copying
the corresponding file is insufficient.
