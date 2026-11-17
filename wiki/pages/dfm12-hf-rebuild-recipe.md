---
type: Runbook
title: DFM12 HF-only rebuild recipe
description: Pinned HF acquisition and exact three-epoch additive reconstruction gated on verified DFM11.
tags: [dfm12, huggingface, reconstruction, verification]
status: draft
last_updated: 2026-11-10
confidence: high
---
# DFM12 HF-only rebuild

The user's request to queue DFM12 includes preparing its executable HF-only
recipe, not merely recording a recipe hold. This supersedes the initial held
queue entry described in the [DFM11 runbook](dfm11-hf-rebuild-recipe.md).

The preserved `data/sampled_dfm12/source-registry.json` defines 381 components
and 1,325 tokenized shards. It is an inventory/reference, never a source of
training text. `config/data/dfm12_hf_rebuild.json` pins 369 HF repositories to
immutable revisions and training-file SHA-256 digests. Public payloads are
acquired into the isolated queue work directory. Direct published DFM12
packages are preferred where the older registry points to producer packages.
Identity repeat remains zero as in the preserved composition.

Twelve audited European DaLA repositories contain two components each. Their
published chat shards are shuffled relative to historical training. Restore
order using each repository's pinned `provenance/train.pairs.jsonl.gz`: look
up the published chat by pair ID and variant, emit clean then corrupted, and
split at 50,000 rows. Payload values are unchanged. Only train chats are
selected; missing pair variants, row counts or shard inventories fail closed.
A temporary per-component SQLite index bounds memory during reordering.

`scripts/rebuild_dfm12_hf.py` provides preparation, preflight and a detached
single-owner runner. The runner requires DFM11's matched 41-array receipt,
matching input/config provenance, all 290 added-task comparisons and the
verified corrected DFM10 predecessor. A partial or failed predecessor cannot
release it. Stages are acquisition, materialization, tokenization, exact task
comparison, additions sampling, combination and final comparison. Completed
stages are journaled and skipped on restart. Runtime/config hashes are frozen
in the schedule; drift blocks execution.

Tokenization uses the frozen f9b588f adapter, verified HF tokenizer bytes and
template, maximum 4,096 tokens, and preserve-first-user=false. Every one of the
1,325 task outputs must match all five reference arrays before sampling.
Historical additions sampling uses three epochs, seed zero, drop mode,
context size 4,097 and minimum response length one. The frozen sampler is
1f52b10. Combination uses the historical deterministic DFM12 implementation:
append additions tokens after verified DFM11 tokens, offset only start indices,
and shuffle each combined epoch with the epoch number as seed. Isolated
metadata wrappers resolve tokenizer paths without reading production tokens.
Final metadata paths are normalized to the locked historical convention.

Final acceptance requires exact equality of all 13 final arrays (tokens and
four index arrays for three epochs) and metadata. Production arrays are
read-only comparison targets. No uploads or production replacements occur.
No DFM13+ execution is included in this request.

Evidence and state: `data/rebuild_hf_dfm/serial-queue/dfm12/`; log:
`logs/analysis/dfm-hf-provenance-20261107/dfm12-scheduled.log`.

## Armed state (2026-11-10)

Preparation and preflight completed. Eleven focused gate/order/merge tests pass;
the broader regression run passed 24 tests before the final temporary-storage
adjustment. Real HF OPUS and provenance-reordered Ukrainian DaLA prefixes each
match all five historical arrays. The original unordered DaLA smoke failure
is preserved as diagnostic evidence. Full-corpus exactness is still pending.

Detached runner PID 2457412 is confirmed alive with status `waiting`, phase
`DFM11 exact HF-only verification`. The serial plan now has recipe
`dfm12-hf-v1`, no recipe hold, and an armed schedule with config/runtime hashes.
DFM11 was still comparing its final arrays at launch. Temporary DaLA indexes
use the configured `/dev/shm/hrm-b-recovery` scratch area to avoid random
filesystem I/O; only reconstructed source shards and receipts persist.

Launch update (2026-11-10): DFM11's complete exact verification passed, releasing
DFM12 automatically. The live runner is acquiring pinned HF inputs; latest
logged count is 1,100/1,185 files with no error reported. Predecessor receipt
hash is recorded in `scheduled-progress.json`. This supersedes waiting status.

Acquisition retry (2026-11-10): HF acquisition stalled with two small files
remaining (Portuguese synthetic math/code, 1,139,698 bytes; Catalan DaLA
acceptability shard 00004, 15,160,520 bytes). At user request, stopped the
single runner and fetched both directly over HTTPS at their pinned revisions,
with bounded curl connect/total timeouts and retries. Both files passed exact
size and SHA-256 checks. The precise cause of the original HF client stall is
not established; the direct HTTP retry succeeded promptly.

The acquisition helper now reuses existing files only after size and SHA-256
verification, avoiding another HF client call for already valid data. The
schedule records old/new runtime hashes and the reason for this change.
Eleven focused tests pass. Restarted detached runner PID 2817511, with Xet
disabled and a 60-second HF download timeout for any future missing-file calls.
Rebuild data/recipe pins and final exact-verification gates are unchanged.

Completion: DFM12 finished every stage and the runner exited successfully.
All 381 materialization receipts and 1,325 tokenized tasks are complete; all
five arrays per addition task matched history. Final comparison passed all
13 arrays (combined tokens and four indices for each of three epochs) plus
metadata. `verified.json` records matched HF-only plus lexdk/DBC status,
config digest and verified DFM11 predecessor. This supersedes running status.
No DFM13 execution is armed by this completion.
