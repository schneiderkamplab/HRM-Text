---
type: Runbook
title: DFM14 DaLA accepted release and integration
description: Sixteen-language audit-passed exports, train-only native tokenization and verified HF publication.
status: stable
confidence: high
last_updated: 2026-10-06
---
# Authorized DFM14 DaLA release

The owner requested export, integration and HF upload after the sixteen-language
DaLA audit completed. This is now an executable DaLA-only DFM14 component, unlike
the earlier research-only status in the [remote handoff](dfm14-remote-production-handoff.md).
Other DFM14 production families and live training remain separate.

Implementation: `dfm12.dfm14_dala_release` and `dfm12.dfm14_dala_publish`.
Run root: `data/dfm14/dala-audited-20261006-v1`.
Producer audit: `/work/dfm/DaLA/la_output/dfm14-audit/20261006-v1`.
Packages: `/work/dfm/DaLA/export-upload/dfm14-audited-20261006`.
Sixteen verified public destinations follow
`schneiderkamplab/dfm14-dala-v2-{language}-compact` (one per language, combining
base/additive runs). Explicit owner upload authorization is recorded in the plan.

The existing `dala-compact-whole-pair-four-labels-v1` acceptance and task-row
helpers are reused. Only correctly formed completed passes with a rationale and
raw-request identity survive; flags/reviews/failures are excluded. Independently
audited controls are retained without manufacturing controls from passing pairs.
All raw same-language heldouts, including rejected rows, protect train selection.
Exact normalized text/document, duplicate input and released split/view checks
apply. Inherited-corpus-wide and semantic decontamination are not claimed.

Every chat is independently reread and reconstructed from its original source
and audit. HF rows use stable native messages/target indices plus lossless
`provenance_json` and `audit_json`. Both tasks retain train and all four heldout
views. Train-only tokenization reuses `scripts/tokenize_chat_template.py`, the
current Gemma tokenizer at `../brainsurgery/models/gemma4_31b/tokenizer.json`,
and `data_io/chat_templates/gemma4_native_chat.jinja`, with 4,096-token bounds.
No dropped rows and exact array counts are required.

After successful integration, `data/dfm14/local-audited-dala-additions.json`
registers the 32 train components. This is a separate additive registry; no
existing DFM13 registry, sampled arrays, scheduler or running training is changed.
After HF verification it points at `published-registry.json`, which includes
immutable HF revisions while preserving the original local registry receipt.

The publisher checks package hashes and card validity before committing. After
publication it verifies every remote file, Git/LFS hash and downloaded manifest,
then loads both task configurations and each split at the pinned revision.
`publication-complete.json` is the final authority; all sixteen publications
and integrations are now complete and verified.

Two focused DaLA-side release tests pass, covering rejection/deduplication,
audit-rejected heldout protection, both HF loaders and remote hash rejection.
These are automatic mechanical checks, not native-human linguistic validation
or isolated-edit producer audit equivalence.

## First-release prior-index correction

The initial export attempt was stopped before any publication. Recovery-run
producer indexes contain parent candidates from this same campaign, despite
inherited zero-count first-release metadata. Applying the final recovery index
as an external prior release wrongly excluded base candidates. The exporter now
measures actual index tables and uses a pinned, actually empty first-release
baseline for external-prior checks, while retaining all producer index pins and
measured counts. Combined-release deduplication and raw-heldout protection still
apply to all runs. A regression fixture includes a populated additive prior and
verifies that base candidates survive. Two release tests pass after the fix.
The discarded attempt is archived under the run root; it produced no HF upload.

Temporary overlap/deduplication indexes use in-memory SQLite during export and
are saved as a pinned `heldout.sqlite` snapshot before export validation. This
avoids repeated shared-storage journal writes without removing any checks. The
run uses sixteen language workers and eight native tokenizer workers per active
language. No GPUs are used. Two regression tests also pass with this path.

The pinned prior index is queried within one read transaction. A 3,000-query
benchmark on shared storage took 0.929 seconds with per-query transactions versus
0.0021 seconds with one consistent read transaction; repeated lock acquisition
was the remaining export bottleneck. The two regression tests pass with the
read-transaction change. Evidence: `prior-read-benchmark.json` in the run root.

## Completed publication — 2026-10-06

All sixteen datasets are public and verified. The release retains **17,973,493
source records**: 14,938,563 corrupted/corrected pairs and 3,034,930 independently
audited clean controls. Each has two task views, yielding 35,946,986 chat rows.
All four original heldout views remain available, totaling 7,197,728 chat rows.
Only the **28,749,258 train chat rows** are integrated as 32 DFM14 components,
with **2,653,005,386 native Gemma tokens** and zero dropped rows.

