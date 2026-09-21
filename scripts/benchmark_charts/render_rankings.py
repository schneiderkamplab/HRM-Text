#!/usr/bin/env python3
"""Rebuild the complete benchmark PNG suite from the current category summary CSV."""

from __future__ import annotations

import math

from PIL import Image, ImageColor, ImageDraw


from . import _bubbles as bubble
from ._common import _OUTPUT_ROOT, _font

__all__ = []
_OUTPUT_DIR = _OUTPUT_ROOT / "benchmark_pngs_updated_20260825"




def _lighten(hex_colour: str, amount: float = 0.56) -> str:
    red, green, blue = ImageColor.getrgb(hex_colour)
    values = [round(channel + (255 - channel) * amount) for channel in (red, green, blue)]
    return f"#{values[0]:02X}{values[1]:02X}{values[2]:02X}"


def _nice_max(value: float, step: int) -> int:
    return max(step, math.ceil(value / step) * step)


def _draw_dashed_vertical(draw: ImageDraw.ImageDraw, x: float, top: float, bottom: float, colour: str = "#D9E2EC") -> None:
    y = top
    while y < bottom:
        draw.line((x, y, x, min(y + 8, bottom)), fill=colour, width=1)
        y += 15


def _score_limits(metric: str, rows: list[dict[str, object]], minimum: int) -> tuple[int, int, int]:
    highest = max(float(row[metric]) for row in rows)
    if metric in {"english", "math_code"}:
        maximum = 100
        step = 5
    elif metric == "danish":
        maximum = _nice_max(highest + 2, 10)
        step = 2 if minimum == 40 else 5
    else:
        maximum = _nice_max(highest + 2, 10)
        step = 2 if minimum == 40 else 5
    return minimum, maximum, step


def _render_bar_chart(
    rows: list[dict[str, object]],
    metric: str,
    title: str,
    filename: str,
    colours: dict[str, str],
    *,
    minimum: int = 0,
    width: int = 1323,
    height: int = 888,
) -> None:
    ordered = sorted(rows, key=lambda row: (-float(row[metric]), int(row["rank"])))
    axis_min, axis_max, tick_step = _score_limits(metric, ordered, minimum)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = _font(24, bold=True)
    model_font = _font(17 if len(rows) <= 10 else 15)
    value_font = _font(15, bold=True)
    tick_font = _font(14)
    axis_font = _font(16, bold=True)

    title_box = draw.textbbox((0, 0), title, font=title_font)
    draw.text(((width - (title_box[2] - title_box[0])) / 2, 27), title, fill="#17324D", font=title_font)

    plot_left, plot_right = 360, width - 84
    plot_top, plot_bottom = 105, height - 94
    plot_width = plot_right - plot_left
    for tick in range(axis_min, axis_max + 1, tick_step):
        x = plot_left + (tick - axis_min) / (axis_max - axis_min) * plot_width
        _draw_dashed_vertical(draw, x, plot_top, plot_bottom)
        text = f"{tick:.1f}"
        box = draw.textbbox((0, 0), text, font=tick_font)
        draw.text((x - (box[2] - box[0]) / 2, plot_bottom + 12), text, fill="#425466", font=tick_font)
    draw.line((plot_left, plot_bottom, plot_right, plot_bottom), fill="#6B7785", width=2)

    pitch = (plot_bottom - plot_top) / len(ordered)
    bar_height = min(44, max(24, pitch * 0.66))
    for index, row in enumerate(ordered):
        model = str(row["model"])
        value = float(row[metric])
        center_y = plot_top + (index + 0.5) * pitch
        top, bottom = center_y - bar_height / 2, center_y + bar_height / 2
        bar_right = plot_left + (value - axis_min) / (axis_max - axis_min) * plot_width
        model_box = draw.textbbox((0, 0), model, font=model_font)
        draw.text((plot_left - 18 - (model_box[2] - model_box[0]), center_y - (model_box[3] - model_box[1]) / 2), model, fill="#243447", font=model_font)
        draw.rounded_rectangle((plot_left, top, bar_right, bottom), radius=4, fill=colours[model])
        draw.text((bar_right + 8, center_y - 8), f"{value:.1f}", fill="#243447", font=value_font)

    label = "Score"
    label_box = draw.textbbox((0, 0), label, font=axis_font)
    draw.text(((plot_left + plot_right - (label_box[2] - label_box[0])) / 2, height - 34), label, fill="#243447", font=axis_font)
    image.save(_OUTPUT_DIR / filename, optimize=True)


