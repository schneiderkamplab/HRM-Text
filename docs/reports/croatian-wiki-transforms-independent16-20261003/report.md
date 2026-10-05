# Croatian Wikipedia transforms: independent 16-case review

## Scope and conclusion

Read-only CPU review of four accepted examples per task, deterministic ordinals
`floor((N-1)*i/3)` for i=0..3. The four exports contain 67,456 denoising,
30,986 reordering, 66,422 continuation and 38,427 span examples (203,291 total).
Those are publication sizes, **not semantically reviewed population counts**.
All 16 selected examples are accepted originals, not repaired candidates.

**The metadata-as-paragraphs issue exists in Croatian.** All four sampled
reordering examples independently shuffle non-prose blocks. One has only one
real prose paragraph; the other three have four, six and four real prose
paragraphs and remain meaningful ordering exercises despite metadata noise.
The stronger Persian category-only pattern is **not demonstrated here**: zero
of these 16 windows is category-only or heading-only. One denoising window is a
discography/list with useful titles and dates, not a mere category list.

Do not infer population prevalence or blanket-hold the four sources. No Persian
regex or automatic semantic grading was used. No data, registry, publisher,
tokenized arrays, workers or GPU state were changed.

## Mechanical evidence

Every source parquet hash and exported data hash is verified. The published
provenance selects the exact source row, ID, URL and title. Replaying
`window(source_text, window_seed, max_chars=4500)` and the Croatian transform with
seed 20261003 reproduces all 16 windows, candidate IDs and user/assistant
messages exactly. Source trailing block whitespace is intentionally stripped by
the original window function; the complete source article is retained in evidence.

- Denoising restores 8, 23, 4 and 1 deleted characters respectively, plus case
  changes. Every target is the source window, and every input is truly changed.
- Reordering preserves every distinct block, with nonidentity permutations
  `[2,4,3,1]`, `[1,3,6,5,4,2]`, `[3,6,8,9,4,1,7,10,2,5]`, `[7,4,6,5,2,3,1]`.
- All four continuations are the exact stripped source suffix.
- All four span targets match the original seeded transform exactly. They each
  contain one input gap; whitespace-normalized reinsertion also matches.

Replay is source-fidelity evidence, not proof of factual truth or unique
recoverability. The judge's `audit_context.original` is not part of the learner
prompt. Factual-looking span details and exact continuation wording can be
underdetermined from the learner-visible context.

## Definite findings

### One paragraph task is really wiki-layout ordering

Case 4, **Alberto Ognjan Striga**, ID
`00017d4187f1436bb6751cce9d5ed80a1cef660b4cb3692615f02e6378b89b4a`,
contains just one prose paragraph. The other three blocks are `Izvori`, an
external-link citation, and three category labels. The permutation is valid,
but calling all four blocks paragraphs does not create a multi-paragraph task.
This is the clearest sampled candidate for a future narrow structural exclusion.

The same example has a **source-internal birth-month contradiction**: biography
`30. travnja g. 1821.` versus citation title `30. svibnja 1821.` (April/May).
Both survive exactly from the original article. This review does not determine
which date is correct; it does prove the incompatibility inside the retained text.

### Mixed metadata does not mean the whole example is useless

Cases 5-7 reorder real prose with semantic cues as well as headings/categories.
Case 7 uses `Dakle` and `također`, giving genuine discourse information. Case 6's
short marriage sentence is still prose and must not be rejected merely for its
length. Several coherent full orders may exist; exact original order is not
logically unique. These observations do not justify dropping the three examples.

Case 2, **Dani Marsan**, ID
`aa641953b412a31480c1263e5af8e649599bceb6fbc8a7b0aff626c5f81194a8`,
is all list/title material: song names, a dated discography, a television
appearance, references and categories. It has zero narrative prose, but
correction of damaged album/person names remains a legitimate denoising task.
This is a negative control against applying a universal zero-prose filter.

