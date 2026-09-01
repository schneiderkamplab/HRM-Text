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
    revision: str | None = None


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
    HFDataset(
        name="dfm11_fineinstructions_nemotron_metadata",
        repo_id="fineinstructions/fineinstructions_nemotron",
        groups=("dfm11_candidate", "english", "synthetic", "instruction_pretraining"),
        allow_patterns=("README.md", "pretrain_snapshot.json"),
        note=(
            "Metadata only: the full Common-Crawl-derived corpus is about 2 TB. "
            "Use prepare_dfm11_fineinstructions_nemotron.py for deterministic, "
            "quality-filtered materialization after its admission gates pass."
        ),
        revision="b1f556ec27529d09602e4dbe49de4263f5ebd068",
    ),

    # Danish and Synquid sources discussed for the replacement mix.
    HFDataset(
        name="danish_dynaword",
        repo_id="danish-foundation-models/danish-dynaword",
        groups=("danish", "danish_continuation", "raw"),
        allow_patterns=("data/**/*.parquet", "README.md", "CHANGELOG.md"),
        note="Raw Danish documents; convert to continuation rows.",
    ),
    HFDataset(
        name="dfm10_elrc_medical",
        repo_id="qanastek/ELRC-Medical-V2",
        groups=("dfm10", "danish", "english", "medical", "translation"),
        allow_patterns=("README.md", "LICENSE", "Sources.md", "csv/en-da.csv"),
        note=(
            "CC-BY-4.0 English-Danish medical/public-health parallel text. "
            "DFM10 filters document artefacts and converts both directions."
        ),
        revision="7f5633e7f9903947a9e51ab0e12ff483574aeebf",
    ),
    HFDataset(
        name="dfm10_emea_medical",
        repo_id="qanastek/EMEA-V3",
        groups=("dfm10", "danish", "english", "medical", "translation"),
        allow_patterns=("README.md", "LICENSE", "csv/da-en.csv.gz"),
        note=(
            "CC-BY-4.0 OPUS/EMA Danish-English medical parallel text. "
            "DFM10 converts both directions and deduplicates against ELRC."
        ),
        revision="783edb3e7341c61ec455b253654550c6bdbdfa89",
    ),
    HFDataset(
        name="dfm10_ecdc_medical",
        repo_id="qanastek/ECDC",
        groups=("dfm10", "danish", "english", "medical", "translation"),
        allow_patterns=("README.md", "LICENSE", "csv/ECDC.csv.gz"),
        note=(
            "EU/ECDC professional public-health translation memory. Its terms "
            "grant commercial and non-commercial reuse with notice retention."
        ),
        revision="30a7e525efbb3094204e7e9a49bc46fd0ec7afb6",
    ),
    HFDataset(
        name="dfm10_nhs_synthetic_clinical_notes",
        repo_id="NHSEDataScience/synthetic_clinical_notes",
        groups=("dfm10", "english", "medical", "synthetic"),
        allow_patterns=(
            "README.md",
            "silver/README.md",
            "silver/synthetic_clinical_notes.csv",
        ),
        note=(
            "MIT-licensed fully synthetic notes. DFM10 uses grounded note "
            "classification and exact span-reconstruction supervision only."
        ),
        revision="368a5bd2a55090a0bae3436f2823d606c5077158",
    ),
    HFDataset(
        name="alexandra_nordjylland_news",
        repo_id="alexandrainst/nordjylland-news-summarization",
        groups=("dfm10", "danish", "instruction", "summarization"),
        allow_patterns=(
            "data/train-00000-of-00001-4fb110c0f6314175.parquet",
            "README.md",
        ),
        note="DFM10 uses only the original 75,219-row train file; the synthetic 63,855-row file is already inherited through Oliver Kinch.",
    ),
    HFDataset(
        name="alexandra_scandi_qa",
        repo_id="alexandrainst/scandi-qa",
        groups=("dfm10", "danish", "instruction", "qa"),
        allow_patterns=("data/da/train.jsonl", "README.md"),
        note="DFM10 uses only Danish train; validation and test remain held out.",
    ),
    HFDataset(
        name="alexandra_multi_zebra_logic",
        repo_id="alexandrainst/multi-zebra-logic",
        groups=("dfm10", "danish", "english", "instruction", "reasoning"),
        allow_patterns=(
            "dataset_da_huse_2x3_5rh/train-00000-of-00001.parquet",
            "dataset_da_huse_4x5_5rh/train-00000-of-00001.parquet",
            "dataset_da_smoerrebroed_2x3_5rh/train-00000-of-00001.parquet",
            "dataset_da_smoerrebroed_4x5_5rh/train-00000-of-00001.parquet",
            "dataset_en_houses_2x3_5rh/train-00000-of-00001.parquet",
            "dataset_en_houses_4x5_5rh/train-00000-of-00001.parquet",
            "README.md",
        ),
        note="DFM10 uses selected Danish and English train configs only; validation and test remain held out.",
    ),
    HFDataset(
        name="alexandra_dane",
        repo_id="alexandrainst/dane",
        groups=("dfm10", "danish", "instruction", "ner"),
        allow_patterns=("dane.py", "README.md"),
        note="The DFM10 converter downloads the upstream ddt.zip referenced by the dataset loader and reads ddt.train.conllu only.",
    ),
    HFDataset(
        name="alexandra_dacoref",
        repo_id="alexandrainst/dacoref",
        groups=("dfm10", "danish", "instruction", "coreference"),
        allow_patterns=(
            "data/train-00000-of-00001-ffdeed5775622c14.parquet",
            "README.md",
        ),
        note="DFM10 uses train only; validation and test remain held out.",
    ),
    HFDataset(
        name="zai_deepdive",
        repo_id="zai-org/DeepDive",
        groups=("dfm10", "english", "instruction", "agentic", "search"),
        allow_patterns=(
            "data/trajectories_sft-00000-of-00001.parquet",
            "README.md",
        ),
        note=(
            "DFM10 uses only the 858 successful SFT search trajectories. "
            "QA/RL splits are excluded; trajectories require native-tool conversion."
        ),
    ),
    HFDataset(
        name="dfm10_synthetic_values_model_charter",
        repo_id="danish-foundation-models/synthetic-values-model-charter",
        groups=("dfm10", "english", "instruction", "alignment", "preference"),
        allow_patterns=(
            "README.md",
            "sft_train.jsonl",
            "sft_test.jsonl",
            "dpo_train.jsonl",
            "dpo_test.jsonl",
            "scenarios_train.jsonl",
            "scenarios_test.jsonl",
            "value_units.jsonl",
        ),
        note=(
            "DFM10 includes both nominal SFT splits; both DPO splits remain in "
            "a separate preference export. Based on model-charter commit "
            "e60e41aad338c6261cc21f926847b3ab77ff4226."
        ),
    ),
    HFDataset(
        name="dfm10_synthetic_values_model_charter_da",
        repo_id="schneiderkamplab/dfm10-synthetic-values-model-charter-da",
        groups=("dfm10", "danish", "instruction", "alignment", "preference"),
        allow_patterns=("README.md", "LICENSE.md", "data/**/*", "metadata/**/*", "recreate_dataset.py"),
        note="Audited Danish SFT/DPO adaptation; DFM10 SFT uses accepted chosen responses at repeat 10.",
    ),
    HFDataset(
        name="dfm10_bornholmsk_parallel",
        repo_id="strombergnlp/bornholmsk_parallel",
        groups=("dfm10", "danish", "translation", "dialect"),
        allow_patterns=("README.md", "bornholmsk_parallel.py", "dataset_infos.json"),
        note=(
            "DFM10 includes train, validation, and test in both translation directions. "
            "The converter fetches the six raw files from the immutable upstream revision "
            "pinned by the dataset loader."
        ),
        revision="3bc5cfb4ec514264fe2db5615fac9016f7251552",
    ),
    HFDataset(
        name="ra_diem_htr",
        repo_id="RA-Data-Science/DiEm_HTR",
        groups=("dfm10", "danish", "historical", "modernization"),
        allow_patterns=("README.md", "dataset_info.json", "data/DiEm_GT_HTR.parquet"),
        note=(
            "Historical Danish ALTO transcriptions. DFM10 admits only independently "
            "audited Gemma 4 31B modernization targets, never the page images as text SFT."
        ),
        revision="6984292ba5992f039ea8a90b3f0fce709ad63093",
    ),
    HFDataset(
        name="dfm10_danish_book_ads",
        repo_id="chcaa/danish-book-ads",
        groups=("dfm10", "danish", "historical", "bibliographic"),
        allow_patterns=("README.md", "data/train-*.parquet"),
        note=(
            "Historical book advertisements. DFM10 admits only grounded, checked "
            "extraction/classification targets after overlap and quality auditing."
        ),
        revision="0dd49411c8922bbcd4da60b147b0d7b4fa422f58",
    ),
    HFDataset(
        name="dfm10_croco_munin_da_50k_candidate",
        repo_id="danish-foundation-models/croco-munin-apertus-8b-da-50k",
        groups=("audit_candidate", "danish", "instruction", "alignment", "preference_candidate"),
        allow_patterns=("README.md", "preference_pairs.jsonl"),
        note=(
            "Excluded from DFM10 after overlap audit: only seven prompts were "
            "absent from the active croco-munin-apertus-8b-da-simpo-full-50k."
        ),
    ),
    HFDataset(
        name="dfm10_danish_personas_seed",
        repo_id="oliverkinch/danish-personas",
        groups=("dfm10", "danish", "synthetic_seed"),
        allow_patterns=("README.md", "data/train-*.parquet"),
        note="Generation seed only; persona rows are never tokenized directly.",
    ),
    HFDataset(
        name="dfm10_domsdatabasen",
        repo_id="alexandrainst/domsdatabasen",
        groups=("dfm10", "danish", "legal", "grounding_source"),
        allow_patterns=("README.md", "data/train-*.parquet"),
        note=(
            "Grounding source only. DFM10 uses non-empty pseudonymized text for "
            "generated and audited legal conversations; judgments are never "
            "admitted as raw continuation data."
        ),
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
        name="opus",
        repo_id="schneiderkamplab/opus-da-en-permissive",
        groups=("danish", "translation", "dfm_rebuild"),
        allow_patterns=("data/opus_da_en.jsonl.gz", "README.md"),
        note="Processed Danish-English OPUS permissive/public-domain subset used by DFM mixes.",
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
        name="oliverkinch_danmarks_statistik",
        repo_id="oliverkinch/danmarks-statistik",
        groups=("danish", "grounding_source", "dfm10"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="Source metadata and passages used with live DST URLs to recover rejected BT rows.",
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
        name="oliverkinch_danish_university_portals",
        repo_id="oliverkinch/danish-university-portals",
        groups=("dfm10_repair_support", "danish", "source_documents"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="Authoritative CC-BY full documents used to recover and audit truncated university-portals BT targets.",
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
    HFDataset(
        name="dfm_dyna_instruct",
        repo_id="danish-foundation-models/dfm-dyna-instruct",
        groups=("dfm7", "danish", "instruction", "code_agentic", "tool_use"),
        allow_patterns=("data/**/*.parquet", "README.md"),
        note="DFM7 expanded instruction collection; de-duplicate against DFM6 constituents.",
        gated=True,
    ),
    HFDataset(
        name="xlam_function_calling_60k",
        repo_id="Salesforce/xlam-function-calling-60k",
        groups=("dfm7", "tool_use", "function_calling"),
        allow_patterns=("*.json", "*.jsonl", "*.parquet", "data/**/*", "README.md"),
        note="APIGen/xLAM function-calling SFT; convert to native Gemma tools when access is available.",
        gated=True,
    ),
    HFDataset(
        name="glaive_function_calling_v2",
        repo_id="glaiveai/glaive-function-calling-v2",
        groups=("dfm7", "tool_use", "function_calling"),
        allow_patterns=("*.json", "*.jsonl", "*.parquet", "data/**/*", "README.md"),
        note="Text-format function-calling SFT; parse system/chat strings into native Gemma tools.",
    ),
    HFDataset(
        name="toolace",
        repo_id="Team-ACE/ToolACE",
        groups=("dfm7", "tool_use", "function_calling"),
        allow_patterns=("*.json", "*.jsonl", "*.parquet", "data/**/*", "README.md"),
        note="ToolACE function-calling conversations; parse bracketed tool-call strings into native Gemma tools.",
    ),
    HFDataset(
        name="danish_wildchat4_8m",
        repo_id="danish-foundation-models/danish-wildchat4.8M",
        groups=("dfm7", "danish", "instruction", "chat"),
        allow_patterns=("data/*.parquet", "README.md"),
        note="DFM7 expanded Danish WildChat replacement for the 100k messages slice.",
        gated=True,
    ),
    HFDataset(
        name="ai_arenaen_conversations",
        repo_id="danish-foundation-models/ai-arenaen-conversations",
        groups=("dfm7", "danish", "dialogue", "alignment"),
        allow_patterns=("data/**/*.parquet", "data/**/*.jsonl", "README.md"),
        note="Danish AI-Arenaen conversation/preference data.",
        gated=True,
    ),
    HFDataset(
        name="ai_arena_udtraek",
        repo_id="danish-foundation-models/ai_arena_udtraek",
        groups=("dfm7", "danish", "dialogue", "alignment"),
        allow_patterns=("*.parquet", "data/**/*.parquet", "README.md"),
        note="Danish AI Arena extract.",
    ),
    HFDataset(
        name="kaenguruen",
        repo_id="danish-foundation-models/kaenguruen",
        groups=("dfm7", "danish", "math_reasoning"),
        allow_patterns=("data/*.parquet", "README.md"),
        note="DFM7 decision: include for training; convert to explicit Danish MCQ prompts before tokenization.",
        gated=True,
    ),
    HFDataset(
        name="oliverkinch_danish_qa",
        repo_id="oliverkinch/danish-qa",
        groups=("dfm7", "danish", "qa", "instruction"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="Danish factual QA.",
    ),
    HFDataset(
        name="oliverkinch_danish_summarization",
        repo_id="oliverkinch/danish-summarization",
        groups=("dfm7", "danish", "summarization"),
        allow_patterns=("**/*.parquet", "README.md"),
        note="Danish summarization configs, including EUR-Lex and Nordjylland.",
    ),
    HFDataset(
        name="oliverkinch_da_instruct_dynaword",
        repo_id="oliverkinch/da-instruct-dynaword",
        groups=("dfm7", "danish", "instruction", "dynaword"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="DFM7 breadth source: include alongside HQ/contemporary variants.",
    ),
    HFDataset(
        name="oliverkinch_da_instruct_dynaword_hq",
        repo_id="oliverkinch/da-instruct-dynaword-hq",
        groups=("dfm7", "danish", "instruction", "dynaword"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="DFM7 breadth source.",
    ),
    HFDataset(
        name="oliverkinch_da_instruct_dynaword_contemporary",
        repo_id="oliverkinch/da-instruct-dynaword-contemporary",
        groups=("dfm7", "danish", "instruction", "dynaword"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="DFM7 breadth source.",
    ),
    HFDataset(
        name="oliverkinch_da_instruct_dynaword_contemporary_hq",
        repo_id="oliverkinch/da-instruct-dynaword-contemporary-hq",
        groups=("dfm7", "danish", "instruction", "dynaword"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="DFM7 breadth source.",
    ),
    HFDataset(
        name="oliverkinch_autodata_da_sft",
        repo_id="oliverkinch/autodata-da-sft",
        groups=("dfm7", "danish", "instruction", "synthetic"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="Small Danish synthetic SFT/chat source.",
    ),
    HFDataset(
        name="giannor_dala_tv2r_it",
        repo_id="giannor/dala_tv2r_it",
        groups=("dfm8", "danish", "gec", "linguistic_acceptability"),
        allow_patterns=("*.json", "*.jsonl", "*.parquet", "data/**/*", "README.md"),
        note="DFM8 decision: fully include TV2R instruction-formatted DaLA acceptability rows.",
    ),
    HFDataset(
        name="giannor_gec_dala_tv2r_it",
        repo_id="giannor/gec_dala_tv2r_it",
        groups=("dfm8", "danish", "gec", "correction"),
        allow_patterns=("*.json", "*.jsonl", "*.parquet", "data/**/*", "README.md"),
        note="DFM8 decision: fully include TV2R instruction-formatted GEC-DaLA rows.",
    ),
    HFDataset(
        name="kobprof_skolegpt_instruct",
        repo_id="kobprof/skolegpt-instruct",
        groups=("dfm8", "danish", "education", "instruction"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="DFM8 Danish school/education instruction source; convert system_prompt/question/response rows to Gemma4 chat.",
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
        repo_id="allenai/code-meta-reasoning-filtered",
        groups=("allenai", "code_agentic", "reasoning", "dfm10"),
        allow_patterns=("data/train-*.parquet", "README.md"),
        note="Structured source used by the DFM10 repair; retains prompt family, question, generation prompt, and response boundaries.",
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
    effective_revision = revision or dataset.revision
    info = api.dataset_info(
        dataset.repo_id,
        revision=effective_revision,
        files_metadata=True,
        token=token,
    )
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
        revision=args.revision or dataset.revision,
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
