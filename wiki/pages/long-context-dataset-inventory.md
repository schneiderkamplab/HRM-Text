---
type: Dataset Inventory
title: Long-Context Dataset Inventory
description: Training candidates, project-derived sources, and evaluation-only corpora for 8K, 16K, and 32K HRM stages.
tags: [long-context, dfm9, dfm10, 8k, 16k, 32k, datasets]
status: stable
last_updated: 2026-08-30
confidence: high
---
# Long-Context Dataset Inventory

The ordinary DFM10 epoch remains a **4,096-token** mixture. Complete examples
that do not fit are deferred rather than response-truncated. This inventory is
for dedicated later 8K, 16K, and 32K epochs. Every training row must be rendered
with the Gemma 4 tokenizer/template at its target length; targets are never
clipped, and evidence required by a target must remain in the retained window.

## Dedicated Public Training Candidates

| Dataset | 8K | 16K | 32K | Intended use and current decision |
| --- | --- | --- | --- | --- |
| `zai-org/LongReward-10k` | Core fitting `sft` rows | Core | Limited need | Long-input QA/instruction SFT. Keep its DPO splits for preference training. |
| `zai-org/LongCite-45k` | Capped, evidence-windowed | Core | Core | Grounded QA with sentence citations. Retain every cited sentence and keep citation syntax a minority style. |
| `zai-org/LongAlign-10k` | Fitting edge only | Core candidate | Core candidate | Roughly 8K--64K multilingual instruction data. It is currently an evaluation diagnostic and DFM9 has indirect LongAlign-derived exposure, so direct training requires replacing/retiring that diagnostic and checking overlap first. |
| `zai-org/LongWriter-6k` | Generally defer | Fitting subset | Core fitting subset | Controlled long-output SFT spanning roughly 2K--32K words. Admit only complete prompt/target rows that fit the stage. |
| `nvidia/ChatQA2-Long-SFT-data` | Core filtered/windowed | Core | Selected long rows | High-volume long RAG and conversational QA. Preserve answer-supporting passages and conversation history. |
| `Yukang/LongAlpaca-12k` | Secondary | Secondary | Limited | Older long-document QA; use only after quality and duplication review. |
| `allenai/tulu-v2-sft-long-mixture` | Fitting subset | Core candidate | Selected rows | Complete long conversations after quality and overlap review. Do not flatten prior turns. |

`zai-org/LongBench`, `LongBench-v2`, and other benchmark releases are never
training candidates. `zai-org/LongAlign-10k` is also evaluation-only while its
current diagnostic remains active; it cannot simultaneously be a clean test
and a direct training source.

## Project-Derived Long Training Sources

| Source family | Upstream/source examples | 8K | 16K/32K preparation |
| --- | --- | --- | --- |
| Common Pile transformations | `USGPO`, `USPTO`, `licensed_pubmed`, `arxiv-papers`, `loc_books`, `project_gutenberg-dolma`, `stackexchange-dolma`, `wikimedia`, and `wikiteam` | Existing DFM9 8K denoising, span filling, prefix continuation, and paragraph reordering | Rebuild longer source windows at each length; do not reuse 8K crops. |
| Danish DynaWord transformations | `ncc_parliament`, `ncc_books`, `ncc_newspaper`, `retsinformationdk`, `tidsskrift-dk`, `gutenberg`, `wikibooks`, `botxt`, `tv2r`, `memo`, `domsdatabasen`, `danske-taler`, `fm-udgivelser`, and `jvj` | Existing DFM9 8K transformations | Generate 12K--16K and 24K--32K windows from source documents, with Danish instruction and retrieval variants. |
| GovReport | `ccdv/govreport-summarization` | Long summarization and grounded QA | Natural 16K/32K reports; preserve full reference summaries and stable held-out IDs. |
| Folketinget | Rigsarkivet handover 14004 and licensed Folketing material | Danish reconstruction, QA, and summarization | Strong source for 16K/32K document tasks after reference/grounding audit. |
| Danish EUR-Lex | `oliverkinch/danish-summarization`, config `eur_lex` | Fitting legal summaries | Natural 16K/32K legal documents; maintain train/eval source-ID separation. |
| Scientific/arXiv/Wiki sources | Open arXiv SFT, Scientific Summaries, WikiCatSum, Danish Wikipedia | Fitting grounded summaries and QA | Wider evidence-preserving windows and multi-hop/distractor synthesis. |
| Native agent trajectories | Nemotron Terminal, Nemotron Agentic, repaired DOLCI, DeepDive | Complete-message 8K windows | Retain longer native histories at 16K/32K. Never serialize prior assistant/tool turns into a user message. |
| Long code/reasoning traces | repaired Nemotron SWE, Big Reasoning Traces, Code Meta-Reasoning, OpenMath/reasoning sources | Only complete fitting targets | Re-render from source at each stage; admit long targets only when the full answer contract fits. |
| Long chat tails | WildChat/Qwen, AI Arena, repaired OpenHermes, Tulu mixtures | Small natural 8K tail | Use complete native conversations; these are anchors, not the main long-context curriculum. |

