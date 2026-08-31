---
type: Dataset Survey
title: Danish Research Data Landscape
description: Ranked Danish NLP, linguistics, historical-text, archive, and digital-humanities sources beyond the project's existing Hub scan.
tags: [danish, datasets, linguistics, history, digital-humanities, archives, evaluation]
status: draft
last_updated: 2026-08-30
confidence: medium
sources:
  - id: dynaword
    resource: https://huggingface.co/datasets/danish-foundation-models/danish-dynaword
    title: Danish DynaWord
  - id: chc-hf
    resource: https://huggingface.co/chcaa/datasets
    title: Center for Humanities Computing Aarhus datasets
  - id: sprogteknologi
    resource: https://sprogteknologi.dk/dataset
    title: Danish language-technology data catalogue
  - id: clarin-dk
    resource: https://info.clarin.dk/en/the-clarin-dk-infrastructure/clarin-dk-datacenter/
    title: CLARIN-DK Data Centre
  - id: awesome-danish
    resource: https://github.com/fnielsen/awesome-danish
    title: Awesome Danish language resources
  - id: danlp
    resource: https://github.com/alexandrainst/danlp/blob/master/docs/docs/datasets.md
    title: DaNLP public dataset inventory
---
# Danish Research Data Landscape

## Scope

This survey broadens the 2026-08-30 Hugging Face namespace scan beyond model
builders. It covers linguists, lexicographers, historians, archives, libraries,
literary scholars, and digital-humanities groups. It is a discovery and triage
document, not an admission decision. The operationally approved Hub additions
remain in the [DFM10 Danish Hub Gap Integration](/pages/dfm10-danish-hf-gap-integration-plan.md).

The central finding is that many large humanities corpora are already present
in DynaWord. Their incremental value is usually the structure discarded by a
flat text conversion: scholarly commentary, alignments, corrected OCR,
historical metadata, linguistic labels, and paired varieties. Do not add a
second raw-text route without exact and near-duplicate audits.

## Organizations and researchers to monitor

| Organization or namespace | Discipline | High-value resources | Project interpretation |
| --- | --- | --- | --- |
| `chcaa` and `centre-for-humanities-computing` | Digital humanities, computational literary studies, NLP | MeMo, ENO enrichment, Danish book ads, historical POS, literary sentiment, social-norm alignment | Most active source of newly structured Danish humanities data. Audit raw-text overlap with DynaWord; prefer labels and alignments. |
| MiMe-MeMo, University of Copenhagen | Literary history and corpus philology | `MiMe-MeMo/Corpus-v1.1` | Already represented by DynaWord `memo`; retain as canonical provenance and corrected-structure source, not a second raw route. |
| History Lab/CALDISS, Aalborg University; Johan Heinsen | History and historical newspapers | `JohanHeinsen/ENO` | Already represented by DynaWord `enevaeldens_nyheder`; enriched article structure may support derived tasks. |
| Royal Danish Library, `kb-dk`, and LOAR | Cultural heritage, scholarly editions, letters, books | `SKS_tei`, ADL, Danmarks Breve, public-domain books | Danmarks Breve and ADL are already in DynaWord. The CC0 Kierkegaard scholarly TEI is a promising structured delta. |
| Rigsarkivet and `RA-Data-Science` | Archives and historical handwriting | `DiEm_HTR`, Folketing records | Folketing is already integrated separately. DiEm is a small new historical transcription resource. |
| Aarhus City Archives | Archives and handwritten municipal records | `historical-danish-handwriting` | Already in DynaWord; images matter only for a future multimodal model. |
| DSL, CST, Dansk Sprognævn; `dsldk`, `kuhumcst` | Lexicography, semantics, corpus linguistics | COR, COR.SEM, DanNet, FrameNet, sentiment, SemDaX | COR.SEM is the clearest unintegrated open semantic resource. Some extensions and corpora have restrictive licenses. |
| StrombergNLP / ITU researchers | NLP, dialects, fact checking, stance | Bornholmsk parallel, DanFEVER, DAST, Faroese-Danish | Use paired dialect data for training; reserve benchmark and social-media resources for evaluation or exclude. |
| Alexandra Institute, DDSC, DaNLP, Kenneth Enevoldsen | Danish NLP benchmarks and annotations | DaNE+, compounds, spontaneous-speech QA, retrieval queries | Current DFM10 already uses DaNE train. Consider annotation replacement or new held-out diagnostics, not duplicate text. |
| CoRal consortium | Speech, dialects, accents | `CoRal-project/coral-v3` | Conversational transcripts could add spoken Danish, subject to gated OpenRAIL terms. Read-aloud text alone is low-value for a text LLM. |
| CLARIN-DK | Research infrastructure | SemDaX, reference corpora, NOMCO, lexical resources | Public and academic-only resources coexist. Record the resource-level license; repository access does not imply redistribution rights. |
| H.C. Andersen Centre, SDU | Literary scholarship | Andersen modernization and related editions | The approved aligned modernization is already integrated. Other repositories still need explicit rights review. |

