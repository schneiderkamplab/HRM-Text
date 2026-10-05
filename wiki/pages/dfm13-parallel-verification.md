---
type: Runbook
title: DFM13 Parallel Verification
description: Thirty-two-worker source verification with single-writer publication and restart receipts.
status: stable
confidence: high
last_updated: 2026-10-05
tags: [dfm13, verification, throughput]
---
# DFM13 Parallel Verification

On 2026-10-05 the owner authorized parallelizing the running final verification.
The sequential process held unpublished source results only in memory; these
could not be recovered on restart. Published predecessor checks are reused
only after full hash verification. The restarted registry has 607 entries
(including the now registered Setur/fo-instruct); 135 need source verification
beyond the published predecessor. Four explicit quality holds remain unchanged.
See [assembly history](dfm13-verified-additions-assembly.md).

## Execution

### Final sampled-output validation finding (2026-10-05)

Source verification and token copying/merging completed, but the final sampled
output was not published: `sample_dfm13_final.validate_sample` rejects response
lengths below two. A complete index-length scan found exactly 407 such rows in
both inherited DFM11 (235,520,711 rows) and merged DFM13 (365,938,673 rows),
and none in the new additions (130,417,962 rows). Neither base nor additions
nor merged output has an over-context prompt or combined length. Example base
row 217472 has instruction length 4096 and response length 1, within the 4097
storage limit. The sampler's truncation path checks the minimum response length
before truncating and permits one remaining response token; the final validator
uses a stricter invariant. This is an inherited-data/validator contract mismatch,
not evidence of newly introduced overlength examples. Staging remains available
at `data/sampled_dfm13.building-20261005-v1`; do not redo token copying or silently
drop inherited rows. Resolve the validation contract and rerun validation before
publication. No validator or data change was made during this diagnosis.

The owner subsequently authorized finishing the handoff. The validator now
allows only the exact inherited short-row multiset (all four token index
fields and multiplicity), rejects empty responses and unapproved short rows,
and requires every approved inherited occurrence to remain present. New
additions still use the strict two-token minimum. Five focused tests passed.
The sampler was restarted with 32 hash workers, reusing completed additions
and merged staging rather than recopying; final publication remains gated on
the full scans. This supersedes the earlier unresolved-validator status.

Set `DFM13_VERIFY_WORKERS=32` for the final assembly, Faroese successor and
sampling processes. `assemble_dfm13_successor.py` uses 32 spawned processes for
independent semantic/provenance/token verification. Each worker owns its
read-only SQLite connections and local pin map. The parent alone writes
receipts, assembles ordered results, checks duplicates/shared pins and publishes
under existing locks. Full pinned-file rechecks use 32 hash threads. Defaults
remain sequential when the environment variable is absent.

Set `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
TOKENIZERS_PARALLELISM=false` to avoid nested CPU thread pools. Spawn avoids
inheriting publisher lock descriptors. Completion order does not change
registry ordering or admission policy.

## Restart and Progress

Per-source receipts under `<assembly>-control/verification-receipts/` bind
the full registry entry, tokenizer contract, verifier code hashes and file
signatures. Only successful unchanged receipts are reusable; final assembly
hash checks still run. Failed sources never get a success receipt. Progress
is published at `<assembly>-control/parallel-progress.json`, with total,
completed, failed and remaining source names.

Current log: `logs/dfm13-final-successor-parallel-20261005.log`.
The original final verifier and waiting Faroese/sampling processes were
restarted by exact PID; training and the evaluation scheduler were untouched.
The Faroese successor accepts an identical already-included registration
without duplication, but still rejects conflicting versions.

Focused verification/restart tests: 70 passed. The XL handoff guard also uses
the sampled metadata's existing 4097-token storage convention (4096 predictive
positions), rather than incorrectly expecting a 4096 metadata value.
