---
type: Runbook
title: DFM12 Token Budget Accounting
description: Exact inherited EN-DA per-epoch translation baseline and read-only component token inventories.
tags: [dfm12, token-budgets, translation, cpu, provenance]
status: draft
last_updated: 2026-10-02
confidence: high
---
# DFM12 Token Budget Accounting

## Active XL Composition Source Recovery (2026-10-02)

`scripts/dfm12_training_composition.py` reports the actual no-identity
`epoch_10` in `docs/reports/dfm12_training_composition.json`: 117,000,690,762
rendered tokens, 42,652,451,265 response tokens and 284,380,704 target occurrences.
The selected inherited DFM11 `epoch_0` contributes 103,215,092,251 rendered
tokens, not its rounded ten-epoch metadata mean. The additions contribute
13,785,598,511. All dedicated identity additions have zero sampled occurrences.

Superseding the initial composition report's wholly unattributable inherited
bucket, the authorized SSH recovery from `ssh.cloud.sdu.dk:6768` retained small
provenance under `data/provenance/dfm11_remote_20261002`. All 16,023 source-task
names match the corrected sampling log, source ranges sum to 223,595,843,215
stored tokens, and 48,015 first/middle/last token probes match the local backing
store. This is bounded probe verification, not a full token-payload hash.
No token payload was transferred; training inputs were not modified.

Every inherited sampled token is now source-attributed. Conservative export and
downloader declarations assign 49,910,102,323 inherited tokens to documented
language categories; 53,304,989,928 remain language-unallocated or multilingual.
Broad SFT remains mixed, not benchmark instruction-following. Generic reasoning
is not commonsense; missing table cells remain null. Exact row alignment split
151 addition shards, including EN/NL DaLA and text transformations, with no
target-count mismatch. Portuguese locale aliases are normalized explicitly.

The recovery helper is `scripts/dfm12_recover_dfm11_provenance.py`. Offline report
replay runs the composition script, `--refine-only`, `--normalize-only`,
`--inherited-provenance data/provenance/dfm11_remote_20261002`, then
`--reclassify-inherited`. All language/family cells plus unallocated buckets
reconcile exactly to the active epoch's rows, rendered tokens and responses.
Every table/source/unallocated row also carries `row_percent_of_epoch`,
`rendered_token_percent_of_epoch` and `response_token_percent_of_epoch`.
Denominators are the whole active epoch, not a language subtotal; null counts
retain null percentages. `--percentages-only` refreshes these without rescanning.
Inherited DFM11 contributes 82.818809% of row occurrences and 88.217507% of
rendered tokens; additions contribute 17.181191% and 11.782493%, respectively.

For the separate corruption analysis, `sampled_error_rows/receipt.json` binds
42 per-tokenized-ordinal NPZ files covering 5,811,951 target occurrences and
4,806,880,490 rendered tokens. Raw-source-row joins must still verify assistant
expansion and tokenizer skips. TV2R task names `test`/`validation` have nonzero
inherited selection; this is not itself proof of overlap with any particular
evaluation release. See the recovery root's `sampled_error_rows_handoff.md`.

## Sampled Corruption Composition (2026-10-02)

Read-only script: `scripts/dfm12_error_composition.py`; report:
`docs/reports/dfm12_error_composition.json`. Renderer contract is documented in
`docs/reports/dfm12_error_composition_handoff.md`. The active population is
`data/sampled_dfm12_xl_epoch11_noidentity/epoch_10`: **284,380,704 row occurrences**,
**117,000,690,762 tokens**. The inherited base contributes 235,520,711 rows and
the sampled DFM12 additions 48,859,993 rows. These are not the older DFM12
sample or unique accepted-export counts.

