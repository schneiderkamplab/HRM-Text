---
type: Report
title: DFM16 Additional Sources and SimpleStories Review
description: Candidate instruction, reasoning and agentic additions grounded in public training recipes, plus story-derived SFT options.
tags: [dfm16, datasets, synthetic, research]
status: draft
last_updated: 2026-10-27
confidence: medium
---
# DFM16 Additional Sources and SimpleStories Review

Research recommendations, not admission decisions. No new generation, downloads
of full corpora or sampling changes are authorized by this review. Counts below
are approximate producer-card counts, not accepted/tokenized counts.

## Published Recipes

* [Olmo 3](https://huggingface.co/allenai/Olmo-3-7B-Instruct) separates Dolma
  pretraining from Dolci SFT, preference optimization and verifiable-reward RL.
  DFM already includes Dolci sources. Additional RL prompts need correct teacher
  solutions before SFT; importing prompts alone does not reproduce the recipe.
* [SmolLM3](https://huggingface.co/blog/smollm3) publishes Smoltalk2 mid-training,
  SFT and preference subsets. DFM14 already selects multi-turn reasoning/IF and
  agent traces; inspect uncovered subsets rather than reimporting aggregates.
* [OpenThinker3](https://huggingface.co/datasets/open-thoughts/OpenThoughts3-1.2M)
  provides a concrete reasoning-data recipe. OpenThoughts2 is already inherited;
  novelty and complete context fit matter more than adding another large name.
* [MiniCPM5-1B SFT](https://huggingface.co/datasets/openbmb/UltraData-SFT-2605)
  uses UltraData-SFT-2605 across math, code, knowledge and instruction following.
  Its scale is particularly relevant to Mimir, but producer results do not
  establish that adding the whole mixture improves our existing model.

## Prioritized Candidates

| Priority | Repository | Contribution | Size and integration requirements |
|---|---|---|---|
| High | [openbmb/UltraData-SFT-2605](https://huggingface.co/datasets/openbmb/UltraData-SFT-2605) | Broad English/Chinese knowledge, IF, math and code | Card claims over 15M; gated Apache-2.0. Start with balanced, deduplicated thinking/non-thinking subsets, not wholesale repetition. |
| High | [nvidia/Nemotron-RL-instruction_following-structured_outputs](https://huggingface.co/datasets/nvidia/Nemotron-RL-instruction_following-structured_outputs) | Structured extraction and output-contract compliance | About 9.4K train prompts with schemas, not finished SFT. Generate answers and verify both schema and source faithfulness. |
| High | [Nanbeige/ToolMind](https://huggingface.co/datasets/Nanbeige/ToolMind) | Tool planning and multi-step interactions | About 369K across splits; Apache-2.0. Validate definitions, calls/results and reasoning boundaries; raw think tags must not leak into assistant text. |
| High | [SWE-bench/SWE-smith-trajectories](https://huggingface.co/datasets/SWE-bench/SWE-smith-trajectories) | Executable software-agent trajectories | About 76K rows across three splits, including failures and alternative representations. Select successful unique trajectories; preserve tool results and complete context. Not the SWE-bench evaluation set. |
| Medium-high | [open-thoughts/OpenThoughts3-1.2M](https://huggingface.co/datasets/open-thoughts/OpenThoughts3-1.2M) | Math, code and science reasoning | 850K math, 250K code, 100K science. Deduplicate against OT2 and existing code/math; long traces need complete-fit selection or a long-context recipe. |
| Medium | [MiniMaxAI/SynLogic](https://huggingface.co/datasets/MiniMaxAI/SynLogic) | Verifiable logical reasoning | About 49K across easy/hard configurations and splits. Prompts/verifiers, not ready SFT. Generate verified solutions; rewrite legacy think/answer instructions to native conventions and check benchmark overlap. |
| Review existing coverage | [allenai/atomic](https://huggingface.co/datasets/allenai/atomic) and ATOMIC2020 plan | Social and everyday commonsense | ATOMIC2020 was already proposed in DFM14. Establish realized coverage before adding; conditional/plausible relations are not universal facts, and empty/none labels are not interchangeable. |

Local registration searches found no exact entries for UltraData-SFT-2605,
ToolMind, SWE-smith, SynLogic or SimpleStories. This does not prove that all rows
are absent from inherited aggregate datasets. Dataset-ID and content deduplication
are separate checks.

Already represented or planned: selected Smoltalk/Smoltalk2, OpenCoder,
UltraChat, Dolci, IF_multi_constraints_upto5, OpenThoughts2, SYNTH via Sapient,
MegaScience/TextbookReasoning, xLAM/ToolACE and DFM16 Nemotron knowledge/OpenScience
additions. Do not count these as new wholesale additions. Evidence includes
`dfm14/english_additions.py`, `config/dfm10_residual_quality_audits.yaml`,
`scripts/download_training_datasets.py`, and the DFM14 knowledge/commonsense page.

For all candidates: retain lineage and split identities; screen evaluation
overlap; audit a stratified sample; serialize tools/reasoning through our Gemma 4
adapter; validate tokenization and complete examples. Do not truncate away final
answers or required tool observations. RL environment/task definitions alone are
not tool-use response supervision.

## SimpleStories

No SimpleStories/TinyStories registration was found in the searched source
manifests, conversion code or wiki. Aggregate-row membership remains unverified.

[SimpleStories/SimpleStories](https://huggingface.co/datasets/SimpleStories/SimpleStories)
contains approximately 2.14M English synthetic stories, including splits, with
story/topic/style/grammar metadata, under MIT. The metadata describe intended
generation conditions, not guaranteed compliance: inspected examples do not
always satisfy the requested initial letter. Never blindly use all metadata as
instructions paired with the existing story.

Recommended pilot: sample 100K diverse base stories, produce two or three task
variants per story distributed over English and Danish, repeat 1, then measure
actual token size and quality before expansion. This is a proposed allocation,
not a measured corpus. Keep source-family identifiers across translations and
variants to prevent duplicate inflation and split leakage.

| Task | Construction |
|---|---|
| Controlled creative writing | CPU-verify factual metadata constraints; teacher-check semantic ones before pairing request with story. |
| Summarization | Generate and audit one-sentence, two-sentence and brief summaries with faithful events. |
| Editing | Tense, perspective, style and reading-level changes while preserving intended facts. |
| Narrative understanding | Grounded questions on chronology, references, motivations and causality, with evidence. |
| Multi-turn revision | Initial story, concrete revision request, corrected story; verify requested edits and retained constraints. |
| Completion/repair | Prefix completion and controlled damaged-text repair, capped because DFM already has extensive transformation data. |

These are primarily fluency, narrative coherence and instruction-following data.
Fantasy stories are not factual-knowledge or physical-commonsense supervision.
Most tasks should be native non-thinking chat; use genuine native reasoning only
where appropriate. Summaries/edits/QA require generation and checking, not merely
CPU wrapping. Raw continuation is not recommended as a new English component.

## Translated and Multilingual Stories

| Repository | What is actually provided |
|---|---|
| [SmallScale/Simple-Stories-Eng-Hin](https://huggingface.co/datasets/SmallScale/Simple-Stories-Eng-Hin) | Card reports about 1.72M parallel English/Hindi stories, MIT. Actual translations. Card's loading snippet names a different owner, so pin the inspected repository and verify provenance/alignment before use. |
| [SmallScale/Simple-Stories-Hindi](https://huggingface.co/datasets/SmallScale/Simple-Stories-Hindi) | Hindi-only translation of Simple Stories per card; exact count and overlap with the parallel release not verified. Do not add both blindly. |
| [SimpleStories/SimpleStories-JA](https://huggingface.co/datasets/SimpleStories/SimpleStories-JA) | Approximately 2.11M Japanese stories, independently generated, not aligned English translations. |
| [keenanpepper/simplestories-ja-en-endings](https://huggingface.co/datasets/keenanpepper/simplestories-ja-en-endings) | Approximately 2.08M rows containing Japanese stories and selected ending passages translated into English, not full-story translation pairs. |

No verified Danish translation was found in this search. A Danish pilot would
require translation/adaptation plus an audit. TinyStories is a separate corpus;
translations of it must not be described as SimpleStories translations. Hindi
cards were read directly from Hub raw README endpoints where the browser failed.
