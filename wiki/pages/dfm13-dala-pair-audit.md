---
type: Runbook
title: DFM13 DaLA v2 Pair Audit
description: Full-pool batched pair and clean-control review without duplicate LA and GEC calls.
status: draft
confidence: high
last_updated: 2026-10-03
tags: [dfm13, dala, audit, multilingual]
---
# Full-Pool Pair Review

## Expanded Launch, 2026-10-04

### Completed nl/fa recovery additions

User-authorized recovery exports at
`/work/mimir/DaLA/la_output/v2/grammar-recovery-production-v3/{nl,fa}/output`
now independently report `ready_for_gpu_audit`, complete, pending checker0.
They were frozen separately at
`data/dfm13/dala-v2-nl-fa-recovery-inputs-20261004-v1` with all four compressed
source hashes and status/breadth/identity evidence. This adds359477 rows:
NL137888 pairs+114360 controls, FA58971 pairs+48258 controls.

Additive audit PID2821841 uses the same batch client at32 requests/server while
baseline PID2819305 remains untouched. Output:
`data/dfm13/dala-v2-nl-fa-recovery-batch-audit-20261004-v1`; log with that basename
under `logs/dfm13/`. It preserves source, row split/view and aliases. Sources and
producer processes were not modified. The two runs total at most64 requests per
server. Canonical deduplication is within each run; cross-run overlaps still need
deduplicated disposition when combining results. No training admission is implied.

The user expanded the request to all34 ready v2 baseline languages. This
supersedes the26-language scope below, not its provenance or non-admission rules.
Jason's sealed manifest is `data/dfm13/dala-v2-audit34/manifest.json`:
35,211,311 pair/control rows. Ready Dutch/Persian baseline exports are included;
ongoing additional production is neither consumed nor modified.

Initial PID2817453 made actual requests on all eight existing26B endpoints.
It was gracefully drained to apply the required `finish_reason=stop` check and
add the eight languages. It preserved30078 completed decisions and all queued
rows; a read-only check found zero non-stop completions among those decisions.
The original config is archived in the output root. Explicit predecessor config
SHA256 and unchanged source pins gate the additive expansion.

Resumed PID2819305,32 requests/server, at most16 pairs/control items per request:
`data/dfm13/dala-v2-baseline-batch-audit-20261004-v1`.
Log: `logs/dfm13/dala-v2-baseline-batch-audit-20261004-v1-34.log`.
Compressed sources stream directly; source hashes are verified as each source is
reached, not by expanding all exports before launch. Actual per-row split/view
and full source metadata are preserved in the alias table. Five focused tests
passed. No server or unrelated process was signalled. These are whole-pair audit
signals, not replacements for the producer's isolated-edit/composition receipts.

User scope is all26 DaLA v2 candidate pools, approximately24M pairs plus controls,
not a100-row sample. Jason owns pinned source discovery. Exports, original split
membership and unrelated nl/fa production are read-only. No audit launch is
claimed until an actual source manifest and process receipt exist.

The [batch handoff](../../docs/reports/dfm13_dala_v2_batch_handoff_20261003.md)
defines manifest fields and the command for `scripts.audit_dala_v2_batches`.
The adapter `dfm12.dala_batch_review` sends at most16 pairs/control sentences per
request, bounded by actual26B template tokenization and4096 response tokens.
Oversized batches split without truncation. Exact IDs bind decisions to complete
sentences; missing or duplicated members retry without repeating valid members.
One pair judgment serves LA and GEC, with source/split/ordinal aliases retained.
Clean controls are deduplicated separately and never mislabeled as noisy errors.

The reviewer independently checks clean grammar/spelling, a genuine noisy error,
complete correction and meaning preservation. Valid standard variants and merely
stylistic differences do not count as errors. Uncertainty stays nonaccepted.
These whole-pair signals are not native certification and do not impersonate the
producer's separate isolated-edit/composition audit receipts. No publication or
training admission occurs in this runner.

Existing `dfm12.audit_full.Database` provides durable leases/cursors and four
bounded technical attempts. Source reading and SQLite ownership use separate
single-thread executors; network concurrency is explicitly bounded per endpoint.
Every full source and receipt is hashed before dispatch from that source.
Five focused batch tests passed (eleven with repair/postprocess regressions).
Brief representative batch checking is required before bulk; no lengthy repeated
calibration stack is prescribed.
