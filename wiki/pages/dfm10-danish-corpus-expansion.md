---
type: Runbook
title: DFM10 Danish Corpus Expansion
description: License-gated Tidsskrift harvesting, new DynaWord transformation candidates, and deterministic DSL lexical supervision.
tags: [dfm10, danish, tidsskrift, dynaword, dsl, sft, licensing]
status: stable
last_updated: 2026-08-30
confidence: high
sources:
  - id: tidsskrift-oai
    resource: https://tidsskrift.dk/index/oai?verb=Identify
    title: Tidsskrift.dk OAI-PMH endpoint
  - id: dynaword
    resource: https://huggingface.co/datasets/danish-foundation-models/danish-dynaword
    title: Danish DynaWord 1.2.22
  - id: dsl-sentiment
    resource: https://github.com/dsldk/danish-sentiment-lexicon
    title: Danish Sentiment Lexicon
  - id: dsl-framenet
    resource: https://github.com/dsldk/dansk-frame-net
    title: Danish FrameNet
---
# DFM10 Danish Corpus Expansion

## Tidsskrift.dk

`scripts/prepare_dfm10_tidsskrift_expansion.py` implements a metadata-first,
fail-closed expansion. It never fetches article files before an article-level
rights gate succeeds. The inventory is stored transactionally in
`data/dfm10_tidsskrift_expansion/inventory.sqlite3`; SQLite WAL, primary-key
upserts, atomic JSONL exports, per-journal resume tokens, bounded retries, and
temporary download files make interruption and concurrent journal workers
safe.

The production inventory completed on 2026-08-29 with:

- `127,510` unique OAI records across all `232` base journal sets;
- `2,450` CC BY and `29` CC BY-SA records before overlap removal;
- `2,173` strict-open records not already represented by the existing
  Tidsskrift BT URLs or raw DynaWord titles;
- `758` records with an author abstract of at least 120 characters and thus
  eligible for a PDF request.

The conservative resumable inventory command is:

```bash
python scripts/prepare_dfm10_tidsskrift_expansion.py scan-sets \
  --workers 2 --delay 1.0
```

The two workers each issue only one serial request at a time. The scanner
handles malformed legacy OJS XML through an entity-disabled recovery parser,
but downstream admission still requires structurally parsed metadata and an
explicit rights URL. Admitted rights are CC0, CC BY, CC BY-SA, and an explicit
public-domain mark. CC BY-NC, ND, unknown, and free-access-only records are
excluded from this strict-open package.

After the scan:

```bash
python scripts/prepare_dfm10_tidsskrift_expansion.py export
python scripts/prepare_dfm10_tidsskrift_expansion.py download --delay 1.5
python scripts/prepare_dfm10_tidsskrift_expansion.py convert
```

The export deduplicates canonical article URLs from the existing Tidsskrift BT
source and normalized titles from the 4,121-row raw DynaWord component. The
downloader preserves exact OAI identifier, URL, title, authors, journal, DOI,
copyright, and license. Conversion admits only Danish or English PDF text whose
detected language agrees with the author abstract and whose full extracted body
fits the 4K training contract. The task is article-to-author-abstract
summarization. A whitespace-equivalent author abstract is removed from the PDF
input, and residual near-verbatim target spans cause rejection, so the gold
target cannot leak into the prompt. No synthetic abstract is treated as gold. PDF/OCR failures,
missing abstracts, cross-language abstracts, and overlength articles are
rejected. The default PDF engine is the already-installed `pypdf`; the optional
`--pdf-engine pdftotext` path is available where the Poppler executable exists.
The converted candidates then receive an independent Gemma 4 31B audit for
topical match, grounding, summary quality, and training value. Exact duplicate
targets are also rejected. Each audit is bound to a SHA-256 fingerprint of the
exact prompt and target, preventing stale judgments after extraction changes.
The completed audit retained `9` of `24` structurally valid candidates.

**Superseded packaging decision (2026-08-29):** the nine rows remain the gold
`article_to_author_abstract` subset, but a standalone nine-row
`dfm10-tidsskrift-open-article-summaries` package is not an appropriate release
unit. They are merged at final build time into `dfm10-tidsskrift-open-sft`,
where their gold origin and task label remain explicit. They are not duplicated
as a separate tokenizer input.

