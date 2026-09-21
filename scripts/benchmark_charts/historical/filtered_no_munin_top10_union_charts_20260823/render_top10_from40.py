#!/usr/bin/env python3
"""Render exact 40-baseline PNG variants from the filtered benchmark CSV."""

from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "summary_by_category.csv"
OUTPUT_DIR = Path(__file__).resolve().parent / "top10_from_40"
WIDTH, HEIGHT = 1323, 888
SCALE = 2

FONT_REGULAR = Path("/opt/X11/share/system_fonts/Supplemental/Arial.ttf")
FONT_BOLD = Path("/opt/X11/share/system_fonts/Supplemental/Arial Bold.ttf")

PALETTE = {
    "Mixtral-8x22B": "#8DD3C7",
    "Apertus-v1.5-70B": "#FB8072",
    "Apertus-70B": "#80B1D3",
    "HRM-Mimir-v1": "#D32F2F",
    "Mixtral-8x7B": "#FDB462",
    "HRM-Text-1B": "#FCCDE5",
    "Mistral-Small-3.2": "#4169E1",
    "EuroLLM-22B": "#BC80BD",
    "Apertus-v1.5-8B": "#CCEBC5",
    "EuroLLM-9B": "#FFED6F",
    "Apertus-8B": "#B3E2CD",
    "Devstral-2": "#FDCDAC",
    "Ministral-3-14B": "#F4CAE4",
    "Ministral-3-8B": "#E6F5C9",
    "Ministral-3-3B": "#F1E2CC",
    "Mistral-Nemo": "#D5AAFF",
}

CHARTS = (
    ("english", "English", 100, 5, "01_english_top10_from40.png"),
    ("danish", "Danish", 60, 2, "02_danish_top10_from40.png"),
    ("math_code", "Math & Code", 100, 5, "03_math_and_code_top10_from40.png"),
    ("overall", "Overall", 70, 2, "04_overall_top10_from40.png"),
)


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size * SCALE)


def _eligible(model: str) -> bool:
    lowered = model.casefold()
    return not lowered.startswith(("qwen", "gemma", "smollm3", "munin")) and model != "CohereLabs-tiny-aya-global"


def _load_rows() -> list[dict[str, str]]:
    with SOURCE.open(newline="", encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle) if _eligible(row["model"])]


def _draw_dashed_vertical(draw: ImageDraw.ImageDraw, x: int, top: int, bottom: int) -> None:
    dash, gap = 8 * SCALE, 7 * SCALE
    y = top
    while y < bottom:
        draw.line((x, y, x, min(y + dash, bottom)), fill="#D9E2EC", width=SCALE)
        y += dash + gap


def _render(rows: list[dict[str, str]], key: str, label: str, maximum: int, step: int, filename: str) -> None:
    ranked = sorted(rows, key=lambda row: (-float(row[key]), int(row["rank"])))[:10]
    image = Image.new("RGB", (WIDTH * SCALE, HEIGHT * SCALE), "white")
    draw = ImageDraw.Draw(image)

    title_font = _font(24, bold=True)
    model_font = _font(18)
    value_font = _font(16, bold=True)
    tick_font = _font(15)
    axis_font = _font(17, bold=True)

    title = f"Top 10 — {label} — axis starts at 40"
    title_box = draw.textbbox((0, 0), title, font=title_font)
    draw.text(((WIDTH * SCALE - (title_box[2] - title_box[0])) / 2, 35 * SCALE), title, fill="#17324D", font=title_font)

    plot_left, plot_right = 350 * SCALE, 1240 * SCALE
    plot_top, plot_bottom = 120 * SCALE, 790 * SCALE
    plot_width = plot_right - plot_left
    minimum = 40

    for tick in range(minimum, maximum + 1, step):
        x = plot_left + round((tick - minimum) / (maximum - minimum) * plot_width)
        _draw_dashed_vertical(draw, x, plot_top, plot_bottom)
        tick_text = f"{tick:.1f}"
        box = draw.textbbox((0, 0), tick_text, font=tick_font)
        draw.text((x - (box[2] - box[0]) / 2, 805 * SCALE), tick_text, fill="#425466", font=tick_font)

    draw.line((plot_left, plot_bottom, plot_right, plot_bottom), fill="#6B7785", width=2 * SCALE)

    row_pitch = (plot_bottom - plot_top) / len(ranked)
    bar_height = 43 * SCALE
    for index, row in enumerate(ranked):
        score = float(row[key])
        center_y = plot_top + (index + 0.5) * row_pitch
        bar_top = round(center_y - bar_height / 2)
        bar_bottom = round(center_y + bar_height / 2)
        bar_right = plot_left + round((score - minimum) / (maximum - minimum) * plot_width)

        model = row["model"]
        model_box = draw.textbbox((0, 0), model, font=model_font)
        draw.text((plot_left - 18 * SCALE - (model_box[2] - model_box[0]), center_y - (model_box[3] - model_box[1]) / 2), model, fill="#243447", font=model_font)
        draw.rounded_rectangle((plot_left, bar_top, bar_right, bar_bottom), radius=4 * SCALE, fill=PALETTE[model])

        value = f"{score:.1f}"
        draw.text((bar_right + 9 * SCALE, center_y - 9 * SCALE), value, fill="#243447", font=value_font)

    axis_label = "Score"
    box = draw.textbbox((0, 0), axis_label, font=axis_font)
    draw.text(((plot_left + plot_right - (box[2] - box[0])) / 2, 850 * SCALE), axis_label, fill="#243447", font=axis_font)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS).save(OUTPUT_DIR / filename, optimize=True)


def main() -> None:
    rows = _load_rows()
    for chart in CHARTS:
        _render(rows, *chart)


if __name__ == "__main__":
    main()