def _render_union_chart(
    rows: list[dict[str, object]],
    metric: str,
    label: str,
    filename: str,
    colours: dict[str, str],
) -> None:
    count = len(rows)
    _render_bar_chart(
        rows,
        metric,
        f"Top-10 union ({count}) — {label}",
        filename,
        colours,
        minimum=0,
        width=1500,
        height=max(1200, 78 * count),
    )


def _render_size_chart(rows: list[dict[str, object]], filename: str, colours: dict[str, str]) -> None:
    known = [row for row in rows if row["total"] is not None and row["noemb"] is not None]
    missing = [str(row["model"]) for row in rows if row["total"] is None or row["noemb"] is None]
    ordered = sorted(known, key=lambda row: (-float(row["total"]), int(row["rank"])))
    width, height = 1500, max(1200, 78 * len(rows))
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font, model_font, value_font, tick_font, axis_font = _font(25, bold=True), _font(15), _font(14, bold=True), _font(14), _font(16, bold=True)
    title = f"Model size — filtered top-10 union ({len(rows)})"
    title_box = draw.textbbox((0, 0), title, font=title_font)
    draw.text(((width - (title_box[2] - title_box[0])) / 2, 26), title, fill="#17324D", font=title_font)
    if missing:
        note = f"Size unavailable and omitted: {', '.join(missing)}"
        note_box = draw.textbbox((0, 0), note, font=tick_font)
        draw.text(((width - (note_box[2] - note_box[0])) / 2, 72), note, fill="#7A4E00", font=tick_font)
    legend_y = 96
    draw.rectangle((width - 465, legend_y, width - 435, legend_y + 16), fill="#80B1D3")
    draw.text((width - 425, legend_y - 2), "Non-embedding", fill="#425466", font=tick_font)
    draw.rectangle((width - 245, legend_y, width - 215, legend_y + 16), fill="#CEE3F0")
    draw.text((width - 205, legend_y - 2), "Embedding", fill="#425466", font=tick_font)
    plot_left, plot_right, plot_top, plot_bottom = 390, width - 105, 130, height - 95
    maximum = _nice_max(max(float(row["total"]) for row in ordered) * 1.06, 20)
    for tick in range(0, maximum + 1, 20):
        x = plot_left + tick / maximum * (plot_right - plot_left)
        _draw_dashed_vertical(draw, x, plot_top, plot_bottom)
        box = draw.textbbox((0, 0), str(tick), font=tick_font)
        draw.text((x - (box[2] - box[0]) / 2, plot_bottom + 12), str(tick), fill="#425466", font=tick_font)
    draw.line((plot_left, plot_bottom, plot_right, plot_bottom), fill="#6B7785", width=2)
    pitch = (plot_bottom - plot_top) / len(ordered)
    bar_height = min(40, pitch * 0.62)
    for index, row in enumerate(ordered):
        model = str(row["model"])
        total, noemb = float(row["total"]), float(row["noemb"])
        center_y = plot_top + (index + 0.5) * pitch
        top, bottom = center_y - bar_height / 2, center_y + bar_height / 2
        noemb_right = plot_left + noemb / maximum * (plot_right - plot_left)
        total_right = plot_left + total / maximum * (plot_right - plot_left)
        model_box = draw.textbbox((0, 0), model, font=model_font)
        draw.text((plot_left - 18 - (model_box[2] - model_box[0]), center_y - (model_box[3] - model_box[1]) / 2), model, fill="#243447", font=model_font)
        draw.rectangle((plot_left, top, noemb_right, bottom), fill=colours[model])
        draw.rectangle((noemb_right, top, total_right, bottom), fill=_lighten(colours[model]))
        draw.text((total_right + 8, center_y - 7), f"{total:.2f}B", fill="#243447", font=value_font)
    axis = "Parameters (billions)"
    axis_box = draw.textbbox((0, 0), axis, font=axis_font)
    draw.text(((plot_left + plot_right - (axis_box[2] - axis_box[0])) / 2, height - 36), axis, fill="#243447", font=axis_font)
    image.save(_OUTPUT_DIR / filename, optimize=True)


