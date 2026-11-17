---
type: Dataset Catalog
title: Dataset Entities
description: Inventory of datasets, source policy, and conversion decisions.
tags: [datasets, catalog, conversion]
status: stable
last_updated: 2026-10-07
confidence: medium
---
# Dataset Entities

## BAAI Access Candidates — 2026-10-07

User-selected candidates are [COIG-PC](https://huggingface.co/datasets/BAAI/COIG-PC)
for Chinese instruction data and
[IndustryCorpus2](https://huggingface.co/datasets/BAAI/IndustryCorpus2)
for potential domain-specific grounding, subject to
[source filtering](/pages/source-filtering.md). Access is not admission to the
training mix. Skip requests for broad web corpora and audio/multimodal datasets
in this access round.

Use University of Southern Denmark and Denmark in access forms. The user
reported that an HF token does not authenticate these browser forms; a logged-in
Firefox session was available and both forms were inspected on 2026-10-07.
COIG-PC requires name, affiliation, country, license acknowledgement and a
non-commercial-only agreement. IndustryCorpus2 requires organization, country
and agreement not to conduct experiments that harm human subjects. Both forms
state that the HF email and username are shared with repository authors.

Initial status (superseded by the browser observation below on 2026-10-07):
affiliation/country fields prepared; neither form submitted by the agent.
Follow-up: IndustryCorpus2 now visibly reports access granted; the agent did
not submit its form. The user supplied Peter Schneider-Kamp as the name;
COIG-PC's browser form already contains that name, the affiliation and country,
and a checked non-commercial agreement. Its final Acknowledge license button
remained present; submission confirmation was pending at that observation.
Final status, 2026-10-07: after the user's explicit confirmation, the agent
clicked COIG-PC's Acknowledge license. Reopening its page verified "You have
been granted access to this dataset." Both candidates now have browser-verified
access; no dataset downloads or training admission were performed in this task.
IndustryCorpus2's card describes broad aggregated sources including Pile,
BigCode and OpenWebMath; any later use requires component-level selection.

## Local Andersen Modernization

- `/work/dfm/andersen/pairs_chunked_train.jsonl`
  - Status: include in DFM10 at repeat 20.
  - Conversion: already formatted as `system`/`user`/`assistant` messages and
    rendered with the Gemma 4 native chat template.
  - Rows: 1,068; 1,205,157 unique rendered tokens; about 24.10M tokens per
    DFM10 epoch after repetition.
- `/work/dfm/andersen/pairs_chunked_val.jsonl`
  - Status: evaluation only; never include in training tokenization.
  - Rows: 119 paragraph chunks.
  - Evaluation: zero-shot modernization with sentence GLEU and chrF3++.
  - Caveat: keys are disjoint, but all 71 validation story IDs also occur with
    different chunks in training.

See [DFM10 Plan](/pages/dfm10-plan.md) for hashes, commands, and verified
pipeline state.

## Raw Continuation

- `danish-foundation-models/danish-dynaword`
  - Status: include
  - Conversion: `text` -> empty-instruction continuation chunks
  - Notes: only raw continuation source currently allowed

## Sapient Cleaned

- `sapientinc/HRM-Text-data-io-cleaned-20260515`
  - Status: include after filtering
  - Conversion: already mostly `condition/instruction/response`
  - Notes: FLAN and Tasksource are denied broadly with narrow allow overrides

## Synquid

- `synquid/danish-verifiable-reasoning`
  - Status: include
  - Conversion: `prompt` -> instruction; `reasoning + target` -> response; `condition=cot`
- `synquid/translation-100k`
  - Status: include
  - Conversion: `prompt/target`, `condition=direct`
- `synquid/ifbench-train`
  - Status: include
  - Conversion: message rows to assistant-turn examples
- Gated Synquid datasets are not present in the `--exclude-gated` download run.
- Access recheck on 2026-05-27: Hub metadata was visible for the previously
  gated datasets, but the local shell had no configured HF token
  (`HF_TOKEN`/cached token absent), so `datasets.load_dataset(...,
  streaming=True)` still failed with gated-dataset authentication errors.
  Export `HF_TOKEN` in the shell before downloading or schema sampling.
  Confidence: high for local token state and metadata visibility.
- `synquid/wildchat-100k-qwen`
  - Status: superseded by `synquid/wildchat-100k-qwen-messages`; do not use.
  - Access recheck on 2026-05-27 with an explicit user-provided HF token still
    failed at row level: Hugging Face reported the dataset is gated and access
    must be requested/approved. Hub metadata remains visible, including
    `data/train.jsonl`, but the row schema cannot be verified until access is
    actually granted.
  - Confidence: high for access failure and supersession.
- `synquid/wildchat-100k-qwen-messages`
  - Status: include, tightly capped.
  - Access recheck on 2026-05-27 with an explicit HF token succeeded. Schema:
    `messages` plus generation/source metadata such as `model`,
    `source_record`, `system_prompt_leak`, and `followup_system_prompt_leak`.
  - Conversion: existing `messages` JSONL converter expands assistant turns into
    PrefixLM instruction/response rows.
  - Policy note: the assistant responses are synthetic, but the prompts derive
    from WildChat. A local 2026-06-01 regex scan of 99,688 prompt rows found
    email-like, phone-like, URL, and contact/address/name-word matches,
    including examples with order names/addresses/emails and named family
    members. Many hits are false positives, but the source has real user-prompt
    PII/GDPR risk. Project decision on 2026-06-01: keep it in the mix with the
    existing tight cap and prioritize it for later PII scrubbing rather than
    excluding it now.
  - Audit-evidence reconstruction, 2026-08-17: the exact aggregate counts are
    preserved in repository history (introduced by commit `332260d`) and in
    the DFM4 policy notes, and the scanned 99,688-row source remains available
    at `data/downloads/datasets/synquid_wildchat_100k_qwen_messages/data/train.jsonl`.
    No original scan script, regex specification, matched-row manifest, or
    removal report was found in the repository. A fresh broad-regex check of
    all user turns reproduced the scale but not the exact historical counts
    (`64` email-like, `2,067` phone-like, and `1,794` URL rows). Therefore the
    2026-06-01 result is evidence of risk screening, not a reproducible
    anonymisation/PII-removal audit or proof that retained rows are PII-free.
  - Upstream consent evidence: the WildChat paper reports affirmative opt-in
    before use of its public GPT-3.5/GPT-4 chatbot. Its two-step flow disclosed
    collection of chats and technical data; use for research, service
    improvement, and product development; third-party sharing/publication; and
    retention, followed by a separate confirmation for publication/sharing.
    The paper's summary does not separately state "training arbitrary
    third-party models." Treat this as evidence of collection/use/publication
    consent, but not by itself as a conclusive GDPR determination or
    unambiguous purpose-specific consent for this project's model training.
    Project decision, 2026-08-17: accept the documented affirmative consent as
    express permission for the current research model training. This resolves
    the source-expression permission question for this use; it does not waive
    GDPR data-minimisation, PII screening, security, retention, or data-subject
    rights obligations.
  - Sampling: `data_io/prefix_config_dfm4.yaml` currently caps
    `synquid_wildchat_100k_qwen_messages__` at `50,000` rows per file.
  - Confidence: high for access/schema/local scan; medium for final inclusion.

## Web-Sourced Instruction/QA

- `TIGER-Lab/WebInstruct-verified`
  - Status: include, Article-3/source-route dependent.
  - Local schema: 228,736 train rows with `question`, `answer`,
    `answer_type`, `category`, and `difficulty`; no per-row source URL in the
    local Parquet schema.
  - Policy note: Apache-2.0 dataset card says the authors traced WebInstruct
    entries back to original web pages and re-crawled human-written
    question-answer pairs. This is high-value reasoning data but should be
    documented as web-recrawl-derived rather than provenance-free.
- `HuggingFaceH4/no_robots`
  - Status: include only as a capped small human-instruction source.
  - Local schema: 9,500 train rows with `prompt`, `messages`, and `category`.
  - Policy note: the name is unrelated to robots.txt. The issue is missing
    source/annotator/PII documentation in the card. A simple 2026-06-01 local
    scan found 9 email-like and 37 phone-like matches; some are tasks about
    redacting PII rather than necessarily real personal data.

## Oliver Kinch

Included in `scripts/download_training_datasets.py`:

- `oliverkinch/instruct-bt`
  - Status: include in the DFM mix.
  - Conversion: existing `messages` Parquet converter expands assistant turns
    into PrefixLM instruction/response rows.
  - Access recheck 2026-05-27 with an explicit HF token succeeded. Schema:
    `messages`, `prompt_id`, `section_heading`, `subset`, `title`, `url`.
  - Sampling: `data_io/prefix_config_dfm.yaml` repeats
    `oliverkinch_instruct_bt__` 5 times because the dataset is small.
- `oliverkinch/multi-wiki-qa-high-quality-subset`
  - Status: include
  - Conversion: `context + question` -> instruction; first answer text -> response
  - Notes: downloads only `da/train-*.parquet` to avoid duplicate short views
- `oliverkinch/eur-lex-sum-instruct`
  - Status: include
  - Conversion: `prompt` -> instruction; `target` -> response
- `oliverkinch/machine-translation-da-en`
- `oliverkinch/machine-translation-da-uk`
- `oliverkinch/machine-translation-da-ar`
  - Status: include with caps
  - Conversion: bidirectional translation rows from `danish` and the target language column
  - Notes: `da-en` is much larger than the other Oliver Kinch additions and should be capped during sampling
- `oliverkinch/danmarks-statistik-bt`
- `oliverkinch/tidsskrift-dk-bt`
- `oliverkinch/doab-da-bt`
- `oliverkinch/danish-university-portals-bt`
- `oliverkinch/eur-lex-bt`
- `oliverkinch/dynaword-bt`
- `oliverkinch/dst-table-prompts-bt`
  - Status: include
  - Conversion: `prompt` -> instruction; `target` -> response

Excluded by default:

- Raw Oliver Kinch corpora, because the current continuation policy allows only Danish DynaWord as raw text.
- `oliverkinch/dsk-bt`, because the card describes non-public internal DSK source material and says it is not intended for public redistribution.
- `oliverkinch/da-bird`, because it is better treated as a text-to-SQL benchmark/eval corpus than as SFT training data.
- `oliverkinch/dynaword-no-bt`, because it is Norwegian. Superseded for
  multilingual DFM16 on 2026-10-27; see [DFM16 preparation](../pages/dfm16-plan.md).

## Dolci

- `allenai/Dolci-Instruct-SFT`
- `allenai/Dolci-Instruct-SFT-No-Tools`
- `allenai/Dolci-Instruct-SFT-Tool-Use`
- `allenai/Dolci-Instruct-SFT-Tool-Use-SA`

Status: include. Conversion depends on schema, usually messages or prompt/response style.

## AllenAI

Included manifest candidates:

- Tulu SFT mixtures and persona subsets
- SciRIFF train mix
- instruction-following verified/constraint datasets
- verifiable reasoning
- code meta reasoning
- OpenMath/RLVR subsets
- big reasoning traces

Removed:

- AllenAI WildChat 1M and 4.8M were removed because real chat data is higher PII/provenance risk.

## Nemotron

Included with caps recommended:

- Instruction Following Chat v2, reasoning off
- Terminal Corpus
- Agentic v2
- SWE v2
- Multilingual v1

Notes: mostly non-Danish. Useful for capability transfer but should not dominate Danish/reasoning mix.

## Local DBC

Source locations after local cleanup:

```text
data/downloads/datasets/dbc
data/downloads/datasets/lexdk
data/downloads/datasets/opus
```

Status: include only selected instruction-style families; deny removed/raw/crawl/continuation DBC-style files by default.

Allowlisted in `config/data/source_filter.yaml`:

- `dbc/dbc-abstracts_*.jsonl.gz`
  - Conversion: bibliographic metadata (`title`, `creators`, `subjects`) becomes the instruction; `text` becomes the requested abstract/summary response.
  - Sampling: `data_io/prefix_config.yaml` caps `dbc__dbc-abstracts_` at `50,000` rows per shard.
- `dbc/dbc-reviews.jsonl.gz`
  - Conversion: `metadata.is_review_of` becomes the material id in the instruction; `text` becomes the review response.
  - Sampling: capped at `100,000` rows.
- `dbc/dbc-faktalink.jsonl.gz`
  - Conversion: article `text` is split into title plus section heading/body pairs. Each row asks for a named section of a Danish Faktalink article; section body is the response.
  - Sampling: repeated `10` times because the converted set is small.
- `dbc/dbc-farfatterweb.jsonl.gz`
  - Conversion: article `text` is split into title plus section heading/body pairs. Each row asks for a named section of a Danish Forfatterweb article; section body is the response.
  - Sampling: repeated `10` times because the converted set is small.
- `lexdk/lexdk_articles.jsonl.gz`
  - Conversion: `metadata.title`, optional `metadata.clarification`, and `metadata.url` become an instruction to write a Danish encyclopedia article; `text` is the response.
  - Sampling: repeated `3` times.
- `opus/opus_da_en.jsonl.gz`
  - Conversion: direct `da`/`en` sentence pairs become both Danish-to-English and English-to-Danish translation instructions. The optional `source` field is included as an OPUS source note.
  - Current local state on 2026-05-23: OPUS was rescanned and now contains a single `2.4G` `opus_da_en.jsonl.gz` file with rows shaped as `id`, `da`, `en`, and `source`. The stale old `opus-da_*.jsonl.gz` symlinks were removed by rebuilding `data/filtered_sources` with `--force`.
  - Sampling: cap `opus__` at `200,000` rows per converted shard.

Smoke test on 2026-05-23 converted representative files successfully:

```text
dbc-abstracts_0001: 544,036 rows
dbc-reviews:        214,035 rows
dbc-faktalink:        5,991 rows
dbc-farfatterweb:     2,831 rows
lexdk_articles:     108,711 rows
opus_da_en:      58,522,188 rows
```

Confidence: high for observed schemas and local converter smoke test; medium for final sampling balance until full token counts are inspected.

## Excluded

- Common Pile was removed from the downloader manifest.
- Non-Danish raw continuation is not part of the current plan.