Excluded: 410,140 flagged decisions, 1,062 review decisions, 46 failed requests,
828 nominal passes with empty rationales, six duplicate noisy/control inputs,
five contradictory clean/noisy labels and 84 released split/view conflicts.
All 828 strict-pass exclusions were independently classified as empty rationales.
Family/split counts and full source licenses/provenance are in each package.
This remains automated compact whole-pair/control selection, not native-human
or isolated-edit linguistic certification.

Every remote file inventory, size, Git/LFS content hash and manifest was verified.
Both task configurations and all five splits loaded at the pinned HF revisions;
every exported row had already passed full local source/audit/chat reconstruction.
The final registry includes immutable HF revisions and verified upload receipts.

| Language / HF dataset | Source records | Train chat rows | HF revision |
| --- | ---: | ---: | --- |
| [Turkish](https://huggingface.co/datasets/schneiderkamplab/dfm14-dala-v2-tr-compact) | 1,151,081 | 1,841,588 | `cd0e1516fe2a` |
| [Russian](https://huggingface.co/datasets/schneiderkamplab/dfm14-dala-v2-ru-compact) | 1,031,631 | 1,647,456 | `abfc2c949704` |
| [Chinese](https://huggingface.co/datasets/schneiderkamplab/dfm14-dala-v2-zh-compact) | 1,299,836 | 2,075,576 | `15352f68bde5` |
| [Modern Standard Arabic](https://huggingface.co/datasets/schneiderkamplab/dfm14-dala-v2-ar-compact) | 1,064,073 | 1,701,722 | `ad58595f0c29` |
| [Irish](https://huggingface.co/datasets/schneiderkamplab/dfm14-dala-v2-ga-compact) | 1,030,872 | 1,648,408 | `e0c676b7c5b4` |
| [Korean](https://huggingface.co/datasets/schneiderkamplab/dfm14-dala-v2-ko-compact) | 1,042,767 | 1,667,072 | `01b55cc6a378` |
| [Japanese](https://huggingface.co/datasets/schneiderkamplab/dfm14-dala-v2-ja-compact) | 1,141,344 | 1,822,762 | `a86fc722749a` |
| [Galician](https://huggingface.co/datasets/schneiderkamplab/dfm14-dala-v2-gl-compact) | 1,009,758 | 1,614,874 | `b75e93ac5754` |
| [Basque](https://huggingface.co/datasets/schneiderkamplab/dfm14-dala-v2-eu-compact) | 1,108,456 | 1,774,050 | `038300c0a2c5` |
| [Welsh](https://huggingface.co/datasets/schneiderkamplab/dfm14-dala-v2-cy-compact) | 1,307,705 | 2,092,462 | `6d453aecf74f` |
| [Hindi](https://huggingface.co/datasets/schneiderkamplab/dfm14-dala-v2-hi-compact) | 1,298,249 | 2,077,546 | `f0dcb19a7700` |
| [Hebrew](https://huggingface.co/datasets/schneiderkamplab/dfm14-dala-v2-he-compact) | 1,309,436 | 2,099,598 | `e7cad1e0231e` |
| [Indonesian](https://huggingface.co/datasets/schneiderkamplab/dfm14-dala-v2-id-compact) | 1,096,026 | 1,758,880 | `9775f0cb1db5` |
| [Vietnamese](https://huggingface.co/datasets/schneiderkamplab/dfm14-dala-v2-vi-compact) | 1,075,998 | 1,719,312 | `3d6edfed4f2b` |
| [Maltese](https://huggingface.co/datasets/schneiderkamplab/dfm14-dala-v2-mt-compact) | 1,011,471 | 1,615,998 | `aacd0f7ef0b2` |
| [Macedonian](https://huggingface.co/datasets/schneiderkamplab/dfm14-dala-v2-mk-compact) | 994,790 | 1,591,954 | `71cb0e6d0f75` |


Final evidence in `/work/dfm/HRM-Text/data/dfm14/dala-audited-20261006-v1`:
`publication-complete.json`, `published-registry.json`, `release-summary.json`,
`final-verification.json` and `strict-pass-exclusions.json`.
The active additive registry is
`/work/dfm/HRM-Text/data/dfm14/local-audited-dala-additions.json`.
This completes the DaLA component export/integration/publication; it does not
claim assembly of other DFM14 families or alteration of live DFM13 training.
