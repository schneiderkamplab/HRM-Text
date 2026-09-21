#!/usr/bin/env python3
"""Render European Danish-vs-English/Math size charts without Mistral actors."""

from __future__ import annotations



from . import _bubbles as bubble
from ._common import _OUTPUT_ROOT

__all__ = []
_OUTPUT_DIR = _OUTPUT_ROOT / "danish_english_math_size_european_no_mistral_20260825"

# Covers Mistral AI's named families and Mistral-derived models identified as
# such in this dataset (for example Munin-Mistral and NorMistral).
_MISTRAL_FAMILY_MARKERS = ("mistral", "ministral", "mixtral", "devstral", "codestral")
_NON_EUROPEAN_PREFIXES = ("qwen", "gemma")



def _is_mistral_family(model: str) -> bool:
    folded = model.casefold()
    return any(marker in folded for marker in _MISTRAL_FAMILY_MARKERS)


def _is_munin(model: str) -> bool:
    return model.casefold().startswith("munin-")


def _is_eligible(model: str) -> bool:
    folded = model.casefold()
    if _is_munin(model):
        return True
    return (
        not _is_mistral_family(model)
        and not folded.startswith(_NON_EUROPEAN_PREFIXES)
        and model != "CohereLabs-tiny-aya-global"
    )


def _top10_union(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    eligible = [
        row
        for row in rows
        if _is_eligible(str(row["model"]))
    ]
    selected: set[str] = set()
    for metric in ("english", "danish", "math_code", "overall"):
        ordered = sorted(
            eligible,
            key=lambda row: (-float(row[metric]), int(row["rank"])),
        )
        selected.update(str(row["model"]) for row in ordered[:10])
    return [row for row in eligible if str(row["model"]) in selected]


def _main() -> None:
    rows = bubble._read_rows()
    eligible = [row for row in rows if _is_eligible(str(row["model"]))]
    union = _top10_union(rows)
    top10 = sorted(
        eligible,
        key=lambda row: (-float(row["overall"]), int(row["rank"])),
    )[:10]

    options = {
        "x_metric": "english_math_average",
        "x_axis_label": "Average of English and Math & Code scores",
        "frontier_label": "Danish–English/Math average Pareto frontier",
        "output_dir": _OUTPUT_DIR,
    }
    union_count = len(union)
    all_count = len(eligible)
    bubble._render(
        union,
        f"01_danish_vs_english_math_average_size_top10_union_{union_count}_european.png",
        f"Danish versus average English and Math & Code — European top-10 union ({union_count})",
        2400,
        1600,
        58,
        **options,
    )
    bubble._render(
        eligible,
        f"02_danish_vs_english_math_average_size_all_{all_count}_european.png",
        f"Danish versus average English and Math & Code — all {all_count} eligible European models",
        3200,
        2300,
        72,
        **options,
    )
    bubble._render(
        top10,
        "03_danish_vs_english_math_average_size_top10_overall_european.png",
        "Danish versus average English and Math & Code — European top 10 overall",
        2400,
        1600,
        58,
        **options,
    )

    removed = [str(row["model"]) for row in rows if not _is_eligible(str(row["model"]))]
    retained_munin = [str(row["model"]) for row in rows if _is_munin(str(row["model"]))]
    print(f"Generated 3 PNGs; removed {len(removed)} ineligible models")
    print(f"Eligible population: {all_count}; recalculated top-10 union: {union_count}")
    print("Removed: " + ", ".join(removed))
    print("Retained Munin: " + ", ".join(retained_munin))
    print("Union: " + ", ".join(str(row["model"]) for row in union))
    print("Top 10 overall: " + ", ".join(str(row["model"]) for row in top10))


if __name__ == "__main__":
    _main()