The script reconstructs additions' token offsets in the sampler's sorted source
order and matches actual sampled instruction starts to source row ordinals.
It counts only accepted student rows explicitly labeled `correction`, excluding
acceptability examples. Producer train-pair annotations are joined by exact
original/target and corrupted/input strings, with character-edit reconstruction
checks. Conflicting/missing annotations remain unknown. No edit distance is
used to infer mistake counts, spelling, grammar, or edit identities.

Per-language bins are 0/1/2/3/4+/unknown annotated edits, including clean controls
in the denominator. Separate spelling, explicitly enumerated grammatical
morphology/syntax labels, and unclassified categories carry sampled rows/tokens,
percentages of whole training, and distinct rule-ID and exact edit-span-pair
counts. Mixed rows can belong to multiple categories; percentages are not
additive. Unknown metadata and generic word-deletion/swap labels are not silently
classified as grammar. Rule IDs and edit pairs are different diversity measures.

Coverage is explicitly partial: local inherited DFM11 sampled arrays lack a
complete source-boundary/row-provenance map. Danish is unknown, not zero; other
reported counts are identified DaLA-addition lower bounds, not a complete census
of all correction instructions in inherited or general instruction data.
Per-language caches and partial output include hashes and completion status;
the renderer must inspect `status`/`completed_languages`. The pre-category output
is historical, not the render input. Focused tests: **9 passed**. No training,
evaluation, data, GPU, or server state is changed by this report.

The category-enabled scan completed for all 20 non-Danish languages:
**12,773,305 identified correction row occurrences / 1,480,965,277 tokens**.
Spelling membership is 2,973,400 rows / 327,361,613 tokens; grammar membership
is 3,446,174 rows / 417,113,763 tokens; unclassified membership is 28,611 rows /
2,781,673 tokens. These overlapping memberships are not additive. Mistake-count
bins are 6,380,224 zero-edit controls, 6,234,280 one-edit, 158,722 two-edit,
zero three-or-more-edit, and 79 unknown rows. Final report status is
`complete_with_explicit_missing_inherited_coverage`; Danish remains unknown.
All category percentages and row-bin sums passed consistency checks; focused
tests were rerun successfully (9 passed).

### Remote Inherited Recovery (2026-10-02)

The additions-only coverage statement above is **superseded in part** by
authorized read-only recovery from `ssh.cloud.sdu.dk:6768`,
`/work/dfm/HRM-Text`. Evidence is isolated under
`data/provenance/dfm11_remote_20261002`; no active data or training state changed.
`scripts/recover_dfm11_error_provenance.py` extracts compact source metadata,
ordinals and message hashes; raw TV2R GEC and CoEdit provenance, source cards,
and Danish corruption-rule reference code are also retained. No token payload
was transferred. CoEdit Parquet uses PyArrow, not JSONL decoding. An initial
in-memory JSONL-only extraction failed when it reached CoEdit; its completed
JSONL outputs were validated and retained, and separate Parquet extraction
superseded that failure.

Boole's independent source-map and sampled-ordinal recovery supplies exact
multiplicity and rendered-token counts from inherited `sampled_dfm11/epoch_0`.
The error join verifies its successful receipt, source-map hash and each NPZ
hash. Source rows with exactly one assistant target can be joined only when
target counts align. Uniform correction sources with tokenizer skips retain
exact aggregate exposure but unknown row annotations; mixed summary/rewrite
sources do not receive an unsafe ordinal join or wholesale correction label.
The old additions-only report is preserved as
`docs/reports/dfm12_error_composition.additions-only.json`.

Reproduction command:
`python scripts/dfm12_error_composition.py --augment-report docs/reports/dfm12_error_composition.additions-only.json --inherited-root data/provenance/dfm11_remote_20261002 --output docs/reports/dfm12_error_composition.json`.
New per-language status is `complete_identified_sources`; category fields and
whole-training denominators are unchanged. TV2R test/train/validation and
CoEdit train/validation are accounted according to actual selection, not
silently filtered to train. This records historical exposure, not a claim of
benchmark decontamination. Clean TV2R controls use raw sentence equality after
full converted-message hash verification, not splitting a multi-paragraph
instruction at its first blank line.

