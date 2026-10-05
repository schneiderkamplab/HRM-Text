# Croatian transform structural census: diagnostic only

Final version: **v4**. Scanned every row in all four pinned accepted Croatian
exports: **203,291 rows**, including **30,986 paragraph-reordering rows**.
No filtering, publication, registry, tokenization, worker or GPU changes.

## Exact counts, with their limits

These are exact counts of the documented Croatian structural detector, **not**
exact corpus-wide semantic-quality or meaningful-paragraph counts. The lexicon
is intentionally incomplete. A positive prose detection is not factual approval;
an unknown block is not bad content. Rows with two detected prose blocks may
still contain metadata, grammatical mistakes or factual problems.

| Task | Rows | At least 2 detected prose blocks | Below 2, furniture-only remainder | Below 2, unresolved/list remainder |
| --- | ---: | ---: | ---: | ---: |
| Denoising | 67,456 | 47,279 | 355 | 19,822 |
| Paragraph reordering | 30,986 | 22,810 | **44** | **8,132** |
| Prefix continuation | 66,422 | 46,520 | 348 | 19,554 |
| Span filling | 38,427 | 27,065 | 221 | 11,141 |

The two-prose requirement is relevant to **paragraph reordering only**. The
other task counts are diagnostics, not proposed rejects. A one-paragraph
denoising or span example is ordinarily legitimate.

Reordering detector histogram: **2,567 zero**, **5,609 one**, **6,393 two**, and
**16,417 three-or-more** detected prose blocks. The 8,176 below-two rows split
into 44 narrow candidates and 8,132 unresolved/list cases. **Do not reject all
8,176.** Detected meaningful-list blocks occur in 2,390 reordering windows
(overlaps the other columns), and 5,321/5,278/2,800 denoising/continuation/span
windows. Lists are explicitly protected from the narrow furniture-only bucket.

Zero rows satisfy the strict recognized category-plus-heading-only flag. One
denoising row is recognized reference furniture plus a category: an external-link
collection, not literally category-only. These zeros are lexicon-limited counts,
not proof that no category-only windows exist in the corpus.

## Croatian-specific method

`scripts/diagnose_hr_transform_structure.py` defines exact Croatian heading
labels, a limited Croatian category-tail recognizer, finite-verb/sentence cues,
list/inventory labels and conservative short link/citation recognition. It does
not import or reuse Persian rules. Category recognition is limited to the final
block. Unknown bibliography, taxon inventories and short noun lines remain
unresolved; narrative reference annotations are not silently treated as furniture.

The counted units are the actual blank-line-delimited **shuffled blocks**. A
single block can contain several sentences, single newlines or a heading plus
prose; they do not become independently reorderable paragraphs. No sentence
splitting is used to inflate paragraph counts. Short complete prose such as
`Rod je opisan 1948.` remains eligible.

Exploratory v1-v3 outputs are preserved but superseded. Inspection exposed year-
and Croatian day/month-led narrative being mistaken for numbered-list entries;
v4 retains the corrected date exceptions. It also separates reference-furniture
from literal category/heading-only flags. Ten focused tests pass, including these
regressions. Only v4 counts and pins are authoritative for this recommendation.

## All 44 narrow candidates manually read

After the census, every one of the 44 narrow candidates was read, not merely the
first few examples. They all have **one substantive shuffled content unit** and
otherwise recognized source headings, empty section headings, citation/link
furniture or categories. This confirms a bounded 44-row structural issue, not
classifier accuracy over the remainder of the population. All 44 additionally
replay their original pinned parquet document identity, window, ID and messages.

Examples (full IDs and records in `reviewed44.jsonl`):

- **Metoksetamin**, `9ab167fb59faad526a4d978d8f0aefd230bbd43642f56ba655a01e5eb75d9200`:
  one description block, `Izvori`, `Psihotropne tvari`. A three-block shuffle is
  mechanically valid but cannot exercise ordering two meaningful prose units.
- **Publije Kornelije Dolabella**, `ffe23c44d49a395e9c9dce7ff2469c5cff50f43118d9511816f3a9cd1981123e`:
  long Roman-road paragraph, sources heading and `Životopisi, Stari Rim` category.
  Paragraph length and many sentences do not create additional shuffled units.