The DFM9 8K tokenized tree already contains substantial examples above 4K.
The largest measured families are shown below. Counts are tokenized assistant
examples with `prompt + target > 4096`, before final sampling caps/repeats.

| Existing DFM9 family | Rows above 4K | Interpretation |
| --- | ---: | --- |
| `nemotron_swe_windowed` | 9,484,732 | Large legacy source; use only its repaired/native successor in future mixes. |
| `nemotron_terminal_corpus` | 1,684,707 | Legacy flattened/colliding conversion; superseded by native role-preserving conversion. |
| `nemotron_agentic` | 333,819 | Natural long agent trajectories. |
| Common Pile four transformation families | 428,745 | Deliberately generated long document objectives. |
| `allenai_big_reasoning_traces` | 216,009 | Long reasoning targets; exact-fit filtering required. |
| `allenai/tulu-v2-sft-long-mixture` | 180,128 | Natural long conversation/instruction source. |
| `SYNTH` Sapient family | 148,228 | Mixed inherited long tail, not a dedicated curriculum. |
| FLAN plus factual FLAN | 102,482 | Mostly incidental long prompts/summarization tasks. |
| DOLCI instruction/tool families | 208,008 | Native conversation/tool candidates after the DFM10 repair path. |
| DynaWord four transformation families | 44,790 | Deliberately generated Danish long-document objectives. |
| Tulu 3 SFT mixture | 67,266 | Natural long instruction tail. |
| DFM Dyna instruction composite | 88,984 | Mixed long tail; includes duplicate routes that must be reconciled. |

## Evaluation-Only Long-Context Datasets

| Dataset/task | Length stages | Role |
| --- | --- | --- |
| NVIDIA RULER | 8K, 16K, 32K | Controlled retrieval, variable tracking, aggregation, and NIAH. |
| `zai-org/LongBench` / LongBench-E | 8K, 16K, 32K | English long QA, retrieval, summarization, few-shot, and code. |
| `zai-org/LongAlign-10k` diagnostic split | 8K, 16K, 32K | Long instruction-format diagnostic while excluded from direct training. |
| `Hambaobao/Marathon` | 16K and 32K+ | Very-long multiple choice; current local conversion is format-only without a trustworthy answer key. |
| `pszemraj/qmsum-cleaned` validation | 8K and 16K | English meeting summarization. |
| GovReport held-out long subset | 8K, 16K, 32K | English long summarization with stable held-out report IDs. |
| Nordjylland multi-document task | 8K and 16K | Danish retrieval-plus-summarization; individual articles are usually too short. |
| Danish EUR-Lex held-out subset | 8K, 16K, 32K | Danish legal-document summarization. |
| Folketing held-out task | 8K, 16K, 32K | Future Danish document QA/summarization after references are available. |

## Stage Policy

1. **8K:** prioritize LongReward SFT, ChatQA2, fitting LongCite, project Common
   Pile/DynaWord transformations, GovReport, and native trajectory windows.
2. **16K:** rebuild all windows from source; add fitting LongAlign, wider
   LongCite/ChatQA2, Tulu-long, and carefully filtered LongWriter/LongAlpaca.
3. **32K:** emphasize naturally long documents and tasks whose answers depend
   on distributed evidence. LongWriter can add controlled long output, but
   generic long text without long-range dependency is insufficient.
4. Preserve high-quality short-context anchors at every stage and report rows,
   tokens, prompt lengths, target lengths, and supervised target tokens beyond
   the previous context boundary before sampling.