Counts are producer/audit annotations, not human-certified linguistic errors.
TV2R `corrupt_spelling` is spelling; enumerated morphology/syntax rules are
grammar; `flip_far_for` remains unclassified. Folketing OCR, DynaWord/Common
Pile denoising, and CoEdit/editing without error taxonomy remain unclassified.
Source cards declare English Common Pile and Danish DynaWord; this is source
language attribution, not per-row language detection. Exact affected-token
pairs count only if they reconstruct the raw corrupted sentence. No spelling
or grammar inference uses edit distance. Focused regression tests: **19 passed**.

Final augmented report: **16,874,605 identified correction/editing rows /
5,870,903,549 rendered tokens**, including **4,101,300 inherited rows /
4,389,938,272 tokens**. Danish now has 3,266,822 identified rows and 3,502,109,299
tokens rather than wholly unknown exposure. Its bins are 492,063 clean controls,
448,490 one-edit, 32,303 two-edit, 64,173 three-edit, 193,536 four-plus-edit and
2,036,257 unknown rows. Explicit spelling covers 15,048 Danish rows (one rule,
66 verified pairs); grammar covers 372,565 rows (12 rules, 29,510 verified pairs).
Nine Folketing shards retain unknown row annotations despite known exposure;
five mixed synthetic shards remain unjoined. Four aligned synthetic shards
contribute 99,185 identifiable rewrite rows, excluding ordinary summaries/titles.
All recovered Folketing source hashes/counts match its 13-shard export manifest.
All language-bin sums and category percentages passed consistency checks.

## Final Accepted Supply, 2026-09-25

Supersedes the partial accepted-export snapshots below. All 89 validated and
uploaded packages have been measured in
`data/dfm12/export-token-accounting-final-20260925/accounting.json`:
15,988,682 training rows, 14,557,854 accepted parent records, and
3,548,176,188 preserved rendered tokens. Zero missing token records and zero
representative-template mismatches were found. Hash verification passed.

With all non-identity additions at repeat 1 and identity's 4,109,461 tokens at
repeat 10, the expected addition is 3,585,161,337 tokens per epoch. Added to
DFM11's rounded ten-epoch mean of 103,214,604,702, this gives an expected
106,799,766,039 tokens per epoch. These are accepted-rendering accounting
figures were subsequently confirmed exactly by all 387 tokenized shards and
the completed ten-epoch additions sample (`data/sampled_dfm12_additions`).
Tokenization emitted 16,499,866 assistant-target examples with zero skips;
multi-turn expansion explains the difference from 15,988,682 export rows.
Full DFM11-plus-additions assembly is still running separately.

| Added category | Tokens per epoch |
| --- | ---: |
| DaLA acceptability/correction | 1,080,646,674 |
| Other instruction (including Polish PLLuM sources) | 1,368,942,785 |
| DynaWord transformations excluding separate reordering | 730,103,835 |
| Reordering | 138,709,585 |
| Translation | 225,663,848 |
| Identity at repeat 10 | 41,094,610 |
| Total additions | 3,585,161,337 |

Related: [component preparation](dfm12-components.md),
[paragraph repair](dfm12-paragraph-repair.md),
[structure-preserving alternatives](dfm12-structure-preserving-reordering.md).
This task owns `dfm12/token_accounting.py`, its explicit auxiliary manifest,
focused tests, this page and isolated accounting outputs only. Central
status/index/log maintenance remains with the coordinating task.

## Recovered Inherited Baseline

### Current Additional Pool Snapshot, 2026-09-25

