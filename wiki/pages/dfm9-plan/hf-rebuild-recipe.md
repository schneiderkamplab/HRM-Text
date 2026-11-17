---
type: Runbook
title: DFM9 HF-only rebuild recipe
description: Locked acquisitions, union composition and guarded stages for the DFM9 serial rebuild.
status: draft
confidence: high
last_updated: 2026-11-02
---
# DFM9 HF-only rebuild recipe

The DFM9 union is a link farm over the verified DFM6 direct-jinja, DFM7 and
DFM8 rebuild trees plus 693 freshly converted and tokenized tasks. The rebuild
lives in `scripts/rebuild_dfm9.py` with the input lock
`config/data/dfm9_hf_rebuild.json`; the queue row gains stages
`prepare, convert, verify-rows, tokenize, assemble, verify, sample, compare`
after `enable-dfm9`. `recover-lock` and `acquire` run manually before enabling.

## Union composition (from the historical link table)

- 10,722 base entries recorded verbatim from `logs/analysis/dfm9-prep/link_table.json`:
  10,521 links into `tokenized_dfm6_direct_jinja` (rebuild names are the
  stripped `dfm6/tokenized` names), 130 into `tokenized_dfm7_jinja`, 69 into
  `tokenized_dfm8_jinja`, plus `tokenizer_info.json` (dfm8_jinja) and
  `union_manifest.json` (tokenized_dfm8).
- 693 fresh tasks: 682 new-source conversions, 9 windowed Nemotron SWE tasks,
  2 Danish extension tasks (croco-munin DPO, multilingual GSM Symbolic DA).
- The 2026-11-02 live-tree cross-check found no in-tree alias links; an
  earlier reading that suggested `sapient_cleaned__data_clustered__*` aliases
  was wrong (superseded).

## Frozen revisions

- Adapter `cd88c93` — last `scripts/tokenize_chat_template.py` state before
  the 2026-08-07 DFM9 tokenization; it natively parses the
  `(condition, instruction, response)` parquet schema and generic jsonl.
- Chat template asserted byte-equal between `0483afe` (DFM8 pin) and `fe79a2d`
  (DFM9 prefix config state).
- Converters from `69fd85c4f9da91dac1b883f89cada6c88ac3117c`
  (`convert_dfm9_new_sources.py`, `convert_nemotron_swe_windowed.py`,
  `convert_dfm9_extension.py`); they were recorded after the historical run,
  so `verify-rows` byte-compares all 693 conversion outputs against
  `data/converted_sources` with a pyarrow content fallback for parquet.
- Sampling: `epochs=10 seed=0 concat_workers=4` with
  `prefix_config_dfm9.yaml` @ data_io `fe79a2d`; compare target
  `data/sampled_dfm9` (10 epochs, tokens.npy 202,238,551,523 int32 tokens,
  metadata total_length 93,929,976,190).

## Acquisitions

| Source | Repo | Note |
| --- | --- | --- |
| Natural Instructions | `Muennighoff/natural-instructions` | 757 frozen files |
| Code Meta Reasoning | `allenai/code-meta-reasoning-cleaned-final-string-id` | see below |
| Nemotron Terminal Corpus | `nvidia/Nemotron-Terminal-Corpus` | 29 files |
| NuminaMath 1.5 | `AI-MO/NuminaMath-1.5` | 3 files |
| CoEdIT | `grammarly/coedit` | 2 files |
| ASSET | `facebook/asset` | 2 files |
| Nemotron SWE | `nvidia/Nemotron-SFT-SWE-v2` | agentless + swe jsonl |
| croco-munin DPO | `danish-foundation-models/croco-munin-apertus-8b-da-simpo-full-50k` | preference_pairs.jsonl |
| GSM Symbolic DA | `danish-foundation-models/multilingual-gsm-symbolic` | historical revision; main moved |

Two recovery paths were needed on 2026-11-02:

1. The `allenai_code_meta_reasoning` raw download directory was replaced on
   2026-08-28 against the restructured `allenai/code-meta-reasoning-filtered`
   (36 shards). The 69fd85c downloader record shows the historical source was
   `allenai/code-meta-reasoning-cleaned-final-string-id`; the byte-faithful
   copy survives locally as `data/downloads/datasets/allenai_code_meta_reasoning_flattened_legacy`
   and `recover-lock` hashes it (`RECOVERY_SOURCE`). The `allenai/code_meta_reasoning`
   and `allenai/code-meta-reasoning` Hub ids are gone (404).
