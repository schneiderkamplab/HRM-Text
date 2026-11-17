---
type: Reference
title: Separate DaLA Language Inventories
description: Source-level bounded-choice applicability and provenance for the DFM8-13 review.
tags: [decision-datasets, provenance]
status: draft
last_updated: 2026-10-21
confidence: medium
---
# Separate DaLA Language Inventories

Part of [DFM8-13 review](middle-datasets.md). Review only; no new conversion or admission.

DFM12's 381-component table enumerates its acceptability/correction views.
Its 24 local European task components map to 12 exact producer repositories via
[the explicit map](../../../docs/reports/dfm12_inherited_dala_upload_targets_20261004.json)
and [revision-pinned reuse receipt](../../../docs/reports/dfm13_inherited_dala_reuse_handoff_20261004.json).
Those repositories are already present in that table, not extra independent sources.

DFM13's 34 accepted compact-v2 language packages are **outside the 312-entry
addition registry** inspected here. Exact destination construction is in
[language packager](../../../scripts/package_dala_languages.py) and
[upload guard](../../../scripts/upload_dfm13_remaining_ready.py). The following
rows are derived from exact pinned ready-package paths in the two linked eval
manifests, not invented by lower-casing language names. In particular pt-PT
case differs from the eval key `pt_pt`.

For every language: **A** existing acceptability yes/no; **B/C** correction
validity or candidate correction, B only for traceable valid corruptions and
exact defined source recovery, C for alternate grammatical rewrites. Preserve
clean controls, meaning, task-specific language and paired provenance. No
assumption that the generated clean sentence is the only acceptable correction.

**These manifest rows are test/representative selections, not training rows.**
Only separately pinned train integration may contribute training decisions.
[Coverage report](../dfm13-dala-eval-coverage.md) records all 34 accepted-v2
packages, but historical21 evaluation still used legacy populations at capture.

