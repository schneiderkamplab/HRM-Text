#!/usr/bin/env python3
"""Render English/Danish nested-bubble PNGs with literal parameter-area scaling."""

from __future__ import annotations

import colorsys
import csv
import math
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont


from ._common import _SOURCE as _SOURCE, _OUTPUT_ROOT, _font

__all__ = []
_OUTPUT_DIR = _OUTPUT_ROOT / "english_danish_size_bubbles"
_AVERAGE_OUTPUT_DIR = _OUTPUT_ROOT / "danish_english_math_average_size_bubbles"

_ESTABLISHED = {
    "Mistral-Small-4-119B": "#A6CEE3",
    "Mistral-Large-2411": "#B2DF8A",
    "NorMistral-11B": "#CAB2D6",
    "Mixtral-8x22B": "#8DD3C7",
    "Munin-Qwen3.5-9B": "#FFFFB3",
    "Munin-Mistral3-8B": "#BEBADA",
    "Apertus-v1.5-70B": "#FB8072",
    "Apertus-70B": "#80B1D3",
    "HRM-Mimir-v1": "#D32F2F",
    "Mixtral-8x7B": "#FDB462",
    "Qwen3.5-4B": "#B3DE69",
    "HRM-Text-1B": "#FCCDE5",
    "Mistral-Small-3.2": "#4169E1",
    "EuroLLM-22B": "#BC80BD",
    "Apertus-v1.5-8B": "#CCEBC5",
    "EuroLLM-9B": "#FFED6F",
    "Apertus-8B": "#B3E2CD",
    "Devstral-2": "#FDCDAC",
    "Munin-Apertus-8b": "#CBD5E8",
    "Ministral-3-14B": "#F4CAE4",
    "Ministral-3-8B": "#E6F5C9",
    "Ministral-3-3B": "#F1E2CC",
    "Gemma-4-E2B-it": "#FBB4AE",
    "Gemma-4-E2B-it-thinking": "#B3CDE3",
    "SmolLM3-3B": "#DECBE4",
    "Mistral-Nemo": "#D5AAFF",
}



def _read_rows() -> list[dict[str, float | str | int]]:
    def optional_float(value: str) -> float | None:
        return float(value) if value.strip() else None

    with _SOURCE.open(newline="", encoding="utf-8") as handle:
        return [
            {
                "rank": int(row["rank"]),
                "model": row["model"],
                "total": optional_float(row["params_B"]),
                "noemb": optional_float(row["noemb_B"]),
                "english": float(row["english"]),
                "danish": float(row["danish"]),
                "math_code": float(row["math_code"]),
                "english_math_average": (float(row["english"]) + float(row["math_code"])) / 2,
                "overall": float(row["overall"]),
            }
            for row in csv.DictReader(handle)
        ]


def _filtered_union(rows: list[dict[str, float | str | int]]) -> list[dict[str, float | str | int]]:
    def eligible(row: dict[str, float | str | int]) -> bool:
        model = str(row["model"])
        return not model.casefold().startswith(("qwen", "gemma", "smollm3", "munin")) and model != "CohereLabs-tiny-aya-global"

    eligible_rows = [row for row in rows if eligible(row)]
    union: set[str] = set()
    for metric in ("english", "danish", "math_code", "overall"):
        union.update(str(row["model"]) for row in sorted(eligible_rows, key=lambda row: (-float(row[metric]), int(row["rank"])))[:10])
    return [row for row in eligible_rows if str(row["model"]) in union]


def _fallback_colour(index: int) -> str:
    hue = (0.08 + index * 0.61803398875) % 1.0
    saturation = 0.48 + 0.10 * (index % 3)
    lightness = 0.60 + 0.06 * (index % 2)
    red, green, blue = colorsys.hls_to_rgb(hue, lightness, saturation)
    return f"#{round(red * 255):02X}{round(green * 255):02X}{round(blue * 255):02X}"


def _colour_map(rows: list[dict[str, float | str | int]]) -> dict[str, str]:
    result = dict(_ESTABLISHED)
    missing = [str(row["model"]) for row in rows if str(row["model"]) not in result]
    for index, model in enumerate(missing):
        result[model] = _fallback_colour(index)
    return result


