---
type: Runbook
title: DFM12 Multilingual Component Preparation
description: Independent identity, instruction, transformation and OPUS components without final DFM12 sampling.
tags: [dfm12, multilingual, identity, synthetic-data, opus]
status: draft
last_updated: 2026-09-24
confidence: high
---
# DFM12 Multilingual Component Preparation

The implementation is the repo-root `dfm12` Python package. Its README documents
commands and operational contracts. Run `python -m dfm12 --help` from the
repository root. Default workspace: `data/dfm12`.

## Scope and Boundaries

Decision, 2026-09-24: build additions independently; **do not assemble or sample
the final DFM12**. Another thread is preparing additional acceptability and
correction datasets for Polish, Swedish and other languages. Do not duplicate
that work or change its outputs. No current training/evaluation/scheduler
configuration is modified by these commands.

The future mix adds to inherited allocations. New instruction components start
at repeat 1. Corpus-level allocation remains deferred until the full DFM12
source set is settled.

## Identity and Language Contracts

- Target 1,000 accepted identity conversations in each of en, da, nl, nb, nn,
  sv, is, fo and pl: 9,000 total. Vary Q&A and multi-turn contexts.
- Use the owner-specified names and leadership, not inferred author rankings.
- Separate common Mimir identity from `xl-full-bp` and `generic` profiles.
  XL has 16 layers in each L/H module, six L passes and two H passes.
- Important historical distinction: the Mimir v1 report describes BP5 with
  warmup. It does not support a claim that v1 used full backpropagation
  throughout. The full-BP claim belongs to the new owner-specified profile.
- Fact registry: `dfm12/identity_facts.yaml`; primary report references are
  arXiv 2608.13517v1 and 2605.20613v1.
- English/Dutch DaLA already name their languages. Preserve those prompts
  and yes/no labels. NB and NN are distinct languages for these task contracts;
  generic Norwegian labels are not automatically mapped to Bokmal.

## Generation and Audit

Teacher and auditor: `google/gemma-4-26B-A4B-it`, with independent prompts.
Pilot defaults to 20 identity requests per language. Bulk identity generation
and bulk audits require `pilot-approval.json` covering all nine languages and
the chosen model, with review evidence. Low-resource fluency must not be
inferred from a teacher merely accepting its own output.

The clients use explicit OpenAI-compatible endpoints, start no servers, and
default to 32 concurrent requests per endpoint. SQLite leases prevent duplicate
claims across client processes; expired leases recover after 15 minutes and
stale owners cannot overwrite newer results. Four total request attempts,
persisted failure reasons, strict JSON/score validation, no acceptance of
truncated generations.

## Transformations and Translation

Each new language targets 25% of the **unique accepted Danish examples** in
each corresponding transformation task. Measure the expanded inherited corpus,
not outdated HF-card counts. Tasks are denoising, prefix completion, span filling
and paragraph reordering. Deterministic sampling spans approved source files;
audit judges original quality, task validity and language preservation. Genuine
source exhaustion is reported, not masked by repetitions.

For OPUS, future sampled-token caps refer to the repaired English-Danish
baseline T, both directions together:

| Pair family | Pair count | Cap per pair |
| --- | ---: | ---: |
| English with Swedish, Dutch, NB, NN, Polish | 5 | T / 4 |
| Pairs among Danish and the seven new languages | 28 | T / 16 |

Direct pairs only; no English pivots, synthetic fill or aggressive repeats.
License allowlist: public domain, CC0, CC-BY, CC-BY-SA. Exclude NC, ND and
unclear rights. Corpus-version approvals retain evidence, source archive hashes,
README/LICENSE and attribution references. Tatoeba's actual archive README was
verified to specify CC BY 2.0 FR. Other OPUS entries stay on review hold.

## Source Selection

The pinned inventory contains 20 source/config entries. Six initially approved
download routes: English/Dutch DaLA, Dutch UltraChat train_sft, and the Dutch,
Polish and Swedish OpenEuroLLM Dolci configurations. Do not add the Swedish
mirror as a second source.

