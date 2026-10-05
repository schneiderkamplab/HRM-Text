---
type: Reference
title: DFM13 DaLA V2 Audit Inventory
description: Frozen26-language final CPU candidate inventory with split and compact review contracts.
status: draft
confidence: high
last_updated: 2026-10-04
tags: [dfm13, dala, audit, provenance]
---
# Frozen Inputs, Not Accepted Training

## Assembly Readiness Snapshot, 2026-10-04

Read-only inspection found no new v2 export/integration package ready for Tesla.
Main baseline audit PID2883484 was active; EN/DE/FR/ES/IT/PT-PT/CS/SK/PL/UK
had both streams fully ingested, with no pending/running jobs in those languages
at the sampled instant, but each retained failed jobs. Source `complete=1`
means ingestion completion, not all-positive audit or release readiness.
BE was processing; later baseline languages were not yet ingested.

Separate recovery audit
`data/dfm13/dala-v2-nl-fa-recovery-batch-audit-20261004-v1/complete.json`
is terminal:354,584 valid decisions and4,893 failed jobs. Its last progress file
is stale relative to completion. Read-only decision counts:

| Recovery component | Pass | Flag | Review | Failed |
| --- | ---: | ---: | ---: | ---: |
| NL controls |112269|3|0|2088|
| NL pairs |135914|1220|19|735|
| FA controls |48255|3|0|0|
| FA pairs |55510|1385|6|2070|

Pass counts are all-split automated signals, not train-only exports. Sampled
failed controls had unexpected response IDs, not a negative linguistic verdict.
No reset/retry or client change was made. The main baseline manifest excludes
recovery intentionally: it has its own completed audit ledger.

Missing finalization before assembly:

1. Freeze per-language decisions and join every source alias back to pinned
   originals, split/view, document and edit provenance. Keep failed, flagged and
   uncertain records out of accepted subsets; document unresolved failures.
2. Use an explicit compact-batch acceptance adapter: results declare
   `producer_v2_audit_equivalent=false`. Do not forge producer isolated-edit
   receipts. Existing `dala_audited_release.py` expects an older different audit
   schema and implicitly expands pairs to clean rows; it is not directly usable
   for independent v2 controls without adaptation.
3. Preserve baseline/recovery/v1 deduplication, unique clean controls, document
   and raw heldout protection, split boundaries and agreed selection constraints.
   Failed coverage targets do not become satisfied through audit completion.
4. Emit validated acceptability/correction packages (yes/no vs exact original),
   train-only accepted artifacts, tokenizer receipts and registry entries before
   Tesla assembles them. Do not force clean controls to50% if supply is short.

Terminal pass subsets can be finalized with explicit excluded-failure counts;
there is no need to call failures accepted or wait for unrelated languages.
No such v2 finalization artifact was located in the inspected DaLA export and
HRM DaLA roots. Earlier published v1 packages are not new v2 completion evidence.

## Completed Recovery Included, 2026-10-04

**Supersedes the earlier waiting/exclusion state below:** both NL and FA
`grammar-recovery-production-v3/<lang>/output/status.json` now have
`complete=true`, `stage=ready_for_gpu_audit`; both breadth receipts show zero
pending checker rows. NL exports137,888 pairs/114,360 controls; FA exports58,971
pairs/48,258 controls. Both `coverage_requirements_met=false`: preparation is
complete despite unmet coverage targets. NL observed-family floors are false;
FA observed-family floors are true. Neither implies semantic acceptance.

New frozen successor:
`data/dfm13/dala-v2-audit34-with-recovery-v1/manifest.json`, with seal and72
explicit source components:68 baseline files plus4 recovery files. Baseline
manifests remain unchanged. Totals30,021,970 pair rows and5,548,818 control rows
are input sums, not cross-pool deduplicated counts. Preserve all split/view
aliases when reusing identical judgments; no validation/test training admission.
Preparation is finished; audit is not. Baseline audit PID2819305 was observed
running; main/Boole owns extending it to this manifest, with no duplicate launch
by inventory preparation. New sources have distinct `nl:recovery-v3:*` and
`fa:recovery-v3:*` components. `scripts/freeze_dala_v2_recovery.py` reproduces
this immutable successor. No DaLA edits.

## All34 Successor, 2026-10-04

The user expanded scope to all34, superseding the26-language operational scope
below while preserving its artifact. New inventory:
`data/dfm13/dala-v2-audit34/manifest.json`; see its
[handoff](../../data/dfm13/dala-v2-audit34/README.md).
Totals29,825,111 pairs/5,386,200 controls. Additional DA/NL/FA/BS/HU/LB/SQ/SR
use completed roots from the CPU completion report. NL/FA additive recovery
does not block auditing their preserved baseline; no live recovery rows enter
this snapshot. All68 exports are content-pinned,52 hashes inherited with fresh
stat checks and16 newly computed. Runner must verify content before consumption.
Main/Boole owns the direct-gzip adapter and actual launch; no duplicate client
was started by inventory preparation. No DaLA edits or training admission.

## Preserved26-Language Inventory

The user-requested26 languages are frozen in
`data/dfm13/dala-v2-audit/manifest.json`, with a separate seal and
[handoff](../../data/dfm13/dala-v2-audit/README.md).
Authority is DaLA's `wiki/artifacts/v2-audit-readiness-20261003.json`, not an
old baseline inventory. All52 candidate gzip exports were independently hashed;
counts reuse pinned producer full-stream censuses and are explicitly not a new
full-row recount. Samples confirm candidate structure, not population quality.

Total24,075,603 noisy pairs and3,624,839 clean controls. Train holds19,681,736
pairs/2,914,600 controls; all validation/test views remain separate and cannot
automatically become training. `pt_pt` maps to `pt-PT`; Lithuanian/Latvian use
revised `additional-baltic-v2` roots. Dutch/Persian live recovery is untouched.

Reuse existing compact clean and per-edit/composed-pair review contracts and
exact hash-bound caches. Check original correctness, real errors, meaning,
plausibility and label consistency. Acceptability uses yes/no; correction uses
the exact original. CPU-screened candidate flags are not semantic acceptance.
26B is bulk default,31B diagnostic-only; main owns the runner. No GPU work,
publication, source edits or training admission occurred.

`scripts/freeze_dala_v2_audit.py` reproduces the inventory into a fresh HRM root;
two focused tests pass. External source files remain in DaLA: consumption must
reverify the frozen hashes and fail on drift. No native-speaker certification
or new quality acceptance is claimed.