def _pareto(rows: list[dict[str, float | str | int]], x_metric: str, y_metric: str) -> list[dict[str, float | str | int]]:
    frontier = []
    for row in rows:
        dominated = any(
            float(other[x_metric]) >= float(row[x_metric])
            and float(other[y_metric]) >= float(row[y_metric])
            and (float(other[x_metric]) > float(row[x_metric]) or float(other[y_metric]) > float(row[y_metric]))
            for other in rows
        )
        if not dominated:
            frontier.append(row)
    return sorted(frontier, key=lambda row: float(row[x_metric]))


def _ticks(lower: float, upper: float, step: int = 5) -> list[int]:
    start = math.floor(lower / step) * step
    end = math.ceil(upper / step) * step
    return list(range(start, end + 1, step))


def _overlap_area(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def _place_labels(
    points: list[dict[str, float | str | int]],
    draw: ImageDraw.ImageDraw,
    font: ImageFont.FreeTypeFont,
    bounds: tuple[int, int, int, int],
) -> list[dict[str, object]]:
    left, top, right, bottom = bounds
    placed: list[dict[str, object]] = []
    priority = sorted(
        points,
        key=lambda point: (
            str(point["model"]) not in {"HRM-Mimir-v1", "HRM-Text-1B"},
            not bool(point["frontier"]),
            -float(point["r"]),
        ),
    )
    angles = [0, math.pi, -math.pi / 2, math.pi / 2, -math.pi / 4, math.pi / 4, -3 * math.pi / 4, 3 * math.pi / 4]
    for point in priority:
        text = str(point["model"])
        box = draw.textbbox((0, 0), text, font=font, stroke_width=2)
        width, height = box[2] - box[0], box[3] - box[1]
        candidates: list[tuple[float, tuple[float, float, float, float]]] = []
        for ring in range(9):
            distance = float(point["r"]) + 10 + ring * (height + 5)
            for angle in angles:
                cx = float(point["x"]) + math.cos(angle) * distance
                cy = float(point["y"]) + math.sin(angle) * distance
                rect = (cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2)
                if rect[0] < left or rect[2] > right or rect[1] < top or rect[3] > bottom:
                    continue
                label_overlap = sum(_overlap_area(rect, item["rect"]) for item in placed)  # type: ignore[arg-type]
                bubble_penalty = 0.0
                for other in points:
                    nearest_x = min(max(float(other["x"]), rect[0]), rect[2])
                    nearest_y = min(max(float(other["y"]), rect[1]), rect[3])
                    if math.hypot(float(other["x"]) - nearest_x, float(other["y"]) - nearest_y) < float(other["r"]) + 3:
                        bubble_penalty += 1.0
                score = label_overlap * 10000 + bubble_penalty * 2500 + ring * 8
                candidates.append((score, rect))
                if score == 0:
                    break
            if candidates and candidates[-1][0] == 0:
                break
        if not candidates:
            rect = (left, top, left + width, top + height)
        else:
            rect = min(candidates, key=lambda candidate: candidate[0])[1]
        placed.append({"point": point, "text": text, "rect": rect})
    return placed


def _draw_dashed_line(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], fill: str, width: int, dash: int = 12) -> None:
    for first, second in zip(points, points[1:]):
        x1, y1 = first
        x2, y2 = second
        length = math.hypot(x2 - x1, y2 - y1)
        if length == 0:
            continue
        ux, uy = (x2 - x1) / length, (y2 - y1) / length
        position = 0.0
        while position < length:
            end = min(length, position + dash)
            draw.line((x1 + ux * position, y1 + uy * position, x1 + ux * end, y1 + uy * end), fill=fill, width=width)
            position += dash * 1.7