- **Fountain Estate**, `d37ea0b57d887edcdc333881c4dc7dce34e636dfa741539a1aa364b563dad19d`:
  neighborhood prose followed only by sources and settlement category.
- **Rovanjska**, `adae9b10585c0c99eefdd2aeb0efc25a52b693599521662ede13b82e978ca88e`:
  church and monument descriptions share one block with single newlines. They
  are not independently shuffled; sources/category are the remaining units.
- **Ivan Zak**, `1e0319f216477d458d1e3a0a866b03f3c3afb4f65cebb5aed1f00c272de850d6`:
  several trivia statements occupy one content block, plus links/categories.
  The verdict is about actual task units, not claiming the block is one natural
  linguistic paragraph. This distinction is retained in the individual notes.

The prior Striga case is among these 44. Source factual assertions in chemistry,
history and regulations were not independently certified; the recommendation is
based on task structure alone. Original paragraphs may still be useful in the
other three tasks, which are not proposed for removal.

## Representative unresolved and control cases

Seventeen additional hash-bound cases were individually inspected. Four per
selected diagnostic bucket are chosen by the smallest deterministic SHA256 ranks;
one is the sole recognized all-furniture denoising example. `examples.json`
contains full windows/messages; `representative-review-bound.json` records each
judgment with hashes. These are purposive diagnostic examples, not a prevalence
sample and not a full semantic review of the 8,132 unresolved rows.

- **Klickitat** (`d4883418...`) has one ethnographic block plus links/categories,
  but those labels are outside the narrow lexicon. Genuine structural problems
  therefore remain in the unresolved bucket; 44 is not a total failure count.
- **Donja Dubica** (`525bef45...`) has a village sentence, an empty population
  heading, club listing and references. It also shows concatenated bibliography
  and category text. Useful short inventory content warrants separate judgment.
- **German softball championship** (`8ef8bb45...`) has a meaningful chronological
  winner list; **E-number inventory** (`8861ab9d...`) has numeric ordering cues.
  Neither should be blanket-labelled category rubbish because prose is absent.
- **Joe's Garage** (`376e3d59...`) has album sides/acts, tracks and personnel;
  **Alyxia** (`ef0a22a4...`) has species and synonym inventories. These show why
  list-aware review must remain separate from furniture-only exclusion.
- **Rab**, **HKD Ljuba**, **Sovke** and **Evanđelje po Tomi** contain several real
  narrative paragraphs despite mixed headings/categories. Mixed metadata alone
  does not establish a useless task.
- Denoising controls **Renzo Agasso**, **Clupea**, **60 BC**, and the **2012 baseball
  league** contain bibliography, taxonomy, events or scores. Preserve meaningful
  lists; source typos, empty score slots or suspect chronology are separate issues.
- **Jadranka Brnčić**, `d3ad7837743664c6656bafddbfc5285261981b327ab9458b05408011189f0740`,
  is link-only reference furniture plus a writer category. It is not part of the
  reordering proposal, and this single case does not justify an all-task filter.

## Narrow recommendation

Recommend a **separately authorized 44-ID paragraph-reordering-only exclusion**,
bound to this publication hash and manually reviewed ledger. It would retain
**30,942 reordering rows** and leave the other **172,305 rows** unchanged, for
**203,247 total**. `proposed-reordering-ids.json` is a proposal, not an applied
filter or new publication receipt.

Do not auto-remove the remaining 8,132 low-detection rows, do not generalize a
two-paragraph threshold to the other tasks, and do not infer population factual
quality from either the prior sixteen examples or this census. Expanding coverage
would require additional Croatian-specific calibration and manually supported
categories, not an enlarged regex justified by convenience.

## Reproduction and provenance

```bash
python -m scripts.diagnose_hr_transform_structure --output <fresh-diagnostic-root>
python -m pytest -q tests/test_hr_transform_structure.py
```

`report.json` pins the four exports/HF revisions, classifier and census artifacts.
`flags.jsonl` includes every accepted row's ID, canonical record hash, window hash
and block decisions. `manual44.json` contains the handwritten per-title review;
`reviewed44.jsonl` binds it to full unchanged records and source replay.
`finalize.py` checks these bindings and writes `receipt.json`, rechecking original
input hashes. No GPU calls, remote model calls, filtering, uploads or registry
changes are part of this diagnostic.
