---
type: Plan
title: DFM13 Dataset Additions
description: Incremental source decisions and reproducible preparations for the next training mix.
status: draft
confidence: high
last_updated: 2026-10-01
tags: [data, dfm13, danish, preferences]
---
# DFM13 Dataset Additions

## Baltic Expansion Preparation (2026-10-03)

Lithuanian and Latvian source selection is recorded in the
[Baltic source inventory](dfm13-baltic-language-sources.md), including verified
HF revisions/counts, native text, SFT, translation candidates and admission
gates. The discovery-only status is superseded by CPU download, conversion,
transformation and all-43-pair translation preparation. Candidates remain
audit-gated, not admitted training additions. The separate synthetic campaign
targets 70K accepted conversations per language. DaLA creation for these
languages is explicitly owned by a parallel thread and excluded from this work;
original DaLA source articles/sittings are retained as explicitly requested.

## Existing Model Charter Inheritance (2026-10-02)

User requested integration of `danish-foundation-models/model-charter` unless
already present. Verified existing scenario-based supervision inherited through
DFM10/11/12; do not register a duplicate DFM13 addition:

- English: `danish-foundation-models/synthetic-values-model-charter`, 1,360
  SFT rows, 432,223 rendered tokens.
- Danish: `schneiderkamplab/dfm10-synthetic-values-model-charter-da`, 1,343
  audited rows, 623,325 rendered tokens.

Recovered source-map resolved paths explicitly identify the two charter token
trees. Current selected DFM12 epoch accounting contains one occurrence per row,
not the older DFM10 repeat-10 intended exposure. Evidence is in
`data/provenance/dfm11_remote_20261002/source-map.json` and the corresponding
`source_rows` in `docs/reports/dfm12_training_composition.json`.
Separate preference pairs exist in the preparation design; rejected answers
are not part of SFT. See [the original integration](dfm10-danish-hf-gap-integration-plan.md).

The inherited scenarios reference charter commit
`e60e41aad338c6261cc21f926847b3ab77ff4226`, not necessarily the latest charter.
The GitHub HEAD observed today is `3114a43a012c5679cd444a6ae4b53ed6d6247d96`.
No claim that later charter amendments are covered, and no automatic source
revision update or regeneration was made.

## MATH Repeat Update (2026-10-02)

### HF-ready Package (2026-10-04)

The missing CPU publication package is now prepared and verified at
`exports_dfm13/dfm13-hendrycks-math-worked`, with an external `.ready.json`
receipt.7,496 unchanged physical rows, repeat5 metadata only; full existing
MATH source/token adapter verification passed. Source MIT card/citation,
license attribution, screening and original provenance are included. No HF
upload or registry change is claimed. Tesla owns publication-metadata integration;
see [MATH and TLPC handoff](../../docs/reports/dfm13-math-package-tesla-handoff-20261004.md).
The earlier inventory's missing-package finding is superseded, not its
observation that remote publication was absent.

User request supersedes the repeat-1 policy below: `hendrycks_math_worked`
now uses **repeat 5** in the additions registry and preparation defaults.
This corresponds to 37,480 sampled occurrences and 12,155,725 rendered tokens
before any later mixture-level caps. The 7,496 unique rows and tokenized payload
are unchanged. Existing hashed preparation receipts retain the historical
repeat-1 setting; current sampling policy is the registry. No resampling was run.

## jjzha Preparation Status (2026-10-02)

**Superseded later on 2026-10-02:** preparation below is now executed. See
[jjzha native additions and audit](dfm13-jjzha-native-additions.md) for actual
admitted counts, quality gates and the waiting audit client. Four structured
sources are registered; IMDb and CroCo remain pending audit, not active additions.

Selection and converter are scaffolded in `config/dfm13_jjzha_sources.json`
and `scripts/prepare_dfm13_jjzha.py`; **not downloaded, converted or registered
yet**. Selected train-only sources: `jjzha/skillspan`, `jjzha/kompetencer`,
`jjzha/green`, `jjzha/imdb-dutch-instruct`, `jjzha/dutch-central-exam-mcq`.
`jjzha/croco-translated-data` is an audit candidate, not admitted training data:
an inspected example summarizes an unavailable named report. Preserve full
messages, screen tool/template issues, and audit unsupported premises and
correctness before admission. Source decisions/pins and deferred sources are
in the configuration. The converter still needs testing before execution.

