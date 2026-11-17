---
type: Runbook
title: DFM13–15 HF-only rebuild recipes
description: Isolated serial reconstruction of DFM13 and DFM14 additions and the preserved DFM15 native-reasoning sample.
tags: [dfm13, dfm14, dfm15, huggingface, reconstruction]
status: draft
last_updated: 2026-11-14
confidence: high
---
# DFM13–15 HF-only reconstruction

The user authorized preparation and execution of all three successors after
[DFM12 exact success](dfm12-hf-rebuild-recipe.md). This supersedes earlier
statements that no DFM13 execution was scheduled. Production data remain
read-only reference material; no uploads or promotion are part of this run.

`scripts/prepare_dfm13_15_hf.py` resolves immutable HF package revisions and
file SHA-256 pins. `scripts/rebuild_dfm13_15_hf.py` runs each version in its own
single-owner journal, with strict recursive predecessor receipt/config checks.
Configurations are `config/data/dfm{13,14,15}_hf_rebuild.json`; runtime and frozen
code hashes are checked at entry to each stage. Missing predecessor receipts
wait; mismatches fail closed. Download retries use explicit connect and total
timeouts, checksum checks and atomic replacement. Valid local acquisitions
are reused only after size and SHA verification.

DFM13 has 603 components, 7,692 reference shards and 565 HF packages. Published
accepted derivatives supersede stale null repository IDs in the historical
registry. Compact DaLA uses only train-representative rows, filters the
published recovery/baseline pool where required, and restores 25,000-row
shards. Wave sources use historical 5,000-row capped tokenization; nonwave and
synthetic sources use their 2,000-row full-context staging, followed by complete
overlength-example removal and token repacking. Faroese Setur instruction
pairs are mapped without editing text, retaining repeat 10. Worked MATH uses
its published derivative and historical task name. All five arrays per task
must match references before additions sampling.

DFM14 has 277 components and 261 HF packages. Nested Parquet `messages_json`
and `tools_json` fields are decoded; source texts are unchanged. Each published
shard maps to its historical tokenized part. The sampling tree restores the
historical component/part naming order. Keep all accepted additions: inherited
example deduplication remains disabled. Tokenization uses the 4,096-token
contract, and every added task must pass exact comparison before sampling.

Both versions sample three additions epochs using the frozen 1f52b10 sampler,
seed zero, drop mode, minimum response length one, and historical repeats.
The historical combine implementation appends tokens, offsets addition starts
and shuffles combined rows with the epoch number as seed. Final qualification
requires all 13 arrays and metadata to match the preserved sample.

The preserved DFM15 target is
`data/dfm15/native-reasoning-v2/sampled_dfm15`; the legacy
`data/sampled_dfm15` path is absent. Its recipe is a deterministic repair over
verified DFM14, not an additive four-package build. Registered later additions
are marked unsampled and are not silently inserted. Repair source offsets are
reconstructed from verified DFM11 union and DFM12 addition arrays, checked
against historical inventory metadata, and matched against the DFM14 backing
store before rewriting. Native thinking/direct conversion, quarantine and
sample pointer redirection use pinned implementations. Repaired arrays and
validity flags must match historical repair outputs; then all 13 final arrays
and metadata must match. Metadata reference paths are normalized to the locked
historical convention without taking production payloads as inputs.

## Launch evidence

Fifteen focused tests passed, including predecessor failure, train-only and
pool selection, nested JSON decoding, and inherited gate/merge/order tests.
Real HF DFM13 AI-arena and DFM14 Arabic denoising shards matched all five
historical arrays. Three repaired reasoning examples and the native template
matched preserved DFM15 outputs. These are preflight checks, not full-corpus
certification; the complete exact comparisons remain pending.

Confirmed detached runners: DFM13 PID 3183019 acquiring HF inputs; DFM14 PID
3183020 waiting for DFM13 exact success; DFM15 PID 3183021 waiting for DFM14
exact success. Work/receipts live under
`data/rebuild_hf_dfm/serial-queue/dfm{13,14,15}`. Logs are
`logs/analysis/dfm-hf-provenance-20261107/dfm{13,14,15}-scheduled.log`.

## Persian TLPC staging correction (2026-11-11)

