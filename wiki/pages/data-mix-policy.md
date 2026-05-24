# Data Mix Policy

Last updated: 2026-05-24  
Confidence: high  
Scope: Dataset inclusion policy for academic/non-commercial HRM-Text training.

## Objective

Replace or supplement Sapient's original cleaned corpus with a cleaner, more controllable mix while preserving HRM-Text's PrefixLM training format:

```text
instruction span + response span
```

This repo does not currently train on raw documents as ordinary causal-LM pretraining. Raw text must be converted to continuation rows:

```text
condition = direct
instruction = ""
response = document chunk
```

## Continuation Data

Only Danish continuation data is currently allowed:

- Include: `danish-foundation-models/danish-dynaword`
- Exclude: Common Pile. Common Pile was removed from the downloader manifest.

Recommended continuation share: capped auxiliary slice, roughly 5-10% of total tokens if used.

## Sapient Cleaned Policy

Sapient cleaned data is included only after source filtering.

Broad exclusions:

- ReClor
- SciBench
- ScienceQA
- most FLAN
- most Tasksource

Narrow FLAN/Tasksource allow overrides are documented in [[pages/source-filtering]].

## Include / Prefer

Academic/non-commercial use permits CC-BY-NC sources, but provenance and GDPR/PII concerns still matter.

Good instruction/reasoning sources:

- Sapient non-denied cleaned sources
- `synquid/danish-verifiable-reasoning`
- `synquid/translation-100k`
- `synquid/ifbench-train`
- Oliver Kinch Danish instruction/backtranslation, QA, summarization, and translation sources with public/OPUS provenance:
  - `oliverkinch/instruct-bt` remains gated and optional.
  - Added open sources: `multi-wiki-qa-high-quality-subset`, `eur-lex-sum-instruct`, `machine-translation-da-{en,uk,ar}`, `danmarks-statistik-bt`, `tidsskrift-dk-bt`, `doab-da-bt`, `danish-university-portals-bt`, `eur-lex-bt`, `dynaword-bt`, and `dst-table-prompts-bt`.
- AllenAI Dolci SFT variants
- AllenAI Tulu SFT/persona/reasoning variants
- Nemotron instruction/SWE/terminal/agentic/multilingual, capped by objective
- DynaWord as the only raw continuation source
- Local DBC/LexDK/OPUS instruction-style additions under `data/downloads/datasets`: DBC abstracts/reviews/Faktalink/Forfatterweb, LexDK articles, and OPUS Danish-English translation shards when both language sides are present. These are converted to supervised bibliographic/article-writing/translation tasks, not empty-instruction raw continuation.

Gated sources not downloaded in the current `--exclude-gated` run:

- `danish-foundation-models/laerebogen`
- `synquid/wiki-instruct-da`
- `oliverkinch/instruct-bt`
- `synquid/mt-da-deepseek`
- Synquid WildChat variants

## Oliver Kinch Source Policy

Reviewed on 2026-05-21 from Hugging Face dataset metadata, cards, and sample schemas.

Include:

- Public Danish backtranslation/instruction datasets where targets come from CC-BY, EU legal, DST, DOAB, university portal, tidsskrift.dk, or DynaWord-style public provenance.
- Public Danish QA from Wikipedia-derived `multi-wiki-qa-high-quality-subset`.
- Danish translation pairs from `machine-translation-da-en`, `machine-translation-da-uk`, and `machine-translation-da-ar`, with sampling caps because `da-en` is much larger than the other additions.

Exclude by default:

- Raw Oliver Kinch document corpora such as `danish_wikipedia`, `eur-lex`, `tidsskrift-dk`, `tidsskrift-dk-en`, `danmarks-statistik`, `danish-university-portals`, `doab-da`, and `dst-table-prompts`; the current plan allows only Danish DynaWord as raw continuation data.
- `oliverkinch/dsk-bt`; the card says it is derived from non-public internal DSK material and is not intended for public redistribution.
- `oliverkinch/da-bird`; useful as an evaluation/text-to-SQL benchmark, but its Harbor task layout and CC-BY-SA inherited BIRD tasks make it a poor fit for the current mixed training corpus.
- `oliverkinch/dynaword-no-bt`; Norwegian rather than Danish.
- Small/no-license synthetic/demo datasets (`life-in-the-uk-multiple-choice`, `synthetic-qa`, `synthetic-qa-context-qa`, `mt_da_uk`) unless separately justified.

Confidence: medium for source-card safety; high for local manifest/converter support after `py_compile` and downloader dry-run.

## Exclude / Avoid

- AllenAI WildChat was removed from the downloader manifest by decision.
- Common Pile was removed from the downloader manifest by decision.
- Raw non-Danish continuation corpora should not be used in the current plan.
- Local DBC raw/crawl/continuation files are denied by default. Only the instruction-style DBC, LexDK, and OPUS families listed above are allowlisted.

## Sampling Shape

For a 40B-token target, a reasonable target allocation remains:

- 35-45% math/reasoning/STEM
- 25-35% Danish instruction/chat/translation
- 10-20% general instruction/chat
- 5-15% code/SWE/terminal/agentic
- 0-10% Danish raw continuation

Use token-budgeted sampling rather than row-count caps alone.

## Original Plus Mixed Danish Instruction Rich

Verified locally on 2026-05-24 from:

- `data/show_analytics_original_sapient.md`
- `data/show_analytics_original_plus_mixed_danish_instruction_rich.md`
- `data/tokenized_original_plus_mixed/union_manifest.json`

The `original_plus_mixed_danish_instruction_rich` sample preserves the original Sapient portion almost exactly, then adds mixed/Danish sources on top.

Source union facts:

