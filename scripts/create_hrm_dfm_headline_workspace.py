#!/usr/bin/env python3
"""Create a W&B HRM DFM workspace with headline eval metrics by area."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import wandb_workspaces.reports.v2 as wr
import wandb_workspaces.workspaces as ws
from wandb_workspaces import expr
from wandb_workspaces.workspaces import internal


ENTITY = "peter-sk-sdu"
PROJECT = "HRM DFM"
WORKSPACE_NAME = "HRM DFM headline metrics"
X_AXIS = "eval/epoch"
MAX_RUNS_TO_SHOW = 50

ENGLISH_METRICS = [
    ("ARC accuracy", "eval/ARC/acc"),
    ("BoolQ accuracy", "eval/BoolQ/acc"),
    ("DROP F1", "eval/DROP/f1"),
    ("HellaSwag accuracy", "eval/HellaSwag/acc"),
    ("MMLU accuracy", "eval/MMLU/acc"),
    ("Winogrande accuracy", "eval/Winogrande/acc"),
    ("GovReport ROUGE-2", "eval/govreport/rouge2/mean"),
]

MATH_CODE_METRICS = [
    ("GSM8k accuracy", "eval/GSM8k/acc"),
    ("MATH accuracy", "eval/MATH/acc"),
    ("HumanEval pass rate", "eval/humaneval/verify/accuracy"),
]

DANISH_METRICS = [
    ("DaLA macro F1", "eval/dala/linguistic-acceptability/dfm_evals_macro_f1"),
    ("Danish Citizen Tests accuracy", "eval/danish-citizen-tests/knowledge/accuracy"),
    ("GEC-DaLA exact match", "eval/gec_dala/exact_match/mean"),
    ("Talemaader judged accuracy", "eval/generative-talemaader/model_graded_fact/accuracy"),
    ("IFEval-DA final accuracy", "eval/ifeval-da/instruction_following/final_acc"),
    ("MultiWikiQA F1", "eval/multi_wiki_qa/f1/mean"),
    ("NordjyllandNews ROUGE-2", "eval/nordjyllandnews/rouge2/mean"),
    ("PIQA-da accuracy", "eval/piqa/piqa_scorer/accuracy"),
    ("WMT24++ en-da chrF++", "eval/wmt24pp-en-da/chrf3pp/mean"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entity", default=ENTITY)
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--name", default=WORKSPACE_NAME)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("logs/wandb_workspace_specs/hrm_dfm_headline_metrics_by_language.json"),
    )
    return parser.parse_args()


def panel(title: str, metric: str) -> wr.LinePlot:
    return wr.LinePlot(
        title=title,
        x=X_AXIS,
        y=[metric],
        title_x="epoch",
        legend_fields=["run:displayName"],
        smoothing_type="none",
        max_runs_to_show=MAX_RUNS_TO_SHOW,
        xaxis_format="number",
    )


def section(name: str, metrics: list[tuple[str, str]]) -> ws.Section:
    return ws.Section(
        name=name,
        panels=[panel(title, metric) for title, metric in metrics],
        is_open=True,
        layout_settings=ws.SectionLayoutSettings(columns=3, rows=4),
    )


def main() -> None:
    args = parse_args()
    workspace = ws.Workspace(
        entity=args.entity,
        project=args.project,
        name=args.name,
        sections=[
            section("Danish Headline Metrics", DANISH_METRICS),
            section("English Headline Metrics", ENGLISH_METRICS),
            section("Math & Code Headline Metrics", MATH_CODE_METRICS),
        ],
        settings=ws.WorkspaceSettings(
            x_axis=X_AXIS,
            smoothing_type="none",
            max_runs=MAX_RUNS_TO_SHOW,
            remove_legends_from_panels=False,
            tooltip_number_of_runs="all_runs",
        ),
        runset_settings=ws.RunsetSettings(
            order=[expr.Ordering(expr.Metric("CreatedTimestamp"), ascending=True)],
            pinned_columns=[
                "run:displayName",
                "summary:eval/last_train_step",
                "summary:eval/last_epoch",
            ],
        ),
        auto_generate_panels=False,
    )
    view = workspace._to_model()
    if not view.name:
        view.name = internal._generate_view_name()
    view.spec.section.run_sets[0].run_feed.page_size = MAX_RUNS_TO_SHOW
    response = internal.upsert_view2(view)
    workspace._internal_name = response["upsertView"]["view"]["name"]
    workspace._internal_id = response["upsertView"]["view"]["id"]
    print(f"View saved: {workspace.url}")

    manifest = {
        "entity": args.entity,
        "project": args.project,
        "name": args.name,
        "url": workspace.url,
        "x_axis": X_AXIS,
        "max_runs_to_show": MAX_RUNS_TO_SHOW,
        "run_feed_page_size": MAX_RUNS_TO_SHOW,
        "run_order": "CreatedTimestamp ascending",
        "sections": {
            "Danish Headline Metrics": DANISH_METRICS,
            "English Headline Metrics": ENGLISH_METRICS,
            "Math & Code Headline Metrics": MATH_CODE_METRICS,
        },
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
