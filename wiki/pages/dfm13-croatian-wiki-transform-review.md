---
type: Report
title: Croatian Wikipedia Transform Sample Review
description: Independent source replay and bounded structural and semantic review of sixteen accepted Croatian Wikipedia transformations.
status: stable
confidence: high
last_updated: 2026-10-03
---
# Croatian Wikipedia Transform Sample Review

Read-only CPU follow-up to the
[Persian review](/pages/dfm13-persian-wiki-transform-review.md). Four accepted
examples per task, using ordinals `floor((N-1)*i/3)`, i=0..3. Published task
populations at review: denoising 67,456; reordering 30,986; continuation 66,422;
span filling 38,427. These are population sizes, not semantic review coverage.

All 16 pinned source rows, document IDs/URLs/titles, seeded windows, candidate
IDs and messages replay exactly. All are accepted originals. Denoising restores
8/23/4/1 deleted characters plus case changes; all four reordering permutations
are complete and nonidentity; suffixes and spans are exact. No wrong-source join,
transform target drift or generative-repair hallucination was observed.

## Content Findings

- All four reordering cases shuffle non-prose headings/categories alongside prose.
  One, Alberto Ognjan Striga (`00017d4187f1436bb6751cce9d5ed80a1cef660b4cb3692615f02e6378b89b4a`),
  has only one prose paragraph, plus sources, an external-link citation and
  categories. This is a definite layout-versus-paragraph task mismatch.
- That same source/target contains conflicting birth months: biography April 30,
  external-link title May 30, both 1821. The contradiction is demonstrated without
  choosing which date is correct or attributing it to transformation generation.
- The other reordering cases contain four, six and four real prose paragraphs.
  Discourse/chronological cues remain useful; metadata presence alone does not
  justify removing them. Exact original ordering need not be uniquely inferable.
- Zero of the sixteen windows is category-only or heading-only. One denoising
  window is a discography/list with titles and dates, not merely category labels.
  It is a useful counterexample to a blanket zero-prose exclusion rule.
- All continuation cases contain substantive prose; Kardisa additionally has an
  empty population-growth section. All span gaps are meaningful source passages,
  but exact factual details are not uniquely determined by visible context.
- Several original spelling/grammar problems survive exact targets. This is
  source noise, not generated hallucination. Fine Croatian register/style and
  external historical/legal/scientific facts are not certified by this review.
- Raw empty infobox fields occur in the full Marty McFly source **outside** the
  selected window. They must not be counted as defects in that accepted candidate.

## Policy Boundary

The shared metadata-as-paragraphs mechanism exists in HR; the prevalence and
the Persian category-only pattern are not established by this bounded sample.
Recommend a Croatian-specific diagnostic census with manually checked examples
and uncertainty labels before any filter proposal. Do not reuse Persian regexes,
reject legitimate lists or short prose, apply whole-article defects to a window,
or extrapolate a failure rate from these sixteen cases. The present evidence
nominates one sampled reordering case, not a quantified corpus-wide exclusion.

No source data, publication, registry, token arrays, eligibility, worker or GPU
state changed. No source-wide hold or automatic filter was applied.

## Full Croatian-Specific Census

The proposed diagnostic above was subsequently completed over all **203,291**
accepted rows. Final artifacts:
`docs/reports/hr-transform-structural-census-20261003-v4`.
`scripts/diagnose_hr_transform_structure.py` is Croatian-specific and does not
import Persian rules. Exact heading labels, limited final-block category cues,
finite-verb/sentence evidence and list/reference uncertainty are kept separate.
These are **exact detector counts, not exact semantic-quality counts**:

| Task | Rows | At least 2 detected prose blocks | Below 2, furniture-only remainder | Below 2, unresolved/list remainder |
| --- | ---: | ---: | ---: | ---: |
| Denoising | 67,456 | 47,279 | 355 | 19,822 |
| Reordering | 30,986 | 22,810 | 44 | 8,132 |
| Continuation | 66,422 | 46,520 | 348 | 19,554 |
| Span filling | 38,427 | 27,065 | 221 | 11,141 |

The two-prose threshold applies only to reordering, not the other three tasks.
Reordering histogram: 2,567 zero / 5,609 one / 6,393 two / 16,417 three-or-more
detected prose blocks. Unknown and list blocks are deliberately not treated as
confirmed furniture. Meaningful-list evidence occurs in 2,390 reordering rows,
overlapping these categories; it does not imply failure. Strict recognized
category-plus-heading-only counts are zero (limited lexicon, not proof of absence).
One denoising window is external-link furniture plus a category, not literally
category-only; it is outside the reordering recommendation.