## Original MATH Worked Solutions (2026-10-01)

User-authorized CPU preparation adds `hendrycks_math_worked` at **repeat 1**,
preserving all eight existing audited Arena entries in `config/dfm13_sources.json`.
Source: `EleutherAI/hendrycks_math`, pinned revision
`21a5633873b6a120296cce3e2df9d5550074f4a3`; pinned source card declares MIT.
All seven configurations were downloaded as 14 hashed parquet files: **7,500
train / 5,000 test**. Test is used only for problem-overlap screening, never
converted into training rows. Exact and collapsed-whitespace problem matching
is global across configurations, without case folding or semantic heuristics.

Final retained count: **7,496 worked solutions**. Exclusions: zero exact train/test
matches, one whitespace-normalized train/test match, one normalized duplicate
train problem, and two source solutions with empty `\boxed{}` answers. The
test match is `geometry:train:433` against `precalculus:test:202`; the train
duplicate `algebra:train:959` retains `algebra:train:925` (different worked text
is recorded, not asserted equivalent). Empty boxes are `number_theory:train:661`
and `number_theory:train:663`; no answer was invented for either.

The complete original solution is preserved verbatim as a prefix. A canonical
terminal box is appended using `utils.functions.last_boxed_only_string`.
Unambiguous single-digit TeX shorthand `\boxed 2` / `\boxed 9` is normalized
for extraction, not mistaken for a missing answer. This supersedes the initial
7,494-row preparation; its artifacts are preserved outside active input roots
under `data/dfm13/math-worked-pre-normalization/`. The shared helper/evals were
not changed. Provenance includes source config, split, row index, level/type,
file/row/solution hashes, final answer and normalization policy.

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/prepare_dfm13_math.py --tokenize --register
```

Fresh-only preparation; existing artifacts are never overwritten by rerunning.
Converted data: `data/converted_sources/dfm13_math_worked/train.jsonl`.
Metadata alongside it records source pins, screening exclusions, normalization
history, tokenization/registration receipts and independent verification.
Tokenized output: `data/tokenized_dfm13_additions/hendrycks_math_worked/`.
Uses `scripts/tokenize_chat_template.py`, native
`data/dfm11_tokenizer/{tokenizer.json,chat_template.jinja}`, **one CPU worker**,
no regex modification, no hard truncation and zero skipped rows. Actual tokens:
**2,431,145 total = 634,782 prompt + 1,796,363 target**; maximum sequence 2,999
tokens, zero sequences over 4,096. Focused tests: **18 passed**, including real
native-template tokenization and preservation of the eight prior registry entries.

This is **not whole-corpus deduplication**. The inherited RLVR MATH derivative
already contains 7,498 direct-answer examples at repeat 10; shared problems with
this repeat-1 worked-solution addition are expected. A previous raw `math_train`
prefix lookup with no matches is not proof of absence. No sampling, upload,
training, GPU operation, or evaluation change was performed for this addition.

## Excluded Research Datasets (2026-10-01, Latest Decision)

The user explicitly excluded **RepoChat, SearchArena and Mimir Search** from
DFM13. This supersedes earlier plans for their source registration or integration,
including conditional accepted-only integration. Preserve research artifacts,
cached evidence and assessments, but do not register, tokenize or sample these
three datasets into DFM13. Existing audited preference datasets are unaffected.
Verified at this decision: none of the three is registered in
`config/dfm13_sources.json`. Search work remains paused; this decision does not
cancel the existing training-resume handoff.

## Release And Scale-Up Decision (2026-10-01)

The user clarified that existing unaudited HF repositories must be replaced
in place, while entirely new datasets may receive new repositories. Do not
create parallel `-audited` repositories for existing datasets. Export,
publication verification, and source registration should progress as a detached
pipeline; publication failures must remain visible rather than count as success.

Superseding calibration-only execution limits, the user requested full RepoChat
generation and audit, using all eight shared servers with high concurrency.
This authorizes processing, not accepting failed quality checks: preserve real
repository observations, distinguish unavailable sources from rejected answers,
and retain existing holds. Do not execute untrusted repository code.

SearchArena is authorized to use the remaining paid retrieval budget concurrently,
up to 200 total reservations across the shared cache and all clients (not 200
additional calls). Cache responses for reuse, audit generated trajectories, then
classify failed first reviews for evidence repair or regeneration. Existing
quality holds remain applicable; no automatic acceptance follows from scaling.

The concurrent 86-query followup reached the 200-reservation ceiling on
2026-10-01. It recorded 16 successful retrievals, 69 HTTP 402 responses, and
one HTTP 422 response. A reservation is an attempted request, not a successful
search or confirmed charge. HTTP 402 indicates a provider payment/credit issue;
do not retry paid requests or reset the counter. Continue with cached evidence.
Details: `data/dfm13/search-parallel86-20261001/retrieval` and the shared
`data/dfm13/search-jina-paid-campaign-20261001/cache.sqlite`.

DFM13 is planned as an extension of DFM12. Its initial additions registry is
`config/dfm13_sources.json`; no complete sampling/assembly has been requested
or performed yet. Existing DFM12 training and scheduling are unchanged.

## AI-Arenaen Preferred Conversations

User-approved source: [danish-foundation-models/ai-arenaen](https://huggingface.co/datasets/danish-foundation-models/ai-arenaen),
CC-BY-4.0, pinned revision `bb3b6d28e4e159fb23dbf9aa4f9902696ed678be`.
This is distinct from older `ai-arenaen-conversations` and `ai_arena_udtraek`.
Future final assembly should check overlap with those inherited sources,
without silently broadening the selected targets or changing this vote policy.

| Vote | Supervised answer(s) | Current output count |
| --- | --- | ---: |
| a_better | A | 735 |
| b_better | B | 743 |
| both_good | A and B separately | 1124 |
| both_bad, idk, null/no choice | None | 0 |

The source has 3879 turn-level rows; 2040 selected rows yield 2602 SFT examples,
including 361 with multi-turn context. 1839 rows are excluded by vote alone.
Default addition repeat is 1, pending broader DFM13 budgeting.

Votes are per turn, while full histories repeat across rows. Preserve the
selected side's preceding messages but end at the selected assistant answer;
set `target_message_index` to that last message. The existing Gemma chat
tokenizer supports this field and must emit exactly one supervised target per
example. Earlier answers can be context, never additional targets; later
unrated/rejected answers are not copied. Do not train every assistant turn in
each full conversation or duplicate entire histories for every vote.

Only visible `content` is retained; separate `reasoning_content`, model names,
votes and metadata do not enter prompt/answer text. Provenance remains in
metadata. One record had an identical consecutive user message in its history;
the converter removes that duplicate after uniquely locating the rated turn.
Other malformed or ambiguous histories fail closed. Both-good sides remain
separate even when their content matches, as explicitly requested.

```bash
python scripts/prepare_dfm13_ai_arenaen.py
```

This downloads the pinned parquet, streams conversion, atomically publishes
`data/converted_sources/dfm13/ai_arenaen_preferred/train.jsonl`, and writes
`train.manifest.json` with counts, revision and source/output SHA256 hashes.
The downloader catalog also exposes this source under group `dfm13`.
The normalized JSONL uses messages, selected target index and thinking-disabled
chat-template kwargs; it is ready for the existing Gemma tokenizer. No raw
source templates are inserted. No tokenization, HF upload or final sampling
has been performed by this preparation step.

Eight tests cover all vote cases, target-only supervision, future-turn
exclusion, duplicate-user repair and inconsistent-history rejection. The full
converted set was also checked through the tokenizer example adapter.

Human preference means comparatively preferred, not necessarily correct:
inspection found some selected responses with factual and language mistakes.
No extra quality filter was applied beyond the user's vote-selection policy.

## Publication (2026-09-30)

The earlier preparation-only/no-upload state is superseded by publication:
[schneiderkamplab/dfm13-ai-arenaen-preferred](https://huggingface.co/datasets/schneiderkamplab/dfm13-ai-arenaen-preferred).
Public commit `effafd348e1aaa493e2fb72896d29a17fb6316ee` contains
2602 train examples, a provenance manifest and a CC-BY-4.0 dataset card.
The uncompressed JSONL is 10,623,682 bytes; its downloaded SHA256 matches
the converted source. Selected-target indices and both-good separate sides
are preserved. No tokenization or final DFM13 sampling has been performed.

Reproduce packaging/upload with
`python scripts/export_dfm13_ai_arenaen.py --upload`.
Local export: `exports_dfm13/dfm13-ai-arenaen-preferred`.
The card explicitly warns that generic all-assistant-turn loss is inappropriate:
earlier accepted turns already have independent vote-selected examples.

## International Arena Releases (2026-09-30)

All three requested `lmarena-ai/arena-human-preference-{140k,100k,55k}`
releases are downloaded, converted and registered as repeat-1 DFM13 additions
in `config/dfm13_sources.json` and the downloader's `dfm13` group.
This is source integration, not a final assembled/tokenized/sampled DFM13 mix.
Run `python scripts/prepare_dfm13_arena.py` after preparing Danish AI-Arenaen.
The registry pins each upstream revision; manifests include source file hashes,
output hashes, vote counts, language counts and exclusions.

| Release | Source rows | Converted SFT examples | Multi-turn examples | Exact duplicates removed | Invalid rows excluded |
| --- | ---: | ---: | ---: | ---: | ---: |
| 140K | 135634 | 98230 | 30600 | 51 | 67 |
| 100K | 106134 | 64939 | 11584 | 475 | 4 |
| 55K | 57477 | 39471 | 5346 | 168 | 77 |
| Total | 299245 | 202640 | 47530 | 694 | 148 |

Outputs: `data/converted_sources/dfm13/arena_human_preference_{140k,100k,55k}/train.jsonl`.
Only explicit model-A/model-B winners are included. Ties are not positive
endorsements; 55K combines ties and both-bad in one flag, which is excluded.
All source languages are retained; no 21-language filter was requested.
Language names/codes are preserved as supplied, and 55K has no row-level
language labels (stored as `unspecified`, not assumed English).

55K's JSON-encoded prompt/answer lists are interleaved; 100K already contains
message arrays. 140K's current evaluation block is uniquely matched in the
selected side of the full history, preserving preceding turns and cutting
future turns. Model identities can change between evaluations; no identity
is injected into conversation text. Ambiguous matches and empty/nontext
content are excluded, with row IDs/reasons in `rejected.jsonl`.

The conservative target policy for all three is the final winning assistant
response only, not every earlier assistant answer in the selected history.
The older releases contain conversation-level votes rather than an independent
approval of each earlier turn; this policy deliberately avoids assuming such
approval. `target_message_index` and thinking-disabled Gemma chat kwargs are
preserved. Upstream visible prose is not regenerated or silently rewritten.
Exact normalized full-message deduplication runs in order: Danish AI-Arenaen,
140K, 100K, 55K. It does not claim fuzzy, prompt-only or full inherited-DFM12
deduplication. No model inference, tokenization, upload or sampling was run
for the international additions.

### Licensing and Newer Releases

The 140K/100K cards specify CC-BY-4.0 for prompts but model-provider terms for
outputs. This supersedes any interpretation of the 140K metadata tag as a
blanket CC-BY grant for all outputs. 55K's card declares Apache-2.0.
These distinctions are retained in the source registry and row provenance.

The live official HF organization inventory and Arena research announcements
were checked on 2026-09-30. No larger/newer general text human-preference
release than 140K was found. Relevant separate candidates, not integrated:

- [arena-expert-5k](https://huggingface.co/datasets/lmarena-ai/arena-expert-5k):
  newer, approximately 5130 specialized examples; smaller, not a replacement.
- [search-arena-24k](https://huggingface.co/datasets/lmarena-ai/search-arena-24k):
  search-augmented conversations; requires preserving evidence/tool context.
- [lmsys-chat-1m](https://huggingface.co/datasets/lmsys/lmsys-chat-1m):
  larger but older conversation corpus, not an equivalent winner-labelled set.
- [leaderboard-dataset](https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset):
  leaderboard history, not millions of downloadable training conversations.

Discovery references: [official HF organization](https://huggingface.co/lmarena-ai),
[140K release](https://arena.ai/blog/opendata-july2025),
[leaderboard release](https://arena.ai/blog/arena-leaderboard-dataset).

### International Dataset Publication (2026-09-30)

The earlier international no-upload state is superseded: all three converted
sources are now public, with cards, manifests and exact source-matching JSONL.
`python scripts/export_dfm13_arena.py --upload` reproduces the exports under
`exports_dfm13/`. Each upload was downloaded at its commit and SHA256-verified.
All 202640 examples also passed the tokenizer adapter's single-target check;
15 converter tests passed. No tokenization or final sampling was performed.

| HF repository under schneiderkamplab/ | Rows | Uncompressed JSONL bytes | Commit |
| --- | ---: | ---: | --- |
| [dfm13-arena-human-preference-140k-preferred](https://huggingface.co/datasets/schneiderkamplab/dfm13-arena-human-preference-140k-preferred) | 98230 | 753912708 | `22d044259c186f07d99d3be5292ec6c8eb22c6ff` |
| [dfm13-arena-human-preference-100k-preferred](https://huggingface.co/datasets/schneiderkamplab/dfm13-arena-human-preference-100k-preferred) | 64939 | 287526045 | `7f7555a34231934cb418958747b5d93f579597cf` |
| [dfm13-arena-human-preference-55k-preferred](https://huggingface.co/datasets/schneiderkamplab/dfm13-arena-human-preference-55k-preferred) | 39471 | 98679237 | `34b349002f7c8c4867a787833c83ae9c35033ff4` |

### Third Grounded Dataset Planned 2026-10-01

User requested a separate own-source search dataset alongside RepoChat and
SearchArena. [Mimir Search](dfm13-mimir-evidence.md) records
50% Danish, 25% English, 25% other languages, 90% stable/10% current topics,
scale gates and verifiable native tool trajectories. The user subsequently
authorized generation; the initial frozen-source pilot needs no paid searches.

### Further Candidates Checked 2026-10-01 (Not Integrated)

The official Arena organization still lists no larger successor to 140K for
general text preference battles. Newer specialized Arena Expert 5K is worth
inspecting; large leaderboard row counts are not conversation counts.

- [ministere-culture/comparia-fr-arena](https://huggingface.co/datasets/ministere-culture/comparia-fr-arena):
  675K paired response turns, approximately 208K rated, primarily French.
  Same turn-level schema and explicit both-good labels as Danish AI-Arenaen.
  Card counts imply approximately 262200 selected SFT examples before
  validation/deduplication (72400 + 72200 + 2*58800). Gated; Etalab-2.0 and
  CC-BY-4.0 with third-party model-output caveat. Highest-priority new
  arena-style candidate; do not confuse unrated turns with approved responses.
- [nvidia/HelpSteer3](https://huggingface.co/datasets/nvidia/HelpSteer3):
  40476 preference samples, 40821 feedback samples, 14461 human-edit samples;
  related subsets, not independent quantities to sum. CC-BY-4.0, explicit
  train/validation splits. Human-edited outputs are attractive corrective SFT
  targets; nonzero preferences support winner SFT/DPO. Check inherited overlap.
- [HannahRoseKirk/prism-alignment](https://huggingface.co/datasets/HannahRoseKirk/prism-alignment):
  8011 conversation trees and 68371 rated utterances, mostly English. Useful
  turn-level feedback, but outputs are CC-BY-NC-4.0 plus provider terms;
  not a default inclusion for a broadly reusable training corpus.
- [lmarena-ai/webdev-arena-preference-10k](https://huggingface.co/datasets/lmarena-ai/webdev-arena-preference-10k):
  approximately 10K web-development battles; custom license prohibits dataset
  redistribution. Not compatible with our usual public derivative upload flow.
- [lmarena-ai/repochat-arena-preference-4k](https://huggingface.co/datasets/lmarena-ai/repochat-arena-preference-4k):
  code/repository conversations; inspect whether necessary repository context is
  provided before use. Prompts CC-BY-4.0, outputs under provider terms.

At the time of the initial discovery these were card-only recommendations.
Superseded on 2026-10-01 for download/inspection scope: the user requested
preferred-response sampling and retrieval-context investigation. See the
[quality and context review](/pages/dfm13-arena-quality-review.md). Local source
downloads and review samples now exist; no additional candidate inclusion or
upload has been performed.