## Priority training candidates

## Decisions and task contracts (2026-08-30)

The following decisions refine the initial survey:

- Admit all 6,785 pairs from the official Bornholmsk train, validation, and
  test splits as training data in both directions. This produces 13,570
  directional examples. Preserve the original split as provenance, but do not
  present either original holdout as an evaluation after training on it.
- Admit DiEm as a historical-modernization source only after Gemma 4 31B
  target generation and an independent E4B row audit. The raw dataset has
  transcriptions but no modern-Danish targets.
- CoRal is out of scope for the current DFM line.
- COR.SEM, Danish book ads, and SKS TEI remain pilots pending conversion and
  overlap audits. Their concrete task contracts follow below.

### COR.SEM versus COR.SEM.EXT

COR.SEM is the CC0 formal semantic table. Each sense can expose a lemma,
part-of-speech and gender information, a textual and DanNet hypernym, related
words, synonyms, ontological types, subject/domain, systematic polysemy,
FrameNet frame, sentiment, restrictions, and curation metadata. For example,
the sense for `45-knallert` identifies `køretøj` as its hypernym, links related
vehicle words, gives `EU-knallert` as a synonym, and assigns an ontological
vehicle type.

COR.SEM.EXT is a separate supplementary resource containing a prose definition
for every COR.SEM sense and usage examples for most senses, primarily from Den
Danske Ordbog. It is licensed CC BY-NC-ND 4.0 rather than CC0. Do not copy,
paraphrase, or use its definitions/examples to generate DFM training targets
without explicit derivative-use permission. The shared `COR.EXT-id` is only a
linking identifier and does not transfer the extension's text into COR.SEM.

Useful COR.SEM-only task shapes include:

| Task | Example prompt | Gold target source |
| --- | --- | --- |
| Hypernym selection | `Hvilket overbegreb passer til "45-knallert": køretøj, person eller følelse?` | `overbegreb-tekst` |
| Synonym production | `Angiv et registreret synonym til "45-knallert".` | `synonym` |
| Semantic relation discrimination | `Hvilket ord er semantisk relateret til "68'er": ungdomsoprører, togkort eller mineral?` | `relaterede-ord`, with controlled negatives from unrelated senses |
| Ontological classification | `Er en "68'er" en person, en begivenhed eller et artefakt?` | `ontologisk-type` |
| Domain classification | `Hvilket emneområde tilhører dette ord ifølge COR.SEM?` | `emne` |
| Frame/sentiment classification | Given an eligible lemma, predict its registered frame or sentiment value | `frame` or `sentiment`; omit rows where the field is empty |
| Sense contrast | Present two senses of one lemma and ask which formal relations distinguish them | sense-numbered formal fields only; no invented prose definitions |

Generation must be deterministic from populated fields. Avoid questions that
have several valid answers unless every registered answer is accepted. Reserve
complete lemmas, not random senses, for a lemma-disjoint semantic evaluation.

### Danish book-ad task shapes

The source provides an advertisement excerpt plus title, cleaned title, author,
book/periodical category, subscription status, date, predicted subject, and
quality/confidence fields. Safe grounded tasks are:

