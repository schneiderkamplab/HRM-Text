# Changelog

All notable changes to DFM Dyna-Instruct will be documented in this file.

## [0.1.3] - 2026-06-09

- Re-added `da-refusals` since license was clarified

## [0.1.2] - 2026-06-08

- Added `creation_approach` metadata field to dataset schema with four labels: `synthetic`, `semi-synthetic`, `collected`, `human`
- Added Creation Approach section to README with table and bar chart

## [0.1.1] - 2026-06-08

- Removed `da-refusals` due to unclear licensing

## [0.1.0] - 2026-06-08

- Added `wildchat-qwen`: ~99.7k Danish-predominant real user conversations re-generated with Qwen3.5-397B-A17B-NVFP4
- Added `wiki-instruct-da`: 226k Danish Wikipedia instruction pairs generated via backtranslation
- Added `mt-da-deepseek`: 1,251 Danish multi-turn grounded text extraction conversations generated with DeepSeek
- Added `knowledge` task type to schema
- Removed sample counts from short descriptions across all datasheets
- Added note to `da-refusals` that harmful prompts were generated using Grok
- Converted creation date range plot from Plotly to plotnine to match style of other plots
- Fixed tokens-over-time plot ordering for commits on the same date

## [0.0.9] - 2026-06-08

- Minor datasheet update to da-refusals

## [0.0.8] - 2026-06-04

- Added `apertus-sft-mixture`: ~3.9M multilingual SFT samples from the Swiss-AI Apertus training mixture (English, French, German, Italian) under ODC-By
- Per-sample language detection using CLD2 on the first 2,000 characters
- Updated global language list in README frontmatter to ISO 639-3 (dan, eng, fra, deu, ita)

## [0.0.7] - 2026-06-03

- Added `ifbench-train`: 2,000 Danish instruction-following samples with verifiable constraints from IFBench
- Added `when2call`: 3,648 English tool-use samples teaching when to call tools vs. respond directly (304 source duplicates removed)
- Extended `DataSheet.language` to support `fr`, `de`, `it`, `rm` BCP-47 codes

## [0.0.6] - 2026-06-03

- Added `agentic-code-sft-mix-v1`: 24,192 English agentic code samples from three NVIDIA CC-BY 4.0 datasets
- Extended `Message.role` schema to include `"tool"` for function-calling conversations
- Updated empty-message test to allow empty `tool`/`assistant` content (legitimate in agentic function-calling format)

## [0.0.5] - 2026-06-03

- Added `da-refusals`: 404 Danish refusal responses across harmful request categories (32 duplicates removed from source)

## [0.0.3] - 2026-06-03

- Added `translation-100k`: 99,914 Danish↔English translation pairs from EU legal and administrative corpora

## [0.0.2] - 2026-06-03

- Added `created` field to schema (year-level date range approximating when source data was created)
- Extended `DescriptiveStatsOverview` with `min_turns`, `max_turns`, `created_start`, `created_end`, and `languages` counts
- Added global plots: creation date Gantt, language distribution, dataset size range, turns range, tokens over time
- Added per-dataset turns distribution plot alongside token count plot
- Renamed dataset cards to `datasheet.md`
- Language field changed to `list[str]` with ISO 639-3 codes

## [0.0.1] - 2026-06-03

- Initial release of DFM Dyna-Instruct framework
- Added `danish-verifiable-reasoning`: 2,800 synthetic Danish logic puzzles across 14 families with Qwen-235b chain-of-thought reasoning