### Grounded Tidsskrift SFT and chats

The strict-open expansion now downloads every one of the `2,173` non-overlap
article candidates, including articles without author abstracts. Downloads are
serial, rate-limited, resumable, written through `.part` files, and retried with
a 512 MiB per-article ceiling. PDF extraction removes repeated page furniture,
truncates reference sections, preserves paragraph boundaries, rejects damaged
text, detects Danish or English, and creates overlapping coherent chunks using
the contract in `config/dfm10_tidsskrift_grounded_sft.json`.

Two separately audited products are derived from the same licensed chunks:

| Dataset | Contract | Final source |
| --- | --- | --- |
| `dfm10-tidsskrift-open-sft` | Gemma 4 31B produces grounded questions, explanations, and only naturally appropriate section summaries. Each of the 189,392 candidates receives a separate row-level 31B audit. The build fails below 125,000 accepted synthetic rows, then appends the nine gold author-abstract rows. | `data/dfm10_tidsskrift_open_sft_source/tidsskrift_open_sft.jsonl` |
| `dfm10-tidsskrift-open-chats` | Gemma 4 31B produces natural student inquiry conversations with 2–10 student/assistant exchanges. The first question requests broad orientation; later turns ask for details, causes, relations, examples, limits, or elaboration. Every answer must be grounded, every assistant turn is audited, and the complete rendered chat must fit 4,096 tokens. | `data/dfm10_tidsskrift_open_chats_source/tidsskrift_open_chats.jsonl` |

The source excerpt is retained as system grounding in chat rows. The standard
chat tokenizer emits each assistant message as a supervised target with the
preceding conversation as context, so a retained conversation contributes all
of its progressively deeper assistant turns. Both packages preserve OAI ID,
article and PDF URLs, title, authors, journal, exact license URL, chunk hash,
teacher model, judge model, and audit result.

The production runner is:

```bash
setsid bash scripts/run_dfm10_tidsskrift_grounded_8gpu.sh \
  > logs/dfm10_tidsskrift_grounded/bootstrap.log 2>&1 < /dev/null &
```

It first waits for the rate-limited download, retries missing PDFs, extracts
and shards requests, and refuses to launch below 180,000 SFT candidates. It
then waits on the current Mimir campaign lock and for all GPUs to become free,
starts one Gemma 4 31B server per GPU, interleaves SFT and chat shards, retries
incomplete generation/audit shards up to four times, and tears down its servers
on exit. Successful completion builds both upload-ready packages, tokenizes
them with 16 workers, and rebuilds the DFM10 tokenized union. On 2026-08-29 the
current watcher was active as PID `2532197`;
the existing Mimir workload remained untouched. **Superseded 2026-08-30:** the
300,000-candidate/200,000-accepted design was impossible for the completed
strict-open harvest. The production gates are now 180,000 candidates and
125,000 accepted rows; all 189,392 available candidates are audited. The chat
gates are 18,000 accepted conversations and 100,000 supervised assistant turns
from the 23,674 available chunks.

**Partial-batch recovery, 2026-08-30:** The initial SFT validator rejected an
entire teacher batch unless Gemma returned exactly all eight requested
examples. This is superseded. Generated JSONL retained every raw response, and
the production parser now keeps each individually valid example from a short
or partly malformed batch, recovers complete objects before a truncated JSON
tail, and records requested, returned, and retained counts. It reparses saved
raw responses before making any inference request. The first offline pass
recovered 6,272 previously discarded request batches containing 35,379 valid
examples from 74 attempted shards; only 461 requests in those shards still
require generation. Independent
row-level auditing remains mandatory, so salvage weakens no quality gate.

The resumed queue prioritizes the two missing chat shards before all SFT work.
It then audits recovered SFT rows and generates only unresolved requests.