**All 44 narrow reordering candidates were manually read**, with individual
notes, and replayed against pinned source parquet rows/windows/messages. Each
has one substantive **shuffled unit**, with sources/headings/citations/categories
providing the remaining units. Some units contain single-newline-separated
sentences or topic snippets; they must not be relabelled as separately shuffled
paragraphs. Examples span chemical descriptions, biography, neighborhoods,
winemaking, village history and river history. The exact 44 IDs and record hashes
are bound in `reviewed44.jsonl` and `proposed-reordering-ids.json`.

Seventeen additional representative/control cases were independently read.
Klickitat and Donja Dubica show genuine sparse layouts outside the narrow
dictionary; E-number, sports-result, album and species inventories demonstrate
why missing prose is not automatically useless content. Rab and HKD Ljuba retain
substantial narrative despite metadata. Do not equate unresolved with either
accepted quality or a confirmed defect.

**Recommendation only:** separately authorize these exact 44 reordering IDs
for exclusion; this would retain 30,942 reordering rows and all 172,305 rows in
the other tasks (203,247 total). Do not automatically reject the other 8,132
low-detection reordering rows or broaden to list-bearing tasks. No filter or
publication change was performed in this diagnostic turn.

Versions v1-v3 are superseded exploratory outputs: inspection caught date-led
Croatian prose mistaken for numbered lists, and a link-furniture flag initially
misnamed as category/heading-only. The final classifier corrects both and has
10 passing tests. `report.md` explains boundaries, `flags.jsonl` records every
row, and `receipt.json` binds manual evidence and unchanged source/export pins.

## Applied Exact 44-ID Subset

**Supersedes the proposal-only state above:** the user explicitly authorized
only the 44 manually reviewed reordering IDs. Applied with
`dfm12/hr_transform_subset.py`, using immutable proposal/review hashes and no
classifier rerun. Other Croatian tasks and meaningful lists remain unchanged.

Result: **30,942 reordering rows / 39,505,426 actual tokens**; exactly 44 rows /
22,456 tokens removed. Retained records are an ordered, byte-identical subset.
Only this artifact was retokenized, using 16 CPU workers with zero dropped rows.

- Package: `exports_dfm13/hr-reordering-manual44-subset-20261003-v1`.
- Same HF repo: `schneiderkamplab/dfm13-wave4-wikipedia-hr-paragraph-reordering`.
- New revision: `116c771f15f417d3ac0e06ac8d8867bb7fbc04b1`.
- Data SHA256: `6bef12c4023d4881ee383d4f6dc75a5588986444af319654d5218dede3197fec`.
- Completion SHA256: `1e69fc3bfd7873d9e4b14ce06a10b7a1eb9f7cac7b27286e6a0235a34f6cb871`.
- New arrays: `data/dfm13/tokenized_hr_manual44_subsets/dfm13_wave4_wikipedia_hr_paragraph_reordering/4fd7064b42f0e494631ecf5c7dadbee0fc38365034bbd585f3e05f644aa8fd32/tokens`.

All 13 uploaded attachments were downloaded at the new commit and hash-verified.
The package preserves parent publication/source attribution and review evidence,
with hash-bound exclusions and subset receipt. Old export, receipt, HF history
and arrays are preserved. New publication receipts replace registry pointers, not
historical files. The old finalizer is blocked only for HR paragraph reordering;
the other three Croatian publication paths are unaffected.

The established FA uploader, token verifier and locked registry promotion are
reused through an explicit scoped backend; FA defaults remain unchanged.
Assembler dispatch `hr_reordering_manual44_v1` checks the exact manual-ID subset
and all ordinary source/array/native-render contracts before integration.
95 focused tests pass, including FA regressions and HR task-specific guards.

`data/dfm13/verified-wave-additions-20261003-v4` is now **historical, before this
HR change**, not a current filtered assembly. Its snapshot, hashes and links were
not rewritten. All **215 historical Croatian arrays** still match frozen v4
hashes, and all three other Croatian entries/data are unchanged. Current changed-
entry verification is in the package's `assembly-verification.json`.
Poincare integration handoff:
`docs/reports/hr-manual44-assembly-handoff-20261003.md`.
`docs/reports/hr-manual44-transition-20261003/receipt.json` binds historical and
current evidence (SHA256
`22e7c28e3e57182c35537c7bcbf02e525cdfe185c4626955af1fc80c10adca5f`).
A new full assembly must use a fresh output root; no sampling or GPU work was
performed.

## Evidence

`docs/reports/croatian-wiki-transforms-independent16-20261003/report.md` has the
full findings and per-case table. `overview.md` contains all selected prompts
and answers; `evidence.json` also contains complete original source articles.
`findings.json` is the individually written manual ledger; `review.json` binds
each judgment to candidate/record/window/source hashes, ordinal and HF revision.
`mechanical-checks.json` records all replay results. `receipt.json` hashes report
artifacts and rechecks unchanged source/publication pins. `replay.py` and
`finalize.py` make evidence extraction and receipt binding reproducible; the
manual judgments are not computed by a classifier.
