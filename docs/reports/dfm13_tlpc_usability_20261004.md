# TLPC authenticated usability check, 2026-10-04

## Access and bounded evidence

Actual payload access succeeds using existing stored HF credentials. No token
was printed or persisted. This supersedes the earlier HTTP403 access deferral,
not the source-quality or publication gates. No GPU calls or production changes.

Receipt: `data/dfm13/wave4/tlpc-usability-1791109046036714235/access.json`.
Sample pins: `sample-manifest.json` in the same directory. Revision:
`e2fea1d2c4c0828a218c79d6806fe98f821ad8ce`.
The original 15,888-byte access probe matches SHA256
`ac98d917f26012bd2ebab17e7b73b75a44f4695a1814b6e70fdd956e8b6f0cbf`.

Six downloaded gzip shards total **211,178 compressed bytes, 127 records**.
All six hashes match the existing upstream LFS inventory. Selection is purposive:
shards nearest 40KB within 15-120KB from five sites, plus the original access
probe. This is not a random quality estimate or a representative corpus sample.

| Shard | Records | Observed label |
|---|---:|---|
| irna/2006-08.jsonl.gz | 51 | Formal |
| isna/2001-02.jsonl.gz | 18 | Formal |
| mehrnews/2003-08.jsonl.gz | 36 | Formal |
| zoomit/2012-11.jsonl.gz | 3 | Formal |
| tebyan (exact path in manifest) | 15 | Formal |
| wikiravan/2024-03.jsonl.gz | 4 | Unk |

All rows parsed as JSON. NFKC plus whitespace-normalized joined content bodies
yield **122 unique bodies**, five repeated occurrences (three IRNA, two Wikiravan).
This is sample-local exact dedup only, not inherited-corpus dedup or near-dedup.

## Assessment

Assistant spot inspection of selected text, not native-speaker certification:

- ISNA exhibits coherent Persian reporting with dates, attribution and numerical
  details, useful for source-conditioned extraction and summary tasks.
- IRNA includes title/dateline repetition, standalone hash separators and agency
  codes. Formal labels do not imply clean paragraph boundaries or neutral claims.
- Mehrnews includes strongly attributed political reporting. Preserve attribution
  and date; do not transform a source's claims into timeless verified facts.
- Zoomit has substantive Persian technology reviews, including a Nexus7 review,
  but copy-link navigation appears within the body. Prices/specifications are
  historical, not current product advice. Heading/list structure matters.
- Tebyan and Wikiravan include health/psychology advice and promotional or internal
  links. Wikiravan combines advice and a user question within content, and its
  metadata says `Unk`. Exclude these from the initial factual-gold slice.
- `ilink` elements can contain substantive prose, not just navigation. Dropping
  every link element loses content; joining every element imports boilerplate.

The existing `wave4_persian_local.document` Formal filter would exclude the four
Wikiravan rows but not automatically remove the other problems. Its flattened
paragraph interpretation needs source-specific validation before production.
The prior 64-shard plan is diversity-balanced, not quality-curated; cache
downloads here do not complete that plan's expected local download directory.

## Recommendation and limits

**Proceed with a small curated TLPC source-text integration, not full-corpus or
raw-continuation admission.** Start with low-risk informative ISNA/Zoomit articles
after navigation cleanup and date-aware, full-source task construction; manually
check a broader date/category slice before scaling. Keep original element types,
URLs, dates, revision, compressed-file hash and document fingerprints. Use the
existing four-transform route with independent whole-source fidelity checks.
Do not treat scraped QA answers, medical advice or source summaries as gold.

TLPC adds native long-form source material rather than more translated/template
instruction instances. Existing FarsInstruct pn_sum/wiki_sum fidelity holds are
not cleared by access to TLPC. PersianQA and other existing instruction sources
remain distinct; incremental unique content has **not** been measured.

No full DFM11/DFM12/DFM13 text or evaluation inventory was compared in this bounded
check. News syndication, reused articles and benchmark passages can overlap even
without Wikipedia shards. Before admission run disk-backed normalized body and
conversation fingerprints against inherited sources and full held-out passages,
plus near-duplicate/source-URL checks. Prior source permission is not a blanket
held-out/evaluation exception. No clean-overlap claim is made.

## License and primary evidence

The [pinned dataset card](https://huggingface.co/datasets/Targoman/TLPC/blob/e2fea1d2c4c0828a218c79d6806fe98f821ad8ce/README.md)
lists CC-BY-NC-SA-4.0 and describes a broad Persian web corpus, not an instruction
train/eval split. Preserve that license and source attribution; project owner
approval already permits this source and is not a replacement upstream license.
The scraper's LGPL software license is separate from the corpus license.

- [Repository/files and access conditions](https://huggingface.co/datasets/Targoman/TLPC)
- [Pinned successful payload](https://huggingface.co/datasets/Targoman/TLPC/resolve/e2fea1d2c4c0828a218c79d6806fe98f821ad8ce/wikiravan/2024-03.jsonl.gz)
- [Primary scraper](https://github.com/Targoman/PersianWebScraper)

No full41B download, tokenizer run, training admission, upload or GPU work.