| Task | Example prompt | Target and filter |
| --- | --- | --- |
| Title extraction | `Hvilken bogtitel annonceres i uddraget?` followed by the advertisement | `title`; require that a normalized title span is supported by the excerpt |
| Author extraction | `Hvem angives som forfatter til "10 Dages Læsning"?` plus excerpt | `full_name`/`author_original`; exclude `NO_AUTHOR` and unsupported names |
| Bibliographic JSON | `Udtræk titel, forfatter og publikationstype fra annoncen.` | Exact structured fields; emit `null` rather than guessing |
| Historical-title normalization | `Skriv titlen med datasettes normaliserede stavning.` | `clean_title`, but only where manually checked and genuinely different from `title` |
| Publication-type classification | `Er dette en bogannonce, tidsskriftsannonce eller subskriptionsannonce?` | `category` and `subscription` |
| Subject classification | Choose among a closed list of historical subject classes | `category_predicted`, only for manually checked or adequately confident labels |
| Grounded list extraction | `Nævn de tre værker i uddraget, som har en angivet pris.` | Derived deterministically only when title/price spans can be validated in source text |

Do not ask the model to infer the newspaper date from ad text when the date is
metadata only. OCR-heavy rows, automatic labels without adequate confidence,
and title/author fields unsupported by the excerpt must be filtered rather than
converted into false supervision.

### SKS TEI task shapes

The SKS TEI source separates Kierkegaard's authorial text from editorial
commentary and supplies machine-readable references, dates, and scholarly
notes. Useful tasks should preserve that distinction:

| Task | Example prompt | Target construction |
| --- | --- | --- |
| Grounded note explanation | Present a short author passage and its linked editorial note; ask what historical/reference information the note adds | Editorial note, lightly reformatted but not expanded by a teacher |
| Reference resolution | `Hvilken person, bog eller bibelpassage henviser markøren til?` | Linked TEI reference target |
| Date/context extraction | Ask for a work date or named entity explicitly encoded in TEI metadata | Exact metadata value |
| Author/editor distinction | Present two snippets and ask which is Kierkegaard's text and which is editorial commentary | TEI element provenance |
| Grounded modernization | `Omskriv dette korte historiske afsnit til nutidigt dansk uden at ændre argumentet.` | Teacher-generated target with an independent preservation audit; never use commentary as if it were a modernization |
| Passage-to-commentary QA | Ask a narrowly answerable question whose evidence is included in the supplied note | Deterministic answer extracted from the note, with passage and note both in context |

Hash authorial passages against DynaWord `adl`. Prefer unique commentary,
structure, and relations; do not add a second copy of overlapping Kierkegaard
prose merely because it is represented in TEI.

### Implemented Bornholmsk and DiEm paths

- `scripts/prepare_dfm10_bornholmsk_parallel.py` downloads the immutable
  upstream raw files, validates all three official split sizes, and emits both
  Bornholmsk-to-standard-Danish and standard-Danish-to-Bornholmsk tasks.
- `scripts/prepare_dfm10_diem_modernization.py` reads only ALTO, document ID,
  and page sequence columns from DiEm; it does not load images into the text
  pipeline. It extracts page-local windows with provenance.
- `scripts/finish_dfm10_diem_modernization.sh` performs Gemma 4 31B generation,
  independent E4B auditing, accepted-row building, and a fail-closed production
  gate. Generation coverage must reach 95%, every successful generation must
  be audited, and at least 70% must pass.
- The Bornholmsk conversion is materialized and tokenized: 13,570 directional
  rows produce 664,901 Gemma-native tokens per source pass and 6,649,010 tokens
  at repeat 10. DFM10 samples accepted DiEm at repeat 5. These settings are
  intentionally below web-scale volume and can be reconsidered after the DiEm
  acceptance count and first model deltas are available.
- Export staging registers `dfm10-bornholmsk-parallel` as a validated,
  one-shard, 13,570-row CC BY 4.0 package ready for upload. It registers
  `dfm10-diem-historical-modernization` separately as work in progress with
  1,259 prepared requests and a target of 881--1,259 accepted rows; no empty or
  unaudited DiEm package is presented as uploadable.

### Production status on 2026-08-30

All admitted sources from this research-source tranche are explicitly marked
`work_in_progress` in `exports_dfm10/manifest.json`; CoRal remains excluded.
The materialized packages and tokenized training slices are:

