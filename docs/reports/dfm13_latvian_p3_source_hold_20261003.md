# Latvian P3 whole-source fidelity hold

## Supersession

Owner instruction on 2026-10-03 supersedes the earlier proposal to filter eight
sampled rows into a v2 release. The stratified sample revealed systematic risk,
not an exhaustive defect list. Both complete partitions now have registry status
`quality_hold_source_fidelity`. Repeats, original HF data revisions, provenance,
tokenization receipts and token arrays are unchanged. No filtered replacement
was built or published. Initial accepted_uploaded receipts remain historical
upload evidence, not current admission clearance. The tokenizer and assembler
exclude both entries; republishing cannot clear the explicit owner quality hold.

## Atomic Hold And Card Warnings

`data/dfm13/latvian-p3-quality-hold-20261003-v1/` contains the hash-bound reason,
before/after registry snapshots, atomic hold receipt and HF card-warning receipt.

| Repository suffix | Original data commit retained | New README-only warning commit |
| --- | --- | --- |
| `cc-by-4-0` | `dd39d2e75964de419df9ab38ac66d511bea3b756` | `a64b01b3fbc93eb203c67c868989cb5f0bbe446b` |
| `cc-by-sa-4-0` | `4bd0277b998dd85b0df21949ceb4ecfaaa666f67` | `4a53cf0c80f37d27b3d64d5c5fa014e43dfdc7ff` |

Repository prefix: `schneiderkamplab/dfm13-wave3-latvian-p3-`.
Remote warning bytes were verified. All non-card files retained their prior blob
IDs. Published data and original pin receipts were not overwritten. Historical
commits retain historical cards; warnings are on the new repository heads.

## Full Review Packet And Alignment Boundary

`data/dfm13/latvian-p3-english-alignment-20261003-v1/english-raw/` caches four
complete English train configurations, 9,844 rows, at `bigscience/P3` converted
Parquet revision `985469b111586131283ac28a9f92ef720c48a8fe`. The cache manifest
pins all raw files. No translation/model API was called.

Current packets are under `review-v2/`; previous `review/` files are preserved.
`all-candidates.jsonl` contains all 4,480 CC BY and 3,200 CC BY-SA rows, full
messages/targets, translated source questions/answers, hashes, English proposals
and all matching English-question alternatives.

Every released question is checked by configuration plus exact normalized Latvian
question text against its pinned source, not just ordinal. English lookup is by
configuration plus full question text, refusing arbitrary duplicate-key selection.
Only Unicode composition, line endings and edge whitespace normalize; negation,
punctuation and case are preserved.

**This is not yet a fully verified bilingual alignment.** Translated files lack
English question IDs. Exact lookup within each language cannot prove the bridge:

| State | Rows |
| --- | ---: |
| Manually checked bilingual bridge plus unique English question lookup | 20 |
| Unverified bilingual proposal, not ordinal proof | 7,639 |
| Ambiguous/nonunique English question match, alternatives retained | 21 |

Full source-aware pairing validation remains necessary. Ambiguous alternatives
must not silently collapse to the first English answer. All packet rows remain
admission-disabled and the whole-source holds remain active.

## Unsent 31B Calibration

`review-v2/calibration-requests.jsonl` contains 20 source-aware audits and eight
repair-proposal requests for `google/gemma-4-31B-it`. Zero requests were sent;
no 26B rerun or GPU process was launched. Diagnostic expectations are separate,
never embedded in audit prompts.

The rubric separates pairing, source fidelity, correctness, instruction compliance
and Latvian quality; requires literal evidence; treats English keys as fallible;
and distinguishes supplied-context reasoning from real-world factual assertions.
Repair requests preserve complete possible corrected questions/targets, allow
explicit source-grounded restoration of missing context, and require independent
later review. They authorize neither automatic admission nor silent data edits.
Manual labels are diagnostic, not native gold or fresh heldout evaluation.

Implementation: `dfm12/latvian_p3_alignment.py`. Exporter/publisher/alignment
tests: 26 passed. Stronger source-aware pairing/audit calibration remains the
next dependency, not a generic approval gate or an eight-row filter.