**Superseded terminal shard closure, 2026-08-30:** The temporary 97.5% chat and
97% SFT completion thresholds are no longer accepted. They prematurely marked
138 shards complete with 150 structurally missing generation or audit records.
Production now requires 100% requested/generated/audited coverage per shard.
The campaign reparses retained raw responses before new inference, treats
legitimate discussion of a research `dataset`/`datasæt` as content rather than
prompt meta-language, canonicalizes copied audit item IDs only when decision
count and ordered numeric suffixes align exactly, and gives bibliography-only
chunks an explicit grounded bibliographic task contract. Premature done markers
are archived and incomplete shards requeued; quality admission remains governed
by the unchanged independent row-level audit. The first reconciliation recovered
all 150 missing records across 138 prematurely closed shards. A final scan of
the subsequently completed SFT tail found three additional records: two judge
repetition failures caused by copying full SHA-256 IDs and one malformed JSON
escape. Judge prompts now use deterministic short item aliases that map back to
canonical IDs. Those three records are queued under the corrected runner behind
the active shared-GPU campaign; no source request is intentionally excluded.

## DynaWord 1.2.22 additions

The four non-Folketing text additions were downloaded separately under
`data/downloads/datasets/danish_dynaword_1_2_22_additions` so the pinned local
DynaWord 1.2.16 tree was not mutated.

| Source | Inspected content | Decision |
| --- | --- | --- |
| `mosel_voxpopuli` | 1,590,405 short Whisper transcripts, CC BY 4.0 | Group by recording and contiguous segment; candidate for faithful spoken-to-written Danish normalization, never raw prompt-to-answer synthesis |
| `kalliope` | 22,270 public-domain historical poetry/literature documents | Candidate for contemporary-Danish modernization preserving meaning, genre, tone, line breaks, and dialogue |
| `mosel_youtubecommons` | 128 CC BY fragments from eight videos | Too small for an independent source; defer to a later grouped speech pilot |
| `dakultur` | 344 cultural-evaluation questions without gold answers | Exclude from training to avoid evaluation contamination and unsupported teacher answers |

`scripts/prepare_dfm10_dynaword_sft_candidates.py` selected 100,000 of 153,048
VoxPopuli recording windows and 20,000 of 23,144 Kalliope chunks by deterministic
lowest-hash sampling. Each source passage is stored once, split into 16 atomic
request shards per family under `data/dfm10_dynaword_sft/requests`.

`scripts/run_dfm10_dynaword_sft.py` provides resumable `generate`, `audit`, and
`build` phases. Production admission requires Gemma 4 31B generation followed
by a separate semantic-preservation audit scoring at least 4/5 on meaning,
Danish quality, task adherence, and absence of unsupported content. Do not add
the candidates to the tokenized union before this gate. A 100-row pilot per
family was launched at concurrency two against the existing Gemma 4 31B
servers without reconfiguring or terminating the primary Mimir generation
campaign. Final results were:

| Family | Successful generations | Accepted | Accepted near-copies (`similarity >= 0.98`) | Decision |
| --- | ---: | ---: | ---: | --- |
| Kalliope | 99/100 | 60 | 0/60 | Useful after strict audit; retain the 20,000 production candidates, but do not admit them before full generation and audit |
| VoxPopuli | 100/100 | 79 | 67/79 | Do not add to DFM10: the accepted rows are predominantly low-signal copies with punctuation changes |

Kalliope's main rejection modes were semantic preservation failures and
incorrect modernization of dialectal or archaic Danish. The audit is therefore
not optional. The 60 pilot rows are diagnostic artifacts under
`data/dfm10_dynaword_sft/pilot_accepted`, not an active DFM10 source.

## DSL lexical supervision

The already-prepared openly licensed Andersen modernization remains active:

| Source | Train rows | Natural-pass Gemma tokens | DFM10 repeat | Effective tokens/epoch | License |
| --- | ---: | ---: | ---: | ---: | --- |
| `ogierMontanus/hcandersenDk_data_2024` | 1,068 | 1,205,157 | 20 | 24,103,140 | GNU AGPLv3 corpus notice |

Its separate 119-row validation split is not exposed to tokenization. Hashes
and the exact train/validation partition are enforced by
`scripts/prepare_dfm10_andersen.py`.