- `data/tokenized_original_plus_mixed/union_manifest.json` records `original_tasks: 5212`.
- All `5212` original Sapient tokenized tasks are present in the original+mixed union.
- `mixed_tasks_added: 226`.
- `include_mixed_sapient: false`, so duplicate Sapient tasks from the mixed tree are skipped rather than added twice.

Covered-token comparison across 4 epochs:

| Sample | Original Sapient covered tokens | Global covered tokens |
|---|---:|---:|
| `sampled_original_sapient` | `56,140,714,711` | `56,140,714,711` |
| `sampled_original_plus_mixed_danish_instruction_rich` | `56,140,181,363` | `110,736,199,356` |

Difference in the original Sapient portion: `-533,348` tokens, about `0.00095%`. This is consistent with sampling/shuffling boundary effects, not intentional reweighting of the original subset.

Per-category ratios for original Sapient categories in `original_plus_mixed_danish_instruction_rich` versus `original_sapient`:

| Category | Ratio |
|---|---:|
| `Platypus` | `1.000000` |
| `SYNTH` | `1.000000` |
| `acereason` | `0.999996` |
| `ampsmathematica` | `0.999924` |
| `dmmath` | `0.999944` |
| `flan` | `0.999960` |
| `openmathinstruct2` | `1.000217` |
| `openthoughts2` | `0.999905` |
| `sudoku_extreme` | `1.000000` |
| `tasksource` | `0.999956` |
| `textbookreasoning` | `1.000000` |

Task/file-level comparison:

- Matching original tasks: `5212 / 5212`
- Missing original tasks: `0`
- Exact same covered-token count: `2645 / 5212`
- Within `10,000` tokens: `4738 / 5212`
- Within `100,000` tokens: `5193 / 5212`
- Largest observed task difference: `openmathinstruct2__cot.parquet`, about `+902,328` covered tokens, ratio `1.000279`.

Conclusion: use `original_plus_mixed_danish_instruction_rich` when the goal is to keep the original Sapient training signal essentially unchanged while adding roughly `54.6B` extra covered tokens over 4 epochs from the mixed/Danish additions.

Confidence: high.

## Mixed English/Danish Filtered 2x-Original Cap

Verified/created locally on 2026-05-24.

The first mixed-only filtered sample used `data_io/prefix_config.yaml` against `data/tokenized_mixed` and produced a very large corpus:

- Output: `data/sampled_mixed_english_danish_filtered`
- Analytics: `data/show_analytics_mixed_english_danish_filtered.md`
- Per-epoch `metadata.total_length`: `70,644,435,216` tokens
- 4-epoch covered tokens: `282,577,740,862`

Cause: `data/tokenized_mixed` task names include source prefixes such as `sapient_cleaned__data_clustered__SYNTH__...`, but the shared `data_io/prefix_config.yaml` uses unprefixed Sapient rules such as `SYNTH__`, `flan__`, and `dmmath__`. Those rules therefore did not match the filtered Sapient tasks in the mixed-only tokenized tree, causing most filtered Sapient files to be sampled uncapped.

A dedicated capped config was added:

```text
data_io/prefix_config_mixed_2x_original.yaml
```

Target ceiling:

- Original Sapient sample: `56,140,714,711` covered tokens over 4 epochs.
- Original per-epoch size: `14,035,178,677.75` tokens.
- 2x ceiling: `28,070,357,355.5` tokens per epoch.

Dry-run estimate after applying the new config with PrefixLM truncation/filtering:

- Estimated per-epoch sampled tokens: `24,630,898,966`
- Ratio to original per-epoch size: `1.755x`
- This is below the `2x` ceiling.

Final completed sample:

- Output: `data/sampled_mixed_english_danish_filtered_2x_original`
- Analytics: `data/show_analytics_mixed_english_danish_filtered_2x_original.md`
- Hydra config: `config/data/mixed_english_danish_filtered_2x_original.yaml`
- `metadata.total_length`: `24,630,436,020` tokens per epoch
- 4-epoch covered tokens: `98,521,744,082`
- Ratio to original per-epoch size: `1.755x`
- Unique sampled tokens: `55,258,504,135 / 78,082,414,846` (`70.77%`)
- Directory size: about `625G`

Note: `sample_tokenized.py` copies the full token bank into output `tokens.npy` before writing capped epoch indices, so the disk footprint remains large even though the epoch index budget is capped.

Estimated largest per-epoch category shares:

| Category | Estimated tokens/epoch | Share |
|---|---:|---:|
| `sapient_cleaned` | `8,129,060,084` | `33.0%` |
| `danish_dynaword` | `3,093,170,660` | `12.6%` |
| `nemotron_multilingual` | `3,001,252,991` | `12.2%` |
| `allenai_big_reasoning_traces` | `1,624,580,477` | `6.6%` |
| `dolci_instruct_sft` | `1,380,220,345` | `5.6%` |
| `dolci_instruct_sft_no_tools` | `962,106,919` | `3.9%` |
| `allenai_tulu_v2_sft_mixture` | `902,702,844` | `3.7%` |
| `allenai_tulu_3_sft_mixture` | `831,587,284` | `3.4%` |

Sampling was launched in tmux:

```bash
cd /work/dfm/HRM-Text/data_io
/home/ucloud/miniforge3/envs/hrm/bin/python sample_tokenized.py \
  tokenized_path=../data/tokenized_mixed \
  output_path=../data/sampled_mixed_english_danish_filtered_2x_original \
  prefix_config_path=prefix_config_mixed_2x_original.yaml \
  epochs=4 \
  concat_workers=4 \
  > ../data/show_analytics_mixed_english_danish_filtered_2x_original.md \
  2> ../logs/sample_mixed_english_danish_filtered_2x_original.err
```

Session:

```bash
tmux attach -t hrm_sample_mixed_2x_original
```

Confidence: high.