**Accepted-export refresh, later on 2026-09-25:** the 53-package export
snapshot below is superseded for latest exported supply by
`data/dfm12/export-token-accounting-20260925-v2/accounting.json` and its frozen
`inventory.json`: **58 validated packages**, **1,483,246,011 rendered tokens**,
**3,299,344 accepted parent records**, **3,431,930 training rows**. Zero missing
counts; all 58 first-record training-template checks matched. All compressed
audit-sidecar and package-manifest hashes verified. The five added packages are
DynaWord NO (209,480,476 tokens), DynaWord PL (170,530,106), UltraChat NL
(403,698,278), DaLA SV acceptability (56,327,041), and DaLA SV correction
(101,645,096). Export files and running jobs were not modified.

| Latest Accepted Export Category | Tokens |
| --- | ---: |
| Translation | 14,196,286 |
| Reordering | 138,709,585 |
| Other transformations | 730,103,835 |
| Other instruction | 410,593,667 |
| PLLuMIC / Align | 1,169,451 |
| DaLA instruction | 188,473,187 |

Refresh command: `python -m dfm12.export_token_accounting --output
data/dfm12/export-token-accounting-20260925-v2`. This invocation intentionally
does not repeat candidate accounting; its empty candidate subsection is not
a zero-supply claim. The separate complete current candidate report below
remains authoritative. Identity automated passes remain outside this exported
snapshot. These amounts are not sampled-per-epoch tokens.

The historical v2 inventory is superseded **for current candidate supply only**
by `data/dfm12/current-candidate-token-accounting-20260925-v1/accounting.json`.
The inherited per-epoch baseline below is unchanged.

- Frozen completed exports: **541,565,014 rendered tokens**, 1,075,834 accepted
  parent records, **1,208,420 training rows**, 53 validated packages. Evidence:
  `data/dfm12/export-token-accounting-20260925-v1/accounting.json` and its
  `inventory.json`. Later concurrent exports are not included. All sidecar and
  package-manifest hashes verified; zero missing token counts. First-record
  template checks matched in all 53 packages, including OPUS reverse directions
  and target-message selection. This is not a complete retokenization.
- Current candidate pool: **4,502,796,551 rendered tokens**, **16,217,646 parent
  records**, **18,093,272 training rows**. Four CPU workers streamed and SHA256
  verified every source in main 67 + Swedish 2 + Polish/Icelandic 4 manifests;
  unique identity records were read separately in a short read-only transaction.
  Zero missing counts. Superseded reordering and unscreened alternatives were
  not added. PL/IS contributes 3,065,136 records and **377,269,518 tokens**.
- Identity: 8,752 unique candidates / 4,128,102 tokens, all audits completed
  (177 pilot + 8,575 bulk). Automated keep=true with all three scores >=4:
  **8,715 records / 4,109,461 tokens**. These are not exported in the frozen
  inventory and are not human/native-speaker certified. Existing questionable
  Icelandic pilot acceptance remains a review caveat. Evidence:
  `data/dfm12/export-token-accounting-20260925-v1/identity-automated-pass.json`.

Candidate totals include eventual rejections and deterministic audit quarantines;
they describe available input, not accepted supply. They overlap exported tokens
and must **not** be added to them. OPUS counts already include both directions
and are summed once per parent pair. None of these totals is a sampled-per-epoch
amount. Deferred/unintegrated sources are outside this inventory.

| Current Candidate Category | Recorded Tokens |
| --- | ---: |
| Translation | 296,905,498 |
| Reordering | 163,692,994 |
| Other transformations | 1,055,861,393 |
| DaLA instruction | 1,147,079,782 |
| Other instruction | 1,833,653,295 |
| PLLuMIC / Align | 1,475,487 |
| Identity | 4,128,102 |

Reproduce with `python -m dfm12.export_token_accounting --output NEW_EXPORT_ROOT`
for a new export snapshot. Current candidate command:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.candidate_token_snapshot \
  --output NEW_CANDIDATE_ROOT \
  --identity-db data/dfm12/identity-9000-20260924-v1/jobs.sqlite \
  --source-manifests data/dfm12/full-audit-20260924-v1/sources.json \
  data/dfm12/full-audit-sv-20260924-v1/sources.json \
  data/dfm12/full-audit-pl-is-20260925-v1/sources.json
