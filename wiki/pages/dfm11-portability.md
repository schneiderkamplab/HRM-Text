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
