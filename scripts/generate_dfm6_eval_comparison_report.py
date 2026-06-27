#!/usr/bin/env python3
"""Generate the DFM6 eval comparison Markdown report from local artifacts."""

from __future__ import annotations

from pathlib import Path

import generate_dfm5_l_eval_comparison_report as dfm5


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/dfm6.md"


DFM6_CHECKPOINTS = [
    (
        "DFM6-XL-gas2 50K",
        "step_50000",
        ROOT / "logs/eval/dfm6_XL_gas2_step50000_vllm_main_20260620",
        ROOT / "logs/dfm_evals/dfm6_XL_gas2_step50000_vllm_main_20260620",
        ROOT / "logs/euroeval/dfm6_XL_gas2_step50000_vllm_main_20260620/step_50000",
    ),
    (
        "DFM6-XL-gas2 100K",
        "step_100000",
        ROOT / "logs/eval/dfm6_XL_gas2_step100000_vllm_main_20260621",
        ROOT / "logs/dfm_evals/dfm6_XL_gas2_step100000_vllm_main_20260621",
        ROOT / "logs/euroeval/dfm6_XL_gas2_step100000_vllm_main_20260621/step_100000",
    ),
    (
        "DFM6-XL-gas2 150K",
        "step_150000",
        ROOT / "logs/eval/dfm6_XL_gas2_step150000_vllm_main_20260621",
        ROOT / "logs/dfm_evals/dfm6_XL_gas2_step150000_vllm_main_20260621",
        ROOT / "logs/euroeval/dfm6_XL_gas2_step150000_vllm_main_20260621/step_150000",
    ),
    (
        "DFM6-XL-gas2 200K",
        "step_200000",
        ROOT / "logs/eval/dfm6_XL_gas2_step200000_vllm_main_20260621",
        ROOT / "logs/dfm_evals/dfm6_XL_gas2_step200000_vllm_main_20260621",
        ROOT / "logs/euroeval/dfm6_XL_gas2_step200000_vllm_main_20260621/step_200000",
    ),
    (
        "DFM6-XL-gas2 250K",
        "step_250000",
        ROOT / "logs/eval/dfm6_XL_gas2_step250000_vllm_main_20260621",
        ROOT / "logs/dfm_evals/dfm6_XL_gas2_step250000_vllm_main_20260621",
        ROOT / "logs/euroeval/dfm6_XL_gas2_step250000_vllm_main_20260621/step_250000",
    ),
    (
        "DFM6-XL-gas2 300K",
        "step_300000",
        ROOT / "logs/eval/dfm6_XL_gas2_step300000_vllm_main_20260622",
        ROOT / "logs/dfm_evals/dfm6_XL_gas2_step300000_vllm_main_20260622",
        ROOT / "logs/euroeval/dfm6_XL_gas2_step300000_vllm_main_20260622/step_300000",
    ),
    (
        "DFM6-XL-gas2 350K",
        "step_350000",
        ROOT / "logs/eval/dfm6_XL_gas2_step350000_vllm_main_20260622",
        ROOT / "logs/dfm_evals/dfm6_XL_gas2_step350000_vllm_main_20260622",
        ROOT / "logs/euroeval/dfm6_XL_gas2_step350000_vllm_main_20260622/step_350000",
    ),
    (
        "DFM6-XL-gas2 400K",
        "step_400000",
        ROOT / "logs/eval/dfm6_XL_gas2_step400000_vllm_main_20260622",
        ROOT / "logs/dfm_evals/dfm6_XL_gas2_step400000_vllm_main_20260622",
        ROOT / "logs/euroeval/dfm6_XL_gas2_step400000_vllm_main_20260622/step_400000",
    ),
    (
        "DFM6-XL-gas2 450K",
        "step_450000",
        ROOT / "logs/eval/dfm6_XL_gas2_step450000_vllm_main_20260622",
        ROOT / "logs/dfm_evals/dfm6_XL_gas2_step450000_vllm_main_20260622",
        ROOT / "logs/euroeval/dfm6_XL_gas2_step450000_vllm_main_20260622/step_450000",
    ),
]


def load_checkpoints(
    checkpoints: list[tuple[str, str, Path, Path, Path]],
) -> tuple[list[str], dict[str, dict[str, float]]]:
    labels: list[str] = []
    columns: dict[str, dict[str, float]] = {}
    for label, _, standard_root, dfm_root, euro_root in checkpoints:
        labels.append(label)
        values: dict[str, float] = {}
        values.update(dfm5.parse_standard_merged(standard_root))
        values.update(dfm5.parse_dfm(dfm_root))
        values.update(dfm5.parse_euro(euro_root))
        columns[label] = values
    return labels, columns


def load_dfm5_900k() -> tuple[list[str], dict[str, dict[str, float]]]:
    checkpoints = [row for row in dfm5.DFM5_CHECKPOINTS if row[0] == "DFM5-L 900K"]
    if len(checkpoints) != 1:
        raise RuntimeError("Expected exactly one DFM5-L 900K checkpoint definition")
    return load_checkpoints(checkpoints)


def main() -> None:
    dfm6_labels, dfm6_columns = load_checkpoints(DFM6_CHECKPOINTS)
    dfm5_900_labels, dfm5_900_columns = load_dfm5_900k()
    orig_labels, orig_columns = dfm5.load_original()
    dfm5.QWEN35_2B.update(dfm5.load_qwen35_2b())

    labels = dfm6_labels + dfm5_900_labels + orig_labels
    columns = {**dfm6_columns, **dfm5_900_columns, **orig_columns}

    lines = [
        "# DFM6 eval comparison",
        "",
        "Values are percent-style scores where applicable. `—` means no comparable value. "
        "DFM6 checkpoint columns use local DFM6 artifacts. The DFM5-L 900K column is "
        "included immediately before the Original Sapient L comparison columns. "
        "Model-card L/XL values and Qwen3.5 comparison columns match the DFM5 report.",
        "",
        "DFM6-XL-gas2 is evaluated with the Gemma-native chat template for standard "
        "vLLM prompts and for vLLM server based DFM/EuroEval jobs.",
        "",
        "Original Sapient L uses EMA/default evaluation sources: full epoch-wise "
        "standard eval logs, epoch-wise EuroEval JSONL files, and the default/EMA "
        "local DFM-evals artifacts. The original DFM-evals artifacts are "
        "lite/sharded-local rows, so use them directionally for non-standard metrics. "
        "No `*_noema_*` artifacts are used.",
        "",
        "Qwen3.5 9B official adjacent language benchmarks from the model card: "
        + ", ".join(f"{name} {value:.1f}" for name, value in dfm5.QWEN35_9B_OFFICIAL_ADJACENT.items())
        + ". These are not inserted into the main rows because they are not the same "
        "benchmark/configuration as the HRM-Text standard table.",
        "",
    ]
    dfm5.write_section(lines, "Danish", dfm5.DANISH, "Danish average", labels, columns)
    dfm5.write_section(lines, "English", dfm5.ENGLISH, "English average", labels, columns)
    dfm5.write_section(lines, "Math & Code", dfm5.MATH_CODE, "Math & Code average", labels, columns)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