| Package | Training rows | Tokens/pass | Weighted tokens/epoch | Current state |
| --- | ---: | ---: | ---: | --- |
| `dfm10-bornholmsk-parallel` | 13,570 | 664,901 | 6,649,010 (repeat 10) | Packaged and tokenized; source-quality audit and final union/sample validation pending. |
| `dfm10-cor-sem-sft` | 130,111 | 5,812,032 | 11,624,064 (repeat 2) | CC0 fields converted into grounded hypernym, synonym, related-word, ontology, and frame tasks; 14,747 lemma-disjoint holdout rows excluded; packaged and tokenized. |
| `dfm10-danish-book-ads-sft` | 73,301 | 16,566,438 | 33,132,876 (repeat 2) | Derived from 51,251 manually checked ads; every extraction target is source-supported; 8,106 ad-disjoint holdout rows excluded; packaged and tokenized. |
| `dfm10-sks-tei-sft` | 39,007 | 7,480,454 | 14,960,908 (repeat 2) | CC0 editorial `kom.xml` commentary QA only; 4,386 note-disjoint holdout rows excluded; raw authorial text and modernization remain deferred; packaged and tokenized. |
| `dfm10-diem-historical-modernization` | 0 materialized; 1,259 requests | pending | repeat 5 after audit | Gemma 4 31B generation and independent E4B audit queued before tokenization or packaging. |

All four materialized slices fit the current 4K training contract: the maximum
prompt-plus-target lengths are 911, 130, 1,753, and 3,462 tokens respectively.
The Bornholmsk tokenized root was rebuilt after detecting and removing one stale
pre-rename task directory, preventing accidental double sampling.

The restart-safe handoff is
`scripts/run_dfm10_research_sources_when_free.sh`. It locks
`data/mimir_grounded_500k_sft/campaign.lock`, so it cannot race the active
Tidsskrift/Mimir vLLM fleet. It first generates DiEm targets with eight 31B
servers, tears those down, then audits DiEm and a deterministic 100-row sample
from each of the four materialized sources with eight independent E4B servers.
Only a passing per-source audit gate permits DiEm building and the DFM10 union
rebuild. The queued launch PID and log are recorded under
`logs/dfm10_research_sources_queue/`.

The tokenized-union builder treats these unfinished research additions as
optional queued roots. This supersedes the earlier mandatory DiEm root that
caused unrelated DFM10 rebuilds to fail before DiEm generation existed. The
source-specific campaign remains fail-closed and explicitly requires all
artifacts before final integration.

**Completed campaign update, 2026-08-30 10:52 CEST:** the queued campaign
finished and released all eight GPUs. The independent E4B samples had zero
judge errors and accepted Bornholmsk 94/100, COR.SEM 100/100, book ads 98/100,
and SKS 94/100. DiEm generated 1,258/1,259 requests and accepted 1,167 rows
(92.77% of audited generations); its production gate passed. The DiEm slice is
1,658,595 tokens per pass and 8,292,975 tokens at repeat five. All five sources
are now present in the 15,728-task DFM10 tokenized union. They remain marked
work in progress because final DFM10 resampling and publication are separate
explicit operations.

### Tier A: structured additions worth implementing or piloting

| Source | Size and license | Incremental value | Required gate |
| --- | --- | --- | --- |
| `dsldk/COR.SEM` / COR.SEM 1.0 | 34,000 lemmas, 42,000 senses; CC0 | High-quality semantic types and links across COR, DanNet, FrameNet, sentiment, and thesaurus concepts. Suitable for lexical relation, ambiguity, semantic-class, and contrast tasks. | Use only CC0 COR.SEM. Do not mix in COR.SEM.EXT definitions/examples, which are CC BY-NC-ND. Reserve a lemma-disjoint diagnostic set before task generation. |
| `chcaa/danish-book-ads` | 80,938 records; CC BY 4.0 | Historical Danish plus title/author extraction, advertisement type, date, geography, and subject labels. | Prefer manually verified and high-confidence labels. Audit original advertisement hashes against ENO/DynaWord and train on structure rather than duplicated raw prose. |
| `strombergnlp/bornholmsk_parallel` | 6,785 pairs; CC BY 4.0 | Genuine Bornholmsk-to-standard-Danish parallel supervision. The pairing is additive even though DynaWord contains the unpaired `botxt` corpus. | **Superseded on 2026-08-30:** the project deliberately includes all official train, validation, and test pairs in both directions, preserves split provenance, and does not use those splits as an evaluation. Audit short/identity pairs before final sampling. |
| `kb-dk/SKS_tei` | Scholarly TEI edition; CC0 | Kierkegaard works plus machine-readable dates, references, and merged short/extended editorial commentary. | Hash author text against DynaWord `adl`; admit only non-overlap or derived grounded commentary/modernization tasks. Keep editorial and author voices distinct. |
| `RA-Data-Science/DiEm_HTR` | 975 images, 67,410 lines, 383,339 words; CC BY 4.0 | Proofread 17th--18th-century Danish handwriting transcriptions. Useful for historical-language modernization and, later, multimodal HTR. | Current text model can use only transcripts or derived tasks. Audit names and sensitive church-record content; do not fabricate noisy OCR as if it were observed. |