| Eval language key | Exact HF language-package destination | Evidence / status | Applicability |
|---|---|---|---|
| `lt` | `schneiderkamplab/dfm13-dala-v2-lt-compact` | [additional13 test manifest](../../../config/dfm13_dala_heldout_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `lv` | `schneiderkamplab/dfm13-dala-v2-lv-compact` | [additional13 test manifest](../../../config/dfm13_dala_heldout_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `sq` | `schneiderkamplab/dfm13-dala-v2-sq-compact` | [additional13 test manifest](../../../config/dfm13_dala_heldout_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `be` | `schneiderkamplab/dfm13-dala-v2-be-compact` | [additional13 test manifest](../../../config/dfm13_dala_heldout_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `bs` | `schneiderkamplab/dfm13-dala-v2-bs-compact` | [additional13 test manifest](../../../config/dfm13_dala_heldout_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `bg` | `schneiderkamplab/dfm13-dala-v2-bg-compact` | [additional13 test manifest](../../../config/dfm13_dala_heldout_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `hr` | `schneiderkamplab/dfm13-dala-v2-hr-compact` | [additional13 test manifest](../../../config/dfm13_dala_heldout_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `hu` | `schneiderkamplab/dfm13-dala-v2-hu-compact` | [additional13 test manifest](../../../config/dfm13_dala_heldout_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `lb` | `schneiderkamplab/dfm13-dala-v2-lb-compact` | [additional13 test manifest](../../../config/dfm13_dala_heldout_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `sr` | `schneiderkamplab/dfm13-dala-v2-sr-compact` | [additional13 test manifest](../../../config/dfm13_dala_heldout_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `sk` | `schneiderkamplab/dfm13-dala-v2-sk-compact` | [additional13 test manifest](../../../config/dfm13_dala_heldout_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `sl` | `schneiderkamplab/dfm13-dala-v2-sl-compact` | [additional13 test manifest](../../../config/dfm13_dala_heldout_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `fa` | `schneiderkamplab/dfm13-dala-v2-fa-compact` | [additional13 test manifest](../../../config/dfm13_dala_heldout_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `da` | `schneiderkamplab/dfm13-dala-v2-da-compact` | [existing21 test manifest](../../../config/dfm13_dala_v2_existing21_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `en` | `schneiderkamplab/dfm13-dala-v2-en-compact` | [existing21 test manifest](../../../config/dfm13_dala_v2_existing21_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `nb` | `schneiderkamplab/dfm13-dala-v2-nb-compact` | [existing21 test manifest](../../../config/dfm13_dala_v2_existing21_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `nn` | `schneiderkamplab/dfm13-dala-v2-nn-compact` | [existing21 test manifest](../../../config/dfm13_dala_v2_existing21_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `sv` | `schneiderkamplab/dfm13-dala-v2-sv-compact` | [existing21 test manifest](../../../config/dfm13_dala_v2_existing21_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `is` | `schneiderkamplab/dfm13-dala-v2-is-compact` | [existing21 test manifest](../../../config/dfm13_dala_v2_existing21_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `fo` | `schneiderkamplab/dfm13-dala-v2-fo-compact` | [existing21 test manifest](../../../config/dfm13_dala_v2_existing21_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `nl` | `schneiderkamplab/dfm13-dala-v2-nl-compact` | [existing21 test manifest](../../../config/dfm13_dala_v2_existing21_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `pl` | `schneiderkamplab/dfm13-dala-v2-pl-compact` | [existing21 test manifest](../../../config/dfm13_dala_v2_existing21_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `de` | `schneiderkamplab/dfm13-dala-v2-de-compact` | [existing21 test manifest](../../../config/dfm13_dala_v2_existing21_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `fr` | `schneiderkamplab/dfm13-dala-v2-fr-compact` | [existing21 test manifest](../../../config/dfm13_dala_v2_existing21_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `es` | `schneiderkamplab/dfm13-dala-v2-es-compact` | [existing21 test manifest](../../../config/dfm13_dala_v2_existing21_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `it` | `schneiderkamplab/dfm13-dala-v2-it-compact` | [existing21 test manifest](../../../config/dfm13_dala_v2_existing21_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `cs` | `schneiderkamplab/dfm13-dala-v2-cs-compact` | [existing21 test manifest](../../../config/dfm13_dala_v2_existing21_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `pt_pt` | `schneiderkamplab/dfm13-dala-v2-pt-PT-compact` | [existing21 test manifest](../../../config/dfm13_dala_v2_existing21_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `fi` | `schneiderkamplab/dfm13-dala-v2-fi-compact` | [existing21 test manifest](../../../config/dfm13_dala_v2_existing21_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `et` | `schneiderkamplab/dfm13-dala-v2-et-compact` | [existing21 test manifest](../../../config/dfm13_dala_v2_existing21_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `ca` | `schneiderkamplab/dfm13-dala-v2-ca-compact` | [existing21 test manifest](../../../config/dfm13_dala_v2_existing21_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `el` | `schneiderkamplab/dfm13-dala-v2-el-compact` | [existing21 test manifest](../../../config/dfm13_dala_v2_existing21_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `ro` | `schneiderkamplab/dfm13-dala-v2-ro-compact` | [existing21 test manifest](../../../config/dfm13_dala_v2_existing21_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |
| `uk` | `schneiderkamplab/dfm13-dala-v2-uk-compact` | [existing21 test manifest](../../../config/dfm13_dala_v2_existing21_20261006.json), ready package path; held-out selection | A acceptability; B/C correction; no training from this eval selection |

The earlier proposed per-pool names ending `-compact-baseline` or
`-compact-recovery` are superseded by per-language publication; do not count
both. See [supersession script](../../../scripts/supersede_dala_pool_publications.py).
The [DFM12 catalog](../../../dfm12/config.yaml) pins
`schneiderkamplab/dala-english-common-pile` and
`schneiderkamplab/dala-dutch-dynaword`; six-language local producer definitions
are in [dala_sources.yaml](../../../dfm12/dala_sources.yaml). The latter give
local dataset names, not verified public HF destinations by themselves.

Earlier Danish candidates/fallbacks, not new active DFM8 additions:
`giannor/dala`, `giannor/dala_medium`, `giannor/dala_large`,
`giannor/dala_label_da` (A label candidates);
`giannor/dala_gen_v2`, `giannor/dala_gen_v3`,
`giannor/dala_gen_large_v3`, `giannor/dala_gen_large_v3_ci`,
`giannor/dala_gen_tv2r`, `giannor/dala_tv2r` (A/B/C depending on
acceptability versus correction config). Evidence: [original inventory](../dfm8-plan/danish-linguistic-acceptability-and-gec-data.md).
Do not use legacy evaluation splits simply because the source is convertible.
