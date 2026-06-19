#!/usr/bin/env python3
"""Generate the DFM5 L eval comparison Markdown report from local artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/dfm5.md"


DFM5_CHECKPOINTS = [
    (
        "DFM5-L 50K",
        "step_50000",
        ROOT / "logs/eval/dfm5_L_step50000_full_20260614_dfm5_L_step50000_full",
        ROOT / "logs/dfm_evals/dfm5_L_step50000_full_20260614_dfm5_L_step50000_full",
        ROOT / "logs/euroeval/dfm5_L_step50000_full_20260614_dfm5_L_step50000_full/step_50000",
    ),
    (
        "DFM5-L 100K",
        "step_100000",
        ROOT / "logs/eval/dfm5_L_step100000_full_20260614_eurofirst_guard",
        ROOT / "logs/dfm_evals/dfm5_L_step100000_full_20260614_eurofirst_guard",
        ROOT / "logs/euroeval/dfm5_L_step100000_full_20260614_eurofirst_guard/step_100000",
    ),
    (
        "DFM5-L 150K",
        "step_150000",
        ROOT / "logs/eval/dfm5_L_step150000_full_20260615_eurofirst_guard",
        ROOT / "logs/dfm_evals/dfm5_L_step150000_full_20260615_eurofirst_guard",
        ROOT / "logs/euroeval/dfm5_L_step150000_full_20260615_eurofirst_guard/step_150000",
    ),
    (
        "DFM5-L 200K",
        "step_200000",
        ROOT / "logs/eval/dfm5_L_step200000_full_20260615_eurofirst_guard",
        ROOT / "logs/dfm_evals/dfm5_L_step200000_full_20260615_eurofirst_guard",
        ROOT / "logs/euroeval/dfm5_L_step200000_full_20260615_eurofirst_guard/step_200000",
    ),
    (
        "DFM5-L 250K",
        "step_250000",
        ROOT / "logs/eval/dfm5_L_step250000_full_20260615_eurofirst_guard",
        ROOT / "logs/dfm_evals/dfm5_L_step250000_full_20260615_eurofirst_guard",
        ROOT / "logs/euroeval/dfm5_L_step250000_full_20260615_eurofirst_guard/step_250000",
    ),
    (
        "DFM5-L 300K",
        "step_300000",
        ROOT / "logs/eval/dfm5_L_step300000_full_20260616_eurofirst_guard",
        ROOT / "logs/dfm_evals/dfm5_L_step300000_full_20260616_eurofirst_guard",
        ROOT / "logs/euroeval/dfm5_L_step300000_full_20260616_eurofirst_guard/step_300000",
    ),
    (
        "DFM5-L 350K",
        "step_350000",
        ROOT / "logs/eval/dfm5_L_step350000_full_20260616_new_scheduler",
        ROOT / "logs/dfm_evals/dfm5_L_step350000_full_20260616_new_scheduler",
        ROOT / "logs/euroeval/dfm5_L_step350000_full_20260616_new_scheduler/step_350000",
    ),
    (
        "DFM5-L 400K",
        "step_400000",
        ROOT / "logs/eval/dfm5_L_step400000_full_ordered_20260616",
        ROOT / "logs/dfm_evals/dfm5_L_step400000_full_ordered_20260616",
        ROOT / "logs/euroeval/dfm5_L_step400000_full_ordered_20260616/step_400000",
    ),
    (
        "DFM5-L 450K",
        "step_450000",
        ROOT / "logs/eval/dfm5_L_step450000_full_ordered_20260616",
        ROOT / "logs/dfm_evals/dfm5_L_step450000_full_ordered_20260616",
        ROOT / "logs/euroeval/dfm5_L_step450000_full_ordered_20260616/step_450000",
    ),
]

ORIG_DFM_ROOT = ROOT / "logs/dfm_evals/original_sapient_L_lite_all_checkpoints_20260603T213010"
QWEN35_2B_STANDARD_ROOT = ROOT / "logs/eval/qwen35_2b_clean_standard_20260617"
QWEN35_2B_DFM_ROOT = ROOT / "logs/dfm_evals/qwen35_2b_full_ordered_20260616"
QWEN35_2B_EURO_ROOT = ROOT / "logs/euroeval/qwen35_2b_full_ordered_20260616/qwen35_2b"


STANDARD_MAP = {
    "GSM8k acc": ("GSM8k", "eval/GSM8k/acc", ("GSM8k", "acc")),
    "MATH acc": ("MATH", "eval/MATH/acc", ("MATH", "acc")),
    "DROP F1": ("DROP", "eval/DROP/f1", ("DROP", "f1")),
    "MMLU acc": ("MMLU", "eval/MMLU/acc", ("MMLU", "acc")),
    "ARC-C acc": ("ARC", "eval/ARC/acc", ("ARC", "acc")),
    "HellaSwag acc": ("HellaSwag", "eval/HellaSwag/acc", ("HellaSwag", "acc")),
    "Winogrande acc": ("Winogrande", "eval/Winogrande/acc", ("Winogrande", "acc")),
    "BoolQ acc": ("BoolQ", "eval/BoolQ/acc", ("BoolQ", "acc")),
}

DFM_MAP = {
    "DaLA macro F1": ("dala/merged_metrics.json", "dala/linguistic-acceptability/dfm_evals_macro_f1"),
    "Danish Citizen Tests acc": ("danish_citizen_tests/merged_metrics.json", "danish-citizen-tests/knowledge/accuracy"),
    "GEC-DaLA exact match": ("gec_dala/merged_metrics.json", "gec_dala/exact_match/mean"),
    "Talemaader judged acc": ("generative_talemaader/merged_metrics.json", "generative-talemaader/model_graded_fact/accuracy"),
    "IFEval-DA final acc": ("merged_ifeval_da_metrics.json", "ifeval-da/instruction_following/final_acc"),
    "MultiWikiQA exact match": ("multi_wiki_qa/merged_metrics.json", "multi_wiki_qa/exact_match/mean"),
    "NordjyllandNews BERTScore": ("nordjyllandnews/merged_metrics.json", "nordjyllandnews/bertscore_f1/mean"),
    "PIQA-da acc": ("piqa/merged_metrics.json", "piqa/piqa_scorer/accuracy"),
    "WMT24++ en-da chrF++": ("wmt24pp_en_da/merged_metrics.json", "wmt24pp-en-da/chrf3pp/mean"),
    "GovReport BERTScore": ("govreport/merged_metrics.json", "govreport/bertscore_f1/mean"),
    "HumanEval pass rate": ("humaneval/merged_metrics.json", "humaneval/verify_sanitized/accuracy"),
}

EURO_MAP = {
    ("angry-tweets", "test_macro_f1"): "EuroEval Angry Tweets macro F1",
    ("scala-da", "test_macro_f1"): "EuroEval ScaLA-da macro F1",
    ("dansk", "test_micro_f1"): "EuroEval DaNSK NER micro F1",
    ("multi-wiki-qa-da", "test_f1"): "EuroEval MultiWikiQA-da F1",
    ("nordjylland-news", "test_chr_f3pp"): "EuroEval NordjyllandNews chrF++",
    ("danske-talemaader", "test_accuracy"): "EuroEval Talemaader acc",
    ("danish-citizen-tests", "test_accuracy"): "EuroEval Citizen Tests acc",
    ("hellaswag-da", "test_accuracy"): "EuroEval HellaSwag-da acc",
    ("ifeval-da", "test_instruction_accuracy"): "EuroEval IFEval-da instr acc",
    ("valeu-da", "test_european_values"): "EuroEval VaLEU-da",
    ("sst5", "test_macro_f1"): "EuroEval SST-5 macro F1",
    ("scala-en", "test_macro_f1"): "EuroEval ScaLA-en macro F1",
    ("conll-en", "test_micro_f1"): "EuroEval CoNLL-en NER micro F1",
    ("squad", "test_f1"): "EuroEval SQuAD F1",
    ("cnn-dailymail", "test_chr_f3pp"): "EuroEval CNN/DM chrF++",
    ("life-in-the-uk", "test_accuracy"): "EuroEval Life in UK acc",
    ("hellaswag", "test_accuracy"): "EuroEval HellaSwag acc",
    ("ifeval", "test_instruction_accuracy"): "EuroEval IFEval instr acc",
    ("bfcl-v2", "test_tool_calling_accuracy"): "EuroEval BFCL-v2 tool acc",
    ("valeu-en", "test_european_values"): "EuroEval VaLEU-en",
}

DANISH = [
    "DaLA macro F1",
    "Danish Citizen Tests acc",
    "GEC-DaLA exact match",
    "Talemaader judged acc",
    "IFEval-DA final acc",
    "MultiWikiQA exact match",
    "NordjyllandNews BERTScore",
    "PIQA-da acc",
    "WMT24++ en-da chrF++",
    "EuroEval Angry Tweets macro F1",
    "EuroEval ScaLA-da macro F1",
    "EuroEval DaNSK NER micro F1",
    "EuroEval MultiWikiQA-da F1",
    "EuroEval NordjyllandNews chrF++",
    "EuroEval Talemaader acc",
    "EuroEval Citizen Tests acc",
    "EuroEval HellaSwag-da acc",
    "EuroEval IFEval-da instr acc",
    "EuroEval VaLEU-da",
]
ENGLISH = [
    "ARC-C acc",
    "BoolQ acc",
    "DROP F1",
    "HellaSwag acc",
    "MMLU acc",
    "Winogrande acc",
    "GovReport BERTScore",
    "EuroEval SST-5 macro F1",
    "EuroEval ScaLA-en macro F1",
    "EuroEval CoNLL-en NER micro F1",
    "EuroEval SQuAD F1",
    "EuroEval CNN/DM chrF++",
    "EuroEval Life in UK acc",
    "EuroEval HellaSwag acc",
    "EuroEval IFEval instr acc",
    "EuroEval VaLEU-en",
]
MATH_CODE = [
    "GSM8k acc",
    "MATH acc",
    "HumanEval pass rate",
    "EuroEval BFCL-v2 tool acc",
]

CARD = {
    "GSM8k acc": (77.6, 84.7),
    "MATH acc": (51.2, 56.5),
    "DROP F1": (78.6, 82.3),
    "MMLU acc": (56.6, 60.7),
    "ARC-C acc": (75.9, 81.9),
    "HellaSwag acc": (52.7, 63.4),
    "Winogrande acc": (67.6, 72.4),
    "BoolQ acc": (85.0, 86.2),
}

QWEN35_2B = {
    "GSM8k acc": 53.0,
    "MATH acc": 34.2,
    "DROP F1": 30.8,
    "MMLU acc": 64.5,
    "ARC-C acc": 81.0,
    "HellaSwag acc": 64.6,
    "Winogrande acc": 56.7,
    "BoolQ acc": 80.5,
}

QWEN35_9B: dict[str, float] = {}

QWEN35_9B_OFFICIAL_ADJACENT = {
    "MMLU-Pro": 82.5,
    "MMLU-Redux": 91.1,
    "C-Eval": 88.2,
    "SuperGPQA": 58.2,
    "GPQA Diamond": 81.7,
    "IFEval": 91.5,
    "IFBench": 64.5,
    "Global PIQA": 83.2,
    "WMT24++": 72.6,
}


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def percent(value: float | None) -> float | None:
    if value is None:
        return None
    return value * 100 if abs(value) <= 1 else value


def metric_from_json(path: Path, suffix: str) -> float | None:
    obj = load_json(path)
    if not obj:
        return None
    for key, value in obj.get("metrics", {}).items():
        if key.endswith(suffix):
            return percent(float(value))
    return None


def parse_standard_merged(root: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    for metric, (task, key, _) in STANDARD_MAP.items():
        obj = load_json(root / "standard_shards" / task / "merged_metrics.json")
        if obj and key in obj.get("metrics", {}):
            out[metric] = percent(float(obj["metrics"][key]))  # type: ignore[arg-type]
    return out


def parse_standard_log(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    out: dict[tuple[str, str], float] = {}
    section = None
    for line in path.read_text(errors="ignore").splitlines():
        m = re.match(r"--- (.+) ---", line)
        if m:
            section = m.group(1)
            continue
        if section and (m := re.match(r"(acc|f1)\.*:\s*([0-9.]+)", line)):
            out[(section, m.group(1))] = float(m.group(2)) * 100
    return {metric: out[src] for metric, (_, _, src) in STANDARD_MAP.items() if src in out}


def parse_dfm(root: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    for metric, (rel, suffix) in DFM_MAP.items():
        value = metric_from_json(root / rel, suffix)
        if value is not None:
            out[metric] = value
    return out


def parse_euro(root: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    if not root.exists():
        return out
    files = []
    if (root / "euroeval_benchmark_results.jsonl").exists():
        files.append(root / "euroeval_benchmark_results.jsonl")
    files.extend(sorted(root.glob("*/euroeval_benchmark_results.jsonl")))
    for path in files:
        for line in path.read_text(errors="ignore").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            dataset = obj["eval_library"]["additional_details"]["dataset"]
            for result in obj.get("evaluation_results", []):
                metric = EURO_MAP.get((dataset, result["evaluation_name"]))
                if metric:
                    out[metric] = percent(float(result["score_details"]["score"]))  # type: ignore[assignment]
    return out


def load_dfm5() -> tuple[list[str], dict[str, dict[str, float]]]:
    labels: list[str] = []
    columns: dict[str, dict[str, float]] = {}
    for label, _, standard_root, dfm_root, euro_root in DFM5_CHECKPOINTS:
        labels.append(label)
        status = standard_root / "status.tsv"
        if status.exists() and "FINAL_MERGE_END" not in status.read_text(errors="ignore"):
            columns[label] = {}
            continue
        values: dict[str, float] = {}
        values.update(parse_standard_merged(standard_root))
        values.update(parse_dfm(dfm_root))
        values.update(parse_euro(euro_root))
        columns[label] = values
    return labels, columns


def load_original() -> tuple[list[str], dict[str, dict[str, float]]]:
    labels: list[str] = []
    columns: dict[str, dict[str, float]] = {}
    for epoch in range(1, 5):
        label = f"Orig Sapient L e{epoch} EMA"
        labels.append(label)
        values: dict[str, float] = {}
        values.update(parse_standard_log(ROOT / f"logs/eval/original_sapient_L/epoch_{epoch}.log"))
        values.update(parse_dfm(ORIG_DFM_ROOT / f"epoch_{epoch}"))
        values.update(parse_euro(ROOT / f"logs/euroeval/original_sapient_L/epoch_{epoch}"))
        columns[label] = values
    return labels, columns


def load_qwen35_2b() -> dict[str, float]:
    values = dict(QWEN35_2B)
    values.update(parse_standard_merged(QWEN35_2B_STANDARD_ROOT))
    values.update(parse_dfm(QWEN35_2B_DFM_ROOT))
    values.update(parse_euro(QWEN35_2B_EURO_ROOT))
    return values


def fmt(value: float | None, bold: bool = False) -> str:
    if value is None:
        return "—"
    text = f"{value:.1f}"
    return f"**{text}**" if bold else text


def section_average(values: dict[str, float], metrics: list[str]) -> float | None:
    filtered = [m for m in metrics if "VaLEU" not in m]
    nums = [values[m] for m in filtered if m in values]
    if len(nums) != len(filtered):
        return None
    return sum(nums) / len(nums)


def write_section(
    lines: list[str],
    title: str,
    metrics: list[str],
    avg_label: str,
    labels: list[str],
    columns: dict[str, dict[str, float]],
) -> None:
    lines.append(f"## {title}")
    lines.append("")
    lines.append("| Metric | " + " | ".join(labels) + " | Card L | Card XL | Qwen3.5 2B | Qwen3.5 9B |")
    lines.append("|---|" + "---:|" * (len(labels) + 4))
    for metric in metrics:
        card_l, card_xl = CARD.get(metric, (None, None))
        qwen35_2b = QWEN35_2B.get(metric)
        qwen35_9b = QWEN35_9B.get(metric)
        vals = [fmt(columns[label].get(metric)) for label in labels]
        lines.append(
            f"| {metric} | "
            + " | ".join(vals)
            + f" | {fmt(card_l)} | {fmt(card_xl)} | {fmt(qwen35_2b)} | {fmt(qwen35_9b)} |"
        )
    vals = [fmt(section_average(columns[label], metrics), bold=True) for label in labels]
    lines.append(f"| **{avg_label}** | " + " | ".join(vals) + " | — | — | — | — |")
    lines.append("")


def main() -> None:
    dfm5_labels, dfm5_columns = load_dfm5()
    orig_labels, orig_columns = load_original()
    QWEN35_2B.update(load_qwen35_2b())
    labels = dfm5_labels + orig_labels
    columns = {**dfm5_columns, **orig_columns}

    lines = [
        "# DFM5 L eval comparison",
        "",
        "Values are percent-style scores where applicable. `—` means no comparable value. Model-card L/XL values are only available for the standard README benchmarks. Qwen3.5 2B values use the local clean Qwen run artifacts where available, including the fixed GSM8K rerun, and fall back to HRM-Text arXiv v1 Table 4 for missing standard metrics. Qwen3.5 9B has official Qwen model-card results for adjacent newer benchmarks, but no same-suite HRM-Text standard row was found, so the table column is left unavailable.",
        "",
        "Original Sapient L uses EMA/default evaluation sources: full epoch-wise standard eval logs, epoch-wise EuroEval JSONL files, and the default/EMA local DFM-evals artifacts. The original DFM-evals artifacts are lite/sharded-local rows, so use them directionally for non-standard metrics. No `*_noema_*` artifacts are used.",
        "",
        "Qwen3.5 9B official adjacent language benchmarks from the model card: "
        + ", ".join(f"{name} {value:.1f}" for name, value in QWEN35_9B_OFFICIAL_ADJACENT.items())
        + ". These are not inserted into the main rows because they are not the same benchmark/configuration as the HRM-Text standard table.",
        "",
    ]
    write_section(lines, "Danish", DANISH, "Danish average", labels, columns)
    write_section(lines, "English", ENGLISH, "English average", labels, columns)
    write_section(lines, "Math & Code", MATH_CODE, "Math & Code average", labels, columns)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines)
    OUT.write_text(text, encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
