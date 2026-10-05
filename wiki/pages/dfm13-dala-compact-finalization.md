---
type: Runbook
title: DFM13 DaLA Compact Accepted Subsets
description: Terminal compact-audit snapshots and CPU-only train-isolated finalization for Tesla assembly.
status: draft
confidence: high
last_updated: 2026-10-04
tags: [dfm13, dala, audit, integration]
---
# Independent Terminal-Group Finalization

## Nine Subsets Marked for Upload

Explicit user scope: EN/DE/FR/ES/IT/pt-PT/CS baseline plus NL/FA recovery.
`data/dfm13/dala-v2-upload-nine-20261004-v1/queue.json` durably records upload
intent, all-split paired-task exports, evidence pins and attribution requirements.
No HF call or upload completion is claimed. `uploaded=false` remains until a
remote revision and verified attachment receipt exist. Existing v1 repos remain
untouched; proposed destinations are new compact-subset repositories.

The separate `tesla-snapshot-binding.json` verifies exact9 integration hashes
and18 components against Tesla's immutable
`data/dfm13/dala-compact-nine-completed-20261004-v1` snapshot, registry SHA256
`6011c4af85fd7a95ebfdcee73e52ce4f60828f54593b4de2c065b96c86938993`.
Totals12,425,942 train task rows/1,027,403,459 tokens. Its combined assembly
PID2953341 was observed running; no changes were made to that process or the
live finalizer registry.22 focused tests pass (finalizer, queue and snapshot
binding). See the [queue handoff](../../data/dfm13/dala-v2-upload-nine-20261004-v1/README.md).

## Live Completion Check, 2026-10-04

PID2921663 remained healthy at17minutes elapsed with8 CPU workers and no
recorded errors.13 terminal groups were selected: NL/FA recovery plus baseline
EN/DE/FR/ES/IT/PT-PT/CS/SK/PL/UK/BE.23 other baseline groups were nonterminal
at the frozen selection point; the pipeline does not silently admit later rows.

Recovery exports/tokenization now completed and entered the local registry:

| Scope/task | Train task rows | Tokens |
| --- | ---: | ---: |
| FA recovery acceptability |83701|5250002|
| FA recovery correction |83701|8564564|
| NL recovery acceptability |201399|13371705|
| NL recovery correction |201399|24739034|

Total570,200 train task rows/51,925,305 tokens. These are two task views of
285,100 retained train source rows, not570,200 independent sentences.
Eleven selected baseline groups remained in progress. Local `registry.json`
contains4 complete components for Tesla; no claim of central assembly intake.
The overall `complete.json` was not yet present. This supersedes the earlier
first-check statement below that no exports/tokenization had completed.

User authorized accepted-subset finalization without waiting for unrelated
languages. `dfm12/dala_compact_finalize.py` implements the explicit
`dala-compact-whole-pair-four-labels-v1` contract. It never claims producer
per-edit equivalence.15 CPU tests pass, including a full synthetic export test
preserving validation/test but staging only train for tokenization.

Owned integration root:
`data/dfm13/dala-v2-compact-finalized-20261004-v1`.
Detached CPU pipeline launched PID2921663, CUDA hidden,8 preparation workers
with at most one tokenizer subprocess each. See the root's
[handoff](../../data/dfm13/dala-v2-compact-finalized-20261004-v1/HANDOFF.md),
`launch.json`, `pipeline.log`, then `plan.json`/`progress.json` when emitted.
Tesla owns central assembly; this pipeline only writes its own registry.

Every group is bound to a single read transaction over the live audit database,
with complete input/alias coverage and no pending/running jobs. Terminal failures
are excluded alongside flags, uncertainty and malformed positives. No accepted
raw fallback. Exports preserve source provenance and all original splits/views;
only accepted train rows enter native-template tokenization. Dropped token rows
or mismatched arrays prevent registry admission. Original26/34/recovery manifests,
DaLA sources, v1 history and GPU clients are untouched.

Heldout checks cover every raw baseline/recovery stream of the selected language,
including unaudited/rejected rows. Hash-pinned producer prior indexes preserve
v1 duplicate/split protection. Independent controls are not synthesized from
passing pairs. This is not producer balanced-release selection or a coverage
floor waiver; actual subset composition is reported rather than called balanced.

At first live check NL/FA recovery snapshots were frozen and EN baseline was
being read. That confirms preparation progress, **not completed exports or
tokenization**. Consult actual registry/progress files for current completions.

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.dala_compact_finalize \
  --root <fresh-root> --workers 8 --tokenize
```

The command refuses an existing plan. Failed/nonterminal groups stay out of its
registry and require a separately scoped successor, not mutation of audit jobs.
See [frozen inventory](dfm13-dala-v2-audit-inventory.md) for input scope and
the earlier read-only readiness investigation.
