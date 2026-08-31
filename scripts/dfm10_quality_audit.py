#!/usr/bin/env python3
"""Prepare, judge, and atomically merge a source-level DFM10 quality audit.

The audit samples the exact prompt/response spans visible in the tokenized
DFM10 tree. The pending Folketing source is sampled from its audited chat tree
because it cannot enter the tokenized union until its separate acceptance audit
has completed.
"""

from __future__ import annotations

import argparse
import fcntl
import fnmatch
import gzip
import hashlib
import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import yaml
from tokenizers import Tokenizer


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOKENIZED_ROOT = ROOT / "data/tokenized_dfm10"
DEFAULT_PREFIX_CONFIG = ROOT / "data_io/prefix_config_dfm10.yaml"
DEFAULT_INVENTORY_DOC = ROOT / "docs/dfm8-datasets.md"
DEFAULT_FOLKETING_ROOT = ROOT / "data/dfm10_folketing_transform_sources_audited"
DEFAULT_SEED = 20260826
CONTEXT_SIZE = 4097


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    generation: str
    patterns: tuple[str, ...]
    form: str
    raw_root: str | None = None
    sample_count: int | None = None


DFM9_ADDITIONS = (
    SourceSpec("AI-MO/NuminaMath-1.5", "dfm9", ("numinamath_1_5",), "converted"),
    SourceSpec("nvidia/Nemotron-Terminal-Corpus", "dfm9", ("nemotron_terminal_corpus",), "converted"),
    SourceSpec("Muennighoff/natural-instructions", "dfm9", ("posttrain_natural_instructions",), "filtered/converted"),
    SourceSpec("grammarly/coedit", "dfm9", ("posttrain_coedit",), "converted"),
    SourceSpec("facebook/asset", "dfm9", ("posttrain_asset",), "converted"),
    SourceSpec("nvidia/Nemotron-SFT-SWE-v2", "dfm9", ("nemotron_swe_windowed",), "windowed conversion"),
    SourceSpec("croco-munin/apertus-8b-da-simpo-full-50k", "dfm9", ("croco_munin_da_sft",), "chosen-response SFT conversion"),
    SourceSpec("google/multilingual_gsm_symbolic", "dfm9", ("gsm_symbolic_da",), "converted Danish subset"),
)

DFM10_ADDITIONS = (
    SourceSpec(
        "dsldk/danish-sentiment-lexicon",
        "dfm10",
        ("dsldk_danish_sentiment_lexicon.jsonl",),
        "gold lexical polarity batches",
    ),
    SourceSpec(
        "dsldk/dansk-frame-net",
        "dfm10",
        ("dsldk_danish_framenet.jsonl",),
        "gold lexical semantic-frame batches",
    ),
    SourceSpec(
        "tidsskrift.dk/strict-open-sft",
        "dfm10",
        ("tidsskrift_open_sft.jsonl",),
        "audited grounded questions, explanations, natural summaries, and gold author abstracts",
    ),
    SourceSpec(
        "tidsskrift.dk/strict-open-chats",
        "dfm10",
        ("tidsskrift_open_chats.jsonl",),
        "audited 2-10 exchange source-grounded student inquiry chats",
    ),
    SourceSpec(
        "danish-foundation-models/danish-dynaword/wikipedia",
        "dfm10",
        ("danish_wikipedia_open_chats.jsonl",),
        "audited source-grounded Danish student inquiry chats",
    ),
    SourceSpec(
        "OpenStax/official-cc-by-4.0",
        "dfm10",
        ("openstax_open_chats.jsonl",),
        "audited multi-lens English textbook student inquiry chats",
    ),
    SourceSpec(
        "allenai/code_meta_reasoning",
        "dfm10",
        ("code_meta_reasoning_repaired",),
        "structured repaired conversion",
    ),
    SourceSpec("dfm-agreement/hc-andersen-modernization", "dfm10", ("andersen_modernization",), "converted"),
    SourceSpec(
        "alexandrainst/nordjylland-news-summarization",
        "dfm10",
        ("nordjylland_news_repaired",),
        "headline-aware, full-corpus grounded repair",
    ),
    SourceSpec("alexandrainst/scandi-qa", "dfm10", ("alexandra_scandi_qa_da",), "converted Danish train split"),
    SourceSpec("alexandrainst/multi-zebra-logic", "dfm10", ("alexandra_multi_zebra",), "converted Danish/English train splits"),
    SourceSpec("alexandrainst/dane", "dfm10", ("alexandra_dane",), "converted train split"),
    SourceSpec("alexandrainst/dacoref", "dfm10", ("alexandra_dacoref",), "converted train split"),
    SourceSpec("zai-org/DeepDive", "dfm10", ("zai_deepdive_trajectories_sft",), "native-tool conversion"),
    SourceSpec(
        "dfm-agreement/rigsarkivet-folketinget-14004",
        "dfm10",
        ("folketingets-dokumenter",),
        "generated and separately audited",
        str(DEFAULT_FOLKETING_ROOT),
    ),
)


