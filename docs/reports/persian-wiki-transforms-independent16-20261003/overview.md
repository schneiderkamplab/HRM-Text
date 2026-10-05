# Persian Wikipedia Transform Review: 16 Examples

2026-10-03. CPU/read-only inspection; four accepted examples per task from the
four current uploaded Persian Wikipedia transform entries. No model calls,
GPU actions, data/code/registry/eligibility changes. Generated review artifacts
only. Sample selected before semantic reading: published row ordinals
`floor((N-1)*i/3)`, i=0..3 for each task. This is deterministic spread, not random
sampling and not a population quality-rate estimate.

## Result

**Source identity, source-window replay and transform replay pass for all 16.**
No wrong article join, missing shuffled block, invented paragraph, changed target,
or generative assistant-repair hallucination was found. All sampled rows are
original `accepted`, not accepted repairs.

The material concerns are upstream/window/task quality, which exact replay alone
does not validate:

- All four reordering cases contain headings/category metadata as shuffled units.
  Cases 4 and 5 are especially degenerate: empty standalone headings have no
  semantic payload to determine a unique order. Cases 6 and 7 retain real ordering
  cues between two prose blocks, so they are weak tasks, not wholly unsolvable.
- Prefix cases 8 and 11 expose only metadata, without the person's name, then
  supervise detailed category inventories. Case 9 also targets category tail.
  Case 10 has a meaningful prose/list continuation before its metadata tail.
- Denoising case 3 retains an empty birth-date template and duplicated club in
  the supposedly corrected target. Reordering case 6 retains another empty
  birth-date template. These are inherited source defects, not corruption bugs.
- Span case 13 has a visible source chronology contradiction: July 2015 damage,
  months of repairs, then an April 2015 resumption. The exact extracted span is
  still correct. Case 14 has suspect literal Persian wording; this is explicitly
  a native-review uncertainty, not an independently proven biographical error.

No blanket pass/hold rate is assigned. The report does not declare the full
corpus unfit, clear existing holds, or demand unique answers for language modeling.
It supports filtering page furniture and checking source cleanliness before
treating exact-match audit success as evidence of useful task construction.

## Task Fidelity and Solvability

| Task | Mechanical result in these four samples | Semantic reading |
| --- | --- | --- |
| Denoising | Exact original targets; 2, 6, 7, 12 alphabetic deletions restored; no case changes | Mostly recoverable spelling; metadata-heavy, one visibly unclean target |
| Paragraph reordering | Same complete original double-newline blocks, nonidentity permutations, exact original targets | Page furniture inflated paragraph counts; two cases retain useful prose ordering cues |
| Prefix continuation | Exact source suffix after whitespace trimming | Open-ended by design; category-only windows are a separate quality concern |
| Span filling | One gap; exact stripped source spans, lengths 54/352/82/189 characters | Plausible cloze, often knowledge-dependent; source flaws survive |

All four Persian instruction templates are comprehensible and appropriate in
register for direct task commands. `بندها` is understandable as paragraphs;
the problem is what the generator counts as a paragraph, not that instruction's
language. Fine stylistic preference is not treated as an error. Persian fluency
judgments here are limited; obvious structural/template defects are higher
confidence than nuanced translation-quality judgments.

Source fidelity is to the pinned historical article, not a certification of
every fact in it. Prefix/cloze tasks normally have multiple plausible outputs;
nonuniqueness alone is not a construction bug. Conversely, the model cannot see
the source title or full `audit_context.original` unless included in messages:
`scripts/tokenize_chat_template.py` renders messages, not audit metadata. Judges
checking against that hidden original can verify the target without establishing
that the learner-facing task is informative or recoverable.

## Source and Code Binding

Upstream: `wikimedia/wikipedia`, revision
`b04c8d1ceb2f5cd4588862100d08de323dccfbaa`, config `20231101.fa`.
All referenced local parquet file bytes match the preparation receipt.
Article ID/title/URL, file and row match the selected source records.
`window(source_text, window_seed, max_chars=4500)` reproduces each exact
`audit_context.original`; `transform(..., seed=20261003)` reproduces each ID and
both messages. Separate content checks validate deletions, permutations and
prefix/span boundaries. Source paragraph stripping/joining and target edge
whitespace normalization are intentional; do not describe spans as raw-byte
identity across removed boundary whitespace.

| Published task | Rows in pinned publication | HF data revision |
| --- | ---: | --- |
| denoising | 73,802 | 64bf4b8aae08c303734d162e9d0fd736f85914ac |
| paragraph-reordering | 31,490 | 2c931642f524e79942e41b59cb71d6624bba7a60 |
| prefix-continuation | 110,813 | 3d2f4397565d8bd12e329b01e3900fb1de5cb692 |
| span-filling | 25,937 | aeaa6b115e61ecda16a2df4add70b040945c16e8 |

Repos are `schneiderkamplab/dfm13-wave4-wikipedia-fa-<task>`. These are the
registry-pinned publications, not an assertion that remote main was refreshed
during this CPU-only review. Every local published file hash was checked.

Evidence SHA256:
`093d792842302c3dde3ba832954bd1adac786dffe9101d6095b9d1b1b3d45cae`.
`evidence.json` retains full source articles, full published records, source file
pins, publication/revision metadata and code hashes. `mechanical-checks.json`
contains the separate construction checks. `review.json` joins manual findings
with exact candidate/record/window hashes. `receipt.json` binds all report files.

## Per-Case Full Input and Target