def _render(
    rows: list[dict[str, float | str | int]],
    filename: str,
    title: str,
    width: int,
    height: int,
    max_radius: int,
    *,
    x_metric: str = "english",
    x_axis_label: str = "English score",
    y_metric: str = "danish",
    y_axis_label: str = "Danish score",
    frontier_label: str = "English–Danish Pareto frontier",
    output_dir: Path = _OUTPUT_DIR,
) -> None:
    colours = _colour_map(rows)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = _font(42, bold=True)
    legend_font = _font(23)
    axis_font = _font(27, bold=True)
    tick_font = _font(22)
    label_font = _font(24 if len(rows) > 20 else 28, bold=True)

    plot = (170, 190, width - 145, height - 150)
    plot_left, plot_top, plot_right, plot_bottom = plot
    plot_width, plot_height = plot_right - plot_left, plot_bottom - plot_top

    x_values = [float(row[x_metric]) for row in rows]
    y_values = [float(row[y_metric]) for row in rows]
    x_span, y_span = max(x_values) - min(x_values), max(y_values) - min(y_values)
    x_ticks = _ticks(min(x_values) - x_span * 0.07, max(x_values) + x_span * 0.07)
    y_ticks = _ticks(min(y_values) - y_span * 0.08, max(y_values) + y_span * 0.08)
    x_min, x_max = x_ticks[0], x_ticks[-1]
    y_min, y_max = y_ticks[0], y_ticks[-1]

    x = lambda value: plot_left + (value - x_min) / (x_max - x_min) * plot_width
    y = lambda value: plot_bottom - (value - y_min) / (y_max - y_min) * plot_height

    title_box = draw.textbbox((0, 0), title, font=title_font)
    draw.text(((width - (title_box[2] - title_box[0])) / 2, 28), title, fill="#17324D", font=title_font)

    legend_y = 108
    draw.ellipse((65, legend_y - 18, 101, legend_y + 18), fill="#8DD3C744", outline="#5CAFA4", width=2)
    draw.ellipse((75, legend_y - 8, 91, legend_y + 8), fill="#8DD3C7", outline="white", width=1)
    draw.text((114, legend_y - 14), "Outer area = total params; inner area = non-embedding; area scale is linear", fill="#425466", font=legend_font)
    frontier_box = draw.textbbox((0, 0), frontier_label, font=legend_font)
    frontier_text_width = frontier_box[2] - frontier_box[0]
    frontier_text_x = width - 65 - frontier_text_width
    _draw_dashed_line(draw, [(frontier_text_x - 90, legend_y), (frontier_text_x - 20, legend_y)], "#17324D", 3)
    draw.text((frontier_text_x, legend_y - 14), frontier_label, fill="#425466", font=legend_font)
    missing_size_count = sum(row["total"] is None or row["noemb"] is None for row in rows)
    if missing_size_count:
        missing_y = 150
        draw.ellipse((66, missing_y - 9, 84, missing_y + 9), outline="#526579", width=2)
        draw.line((69, missing_y - 6, 81, missing_y + 6), fill="#526579", width=2)
        draw.line((69, missing_y + 6, 81, missing_y - 6), fill="#526579", width=2)
        draw.text((96, missing_y - 13), f"Size unavailable: hollow × marker ({missing_size_count})", fill="#425466", font=legend_font)

    for tick in x_ticks:
        px = x(tick)
        draw.line((px, plot_top, px, plot_bottom), fill="#D9E2EC", width=2)
        text = str(tick)
        text_box = draw.textbbox((0, 0), text, font=tick_font)
        draw.text((px - (text_box[2] - text_box[0]) / 2, plot_bottom + 16), text, fill="#526579", font=tick_font)
    for tick in y_ticks:
        py = y(tick)
        draw.line((plot_left, py, plot_right, py), fill="#D9E2EC", width=2)
        text = str(tick)
        text_box = draw.textbbox((0, 0), text, font=tick_font)
        draw.text((plot_left - 18 - (text_box[2] - text_box[0]), py - (text_box[3] - text_box[1]) / 2), text, fill="#526579", font=tick_font)
    draw.rectangle(plot, outline="#7C8C9E", width=2)

    x_label = x_axis_label
    x_box = draw.textbbox((0, 0), x_label, font=axis_font)
    draw.text(((plot_left + plot_right - (x_box[2] - x_box[0])) / 2, height - 64), x_label, fill="#17324D", font=axis_font)
    y_text = y_axis_label
    y_text_box = draw.textbbox((0, 0), y_text, font=axis_font)
    y_label = Image.new("RGBA", (y_text_box[2] - y_text_box[0] + 20, y_text_box[3] - y_text_box[1] + 20), (255, 255, 255, 0))
    y_draw = ImageDraw.Draw(y_label)
    y_draw.text((10, 10 - y_text_box[1]), y_text, fill="#17324D", font=axis_font)
    rotated = y_label.rotate(90, expand=True)
    image.paste(rotated, (30, round((height - rotated.height) / 2)), rotated)
    draw = ImageDraw.Draw(image)

    frontier = _pareto(rows, x_metric, y_metric)
    _draw_dashed_line(draw, [(x(float(row[x_metric])), y(float(row[y_metric]))) for row in frontier], "#17324D", 4, dash=18)
    frontier_names = {str(row["model"]) for row in frontier}

    known_size_rows = [row for row in rows if row["total"] is not None and row["noemb"] is not None]
    if not known_size_rows:
        raise RuntimeError("No model-size values are available for this chart")
    largest = max(float(row["total"]) for row in known_size_rows)
    points: list[dict[str, float | str | int]] = []
    bubble_layer = Image.new("RGBA", image.size, (255, 255, 255, 0))
    bubble_draw = ImageDraw.Draw(bubble_layer)
    for row in sorted(rows, key=lambda item: float(item["total"]) if item["total"] is not None else -1.0, reverse=True):
        px, py = x(float(row[x_metric])), y(float(row[y_metric]))
        colour = colours[str(row["model"])]
        rgb = ImageColor.getrgb(colour)
        if row["total"] is None or row["noemb"] is None:
            radius = 10.0
            bubble_draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=(255, 255, 255, 0), outline=(*rgb, 255), width=3)
            bubble_draw.line((px - 6, py - 6, px + 6, py + 6), fill=(*rgb, 255), width=3)
            bubble_draw.line((px - 6, py + 6, px + 6, py - 6), fill=(*rgb, 255), width=3)
        else:
            radius = max_radius * math.sqrt(float(row["total"]) / largest)
            inner_radius = radius * math.sqrt(float(row["noemb"]) / float(row["total"]))
            bubble_draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=(*rgb, 76), outline=(*rgb, 255), width=3 if str(row["model"]) in frontier_names else 2)
            bubble_draw.ellipse((px - inner_radius, py - inner_radius, px + inner_radius, py + inner_radius), fill=(*rgb, 225), outline=(255, 255, 255, 235), width=2)
        points.append({**row, "x": px, "y": py, "r": radius, "frontier": str(row["model"]) in frontier_names})
    image = Image.alpha_composite(image.convert("RGBA"), bubble_layer).convert("RGB")
    draw = ImageDraw.Draw(image)

    labels = _place_labels(points, draw, label_font, (15, plot_top + 2, width - 15, plot_bottom - 2))
    for item in labels:
        point = item["point"]
        rect = item["rect"]
        cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2  # type: ignore[index]
        px, py, radius = float(point["x"]), float(point["y"]), float(point["r"])  # type: ignore[index]
        dx, dy = cx - px, cy - py
        distance = max(1.0, math.hypot(dx, dy))
        draw.line((px + dx / distance * radius, py + dy / distance * radius, cx, cy), fill="#9AA9B8", width=2)
    for item in labels:
        rect = item["rect"]
        draw.text((rect[0], rect[1]), str(item["text"]), fill="#17324D", font=label_font, stroke_width=4, stroke_fill="white")  # type: ignore[index]

    output_dir.mkdir(parents=True, exist_ok=True)
    image.save(output_dir / filename, optimize=True)