def parse_dfm8_inventory(path: Path) -> list[SourceSpec]:
    specs: list[SourceSpec] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| ["):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 8:
            continue
        match = re.match(r"\[([^]]+)\]", cells[0])
        if match is None:
            continue
        source_id = match.group(1)
        # The Sapient category contains literal pipes inside braces. Rebuild
        # the category from all cells preceding the six fixed trailing cells.
        category = "|".join(cells[1:-6]).strip()
        form = cells[-6]
        patterns = category_patterns(category)
        if source_id == "giannor/dala_tv2r_it":
            patterns = ("giannor_tv2r_instruction__giannor_dala_tv2r_it",)
        elif source_id == "giannor/gec_dala_tv2r_it":
            patterns = ("giannor_tv2r_instruction__giannor_gec_dala_tv2r_it",)
        elif source_id == "allenai/Dolci-Instruct-SFT-Tool-Use":
            patterns = ("dolci_tool_use_repaired__dolci_instruct_sft_tool_use__",)
        elif source_id == "allenai/Dolci-Instruct-SFT-Tool-Use-SA":
            patterns = ("dolci_tool_use_repaired__dolci_instruct_sft_tool_use_sa__",)
        elif source_id == "ccdv/govreport-summarization":
            patterns = ("govreport_summarization_repaired__",)
        elif source_id == "schneiderkamplab/opus-da-en-permissive":
            patterns = ("opus_da_en_repaired",)
        elif source_id == "GEM/wiki_cat_sum":
            patterns = ("wiki_cat_sum_repaired__",)
            form = "evidence-selected, full-corpus grounding-filtered repair"
        elif source_id == "oliverkinch/danmarks-statistik-bt":
            patterns = ("danmarks_statistik_bt_repaired__",)
            form = "answer-matched prompt regeneration and full-corpus coherence filter"
        elif source_id == "sapientinc/HRM-Text-data-io-cleaned-20260515":
            patterns = (*patterns, "flan_factual")
        specs.append(SourceSpec(source_id, "dfm8", patterns, form))

    specs.extend(
        (
            SourceSpec("dfm-agreement/dbc", "dfm8", ("dbc_repaired", "dbc"), "repaired/converted"),
            SourceSpec("dfm-agreement/lexdk", "dfm8", ("lexdk",), "converted"),
        )
    )
    if len(specs) != 161:
        raise ValueError(f"expected 161 DFM8 sources, parsed {len(specs)} from {path}")
    return specs


def category_patterns(category: str) -> tuple[str, ...]:
    category = category.strip().strip("`")
    if category.startswith("{") and category.endswith("}"):
        values = category[1:-1].split("|")
    else:
        values = category.split("/")
    return tuple(value.strip().strip("`") for value in values if value.strip())


def source_specs(inventory_doc: Path) -> list[SourceSpec]:
    specs = parse_dfm8_inventory(inventory_doc) + list(DFM9_ADDITIONS) + list(DFM10_ADDITIONS)
    ids = [spec.source_id for spec in specs]
    if len(ids) != len(set(ids)):
        duplicates = sorted({source_id for source_id in ids if ids.count(source_id) > 1})
        raise ValueError(f"duplicate source IDs: {duplicates}")
    return specs


def configured_source_specs(path: Path, stage_id: str, task_dirs: list[Path]) -> list[SourceSpec]:
    """Load one targeted audit stage without changing the legacy inventory."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    stages = document.get("stages", []) if isinstance(document, dict) else []
    matches = [stage for stage in stages if str(stage.get("id")) == stage_id]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one stage {stage_id!r} in {path}, found {len(matches)}")

    stage = matches[0]
    required_status = stage.get("wait_for_manifest_status")
    manifest_status: dict[str, str] = {}
    if required_status is not None:
        manifest = json.loads((ROOT / "exports_dfm10/manifest.json").read_text(encoding="utf-8"))
        manifest_status = {str(item["name"]): str(item.get("status", "")) for item in manifest["packages"]}

    specs: list[SourceSpec] = []
    for item in stage.get("sources", []):
        source_id = str(item["source_id"])
        patterns = tuple(str(value) for value in item.get("patterns", ()))
        sample_count = int(item.get("samples", 100))
        generation = str(item.get("generation", "dfm10_residual_audit"))
        form = str(item.get("form", "final_training_representation"))
        raw_root = item.get("raw_root")
        if raw_root is not None:
            raw_root = str(raw_root)
            if required_status is not None:
                package_name = Path(raw_root).name
                actual_status = manifest_status.get(package_name, "missing")
                if actual_status != str(required_status):
                    raise ValueError(
                        f"stage {stage_id} package {package_name} requires status {required_status}, "
                        f"found {actual_status}"
                    )

        if bool(item.get("per_task", False)):
            matching_tasks = sorted(
                task for task in task_dirs if any(matches_pattern(task.name, pattern) for pattern in patterns)
            )
            minimum_matches = int(item.get("minimum_matches", 1))
            if len(matching_tasks) < minimum_matches:
                raise ValueError(
                    f"stage {stage_id} source {source_id} expected at least {minimum_matches} tasks, "
                    f"found {len(matching_tasks)}"
                )
            for task in matching_tasks:
                specs.append(
                    SourceSpec(
                        source_id=f"{source_id}/{task.name}",
                        generation=generation,
                        patterns=(task.name,),
                        form=form,
                        sample_count=sample_count,
                    )
                )
            continue

        if raw_root is None:
            minimum_matches = int(item.get("minimum_matches", 1))
            matching_count = sum(
                any(matches_pattern(task.name, pattern) for pattern in patterns) for task in task_dirs
            )
            if matching_count < minimum_matches:
                raise ValueError(
                    f"stage {stage_id} source {source_id} expected at least {minimum_matches} tasks, "
                    f"found {matching_count}"
                )
        specs.append(
            SourceSpec(
                source_id=source_id,
                generation=generation,
                patterns=patterns,
                form=form,
                raw_root=raw_root,
                sample_count=sample_count,
            )
        )

    ids = [spec.source_id for spec in specs]
    if not specs or len(ids) != len(set(ids)):
        raise ValueError(f"empty or duplicate configured source IDs in stage {stage_id}")
    return specs


def matches_pattern(task_name: str, pattern: str) -> bool:
    if any(character in pattern for character in "*?["):
        return fnmatch.fnmatchcase(task_name, pattern)
    if pattern.endswith("__"):
        return task_name.startswith(pattern)
    return task_name == pattern or task_name.startswith(pattern + "__")


def load_sampling_policy(path: Path) -> list[dict[str, Any]]:
    policy = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(policy, list):
        raise ValueError(f"expected a list in {path}")
    return policy


def task_policy(task_name: str, policy: list[dict[str, Any]]) -> dict[str, Any]:
    # Match sample_tokenized.py exactly: the first matching prefix wins.
    for item in policy:
        if task_name.startswith(str(item["prefix"])):
            return item
    # sample_tokenized.py includes unmatched tasks with PrefixConfig defaults.
    return {}


def load_array(task: Path, name: str) -> np.ndarray:
    return np.load(task / f"{name}.npy", mmap_mode="r")


def eligible_indices(task: Path, policy_item: dict[str, Any]) -> np.ndarray:
    inst_len = load_array(task, "inst_len")
    resp_len = load_array(task, "resp_len")
    long_context = str(policy_item.get("long_context", "drop"))
    if long_context == "truncate":
        mask = (resp_len >= 1) & (CONTEXT_SIZE - np.minimum(inst_len, CONTEXT_SIZE) >= 1)
    else:
        mask = (resp_len >= 1) & (inst_len + resp_len <= CONTEXT_SIZE)
    return np.flatnonzero(mask)


def stable_seed(seed: int, source_id: str) -> int:
    digest = hashlib.blake2b(f"{seed}\0{source_id}".encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big")


def choose_global_indices(total: int, count: int, seed: int) -> list[int]:
    if total <= count:
        return list(range(total))
    return sorted(random.Random(seed).sample(range(total), count))


def decode_tokenized_samples(
    source: SourceSpec,
    tasks: list[Path],
    policy: list[dict[str, Any]],
    tokenizer: Tokenizer,
    sample_count: int,
    seed: int,
) -> tuple[list[dict[str, Any]], int]:
    task_rows: list[tuple[Path, np.ndarray]] = []
    total = 0
    for task in tasks:
        policy_item = task_policy(task.name, policy)
        if int(policy_item.get("max_per_file", -1)) == 0:
            continue
        eligible = eligible_indices(task, policy_item)
        if len(eligible):
            task_rows.append((task, eligible))
            total += len(eligible)

    selected = choose_global_indices(total, sample_count, stable_seed(seed, source.source_id))
    samples: list[dict[str, Any]] = []
    task_cursor = 0
    selected_cursor = 0
    for task, eligible in task_rows:
        task_end = task_cursor + len(eligible)
        local: list[int] = []
        while selected_cursor < len(selected) and selected[selected_cursor] < task_end:
            local.append(int(eligible[selected[selected_cursor] - task_cursor]))
            selected_cursor += 1
        if local:
            tokens = load_array(task, "tokens")
            inst_start = load_array(task, "inst_start")
            inst_len = load_array(task, "inst_len")
            resp_start = load_array(task, "resp_start")
            resp_len = load_array(task, "resp_len")
            for row_index in local:
                prompt_ids = tokens[int(inst_start[row_index]) : int(inst_start[row_index] + inst_len[row_index])]
                response_ids = tokens[int(resp_start[row_index]) : int(resp_start[row_index] + resp_len[row_index])]
                samples.append(
                    {
                        "source_id": source.source_id,
                        "generation": source.generation,
                        "form": source.form,
                        "task_name": task.name,
                        "row_index": row_index,
                        "prompt": tokenizer.decode(prompt_ids.tolist(), skip_special_tokens=False),
                        "response": tokenizer.decode(response_ids.tolist(), skip_special_tokens=False),
                    }
                )
        task_cursor = task_end
    return samples, total


def iter_chat_rows(root: Path) -> Iterable[tuple[str, int, dict[str, Any]]]:
    paths = list(root.glob("data/*.jsonl*")) + list(root.glob("*/data/*.jsonl*"))
    for path in sorted(set(paths)):
        opener = gzip.open if path.name.endswith(".gz") else open
        with opener(path, "rt", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle):
                if not line.strip():
                    continue
                yield path.relative_to(root).as_posix(), line_number, json.loads(line)


def reservoir_raw_samples(source: SourceSpec, count: int, seed: int) -> tuple[list[dict[str, Any]], int]:
    if source.raw_root is None:
        return [], 0
    root = Path(source.raw_root)
    if not root.is_dir():
        raise FileNotFoundError(f"audited source tree not ready: {root}")
    rng = random.Random(stable_seed(seed, source.source_id))
    reservoir: list[dict[str, Any]] = []
    seen = 0
    for relative_path, line_number, row in iter_chat_rows(root):
        messages = row.get("messages")
        if not isinstance(messages, list):
            continue
        assistant_positions = [idx for idx, message in enumerate(messages) if message.get("role") == "assistant"]
        if not assistant_positions:
            continue
        target = assistant_positions[-1]
        sample = {
            "source_id": source.source_id,
            "generation": source.generation,
            "form": source.form,
            # Shard-local line numbers repeat. The complete relative filename is
            # therefore part of the stable sample identity for packaged rows.
            "task_name": relative_path,
            "row_index": line_number,
            "prompt": json.dumps(messages[:target], ensure_ascii=False),
            "response": json.dumps(messages[target], ensure_ascii=False),
        }
        seen += 1
        if len(reservoir) < count:
            reservoir.append(sample)
        else:
            replacement = rng.randrange(seen)
            if replacement < count:
                reservoir[replacement] = sample
    return reservoir, seen


def atomic_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def prepare(args: argparse.Namespace) -> None:
    root = args.tokenized_root
    tokenizer_info = json.loads((root / "tokenizer_info.json").read_text())
    tokenizer = Tokenizer.from_file(tokenizer_info["tokenizer_path"])
    policy = load_sampling_policy(args.prefix_config)
    task_dirs = [path for path in root.iterdir() if path.is_dir()]
    if args.source_specs is None:
        specs = source_specs(args.inventory_doc)
    else:
        if not args.stage:
            raise ValueError("--stage is required with --source-specs")
        specs = configured_source_specs(args.source_specs, args.stage, task_dirs)
    assignments: dict[str, list[Path]] = {spec.source_id: [] for spec in specs}

    for task in task_dirs:
        matches = [
            spec for spec in specs if spec.raw_root is None and any(matches_pattern(task.name, pattern) for pattern in spec.patterns)
        ]
        if len(matches) > 1:
            raise ValueError(f"ambiguous source assignment for {task.name}: {[item.source_id for item in matches]}")
        if matches:
            assignments[matches[0].source_id].append(task)

    inventory: list[dict[str, Any]] = []
    all_samples: list[dict[str, Any]] = []
    for source in specs:
        if source.raw_root is not None:
            try:
                samples, available = reservoir_raw_samples(
                    source, source.sample_count or args.samples_per_source, args.seed
                )
            except FileNotFoundError:
                if not args.allow_pending_raw:
                    raise
                inventory.append(
                    {
                        **asdict(source),
                        "matched_tasks": 0,
                        "available_rows": 0,
                        "sampled_rows": 0,
                        "pending": True,
                    }
                )
                continue
        else:
            samples, available = decode_tokenized_samples(
                source,
                assignments[source.source_id],
                policy,
                tokenizer,
                source.sample_count or args.samples_per_source,
                args.seed,
            )
        if available == 0:
            raise ValueError(f"source has no eligible DFM10 rows: {source.source_id} patterns={source.patterns}")
        for ordinal, sample in enumerate(samples):
            sample["sample_ordinal"] = ordinal
            sample["sample_id"] = hashlib.blake2b(
                f"{source.source_id}\0{sample['task_name']}\0{sample['row_index']}".encode(), digest_size=16
            ).hexdigest()
            sample["source_available_rows"] = available
        all_samples.extend(samples)
        inventory.append(
            {
                **asdict(source),
                "matched_tasks": len(assignments[source.source_id]),
                "available_rows": available,
                "sampled_rows": len(samples),
            }
        )

    sample_ids = [row["sample_id"] for row in all_samples]
    if len(sample_ids) != len(set(sample_ids)):
        raise ValueError("sample IDs are not unique")
    atomic_jsonl(args.samples_output, all_samples)
    args.inventory_output.parent.mkdir(parents=True, exist_ok=True)
    args.inventory_output.write_text(
        json.dumps(
            {
                "sources": inventory,
                "source_count": len(inventory),
                "sample_count": len(all_samples),
                "samples_per_source": args.samples_per_source,
                "seed": args.seed,
                "tokenized_root": str(root),
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"sources": len(inventory), "samples": len(all_samples)}, indent=2))


JUDGE_SYSTEM = """You are a strict but domain-aware quality auditor for language-model training data.
Return one compact JSON object and no prose. Evaluate the supplied prompt and assistant target as training supervision.
Do not reject an example merely because it is short, specialized, synthetic, multilingual, a classification task,
a translation task, a tool call, or a text-reconstruction task. Judge it according to its intended task.

Use integer scores from 1 (unusable) to 5 (excellent):
- language_quality: grammaticality, fluency, legibility, and absence of corruption in the language(s) the task requires.
- instruction_answer_coherence: whether the target follows and answers the prompt, preserves required structure,
  and is internally consistent. For tool use, assess tool schema/call/result coherence.
- training_value: whether the example teaches meaningful knowledge, reasoning, language, instruction following,
  transformation, coding, mathematics, dialogue, or tool behavior rather than noise or arbitrary mappings.

Required schema:
{"primary_language":"short language label", "language_quality":{"score":1,"issues":["..."]},
 "instruction_answer_coherence":{"score":1,"issues":["..."]},
 "training_value":{"score":1,"contributions":["..."],"issues":["..."]},
 "usable_for_training":true, "primary_problem":"none or short category", "assessment":"one concise sentence"}
Set usable_for_training=false when any central dimension is 1, or when the row would actively teach incorrect/incoherent behavior.
"""

JUDGE_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "training_data_quality_audit",
        "schema": {
            "type": "object",
            "properties": {
                "primary_language": {"type": "string"},
                "language_quality": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "integer", "minimum": 1, "maximum": 5},
                        "issues": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["score", "issues"],
                    "additionalProperties": False,
                },
                "instruction_answer_coherence": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "integer", "minimum": 1, "maximum": 5},
                        "issues": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["score", "issues"],
                    "additionalProperties": False,
                },
                "training_value": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "integer", "minimum": 1, "maximum": 5},
                        "contributions": {"type": "array", "items": {"type": "string"}},
                        "issues": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["score", "contributions", "issues"],
                    "additionalProperties": False,
                },
                "usable_for_training": {"type": "boolean"},
                "primary_problem": {
                    "type": "string",
                    "enum": [
                        "none",
                        "wrong_language",
                        "incoherent",
                        "incorrect",
                        "low_quality",
                        "low_value",
                        "format_error",
                        "other",
                    ],
                },
                "assessment": {"type": "string"},
            },
            "required": [
                "primary_language",
                "language_quality",
                "instruction_answer_coherence",
                "training_value",
                "usable_for_training",
                "primary_problem",
                "assessment",
            ],
            "additionalProperties": False,
        },
    },
}

COMPACT_JUDGE_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "compact_training_data_quality_audit",
        "schema": {
            "type": "object",
            "properties": {
                "primary_language": {"type": "string"},
                "language_quality": {"type": "integer", "minimum": 1, "maximum": 5},
                "instruction_answer_coherence": {"type": "integer", "minimum": 1, "maximum": 5},
                "training_value": {"type": "integer", "minimum": 1, "maximum": 5},
                "usable_for_training": {"type": "boolean"},
                "primary_problem": {"type": "string"},
            },
            "required": [
                "primary_language",
                "language_quality",
                "instruction_answer_coherence",
                "training_value",
                "usable_for_training",
                "primary_problem",
            ],
            "additionalProperties": False,
        },
    },
}


def extract_json(content: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", content, re.S)
    if match is None:
        raise json.JSONDecodeError("judge returned no JSON object", content, 0)
    result = json.loads(match.group(0))
    for dimension in ("language_quality", "instruction_answer_coherence", "training_value"):
        score = result.get(dimension, {}).get("score")
        if not isinstance(score, int) or not 1 <= score <= 5:
            raise ValueError(f"invalid {dimension} score: {score!r}")
    if not isinstance(result.get("usable_for_training"), bool):
        raise ValueError("usable_for_training must be boolean")
    return result


def call_judge(args: argparse.Namespace, sample: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "source_id": sample["source_id"],
        "form": sample["form"],
        "task_name": sample["task_name"],
        "prompt": sample["prompt"],
        "assistant_target": sample["response"],
    }
    body = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "temperature": 0,
        "top_p": 1,
        "max_tokens": args.max_tokens,
        "response_format": JUDGE_RESPONSE_FORMAT,
    }
    last_error = ""
    for attempt in range(args.retries + 1):
        try:
            request = urllib.request.Request(
                args.base_url.rstrip("/") + "/chat/completions",
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json", "Authorization": "Bearer local"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=args.timeout) as response:
                response_payload = json.loads(response.read().decode())
            judgment = extract_json(response_payload["choices"][0]["message"]["content"])
            return {**sample, "judge_model": args.model, "judgment": judgment}
        except (OSError, TimeoutError, urllib.error.URLError, KeyError, ValueError, json.JSONDecodeError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < args.retries:
                time.sleep(args.retry_sleep * (attempt + 1))
    return {**sample, "judge_model": args.model, "judge_error": last_error}


def call_compact_judge(args: argparse.Namespace, sample: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "form": sample["form"],
        "task_name": sample["task_name"],
        "prompt": sample["prompt"],
        "assistant_target": sample["response"],
    }
    body = {
        "model": args.model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Audit this language-model training example. Score language quality, prompt/target "
                    "coherence, and training value from 1 to 5. A concise direct answer is valid when the "
                    "declared form requests direct-answer supervision. Return only the required JSON."
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "temperature": 0,
        "top_p": 1,
        "max_tokens": args.max_tokens,
        "response_format": COMPACT_JUDGE_RESPONSE_FORMAT,
    }
    last_error = ""
    for attempt in range(args.retries + 1):
        try:
            request = urllib.request.Request(
                args.base_url.rstrip("/") + "/chat/completions",
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json", "Authorization": "Bearer local"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=args.timeout) as response:
                content = json.loads(response.read().decode())["choices"][0]["message"]["content"]
            compact = json.loads(content)
            issue = compact["primary_problem"]
            issues = [] if issue.casefold() == "none" else [issue]
            judgment = {
                "primary_language": compact["primary_language"],
                "language_quality": {"score": compact["language_quality"], "issues": issues},
                "instruction_answer_coherence": {
                    "score": compact["instruction_answer_coherence"],
                    "issues": issues,
                },
                "training_value": {
                    "score": compact["training_value"],
                    "contributions": [],
                    "issues": issues,
                },
                "usable_for_training": compact["usable_for_training"],
                "primary_problem": issue,
                "assessment": "compact fallback judgment after malformed detailed JSON",
            }
            return {**sample, "judge_model": args.model, "judgment": judgment, "compact_fallback": True}
        except (OSError, TimeoutError, urllib.error.URLError, KeyError, ValueError, json.JSONDecodeError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < args.retries:
                time.sleep(args.retry_sleep * (attempt + 1))
    return {**sample, "judge_model": args.model, "judge_error": last_error, "compact_fallback": True}


def judge_with_fallback(args: argparse.Namespace, sample: dict[str, Any]) -> dict[str, Any]:
    result = call_judge(args, sample)
    return call_compact_judge(args, sample) if "judge_error" in result else result


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc


def load_resumable(path: Path) -> tuple[list[dict[str, Any]], set[str]]:
    if not path.exists():
        return [], set()
    raw = path.read_bytes()
    valid_end = 0
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines(keepends=True):
        if not line.endswith((b"\n", b"\r")):
            break
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed completed audit row in {path}: {exc}") from exc
        valid_end += len(line)
    if valid_end != len(raw):
        with path.open("r+b") as handle:
            handle.truncate(valid_end)
    successful = [row for row in rows if "judge_error" not in row]
    if len(successful) != len(rows):
        # Failed records are retry state, not completed audit decisions. Rewrite
        # the single-writer partition before submitting them again.
        atomic_jsonl(path, successful)
    return successful, {row["sample_id"] for row in successful}


def stable_partition(sample_id: str, partitions: int) -> int:
    return int.from_bytes(hashlib.blake2b(sample_id.encode(), digest_size=8).digest(), "big") % partitions


def audit(args: argparse.Namespace) -> None:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    existing, completed = load_resumable(args.output) if args.resume else ([], set())
    jobs = [
        row
        for row in read_jsonl(args.samples)
        if stable_partition(row["sample_id"], args.partitions) == args.partition_index
        and row["sample_id"] not in completed
    ]
    mode = "a" if args.resume else "w"
    finished = len(existing)
    with args.output.open(mode, encoding="utf-8") as handle, ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        iterator = iter(jobs)
        pending: dict[Any, None] = {}

        def fill() -> None:
            while len(pending) < args.concurrency:
                try:
                    sample = next(iterator)
                except StopIteration:
                    return
                pending[pool.submit(judge_with_fallback, args, sample)] = None

        fill()
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                del pending[future]
                handle.write(json.dumps(future.result(), ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
                finished += 1
                if finished % args.progress_interval == 0:
                    print(f"partition={args.partition_index} completed={finished}", flush=True)
            fill()
    print(json.dumps({"partition": args.partition_index, "completed": finished}, sort_keys=True))
    final_rows = list(read_jsonl(args.output))
    errors = sum("judge_error" in row for row in final_rows)
    if errors:
        raise SystemExit(f"partition {args.partition_index} has {errors} retryable judge errors")


def merge(args: argparse.Namespace) -> None:
    lock_path = args.output.with_suffix(args.output.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        expected_rows = list(read_jsonl(args.samples))
        expected = {row["sample_id"] for row in expected_rows}
        merged: dict[str, dict[str, Any]] = {}
        for partition in range(args.partitions):
            path = args.partition_root / f"partition_{partition}.jsonl"
            if not path.is_file():
                raise FileNotFoundError(path)
            for row in read_jsonl(path):
                sample_id = row["sample_id"]
                if sample_id in merged:
                    raise ValueError(f"duplicate result for {sample_id}")
                merged[sample_id] = row
        missing = expected - merged.keys()
        unexpected = merged.keys() - expected
        if missing or unexpected:
            raise ValueError(f"merge coverage mismatch: missing={len(missing)} unexpected={len(unexpected)}")
        ordered = sorted(
            merged.values(),
            key=lambda row: (
                row["source_id"],
                row.get("sample_ordinal", row["sample_id"]),
            ),
        )
        atomic_jsonl(args.output, ordered)
        errors = sum("judge_error" in row for row in ordered)
        summary = {
            "output": str(args.output),
            "rows": len(ordered),
            "sources": len({row["source_id"] for row in ordered}),
            "judge_errors": errors,
            "usable": sum(row.get("judgment", {}).get("usable_for_training") is True for row in ordered),
        }
        summary_path = args.output.with_suffix(".summary.json")
        temporary = summary_path.with_name(f".{summary_path.name}.tmp.{os.getpid()}")
        temporary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        os.replace(temporary, summary_path)
        print(json.dumps(summary, indent=2, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--tokenized-root", type=Path, default=DEFAULT_TOKENIZED_ROOT)
    prepare_parser.add_argument("--prefix-config", type=Path, default=DEFAULT_PREFIX_CONFIG)
    prepare_parser.add_argument("--inventory-doc", type=Path, default=DEFAULT_INVENTORY_DOC)
    prepare_parser.add_argument("--source-specs", type=Path)
    prepare_parser.add_argument("--stage")
    prepare_parser.add_argument("--samples-per-source", type=int, default=100)
    prepare_parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    prepare_parser.add_argument("--samples-output", type=Path, required=True)
    prepare_parser.add_argument("--inventory-output", type=Path, required=True)
    prepare_parser.add_argument(
        "--allow-pending-raw",
        action="store_true",
        help="prepare ready sources while recording unavailable raw-only sources as pending",
    )
    prepare_parser.set_defaults(func=prepare)

    audit_parser = commands.add_parser("audit")
    audit_parser.add_argument("--samples", type=Path, required=True)
    audit_parser.add_argument("--output", type=Path, required=True)
    audit_parser.add_argument("--base-url", required=True)
    audit_parser.add_argument("--model", required=True)
    audit_parser.add_argument("--partitions", type=int, default=8)
    audit_parser.add_argument("--partition-index", type=int, required=True)
    audit_parser.add_argument("--concurrency", type=int, default=64)
    audit_parser.add_argument("--max-tokens", type=int, default=512)
    audit_parser.add_argument("--retries", type=int, default=3)
    audit_parser.add_argument("--retry-sleep", type=float, default=1.0)
    audit_parser.add_argument("--timeout", type=float, default=300.0)
    audit_parser.add_argument("--progress-interval", type=int, default=100)
    audit_parser.add_argument("--resume", action="store_true")
    audit_parser.set_defaults(func=audit)

    merge_parser = commands.add_parser("merge")
    merge_parser.add_argument("--samples", type=Path, required=True)
    merge_parser.add_argument("--partition-root", type=Path, required=True)
    merge_parser.add_argument("--partitions", type=int, default=8)
    merge_parser.add_argument("--output", type=Path, required=True)
    merge_parser.set_defaults(func=merge)
    return root


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