```

Both commands are read-only toward audits, exports and sources. Five focused
tests pass in `tests/test_dfm12_export_token_accounting.py`, covering pair-count
semantics, source hash mismatch, missing counts, accepted totals and rejection
of nonaccepted export-sidecar rows. No audit/server/export process was modified.

### Inherited Baseline Evidence

The installed `data/sampled_dfm11` contains ten epoch index sets. Its local
transfer did not include `logs/dfm11/sample_corrected.log`. Retrieved that report
read-only from the original transfer endpoint, `ucloud@ssh.cloud.sdu.dk:6977`,
at `/work/dfm/HRM-Text/logs/dfm11/sample_corrected.log`. No remote job or sampling
was started. The report is archived with SHA256 evidence in the accounting root.

The report's `Cov Toks (%)` is **cumulative across ten epochs**, not per-epoch
tokens or unique stored tokens. Verified in `data_io/sample_tokenized.py`:
`task.coverage` accumulates selections across epochs; the report multiplies
index lengths by coverage, while metadata divides total tokens by epoch count.

- Global report coverage: **1,032,146,047,024** tokens and **2,355,207,110** rows.
- Installed mean tokens rounded: **103,214,604,702**, matching report / 10.
- Installed index headers: **235,520,711** rows in each of ten epochs.
- Repaired OPUS EN-DA: **64 task shards**, **26,453,193,085** cumulative tokens.
- **T = 2,645,319,308.5 tokens per epoch**, both translation directions combined,
  including prompt and response tokens. This is the exact ten-epoch mean, not
  a claim about a particular epoch's individually sampled total.
- New English-pair cap: **floor(T/4) = 661,329,827** tokens per pair.
- Non-English-pair cap: **floor(T/16) = 165,332,456** tokens per pair.

The rational numerator/denominator is retained and integer caps are calculated
without floating-point rounding. The command reconciles every task-table
column with GLOBAL, rejects duplicate task rows, checks installed epoch row
headers and metadata, and refuses missing/zero repaired OPUS coverage.

**Superseded interpretation, 2026-09-24:** the existing
`dfm12.budgets.opus_budget` / `python -m dfm12 translation-budget` helper sums
coverage without epoch normalization. Applied directly to this ten-epoch
report, it overstates the intended per-epoch caps tenfold. That shared helper
is not changed by this ownership-scoped task. Use the new accounting result;
do not use raw `Tokens (%)`, unique coverage, or stored token-array size as T.

## Reproducible Command

From the repository root, first retrieval and inventory:

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.token_accounting \
  --fetch-inherited-report --output data/dfm12-token-accounting-NEW
```

Offline replay using the archived report:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.token_accounting \
  --report data/dfm12-token-accounting-20260924-v1/inherited-sample-report.log \
  --output data/dfm12-token-accounting-NEW