Two resources have explicit reusable terms and are integrated immediately:

| Source | Source labels retained | SFT rows | Gemma tokens | License |
| --- | ---: | ---: | ---: | --- |
| `dsldk/danish-sentiment-lexicon` | 14,008 | 1,751 | 702,025 | CC BY-SA 4.0 |
| `dsldk/dansk-frame-net` | 33,846 unique non-NULL labels | 4,231 | 1,687,548 | Danish FrameNet 1.0 permissive notice |

`scripts/prepare_dfm10_danish_lexical_sft.py` pins source revisions
`4d50cf4331d50a726599fc93201db77a88d640e3` and
`81da285274c7775cad6598cfe21ff6114f7f7c5b`. Eight gold labels are packed per
row. Sentiment prompts explicitly request a context-free lexical prior, not
contextual sentence sentiment. FrameNet rows remove NULL labels and exact
duplicates. Both original batched sources use repeat one in
`data_io/prefix_config_dfm10.yaml`.

### Additive natural lexical interactions

The machine-oriented eight-label rows remain part of DFM10 unchanged. A
separate additive campaign creates one natural Danish interaction for every
retained gold item: 14,008 sentiment interactions and 33,846 FrameNet
interactions, or 47,854 new rows in total. This is deliberately an addition,
not a replacement.

`scripts/dfm10_danish_lexical_natural.py` explodes the existing gold batches
into stable item IDs and packs eight facts into each of 5,982 Gemma API
requests. Gemma 4 31B varies concise Danish questions, including formulations
such as `Er idyllisk et positivt ord?`, while each answer must retain the exact
signed polarity and direction or exact FrameNet label. Deterministic checks
reject missing expressions, labels, signs, natural questions, or serialized
JSON in the dialogue. A separate Gemma 4 31B pass scores natural Danish,
question usefulness, answer coherence, and label fidelity; each dimension
must score at least 4/5.

Accepted additions are written separately as
`dsldk_danish_sentiment_lexicon_natural.jsonl` and
`dsldk_danish_framenet_natural.jsonl`. They each use repeat one. The base
preparer only removes files it owns, so a later `--force` rebuild cannot erase
these generated additions. `scripts/run_dfm10_danish_lexical_natural_8gpu.sh`
is resumable and owns its server PIDs. It waits for the active Mimir campaign
lock and for all eight GPUs to become free before launching eight Gemma 4 31B
vLLM servers; it never kills or shares the Mimir servers.

On 2026-08-30 the queue was initially held by a stale Mimir shell lock after
that shell had ended on a syntax error. The completed Mimir state was verified
at 640/640 main and 128/128 top-up shards; the lock owner had only a `tee`
child and no workers or servers. Removing that exact stale process group moved
the lexical campaign to its independent all-GPUs-free gate. The unrelated
`dfm10-open-chats` vLLM servers were left untouched.

The tokenized tree is `data/tokenized_dfm10_danish_lexical`. The two packages
are:

- `exports_dfm10/dfm10-danish-lexical-sentiment-sft`
- `exports_dfm10/dfm10-danish-framenet-sft`

Their next export refresh includes both original batched rows and accepted
natural rows in the same source-specific repository. They remain local until
that generation, audit, rebuild, and validation cycle is complete.

The DFM10 union builder and source-quality audit inventory know both sources.
The live `data/tokenized_dfm10` union was rebuilt and contains both lexical
tasks plus the final Tidsskrift task (`15,708` total union tasks).
`data/sampled_dfm10` was deliberately not
resampled while the Tidsskrift and model-audited DynaWord gates remain open;
perform one final sampling rebuild after those inclusion decisions instead of
repeatedly rewriting the approximately 100B-token epoch plan.
The existing Andersen modernization source remains admitted under its AGPLv3
terms. Related Andersen diaries, correspondence, modernized-tale repositories,
and DSL literary editions remain excluded because public repository access did
not establish an explicit data license. The GPL `dsldk/salmer` repository is a
portal implementation with only a partial checked-in corpus and does not
establish a clean, complete text-dataset boundary, so it is not admitted.