def _main() -> None:
    rows = _read_rows()
    filtered = _filtered_union(rows)
    top_overall = sorted(rows, key=lambda row: (-float(row["overall"]), int(row["rank"])))[:10]
    if len(filtered) != 16:
        raise RuntimeError(f"Expected 16 filtered union models, found {len(filtered)}")
    _render(filtered, "01_english_danish_size_16_models.png", "English and Danish performance versus model size — filtered 16", 2400, 1600, 58)
    _render(rows, "02_english_danish_size_all_50_models.png", "English and Danish performance versus model size — all 50 models", 3200, 2300, 72)
    _render(top_overall, "03_english_danish_size_top10_overall.png", "English and Danish performance versus model size — top 10 overall", 2400, 1600, 58)
    average_options = {
        "x_metric": "english_math_average",
        "x_axis_label": "Average of English and Math & Code scores",
        "frontier_label": "Danish–English/Math average Pareto frontier",
        "output_dir": _AVERAGE_OUTPUT_DIR,
    }
    _render(filtered, "01_danish_vs_english_math_average_size_16_models.png", "Danish versus average English and Math & Code performance — filtered 16", 2400, 1600, 58, **average_options)
    _render(rows, "02_danish_vs_english_math_average_size_all_50_models.png", "Danish versus average English and Math & Code performance — all 50 models", 3200, 2300, 72, **average_options)
    _render(top_overall, "03_danish_vs_english_math_average_size_top10_overall.png", "Danish versus average English and Math & Code performance — top 10 overall", 2400, 1600, 58, **average_options)


if __name__ == "__main__":
    _main()