Case 9, **Kardisa**, ID
`55db45e0af3a65b435bc7b76c9b0b4d6351d53b487f8ffaac92ee175a11ebc69`,
retains `Rast stanovništva Kardise posljednjih decenija` with no population data,
immediately followed by external links. This is an actual empty-section artifact,
but history and transport prose remain. Cases 8-11 all have substantive
continuation content, not category-only targets.

### Source language noise is not transformation hallucination

Case 1 retains the malformed source phrase `na u kino`; case 7 retains
`psotignuta`; case 13 retains `kada su donosi odluka`; case 15 retains
`Sjevernii Kap`. These support a limited source-cleanliness concern, not a
claim that the transformation invented them. The broad denoising instruction
`Ispravi pogreške u tekstu` can imply fixing original errors too, while its
target only restores artificial damage. A more precise future instruction could
state that artificial corruption is to be restored, but nothing was changed.

Croatian instructions are comprehensible and task-aligned. Finer grammatical,
regional and stylistic judgments remain lower-confidence; variant forms are not
automatically errors. Historical, botanical, chemical, legal and film-canon claims
are not externally verified by this bounded structural review.

Case 11's full Marty McFly source has raw infobox fields, including empty
assignments, but **they are outside the selected window**. Do not attribute
whole-article defects to an accepted window that does not contain them.

## Per-case record

Full IDs, ordinals, all user/assistant text, full source articles and row hashes
are in `evidence.json`; `overview.md` is the readable prompt/response view.
`findings.json` is the individually written semantic ledger, not regex output.

| Case | Task | Article | Manual result |
| --- | --- | --- | --- |
| 0 | Denoising | Amphineurion | Useful prose plus long taxonomic list/metadata; exact restoration |
| 1 | Denoising | Taksist | Useful plot prose; inherited malformed grammar remains |
| 2 | Denoising | Dani Marsan | List-only discography, not category-only; borderline but useful |
| 3 | Denoising | Flubromazolam | Real prose; source legal/chemical facts not certified |
| 4 | Reordering | Alberto Ognjan Striga | One prose block only; definite task mismatch and internal date conflict |
| 5 | Reordering | Marica Mikrut | Four prose blocks plus metadata; inherited typos |
| 6 | Reordering | Guillaume Bigourdan | Six prose blocks plus metadata; short marriage sentence is prose |
| 7 | Reordering | Norbert Elias | Four prose blocks, real discourse cues; inherited typo |
| 8 | Continuation | Edmund Burke | Substantive prose/title completion plus bibliography tail |
| 9 | Continuation | Kardisa | History/transport prose plus an empty population section |
| 10 | Continuation | Byzantine-Bulgarian wars | Real prose completion plus a long category tail |
| 11 | Continuation | Marty McFly | Real prose/quotation; source noise; infobox excluded from window |
| 12 | Span | Xi'an | Exact prose span; detailed content not forced by context |
| 13 | Span | T-26 | Exact cross-paragraph span; inherited grammar and specific number |
| 14 | Span | Tudoric-Gemo | Exact genealogy span; source repetition and specific dates |
| 15 | Span | Konop-biljka | Exact taxonomic phrase; inherited spelling noise |

## Bounded policy proposal, not an applied filter

1. Run a Croatian-specific **diagnostic census**, not the Persian classifier.
   Count category-only/heading-only windows and reordering windows with fewer
   than two unambiguously real prose blocks. Report uncertainty separately.
2. Use Croatian heading/category evidence and manual calibration; preserve lists
   such as discographies and taxonomic synonyms as counterexamples. Do not
   assume every capitalized short line is a heading, or every short sentence
   is non-prose. Confirm any proposed exclusion set before publication changes.
3. Keep structural checks window-specific. Empty source infobox fields outside
   the selected window are not candidate defects. Mixed metadata and prose is
   a quality signal, not an automatic whole-row rejection.
4. The present evidence nominates **one of the four sampled reordering cases**
   for a narrow exclusion, not an estimated population count. There is no
   basis here for an automatic four-task filter, a source-wide hold or a numeric
   all-source failure rate. Do not extend the Persian 7,086-row decision to HR.
