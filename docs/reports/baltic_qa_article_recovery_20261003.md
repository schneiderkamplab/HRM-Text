# Baltic QA source-article recovery: bounded read-only check

## Finding

No direct article-ID/URL join or auxiliary article files were found in either
original HF repository at the pinned revision (also the current main revision).
Article recovery is possible as **candidate evidence retrieval**, especially for
LV, but exact generation-source recovery is not established. Original QA remains
generated evidence, never gold. No holds, consumers, registry entries or source
data were changed; no paid search or model calls occurred.

## Original Repository Metadata

| Repository / pinned main | Complete file inventory at this revision |
|---|---|
| `neurotechnology/lithuanian-qa-v1` / `a2c5072aa6a01ed44660fafd70b59214563c73f6` | `.gitattributes` (2,307 B), `README.md` (7,277 B), `lithuanian_qa.json` (4,599,403 B) |
| `martinsu/latvian-wikipedia-qa-gemma3` / `ed202b8334890985f0879eeb48fff84565d890aa` | `.gitattributes` (2,461 B), `README.md` (9,808 B), `data/train-00000-of-00001.parquet` (162,584,473 B) |

HF tree/ref metadata and cards were inspected; dataset payloads were not downloaded.
Only main branches were observed. Deleted files in historical commits and other
repositories were not exhaustively searched.

The [LT card](https://huggingface.co/datasets/neurotechnology/lithuanian-qa-v1/blob/a2c5072aa6a01ed44660fafd70b59214563c73f6/README.md)
says the material is mainly generated from Lithuanian Wikipedia, without an
article map, dump date or revision IDs. Inspecting all keys in the already-local
4.6 MB JSON found only `question` and `answer`. It is not safe to assume every
question came from Wikipedia. An author-provided original article mapping and
generation snapshot would be the lowest-computation exact-recovery route, but
availability/response time is unknown; no contact was made.

The [LV card](https://huggingface.co/datasets/martinsu/latvian-wikipedia-qa-gemma3/blob/ed202b8334890985f0879eeb48fff84565d890aa/README.md)
identifies `lvwiki-20241020-pages-articles-multistream.xml.bz2` and describes one
conversation per article. Its generation prompt requests the topic title in the
first question. The already-local Parquet footer confirms 118,507 rows and only
`messages` containing `content`/`role`, with no hidden article column. Thus a title
can often be inferred from text, but the title-to-QA association was not exported.

## Local Evidence Already Available

`data/dfm13/baltic/local-sources.json` points to:

| Local article JSONL | Rows recorded in manifest | Actual file bytes |
|---|---:|---:|
| `data/dfm13/baltic/documents/Wikipedia_lt.jsonl` | 123,850 | 315,915,100 |
| `data/dfm13/baltic/documents/Wikipedia_lv.jsonl` | 76,621 | 214,415,594 |

Rows contain full text, title, URL, `source_document_id` and source filename.
The source files are `20231101.lt` / `20231101.lv`: the LV corpus is older than
the declared QA generation dump. These are filtered article inventories, not
complete raw dumps. Existing manifest flags say DaLA source holdouts are included;
using a document as verification evidence does not authorize adding it to training.

Bounded example: the first three LV QA conversations mention Edi Rama, Liverpool
and Latvijas Banka. One local title scan found `Edi Rama` (`lv:12289`), `Liverpūle`
(`lv:12292`) and `Latvijas Banka` (`lv:12297`), reading 2,606 rows / 13,615,053 bytes.
All have Wikipedia URLs and older snapshot text. This is three candidate topic
matches, not certified generation-source identity, factual correctness or a corpus
recovery-rate estimate. Nearby page IDs or row order are not alignment proof.

## Possibility and Cost

- Cheapest useful next step: a streaming local title/redirect-aware candidate index.
  The two existing files total about 530 MB; one sequential CPU pass needs no
  network transfer. Index size/runtime have not been measured. Handle inflection,
  ambiguity and absent articles explicitly; then compare full questions/claims to
  candidate text. Reject unresolved pairing rather than force a match.
- Exact LV snapshot recovery requires locating the declared October 2024 dump or
  the author's generation inputs, then mapping topics and preserving revision/text
  hashes. Historical dump availability and size were not verified here. This is
  outside the bounded lookup, and could require a substantial download.
- Targeted official Wikipedia revision retrieval could improve individual matches
  without downloading a dump, but current pages are not the October 2024 source.
  Historical revision selection, redirects and generation-time extraction remain
  additional uncertainty. No such requests were made in this check.
- LT is less determinate because the original source date/map is absent. Local
  Wikipedia can support or contradict claims, but cannot by itself prove which
  article/version generated a question or cover non-Wikipedia questions.

Recommendation: use local title candidates for a bounded source-grounding sample
first; retain separate `candidate_article`, `verified_topic_match` and
`exact_generation_source` states. Do not clear holds on topic matching or agreement
with the original synthetic QA.