```

Output roots are exclusive. Outputs are `accounting.json`, `accounting.md`,
the archived inherited report and `input-manifest.json`; initial SSH retrieval
also writes `retrieval.json`. `--root`, `--sampled-root`, `--manifest`, and
`--render-missing-limit` are configurable. The command never modifies candidate
files, receipts, tokenization, audit queues or sampled indices.

Main completed candidate components are discovered under `data/dfm12/candidates`
excluding `*-pilot`. Additional prepared instructions, the v3 native/fallback
reordering pools, prior NL paragraph repair and the Swedish XML alternative are
explicit in `dfm12/token_accounting_manifest.json`. Older diagnostic generations
are not extra supply. Missing/held/pending components are reported, not estimated
from raw corpus sizes. Six-language additional DaLA registration is pending;
pre-isolation producer rows are not available DFM12 tokenized components.

## Measurement Semantics

- Candidate JSONL is streamed one row at a time and SHA256-checked against its
  receipt. Aggregate by language/task and preserve file-level evidence. Paired
  translation rows already contain both directions in `rendered_tokens`; count
  that value once, with two conversations, and label the language as a pair.
- Completed tokenization is checked independently by summing `inst_len.npy`
  and `resp_len.npy` in 65,536-row memory-mapped slices. Read only the header of
  `tokens.npy` for the separate storage count. Multi-turn context can reuse
  stored tokens, so storage is not the training-example token total.
- Candidate and receipt mutation during a scan fails closed. Available amounts
  are unaudited staging, never accepted or final sampled-token claims.
- If a future candidate lacks a recorded count, render up to 64 such rows per
  language/task by default. Any extrapolation is labelled a bounded **prefix**
  estimate, with probe size and no confidence claim. No missing data silently
  becomes zero. In the verified snapshot all available candidate totals are exact;
  no extrapolation was needed.
- PLLuM-Align contains nonfinite upstream metadata emitted by Python's JSON
  serializer. `orjson` rejects those lines, so a standard-library JSON fallback
  is recorded per file. Token counts still require strictly positive integers;
  NaN token counts are rejected. No source file is rewritten.
- No cross-component deduplication or final allocation is performed. Native
  paragraphs and explicit synthetic text-block tasks remain separate. Alternative
  Wikipedia releases must not be added blindly to existing pools.

Initial scan used one CPU and approximately 340 MB RSS. No token payload arrays,
full source corpora, GPU work, training/evaluations, or final sampling were needed.

## Inventory Findings

Major instruction components, exact rendered tokens:

| Component | Tokens |
| --- | ---: |
| English DaLA | 115,127,474 |
| Dutch DaLA | 142,932,108 |
| Dutch UltraChat | 451,482,360 |
| Dutch Dolci | 451,786,787 |
| Polish Dolci | 458,959,735 |
| Swedish Dolci | 457,874,849 |

All six totals match completed tokenization index sums. Smaller additional
instructions and detailed transformation language/task distributions are listed
in the generated reports, alongside alternative reordering pools without a
misleading combined grand total.

Available translation inventories remain far below their caps: EN-NL has
138,540,840 tokens (20.95%), EN-SV 130,723,558 (19.77%), EN-NB 21,149,884
(3.20%), EN-PL 4,941,798 (0.75%), and EN-NN 238,142 (0.036%). Most non-English
pairs are much smaller still. These are ceilings, not instructions to repeat or
fill shortages with lower-quality data. Any audit rejection reduces supply.

## Verification

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m pytest \
  tests/test_dfm12_token_accounting.py tests/test_dfm12.py -q
```

55 tests passed: epoch normalization, exact rational floor caps, report mismatch
and duplicate rejection, paired-direction accounting, receipt checksum failure,
bounded missing-count estimates, nonfinite metadata handling, and stored versus
rendered token semantics, plus existing DFM12 regressions.

The v1 accounting output is retained as diagnostic history: it identified one
PLLuM-Align JSON-parser incompatibility. The v2 replay uses the same inherited
report with the metadata-only JSON fallback and pending DaLA registration added.
**Completed v2:** `data/dfm12-token-accounting-20260924-v2/accounting.{json,md}`
contains 63 inventory entries, 60 exact measured candidate components, three
receipt-only pending/review entries, and zero accounting errors. All candidate
file hashes matched their receipts. All **12** completed tokenization checks
matched candidate rendered totals, including PLLuM-Align's **926,968** tokens.
Its 75 JSON fallback lines contained nonfinite metadata, not invalid token counts.
No extrapolated token estimates were needed. Both foreground accounting runs
completed; no accounting background process remains.

`git diff --check` passed. OKF validation reported only missing shared-index
links for this page and the concurrently authored DaLA registration page
(two errors, zero warnings); no schema or in-page link errors were reported.
Parent should link this dedicated page from the shared index; this task does not
edit central status/index files.
