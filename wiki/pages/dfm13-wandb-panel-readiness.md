---
type: Report
title: DFM13 Workspace Panel Readiness
description: Read-only exact Forge workspace backup and pending multilingual average and panel changes.
status: draft
last_updated: 2026-10-07
confidence: high
---
# DFM13 Workspace Panel Readiness

## Live headline correction (2026-10-07)

The owner requested replacing the stale Multilingual headline panel in
workspace `3fvncok3gjh`, section `Headline Averages`. Its old
`avg_population/multilingual_v1/score` covered only the original19 languages.
It now uses `avg_population/dfm13_multilingual_v2/score`, covering32 non-Danish,
non-English languages including DaLA v2, with axis `avg_population/epoch`.
Other panels, ordering and run selections are preserved. Before/after receipts:
`logs/wandb_workspace_specs/3fvncok3gjh-multilingual-v2-20261007/`.
This is a workspace-only change, not a history rewrite.

## Final deferred mapping

2026-10-07 USER OVERRIDE supersedes complete-only scoring for explicitly opted-in
new DFM13 populations: average available valid tasks per language, then available
languages; no zero imputation. Legacy populations remain complete-only.
Policy attribute `aggregation_policy=available_tasks_then_available_languages_v1`
is restricted to DFM13 IDs, participates in definition hashes, and is enabled
only via explicit copied registry or logger `--available-dfm13`. Original
installed definitions/plans are untouched. Pure historical API and source-pin
coordination are in the [available-policy handoff](../../logs/diagnostics/dfm13_available_population_handoff_20261007.md).
Workspace `population_available` gate verifies positive observed coverage and
exact new definition hash; it does not require complete=1 or3150-only history.
Prepared successor mapping/registry are under the deferred root as
`population-available-v2-{mapping,registry}.json`; already-existing panels must
not be appended again. Titles still need a coordinated update after backfill.
51 focused tests pass. No W&B or live scheduler writes performed.

2026-10-07 read-only audit confirms the coordinated scheduler applied the34
population and4expanded-traditional panels:460total panels,8sections. All new
XL keys have an observed3150000 baseline; four historical successor keys retain
67points. Five initially absent raw-key history-index entries were stale: direct
history scans found their baseline rows. XXL-wide is `dfm10-xxl-wide`; its index
contains no84new visible keys, while legacy headline/suite keys retain19records
each (not asserted unique checkpoints). Preserve legacy comparison panels rather
than fabricate expanded historical scores. Detailed evidence and Poincare handoff:
[history coverage report](../../logs/diagnostics/workspace-history-coverage-20261007/report.md).
No workspace or history writes were made during this audit.

Expanded traditional keys are now confirmed:
`headline_avg_dala_v2/{danish,english,overall}` and `suite_avg_dala_v2/dfm`.
Their four-panel mapping appends into existing headline/suite sections, never
replaces the67-point history. Read-only gate checks actual3150000 values,
definition hash and emitted counts20/17/8sections/99. The
[automatic workspace handoff](../../logs/diagnostics/todo5_workspace_expanded_automatic_handoff_20261006.md)
provides sequential verify/fresh-prepare/apply commands for Epicurus after AVG
completion, separately from the32/34 v2 population baseline. Not applied yet.

The42 old21-language DaLA-v2 raw panels are now APPLIED with exact installed-task
registry verification. Fresh before/after receipt root:
`logs/wandb_workspace_specs/3fvncok3gjh-old21-v2-raw-live-20261006`.
All previous panels remain:8 sections,422 total panels,367 in the combined
multilingual section. These new raw panels may be empty until evaluations log;
no history synchronization is falsely asserted. Seven tool tests pass.

The final deferred additive population mapping has34 panels:32/34 aggregates
plus all32 language averages. It uses Tesla's additive v2 registry and preserves
all old language averages. Mapping:
`logs/wandb_workspace_specs/3fvncok3gjh-deferred-final-20261006/population-additive-v2-all32-mapping.json`.
Apply only after complete remote3150000 baseline and fresh workspace fetch.
Four additional Danish/English/overall/DFM expanded headline/suite panels await
Poincare's exact keys and baseline; this remains explicit unfinished work,
not satisfied by the population panels. No logger or history writes here.

Historical five-panel patch APPLIED and remotely verified on2026-10-06 after
parent's3154500 sync. All67 checkpoint points were independently observed for
each of the four metric keys; average values matched the final prepared payload.
Two Danish panels, overall, DFM-suite and raw generative Talemaader now use
their Talemaader-v2 keys. Latest verified values: Danish0.6775067784,
overall0.6500294175, DFM0.7003715652, raw Talemaader0.3855198020.
Fresh before/intended/after workspace snapshots:
`logs/wandb_workspace_specs/3fvncok3gjh-historical-live-3154500`.
Remote history receipt:
`logs/wandb_workspace_specs/3fvncok3gjh-historical-3154500-remote-verified.json`.
No history writes, layout changes, or expanded-population panel changes occurred.
The initial unbounded read-only scan was stopped and replaced with a scan of
internal history steps3154400 onward; all67 checkpoint-axis points remained
mandatory. Use the hrm environment Python for `wandb_workspaces` availability.
Earlier pending-application notes below are superseded by this result.

Tesla completion subsequently supplied additive v2 population definitions in
the shared registry: legacy slots plus `dfm_la_v2` / `dfm_gec_v2`, not binding
replacement. Read-only inspection confirms Danish18 legacy plus2 new tasks.
Keep these definitions and identities; the handoff's tentative v3 suggestion
is superseded. Separate expanded headline/suite logger keys remain required.

