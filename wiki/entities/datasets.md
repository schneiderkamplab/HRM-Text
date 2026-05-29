# Dataset Entities

Last updated: 2026-05-27  
Confidence: medium  
Scope: Dataset inventory and conversion policy.

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
  - Status: include in the DFM mix, tightly capped.
  - Access recheck on 2026-05-27 with an explicit HF token succeeded. Schema:
    `messages` plus generation/source metadata such as `model`,
    `source_record`, `system_prompt_leak`, and `followup_system_prompt_leak`.
  - Conversion: existing `messages` JSONL converter expands assistant turns into
    PrefixLM instruction/response rows.
  - Policy note: if access is granted, include only with a tight cap because the
    source is generated answers to WildChat prompts, and WildChat provenance has
    higher PII/provenance risk than synthetic or curated instruction datasets.
  - Sampling: `data_io/prefix_config_dfm.yaml` caps
    `synquid_wildchat_100k_qwen_messages__` at `50,000` rows per file.
  - Confidence: high for access/schema and local manifest support; medium for
    cap size.

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
- `oliverkinch/dynaword-no-bt`, because it is Norwegian.

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
