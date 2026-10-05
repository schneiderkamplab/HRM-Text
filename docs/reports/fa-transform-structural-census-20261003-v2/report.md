# Persian Transform Structural Census

2026-10-03. CPU-only diagnostic over **all 242,042 accepted published examples**
across the four current pinned Persian Wikipedia transform exports. No filtering,
source-wide hold, republishing, registry update or GPU/model call was performed.
Counts are exact outputs of the documented rules, NOT semantic error rates.
The same source window can appear under multiple tasks; counts are training
examples, not distinct articles or unique windows.

## Counts

| Task | Accepted | Strict category-only | Strict heading-only | Empty-field-heavy | Proposed minimal exclusions | Remaining untouched |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Denoising | 73,802 | 2,223 | 0 | 2,074 | 2,223 | 71,579 |
| Paragraph reordering | 31,490 | 111 | 0 | 1,115 | 1,102 | 30,388 |
| Prefix continuation | 110,813 | 3,281 | 0 | 3,328 | 3,281 | 107,532 |
| Span filling | 25,937 | 480 | 0 | 663 | 480 | 25,457 |
| Total | 242,042 | 6,095 | 0 | 7,180 | 7,086 | 234,956 |

Columns overlap. In particular, 143 empty-field-heavy examples overlap the minimal
proposal; **7,037 additional empty-field-heavy warnings remain outside it**.
These are a review/cleanup queue, not an automatic second exclusion tranche.
Recognized empty-field presence (not necessarily heavy) totals 27,696 examples.

## Effective Prose Paragraphs

These counts exclude recognized headings/category/list blocks; mixed blocks with
prose count once. Unknown blocks do not count as confirmed prose. Thus this is a
conservative structural estimate, not a linguist-certified paragraph census.

| Task | Zero | One | Two | Three or more | Prose present, no empty-field marker |
| --- | ---: | ---: | ---: | ---: | ---: |
| Denoising | 14,396 | 17,476 | 15,002 | 26,928 | 51,416 |
| Paragraph reordering | 2,578 | 8,026 | 7,583 | 13,303 | 24,593 |
| Prefix continuation | 21,396 | 26,782 | 22,842 | 39,793 | 76,969 |
| Span filling | 3,521 | 6,522 | 5,779 | 10,115 | 19,544 |

**172,522** examples contain detected prose without empty-field markers. This
is evidence against a blanket source hold, not a semantic approval of those rows.
Some retain category tails, weak ordering, factual errors or other source noise.
Similarly, **41,891** zero-detected-prose examples are NOT all confirmed bad:
many contain unrecognized labels, lists, formulas, code, or prose our rules miss.

Reordering has 10,604 windows below two detected prose blocks and 18,187 below
three. Only 1,102 below-two windows are covered by the narrow minimal proposal.
Do not auto-drop the other 9,502 below-two cases with uncertain structure, or the
7,583 exactly-two-prose cases: meaningful two-block ordering can exist.

## Rules and Minimal Proposal

1. **Strict category-only:** at least three recognized category lines; every
   other nonblank line must be a recognized heading. Category patterns cover
   explicit labels such as living people, births/deaths, players/coaches, awards,
   alumni, cities, films and novels. Lines with sentence/clause signals are not
   classified as categories. This is a narrow high-confidence lexical flag,
   not proof that every unseen category or Persian nominal sentence is detected.
2. **Strict heading-only:** every nonblank line matches the explicit heading
   lexicon. Zero detections means zero under this narrow rule, not that there
   are no unknown heading-only windows.
3. **Effective paragraph count:** split original windows on blank lines. Discard
   recognized heading/list/category blocks. Count blocks containing a prose-like
   line of at least 35 characters/six words with sentence punctuation or common
   Persian verb evidence. Other short multiline inventories are uncertain lists;
   all remaining non-prose blocks are uncertain, not confirmed bad.
4. **Empty-field-heavy:** at least two malformed empty markers, OR an affected
   prose block with no clean prose block and at most 300 detected prose characters.
   Markers include empty standalone parentheses and empty birth/death/date-range
   endpoints. Identifier-adjacent function calls such as `Eject()` are excluded.
   This flag is a source-cleanliness warning, not automatic semantic rejection.