### Tier B: useful after overlap or rights resolution

| Source | Size and license | Decision |
| --- | --- | --- |
| `chcaa/kb-books` | 3,485 public-domain documents represented by about 2.34M page rows; CC0 | Run title/page hashes against DynaWord `ncc_books`, `adl`, `gutenberg`, and PleIAs. Keep only unique, usable OCR or derive document-grounded tasks. |
| `PleIAs/Danish-PD` | 3,113 titles, about 322M words; public-domain package | Large but likely overlaps KB, Internet Archive, Gutenberg, and DynaWord. Treat as a deduplication reservoir, not an automatic raw-text addition. |
| `chcaa/Press-and-Plot` | 50 manually cleaned installments from 29 stories; card states public domain/CC0 | Small but high-quality historical genre structure. Use for a held-out fiction/genre diagnostic or a tiny supervised slice after machine-readable license normalization. |
| `chcaa/feuilleton_dataset` | 1,394 rows | Appears to be a lower-level derivative of the same historical newspaper fiction. Do not combine with Press-and-Plot until lineage and license are explicit. |
| `chcaa/fiction4sentiment` | 6,300 human valence annotations | Useful literary sentiment diagnostic, but the Hub card lacks a license and includes modern Hemingway/Plath text. Resolve rights; labels alone do not clear source text. |
| `chcaa/hist-dk-pos` | 704 tokens; card states public-domain/CC0 | Useful tiny historical POS diagnostic; too small to matter as ordinary SFT. Keep separate from any Press-and-Plot training rows. |
| `CoRal-project/coral-v3` conversational train | 156.27 hours of conversational speech; gated OpenRAIL | Potentially valuable natural spoken Danish and dialect coverage. Review model-training and redistribution clauses, use conversation train only, and reserve speaker-disjoint validation/test. |
| `strombergnlp/itu_faroese_danish` | 3,995 pairs; CC BY 4.0 | Small neighboring-language translation resource. Include only if Faroese transfer is an explicit objective; otherwise it dilutes a Danish-English mix. |
| `KennethEnevoldsen/dane_plus` | 4,383 train + 564 dev + 565 test; CC BY-SA 4.0 | Better, manually reviewed OntoNotes-style NER labels on the same 5,512 DaNE sentences. Replace or extend current DaNE annotations; never add as duplicate sentence exposure. |
| `DDSC/da-wikipedia-queries` | 90,840 query-positive-negative rows; CC BY-SA 3.0 | Useful retrieval/query supervision, but generated from Danish Wikipedia already present in DynaWord. Audit query quality and use only a selected model subset; reserve document-disjoint evaluation. |

## Evaluation-first candidates

| Source | Proposed evaluation | Reason not to train directly |
| --- | --- | --- |
| `chcaa/naturalistic_social_norms_alignment` | Danish open-ended social advice/alignment using 3,023 dilemmas and panel-derived solutions | The dataset is explicitly intended for evaluation, uses real listener dilemmas, and licenses only its packaging/processing while disclaiming ownership of source material. It also needs privacy review. |
| `strombergnlp/danfever` | Danish evidence-grounded fact verification | Established benchmark with about 6.4K claims. Training would destroy its diagnostic value; Den Store Danske excerpts also deserve source-level review. |
| `KennethEnevoldsen/danish-compounds` | Compound segmentation/morphological reasoning | Only 624 manually annotated words and explicitly designed as an evaluation resource. |
| Danish Semantic Reasoning Benchmark | Lexical-semantic reasoning headline | Benchmark derived from Danish semantic resources; reserve completely. COR.SEM training splits must be lemma-disjoint from it. |
| `kuhumcst/Danish-Similarity-Dataset` | Semantic similarity | Gold standard of 99 word pairs rated by 38 humans; evaluation value exceeds training value. |
| SemDaX | Word-sense/supersense diagnostics | About 90K words, but CLARIN academic license forbids redistribution. Local academic evaluation may be possible; do not package or upload. |
| `KennethEnevoldsen/spontanous-speech-qa` | Small spoken-Danish QA check | Only 512 train/129 test rows and derived from Danish Gigaword. Avoid leakage into its own test and do not count the underlying speech as new text. |
| CopCo | Psycholinguistic surprisal/reading diagnostic | 1,832 sentences with eye-tracking recordings. This is specialized evaluation data rather than broad SFT. |

