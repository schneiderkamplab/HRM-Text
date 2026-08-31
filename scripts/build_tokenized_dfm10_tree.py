#!/usr/bin/env python3
"""Build DFM10 as the DFM9 tokenized tree plus DFM10 additions."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


# These inherited DFM9 task families are superseded by native, context-safe
# DFM10 additions. Keep the prefixes centralized so rebuilding the union cannot
# accidentally retain both the old and replacement supervision.
REPLACED_BASE_PREFIXES = (
    "nemotron_terminal_corpus__",
    "dolci_instruct_sft_tool_use__",
    "dolci_instruct_sft_tool_use_sa__",
    "dolci_native_tool_use__",
)

REPLACEMENT_SOURCES = {
    "nemotron_terminal_corpus__": "nemotron_terminal_native",
    "dolci_instruct_sft_tool_use__": "dolci_tool_use_repaired",
    "dolci_instruct_sft_tool_use_sa__": "dolci_tool_use_repaired",
    "dolci_native_tool_use__": "dolci_tool_use_repaired",
}


def is_replaced_base_task(name: str) -> bool:
    return name.startswith(REPLACED_BASE_PREFIXES)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path("data/tokenized_dfm9"))
    parser.add_argument(
        "--nemotron-terminal-native",
        type=Path,
        default=Path("data/tokenized_dfm10_nemotron_terminal_native"),
    )
    parser.add_argument(
        "--andersen", type=Path, default=Path("data/tokenized_dfm10_andersen")
    )
    parser.add_argument(
        "--bornholmsk-parallel",
        type=Path,
        default=Path("data/tokenized_dfm10_bornholmsk_parallel"),
    )
    parser.add_argument(
        "--diem-modernization",
        type=Path,
        default=Path("data/tokenized_dfm10_diem_modernization"),
    )
    parser.add_argument(
        "--cor-sem", type=Path, default=Path("data/tokenized_dfm10_cor_sem")
    )
    parser.add_argument(
        "--danish-book-ads",
        type=Path,
        default=Path("data/tokenized_dfm10_danish_book_ads"),
    )
    parser.add_argument(
        "--sks-tei", type=Path, default=Path("data/tokenized_dfm10_sks_tei")
    )
    parser.add_argument(
        "--alexandra", type=Path, default=Path("data/tokenized_dfm10_alexandra")
    )
    parser.add_argument(
        "--folketing", type=Path, default=Path("data/tokenized_dfm10_folketing")
    )
    parser.add_argument(
        "--deepdive", type=Path, default=Path("data/tokenized_dfm10_deepdive")
    )
    parser.add_argument(
        "--dbc-repaired", type=Path, default=Path("data/tokenized_dfm10_dbc_repaired")
    )
    parser.add_argument(
        "--openmath-repaired",
        type=Path,
        default=Path("data/tokenized_dfm10_openmathinstruct2_repaired"),
    )
    parser.add_argument(
        "--dolci-tool-use-repaired",
        type=Path,
        default=Path("data/tokenized_dfm10_dolci_tool_use_repaired"),
    )
    parser.add_argument(
        "--govreport-repaired",
        type=Path,
        default=Path("data/tokenized_dfm10_govreport_repaired"),
    )
    parser.add_argument(
        "--wiki-cat-sum-repaired",
        type=Path,
        default=Path("data/tokenized_dfm10_wiki_cat_sum_repaired"),
    )
    parser.add_argument(
        "--danmarks-statistik-bt-repaired",
        type=Path,
        default=Path("data/tokenized_dfm10_danmarks_statistik_bt_repaired"),
    )
    parser.add_argument(
        "--nordjylland-news-repaired",
        type=Path,
        default=Path("data/tokenized_dfm10_nordjylland_news_repaired"),
    )
    parser.add_argument(
        "--dst-table-prompts-repaired",
        type=Path,
        default=Path("data/tokenized_dfm10_dst_table_prompts_repaired"),
    )
    parser.add_argument(
        "--nemotron-swe-repaired",
        type=Path,
        default=Path("data/tokenized_dfm10_nemotron_swe_repaired"),
    )
    parser.add_argument(
        "--dynaword-instruct-repaired",
        type=Path,
        default=Path("data/tokenized_dfm10_dynaword_instruct_repaired"),
    )
    parser.add_argument(
        "--code-meta-reasoning-repaired",
        type=Path,
        default=Path("data/tokenized_dfm10_code_meta_reasoning_repaired"),
    )
    parser.add_argument(
        "--opus-repaired",
        type=Path,
        default=Path("data/tokenized_dfm10_opus_repaired"),
    )
    parser.add_argument(
        "--university-portals-repaired",
        type=Path,
        default=Path("data/tokenized_dfm10_university_portals_repaired"),
    )
    parser.add_argument(
        "--scientific-summaries-repaired",
        type=Path,
        default=Path("data/tokenized_dfm10_scientific_summaries_repaired"),
    )
    parser.add_argument(
        "--machine-translation-da-uk-repaired",
        type=Path,
        default=Path("data/tokenized_dfm10_machine_translation_da_uk_repaired"),
    )
    parser.add_argument(
        "--qrecc-ii-repaired",
        type=Path,
        default=Path("data/tokenized_dfm10_qrecc_ii_repaired"),
    )
    parser.add_argument(
        "--scibench-repaired",
        type=Path,
        default=Path("data/tokenized_dfm10_scibench_repaired"),
    )
    parser.add_argument(
        "--openstax-sft",
        type=Path,
        default=Path("data/tokenized_dfm10_openstax_sft"),
    )
    parser.add_argument(
        "--mimir-grounded-expanded-sft",
        type=Path,
        default=Path("data/tokenized_dfm10_mimir_grounded_expanded_sft"),
    )
    parser.add_argument(
        "--mimir-answer-contract-calibration",
        type=Path,
        default=Path("data/tokenized_dfm10_mimir_answer_contract_calibration"),
    )
    parser.add_argument(
        "--mimir-benchmark-campaigns",
        type=Path,
        default=Path("data/tokenized_dfm10_mimir_benchmark_campaigns"),
    )
    parser.add_argument(
        "--danish-lexical",
        type=Path,
        default=Path("data/tokenized_dfm10_danish_lexical"),
    )
    parser.add_argument(
        "--tidsskrift-open",
        type=Path,
        default=Path("data/tokenized_dfm10_tidsskrift_open"),
    )
    parser.add_argument(
        "--tidsskrift-open-chats",
        type=Path,
        default=Path("data/tokenized_dfm10_tidsskrift_open_chats"),
    )
    parser.add_argument(
        "--danish-wikipedia-open-chats",
        type=Path,
        default=Path("data/tokenized_dfm10_danish_wikipedia_open_chats"),
    )
    parser.add_argument(
        "--openstax-open-chats",
        type=Path,
        default=Path("data/tokenized_dfm10_openstax_open_chats"),
    )
    parser.add_argument(
        "--synthetic-values-model-charter",
        type=Path,
        default=Path("data/tokenized_dfm10_synthetic_values_model_charter"),
    )
    parser.add_argument(
        "--synthetic-values-model-charter-da",
        type=Path,
        default=Path("data/tokenized_dfm10_synthetic_values_model_charter_da"),
    )
    parser.add_argument(
        "--danish-persona-chats",
        type=Path,
        default=Path("data/tokenized_dfm10_danish_persona_chats"),
    )
    parser.add_argument(
        "--domsdatabasen-grounded-chats",
        type=Path,
        default=Path("data/tokenized_dfm10_domsdatabasen_grounded_chats"),
    )
    parser.add_argument(
        "--medical", type=Path, default=Path("data/tokenized_dfm10_medical")
    )
    parser.add_argument(
        "--medquad", type=Path, default=Path("data/tokenized_dfm10_medquad")
    )
    parser.add_argument("--output", type=Path, default=Path("data/tokenized_dfm10"))
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def link(source: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    destination.symlink_to(source.resolve(), target_is_directory=source.is_dir())


def task_directories(root: Path) -> list[Path]:
    tasks: list[Path] = []
    for directory, _, files in os.walk(root, followlinks=True):
        path = Path(directory)
        if path != root and "metadata.json" in files:
            tasks.append(path)
    return sorted(tasks)


def normalized_tokenizer_info(path: Path) -> dict[str, object]:
    info = json.loads(path.read_text(encoding="utf-8"))
    for key in ("tokenizer_path", "chat_template_path"):
        value = info.get(key)
        if not isinstance(value, str):
            continue
        resource = Path(value)
        if not resource.is_absolute():
            resource = ROOT / resource
        info[key] = str(resource.resolve())
    return info


def main() -> None:
    args = parse_args()
    if not (args.base / "tokenizer_info.json").is_file():
        raise FileNotFoundError(args.base / "tokenizer_info.json")

    additions = (
        ("nemotron_terminal_native", args.nemotron_terminal_native),
        ("andersen", args.andersen),
        ("bornholmsk_parallel", args.bornholmsk_parallel),
        ("diem_modernization", args.diem_modernization),
        ("cor_sem", args.cor_sem),
        ("danish_book_ads", args.danish_book_ads),
        ("sks_tei", args.sks_tei),
        ("alexandra", args.alexandra),
        ("folketing", args.folketing),
        ("deepdive", args.deepdive),
        ("dbc_repaired", args.dbc_repaired),
        ("openmathinstruct2_repaired", args.openmath_repaired),
        ("dolci_tool_use_repaired", args.dolci_tool_use_repaired),
        ("govreport_repaired", args.govreport_repaired),
        ("wiki_cat_sum_repaired", args.wiki_cat_sum_repaired),
        ("danmarks_statistik_bt_repaired", args.danmarks_statistik_bt_repaired),
        ("nordjylland_news_repaired", args.nordjylland_news_repaired),
        ("dst_table_prompts_repaired", args.dst_table_prompts_repaired),
        ("nemotron_swe_repaired", args.nemotron_swe_repaired),
        ("dynaword_instruct_repaired", args.dynaword_instruct_repaired),
        ("code_meta_reasoning_repaired", args.code_meta_reasoning_repaired),
        ("opus_da_en_repaired", args.opus_repaired),
        ("danish_university_portals_bt_repaired", args.university_portals_repaired),
        ("scientific_summaries_repaired", args.scientific_summaries_repaired),
        ("machine_translation_da_uk_repaired", args.machine_translation_da_uk_repaired),
        ("sapient_qrecc_ii_repaired", args.qrecc_ii_repaired),
        ("sapient_scibench_repaired", args.scibench_repaired),
        ("openstax_mimir_sft", args.openstax_sft),
        ("mimir_grounded_expanded_sft", args.mimir_grounded_expanded_sft),
        ("mimir_answer_contract_calibration", args.mimir_answer_contract_calibration),
        ("mimir_benchmark_campaigns", args.mimir_benchmark_campaigns),
        ("danish_lexical_sft", args.danish_lexical),
        ("tidsskrift_open_sft", args.tidsskrift_open),
        ("tidsskrift_open_chats", args.tidsskrift_open_chats),
        ("danish_wikipedia_open_chats", args.danish_wikipedia_open_chats),
        ("openstax_open_chats", args.openstax_open_chats),
        (
            "dfm10_synthetic_values_model_charter",
            args.synthetic_values_model_charter,
        ),
        (
            "dfm10_synthetic_values_model_charter_da",
            args.synthetic_values_model_charter_da,
        ),
        ("danish_persona_chats", args.danish_persona_chats),
        ("domsdatabasen_grounded_chats", args.domsdatabasen_grounded_chats),
        ("medical", args.medical),
        ("medquad", args.medquad),
    )
    optional_queued = {
        "diem_modernization",
        "cor_sem",
        "danish_book_ads",
        "sks_tei",
        "folketing",
        "tidsskrift_open_sft",
        "tidsskrift_open_chats",
        "danish_wikipedia_open_chats",
        "openstax_open_chats",
        "danish_persona_chats",
        "domsdatabasen_grounded_chats",
        "medquad",
        "mimir_benchmark_campaigns",
    }
    for label, root in additions:
        if label not in optional_queued and not root.exists():
            raise FileNotFoundError(root)
    available_additions = tuple(
        (label, root) for label, root in additions if root.exists()
    )
    base_tokenizer_info = normalized_tokenizer_info(args.base / "tokenizer_info.json")
    for _, addition in available_additions:
        if not (addition / "tokenizer_info.json").is_file():
            raise FileNotFoundError(addition / "tokenizer_info.json")
        if base_tokenizer_info != normalized_tokenizer_info(addition / "tokenizer_info.json"):
            raise ValueError(
                f"DFM9 and {addition} use different tokenizer/template metadata"
            )
    dst_gate = args.dst_table_prompts_repaired / "production_gate.json"
    if not dst_gate.is_file():
        raise FileNotFoundError(
            f"DST replacement has not passed its production grounding gate: {dst_gate}"
        )

    if args.output.exists() or args.output.is_symlink():
        if not args.force:
            raise FileExistsError(f"{args.output} exists; pass --force to rebuild")
        if args.output.is_symlink() or args.output.is_file():
            args.output.unlink()
        else:
            shutil.rmtree(args.output)
    args.output.mkdir(parents=True)
    link(args.base / "tokenizer_info.json", args.output / "tokenizer_info.json")

    counts: dict[str, int] = {}
    for label, root in (("dfm9", args.base), *available_additions):
        count = 0
        for source in task_directories(root):
            name = source.relative_to(root).as_posix()
            if label == "dfm9" and is_replaced_base_task(name):
                continue
            link(source, args.output / name)
            count += 1
        counts[label] = count
    for label, _ in additions:
        counts.setdefault(label, 0)

    manifest = {
        "base": str(args.base),
        "replaced_base_prefixes": list(REPLACED_BASE_PREFIXES),
        "replacement_sources": REPLACEMENT_SOURCES,
        "nemotron_terminal_native": str(args.nemotron_terminal_native),
        "andersen": str(args.andersen),
        "bornholmsk_parallel": str(args.bornholmsk_parallel),
        "diem_modernization": str(args.diem_modernization),
        "cor_sem": str(args.cor_sem),
        "danish_book_ads": str(args.danish_book_ads),
        "sks_tei": str(args.sks_tei),
        "alexandra": str(args.alexandra),
        "folketing": str(args.folketing),
        "deepdive": str(args.deepdive),
        "dbc_repaired": str(args.dbc_repaired),
        "openmathinstruct2_repaired": str(args.openmath_repaired),
        "dolci_tool_use_repaired": str(args.dolci_tool_use_repaired),
        "govreport_repaired": str(args.govreport_repaired),
        "wiki_cat_sum_repaired": str(args.wiki_cat_sum_repaired),
        "danmarks_statistik_bt_repaired": str(args.danmarks_statistik_bt_repaired),
        "nordjylland_news_repaired": str(args.nordjylland_news_repaired),
        "dst_table_prompts_repaired": str(args.dst_table_prompts_repaired),
        "nemotron_swe_repaired": str(args.nemotron_swe_repaired),
        "dynaword_instruct_repaired": str(args.dynaword_instruct_repaired),
        "code_meta_reasoning_repaired": str(args.code_meta_reasoning_repaired),
        "opus_da_en_repaired": str(args.opus_repaired),
        "danish_university_portals_bt_repaired": str(
            args.university_portals_repaired
        ),
        "scientific_summaries_repaired": str(args.scientific_summaries_repaired),
        "machine_translation_da_uk_repaired": str(args.machine_translation_da_uk_repaired),
        "sapient_qrecc_ii_repaired": str(args.qrecc_ii_repaired),
        "sapient_scibench_repaired": str(args.scibench_repaired),
        "openstax_mimir_sft": str(args.openstax_sft),
        "mimir_grounded_expanded_sft": str(args.mimir_grounded_expanded_sft),
        "mimir_answer_contract_calibration": str(args.mimir_answer_contract_calibration),
        "mimir_benchmark_campaigns": str(args.mimir_benchmark_campaigns),
        "danish_lexical_sft": str(args.danish_lexical),
        "tidsskrift_open_sft": str(args.tidsskrift_open),
        "tidsskrift_open_chats": str(args.tidsskrift_open_chats),
        "danish_wikipedia_open_chats": str(args.danish_wikipedia_open_chats),
        "openstax_open_chats": str(args.openstax_open_chats),
        "dfm10_synthetic_values_model_charter": str(
            args.synthetic_values_model_charter
        ),
        "dfm10_synthetic_values_model_charter_da": str(
            args.synthetic_values_model_charter_da
        ),
        "danish_persona_chats": str(args.danish_persona_chats),
        "domsdatabasen_grounded_chats": str(args.domsdatabasen_grounded_chats),
        "medical": str(args.medical),
        "medquad": str(args.medquad),
        "output": str(args.output),
        "task_counts": counts,
        "total_tasks": sum(counts.values()),
    }

    leaked = sorted(
        task.relative_to(args.output).as_posix()
        for task in task_directories(args.output)
        if is_replaced_base_task(task.relative_to(args.output).as_posix())
    )
    if leaked:
        raise RuntimeError(
            "superseded DFM9 tasks leaked into the DFM10 union: "
            + ", ".join(leaked[:10])
        )
    (args.output / "union_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
