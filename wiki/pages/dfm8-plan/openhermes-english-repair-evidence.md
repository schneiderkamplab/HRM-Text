---
type: Report
title: OpenHermes English Repair Evidence
description: CPU-only reconstruction of retained English audit and repair provenance for a proposed dataset-card update.
tags: [dfm8, openhermes, provenance, audit, publication]
status: stable
last_updated: 2026-09-23
confidence: high
---
# OpenHermes English Repair Evidence

## Publication Verified (2026-09-23)

After user approval, uploaded the expanded card and ten evidence files to
`schneiderkamplab/dfm8-openhermes-en` in commit
`9a461da6fa1e2792f9ba6430861804443b82d3db`. Verified all ten original training
shards against local SHA256/size before upload and again after upload: unchanged.
All eleven added/updated files match their remote LFS SHA256 or Git blob hashes.
The card restricts the default training split to `data/train-*.jsonl.gz`,
excluding evidence JSONL from training ingestion. Local receipt:
`logs/provenance/openhermes_en_20260923/upload_receipt.json`.
No training rows were regenerated or re-judged. This supersedes the pending
publication and remote-verification notes in the preparation record below.

No new judgments, model calls, dataset changes or uploads were made.
`scripts/prepare_openhermes_en_evidence.py` builds a bounded-memory SQLite
join from the existing audit, generation and local published-package records.
Twelve CPU bookkeeping tests pass.

## Local Artifacts

Prepared under `logs/provenance/openhermes_en_20260923/`:

- `upload_candidate/DATASET_CARD_DRAFT.md`: replacement card proposal.
- `upload_candidate/row_provenance.jsonl.gz`: one record per source ID,
  including existing judges, repair metadata, exact local file/line references
  and message hashes. Approximately 425 MB compressed.
- `upload_candidate/summary.json`: recomputed counts and existing labels.
- `upload_candidate/examples.jsonl`: 20 mechanically selected examples,
  not a representative quality sample or fresh assessment.
- `upload_candidate/input_inventory.jsonl`: original-file and log checksums.
- `upload_candidate/prompts.py`, `code_snapshot/`: current prompt definitions
  and implementation snapshots, not verified historical code versions.
- `proposed_upload_manifest.json`: checksums and publication proposal.
- `join.sqlite`: local-only intermediate; not intended for publication.

## Verified Counts

There are 1,001,551 distinct source rows and source-audit records, 512,376
distinct repair attempt records, 476,639 repair-audit records, and 918,095
distinct packaged source IDs. All packaged rows have matching positive
acceptance evidence and exact message hashes; no missing source links,
published-content mismatches or repair-original mismatches were found.

The package contains 460,695 accepted originals and 457,400 accepted repairs.
Existing source-judge flags for accepted repairs: 206,095 answer-only,
49,904 answer-and-style, 198,422 style-only, and 2,979 other/unspecified.
These remain model judgments, not verified correctness claims.

Omitted rows: 25,674 source-judge exclusions; 17,924 repair-judge rejections;
35,737 repair-generation failures; 2,454 source-audit operational failures;
1,315 repair-audit operational failures; 352 requested repairs without a
retained repair result. Total: 83,456. Archived failures count attempts and
must not be added to these unique-source counts.

## Corrections And Limitations

Supersedes the interpretation of `clean_rows_shadowed_by_repair` in the July
build summary: the code counted all repaired source IDs (457,400), but the
actual intersection with clean source-audit decisions is **zero**.
Published `source_answer_defective=true` is hardcoded for repaired rows;
style-only cases must not be described as proven wrong answers.

The proposed update leaves all training shards untouched. Credential-pattern
checks found no HF/W&B token or private-key signatures in upload candidates;
this is not a general privacy or license clearance. Exact upstream source/model
revision pins and historical implementation identity remain unverified.
The local package is associated with the recorded Hub revision
`157a1488d453aef9e827bddabc77d78c0bfd57ef`, not freshly remote-verified.

Propose a reviewed card update plus an `evidence/` directory with explicit
training-file patterns to avoid ingesting provenance as training rows.
Raw logs, full request archives and SQLite remain local. Publication requires
user approval and remote checksum comparison; no regeneration is required.

See [pipeline history](danish-openhermes-synthetic-run.md) and
[availability and recorded upload](hugging-face-availability.md).