Review-held entries cover Scandinavian instruction data, Norwegian/Icelandic/
Faroese DynaInstruct, PLLuMIC plus synthetic extension, PLLuM-Align chosen
responses, Danish DynaInstruct increments, and six DynaWord repositories for
seven languages. The Norwegian DynaInstruct file selection excludes NorQuAD
and FLEURS pending evaluation-overlap review. Unknown-license island-language
instruction constituents stay held. DynaWord requires explicit high-quality
file selection, not indiscriminate OCR/web inclusion.

The Danish composite requires an inherited-content fingerprint index and
reviewed files. Exact normalized-message deduplication is not semantic
decontamination. Tool-bearing or legacy-template conversations are rejected
with reason counts, not flattened into malformed supervision.

## Local Progress, 2026-09-24

- Downloaded both DaLA training configurations, Dutch UltraChat train_sft,
  and nl/pl/sv OpenEuroLLM Dolci files into `data/dfm12/downloads`.
- Converted 200-row pilots per route with the actual DFM11 tokenizer/template:
  1,194 valid conversations; six user-only Dolci rows rejected.
- Inventoried all 33 OPUS language pairs. Tested Danish-Faroese preparation on
  seven Tatoeba pairs; both directions retained for joint audit.
- Prepared 180 identity generation requests and 607 audit requests in the
  local queue. **No generation/audit server or GPU client was launched**:
  all eight GPUs were occupied by existing work.
- Unit/integration tests cover concurrency, leases, retries, metadata isolation,
  language variants, deterministic transformations, accepted-only exports,
  pilot gates, token-budget units and actual training-template rendering.

Outstanding: source reviews/access where required, full inherited Danish
accepted-row baseline, inherited repaired-OPUS sampler report for absolute
token caps, multilingual teacher pilot, bulk generation/auditing, accepted
exports and tokenization. Do not describe these as completed datasets.

Related: [DFM12 plan](/pages/dfm12-plan.md),
[broad transformation history](/pages/dfm8-plan/broad-synthetic-common-pile-and-dynaword-scaling.md).

## CPU Campaign, 2026-09-24

Supersedes the pilot-only preparation status above: full CPU preparation was
launched, not completed, with `python -m dfm12.cpu_prepare` and
`python -m dfm12.cpu_transforms` in independent detached tmux sessions.
Logs: `data/dfm12/cpu-preparation.log` and `data/dfm12/cpu-transforms.log`.
Download/conversion state: `data/dfm12/cpu-preparation.json`.

The first campaign downloads pinned DynaWord source files (download does not
approve their inclusion), converts the six ready instruction sources, and
pre-tokenizes 10,000-conversation shards with up to 16 CPU workers. These
outputs live under `tokenized_unaudited`, not `accepted` or any sampled mix.
They cannot be included wholesale after an audit rejects rows.

The second campaign retrieves the four published expanded Danish accepted
transformation datasets, records revisions, measures unique conversations,
then prepares multilingual transformation candidates at the agreed 25%
accepted target plus a 1.5x initial candidate allowance. It waits for completed
download receipts. Selected constituents are explicit in
`dfm12/cpu_transforms.py`: educational/scientific/government Dutch, reference
Norwegian, reference/parliamentary Swedish, reference/scientific/parliamentary
Icelandic, Faroese Wikipedia/BLARK, and Polish Wikipedia/government/parliament.
Source cards were inspected; corpus attribution and share-alike obligations
remain applicable. No social-media or bulk historical OCR sources are selected.
Norwegian Wikipedia rows lack language columns; source filenames explicitly
distinguish Bokmal and Nynorsk, with separate per-language quotas.

No GPU workers, teacher servers, training/evaluation changes, or final sampling.
Full candidate quality auditing and multilingual pilot approval remain pending.

Translation CPU preparation was separately launched with
`python -m dfm12.cpu_translations`. Log: `data/dfm12/cpu-translations.log`;
per-pair state: `data/dfm12/opus/preparation-status.json`. It downloads and
prepares every currently approved direct corpus across the 33-pair inventory,
retains both translation directions for joint auditing, and reuses matching
completed receipts. At launch only Tatoeba is approved (32 pairs); Faroese-Dutch
has no approved corpus. This first pass is not the full intended translation
volume: other corpus versions still require license review before inclusion.
No pivot translations, GPU audits, or final sampling are performed.

## OPUS Quality-First Review, 2026-09-24

