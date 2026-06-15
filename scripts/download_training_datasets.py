#!/usr/bin/env python3
"""Download candidate HRM-Text training datasets into this repo.

The script keeps all downloaded files under an ignored repo-local directory by
default: data/downloads/datasets. It uses HF_TOKEN from the environment for
gated Hugging Face datasets.

By default this is an inventory dry run. Pass --download to fetch data.
"""

from __future__ import annotations

import argparse
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from huggingface_hub import HfApi, snapshot_download


@dataclass(frozen=True)
class HFDataset:
    name: str
    repo_id: str
    groups: tuple[str, ...]
    allow_patterns: tuple[str, ...]
    note: str = ""
    gated: bool = False


@dataclass(frozen=True)
class LocalDataset:
    name: str
    path: str
    groups: tuple[str, ...]
    note: str = ""


HF_DATASETS: tuple[HFDataset, ...] = (
    # Sapient/data_io cleaned source, useful when reproducing or comparing.
    HFDataset(
        name="sapient_cleaned",
        repo_id="sapientinc/HRM-Text-data-io-cleaned-20260515",
        groups=("sapient",),
        allow_patterns=("data/**/*.jsonl", "data_clustered/**/*.parquet", "README.md"),
        note="Cleaned Sapient HRM-Text data_io corpus.",
    ),

    # Danish and Synquid sources discussed for the replacement mix.
    HFDataset(
        name="danish_dynaword",
        repo_id="danish-foundation-models/danish-dynaword",
        groups=("danish", "danish_continuation", "raw"),
        allow_patterns=("data/**/*.parquet", "README.md", "CHANGELOG.md"),
        note="Raw Danish documents; convert to continuation rows.",
    ),

    # Selected Common Pile components for English factual/commonsense/reading
    # recovery. Keep this explicit; do not reintroduce a broad common_pile*
    # wildcard without a separate policy decision.
    HFDataset(
        name="common_pile_wikimedia_filtered",
        repo_id="common-pile/wikimedia_filtered",
        groups=("common_pile", "english_raw", "raw"),
        allow_patterns=("*.json.gz", "*.jsonl.gz", "data/**/*.json.gz", "data/**/*.jsonl.gz", "README.md"),
        note="Filtered Wikimedia; CC-BY-SA metadata in rows.",
    ),
    HFDataset(
        name="common_pile_wikiteam_filtered",
        repo_id="common-pile/wikiteam_filtered",
        groups=("common_pile", "english_raw", "raw"),
        allow_patterns=("*.json.gz", "*.jsonl.gz", "data/**/*.json.gz", "data/**/*.jsonl.gz", "README.md"),
        note="Filtered WikiTeam dumps; review row licenses during attribution.",
    ),
    HFDataset(
        name="common_pile_stackexchange_filtered",
        repo_id="common-pile/stackexchange_filtered",
        groups=("common_pile", "english_raw", "raw"),
        allow_patterns=("*.json.gz", "*.jsonl.gz", "data/**/*.json.gz", "data/**/*.jsonl.gz", "README.md"),
        note="Filtered StackExchange; CC-BY-SA rows.",
    ),
    HFDataset(
        name="common_pile_pubmed_filtered",
        repo_id="common-pile/pubmed_filtered",
        groups=("common_pile", "english_raw", "raw"),
        allow_patterns=("*.json.gz", "*.jsonl.gz", "data/**/*.json.gz", "data/**/*.jsonl.gz", "README.md"),
        note="Filtered PubMed/PubMed Central open-license scientific text.",
    ),
    HFDataset(
        name="common_pile_arxiv_abstracts_filtered",
        repo_id="common-pile/arxiv_abstracts_filtered",
        groups=("common_pile", "english_raw", "raw"),
        allow_patterns=("*.json.gz", "*.jsonl.gz", "data/**/*.json.gz", "data/**/*.jsonl.gz", "README.md"),
        note="Filtered arXiv abstracts.",
    ),
    HFDataset(
        name="common_pile_arxiv_papers_filtered",
        repo_id="common-pile/arxiv_papers_filtered",
        groups=("common_pile", "english_raw", "raw"),
        allow_patterns=("*.json.gz", "*.jsonl.gz", "data/**/*.json.gz", "data/**/*.jsonl.gz", "README.md"),
        note="Filtered arXiv papers; use capped raw-objective sampling.",
    ),
    HFDataset(
        name="common_pile_usgpo_filtered",
        repo_id="common-pile/usgpo_filtered",
        groups=("common_pile", "english_raw", "raw"),
        allow_patterns=("*.json.gz", "*.jsonl.gz", "data/**/*.json.gz", "data/**/*.jsonl.gz", "README.md"),
        note="Filtered US Government Publishing Office public-domain text.",
    ),
    HFDataset(
        name="common_pile_regulations_filtered",
        repo_id="common-pile/regulations_filtered",
        groups=("common_pile", "english_raw", "raw"),
        allow_patterns=("*.json.gz", "*.jsonl.gz", "data/**/*.json.gz", "data/**/*.jsonl.gz", "README.md"),
        note="Filtered regulations.gov public-domain text.",
    ),
    HFDataset(
        name="common_pile_uspto_filtered",
        repo_id="common-pile/uspto_filtered",
        groups=("common_pile", "english_raw", "raw"),
        allow_patterns=("*.json.gz", "*.jsonl.gz", "data/**/*.json.gz", "data/**/*.jsonl.gz", "README.md"),
        note="Filtered USPTO patent text.",
    ),
    HFDataset(
        name="common_pile_project_gutenberg_filtered",
        repo_id="common-pile/project_gutenberg_filtered",
        groups=("common_pile", "english_raw", "raw"),
        allow_patterns=("*.json.gz", "*.jsonl.gz", "data/**/*.json.gz", "data/**/*.jsonl.gz", "README.md"),
        note="Filtered Project Gutenberg public-domain books.",
    ),
    HFDataset(
        name="common_pile_public_domain_review_filtered",
        repo_id="common-pile/public_domain_review_filtered",
        groups=("common_pile", "english_raw", "raw"),
        allow_patterns=("*.json.gz", "*.jsonl.gz", "data/**/*.json.gz", "data/**/*.jsonl.gz", "README.md"),
        note="Small public-domain review source.",
    ),
    HFDataset(
        name="common_pile_library_of_congress",
        repo_id="common-pile/library_of_congress",
        groups=("common_pile", "english_raw", "raw"),
        allow_patterns=("*.json.gz", "*.jsonl.gz", "data/**/*.json.gz", "data/**/*.jsonl.gz", "README.md"),
        note="Library of Congress public-domain/open metadata text.",
    ),
    HFDataset(
        name="govreport_summarization",
        repo_id="ccdv/govreport-summarization",
        groups=("english", "summarization", "dfm4"),
        allow_patterns=("document/train-*.parquet", "README.md"),
        note="Long-document government report summarization; train split only.",
    ),
    HFDataset(
        name="wiki_cat_sum",
        repo_id="GEM/wiki_cat_sum",
        groups=("english", "summarization", "wikipedia", "dfm4"),
        allow_patterns=("main_splits/train-*.jsonl", "README.md"),
        note="Wikipedia/WikiSum-derived multi-document summarization; train splits only.",
    ),
    HFDataset(
        name="laion_scientific_summaries",
        repo_id="laion/Scientific-Summaries",
        groups=("english", "summarization", "science", "dfm4"),
        allow_patterns=("data/arxiv/*.parquet", "README.md", "SEARCH_USAGE.md"),
        note="CC-BY-4.0 LLM-generated scientific summaries; arXiv config only by default.",
    ),
    HFDataset(
        name="laerebogen_with_followups",
        repo_id="danish-foundation-models/laerebogen",
        groups=("danish", "instruction"),
        allow_patterns=("with_follow_ups/train-*.parquet", "README.md"),
        note="Gated Danish multi-turn instruction data.",
        gated=True,
    ),
    HFDataset(
        name="synquid_wiki_instruct_da",
        repo_id="synquid/wiki-instruct-da",
        groups=("danish", "instruction", "synquid"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="Gated Danish wiki instruction data.",
        gated=True,
    ),
    HFDataset(
        name="synquid_danish_verifiable_reasoning",
        repo_id="synquid/danish-verifiable-reasoning",
        groups=("danish", "reasoning", "synquid"),
        allow_patterns=("data/train-*.parquet", "README.md"),
    ),
    HFDataset(
        name="synquid_translation_100k",
        repo_id="synquid/translation-100k",
        groups=("danish", "translation", "synquid"),
        allow_patterns=("data/train-*.parquet", "README.md"),
    ),
    HFDataset(
        name="synquid_ifbench_train",
        repo_id="synquid/ifbench-train",
        groups=("danish", "instruction", "synquid"),
        allow_patterns=("data/train-*.parquet", "README.md"),
    ),
    HFDataset(
        name="oliverkinch_instruct_bt",
        repo_id="oliverkinch/instruct-bt",
        groups=("danish", "instruction"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="Gated; requires accepted access.",
        gated=True,
    ),
    HFDataset(
        name="oliverkinch_multi_wiki_qa_high_quality",
        repo_id="oliverkinch/multi-wiki-qa-high-quality-subset",
        groups=("danish", "qa", "instruction"),
        allow_patterns=("da/train-*.parquet", "README.md"),
        note="Danish Wikipedia-derived extractive QA subset; CC-BY-4.0.",
    ),
    HFDataset(
        name="oliverkinch_eur_lex_sum_instruct",
        repo_id="oliverkinch/eur-lex-sum-instruct",
        groups=("danish", "instruction", "summarization", "legal"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="Danish EUR-Lex summarization instruction data derived from EU legal text.",
    ),
    HFDataset(
        name="oliverkinch_machine_translation_da_en",
        repo_id="oliverkinch/machine-translation-da-en",
        groups=("danish", "translation"),
        allow_patterns=("data/train.parquet", "README.md"),
        note="Danish-English OPUS-derived translation data; cap during sampling.",
    ),
    HFDataset(
        name="oliverkinch_machine_translation_da_uk",
        repo_id="oliverkinch/machine-translation-da-uk",
        groups=("danish", "translation"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="Danish-Ukrainian OPUS-derived translation data; cap during sampling.",
    ),
    HFDataset(
        name="oliverkinch_machine_translation_da_ar",
        repo_id="oliverkinch/machine-translation-da-ar",
        groups=("danish", "translation"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="Danish-Arabic OPUS-derived translation data; cap during sampling.",
    ),
    HFDataset(
        name="oliverkinch_danmarks_statistik_bt",
        repo_id="oliverkinch/danmarks-statistik-bt",
        groups=("danish", "instruction", "backtranslation"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="Backtranslation from Danmarks Statistik CC-BY-4.0 publications.",
    ),
    HFDataset(
        name="oliverkinch_tidsskrift_dk_bt",
        repo_id="oliverkinch/tidsskrift-dk-bt",
        groups=("danish", "instruction", "backtranslation"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="Backtranslation from tidsskrift.dk CC-BY academic articles.",
    ),
    HFDataset(
        name="oliverkinch_doab_da_bt",
        repo_id="oliverkinch/doab-da-bt",
        groups=("danish", "instruction", "backtranslation"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="Small backtranslation set from DOAB Danish open-access material.",
    ),
    HFDataset(
        name="oliverkinch_danish_university_portals_bt",
        repo_id="oliverkinch/danish-university-portals-bt",
        groups=("danish", "instruction", "backtranslation"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="Backtranslation from Danish university portal publications; source card says CC-BY-only material.",
    ),
    HFDataset(
        name="oliverkinch_eur_lex_bt",
        repo_id="oliverkinch/eur-lex-bt",
        groups=("danish", "instruction", "backtranslation", "legal"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="Backtranslation from EUR-Lex Danish legal text.",
    ),
    HFDataset(
        name="oliverkinch_dynaword_bt",
        repo_id="oliverkinch/dynaword-bt",
        groups=("danish", "instruction", "backtranslation"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="Backtranslation from Danish DynaWord; cap/review by source subset during sampling.",
    ),
    HFDataset(
        name="oliverkinch_dst_table_prompts_bt",
        repo_id="oliverkinch/dst-table-prompts-bt",
        groups=("danish", "instruction", "backtranslation", "tables"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="Backtranslation/data-to-text from Danmarks Statistik tables; CC-BY-4.0.",
    ),
    HFDataset(
        name="synquid_mt_da_deepseek",
        repo_id="synquid/mt-da-deepseek",
        groups=("danish", "instruction", "synquid"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="Gated; schema should be inspected after access is granted.",
        gated=True,
    ),
    HFDataset(
        name="synquid_danish_wildchat_100k",
        repo_id="synquid/danish-wildchat-100k",
        groups=("danish", "prompts", "synquid"),
        allow_patterns=("data/train.jsonl", "README.md", "metadata/**/*.json"),
        note="Gated prompt-only source; not directly trainable without responses.",
        gated=True,
    ),
    HFDataset(
        name="synquid_wildchat_100k_qwen_messages",
        repo_id="synquid/wildchat-100k-qwen-messages",
        groups=("danish", "instruction", "synquid"),
        allow_patterns=("data/train.jsonl", "README.md", "metadata/**/*.json"),
        note="Gated generated responses for WildChat prompts in messages format; include with a tight cap.",
        gated=True,
    ),

    # Post-training transformation/refinement sources. These are intended for a
    # separate post-training mix rather than the main pretraining corpus.
    HFDataset(
        name="posttrain_coedit",
        repo_id="grammarly/coedit",
        groups=("posttrain_transform", "instruction", "editing"),
        allow_patterns=("train.jsonl", "validation.jsonl", "README.md"),
        note="Instruction-style grammar/editing/rewrite data; convert src/tgt rows.",
    ),
    HFDataset(
        name="posttrain_natural_instructions",
        repo_id="Muennighoff/natural-instructions",
        groups=("posttrain_transform", "instruction", "editing"),
        allow_patterns=("train/*.jsonl", "README.md"),
        note="Super-NaturalInstructions preprocessing; filter to transformation-style train tasks before conversion.",
    ),
    HFDataset(
        name="posttrain_asset",
        repo_id="facebook/asset",
        groups=("posttrain_transform", "simplification", "editing"),
        allow_patterns=("simplification/*.parquet", "README.md"),
        note="ASSET simplification validation/test rows; use as synthetic seed material rather than direct training rows.",
    ),

    # Nemotron sources.
    HFDataset(
        name="nemotron_terminal_corpus",
        repo_id="nvidia/Nemotron-Terminal-Corpus",
        groups=("nemotron", "terminal", "code_agentic"),
        allow_patterns=(
            "dataset_adapters/*.parquet",
            "synthetic_tasks/skill_based/easy/*/data_filtered.parquet",
            "synthetic_tasks/skill_based/medium/*/data_filtered.parquet",
            "synthetic_tasks/skill_based/mixed/*/data_filtered.parquet",
            "README.md",
        ),
    ),
    HFDataset(
        name="nemotron_instruction_reasoning_off",
        repo_id="nvidia/Nemotron-SFT-Instruction-Following-Chat-v2",
        groups=("nemotron", "instruction"),
        allow_patterns=("data/reasoning_off.jsonl", "README.md"),
    ),
    HFDataset(
        name="nemotron_agentic",
        repo_id="nvidia/Nemotron-SFT-Agentic-v2",
        groups=("nemotron", "agentic", "code_agentic"),
        allow_patterns=(
            "data/interactive_agent.jsonl",
            "data/tool_calling.jsonl",
            "data/search.jsonl",
            "README.md",
        ),
    ),
    HFDataset(
        name="nemotron_swe",
        repo_id="nvidia/Nemotron-SFT-SWE-v2",
        groups=("nemotron", "swe", "code_agentic"),
        allow_patterns=("data/agentless.jsonl", "data/swe.jsonl", "README.md"),
    ),
    HFDataset(
        name="nemotron_multilingual",
        repo_id="nvidia/Nemotron-SFT-Multilingual-v1",
        groups=("nemotron", "multilingual"),
        allow_patterns=("data/*.jsonl", "README.md"),
        note="No Danish; useful for multilingual STEM/code transfer.",
    ),

    # AllenAI Dolci instruction data from Hugging Face collections.
    HFDataset(
        name="dolci_instruct_sft",
        repo_id="allenai/Dolci-Instruct-SFT",
        groups=("dolci", "instruction"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="Main Dolci Instruct SFT mixture.",
    ),
    HFDataset(
        name="dolci_instruct_sft_no_tools",
        repo_id="allenai/Dolci-Instruct-SFT-No-Tools",
        groups=("dolci", "instruction"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="Dolci Instruct SFT subset without tool-use data.",
    ),
    HFDataset(
        name="dolci_instruct_sft_tool_use",
        repo_id="allenai/Dolci-Instruct-SFT-Tool-Use",
        groups=("dolci", "instruction", "agentic"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="Dolci tool-use SFT data.",
    ),
    HFDataset(
        name="dolci_instruct_sft_tool_use_sa",
        repo_id="allenai/Dolci-Instruct-SFT-Tool-Use-SA",
        groups=("dolci", "instruction", "agentic"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="Small Dolci tool-use single-agent subset.",
    ),

    # Other AllenAI datasets that fit instruction/reasoning conversion.
    HFDataset(
        name="allenai_tulu_3_sft_mixture",
        repo_id="allenai/tulu-3-sft-mixture",
        groups=("allenai", "instruction"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="General chat/instruction mixture; ODC-By.",
    ),
    HFDataset(
        name="allenai_tulu_v2_sft_mixture",
        repo_id="allenai/tulu-v2-sft-mixture",
        groups=("allenai", "instruction"),
        allow_patterns=("data/train-*.parquet", "README.md"),
    ),
    HFDataset(
        name="allenai_tulu_v2_sft_long_mixture",
        repo_id="allenai/tulu-v2-sft-long-mixture",
        groups=("allenai", "instruction"),
        allow_patterns=("*.jsonl", "README.md"),
        note="Long-context Tulu v2 JSONL mixture.",
    ),
    HFDataset(
        name="allenai_tulu_3_personas_math",
        repo_id="allenai/tulu-3-sft-personas-math",
        groups=("allenai", "math_reasoning", "instruction"),
        allow_patterns=("data/train-*.parquet", "README.md"),
    ),
    HFDataset(
        name="allenai_tulu_3_personas_algebra",
        repo_id="allenai/tulu-3-sft-personas-algebra",
        groups=("allenai", "math_reasoning", "instruction"),
        allow_patterns=("data/train-*.parquet", "README.md"),
    ),
    HFDataset(
        name="allenai_tulu_3_personas_code",
        repo_id="allenai/tulu-3-sft-personas-code",
        groups=("allenai", "code_agentic", "instruction"),
        allow_patterns=("data/train-*.parquet", "README.md"),
    ),
    HFDataset(
        name="allenai_tulu_3_personas_if",
        repo_id="allenai/tulu-3-sft-personas-instruction-following",
        groups=("allenai", "instruction"),
        allow_patterns=("data/train-*.parquet", "README.md"),
    ),
    HFDataset(
        name="allenai_sciriff_train_mix",
        repo_id="allenai/SciRIFF-train-mix",
        groups=("allenai", "instruction", "reasoning"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="Scientific instruction-following data.",
    ),
    HFDataset(
        name="allenai_if_sft_verified",
        repo_id="allenai/IF_sft_data_verified",
        groups=("allenai", "instruction"),
        allow_patterns=("data/train-*.parquet", "README.md"),
    ),
    HFDataset(
        name="allenai_if_multi_constraints_upto5",
        repo_id="allenai/IF_multi_constraints_upto5",
        groups=("allenai", "instruction"),
        allow_patterns=("data/train-*.parquet", "README.md"),
    ),
    HFDataset(
        name="allenai_verifiable_reasoning_gpt41",
        repo_id="allenai/verifiable-reasoning-filtered-gpt-41",
        groups=("allenai", "reasoning"),
        allow_patterns=("data/train-*.parquet", "README.md"),
    ),
    HFDataset(
        name="allenai_verifiable_reasoning_o4mini",
        repo_id="allenai/verifiable-reasoning-filtered-o4-mini",
        groups=("allenai", "reasoning"),
        allow_patterns=("data/train-*.parquet", "README.md"),
    ),
    HFDataset(
        name="allenai_code_meta_reasoning",
        repo_id="allenai/code-meta-reasoning-cleaned-final-string-id",
        groups=("allenai", "code_agentic", "reasoning"),
        allow_patterns=("data/train-*.parquet", "README.md"),
    ),
    HFDataset(
        name="allenai_open_math_2_50k_r1",
        repo_id="allenai/open_math_2_50k_r1-original",
        groups=("allenai", "math_reasoning"),
        allow_patterns=("data/train-*.parquet", "README.md"),
    ),
    HFDataset(
        name="allenai_rlvr_gsm",
        repo_id="allenai/RLVR-GSM",
        groups=("allenai", "math_reasoning"),
        allow_patterns=("data/train-*.parquet", "README.md"),
    ),
    HFDataset(
        name="allenai_rlvr_math",
        repo_id="allenai/RLVR-MATH",
        groups=("allenai", "math_reasoning"),
        allow_patterns=("data/train-*.parquet", "README.md"),
    ),
    HFDataset(
        name="allenai_rlvr_ifeval",
        repo_id="allenai/RLVR-IFeval",
        groups=("allenai", "instruction"),
        allow_patterns=("data/train-*.parquet", "README.md"),
    ),
    HFDataset(
        name="allenai_big_reasoning_traces",
        repo_id="allenai/big-reasoning-traces",
        groups=("allenai", "reasoning"),
        allow_patterns=("**/*.parquet", "README.md"),
        note="Large reasoning traces; cap during sampling.",
    ),
    # Additional permissive / academic-compatible sources from Sapient/data_io.
    HFDataset(
        name="openmathinstruct2",
        repo_id="nvidia/OpenMathInstruct-2",
        groups=("math_reasoning",),
        allow_patterns=("**/*.parquet", "**/*.jsonl", "README.md"),
    ),
    HFDataset(
        name="numinamath_1_5",
        repo_id="AI-MO/NuminaMath-1.5",
        groups=("math_reasoning",),
        allow_patterns=("**/*.parquet", "**/*.jsonl", "README.md"),
    ),
    HFDataset(
        name="openthoughts2_1m",
        repo_id="open-thoughts/OpenThoughts2-1M",
        groups=("math_reasoning",),
        allow_patterns=("**/*.parquet", "**/*.jsonl", "README.md"),
    ),
    HFDataset(
        name="webinstruct_verified",
        repo_id="TIGER-Lab/WebInstruct-verified",
        groups=("instruction", "math_reasoning"),
        allow_patterns=("**/*.parquet", "**/*.jsonl", "README.md"),
    ),
    HFDataset(
        name="omni_math",
        repo_id="KbsdJames/Omni-MATH",
        groups=("math_reasoning",),
        allow_patterns=("**/*.parquet", "**/*.jsonl", "README.md"),
    ),
    HFDataset(
        name="gsm8k",
        repo_id="openai/gsm8k",
        groups=("math_reasoning",),
        allow_patterns=("**/*.parquet", "**/*.jsonl", "README.md"),
    ),
    HFDataset(
        name="hendrycks_math",
        repo_id="EleutherAI/hendrycks_math",
        groups=("math_reasoning",),
        allow_patterns=("**/*.parquet", "**/*.jsonl", "README.md"),
    ),
    HFDataset(
        name="theoremqa",
        repo_id="TIGER-Lab/TheoremQA",
        groups=("math_reasoning",),
        allow_patterns=("**/*.parquet", "**/*.jsonl", "README.md"),
    ),
    HFDataset(
        name="no_robots",
        repo_id="HuggingFaceH4/no_robots",
        groups=("instruction",),
        allow_patterns=("**/*.parquet", "**/*.jsonl", "README.md"),
    ),
    HFDataset(
        name="natural_reasoning",
        repo_id="facebook/natural_reasoning",
        groups=("reasoning",),
        allow_patterns=("**/*.parquet", "**/*.jsonl", "README.md"),
    ),
    HFDataset(
        name="principia_collection",
        repo_id="facebook/principia-collection",
        groups=("reasoning",),
        allow_patterns=("**/*.parquet", "**/*.jsonl", "README.md"),
    ),
    HFDataset(
        name="textbook_reasoning",
        repo_id="MegaScience/TextbookReasoning",
        groups=("reasoning",),
        allow_patterns=("**/*.parquet", "**/*.jsonl", "README.md"),
    ),

)


LOCAL_DATASETS: tuple[LocalDataset, ...] = (
    LocalDataset(
        name="dolci_alignment_free",
        path="datasets/dolci/dolci_instruct_sft_alignment_free.jsonl",
        groups=("dolci_local", "instruction"),
        note="Legacy local path from earlier list; HF Dolci repos are in the dolci group.",
    ),
    LocalDataset(
        name="dolci_random50k",
        path="datasets/dolci/slices/dolci_alignment_free_random50k.messages.jsonl",
        groups=("dolci_local", "instruction"),
    ),
    LocalDataset(
        name="dolci_lowecho50k",
        path="datasets/dolci/slices/dolci_alignment_free_lowecho50k.messages.jsonl",
        groups=("dolci_local", "instruction"),
    ),
    LocalDataset(
        name="dolci_lowecho_lowrep50k",
        path="datasets/dolci/slices/dolci_alignment_free_lowecho_lowrep50k.messages.jsonl",
        groups=("dolci_local", "instruction"),
    ),
    LocalDataset(
        name="dolci_longsafe257_50k",
        path="datasets/dolci/slices/dolci_alignment_free_longsafe257_50k.messages.jsonl",
        groups=("dolci_local", "instruction"),
    ),
)


def parse_args() -> argparse.Namespace:
    group_names = sorted({g for item in (*HF_DATASETS, *LOCAL_DATASETS) for g in item.groups})
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/downloads/datasets"))
    parser.add_argument("--groups", default="danish,synquid,nemotron,dolci,allenai")
    parser.add_argument("--exclude-gated", action="store_true")
    parser.add_argument("--download", action="store_true", help="Actually download/copy data. Default is dry-run inventory.")
    parser.add_argument("--list-groups", action="store_true")
    parser.add_argument("--local-files-only", action="store_true", help="Use only existing Hugging Face cache files.")
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument("--token-env", default="HF_TOKEN")
    parser.add_argument("--revision", default=None, help="Optional revision override for every HF dataset.")
    parser.add_argument("--only", default="", help="Comma-separated dataset names to include.")
    parser.add_argument("--skip", default="", help="Comma-separated dataset names to skip.")
    parser.set_defaults(group_names=group_names)
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def selected_groups(args: argparse.Namespace) -> set[str]:
    if args.groups.strip().lower() == "all":
        return set(args.group_names)
    return {x.strip() for x in args.groups.split(",") if x.strip()}


def selected_names(raw: str) -> set[str]:
    return {x.strip() for x in raw.split(",") if x.strip()}


def should_include(groups: set[str], only: set[str], skip: set[str], item: HFDataset | LocalDataset) -> bool:
    if only and item.name not in only:
        return False
    if item.name in skip:
        return False
    return bool(groups.intersection(item.groups))


def format_bytes(value: int | None) -> str:
    if value is None:
        return "unknown"
    size = float(value)
    for suffix in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or suffix == "TB":
            return f"{size:.1f} {suffix}"
        size /= 1024
    raise AssertionError("unreachable")


def matching_size(api: HfApi, dataset: HFDataset, token: str | None, revision: str | None) -> tuple[int, int]:
    info = api.dataset_info(dataset.repo_id, revision=revision, files_metadata=True, token=token)
    siblings = info.siblings or []

    # Reuse the hub's own pattern matching by doing a cheap metadata-side
    # approximation: include exact names, README.md, and suffix/common globs.
    matched_count = 0
    matched_bytes = 0
    for sibling in siblings:
        name = sibling.rfilename
        if any(pattern_matches(name, pattern) for pattern in dataset.allow_patterns):
            matched_count += 1
            matched_bytes += getattr(sibling, "size", None) or 0
    return matched_count, matched_bytes


def pattern_matches(name: str, pattern: str) -> bool:
    # Good enough for inventory display; snapshot_download does authoritative
    # matching. pathlib.PurePath.match has awkward semantics for ** at root, so
    # handle the patterns used in this manifest explicitly.
    if pattern == name:
        return True
    if pattern == "README.md" and name == "README.md":
        return True
    if pattern.startswith("**/*."):
        return name.endswith(pattern.removeprefix("**/*"))
    if pattern.endswith("/**/*.parquet"):
        return name.startswith(pattern.removesuffix("**/*.parquet")) and name.endswith(".parquet")
    if pattern.endswith("/**/*.jsonl"):
        return name.startswith(pattern.removesuffix("**/*.jsonl")) and name.endswith(".jsonl")
    if "*" in pattern:
        from fnmatch import fnmatch

        return fnmatch(name, pattern)
    return False


def iter_selected(args: argparse.Namespace) -> tuple[list[HFDataset], list[LocalDataset]]:
    groups = selected_groups(args)
    only = selected_names(args.only)
    skip = selected_names(args.skip)
    hf_items = [
        item for item in HF_DATASETS
        if should_include(groups, only, skip, item) and not (args.exclude_gated and item.gated)
    ]
    local_items = [item for item in LOCAL_DATASETS if should_include(groups, only, skip, item)]
    return hf_items, local_items


def print_inventory(args: argparse.Namespace, hf_items: Iterable[HFDataset], local_items: Iterable[LocalDataset]) -> None:
    token = os.environ.get(args.token_env)
    api = HfApi(token=token)
    total = 0
    print(f"Output dir: {(repo_root() / args.output_dir).resolve()}")
    print(f"Mode: {'download' if args.download else 'dry-run'}")
    print()

    for item in hf_items:
        try:
            count, size = matching_size(api, item, token, args.revision)
            total += size
            access = "gated" if item.gated else "open"
            print(f"HF  {item.name:42} {format_bytes(size):>10} {count:4d} files  {access:5}  {item.repo_id}")
            if item.note:
                print(f"    note: {item.note}")
        except Exception as exc:
            print(f"HF  {item.name:42} {'?':>10} {'?':>4} files  error  {item.repo_id}")
            print(f"    {type(exc).__name__}: {exc}")

    for item in local_items:
        source = repo_root() / item.path
        size = source.stat().st_size if source.exists() else None
        state = "found" if source.exists() else "missing"
        print(f"LOC {item.name:42} {format_bytes(size):>10} {state:>10}  {item.path}")
        if item.note:
            print(f"    note: {item.note}")

    print()
    print(f"Estimated selected HF bytes: {format_bytes(total)}")


def download_hf_dataset(args: argparse.Namespace, dataset: HFDataset) -> None:
    token = os.environ.get(args.token_env)
    target = (repo_root() / args.output_dir / dataset.name).resolve()
    target.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {dataset.repo_id} -> {target}")
    snapshot_download(
        dataset.repo_id,
        repo_type="dataset",
        revision=args.revision,
        local_dir=target,
        allow_patterns=list(dataset.allow_patterns),
        token=token,
        local_files_only=args.local_files_only,
        max_workers=args.max_workers,
    )


def copy_local_dataset(args: argparse.Namespace, dataset: LocalDataset) -> None:
    source = repo_root() / dataset.path
    target = repo_root() / args.output_dir / dataset.name / Path(dataset.path).name
    if not source.exists():
        print(f"Skipping missing local dataset: {source}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"Copying {source} -> {target}")
    shutil.copy2(source, target)


def main() -> None:
    args = parse_args()
    if args.list_groups:
        print("\n".join(args.group_names))
        return

    hf_items, local_items = iter_selected(args)
    print_inventory(args, hf_items, local_items)
    if not args.download:
        print("\nDry run only. Re-run with --download to fetch selected datasets.")
        return

    for item in hf_items:
        download_hf_dataset(args, item)
    for item in local_items:
        copy_local_dataset(args, item)


if __name__ == "__main__":
    main()
