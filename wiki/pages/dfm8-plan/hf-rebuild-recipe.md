---
type: Plan Record
title: DFM8 HF-Only Rebuild Recipe
description: 'Recovered DFM8 composition, acquisition pins, and rebuild pipeline for the isolated serial HF queue.'
tags:
- dfm8
- data
- reconstruction
status: draft
last_updated: 2026-11-02
confidence: high
part_of: /pages/dfm8-plan.md
---
# DFM8 HF-Only Rebuild Recipe

Part of [DFM8 Plan](/pages/dfm8-plan.md) and the serial HF reconstruction in
[DFM15 plan](/pages/dfm15-plan.md). Gated on a verified DFM7 rebuild; DFM8 must
not start until `dfm7/verified.json` reports `matched`.

## Union composition (from the preserved manifest)

`data/tokenized_dfm8/union_manifest.json` records exactly:
`base_selected_tasks` 10,651 (the DFM7 union), `dfm8_selected_tasks` 69,
`duplicate_skipped_tasks` 1,357, `skipped_tasks` 2,600, with
`base_tokenized=data/tokenized_dfm7` and `raw_tokenized=data/tokenized_dfm8_jinja`.

The committed union builder (`scripts/build_tokenized_dfm8_tree.py` at
`cd88c93`) fully reconciles with those counts: `dfm8_special_sources__*` (7) is
always selected; `export-upload-dfm8-synthetic__*` (42) and
`export-upload-dfm8-openhermes-repaired__*` (20) are selected when the stripped
name starts with `dfm8-synthetic-` / `dfm8-openhermes-{en,da}__`;
`export-upload__{common-pile,danish-dynaword,transformations}-*` (1,357) strip
to names that already exist in the base and are counted as duplicates;
`dfm8_transform_expansion_filtered__*` (2,600) match no rule and are skipped.
The apparent "prefix bug" (`dfm8_transform_expansion__` vs the actual
`dfm8_transform_expansion_filtered__` wrapper) is the skip mechanism itself,
not a defect. The 2,600 expansion and 1,357 duplicate raw tasks are therefore
deliberately NOT re-tokenized; the rebuild reproduces their manifest counts as
asserted receipts from a frozen-builder census over the preserved
`tokenized_dfm8_jinja` name inventory (4,026 raw tasks).

## The 69 additions and their provenance

- 7 converted special sources (CPU-deterministic converters at `cd88c93`):
  `giannor_tv2r_instruction` (dala_tv2r_it test/train/validation 147,618 /
  787,300 / 49,208 and gec_dala_tv2r_it 139,585 / 744,475 / 46,505 rows;
  `load_dataset` normalized the `val` split to `validation` historically) and
  `kobprof_skolegpt_instruct` (`train-00000.jsonl`, 21,580 rows).
- 20 repaired OpenHermes files (`dfm8-openhermes-en`/`-da`, 10 shards each).
- 42 targeted synthetic files (six families: code-debugging 4,
  constrained-format-following 9, danish-summarization-rewrite-controls 9,
  multiturn-danish-english-chat 5, native-tool-calling 9,
  strict-math-answer-contract 6).

The synthetic/repair generations were sampling-temperature model runs (Gemma 4
31B) and are NOT bit-reproducible; their frozen provenance is the published
Hub commits recorded on the wiki, pinned in the rebuild:
`dfm8-openhermes-en` `157a1488...`, `dfm8-openhermes-da` `a9458057...`,
`dfm8-synthetic-code-debugging` `87e99f98...`,
`-constrained-format-following` `61850112...`,
`-danish-summarization-rewrite-controls` `3b528aa7...`,
`-multiturn-danish-english-chat` `e345d051...`, `-native-tool-calling`
`3c2d1778...`, `-strict-math-answer-contract` `14ff86ff...`. The three special
acquisitions were already downloaded by the later-acquisition coordinator:
`giannor/dala_tv2r_it` `9976093c...`, `giannor/gec_dala_tv2r_it`
`308570cc...`, `kobprof/skolegpt-instruct` `c6152f13...`. Every downloaded
file is sha256-verified against the preserved local
`export-upload-dfm8-*` / `data/downloads/datasets` copies.

## Pipeline

`scripts/rebuild_dfm8.py` stages: `recover-lock`
(`config/data/dfm8_hf_rebuild.json`: 69 tasks, 11 input repos, frozen-builder
census, row counts, tokenizer inherited from the DFM7 lock; tokenizer_info.json
of `tokenized_dfm8` byte-equals DFM7's), `acquire` (snapshot downloads at the
pinned commits into `data/rebuild_hf_dfm/later-acquisition/downloads`, holding
that coordinator's runner.lock), `prepare` (staged prefix config from data_io
`0483afe` — working tree matches, sha256 `5d9469ce...` — frozen converters,
adapter `cd88c93`, template `33204f1a...`, tokenizer semantic check), `convert`
(frozen giannor/skolegpt converters with `PYTHONHASHSEED=2`), `verify-rows`
(byte-compare against `data/dfm8_special_sources`), `smoke` (three rows per
source family vs `tokenized_dfm8_jinja`), `tokenize` (bounded historical chat
driver), `assemble` (custom union assembly mirroring the frozen builder's link
semantics: 10,651 base links from the verified DFM7 rebuild union plus the 69
additions, with the historical 1,357/2,600 counts written as receipts),
`verify` (all 10,720 tasks, five arrays each, vs `data/tokenized_dfm8`).

Sampling: the preserved `data/sampled_dfm8` state is the documented seven-epoch
extension — epochs 0-5 were produced 2026-07-14 (`concat_workers=4`), epoch_6
and metadata were appended 2026-07-17 without touching `tokens.npy`
(139,426,979,015 int32 pool tokens; per-epoch total 70,479,436,697). The
rebuild runs `epochs=7 seed=0 concat_workers=4`; per-epoch selection is
independent of the requested epoch count (DFM7 evidence), so epochs 0-5 must
reproduce byte-for-byte and epoch_6 is the open question the queue comparison
answers.

Queue wiring: `SAMPLE_EPOCHS[8] = 7`; `enable-dfm8` installs recipe
`dfm8-hf-v1` with stages acquire, prepare, convert, verify-rows, smoke,
tokenize, assemble, verify, sample, compare; the sample stage is gated on
`dfm8/all-token-comparison.json` and the frozen prefix config; comparison is
the generic queue byte-compare against `data/sampled_dfm8` (epoch array
inventories, tokens.npy, metadata).

DFM8-post and the DPO preference pairs are separate exports outside this
recipe (`sampled_dfm8_post` has its own six-epoch sample; preference pairs are
a standalone DPO dataset).

Status 2026-11-02: recipe implemented with focused tests (6/6); recover-lock
wrote the lock (69 tasks, 11 inputs, 70 pinned files) and acquire downloaded
all eight pinned repos with per-file sha verification against the preserved
local copies (`registry_pin` basis). Nothing is enabled in the queue and no
equivalence is claimed until `dfm8/verified.json` exists.