After the user-requested ten-minute wait, investigation found exactly two
incomplete materialization families: `dfm13_tlpc_grounded_qa_fa` and
`dfm13_tlpc_grounded_chat_fa`. The historical `dfm12/tlpc_publish.py` uses
2,000 source rows per shard and the uncapped nonwave adapter, preserving every
assistant target and full history. The rebuild had mistakenly classified them
as 5,000-row capped wave sources. QA needs 30 shards; chat needs 20 (40,000
conversations yielding 120,000 assistant targets). All other 601 component
materialization receipts were complete.

Added an explicit TLPC tokenization-policy rule and regression tests. Preserved
the mistaken staging files, previous configs/schedules and acquisition receipt
under each work directory's `tlpc-policy-correction`. Updated runtime/config
pins with a recorded reason; the HF acquisition package pins are unchanged.
Restaged only the two affected families, yielding the expected 50 shards.
Sixteen focused tests pass. DFM14/15 waiters were stopped during the pin update;
their exact predecessor gates remain required on restart.

The first corrected shard of each TLPC family matches all five historical
arrays exactly (8,000 assistant targets total; ten arrays). Evidence:
`dfm13/tlpc-policy-correction/verified.json`. Restarted DFM13 PID 213313,
DFM14 PID 213314 and DFM15 PID 213315. All 603 materialization receipts now
exist; DFM13 resumes materialization validation before tokenization, while
DFM14/15 wait on exact predecessors. Full task/final comparisons remain pending.

Completion update (2026-11-11): DFM13 and DFM14 have each passed all 13 final
arrays and metadata, with matched exact HF-only receipts. DFM15 automatically
started its native-reasoning repair stage after validating DFM14's receipt.
Full DFM15 repaired-array and final-sample comparisons remain pending.

Final completion (2026-11-11): DFM15 completed all 83 repaired source parts,
matched their repaired arrays/validity flags, reconstructed all three epochs,
and passed all 13 final arrays plus metadata. `dfm15/verified.json` records
matched HF-only plus lexdk/DBC status and the exact DFM14 predecessor.
DFM13–15 are now complete; this supersedes all pending DFM15 status above.
The verified DFM15 scope is the preserved native-reasoning-v2 sample, not any
later unsampled additions or different training composition.

## Rebuild artifact retirement (2026-11-14)

Superseded regarding local artifact availability: after direct MTC v1/DFM8,
v1.5/DFM11 and v1.8/DFM15 passed complete final-array proofs in Mimir, the user
explicitly requested deletion of the redundant independent rebuild trees.
`data/rebuild_hf_dfm` has now been deleted, along with Mimir's old staged
`builds/MTCv1` tree. The historical matched results above remain valid; their
old local output paths no longer exist. Production datasets were not targets.

Before deletion, 111,961 HRM-Text metadata files were archived and read-back
verified, including all 15 matched final DFM receipts (DFM10 uses dfm10-hf-v2).
Mimir's 58,146 staged-build metadata files were likewise archived and checked.
Archives and deletion receipts are retained under
`/work/dfm/Mimir/builds/retired-rebuild-evidence/20261114/`.

Mimir first copied/reflinked and fully hash-verified 27,551 unique HF payloads
(542,319,257,731 bytes) into its own cache. All 38,158 active HF input references
now use that cache; its 119,296-link audit found only the 193 allowed external
DBC/Lex.dk links. All agreement targets are outside the deletion area. The
three direct MTC builds are retained. No production training/evaluation jobs
were stopped or modified.

### Remaining storage composition after retirement

The retained HRM-Text data inventory contains 54 physical top-level sampled
directories (24.292 TiB, including 23.552 TiB of token backings) and 93 physical
top-level tokenized directories (8.224 TiB). Converted/cleaned/filtered source
trees use 4.233 TiB; downloads use 0.951 TiB. Other generation/source work uses
9.149 TiB, including `data/dfm14` at 6.210 TiB. Across all retained directories,
token arrays account for approximately 39.24 TiB and indices 1.10 TiB.

DFM9's 8K/16K/32K source, tokenization and sampling variants collectively occupy
12.486 TiB. Historical `sampled_*_pre_*`, before-fix and pre-quality-review
backups also remain. These figures explain the remaining size; they do not
classify those production/history trees as safe to delete. Allocation totals
can count shared hardlink/reflink storage more than once. Evidence is the
Mimir `builds/cache-independence/disk-inventory.json` snapshot.
