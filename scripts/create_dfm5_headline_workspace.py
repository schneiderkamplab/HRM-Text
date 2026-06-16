#!/usr/bin/env python3
"""Create a W&B DFM5 workspace with headline eval and training panels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import wandb_workspaces.reports.v2 as wr
import wandb_workspaces.workspaces as ws
from wandb_workspaces import expr
from wandb_workspaces.workspaces import internal


ENTITY = "peter-sk-sdu"
PROJECT = "DFM5"
WORKSPACE_NAME = "DFM5 headline metrics"
MAX_RUNS_TO_SHOW = 50

EVAL_X_AXIS = "eval/epoch"
DFM_EVAL_X_AXIS = "dfm_eval/epoch"
EUROEVAL_X_AXIS = "euroeval/epoch"
HEADLINE_AVG_X_AXIS = "avg/epoch"
HEADLINE_AVG_PREFIX = "avg"
TRAIN_X_AXIS = "_step"

DANISH_METRICS = [
    ("DaLA macro F1", "dfm_eval/dala/linguistic-acceptability/dfm_evals_macro_f1"),
    ("Danish Citizen Tests accuracy", "dfm_eval/danish-citizen-tests/knowledge/accuracy"),
    ("GEC-DaLA exact match", "dfm_eval/gec_dala/exact_match/mean"),
    ("Talemaader judged accuracy", "dfm_eval/generative-talemaader/model_graded_fact/accuracy"),
    ("IFEval-DA final accuracy", "dfm_eval/ifeval-da/instruction_following/final_acc"),
    ("MultiWikiQA exact match", "dfm_eval/multi_wiki_qa/exact_match/mean"),
    ("NordjyllandNews BERTScore", "dfm_eval/nordjyllandnews/bertscore_f1/mean"),
    ("PIQA-da accuracy", "dfm_eval/piqa/piqa_scorer/accuracy"),
    ("WMT24++ en-da chrF++", "dfm_eval/wmt24pp-en-da/chrf3pp/mean"),
]

DANISH_EUROEVAL_METRICS = [
    ("EuroEval Angry Tweets macro F1", "euroeval/da/sentiment-classification/angry-tweets/macro_f1", EUROEVAL_X_AXIS),
    ("EuroEval ScaLA-da macro F1", "euroeval/da/linguistic-acceptability/scala-da/macro_f1", EUROEVAL_X_AXIS),
    ("EuroEval DaNSK NER micro F1", "euroeval/da/named-entity-recognition/dansk/micro_f1", EUROEVAL_X_AXIS),
    ("EuroEval MultiWikiQA-da F1", "euroeval/da/reading-comprehension/multi-wiki-qa-da/f1", EUROEVAL_X_AXIS),
    ("EuroEval NordjyllandNews chrF++", "euroeval/da/summarization/nordjylland-news/chr_f3pp", EUROEVAL_X_AXIS),
    ("EuroEval Danske Talemaader accuracy", "euroeval/da/knowledge/danske-talemaader/accuracy", EUROEVAL_X_AXIS),
    ("EuroEval Danish Citizen Tests accuracy", "euroeval/da/knowledge/danish-citizen-tests/accuracy", EUROEVAL_X_AXIS),
    ("EuroEval HellaSwag-da accuracy", "euroeval/da/common-sense-reasoning/hellaswag-da/accuracy", EUROEVAL_X_AXIS),
    ("EuroEval IFEval-da instruction accuracy", "euroeval/da/instruction-following/ifeval-da/instruction_accuracy", EUROEVAL_X_AXIS),
    ("EuroEval Value-da score", "euroeval/da/european-values/valeu-da/european_values", EUROEVAL_X_AXIS),
]

ENGLISH_METRICS = [
    ("ARC accuracy", "eval/ARC/acc", EVAL_X_AXIS),
    ("BoolQ accuracy", "eval/BoolQ/acc", EVAL_X_AXIS),
    ("DROP F1", "eval/DROP/f1", EVAL_X_AXIS),
    ("HellaSwag accuracy", "eval/HellaSwag/acc", EVAL_X_AXIS),
    ("MMLU accuracy", "eval/MMLU/acc", EVAL_X_AXIS),
    ("Winogrande accuracy", "eval/Winogrande/acc", EVAL_X_AXIS),
    ("GovReport BERTScore", "dfm_eval/govreport/bertscore_f1/mean", DFM_EVAL_X_AXIS),
]

ENGLISH_EUROEVAL_METRICS = [
    ("EuroEval SST-5 macro F1", "euroeval/en/sentiment-classification/sst5/macro_f1", EUROEVAL_X_AXIS),
    ("EuroEval ScaLA-en macro F1", "euroeval/en/linguistic-acceptability/scala-en/macro_f1", EUROEVAL_X_AXIS),
    ("EuroEval CoNLL-en NER micro F1", "euroeval/en/named-entity-recognition/conll-en/micro_f1", EUROEVAL_X_AXIS),
    ("EuroEval SQuAD F1", "euroeval/en/reading-comprehension/squad/f1", EUROEVAL_X_AXIS),
    ("EuroEval CNN/DailyMail chrF++", "euroeval/en/summarization/cnn-dailymail/chr_f3pp", EUROEVAL_X_AXIS),
    ("EuroEval Life in the UK accuracy", "euroeval/en/knowledge/life-in-the-uk/accuracy", EUROEVAL_X_AXIS),
    ("EuroEval HellaSwag accuracy", "euroeval/en/common-sense-reasoning/hellaswag/accuracy", EUROEVAL_X_AXIS),
    ("EuroEval IFEval instruction accuracy", "euroeval/en/instruction-following/ifeval/instruction_accuracy", EUROEVAL_X_AXIS),
    ("EuroEval Value-en score", "euroeval/en/european-values/valeu-en/european_values", EUROEVAL_X_AXIS),
]

MATH_CODE_METRICS = [
    ("GSM8k accuracy", "eval/GSM8k/acc", EVAL_X_AXIS),
    ("MATH accuracy", "eval/MATH/acc", EVAL_X_AXIS),
    ("HumanEval pass rate", "dfm_eval/humaneval/verify_sanitized/accuracy", DFM_EVAL_X_AXIS),
]

MATH_CODE_EUROEVAL_METRICS = [
    ("EuroEval BFCL-v2 tool-calling accuracy", "euroeval/en/tool-calling/bfcl-v2/tool_calling_accuracy", EUROEVAL_X_AXIS),
]

TRAINING_METRICS = [
    ("Training loss", "train/loss"),
    ("Training accuracy", "train/accuracy"),
    ("Training exact accuracy", "train/exact_accuracy"),
    ("Learning rate", "train/lr"),
    ("BP steps", "bp_steps"),
]

def build_headline_average_metrics(prefix: str = HEADLINE_AVG_PREFIX) -> dict[str, list[tuple[str, str, str]] | tuple[str, str, str]]:
    prefix = prefix.rstrip("/")
    x_axis = f"{prefix}/epoch"
    return {
        "Headline Averages": [
        (
            "Overall headline average",
            f"{prefix}/overall",
            x_axis,
        ),
        (
            "Danish headline average",
            f"{prefix}/danish",
            x_axis,
        ),
        (
            "English headline average",
            f"{prefix}/english",
            x_axis,
        ),
        (
            "Math & Code headline average",
            f"{prefix}/math_code",
            x_axis,
        ),
    ],
    "Danish Headline Metrics": (
        "Danish headline average",
        f"{prefix}/danish",
        x_axis,
    ),
    "English Headline Metrics": (
        "English headline average",
        f"{prefix}/english",
        x_axis,
    ),
    "Math & Code Headline Metrics": (
        "Math & Code headline average",
        f"{prefix}/math_code",
        x_axis,
    ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entity", default=ENTITY)
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--name", default=WORKSPACE_NAME)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("logs/wandb_workspace_specs/dfm5_headline_metrics.json"),
    )
    parser.add_argument(
        "--headline-avg-prefix",
        default=HEADLINE_AVG_PREFIX,
        help="Average metric namespace to use in headline panels.",
    )
    return parser.parse_args()


def line_panel(title: str, metric: str, x_axis: str, title_x: str) -> wr.LinePlot:
    return wr.LinePlot(
        title=title,
        x=x_axis,
        y=[metric],
        title_x=title_x,
        legend_fields=["run:displayName"],
        smoothing_type="none",
        max_runs_to_show=MAX_RUNS_TO_SHOW,
        xaxis_format="number",
    )


def scalar_panel(title: str, metric: str) -> wr.ScalarChart:
    return wr.ScalarChart(
        title=title,
        metric=metric,
        groupby_aggfunc="max",
    )


def eval_section(
    name: str,
    metrics: list[tuple[str, str, str]],
    headline_average_metrics: dict[str, list[tuple[str, str, str]] | tuple[str, str, str]],
) -> ws.Section:
    panels = []
    if name in headline_average_metrics:
        metric = headline_average_metrics[name]
        if isinstance(metric, tuple):
            panels.append(line_panel(*metric, title_x="epoch"))
    panels.extend(line_panel(title, metric, x_axis, "epoch") for title, metric, x_axis in metrics)
    return ws.Section(
        name=name,
        panels=panels,
        is_open=True,
        layout_settings=ws.SectionLayoutSettings(columns=3, rows=4),
    )


def headline_average_section(
    headline_average_metrics: dict[str, list[tuple[str, str, str]] | tuple[str, str, str]],
) -> ws.Section:
    panels = [
        line_panel(title, metric, x_axis, "epoch")
        for title, metric, x_axis in headline_average_metrics["Headline Averages"]
    ]
    return ws.Section(
        name="Headline Averages",
        panels=panels,
        is_open=True,
        layout_settings=ws.SectionLayoutSettings(columns=2, rows=2),
    )


def training_section() -> ws.Section:
    panels: list[wr.LinePlot | wr.ScalarChart] = [
        line_panel(title, metric, TRAIN_X_AXIS, "step") for title, metric in TRAINING_METRICS
    ]
    panels.extend(
        [
            scalar_panel("Configured LR", "config:lr"),
            scalar_panel("Global batch size", "config:global_batch_size"),
            scalar_panel("Epochs", "config:epochs"),
            scalar_panel("Model size", "config:arch.n_layers"),
        ]
    )
    return ws.Section(
        name="Training Metrics & Params",
        panels=panels,
        is_open=True,
        layout_settings=ws.SectionLayoutSettings(columns=3, rows=3),
    )


def main() -> None:
    args = parse_args()
    headline_average_metrics = build_headline_average_metrics(args.headline_avg_prefix)
    danish = [(title, metric, DFM_EVAL_X_AXIS) for title, metric in DANISH_METRICS]
    danish.extend(DANISH_EUROEVAL_METRICS)
    english = [*ENGLISH_METRICS, *ENGLISH_EUROEVAL_METRICS]
    math_code = [*MATH_CODE_METRICS, *MATH_CODE_EUROEVAL_METRICS]
    workspace = ws.Workspace(
        entity=args.entity,
        project=args.project,
        name=args.name,
        sections=[
            headline_average_section(headline_average_metrics),
            eval_section("Danish Headline Metrics", danish, headline_average_metrics),
            eval_section("English Headline Metrics", english, headline_average_metrics),
            eval_section("Math & Code Headline Metrics", math_code, headline_average_metrics),
            training_section(),
        ],
        settings=ws.WorkspaceSettings(
            x_axis=TRAIN_X_AXIS,
            smoothing_type="none",
            max_runs=MAX_RUNS_TO_SHOW,
            remove_legends_from_panels=False,
            tooltip_number_of_runs="all_runs",
        ),
        runset_settings=ws.RunsetSettings(
            order=[expr.Ordering(expr.Metric("CreatedTimestamp"), ascending=True)],
            pinned_columns=[
                "run:displayName",
                "summary:eval/last_epoch",
                "summary:dfm_eval/last_epoch",
                "summary:euroeval/last_epoch",
                "config:data",
                "config:arch",
                "config:lr",
                "config:global_batch_size",
                "config:epochs",
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

    manifest = {
        "entity": args.entity,
        "project": args.project,
        "name": args.name,
        "url": workspace.url,
        "sections": {
            "Headline Averages": headline_average_metrics["Headline Averages"],
            "Danish Headline Metrics": danish,
            "English Headline Metrics": english,
            "Math & Code Headline Metrics": math_code,
            "Training Metrics & Params": TRAINING_METRICS,
        },
        "headline_average_metrics": headline_average_metrics,
        "x_axes": {
            "standard_eval": EVAL_X_AXIS,
            "dfm_eval": DFM_EVAL_X_AXIS,
            "euroeval": EUROEVAL_X_AXIS,
            "headline_avg": f"{args.headline_avg_prefix.rstrip('/')}/epoch",
            "training": TRAIN_X_AXIS,
        },
        "max_runs_to_show": MAX_RUNS_TO_SHOW,
        "run_feed_page_size": MAX_RUNS_TO_SHOW,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"View saved: {workspace.url}")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