## Existing raw-text overlaps

These sources are valuable canonical upstreams but are not additive raw text in
the current DFM lineage:

| External source | Existing local DynaWord route |
| --- | --- |
| `MiMe-MeMo/Corpus-v1.1` | `memo` |
| `JohanHeinsen/ENO` and ENO-derived newspaper text | `enevaeldens_nyheder` |
| `chcaa/grundtvigs-works` | `grundtvig` |
| Aarhus City Archives historical handwriting | `historical-danish-handwriting` |
| Danmarks Breve training data | `kb_historical_letters` |
| Five-municipality meeting minutes | `municipality_meetings` |
| Archive for Danish Literature | `adl` |
| DanNet | `dannet` |
| Bornholmsk raw corpus | `botxt` |

The structured upstream may still replace a lower-quality route or generate a
new supervised task, but every such use needs stable IDs and content hashes so
the sampled mix can account for repeated underlying text.

## Defer or exclude

- Do not admit `north/scandinavian-{educational,linguistic}-annotations` as
  SFT merely because the package says MIT. Inspection shows Common Crawl text
  with synthetic scalar quality annotations, including harmful and noisy web
  pages; the package license does not establish rights to every crawled page.
- Keep DAST/DKStance, DKHate, AngryTweets, and other historical social-media
  datasets out of training. Some contain user-deleted material, sensitive
  speech, or existing evaluation items.
- Keep KorpusDK behind its DSL restricted-license application. Public catalogue
  metadata is not permission to redistribute the corpus.
- Do not transform COR.SEM.EXT under CC BY-NC-ND without an explicit permission
  that covers derivatives and model training. The open COR.SEM base is enough
  for an initial semantic campaign.
- SemDaX is usable locally for academic research under its CLARIN academic
  license, but copies may not be redistributed.
- Public GitHub repositories without a source license remain review-only:
  `dsldk/herman-bang`, `diplomatarium-danicum`, `tycho-brahe`,
  `middelaldertekster`, `brandes_xml`, and related scholarly editions.
- Do not use CHC embedding-only datasets (`eno-embs-old-news`, painting
  embeddings) as language-model text. They add storage, not supervision.
- Treat unlicensed synthetic Danish math, science, instruction, and tool-call
  repositories as audit candidates only. Verify upstream lineage and benchmark
  contamination before considering any subset.

## Recommended next campaign

1. Implement a no-download inventory for COR.SEM, Danish book ads,
   Bornholmsk parallel, SKS TEI, and DiEm HTR with pinned revisions, schema
   hashes, exact licenses, and source IDs.
2. Run normalized exact and MinHash overlap against DynaWord and active DFM10
   sources. For books and historical newspapers, also compare title/date/page
   identifiers because OCR variants defeat exact text hashes.
3. Create held-out evaluations first: Danish compounds, DanFEVER, naturalistic
   social norms, and a lemma-disjoint COR semantic set. Freeze their hashes
   before generating any related training rows.
4. Pilot at most 1,000 converted rows per admitted family and audit Danish
   quality, historical faithfulness, answer grounding, and value over the raw
   source. Do not use a teacher to overwrite gold linguistic labels.
5. Estimate incremental tokens after deduplication. Small expert resources
   should be weighted for task coverage, not repeated until their token volume
   resembles web-scale sources.
6. Monitor CLARIN-DK, Sprogteknologi.dk, `chcaa`, `kb-dk`, `dsldk`,
   `kuhumcst`, `RA-Data-Science`, MiMe-MeMo, JohanHeinsen, StrombergNLP,
   CoRal-project, DDSC, and Alexandra Institute for revisions and new releases.