def _render_efficiency_chart(rows: list[dict[str, object]], filename: str, colours: dict[str, str]) -> None:
    known = [row for row in rows if row["noemb"] is not None]
    missing = [str(row["model"]) for row in rows if row["noemb"] is None]
    enriched = [{**row, "efficiency": float(row["overall"]) / float(row["noemb"])} for row in known]
    ordered = sorted(enriched, key=lambda row: (-float(row["efficiency"]), int(row["rank"])))
    width, height = 1500, max(1200, 78 * len(rows))
    maximum = _nice_max(max(float(row["efficiency"]) for row in ordered) * 1.08, 10)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font, model_font, value_font, tick_font, axis_font = _font(25, bold=True), _font(15), _font(14, bold=True), _font(14), _font(16, bold=True)
    title = f"Overall performance per non-embedding billion parameters — union ({len(rows)})"
    box = draw.textbbox((0, 0), title, font=title_font)
    draw.text(((width - (box[2] - box[0])) / 2, 28), title, fill="#17324D", font=title_font)
    if missing:
        note = f"Non-embedding size unavailable and omitted: {', '.join(missing)}"
        note_box = draw.textbbox((0, 0), note, font=tick_font)
        draw.text(((width - (note_box[2] - note_box[0])) / 2, 68), note, fill="#7A4E00", font=tick_font)
    plot_left, plot_right, plot_top, plot_bottom = 390, width - 105, 105, height - 95
    for tick in range(0, maximum + 1, 10):
        x = plot_left + tick / maximum * (plot_right - plot_left)
        _draw_dashed_vertical(draw, x, plot_top, plot_bottom)
        tick_box = draw.textbbox((0, 0), str(tick), font=tick_font)
        draw.text((x - (tick_box[2] - tick_box[0]) / 2, plot_bottom + 12), str(tick), fill="#425466", font=tick_font)
    draw.line((plot_left, plot_bottom, plot_right, plot_bottom), fill="#6B7785", width=2)
    pitch = (plot_bottom - plot_top) / len(ordered)
    bar_height = min(40, pitch * 0.62)
    for index, row in enumerate(ordered):
        model, value = str(row["model"]), float(row["efficiency"])
        center_y = plot_top + (index + 0.5) * pitch
        right = plot_left + value / maximum * (plot_right - plot_left)
        model_box = draw.textbbox((0, 0), model, font=model_font)
        draw.text((plot_left - 18 - (model_box[2] - model_box[0]), center_y - (model_box[3] - model_box[1]) / 2), model, fill="#243447", font=model_font)
        draw.rounded_rectangle((plot_left, center_y - bar_height / 2, right, center_y + bar_height / 2), radius=4, fill=colours[model])
        draw.text((right + 8, center_y - 7), f"{value:.2f}", fill="#243447", font=value_font)
    axis = "Overall score / non-embedding B parameters"
    axis_box = draw.textbbox((0, 0), axis, font=axis_font)
    draw.text(((plot_left + plot_right - (axis_box[2] - axis_box[0])) / 2, height - 36), axis, fill="#243447", font=axis_font)
    image.save(_OUTPUT_DIR / filename, optimize=True)