User refinement: avoid web-mined and other low-quality material even when
licenses permit use. Prefer named human-translated institutional prose.
`dfm12/opus_review.py` retrieves versioned OPUS metadata at a pinned GitHub
revision; evidence is under `data/dfm12/opus/review_evidence/` and the inventory
of reported licenses is `license-review.json`. Metadata screening is not a
completed row-quality audit or a guarantee of legal clearance.

`dfm12/opus_decisions.py` records these conservative preparation decisions:

| Source | Decision | Basis / limitation |
| --- | --- | --- |
| Tatoeba | Retain | Existing release-license check; short community translations still need auditing |
| ELRC-2707-EMEA, ELRC-2725-EMEA v1 | Prepare | Specific EN-NL / EN-SV medicinal-document translations, CC-BY-4.0; check PDF/alignment artifacts |
| ELRC-401-Swedish_Labour_Part2, ELRC-406-Swedish_Labour_Part1 v1 | Prepare | Swedish labour-agency parallel text, reported public domain |
| ELRC-403-Rights_Arrested v1 | Prepare | Translated rights notice, CC-BY-4.0; small and repetitive |
| ELRC-518-www.regjeringen.no v1 | Prepare | Named Norwegian government EN-NO parallel text, CC-BY-4.0; verify NB/NN at audit |
| ELRC-84-Dutch_Government v1 | Prepare | Named Dutch government text, CC0 |
| ParaCrawl, MultiParaCrawl, CCMatrix, CCAligned, MultiCCAligned, NLLB, HPLT, MultiHPLT, XLEnt | Exclude from this mix | Web-mined alignment/provenance concerns; do not use to fill shortages |
| WikiMatrix, wikimedia, Wikipedia | Exclude from this mix | Automatically mined encyclopedia alignment is not reliable translation supervision merely because text is licensed |
| Ubuntu, GNOME, KDE4, KDEdoc, PHP, translatewiki, tldr-pages, LinguaTools-WikiTitles | Exclude from this mix | Short software/title fragments, not priority prose supervision |
| OpenSubtitles, bible-uedin, Tanzil | Exclude from this mix | Subtitle alignment/context problems or narrow religious domain; not a blanket claim of poor text quality |
| ELRC-EMEA aggregate | Hold | Parent metadata says BY-NC, version metadata says BY; no blanket aggregate approval |
| Europarl, DGT, JRC-Acquis, EUbookshop, EMEA | Hold, promising | Stronger provenance, but custom/unclear terms must not be relabeled CC/PD |
| GlobalVoices | Hold, promising | Human-translated editorial prose; publisher CC-BY-3.0, but release attribution/document mapping needs review |
| TED/TED2020/NeuLab-TedTalks, QED | Hold | Usage/research restrictions, not blanket approved CC-BY rights |
| Other ELRC/ELRA entries | Hold | Exact numbered release and rights review needed; not approved by name prefix |

Evidence examples: [OPUS source registry](https://github.com/Helsinki-NLP/OPUS/tree/main/corpus),
[Global Voices publisher and translation description](https://globalvoices.org/about/).
The dated runtime decisions cover every pair/corpus/version entry in
`data/dfm12/opus/review-decisions.json`; the pre-edit inventory is backed up.
Preparation approvals do not certify individual rows. Retain source attribution,
deduplicate across corpora and directions, and audit language and parallelness.
No new GPU work or final sampling is authorized by this review.

## CPU Work Audit, 2026-09-24

At the post-OPUS-review check, the instruction campaign was converting Dutch
UltraChat (Dutch/Polish/Swedish Dolci follow sequentially); EN/NL DaLA staging
tokenization was complete for 3,065,100 conversations combined. All six
DynaWord repositories were downloaded. Transformation preparation had finished
NL, NB/NN, SV and IS and was processing FO, with PL next.

The Tatoeba-only translation campaign had exited. The seven subsequently
approved numbered ELRC releases were **not yet being prepared**; rerunning
`python -m dfm12.cpu_translations` is needed to extend the affected pair outputs.
Other CPU backlog: resolve Scandinavian/PLLuM source holds and adapters, build
inherited-conversation fingerprints for Danish increments, check held-out
overlap and cross-source duplicates, measure the inherited OPUS token baseline,
and prepare stratified multilingual pilot/review material. Identity generation
and quality audits still require a teacher; final sampling remains deferred.
