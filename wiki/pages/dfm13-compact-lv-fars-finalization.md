---
type: Runbook
title: DFM13 Compact LV Fars Finalization
description: Accepted-only compact-audit staging, exact repair lineage and publication gates.
tags: [dfm13, multilingual, publication, audit]
status: draft
last_updated: 2026-10-03
confidence: high
---
# DFM13 Compact LV Fars Finalization

**2026-10-04 final disposition:** the [Fars final strict audit](dfm13-fars-final-strict-audit.md)
failed its bounded fidelity controls. Preserve but exclude both pn_sum and
wiki_sum staged packages from final integration; no acceptance is implied by
their historical staged_keep counts. Latvian and other Persian components are
unaffected. This supersedes pending-final-audit expectations for these summaries.

The user authorized accepted-only export/upload/integration after the compact
audits and bounded repairs. This does not admit verification holds or clear
independent source-fidelity holds without exact candidate-specific evidence.

`scripts.finalize_compact_lv_fars` stages96922 source candidates from the compact
LV/Fars original audit, completed7840invalid and511interrupted retries, and
running25060one-shot repairs. It revalidates original ledger/catalog provenance,
request bindings, raw complete keep decisions, immutable user/source fields,
repaired-record reconstruction and exact blind re-audit candidate hashes.
Actual native Gemma student rendering enforces4096 context with no truncation.
Seven focused tests pass. No GPU/server/production code changes.

CPU staging PID2744627 uses four threads; root
`exports_dfm13/compact-lv-fars-staging-20261003-v1`, log
`logs/dfm13/compact-lv-fars-finalizer-20261003-v1.log`. Progress is durable in
`progress.json`; selection/evidence is in `selection.sqlite`. Staged keeps are
not marked admitted or publication-ready. Known5LV/7Fars independent source
holds stay excluded across candidate versions pending reviewed exact-hash
clearance. Full-source verification holds never become automatic keeps.

LV here means synthetic grounded-instruct, not the separately held/imported
Latvian Wikipedia QA source. Fars means pn_sum and wiki_sum. Do not overwrite
unrelated existing packages, invent one shared license, or silently replace
original candidate/source text. See the [operational handoff](../../docs/reports/dfm13_compact_lv_fars_finalizer_handoff_20261003.md)
for roots, stage precedence, Poincare review interface and publication steps.

The repair population subsequently completed25060/25060:21093keep,981repair,
2197needs_verification,667unresolved,115reject,7invalid re-audit. These counts
supersede the running-repair status above, not the publication gates. At the
latest CPU checkpoint,62848/96922 rows were examined and39372 staged keeps
passed binding/rendering; selection was still running. Final counts must come
from the sealed staging receipt, not this intermediate observation. No HF upload
or registry mutation has occurred in this finalization pass.
