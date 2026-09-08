---
type: Runbook
title: DFM11 Portability and Bootstrap
description: Transfer and reproducible-rebuild requirements for using DFM11 on another machine.
tags: [dfm11, portability, bootstrap, training-data]
status: draft
last_updated: 2026-09-08
confidence: high
---
# DFM11 Portability and Bootstrap

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