2. `resolve_revision` pins the newest Hub revision whose locked file sizes
   match; main is preferred, and the commit walk recovered the moved
   multilingual-gsm-symbolic revision `9ea1128640ab`.

~~SWE tokenized tasks `nemotron_swe_windowed__merged_XX.jsonl` are byte-identical
renames of converted `data/shards/shard_XX.jsonl` (shards 00-07; source mtime
1786203407 matches the tokenized receipt), and `__agentless.parquet` reads the
converted agentless parquet directly.~~ Superseded 2026-11-02: the merged tasks
are NOT single-shard tokenizations.

Corrected SWE semantics (proven 2026-11-02): each union task
`nemotron_swe_windowed__merged_XX.jsonl` is the concatenation of the
tokenizations of shard group `[8*XX, 8*XX+8)` — e.g. `merged_00` =
tokenize(shard_00..shard_07). Proof: historical `merged_00` (3,746,007,732
tokens, 1,241,832 rows) starts with exactly the fresh single-shard shard_00
tokenization (475,696,096 tokens, 157,042 rows) — `np.array_equal` for all five
arrays — and the group boundary lands on a clean token seam (shard_00's last
response ends at token 475,696,096; `merged_00` row 157,042 has
`inst_start = 475,696,096`, i.e. plain offset shift, no boundary token). All
eight historical `merged_XX` receipts record the source stat of their group's
FIRST shard (merged_01 → shard_08 size 509,224,133, …, merged_07 → shard_56),
confirming contiguous 8-shard blocks over all 64 shards. The 1:1
"merged_XX = shard_XX" reading was an inference from the receipts, which are
misleading: each shard yields ~5.3 tokenizer windows per conversation, so one
509 MB shard produces only ~475M of the ~3.75B tokens per merged task. The
recipe's `recover-lock` now emits `swe_merge` tasks (members = 8 shard paths,
receipt = first member's stat), `convert` links shards as `swe_shard_NN.jsonl`
sources, `tokenize` tokenizes each shard separately and concatenates groups of
8 with `inst_start`/`resp_start` shifted by the running token offset
(`merge_swe_group`), and `verify-rows` byte-compares all 64 shards. The
`__agentless.parquet` task reads the converted agentless parquet directly.

The recorded 69fd85c `convert_nemotron_swe_windowed.py` writes a single
`swe.jsonl` (32,589,195,796 bytes, 1,897,422 rows) while the historical
pipeline consumed 64 shards; the historical sharding script is lost, but the
concatenated historical shards are byte-identical to the fresh `swe.jsonl`,
so the shards are byte-slices of the same stream. The recipe bakes the 63
recovered cumulative byte offsets (`SWE_SHARD_OFFSETS`, derived from the
historical shard sizes; each shard ≈ 509.2 MB with line-boundary slack) and
`split_swe` reproduces all 64 shards byte-for-byte — verified against
historical shards 00, 07, 28 and 63 on 2026-11-02. The historical tree also
contains a stray `swe.parquet`/`swe.jsonl` from an earlier converter
iteration; DFM9 tokenization never consumed them.

## Staging layout

The staged converters resolve `REPO_ROOT` from their own location, so
`prepare` mirrors the historical layout under the work tree:
`work/data/filtered_sources/<friendly>`, `work/data/downloads/datasets/<friendly>`
(with a `.complete` marker for the extension converter) and converter outputs
at `work/data/converted_sources`. An earlier attempt staged them without the
`data/` component, which made `convert_dfm9_new_sources.py` silently convert
nothing; `prepare` now clears stale `filtered_sources`, `downloads` and `data`
directories, and `convert` fails loudly on an empty staged tree.

## Verification scope

`verify` compares the 693 fresh tasks' five arrays against the historical
`tokenized_dfm9_new` / `tokenized_dfm9_swe_windowed` / `tokenized_dfm9_ext`
directories and asserts the union inventory equals the historical 11,413 task
directories; the 10,722 base entries are covered by the DFM6/DFM7/DFM8
matched receipts. `sample` is gated on that receipt plus the frozen prefix
sha, and `compare` runs the queue's version-generic comparison against
`data/sampled_dfm9`.

Status 2026-11-02: lock written, 9 repos acquired (863 files, digest-verified),
DFM9 enabled (`dfm9-hf-v1`). The first convert attempt exposed the staging
layout bug and the lost SWE sharding step (both fixed); the runner is
re-running the pipeline with the recovered split.