def _main() -> None:
    rows = bubble._read_rows()
    if not rows:
        raise RuntimeError("The source CSV contains no rows")
    filtered = bubble._filtered_union(rows)
    top_overall = sorted(rows, key=lambda row: (-float(row["overall"]), int(row["rank"])))[:10]
    colours = bubble._colour_map(rows)
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    metrics = (
        ("english", "English", "english"),
        ("danish", "Danish", "danish"),
        ("math_code", "Math & Code", "math_and_code"),
        ("overall", "Overall", "overall"),
    )
    eligible = [
        row for row in rows
        if not str(row["model"]).casefold().startswith(("qwen", "gemma", "smollm3", "munin"))
        and str(row["model"]) != "CohereLabs-tiny-aya-global"
    ]
    for index, (metric, label, slug) in enumerate(metrics, 1):
        top10 = sorted(eligible, key=lambda row: (-float(row[metric]), int(row["rank"])))[:10]
        _render_bar_chart(top10, metric, f"Top 10 — {label}", f"{index:02d}_{slug}_top10.png", colours)

    union_count = len(filtered)
    _render_size_chart(filtered, f"05_size_{union_count}_models.png", colours)
    _render_efficiency_chart(filtered, f"06_overall_per_noemb_{union_count}_models.png", colours)
    for offset, (metric, label, slug) in enumerate(metrics, 7):
        _render_union_chart(filtered, metric, label, f"{offset:02d}_{slug}_all{union_count}.png", colours)

    for offset, (metric, label, slug) in enumerate(metrics, 11):
        top10 = sorted(eligible, key=lambda row: (-float(row[metric]), int(row["rank"])))[:10]
        _render_bar_chart(top10, metric, f"Top 10 — {label} — axis starts at 40", f"{offset:02d}_{slug}_top10_from40.png", colours, minimum=40)

    bubble._render(filtered, f"15_english_danish_size_{union_count}_models.png", f"English and Danish performance versus model size — filtered {union_count}", 2400, 1600, 58, output_dir=_OUTPUT_DIR)
    bubble._render(rows, f"16_english_danish_size_all_{len(rows)}_models.png", f"English and Danish performance versus model size — all {len(rows)} models", 3200, 2300, 72, output_dir=_OUTPUT_DIR)
    bubble._render(top_overall, "17_english_danish_size_top10_overall.png", "English and Danish performance versus model size — top 10 overall", 2400, 1600, 58, output_dir=_OUTPUT_DIR)

    average_options = {
        "x_metric": "english_math_average",
        "x_axis_label": "Average of English and Math & Code scores",
        "frontier_label": "Danish–English/Math average Pareto frontier",
        "output_dir": _OUTPUT_DIR,
    }
    bubble._render(filtered, f"18_danish_vs_english_math_average_size_{union_count}_models.png", f"Danish versus average English and Math & Code performance — filtered {union_count}", 2400, 1600, 58, **average_options)
    bubble._render(rows, f"19_danish_vs_english_math_average_size_all_{len(rows)}_models.png", f"Danish versus average English and Math & Code performance — all {len(rows)} models", 3200, 2300, 72, **average_options)
    bubble._render(top_overall, "20_danish_vs_english_math_average_size_top10_overall.png", "Danish versus average English and Math & Code performance — top 10 overall", 2400, 1600, 58, **average_options)

    pngs = sorted(_OUTPUT_DIR.glob("*.png"))
    if len(pngs) != 20:
        raise RuntimeError(f"Expected 20 PNGs, found {len(pngs)}")
    print(f"Generated {len(pngs)} PNGs from {len(rows)} models; filtered union: {union_count}")
    for png in pngs:
        print(png.name)


if __name__ == "__main__":
    _main()