2026-10-06 additive-task supersession: new averages must include old21 legacy
tasks PLUS their42 additional DaLA-v2 tasks; existing13 v2 pairs count once.
The prepared replacement-only population v2 definitions below are insufficient
for this latest request and must not be used as the final expanded recipe.
Separate new Danish/English headline, DFM-suite and overall series start only
at a complete3150000 baseline. Overall retains its section weighting and has no
multilingual term. The67-point Talemaader-v2 historical recipe stays frozen.
The [explicit logger/registry handoff](../../logs/diagnostics/todo5_expanded_averages_contract_20261006.md)
reserves new namespaces and describes required completeness/deduplication tests;
implementation and exact key confirmation remain pending Poincare/Tesla.
Expanded panels will be additive, not replacements of historical series.

Latest user supersession: synchronization pause is3154500, parent-owned; a
separate mapping/fresh dry run uses that exact gate. Await sync notification
before applying historical panels. New registry
`config/multilingual_headline_populations_dfm13_dala_v2_20261006.json` adds
32/34-language v2 population identities without modifying prior definitions.
Only old21 DaLA/GEC bindings change (38/42 respectively); their42 new raw panels
are additive and retain old heldouts/series. Exact proposed task-key contract
requires [Tesla confirmation](../../logs/diagnostics/todo5_tesla_dala_v2_contract_20261006.md).
Seven focused tests pass; no history writes or panel replacements performed.

Poincare's final handoff selects the67-point Talemaader-only historical successor,
not semantic-v2. Fresh post-addition mapping/dry runs are under
`logs/wandb_workspace_specs/3fvncok3gjh-deferred-final-20261006`.
Five existing panels change only after remote67-point verification; English/math,
old19 language averages, and the old multilingual aggregate remain untouched.
Fifteen separate32/34-population/new13-language average panels are appended only
after remote complete3150000 baseline values exist. No earlier points fabricated.
[Scheduler commands and evidence gates](../../logs/diagnostics/workspace_deferred_final_handoff_20261006.md)
provide read-only history verification and fresh concurrency-checked application.
Five focused tests pass. This owner has performed no replacement or history sync.

## Layout clarification and tool

Parent applied the combined raw-panel dry run. Independent fresh API check at
2026-10-06T05:10:29Z exactly matched the intended spec:8 sections,380 total
panels,325 multilingual panels. Run sets and all other sections are unchanged,
including visible old average/Talemaader panels. Receipt:
`logs/wandb_workspace_specs/3fvncok3gjh-combined-dryrun-20261006/independent-apply-check.json`.
Any deferred replacement must freshly fetch this updated workspace, not reuse
the pre-addition backup. Final mappings remain pending Poincare and3200000 sync.

The user explicitly retains the combined215-panel multilingual section, not13
new split sections. This supersedes earlier split-section proposals below.
`scripts/patch_dfm13_workspace.py` prepares110 raw additions inside that section
(325 after application), preserving8 sections/all270 existing panels and run
selections. Actual dry run at
`logs/wandb_workspace_specs/3fvncok3gjh-combined-dryrun-20261006` passed exact
full-spec restoration after removing only additions; three focused tests pass.
No remote changes yet. VALEU/unrelated panels remain untouched.

[Poincare/parent handoff and commands](../../logs/diagnostics/workspace_poincare_handoff_20261006.md)
describe deferred replacements: final key mapping plus an owner-produced,
remote-verified synchronization receipt at3200000 is required. Old Talemaader
and average panels remain until replacement values exist. The tool has no
history logging or training-run attachment; stale workspace/definition changes
fail closed. Earlier split-section dry run is superseded and rejected by tool.

TODO5 read-only inspection backed up the user's exact `3fvncok3gjh` view under
`logs/wandb_workspace_specs/3fvncok3gjh-readonly-20261006T050320Z`.
[Report](../../logs/wandb_workspace_specs/3fvncok3gjh-readonly-20261006T050320Z/report.md)
and [proposed keys](../../logs/wandb_workspace_specs/3fvncok3gjh-readonly-20261006T050320Z/proposed-changes.json)
record270 panels/eight sections and all exact current keys.

Forge public frontend configuration identifies backend `/api/wandb`; read-only
GraphQL at `https://forge.coreweave.com/api/wandb/graphql` returned the same view
ID, display name and exact spec as `https://api.wandb.ai`. Both before responses
are saved. No workspace mutation or metric logging occurred; no credentials are
saved in these diagnostic artifacts.

Actual panels retain `headline_avg_v3/{overall,danish,english,math_code}`,
`suite_avg_v3/{standard,dfm,euroeval}`, and `avg_population/multilingual_v1/score`
plus its19 language scores. Generative Talemaader still uses
`dfm_eval/generative-talemaader/model_graded_fact/accuracy`; requested successor
is `dfm_eval/generative-talemaader/model_graded_fact_v2/accuracy`.
The distinct EuroEval multiple-choice Talemaader panel is not that replacement.

Supplied DFM13 definitions propose13 new sections with110 raw metric panels,
plus per-language/population averages once Poincare finalizes versioning.
Old21 heldout sources remain unchanged. Do not replace average keys before
definitions and data availability are final. Preserve all current panel IDs,
layout, run selections, filters, groups and unrelated options; the actual current
workspace has one combined multilingual section, not the historical split layout.
Any later mutation requires a fresh full-spec concurrency check and post-write
verification, without recreating the user's workspace through SDK models.

Follow-up user constraint: retain existing overall weighting; multilingual and
all-language population scores remain separate, never additional overall terms.
Keep language definitions and old21 heldout identities unchanged. The panel owner
does not run any W&B history writer/backfill or attach to the live training run.
Leave the overall panel key unchanged until Poincare confirms an equivalent
successor recipe; do not infer weighting solely from the visible three section
panels because the averaging implementation also includes diagnostic sections.
