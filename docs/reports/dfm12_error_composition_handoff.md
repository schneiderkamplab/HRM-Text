# DFM12 Error Composition Renderer Handoff

## Final Inherited Update

The additions-only completion notes below are superseded in part by authorized
remote provenance recovery. Current JSON is ready: **16,874,605 identified
correction/editing rows / 5,870,903,549 tokens**, across 21 language entries.
DA/EN use `complete_identified_sources`; other languages retain
`complete_identified_additions`. Same category schema and whole-training
denominators. Inherited additions contribute 4,101,300 rows / 4,389,938,272 tokens.
Original additions-only result is preserved in
`docs/reports/dfm12_error_composition.additions-only.json`.

Danish is no longer wholly unknown: 3,266,822 identified rows, including
492,063 explicit clean TV2R controls. Nine Folketing shards retain unknown
row annotations after tokenizer skips; five mixed synthetic shards remain
unjoined. Other general instruction correction tasks can still be unclassified.
Read `inherited_recovery.missing` and `missing_coverage`, not the historical
`missing_coverage_before_recovery`. Full final counts and coordination notes:
`data/provenance/dfm11_remote_20261002/error_metadata_handoff.md`.
Focused tests: **19 passed**; all percentages and bin sums validated.

Current task only, 2026-10-02. No `send_input` tool is exposed in this agent
session; this durable handoff complements the commentary updates.

Output: `docs/reports/dfm12_error_composition.json`.
Read `status` and `completed_languages` before treating it as final. Languages
are checkpointed individually; reruns reuse hash-bound per-language caches.
Runtime estimate for the targeted scan: approximately 3-6 minutes. No recursive
raw-corpus scan, GPU calls, data edits, training or evaluation changes.

## Renderer Schema

Final scan completed: all 20 non-Danish languages are available; status is
`complete_with_explicit_missing_inherited_coverage`. No scan remains running.
Identified correction exposure is **12,773,305 rows / 1,480,965,277 tokens**.
Category memberships total spelling **2,973,400 rows / 327,361,613 tokens**,
grammar **3,446,174 rows / 417,113,763 tokens**, and unclassified
**28,611 rows / 2,781,673 tokens**. Mixed memberships overlap; distinct counts
must be read per language/category, not summed as global unique counts.
Mistake bins are 0: 6,380,224; 1: 6,234,280; 2: 158,722; 3: 0; 4+: 0;
unknown: 79. All per-category row/token percentages and bin totals were checked.
Focused tests rerun after completion: **9 passed**. Ready for rendering now.

- `schema_version: 1`
- `denominators.sampled_rows: 284380704`
- `denominators.sampled_tokens: 117000690762`
- `denominators.dataset`: active `sampled_dfm12_xl_epoch11_noidentity`
- `denominators.epoch: epoch_10`
- `languages[code].correction_rows`, `correction_tokens`
- `languages[code].pct_all_training_rows`, `pct_all_training_tokens`
- `languages[code].mistake_count_rows`: `0`, `1`, `2`, `3`, `4+`, `unknown`
- `languages[code].mistake_count_pct_within_correction`: same bins
- `languages[code].distinct_rule_ids`, `distinct_edit_pairs`
- `languages[code].categories[spelling|grammar|unclassified]`:
  `rows`, `tokens`, `pct_all_training_rows`, `pct_all_training_tokens`,
  `pct_within_correction_rows`, `distinct_rule_ids`, `distinct_edit_pairs`.
- `languages[code].coverage_notes` and `.status`

Category rows mean at least one annotated edit in that category. Mixed rows
count once in both spelling and grammar; category percentages are not additive.
Clean controls count in neither. Missing annotations and non-whitelisted type
labels are unclassified; `word_swap`/`word_deletion` are not automatically
declared grammatical errors. The grammar allowlist is explicit in `definitions`.
Distinct edit pairs are exact original-span -> replacement-span strings, not
whole sentences or edit-distance substitutions. No edit-distance inference.

## Coverage Limitation

Counts are exact sampled exposures for identified DFM12 DaLA correction
additions, not a complete census of embedded correction instructions throughout
all training data. The inherited 235,520,711-row base lacks a complete locally
available source-boundary/row-provenance map. Danish is **unknown, not zero**;
other language counts are identified lower bounds where inherited exposure is
unmapped. Do not label these as exhaustive per-language totals. Whole-training
denominators include the inherited base regardless of this coverage limitation.

The first pre-category output is preserved as
`docs/reports/dfm12_error_composition.pre-categories.json`; do not render it.
Current log: `/tmp/dfm12-error-composition-categories.log`.
Focused tests: 9 passed, including mixed-category rows/tokens and unknowns.
