#!/usr/bin/env python3
"""Build upload-ready Hugging Face packages for DFM10-local datasets.

This command only materializes local packages. It never creates repositories or
contacts the Hugging Face upload API. Dataset rows use the same chat-oriented
JSONL convention as the existing sapient-synth-* and transformations-* exports.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import gzip
import hashlib
import io
import json
import re
import shutil
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "exports_dfm10"
ROWS_PER_SHARD = 250_000


class SkippableRow(ValueError):
    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
DFM9_HF_IDS = (
    "AI-MO/NuminaMath-1.5",
    "nvidia/Nemotron-Terminal-Corpus",
    "allenai/code-meta-reasoning-filtered",
    "Muennighoff/natural-instructions",
    "grammarly/coedit",
    "facebook/asset",
    "nvidia/Nemotron-SFT-SWE-v2",
    "danish-foundation-models/croco-munin-apertus-8b-da-simpo-full-50k",
    "danish-foundation-models/multilingual-gsm-symbolic",
)

WORK_IN_PROGRESS = {
    "dfm10-mimir-ifeval-verifier-sft": (
        "Planned verifier-backed instruction-following generation; target 200,000-300,000 "
        "accepted rows. Generation, verification, audit, tokenization, and packaging are pending."
    ),
    "dfm10-mimir-event-coreference-sft": (
        "Planned event-coreference and temporal-state supervision for WinoGrande and "
        "HellaSwag capability transfer; target 300,000-450,000 accepted rows."
    ),
    "dfm10-mimir-drop-reasoning-sft": (
        "Planned grounded discrete reading-comprehension supervision; target 200,000-300,000 "
        "accepted rows. Generation, exact decontamination, audit, and packaging are pending."
    ),
    "dfm10-mimir-boolq-entailment-sft": (
        "Planned passage-grounded yes/no entailment supervision; target 100,000-200,000 "
        "accepted rows. Generation, exact decontamination, audit, and packaging are pending."
    ),
}

# Planned packages have stable export identities before their source rows are
# materialized. This makes the root inventory the authoritative queue without
# creating empty Hugging Face packages or pretending that zero-row builds are ready.
PLANNED_PACKAGE_METADATA = {
    "dfm10-cor-sem-sft": {
        "upstream": ["DSL/CST COR.SEM 1.0"],
        "languages": ["da"],
        "category": "Danish lexical semantics",
        "source_policy": (
            "CC0 COR.SEM formal fields only; COR.SEM.EXT definitions and usage "
            "examples are excluded under CC BY-NC-ND."
        ),
    },
    "dfm10-danish-book-ads-sft": {
        "upstream": ["chcaa/danish-book-ads"],
        "languages": ["da"],
        "category": "Danish historical bibliographic extraction",
        "target_rows": {"minimum": 1, "maximum": 80_938},
        "source_policy": (
            "Only manually checked or adequately confident labels grounded in "
            "the advertisement excerpt may become targets."
        ),
    },
    "dfm10-diem-historical-modernization": {
        "upstream": ["RA-Data-Science/DiEm_HTR"],
        "languages": ["da"],
        "category": "Danish historical modernization",
        "target_rows": {"minimum": 881, "maximum": 1_259},
        "source_policy": (
            "ALTO transcription only; page images are not packaged. Every target "
            "requires independent semantic-preservation audit."
        ),
    },
    "dfm10-sks-tei-sft": {
        "upstream": ["kb-dk/SKS_tei"],
        "languages": ["da"],
        "category": "Danish scholarly text and modernization",
        "source_policy": (
            "Prefer unique editorial structure and grounded relations; authorial "
            "text requires exact and near-duplicate checks against DynaWord ADL."
        ),
    },
    "dfm10-danish-persona-chats": {
        "upstream": ["oliverkinch/danish-personas"],
        "languages": ["da"],
        "category": "Danish conversation",
        "target_rows": {"minimum": 20_000, "maximum": 25_000},
        "target_assistant_turns": {"minimum": 100_000, "maximum": 125_000},
        "selection_policy": "retain every independently audited accepted candidate",
    },
    "dfm10-domsdatabasen-grounded-chats": {
        "upstream": ["alexandrainst/domsdatabasen"],
        "languages": ["da"],
        "category": "Grounded Danish legal conversation",
        "target_rows": {"minimum": 3_000, "maximum": 4_500},
        "target_assistant_turns": {"minimum": 12_000, "maximum": 22_500},
        "selection_policy": "retain every independently audited accepted candidate",
        "source_policy": "non-empty pseudonymized text only; no raw continuation",
    },
    "dfm10-mimir-ifeval-verifier-sft": {
        "upstream": ["Novel verifier-backed synthetic instruction tasks"],
        "languages": ["da", "en"],
        "category": "Instruction following",
        "target_rows": {"minimum": 200_000, "maximum": 300_000},
    },
    "dfm10-mimir-answer-contract-calibration": {
        "upstream": ["Novel grounded Mimir augmentation tasks"],
        "languages": ["da", "en"],
        "category": "Answer-contract calibration",
        "target_rows": {"minimum": 150_000, "maximum": 150_000},
    },
    "dfm10-mimir-event-coreference-sft": {
        "upstream": ["Novel event-coreference and temporal-state synthetic tasks"],
        "languages": ["da", "en"],
        "category": "Commonsense reasoning",
        "target_rows": {"minimum": 300_000, "maximum": 450_000},
    },
    "dfm10-mimir-drop-reasoning-sft": {
        "upstream": ["Novel openly grounded passages and generated questions"],
        "languages": ["en"],
        "category": "Discrete reading comprehension",
        "target_rows": {"minimum": 200_000, "maximum": 300_000},
    },
    "dfm10-mimir-boolq-entailment-sft": {
        "upstream": ["Novel openly grounded passages and generated propositions"],
        "languages": ["da", "en"],
        "category": "Boolean entailment",
        "target_rows": {"minimum": 100_000, "maximum": 200_000},
    },
}

# Verified against the live schneiderkamplab dataset namespace on 2026-08-30.
# Keep this explicit: package preparation is intentionally offline and must not
# infer publication from a local directory or a successful schema validation.
UPLOADED_PACKAGES = frozenset(
    {
        "dfm10-alexandra-dane",
        "dfm10-alexandra-multi-zebra-logic",
        "dfm10-alexandra-scandi-qa-da",
        "dfm10-andersen-modernization",
        "dfm10-ai-arena-udtraek-sft",
        "dfm10-arxiv-paper-summarization-sft",
        "dfm10-bornholmsk-parallel",
        "dfm10-code-meta-reasoning-repaired",
        "dfm10-cor-sem-sft",
        "dfm10-croco-munin-chosen-sft",
        "dfm10-danish-book-ads-sft",
        "dfm10-danish-framenet-sft",
        "dfm10-danish-lexical-sentiment-sft",
        "dfm10-danish-persona-chats",
        "dfm10-danish-university-portals-bt-repaired",
        "dfm10-danish-wikipedia-open-chats",
        "dfm10-danmarks-statistik-bt-repaired",
        "dfm10-deepdive-gemma4-tool-use",
        "dfm10-diem-historical-modernization",
        "dfm10-domsdatabasen-grounded-chats",
        "dfm10-dolci-tool-use-repaired",
        "dfm10-dst-table-prompts-repaired",
        "dfm10-dynaword-instruct-repaired",
        "dfm10-folketingets-dokumenter-denoising",
        "dfm10-folketingets-dokumenter-error-correction",
        "dfm10-folketingets-dokumenter-prefix-continuation",
        "dfm10-folketingets-dokumenter-span-filling",
        "dfm10-glaive-native-tool-use",
        "dfm10-govreport-summarization-repaired",
        "dfm10-machine-translation-da-uk-repaired",
        "dfm10-medquad-danish-sft",
        "dfm10-medquad-english-sft",
        "dfm10-mimir-answer-contract-calibration",
        "dfm10-mimir-boolq-entailment-sft",
        "dfm10-mimir-drop-reasoning-sft",
        "dfm10-mimir-event-coreference-sft",
        "dfm10-mimir-grounded-expanded-sft",
        "dfm10-mimir-ifeval-verifier-sft",
        "dfm10-natural-instructions-filtered-sft",
        "dfm10-nemotron-terminal-sft",
        "dfm10-nemotron-swe-repaired",
        "dfm10-nordjylland-news-repaired",
        "dfm10-numinamath-valid-sft",
        "dfm10-openmathinstruct2-repaired",
        "dfm10-openstax-open-chats",
        "dfm10-openstax-mimir-sft",
        "dfm10-opus-da-en-repaired",
        "dfm10-sapient-acereason-filtered-sft",
        "dfm10-sapient-amps-mathematica-filtered-sft",
        "dfm10-sapient-dmmath-filtered-sft",
        "dfm10-sapient-flan-cot-filtered-sft",
        "dfm10-sapient-flan-dialog-filtered-sft",
        "dfm10-sapient-flan-flan-filtered-sft",
        "dfm10-sapient-flan-niv2-filtered-sft",
        "dfm10-sapient-flan-t0-filtered-sft",
        "dfm10-sapient-openmathinstruct2-filtered-sft",
        "dfm10-sapient-openthoughts2-filtered-sft",
        "dfm10-sapient-platypus-filtered-sft",
        "dfm10-sapient-qrecc-ii-repaired",
        "dfm10-sapient-scibench-repaired",
        "dfm10-sapient-sudoku-extreme-filtered-sft",
        "dfm10-sapient-synth-filtered-sft",
        "dfm10-sapient-tasksource-filtered-sft",
        "dfm10-sapient-textbook-reasoning-filtered-sft",
        "dfm10-scientific-summaries-repaired",
        "dfm10-sks-tei-sft",
        "dfm10-synthetic-values-model-charter-da",
        "dfm10-tidsskrift-open-chats",
        "dfm10-tidsskrift-open-sft",
        "dfm10-toolace-native-tool-use",
        "dfm10-wiki-cat-sum-repaired",
        "dfm10-xlam-native-tool-use",
    }
)

# Corpus-level sampling policy. This belongs in the root DFM10 inventory rather
# than the standalone dataset cards: downstream users need not reproduce our
# mixture weights. Omitted packages have the conservative one-pass default.
PACKAGE_REPEATS = {
    "dfm10-alexandra-dane": 4,
    "dfm10-alexandra-scandi-qa-da": 4,
    "dfm10-andersen-modernization": 20,
    "dfm10-bornholmsk-parallel": 10,
    "dfm10-cor-sem-sft": 2,
    "dfm10-danish-book-ads-sft": 2,
    "dfm10-diem-historical-modernization": 5,
    "dfm10-sks-tei-sft": 2,
    "dfm10-danish-university-portals-bt-repaired": 10,
    "dfm10-danish-persona-chats": 2,
    "dfm10-danmarks-statistik-bt-repaired": 10,
    "dfm10-dolci-tool-use-repaired": 2,
    "dfm10-dst-table-prompts-repaired": 10,
    "dfm10-dynaword-instruct-repaired": 4,
    "dfm10-govreport-summarization-repaired": 2,
    "dfm10-wiki-cat-sum-repaired": 2,
    "dfm10-synthetic-values-model-charter-da": 10,
}


@dataclass(frozen=True)
class ExportSpec:
    name: str
    source_root: str
    patterns: tuple[str, ...]
    upstream: tuple[str, ...]
    languages: tuple[str, ...]
    category: str
    description: str
    transformation: str
    upload_review: str = "Review upstream terms and dataset-card attribution before upload."
    license: str = "other"
    license_notice: str = (
        "This package does not replace or broaden the licenses of its upstream "
        "materials. Review the dataset card, preserve upstream notices and "
        "attribution, and record the release decision before upload."
    )
    selection_policy: str | None = None


SAPIENT_EXPORT_PARTITIONS = (
    ("platypus", "data/Platypus/*", "Platypus", "Science and reasoning"),
    ("flan-niv2", "data_clustered/flan/niv2_*", "FLAN Natural Instructions v2", "Instruction following"),
    ("flan-t0", "data_clustered/flan/t0_*", "FLAN T0", "Instruction following"),
    ("flan-flan", "data_clustered/flan/flan_*", "FLAN collection", "Instruction following"),
    ("flan-cot", "data_clustered/flan/cot_*", "FLAN chain-of-thought", "Reasoning"),
    ("flan-dialog", "data_clustered/flan/dialog_*", "FLAN dialogue", "Conversation"),
    ("tasksource", "data_clustered/tasksource/*", "Tasksource", "Reasoning and classification"),
    ("synth", "data_clustered/SYNTH/*", "Sapient SYNTH", "Synthetic instruction"),
    ("dmmath", "data_clustered/dmmath/*", "DeepMind Mathematics", "Math reasoning"),
    ("amps-mathematica", "data_clustered/ampsmathematica/*", "AMPS Mathematica", "Math reasoning"),
    ("textbook-reasoning", "data_clustered/textbookreasoning/*", "Textbook reasoning", "Science reasoning"),
    ("openmathinstruct2", "data_clustered/openmathinstruct2/*", "OpenMathInstruct-2", "Math reasoning"),
    ("sudoku-extreme", "data_clustered/sudoku_extreme/*", "Sudoku Extreme", "Puzzle reasoning"),
    ("openthoughts2", "data_clustered/openthoughts2/*", "OpenThoughts2", "Math reasoning"),
    ("acereason", "data_clustered/acereason/*", "AceReason", "Math reasoning"),
)


# Root-inventory release lineage. Standalone packages preserve full native
# source conversations; the context limit below describes the DFM10 training
# rendering and is not a destructive export transform.
EXPORT_VERSION_METADATA: dict[str, dict[str, Any]] = {
    "dfm10-deepdive-gemma4-tool-use": {
        "artifact_version": "2026-08-29-native-source-v1",
        "intended_hf_id": "schneiderkamplab/dfm10-deepdive-gemma4-tool-use",
        "training_rendering": {
            "version": "2026-08-30-complete-message-4k-v2",
            "chat_template": "gemma4_native_chat",
            "max_seq_len": 4096,
            "assistant_target_expansion": True,
            "overlength_policy": "complete-message window; never truncate target",
        },
    },
    "dfm10-dolci-tool-use-repaired": {
        "artifact_version": "2026-08-29-native-source-v1",
        "intended_hf_id": "schneiderkamplab/dfm10-dolci-tool-use-repaired",
        "replaces_training_prefixes": [
            "dolci_instruct_sft_tool_use__",
            "dolci_instruct_sft_tool_use_sa__",
            "dolci_native_tool_use__",
        ],
        "training_rendering": {
            "version": "2026-08-30-complete-message-4k-v2",
            "chat_template": "gemma4_native_chat",
            "max_seq_len": 4096,
            "assistant_target_expansion": True,
            "overlength_policy": "retain original request plus newest complete call/result suffix; never truncate target",
        },
    },
    "dfm10-nemotron-terminal-sft": {
        "artifact_version": "2026-08-30-native-v1",
        "intended_hf_id": "schneiderkamplab/dfm10-nemotron-terminal-sft",
        "replaces_training_prefixes": ["nemotron_terminal_corpus__"],
        "training_rendering": {
            "version": "2026-08-30-complete-message-4k-v2",
            "chat_template": "gemma4_native_chat",
            "max_seq_len": 4096,
            "assistant_target_expansion": True,
            "preserve_first_user": True,
            "overlength_policy": "retain initial task plus newest complete terminal suffix; never truncate target",
        },
    },
}

for suffix, _pattern, _family, _category in SAPIENT_EXPORT_PARTITIONS:
    name = f"dfm10-sapient-{suffix}-filtered-sft"
    EXPORT_VERSION_METADATA[name] = {
        "artifact_version": "2026-08-30-policy-filtered-v1",
        "intended_hf_id": f"schneiderkamplab/{name}",
        "selection_policy_version": "config/data/source_filter.yaml@2026-08-30",
    }

# These packages are part of the intended next upload set. Missing package
# directories remain visible as non-materialized WIP records; once a validated
# package manifest exists, ordinary inventory logic promotes it to
# ready_for_upload without claiming that an upload occurred.
PLANNED_UPLOAD_METADATA: dict[str, dict[str, Any]] = {
    "dfm10-nemotron-terminal-sft": {
        "upstream": ["nvidia/Nemotron-Terminal-Corpus"],
        "languages": ["en"],
        "category": "Terminal agent",
        "status_reason": (
            "Native source package materialization is in progress; upload follows "
            "complete package validation."
        ),
    },
}
for suffix, _pattern, family, category in SAPIENT_EXPORT_PARTITIONS:
    name = f"dfm10-sapient-{suffix}-filtered-sft"
    PLANNED_UPLOAD_METADATA[name] = {
        "upstream": [
            "sapientinc/HRM-Text-data-io-cleaned-20260515",
            family,
        ],
        "languages": ["en", "multilingual"] if suffix.startswith("flan-") else ["en"],
        "category": category,
        "status_reason": (
            "Policy-filtered provenance package materialization or release review "
            "is pending; upload requires the recorded per-family review."
        ),
    }


SPECS = (
    ExportSpec(
        "dfm10-synthetic-values-model-charter-da",
        "data/converted_sources/dfm10_synthetic_values_model_charter_da/data",
        ("model_charter_values_da.jsonl",),
        ("danish-foundation-models/synthetic-values-model-charter",),
        ("da",),
        "Danish values and preference alignment",
        "Independently audited Danish adaptations of the complete aligned SFT/DPO scenario tuples.",
        "Gemma 4 31B translates each prompt, chosen answer, rejected answer, and rejection rationale atomically. A separate inference pass checks Danish quality, semantic fidelity, and preference preservation. Only accepted chosen answers become DFM10 SFT targets; preference fields remain packaged for later DPO.",
        upload_review="Release approved after complete package validation; retain English originals, stable scenario IDs, and model-charter provenance.",
        selection_policy="all rows passing independent translation and preference-preservation audit",
    ),
    ExportSpec(
        "dfm10-medquad-english-sft",
        "data/dfm10_medquad_sources",
        ("medquad_english.jsonl",),
        ("abachaa/MedQuAD",),
        ("en",),
        "English medical consumer QA",
        "Audited English consumer-health question-answer pairs from the openly licensed MedQuAD source corpus.",
        "The official MedQuAD XML is pinned by revision; rows with deliberately withheld answers, over-budget content, duplicates, failed audits, or incomplete translation/audit state are excluded. Accepted rows retain source URL, source site, question type, UMLS metadata, attribution, and audit results.",
        upload_review="Release approved after complete package validation; preserve MedQuAD attribution and row-level source metadata.",
        license="cc-by-4.0",
        license_notice="MedQuAD is distributed under CC BY 4.0. Preserve attribution to Asma Ben Abacha and Dina Demner-Fushman (2019) and the row-level upstream source metadata. Deliberately withheld MedlinePlus-derived answers are not included.",
        selection_policy="all independently audited accepted English rows from the complete-pair intersection",
    ),
    ExportSpec(
        "dfm10-medquad-danish-sft",
        "data/dfm10_medquad_sources",
        ("medquad_danish.jsonl",),
        ("abachaa/MedQuAD",),
        ("da",),
        "Danish medical consumer QA",
        "Audited Danish translations of openly licensed MedQuAD consumer-health question-answer pairs.",
        "Gemma 4 31B translates accepted English pairs without medical expansion. Independent auditing checks medical coherence, factual and numeric preservation, translation fidelity, natural Danish, freshness risk, and training value. Stable pair IDs and all English-source attribution are retained.",
        upload_review="Release approved after complete package validation; label the rows as machine-translated adaptations and preserve MedQuAD attribution.",
        license="cc-by-4.0",
        license_notice="The MedQuAD source is distributed under CC BY 4.0. Danish fields are machine-translated adaptations and retain attribution to Asma Ben Abacha and Dina Demner-Fushman (2019), source URLs, and row-level provenance. Deliberately withheld MedlinePlus-derived answers are not included.",
        selection_policy="all independently audited accepted Danish translations from the complete-pair intersection",
    ),
    ExportSpec(
        "dfm10-danish-persona-chats",
        "data/dfm10_danish_persona_chats_source",
        ("danish_persona_chats__accepted.jsonl",),
        ("oliverkinch/danish-personas",),
        ("da",),
        "Danish conversation",
        "Audited multi-turn Danish assistant conversations seeded by non-sensitive persona attributes.",
        "Gemma 4 31B generates natural three-to-seven-turn chats; a separate judge checks language, coherence, privacy, and training value. Every accepted candidate is retained.",
        selection_policy="all independently audited accepted rows",
    ),
    ExportSpec(
        "dfm10-domsdatabasen-grounded-chats",
        "data/dfm10_domsdatabasen_grounded_chats_source",
        ("domsdatabasen_grounded_chats__accepted.jsonl",),
        ("alexandrainst/domsdatabasen",),
        ("da",),
        "Grounded Danish legal conversation",
        "Audited multi-turn Danish conversations grounded in pseudonymized court decisions.",
        "Only non-empty text_anonymized evidence is excerpted. Gemma 4 31B generates grounded chats and a separate judge checks support, legal-role distinctions, privacy, language, and training value. Every accepted candidate is retained.",
        selection_policy="all independently audited accepted rows; raw judgments are never emitted as continuation data",
    ),
    ExportSpec(
        "dfm10-glaive-native-tool-use",
        "data/dfm7_special_sources/glaive_native_tool_use",
        ("train.jsonl",),
        ("glaiveai/glaive-function-calling-v2",),
        ("en",),
        "Tool use",
        "Glaive function-calling conversations converted to Gemma-native structured tool supervision.",
        "Custom parsing recovers tool schemas and calls, normalizes function names and arguments, assigns call IDs, and rejects malformed trajectories.",
    ),
    ExportSpec(
        "dfm10-toolace-native-tool-use",
        "data/dfm7_special_sources/toolace_native_tool_use",
        ("train.jsonl",),
        ("Team-ACE/ToolACE",),
        ("en",),
        "Tool use",
        "ToolACE conversations converted to Gemma-native structured tool supervision.",
        "Bracketed call syntax is parsed into native tools, assistant tool calls, call IDs, and matched tool results; malformed trajectories are rejected.",
    ),
    ExportSpec(
        "dfm10-xlam-native-tool-use",
        "data/dfm7_special_sources/xlam_native_tool_use",
        ("train.jsonl",),
        ("Salesforce/xlam-function-calling-60k",),
        ("en",),
        "Tool use",
        "xLAM function-calling rows converted to Gemma-native structured tool supervision.",
        "APIGen tool schemas and calls are normalized into native tools and assistant tool_calls with structured argument mappings and stable call IDs.",
    ),
    ExportSpec(
        "dfm10-natural-instructions-filtered-sft",
        "data/converted_sources/posttrain_natural_instructions",
        ("train/*.parquet",),
        ("Muennighoff/natural-instructions",),
        ("en",),
        "Instruction following",
        "Natural Instructions train tasks after the DFM9 PII-sensitive task-family exclusion.",
        "Task definitions and instance inputs are composed into prompts; 96 task files matching the recorded PII-sensitive filename policy are excluded before conversion.",
        selection_policy="scripts/convert_dfm9_new_sources.py:PII_EXCLUDE_KEYWORDS",
    ),
    ExportSpec(
        "dfm10-ai-arena-udtraek-sft",
        "data/dfm7_special_sources/ai_arena_udtraek",
        ("train.jsonl",),
        ("danish-foundation-models/ai_arena_udtraek",),
        ("da", "en", "multilingual"),
        "Conversation",
        "AI Arena preference pairs expanded into independently supervised conversation branches.",
        "Both model branches are retained separately with normalized messages, system prompts, model names, branch labels, and conversation identifiers.",
    ),
    ExportSpec(
        "dfm10-croco-munin-chosen-sft",
        "data/converted_sources/croco_munin_da_sft",
        ("data/*.parquet",),
        ("danish-foundation-models/croco-munin-apertus-8b-da-simpo-full-50k",),
        ("da",),
        "Danish instruction",
        "Croco-Munin preference examples converted to SFT using only the chosen response.",
        "Each non-empty prompt and chosen response becomes one direct user/assistant training example; rejected responses are not included.",
    ),
    ExportSpec(
        "dfm10-numinamath-valid-sft",
        "data/converted_sources/numinamath_1_5",
        ("data/*.parquet",),
        ("AI-MO/NuminaMath-1.5",),
        ("en",),
        "Math reasoning",
        "NuminaMath problems retained only when both upstream validity flags are affirmative.",
        "Rows require problem_is_valid == 'Yes' and solution_is_valid == 'Yes'; retained solutions use the chain-of-thought training contract.",
        selection_policy="scripts/convert_dfm9_new_sources.py:convert_numinamath",
    ),
    ExportSpec(
        "dfm10-nemotron-terminal-sft",
        "data/converted_sources/nemotron_terminal_corpus_native",
        ("**/*.parquet",),
        ("nvidia/Nemotron-Terminal-Corpus",),
        ("en",),
        "Terminal agent",
        "Nemotron Terminal conversations preserved as native multi-turn chat rows.",
        "Every original conversation retains native message roles and source-relative provenance. Assistant-turn supervision is expanded only by the Gemma chat tokenizer; no prior turns are flattened into user text.",
        selection_policy="scripts/prepare_nemotron_terminal_native.py",
    ),
    *tuple(
        ExportSpec(
            f"dfm10-sapient-{suffix}-filtered-sft",
            "data/filtered_sources/sapient_cleaned",
            (pattern,),
            ("sapientinc/HRM-Text-data-io-cleaned-20260515", family),
            ("en", "multilingual") if suffix.startswith("flan-") else ("en",),
            category,
            f"The DFM10-safe policy-selected {family} partition from the Sapient source mirror.",
            "Only files present in the active filtered Sapient symlink tree are packaged. "
            "The partition boundary follows the original provenance family and retains "
            "the training-visible condition, instruction, and response fields.",
            upload_review=(
                "Perform a per-family provenance, attribution, licence, privacy, and release "
                "review before upload; inclusion in an academic TDM training run does not by "
                "itself establish redistribution permission."
            ),
            selection_policy="config/data/source_filter.yaml",
        )
        for suffix, pattern, family, category in SAPIENT_EXPORT_PARTITIONS
    ),
    ExportSpec(
        "dfm10-andersen-modernization",
        "data/dfm10_andersen_sources",
        ("andersen_modernization__pairs_chunked_train.jsonl",),
        ("ogierMontanus/hcandersenDk_data_2024",),
        ("da",),
        "Danish modernization",
        "Paragraph-aligned historical-to-modern Danish instruction data; train split only.",
        "Historical and modern TEI/XML editions are paired and split into paragraph-aligned chat rows.",
        "Retain the AGPLv3 notice and the work-level scholarly credits recorded in the TEI headers.",
        license="agpl-3.0",
        license_notice=(
            "The source corpus declares GNU AGPLv3. Redistributed and transformed "
            "rows retain that license; preserve the corpus notice and work-level credits."
        ),
    ),
    ExportSpec(
        "dfm10-bornholmsk-parallel",
        "data/converted_sources/bornholmsk_parallel",
        ("bornholmsk_parallel__all_splits.parquet",),
        ("strombergnlp/bornholmsk_parallel",),
        ("da",),
        "Danish dialect translation",
        "Bidirectional Bornholmsk and standard-Danish translation supervision.",
        "All 6,785 official train, validation, and test pairs are retained with their original split metadata and emitted in both directions.",
        "Preserve attribution to Leon Derczynski, Alex Speed Kjeldsen, the Bornholmsk contributor community, and the original dataset paper.",
        license="cc-by-4.0",
        license_notice=(
            "The upstream parallel corpus and this transformed package are "
            "distributed under CC BY 4.0. Preserve creator, paper, and community attribution."
        ),
        selection_policy="scripts/prepare_dfm10_bornholmsk_parallel.py",
    ),
    ExportSpec(
        "dfm10-cor-sem-sft",
        "data/converted_sources/cor_sem_sft",
        ("cor_sem__grounded_tasks.parquet",),
        ("DSL/CST COR.SEM 1.0",),
        ("da",),
        "Danish lexical semantics",
        "Grounded lexical-semantic questions generated directly from CC0 COR.SEM fields.",
        "A deterministic lemma-disjoint holdout is excluded; COR.SEM.EXT definitions and examples are never read into targets.",
        license="cc0-1.0",
        selection_policy="scripts/prepare_dfm10_cor_sem.py",
    ),
    ExportSpec(
        "dfm10-danish-book-ads-sft",
        "data/converted_sources/danish_book_ads_sft",
        ("danish_book_ads__checked_grounded_tasks.parquet",),
        ("chcaa/danish-book-ads",),
        ("da",),
        "Danish historical bibliographic extraction",
        "Grounded title, author, normalization, and structured extraction tasks from historical Danish book advertisements.",
        "Only manually checked ads are used, and extraction targets must occur in the advertisement text; an ad-disjoint holdout is excluded.",
        selection_policy="scripts/prepare_dfm10_danish_book_ads.py",
    ),
    ExportSpec(
        "dfm10-sks-tei-sft",
        "data/converted_sources/sks_tei_sft",
        ("sks_tei__editorial_commentary_qa.parquet",),
        ("kb-dk/SKS_tei",),
        ("da",),
        "Danish scholarly commentary",
        "Questions grounded in the scholarly SKS commentary on named passages and references.",
        "Only editorial kom.xml commentary is included; raw authorial prose and un-audited modernization are deferred.",
        license="cc0-1.0",
        selection_policy="scripts/prepare_dfm10_sks_tei.py",
    ),
    ExportSpec(
        "dfm10-diem-historical-modernization",
        "data/converted_sources/diem_modernization",
        ("diem_modernization__accepted.jsonl",),
        ("RA-Data-Science/DiEm_HTR",),
        ("da",),
        "Danish historical modernization",
        "ALTO-derived historical Danish passages paired with faithful modern Danish renderings.",
        "Gemma 4 31B generates targets from source lines; an independent Gemma 4 E4B judge must accept each packaged row.",
        selection_policy="scripts/prepare_dfm10_diem_modernization.py; scripts/run_dfm10_dynaword_sft.py",
    ),
    ExportSpec(
        "dfm10-alexandra-scandi-qa-da",
        "data/dfm10_alexandra_sources",
        ("alexandra_scandi_qa_da__train.jsonl",),
        ("alexandrainst/scandi-qa",),
        ("da",),
        "Danish QA",
        "Danish ScandiQA train examples converted to chat supervision.",
        "Only the upstream Danish train split is represented.",
    ),
    ExportSpec(
        "dfm10-alexandra-dane",
        "data/dfm10_alexandra_sources",
        ("alexandra_dane__train.jsonl",),
        ("alexandrainst/dane",),
        ("da",),
        "Danish NER",
        "DaNE train examples converted to structured Danish NER instructions.",
        "Only ddt.train.conllu is converted; held-out splits are excluded.",
    ),
    ExportSpec(
        "dfm10-alexandra-multi-zebra-logic",
        "data/dfm10_alexandra_sources",
        ("alexandra_multi_zebra__*.jsonl",),
        ("alexandrainst/multi-zebra-logic",),
        ("da", "en"),
        "Reasoning",
        "Selected Danish and English Multi-Zebra train configurations in chat form.",
        "Six selected train configurations are combined; validation and test are excluded.",
    ),
    ExportSpec(
        "dfm10-deepdive-gemma4-tool-use",
        "data/dfm10_deepdive_sources",
        ("zai_deepdive_trajectories_sft__train.jsonl",),
        ("zai-org/DeepDive",),
        ("en",),
        "Agentic search",
        "DeepDive trajectories converted to Gemma-native structured tool calls.",
        "Legacy XML/ReAct calls and visible think blocks are replaced by structured search, click, and open calls.",
    ),
    *tuple(
        ExportSpec(
            f"dfm10-{task}",
            f"data/dfm10_folketing_transform_sources_audited/{task}/data",
            ("train-*.jsonl.gz",),
            ("Rigsarkivet handover 14004 / Folketinget",),
            ("da",),
            "Danish transformation",
            f"Audited {task} tasks derived from Folketing documents.",
            "The complete generated task family is filtered by the production DFM10 audit before packaging.",
            "Attribute Folketinget as creator and Rigsarkivet as publisher.",
            license="cc-by-4.0",
            license_notice=(
                "The source dataset is published under Creative Commons Attribution "
                "4.0. Attribute Folketinget as creator and Rigsarkivet as publisher."
            ),
        )
        for task in (
            "folketingets-dokumenter-denoising",
            "folketingets-dokumenter-error-correction",
            "folketingets-dokumenter-prefix-continuation",
            "folketingets-dokumenter-span-filling",
        )
    ),
    ExportSpec(
        "dfm10-openmathinstruct2-repaired",
        "data/converted_sources/openmathinstruct2_repaired",
        ("*.parquet",),
        ("nvidia/OpenMathInstruct-2",),
        ("en",),
        "Math reasoning",
        "Verified and decontaminated OpenMathInstruct-2 direct and chain-of-thought traces.",
        "Duplicate, unverified, and benchmark-contaminated traces are removed.",
    ),
    ExportSpec(
        "dfm10-dolci-tool-use-repaired",
        "data/converted_sources/dolci_tool_use_repaired",
        ("**/*.jsonl",),
        ("allenai/Dolci-Instruct-SFT-Tool-Use", "allenai/Dolci-Instruct-SFT-Tool-Use-SA"),
        ("en",),
        "Tool use",
        "DOLCI tool-use trajectories repaired as native structured chats.",
        "Tool results, call IDs, and call/result grouping are retained and validated.",
    ),
    ExportSpec(
        "dfm10-govreport-summarization-repaired",
        "data/converted_sources/govreport_summarization_grounded",
        ("*.parquet",),
        ("ccdv/govreport-summarization",),
        ("en",),
        "Summarization",
        "GovReport examples whose complete evidence and reference fit the DFM10 context contract.",
        "Character-truncated evidence is removed; only source-grounded pairs are retained.",
    ),
    ExportSpec(
        "dfm10-arxiv-paper-summarization-sft",
        "data/dfm10_arxiv_summarization_export_source",
        ("arxiv-papers-*.parquet",),
        ("common-pile/arxiv_papers_filtered",),
        ("en",),
        "Scientific summarization",
        "Openly licensed arXiv excerpt-to-abstract supervision with row-level provenance.",
        "The exact inherited DFM task rows are enriched with arXiv URL, authors, date, per-paper license, Common Pile shard and row, and pinned Hub revision.",
        "Preserve each row's arXiv URL, authors, and license metadata and apply its CC BY, CC BY-SA, CC0, or public-domain terms.",
        license="other",
        license_notice=(
            "This mixed-license package contains only source records identified by Common "
            "Pile as CC BY 3.0/4.0, CC BY-SA 4.0, CC0, or public domain. Each row "
            "retains its exact upstream license, URL, and author attribution; preserve and "
            "apply those row-level terms."
        ),
    ),
    ExportSpec(
        "dfm10-wiki-cat-sum-repaired",
        "data/converted_sources/wiki_cat_sum_repaired_with_recovery",
        ("train.parquet",),
        ("GEM/wiki_cat_sum",),
        ("en",),
        "Summarization",
        "Grounded WikiCatSum examples plus independently audited source-grounded recoveries.",
        "Noisy evidence is cleaned and unsupported targets fail closed.",
    ),
    ExportSpec(
        "dfm10-danmarks-statistik-bt-repaired",
        "data/converted_sources/danmarks_statistik_bt_repaired_with_article_recovery",
        ("train.parquet",),
        ("oliverkinch/danmarks-statistik-bt",),
        ("da",),
        "Danish grounded QA",
        "Repaired and source-grounded Danmarks Statistik instruction examples.",
        "Weak topic prompts are replaced by article-grounded requests and audited responses.",
    ),
    ExportSpec(
        "dfm10-nordjylland-news-repaired",
        "data/converted_sources/nordjylland_news_repaired_grounded",
        ("train.parquet",),
        ("alexandrainst/nordjylland-news-summarization",),
        ("da",),
        "Danish summarization",
        "Grounded NordjyllandNews summarization supervision.",
        "Unsupported and incomplete targets are removed by full-corpus judging.",
    ),
    ExportSpec(
        "dfm10-dst-table-prompts-repaired",
        "data/converted_sources/dst_table_prompts_repaired_grounded",
        ("train.parquet",),
        ("oliverkinch/dst-table-prompts-bt",),
        ("da",),
        "Danish data-to-text",
        "Grounded Danish statistics table-to-text prompts and responses.",
        "Weak generated targets are regenerated from tables and pass the production grounding gate.",
    ),
    ExportSpec(
        "dfm10-nemotron-swe-repaired",
        "data/converted_sources/nemotron_swe_repaired",
        ("**/*.jsonl",),
        ("nvidia/Nemotron-SFT-SWE-v2",),
        ("en",),
        "Software engineering",
        "Nemotron SWE trajectories repaired to preserve complete context and tool contracts.",
        "Cumulative targets and duplicated history are removed while native tool structure is retained.",
    ),
    ExportSpec(
        "dfm10-dynaword-instruct-repaired",
        "data/converted_sources/dynaword_instruct_repaired",
        ("*.jsonl",),
        (
            "oliverkinch/da-instruct-dynaword",
            "oliverkinch/da-instruct-dynaword-hq",
            "oliverkinch/da-instruct-dynaword-contemporary",
            "oliverkinch/da-instruct-dynaword-contemporary-hq",
        ),
        ("da",),
        "Danish instruction",
        "Prompt-repaired and audited DynaWord instruction variants.",
        "Targets are retained while mismatched prompts are regenerated and re-audited.",
    ),
    ExportSpec(
        "dfm10-code-meta-reasoning-repaired",
        "data/converted_sources/code_meta_reasoning_repaired",
        ("*.parquet",),
        ("allenai/code-meta-reasoning-filtered",),
        ("en",),
        "Code reasoning",
        "Structured code meta-reasoning tasks with explicit prompts and response contracts.",
        "Empty prompts, unsafe families, and recursive or malformed tasks are removed.",
    ),
    ExportSpec(
        "dfm10-opus-da-en-repaired",
        "data/converted_sources/opus_da_en_repaired",
        ("*.parquet",),
        ("schneiderkamplab/opus-da-en-permissive",),
        ("da", "en"),
        "Translation",
        "Language- and alignment-filtered Danish-English OPUS translation tasks.",
        "Accepted pairs are emitted in both translation directions with clean task prompts.",
    ),
    ExportSpec(
        "dfm10-danish-university-portals-bt-repaired",
        "data/converted_sources/danish_university_portals_bt_repaired",
        ("train.parquet",),
        ("oliverkinch/danish-university-portals-bt",),
        ("da",),
        "Danish instruction",
        "Source-grounded repairs of Danish university portal instruction examples.",
        "Incomplete fragments and extraction artifacts are removed or recovered from source material.",
    ),
    ExportSpec(
        "dfm10-scientific-summaries-repaired",
        "data/converted_sources/scientific_summaries_repaired",
        ("*.parquet",),
        ("laion/Scientific-Summaries",),
        ("en",),
        "Scientific summarization",
        "Complete structured-note scientific summarization examples.",
        "Targets and support fields are never character-truncated; malformed rows fail closed.",
    ),
    ExportSpec(
        "dfm10-machine-translation-da-uk-repaired",
        "data/converted_sources/machine_translation_da_uk_repaired",
        ("*.parquet",),
        ("oliverkinch/machine-translation-da-uk",),
        ("da", "uk"),
        "Translation",
        "Language- and semantic-alignment-filtered Danish-Ukrainian translation tasks.",
        "Accepted pairs pass direction checks and LaBSE filtering and are emitted bidirectionally.",
    ),
    ExportSpec(
        "dfm10-sapient-qrecc-ii-repaired",
        "data/converted_sources/sapient_qrecc_ii_repaired",
        ("*.parquet",),
        ("Sapient FLAN QReCC-II variants",),
        ("en",),
        "Conversational QA",
        "Structurally repaired QReCC-II final-answer and next-question tasks.",
        "Open dialogue turns are completed from the supplied target; leaked or contradictory rows fail closed.",
    ),
    ExportSpec(
        "dfm10-sapient-scibench-repaired",
        "data/converted_sources/sapient_scibench_repaired",
        ("train.parquet",),
        ("Sapient Platypus SciBench variant",),
        ("en",),
        "Science reasoning",
        "SciBench supervision with response contracts derived from target form.",
        "Concise targets use direct mode and substantive derivations use chain-of-thought mode.",
    ),
    ExportSpec(
        "dfm10-openstax-mimir-sft",
        "data/dfm10_openstax_sft_sources/openstax_mimir_sft/data",
        ("part-*.jsonl",),
        ("OpenStax official immutable CC BY 4.0 source books",),
        ("en",),
        "Grounded educational SFT",
        "Fifty thousand independently audited educational SFT rows grounded in 61 official OpenStax books.",
        "Gemma 4 31B generated five task families from pinned passages; every retained row scored at least 4/5 on every audit dimension.",
        "Preserve each row's OpenStax title, source URL, immutable revision, and attribution fields.",
        license="cc-by-4.0",
        license_notice=(
            "The source books and this packaged derivative are distributed under "
            "Creative Commons Attribution 4.0. Preserve row-level OpenStax attribution."
        ),
    ),
    ExportSpec(
        "dfm10-mimir-grounded-expanded-sft",
        "data/mimir_grounded_500k_sft/accepted",
        ("mimir_grounded_expanded_sft.jsonl",),
        ("Common Pile source collections with row-level provenance",),
        ("en",),
        "Grounded capability SFT",
        "More than 700,000 independently audited grounded SFT rows spanning Technical/STEM, professional domains, compositional reasoning, factual QA, and MCQ answer contracts.",
        "Gemma 4 31B generated source-grounded rows; deterministic checks, independent five-dimension audits, global prompt deduplication, 4,096-token validation, and normalized-exact benchmark decontamination were applied before packaging.",
        "Review and preserve every row's upstream dataset, source URL, date, document ID, and license metadata before publication.",
        license="other",
        license_notice=(
            "This is a mixed-source package. Each row retains its upstream license "
            "and provenance metadata; this package does not replace or broaden those "
            "terms. Preserve attribution and apply the row-level source license."
        ),
    ),
    ExportSpec(
        "dfm10-mimir-answer-contract-calibration",
        "data/mimir_answer_contract_calibration/final",
        ("mimir_answer_contract_calibration.jsonl",),
        ("Novel deterministic transformations of audited grounded Mimir rows",),
        ("en",),
        "Answer-contract calibration",
        "One hundred fifty thousand exact answer-contract examples covering labels, short answers, reason-then-final responses, and structured payloads.",
        "Every row passes deterministic contract validation; a family-stratified Gemma 4 E4B audit must cover 1,600 unique rows with zero judge errors and at least 99% usable before finalization.",
        "Preserve row-level provenance and upstream source-license metadata inherited from the grounded Mimir source rows.",
        license="other",
        license_notice=(
            "This is a mixed-source transformed package. Preserve each row's upstream "
            "license and provenance metadata; this package does not broaden those terms."
        ),
    ),
    ExportSpec(
        "dfm10-mimir-ifeval-verifier-sft",
        "data/mimir_benchmark_campaigns/accepted",
        ("ifeval_verifier.jsonl",),
        ("Novel verifier-backed synthetic instruction tasks",),
        ("da", "en"),
        "Instruction following",
        "Verifier-backed instruction-following examples grounded in licensed source passages.",
        "Gemma 4 31B generated candidates; deterministic constraint verification, independent five-dimension audit, exact decontamination, deduplication, and a 4,096-token cap were applied.",
        "Preserve row-level source provenance and upstream license metadata.",
    ),
    ExportSpec(
        "dfm10-mimir-event-coreference-sft",
        "data/mimir_benchmark_campaigns/accepted",
        ("event_coreference.jsonl",),
        ("Novel event-coreference and temporal-state synthetic tasks",),
        ("da", "en"),
        "Commonsense reasoning",
        "Controlled event-coreference and temporal-state supervision grounded in licensed passages.",
        "Gemma 4 31B generated candidates; deterministic position and swap verification, independent five-dimension audit, exact decontamination, deduplication, and a 4,096-token cap were applied.",
        "Preserve row-level source provenance and upstream license metadata.",
    ),
    ExportSpec(
        "dfm10-mimir-drop-reasoning-sft",
        "data/mimir_benchmark_campaigns/accepted",
        ("drop_reasoning.jsonl",),
        ("Novel openly grounded passages and generated questions",),
        ("en",),
        "Discrete reading comprehension",
        "Grounded discrete reading-comprehension examples with executable arithmetic supervision.",
        "Gemma 4 31B generated candidates; operand grounding and arithmetic execution checks, independent five-dimension audit, exact decontamination, deduplication, and a 4,096-token cap were applied.",
        "Preserve row-level source provenance and upstream license metadata.",
    ),
    ExportSpec(
        "dfm10-mimir-boolq-entailment-sft",
        "data/mimir_benchmark_campaigns/accepted",
        ("boolq_entailment.jsonl",),
        ("Novel openly grounded passages and generated propositions",),
        ("da", "en"),
        "Boolean entailment",
        "Balanced passage-grounded yes/no entailment and contradiction supervision.",
        "Gemma 4 31B generated candidates; evidence-span and label checks, independent five-dimension audit, exact decontamination, deduplication, and a 4,096-token cap were applied.",
        "Preserve row-level source provenance and upstream license metadata.",
    ),
    ExportSpec(
        "dfm10-danish-lexical-sentiment-sft",
        "data/dfm10_danish_lexical_sources",
        ("dsldk_danish_sentiment_lexicon*.jsonl",),
        ("dsldk/danish-sentiment-lexicon",),
        ("da",),
        "Danish lexical sentiment",
        "Gold lexical-polarity supervision derived from the Danish Sentiment Lexicon.",
        "Gold batched mappings are supplemented by separately generated and audited natural Danish questions, without inventing sentence context.",
        "Attribute DSL and CST and preserve ShareAlike terms.",
        license="cc-by-sa-4.0",
        license_notice=(
            "The source and this transformed package are distributed under CC BY-SA 4.0. "
            "Attribute DSL and CST and preserve the ShareAlike notice."
        ),
    ),
    ExportSpec(
        "dfm10-danish-framenet-sft",
        "data/dfm10_danish_lexical_sources",
        ("dsldk_danish_framenet*.jsonl",),
        ("dsldk/dansk-frame-net",),
        ("da",),
        "Danish lexical semantics",
        "Gold semantic-frame supervision derived from Danish FrameNet 1.0.",
        "Gold batched mappings are supplemented by separately generated and audited natural Danish questions; NULL labels and duplicate records are removed.",
        "Preserve the Danish FrameNet copyright and license notice on every copy.",
        license="other",
        license_notice=(
            "Danish FrameNet 1.0 permits use, copying, modification, and distribution "
            "provided its copyright, license, and disclaimer are preserved."
        ),
    ),
    ExportSpec(
        "dfm10-tidsskrift-open-sft",
        "data/dfm10_tidsskrift_open_sft_source",
        ("tidsskrift_open_sft.jsonl",),
        ("tidsskrift.dk OAI-PMH article metadata and PDFs",),
        ("da", "en"),
        "Grounded Danish and English article SFT",
        "Strict-open Tidsskrift.dk chunks used for grounded questions, explanations, and natural summaries, plus nine gold author-abstract rows.",
        "Gemma 4 31B creates varied chunk-grounded tasks which pass a separate row-level audit; gold abstracts retain target-leakage checks.",
        "Preserve every row's article URL, authors, journal, and exact license URL.",
        license="cc-by-sa-4.0",
        license_notice=(
            "Rows retain their exact CC BY or CC BY-SA license URL. The combined "
            "package is conservatively marked CC BY-SA 4.0; preserve article-level attribution."
        ),
    ),
    ExportSpec(
        "dfm10-tidsskrift-open-chats",
        "data/dfm10_tidsskrift_open_chats_source",
        ("tidsskrift_open_chats.jsonl",),
        ("tidsskrift.dk OAI-PMH article metadata and PDFs",),
        ("da", "en"),
        "Grounded multi-turn student chats",
        "Audited 2-10 exchange student/assistant conversations grounded in strict-open Tidsskrift.dk chunks.",
        "Gemma 4 31B creates progressive inquiry conversations; every assistant turn and the complete chat are independently audited and remain below 4,096 tokens.",
        "Preserve every row's article URL, authors, journal, and exact license URL.",
        license="cc-by-sa-4.0",
        license_notice=(
            "Rows retain their exact CC BY or CC BY-SA license URL. The combined "
            "package is conservatively marked CC BY-SA 4.0; preserve article-level attribution."
        ),
    ),
    ExportSpec(
        "dfm10-danish-wikipedia-open-chats",
        "data/dfm10_danish_wikipedia_open_chats_source",
        ("danish_wikipedia_open_chats.jsonl",),
        ("danish-foundation-models/danish-dynaword/wikipedia", "Danish Wikipedia",),
        ("da",),
        "Grounded Danish multi-turn student chats",
        "Audited student inquiry conversations grounded in a broad deterministic sample of Danish Wikipedia articles.",
        "One coherent overview-capable chunk per selected article is used; every assistant turn and complete conversation pass a Gemma 4 31B grounding audit.",
        "Preserve article title, URL, DynaWord row identity, Wikimedia attribution, and ShareAlike terms.",
        license="cc-by-sa-4.0",
        license_notice=(
            "This derivative conservatively retains Wikimedia CC BY-SA 4.0 terms. "
            "Preserve article-level title, URL, and Danish Wikipedia contributor attribution."
        ),
    ),
    ExportSpec(
        "dfm10-openstax-open-chats",
        "data/dfm10_openstax_open_chats_source",
        ("openstax_open_chats.jsonl",),
        ("OpenStax official immutable CC BY 4.0 source books",),
        ("en",),
        "Grounded English textbook student chats",
        "Audited student inquiry conversations grounded in 61 immutable historical OpenStax CC BY 4.0 books.",
        "Eight substantive pedagogical lenses are generated per verified passage; every assistant turn and complete conversation pass a Gemma 4 31B grounding audit.",
        "Preserve book title, immutable revision, source URL, artifact hash, and OpenStax attribution.",
        license="cc-by-4.0",
        license_notice=(
            "The source books and this packaged derivative are distributed under "
            "Creative Commons Attribution 4.0. Preserve row-level OpenStax attribution."
        ),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dataset", action="append", help="Build only this package; repeatable.")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--rows-per-shard", type=int, default=ROWS_PER_SHARD)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--refresh-metadata",
        action="store_true",
        help="Refresh cards and license metadata without rewriting packaged data.",
    )
    parser.add_argument(
        "--refresh-inventory",
        action="store_true",
        help="Rebuild only the root inventory from existing package manifests.",
    )
    parser.add_argument("--list", action="store_true", help="List package names and exit.")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_files(spec: ExportSpec) -> list[Path]:
    root = ROOT / spec.source_root
    paths: list[Path] = []
    for pattern in spec.patterns:
        paths.extend(root.glob(pattern))
    files = sorted({path for path in paths if path.is_file()})
    if not files:
        raise FileNotFoundError(f"{spec.name}: no files under {root} matching {spec.patterns}")
    return files


def iter_file_rows(path: Path) -> Iterator[dict[str, Any]]:
    if path.suffix == ".parquet":
        parquet = pq.ParquetFile(path)
        for batch in parquet.iter_batches(batch_size=4096):
            yield from batch.to_pylist()
        return
    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: expected an object")
            yield row


def normalized_row(
    row: dict[str, Any], spec: ExportSpec, relative_file: str, row_number: int
) -> dict[str, Any]:
    data = dict(row)
    messages = data.pop("messages", None)
    if messages is None:
        instruction = data.pop("instruction", data.pop("prompt", None))
        response = data.pop("response", data.pop("target", None))
        if not isinstance(instruction, str) or not instruction.strip():
            raise SkippableRow(
                "empty_instruction",
                f"{spec.name}/{relative_file}:{row_number}: empty instruction",
            )
        if not isinstance(response, str) or not response.strip():
            raise SkippableRow(
                "empty_response",
                f"{spec.name}/{relative_file}:{row_number}: empty response",
            )
        messages = [
            {"role": "user", "content": instruction},
            {"role": "assistant", "content": response},
        ]
    if not isinstance(messages, list) or not messages:
        raise ValueError(f"{spec.name}/{relative_file}:{row_number}: invalid messages")
    for message in messages:
        if not isinstance(message, dict) or not isinstance(message.get("role"), str):
            raise ValueError(f"{spec.name}/{relative_file}:{row_number}: malformed message")
        if "content" not in message and "tool_calls" not in message:
            raise ValueError(f"{spec.name}/{relative_file}:{row_number}: contentless message")

    output: dict[str, Any] = {"messages": messages}
    for key in ("condition", "tools", "target_message_index"):
        value = data.pop(key, None)
        if value not in (None, "", []):
            output[key] = value
    output["source"] = {
        "export_dataset": spec.name,
        "upstream": list(spec.upstream),
        "source_file": relative_file,
        "source_row": row_number,
    }
    if data:
        output["metadata"] = data
    return output


class ShardWriter:
    def __init__(self, data_dir: Path, rows_per_shard: int) -> None:
        self.data_dir = data_dir
        self.rows_per_shard = rows_per_shard
        self.shard_index = -1
        self.rows_in_shard = 0
        self.total_rows = 0
        self.raw: io.BufferedWriter | None = None
        self.gzip_file: gzip.GzipFile | None = None
        self.text: io.TextIOWrapper | None = None
        self.paths: list[Path] = []

    def _open(self) -> None:
        self.shard_index += 1
        path = self.data_dir / f"train-{self.shard_index:05d}.jsonl.gz"
        self.raw = path.open("wb")
        self.gzip_file = gzip.GzipFile(
            filename="", mode="wb", fileobj=self.raw, compresslevel=6, mtime=0
        )
        self.text = io.TextIOWrapper(self.gzip_file, encoding="utf-8", newline="\n")
        self.paths.append(path)
        self.rows_in_shard = 0

    def write(self, row: dict[str, Any]) -> None:
        if self.text is None or self.rows_in_shard >= self.rows_per_shard:
            self.close_current()
            self._open()
        assert self.text is not None
        self.text.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        self.text.write("\n")
        self.rows_in_shard += 1
        self.total_rows += 1

    def close_current(self) -> None:
        if self.text is not None:
            self.text.flush()
            self.text.close()
        self.text = None
        self.gzip_file = None
        self.raw = None

    def close(self) -> None:
        self.close_current()


VALIDATOR = '''#!/usr/bin/env python3
"""Validate the packaged chat dataset."""

import gzip
import hashlib
import json
from pathlib import Path


def main():
    rows = 0
    manifest = json.loads((Path(__file__).parent / "metadata" / "manifest.json").read_text())
    expected_hash = manifest.get("content_sha256")
    digest = hashlib.sha256() if expected_hash else None
    for path in sorted((Path(__file__).parent / "data").glob("train-*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                row = json.loads(line)
                messages = row.get("messages")
                if not isinstance(messages, list) or not messages:
                    raise ValueError(f"{path}:{line_number}: invalid messages")
                for message in messages:
                    if not isinstance(message, dict) or not isinstance(message.get("role"), str):
                        raise ValueError(f"{path}:{line_number}: malformed message")
                    if "content" not in message and "tool_calls" not in message:
                        raise ValueError(f"{path}:{line_number}: contentless message")
                if digest is not None:
                    if len(messages) != 2 or messages[0].get("role") != "user" or messages[1].get("role") != "assistant":
                        raise ValueError(f"{path}:{line_number}: content-hash rows must be user/assistant pairs")
                    payload = [row.get("condition"), messages[0].get("content"), messages[1].get("content")]
                    digest.update(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
                    digest.update(b"\\n")
                rows += 1
    expected = manifest["rows"]
    if rows != expected:
        raise ValueError(f"row count mismatch: {rows} != {expected}")
    result = {"rows": rows, "valid": True}
    if digest is not None:
        actual_hash = digest.hexdigest()
        if actual_hash != expected_hash:
            raise ValueError(f"content hash mismatch: {actual_hash} != {expected_hash}")
        result["content_sha256"] = actual_hash
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
'''


def validate_package(package_root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    rows = 0
    expected_hash = manifest.get("content_sha256")
    digest = hashlib.sha256() if expected_hash else None
    for path in sorted((package_root / "data").glob("train-*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                row = json.loads(line)
                messages = row.get("messages")
                if not isinstance(messages, list) or not messages:
                    raise ValueError(f"{path}:{line_number}: invalid messages")
                for message in messages:
                    if not isinstance(message, dict) or not isinstance(message.get("role"), str):
                        raise ValueError(f"{path}:{line_number}: malformed message")
                    if "content" not in message and "tool_calls" not in message:
                        raise ValueError(f"{path}:{line_number}: contentless message")
                if digest is not None:
                    if (
                        len(messages) != 2
                        or messages[0].get("role") != "user"
                        or messages[1].get("role") != "assistant"
                    ):
                        raise ValueError(
                            f"{path}:{line_number}: content-hash rows must be user/assistant pairs"
                        )
                    payload = [
                        row.get("condition"),
                        messages[0].get("content"),
                        messages[1].get("content"),
                    ]
                    digest.update(
                        json.dumps(
                            payload, ensure_ascii=False, separators=(",", ":")
                        ).encode("utf-8")
                    )
                    digest.update(b"\n")
                rows += 1
    if rows != manifest["rows"]:
        raise ValueError(f"row count mismatch: {rows} != {manifest['rows']}")
    result: dict[str, Any] = {"rows": rows, "valid": True}
    if digest is not None:
        actual_hash = digest.hexdigest()
        if actual_hash != expected_hash:
            raise ValueError(f"content hash mismatch: {actual_hash} != {expected_hash}")
        result["content_sha256"] = actual_hash
    return result


def readme(spec: ExportSpec, rows: int, shards: int) -> str:
    languages = "\n".join(f"- {language}" for language in spec.languages)
    upstream = "\n".join(f"- `{source}`" for source in spec.upstream)
    return f'''---
license: {spec.license}
language:
{languages}
tags:
- instruction-tuning
- chat
- dfm10
- repaired
pretty_name: {spec.name}
---

# {spec.name}

{spec.description}

## Contents

- Format: gzip-compressed JSON Lines under `data/train-*.jsonl.gz`
- Schema: chat `messages`, optional `condition` and `tools`, plus provenance
- Shards: {shards:,}
- Rows: {rows:,}
- Category: {spec.category}

## Upstream material

{upstream}

## Processing

{spec.transformation}

Selection policy: `{spec.selection_policy or "all rows in the packaged source artifact"}`.

Every packaged row is taken from the accepted source tree identified in the
package manifest. Tokenized arrays and epoch sampling indices are not included;
export staging alone does not imply inclusion in a sampled training union.

## License and release review

{spec.license_notice} {spec.upload_review}

## Validate

```bash
python recreate_dataset.py
```
'''


def build_one(spec: ExportSpec, output_root: Path, rows_per_shard: int, force: bool) -> dict[str, Any]:
    destination = output_root / spec.name
    if destination.exists() and not force:
        manifest_path = destination / "metadata" / "manifest.json"
        if manifest_path.is_file():
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        raise FileExistsError(f"{destination} exists without a manifest; use --force")

    output_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{spec.name}.", dir=output_root))
    try:
        data_dir = temporary / "data"
        metadata_dir = temporary / "metadata"
        data_dir.mkdir()
        metadata_dir.mkdir()
        files = source_files(spec)
        logical_source_root = ROOT / spec.source_root
        writer = ShardWriter(data_dir, rows_per_shard)
        input_rows = 0
        skipped_rows: Counter[str] = Counter()
        for path in files:
            relative = path.relative_to(logical_source_root).as_posix()
            for row_number, row in enumerate(iter_file_rows(path), 1):
                input_rows += 1
                try:
                    normalized = normalized_row(row, spec, relative, row_number)
                except SkippableRow as exc:
                    skipped_rows[exc.reason] += 1
                    continue
                writer.write(normalized)
        writer.close()
        if writer.total_rows + sum(skipped_rows.values()) != input_rows or writer.total_rows == 0:
            raise ValueError(
                f"{spec.name}: invalid output count "
                f"{writer.total_rows}+{sum(skipped_rows.values())}/{input_rows}"
            )

        data_files = []
        for path in writer.paths:
            data_files.append(
                {
                    "file": path.relative_to(temporary).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
        manifest = {
            "name": spec.name,
            "format": "gzip JSON Lines with chat messages",
            "rows": writer.total_rows,
            "source_rows": input_rows,
            "skipped_rows": sum(skipped_rows.values()),
            "skip_reasons": dict(sorted(skipped_rows.items())),
            "shards": len(data_files),
            "data_files": data_files,
            "source_root": spec.source_root,
            "source_files": len(files),
            "source_file_paths": [
                path.relative_to(logical_source_root).as_posix() for path in files
            ],
            "source_bytes": sum(path.stat().st_size for path in files),
            "upstream": list(spec.upstream),
            "languages": list(spec.languages),
            "category": spec.category,
            "transformation": spec.transformation,
            "selection_policy": spec.selection_policy,
            "license": spec.license,
            "upload_review": spec.upload_review,
        }
        source_manifest_path = logical_source_root / "manifest.json"
        if source_manifest_path.is_file():
            source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
            if source_manifest.get("content_sha256"):
                manifest["content_sha256"] = source_manifest["content_sha256"]
        (metadata_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (temporary / "README.md").write_text(
            readme(spec, writer.total_rows, len(data_files)), encoding="utf-8"
        )
        (temporary / "LICENSE.md").write_text(
            "# License notice\n\n" + spec.license_notice + "\n", encoding="utf-8"
        )
        validator = temporary / "recreate_dataset.py"
        validator.write_text(VALIDATOR, encoding="utf-8")
        validator.chmod(0o755)
        validation = validate_package(temporary, manifest)
        (metadata_dir / "validation.json").write_text(
            json.dumps(validation, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if destination.exists():
            shutil.rmtree(destination)
        temporary.rename(destination)
        return manifest
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def refresh_metadata(spec: ExportSpec, output_root: Path) -> dict[str, Any]:
    destination = output_root / spec.name
    manifest_path = destination / "metadata" / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"{spec.name}: missing packaged manifest at {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "upstream": list(spec.upstream),
            "languages": list(spec.languages),
            "category": spec.category,
            "transformation": spec.transformation,
            "selection_policy": spec.selection_policy,
            "license": spec.license,
            "upload_review": spec.upload_review,
        }
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (destination / "README.md").write_text(
        readme(spec, int(manifest["rows"]), int(manifest["shards"])), encoding="utf-8"
    )
    (destination / "LICENSE.md").write_text(
        "# License notice\n\n" + spec.license_notice + "\n", encoding="utf-8"
    )
    return manifest


def inherited_dfm8_ids() -> list[str]:
    text = (ROOT / "docs/dfm8-datasets.md").read_text(encoding="utf-8")
    ids: list[str] = []
    pattern = r"\[([^]]+/[^]]+)\]\(https://huggingface\.co/datasets/[^)]+\)"
    for dataset_id in re.findall(pattern, text):
        if dataset_id not in ids:
            ids.append(dataset_id)
    return ids


def inherited_audit() -> dict[str, Any]:
    # The online verification was performed on 2026-08-29. Keep this function
    # deterministic so rebuilding export packages does not require network access.
    ids = inherited_dfm8_ids()
    if len(ids) != 159:
        raise ValueError(f"expected 159 inherited DFM8 Hub IDs, found {len(ids)}")
    return {
        "checked_at": "2026-08-29",
        "method": "Hugging Face dataset API lookup by exact repository ID",
        "dfm8": {"repositories": len(ids), "all_resolved": True, "ids": ids},
        "dfm9_additions": {
            "repositories": len(DFM9_HF_IDS),
            "all_resolved": True,
            "ids": list(DFM9_HF_IDS),
        },
        "not_on_huggingface_by_design": [
            "Lex.dk articles (Danish Foundation Model agreement)",
            "DBC corpus (Danish Foundation Model agreement)",
        ],
    }


def write_root_inventory(output_root: Path, manifests: list[dict[str, Any]]) -> None:
    audit = inherited_audit()
    (output_root / "inherited_hf_audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    verified_receipt = ROOT / "logs/dfm10_ready_upload/verified.jsonl"
    remotely_verified: set[str] = set()
    if verified_receipt.is_file():
        for line in verified_receipt.read_text(encoding="utf-8").splitlines():
            if line.strip():
                receipt = json.loads(line)
                if isinstance(receipt.get("package"), str):
                    remotely_verified.add(receipt["package"])
    inventory_manifests = []
    for manifest in manifests:
        item = dict(manifest)
        item["dfm10_sampling_repeat"] = PACKAGE_REPEATS.get(item["name"], 1)
        item.update(EXPORT_VERSION_METADATA.get(item["name"], {}))
        if item["name"] in WORK_IN_PROGRESS and int(item.get("rows", 0)) == 0:
            item["status"] = "work_in_progress"
            item["status_reason"] = WORK_IN_PROGRESS[item["name"]]
        elif item["name"] in UPLOADED_PACKAGES or item["name"] in remotely_verified:
            item["status"] = "uploaded"
            item["status_reason"] = (
                "Present in the schneiderkamplab Hugging Face dataset namespace "
                "as verified on 2026-08-30."
            )
        else:
            item["status"] = "ready_for_upload"
            item["status_reason"] = (
                "Local package validation passed, but the package is not in the "
                "verified uploaded-package inventory."
            )
        inventory_manifests.append(item)
    present_names = {item["name"] for item in inventory_manifests}
    for name, metadata in PLANNED_PACKAGE_METADATA.items():
        if name in present_names:
            continue
        inventory_manifests.append(
            {
                "name": name,
                **metadata,
                "rows": 0,
                "shards": 0,
                "source_bytes": 0,
                "data_files": [],
                "dfm10_sampling_repeat": PACKAGE_REPEATS.get(name, 1),
                "status": "work_in_progress",
                "status_reason": WORK_IN_PROGRESS[name],
                "materialized": False,
            }
        )
    present_names = {item["name"] for item in inventory_manifests}
    for name, metadata in PLANNED_UPLOAD_METADATA.items():
        if name in present_names:
            continue
        status_reason = str(metadata["status_reason"])
        inventory_manifests.append(
            {
                "name": name,
                **{key: value for key, value in metadata.items() if key != "status_reason"},
                **EXPORT_VERSION_METADATA[name],
                "rows": 0,
                "shards": 0,
                "source_bytes": 0,
                "data_files": [],
                "dfm10_sampling_repeat": PACKAGE_REPEATS.get(name, 1),
                "status": "work_in_progress",
                "status_reason": status_reason,
                "materialized": False,
            }
        )
    registered_names = {item["name"] for item in inventory_manifests}
    uploaded_names = sorted(present_names & UPLOADED_PACKAGES)
    ready_names = sorted(
        item["name"]
        for item in inventory_manifests
        if item["status"] == "ready_for_upload"
    )
    work_in_progress = sorted(
        (
            {"name": item["name"], "reason": item["status_reason"]}
            for item in inventory_manifests
            if item["status"] == "work_in_progress"
        ),
        key=lambda item: item["name"],
    )
    inventory = {
        "packages": sorted(inventory_manifests, key=lambda item: item["name"]),
        "package_count": len(inventory_manifests),
        "materialized_package_count": len(manifests),
        "rows": sum(int(item["rows"]) for item in manifests),
        "source_bytes": sum(int(item["source_bytes"]) for item in manifests),
        "excluded": {
            "dbc_repaired": "Agreement-backed; deliberately not staged for public upload.",
            "lexdk": "Agreement-backed inherited source; deliberately not staged for public upload.",
            "alexandrainst/dacoref": "Disabled by final DFM10 source reconciliation.",
            "alexandrainst/nordjylland-news-summarization original conversion": "Disabled in favor of the repaired package.",
        },
        "upload_performed": False,
        "publication_state_checked_at": "2026-08-30",
        "uploaded_packages": uploaded_names,
        "ready_for_upload": ready_names,
        "work_in_progress": work_in_progress,
    }
    (output_root / "manifest.json").write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# DFM10 Hugging Face export staging",
        "",
        "Each direct child directory is a locally validated dataset package. The",
        "preparation command does not upload packages.",
        "",
        f"Registered packages: {len(inventory_manifests):,}",
        f"Materialized packages: {len(manifests):,}",
        f"Rows: {inventory['rows']:,}",
        "",
        "## Publication status",
        "",
        f"- Uploaded: {len(uploaded_names):,}",
        f"- Ready for upload: {len(ready_names):,}",
        f"- Work in progress: {len(work_in_progress):,}",
        "",
        *[f"- `uploaded`: `{name}`" for name in uploaded_names],
        *[f"- `ready_for_upload`: `{name}`" for name in ready_names],
        "",
        "## DFM10 sampling repeats",
        "",
        "Packages not listed here use the conservative one-pass default.",
        "",
        *[
            f"- `{name}`: {repeat}x"
            for name, repeat in sorted(PACKAGE_REPEATS.items())
            if name in registered_names
        ],
        "",
        "## Work in progress",
        "",
        *[
            f"- `{item['name']}`: {item['reason']}"
            for item in work_in_progress
        ],
        "",
        "Agreement-backed LexDK and DBC data are intentionally absent. See",
        "`manifest.json` and `inherited_hf_audit.json` for the complete decisions.",
        "",
        "Validate one package with:",
        "",
        "```bash",
        "python exports_dfm10/<dataset>/recreate_dataset.py",
        "```",
        "",
    ]
    (output_root / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    by_name = {spec.name: spec for spec in SPECS}
    if args.list:
        for name in by_name:
            print(name)
        return
    selected_names = args.dataset or list(by_name)
    unknown = sorted(set(selected_names) - set(by_name))
    if unknown:
        raise SystemExit(f"unknown dataset(s): {', '.join(unknown)}")
    selected = [by_name[name] for name in selected_names]
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    if args.refresh_inventory:
        manifests = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(output_root.glob("*/metadata/manifest.json"))
        ]
        write_root_inventory(output_root, manifests)
        print(f"Refreshed inventory for {len(manifests):,} packages under {output_root}")
        return

    manifests: list[dict[str, Any]] = []
    if args.refresh_metadata:
        for spec in selected:
            manifest = refresh_metadata(spec, output_root)
            manifests.append(manifest)
            print(f"REFRESHED {spec.name}", flush=True)
        manifests_by_name = {item["name"]: item for item in manifests}
        for manifest_path in output_root.glob("*/metadata/manifest.json"):
            item = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifests_by_name.setdefault(item["name"], item)
        write_root_inventory(output_root, list(manifests_by_name.values()))
        print(f"Refreshed metadata under {output_root}")
        return

    with concurrent.futures.ProcessPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {
            pool.submit(build_one, spec, output_root, args.rows_per_shard, args.force): spec
            for spec in selected
        }
        for future in concurrent.futures.as_completed(futures):
            spec = futures[future]
            manifest = future.result()
            manifests.append(manifest)
            print(
                f"READY {spec.name}: rows={manifest['rows']:,} "
                f"shards={manifest['shards']:,}",
                flush=True,
            )

    # Include previously completed packages when rebuilding only a subset.
    manifests_by_name = {item["name"]: item for item in manifests}
    for manifest_path in output_root.glob("*/metadata/manifest.json"):
        item = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifests_by_name.setdefault(item["name"], item)
    write_root_inventory(output_root, list(manifests_by_name.values()))
    print(f"Prepared {len(manifests_by_name):,} packages under {output_root}")
    print("No Hugging Face upload was performed.")


if __name__ == "__main__":
    main()