**Proposed minimal filter, not applied:** drop strict category-only/heading-only
windows across tasks, plus reordering windows with fewer than two detected prose
blocks **and no uncertain blocks**. This selects 6,095 metadata-only examples
plus 991 additional unambiguous low-prose reorderings = **7,086** examples.

This is a prose-utility policy, not a claim of corrupted targets: category-only
denoising can still teach correct spelling. If that utility is intentionally
desired, retain its 2,223 rows and the narrower proposal affects 4,863 examples.
Do not rewrite the existing published artifacts. Any authorized filtered
derivative should carry original IDs/pins, explicit exclusion reasons and a new
manifest. No automatic re-audit/repair or regeneration is recommended here.

## Manually Inspected Examples

Complete windows/messages, provenance and canonical record hashes are in
`examples.json`; every candidate has a line in `flags.jsonl`.

- Denoising, **source title عصام الراقی**: ID
  `0001d02193b6116148f4c6e3d110bab8b82e4b3b089d030899370e33a6f748e2`, record SHA
  `0d2324d41be8c567f7be1da8eda2e3ee50942c0cde7329d07acd2d06f30b6d16`.
  Window is `منابع` plus 21 category lines, no prose. Spelling task can remain
  mechanically valid, but it is not substantive prose denoising.
- Reordering, **سیمون اوکلند**: ID
  `0176c5ee5e84c1c93053a091aab6139a839ed2a0de5e920c3216ffca9aeb0172`, record SHA
  `485bfb6fbc1263621465d0afd95626d6db6e2d451d33d5fc2e0168f06dacfed6`.
  One filmography paragraph, an empty references heading, and 13 category lines;
  three raw blocks but just one prose unit. Clear low-value reordering candidate.
- Prefix, **ایمن المثلوثی**: ID
  `0001f278a04e3be26278550e8cce66df6742362ff93e19f35e5ef8ec2f52e8c8`, record SHA
  `afd49e6701a453b16585df7b614377ecc5e25116534ef6fe8668dc929024f351`.
  All 26 lines are categories; player identity is absent from the visible prompt.
- Span filling, **محمد کامارا (بازیکن فوتبال، زاده ۲۰۰۰)**: ID
  `00099c01824089b8b2da3e3f1b4b3b9035765f84e3ad6f733964c8871ebc7219`, record SHA
  `5bf9286e4642f4f046e245c2ed09ee9c37da5e4e02265a09feaa3707181fa685`.
  External-links heading and 17 category lines; no prose context.
- Empty-field warning, **کریستوفر هنستین**: ID
  `0003f6b6e23e5b7ae57664b377808b3a7372bf8f1062e5fd76e30d49a0d571fc`, record SHA
  `f4f9e5f89322aeab7e1d0c300ce1ec0170bf962edab66ea17b378e0be1c6747d`.
  A genuine short scientist description contains `(؛ زاده  درگذشته )`.
  This is source damage, but the minimal filter does not discard the prose.
- Useful-prose contrast, **اطلاع‌یابی**, from the preceding independent16 review:
  ID `ab3f5a42a2ffc5c86e9b6ec9bccaac29e6f1e4344d133e72e3430373df7c6be3`,
  record SHA `11c92e9ee33bd51f43b730a9403ad4a61c8eb972cc19d37b92e9791c80157377`.
  The continuation completes a skill-description phrase and follows an ordered
  discussion of information literacy. It has a metadata tail but is not equivalent
  to a category-only example; preserve it under the minimal proposal.

Spot-check scope: eight minimal-filter examples (first two per task) and eight
initial empty-field warnings were read, not all flagged examples. The initial
empty-field scan incorrectly included programming calls in the PLUS-language
article. This was fixed and regression-tested in v2; v1 is retained as superseded
diagnostic evidence. Long prose with one empty parenthesis no longer qualifies
as heavy merely because all prose happens to be in one block.

## Reproduction and Pins

```bash
python -m scripts.diagnose_fa_transform_structure --output <fresh-diagnostic-directory>
python -m pytest -q tests/test_fa_transform_structure.py
```

Seven tests pass. The streaming scanner verifies exact file SHA256 and row count
for every publication. `report.json` pins classifier source, all four published
files/HF data revisions, examples and per-ID flags. `summary.json` records the
overlap accounting. `receipt.json` binds this human-readable report and final
artifacts; source bytes are rechecked unchanged. No output here is a release or
an admission receipt.
