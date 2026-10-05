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
