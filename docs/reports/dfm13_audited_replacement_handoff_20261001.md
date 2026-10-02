# DFM13 audited replacement export: CPU handoff (2026-10-01)

Design only. No export, admission, upload, source-config edit or active pipeline
change. Ledger counts below are read-only transaction snapshots, not final counts.

## Sources and authoritative inputs

`config/dfm13_sources.json` currently lists only the four original additions.
Existing `exports_dfm13` packages and `scripts/export_dfm13_arena.py` are
pre-audit derivatives; the latter copies converted rows, not accepted ledgers.
Its card says no generation/repair was used: that is unsuitable for replacements.

| Component | Original audit input rows |
| --- | ---: |
| ai_arenaen_preferred | 2,602 |
| arena_human_preference_100k | 64,939 |
| arena_human_preference_140k | 98,230 |
| arena_human_preference_55k | 39,471 |
| comparia | 460 |
| helpsteer3_edit | 7,909 |
| helpsteer3_preference | 21,377 |
| expert5k | 2,243 |

Original total 205,242; new eligible total 31,989. These are NOT export counts.
New-source manifest: `data/dfm13/pending-arena-screened-20261001/manifest.json`.
It removes HelpSteer validation overlaps (including two ComparIA matches), holds
57 Expert full-context overflows without truncation, and holds all 18,441 PRISM
candidates for unresolved noncommercial licensing. PRISM is not a ninth export.

Under `logs/arena_audit/`, use the linked pairs:

- `20261001-bulk205242-reasonfirst-thinking-v3` and
  `20261001-repairs-followup-v1`.
- `20261001-pending-next-v1` and `20261001-pending-next-repairs-v1`.

Both repair `plan.json` files identify their original `source` root and pin the
source manifest. Do not read the superseded bulk-v1 ledger as current authority.
During this inspection the repair accepted tables contained respectively
72,990 unchanged keeps + 7,475 corrected keeps, and 7,490 unchanged keeps + 919
corrected keeps. Counts changed during inspection: final snapshots are still needed.
Accepted-table membership alone is NOT independent quality approval.

## Minimal isolated layout

Proposed new root `exports_dfm13_audited/<snapshot>/`, never overwrite old roots:

```text
campaign.json                    # eight components; replaces four old additions
private/snapshots/               # consistent ledger backups; hashes, no upload
private/selections/<ledger>.json # exact seq/kind/candidate hashes for guard
private/readiness/               # Epicurus guard + manual receipts, hash-bound
private/exclusions.jsonl         # holds, rejects, technical failures, duplicates
<component>/data/train.jsonl     # canonical full messages + target_message_index
<component>/provenance.jsonl     # source/audit/repair lineage per exported row
<component>/manifest.json        # counts, pins, license evidence, mask policy
<component>/README.md            # accurate audited/repaired derivative card
```

One package per component, eight total; do not concatenate HelpSteer subsets.
Later integration must REPLACE the four old additions, not append audited copies
alongside their originals. Explicit allowlisted package files only for any later
upload; never root/private audit metadata or ledgers automatically.

## Selection and immutable evidence

1. Finish or deliberately freeze a completed subset using SQLite read-only
   transactions/consistent backup into a NEW directory. Do not copy a live DB
   file without its WAL, checkpoint production, or mark pending rows complete.
   Hash the sealed snapshot, source files, manifests, plans, implementations,
   hold versions and reviewer evidence. Recheck before final publication.
2. Join by `(ledger lineage, seq, source_id)`, not seq alone. Resolve each row
   exactly once. Repair disposition supersedes the corresponding original
   decision; never include both original and correction. Conflicts fail closed.
3. For an unchanged keep, reconstruct the source row using original offset/length,
   verify ID and canonical original-row hash, and preserve its full structure.
   A successful retry audit can create a valid unchanged keep even when the
   original job was invalid; retain its completed attempt and decision proof.
4. For a correction, require candidate hash + completed fresh_reaudit keep,
   correction provenance and original-row hash. Verify only targeted content
   changed; context, target index, tools and source identity stay unchanged.
5. Preserve source repo/revision/split/row/side/model/vote/license metadata.
   Add audit lineage as a sidecar (or explicitly separated export metadata), so
   the audited candidate digest remains distinguishable from final output hash.

## Epicurus hold-guard handoff: reuse, do not duplicate

Existing owner API: `scripts/dfm13_arena_export_readiness.py`,
`prepare(ledger, selection_path, output, manual_review, ...)` then
`enforce(receipt_path)`. Current independent holds:
`docs/reports/dfm13_bulk_repair_independent_holds_20261001.json`.
It blocks candidate-hash OR ledger/seq OR source-ID matches, so changing candidate
content cannot silently release a hold. Manual approval binds exact selection,
holds and assessment hashes and requires whole-target review. It explicitly
does not authorize export/upload. Preserve those semantics.

**Owner integration gap:** current `kind=original` reads original `jobs` and
requires a completed original keep. The repair branch reads `accepted` but
requires `candidate` and `fresh_reaudit`. Repair accepted tables also contain
unchanged keeps (`decision.verdict=keep`, no candidate), including successful
retry-audit keeps. Route ordinary original keeps through their original ledger;
ask Epicurus to add narrowly validated retry-keep support to the existing guard,
or omit those rows explicitly. Do not bypass it with a second permissive guard.
Snapshot-ledger aliases must retain original ledger identity for hold matching.
New next-source holds/reviews need explicit coverage; no empty-holds default.

## Required checks before any later authorization

- **Mask/template:** pin actual training tokenizer and raw current Gemma template,
  no Mistral regex fix. Validate target index is an assistant message. Render and
  CPU-tokenize whole history; loss only on the selected target including intended
  end token, never preceding assistant turns, user/system/tool context or padding.
  Preserve native tools/calls/results and template kwargs; no flattening. Test
  single/multi-turn, repaired-length changes, literal special-token strings and
  exact mask boundaries. Recheck training context budget; audit-fit is not proof
  of training-fit. No silent truncation or blanket all-assistant supervision.
- **Dedup:** exact structured messages + target index + tools + template kwargs,
  within/across all eight and inherited DFM12. Same text at a different target
  or with different tools is not automatically duplicate. Keep attribution for
  all merged occurrences. Recompute after repairs and screen changed content
  against held-out indexes; report missing inherited/benchmark coverage honestly.
- **License:** pin existing evidence, not generic CC-BY for all. AI Arenaen is
  CC-BY-4.0; Arena100/140 and Expert distinguish prompt license/provider output
  terms; 55K uses its Apache-2.0 source-card evidence; ComparIA has Etalab/CC-BY
  and provider terms; HelpSteer is CC-BY-4.0. Preserve repair teacher provenance
  and applicable terms. Do not imply repair erases original obligations. Expert
  train split does not prove universal benchmark decontamination. PRISM held.
- **Reconciliation/tests:** input dispositions sum exactly to snapshot rows;
  exported row hashes match guarded selections after dedup; reject missing target,
  modified history, invalid tools, stale holds, changed candidate, unapproved
  retry keep, duplicate seq, ledger alias mismatch and missing license evidence.
  Add consumer round-trip test proving masks survive package ingestion.

Remaining: final snapshots, owner guard integration, exact independent review
receipts/hold reconciliation, post-repair dedup/overlap and mask tests, derivative
cards, replacement config proposal, then separate export/admission/upload approval.
