---
type: Runbook
title: Benchmark Charts
description: Benchmark chart definitions, preserved builders, and reproduction from the category-score snapshot.
tags: [evaluation, benchmarks, charts]
status: stable
last_updated: 2026-09-21
confidence: high
---
# Benchmark Charts

## Tracked reproduction — 2026-09-21

The 51-model `summary_by_category.csv` snapshot and builders are now tracked.
See [the script README](../../scripts/benchmark_charts/README.md) for portable
commands and dependencies. The current pipeline generates the 20-chart August 25
refresh and the three European/no-Mistral charts, retaining all Munin models.
This reproduces charts from the recorded scores, not the underlying evaluations.

**Superseded source locations:** Commands below record historical runs from
ignored `outputs/` files and a machine-specific runtime. Use the tracked tools
for new runs. Earlier 50-model counts and visual checks describe their dated
runs, not the current 51-row snapshot. The original spreadsheet builders and
40-baseline renderer are retained as historical source; their original input
snapshot and spreadsheet runtime are not bundled.

Validation on 2026-09-21: both tracked renderers generated all 23 expected PNGs
with Pillow 11.3.0 and the original Arial fonts. All 23 were byte-identical to
fresh runs of the original scripts under the same runtime. Against previously
saved August outputs, 22 had identical pixels; the efficiency plot differed
only along a one-pixel-wide bar edge, also present in the original-script rerun.
The wiki validator passed with zero errors and warnings. Historical spreadsheet
builders were archived, not re-executed.

## Historical chart record — August 2026

## Current Chart Set

The workbook and PNG exports in `outputs/summary_by_category_charts_20260823/` contain six horizontal bar-chart rankings:

- English score
- Danish score
- Math & Code score
- Overall score
- Model size in billions of parameters
- Overall score per billion non-embedding parameters

All rankings are displayed highest-first. Non-Mimir models use blue bars; `HRM-Mimir-v1` uses red bars.

## Metric Definitions

- Efficiency is calculated as `overall / noemb_B` without further scaling.
- The size chart is stacked as `noemb_B + (params_B - noemb_B)`, so the full bar equals `params_B` and the lighter segment shows embedding parameters.
- The size chart uses dark/light blue for non-Mimir no-embedding/embedding segments and dark/light red for the corresponding Mimir segments.

## Reproduction

Run from `outputs/summary_by_category_charts_20260823/` with the bundled spreadsheet runtime:

```bash
/Users/petersk/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node build_charts.mjs
```

The builder creates formula-linked native Excel charts, one PNG per chart, and `summary_by_category_charts.xlsx`. The 2026-08-23 run completed successfully; all six charts rendered, and the workbook formula-error scan returned no matches.

## Top-10 and All-22 Category Palette

The union of the English, Danish, Math & Code, and Overall top-10 sets contains 22 models. The formula-linked workbook and PNG exports in `outputs/top10_category_charts_20260823/` use one stable colour per model across the four category charts plus Size and Overall/Non-embedding Size charts. `HRM-Mimir-v1` is red and `Mistral-Small-3.2` is royal blue; the other models use distinct pastel colours.

The original four top-10 category PNGs are preserved. Four additional PNGs—`07_english_all22.png` through `10_overall_all22.png`—show all 22 union models for English, Danish, Math & Code, and Overall, sorted highest-first.

The Size chart covers the same 22-model union and uses the assigned model colour for non-embedding parameters plus a lighter shade of that colour for embedding parameters. The efficiency chart uses `overall / noemb_B` for the same 22 models.

| Model | Colour |
|---|---|
| Mixtral-8x22B | `#8DD3C7` |
| Munin-Qwen3.5-9B | `#FFFFB3` |
| Munin-Mistral3-8B | `#BEBADA` |
| Apertus-v1.5-70B | `#FB8072` |
| Apertus-70B | `#80B1D3` |
| HRM-Mimir-v1 | `#D32F2F` |
| Mixtral-8x7B | `#FDB462` |
| Qwen3.5-4B | `#B3DE69` |
| HRM-Text-1B | `#FCCDE5` |
| Mistral-Small-3.2 | `#4169E1` |
| EuroLLM-22B | `#BC80BD` |
| Apertus-v1.5-8B | `#CCEBC5` |
| EuroLLM-9B | `#FFED6F` |
| Apertus-8B | `#B3E2CD` |
| Devstral-2 | `#FDCDAC` |
| Munin-Apertus-8b | `#CBD5E8` |
| Ministral-3-14B | `#F4CAE4` |
| Ministral-3-8B | `#E6F5C9` |
| Ministral-3-3B | `#F1E2CC` |
| Gemma-4-E2B-it | `#FBB4AE` |
| Gemma-4-E2B-it-thinking | `#B3CDE3` |
| SmolLM3-3B | `#DECBE4` |

Run from `outputs/top10_category_charts_20260823/`:

```bash
/Users/petersk/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node build_top10_charts.mjs
```

The 2026-08-23 run verified all four top-10 tables, all four 22-model category tables, the 22-model palette, ten native charts, and a clean formula-error scan. All four all-22 PNGs were visually checked for complete labels, 22 visible bars, sort order, and colour consistency. Confidence: high.

## Filtered European-Focused Union

A separate regenerated set is stored in `outputs/filtered_top10_union_charts_20260823/`. It explicitly retains `Munin-Qwen3.5-9B` and excludes every model whose name starts with `Qwen`, `Gemma`, or `SmolLM3`, case-insensitively. Applying those rules before selecting each category's top 10 produces a union of 19 models. `Mistral-Nemo` newly enters the union and uses pastel violet (`#D5AAFF`); retained models keep their earlier colours.

The `all_10_pngs/` subdirectory contains four filtered top-10 charts, Size and Overall/Non-embedding Size charts for the 19-model union, and four full-union category charts. The workbook records the selection rules and contains ten native charts. The 2026-08-23 run verified all formula-backed chart tables, found no formula errors, and visually checked all ten PNGs for sorting, complete labels, colour consistency, and clipping. Confidence: high.

Run from `outputs/filtered_top10_union_charts_20260823/`:

```bash
/Users/petersk/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node build_filtered_charts.mjs
```

## Filtered Union Without Munin

A further variant is stored in `outputs/filtered_no_munin_top10_union_charts_20260823/`. It excludes every model whose name starts with `Qwen`, `Gemma`, `SmolLM3`, or `Munin`, case-insensitively, and also excludes the exact model `CohereLabs-tiny-aya-global` before calculating each category's top 10. The resulting union contains 16 models; all retained models preserve their established colours.

Superseded on 2026-08-23: the first no-Munin pass contained 17 models because `CohereLabs-tiny-aya-global` entered the Danish top 10. The user identified it as non-European, so the current pass excludes it explicitly; `Ministral-3-8B` takes its Danish top-10 slot but was already part of the union.

The `all_10_pngs/` subdirectory contains the four recalculated top-10 charts, the two 16-model size/efficiency charts, and four full-union category charts. The workbook records all five exclusion rules. The 2026-08-23 run verified ten native charts, formula-backed helper tables, a clean formula-error scan, and visually checked all ten PNGs for complete labels, sorting, colour consistency, and clipping. Confidence: high.

The separate `top10_from_40/` subdirectory preserves the same four filtered top-10 rankings and model colours while starting each score axis at 40. The original ten PNGs remain unchanged. Four corresponding formula-linked sheets were added to the workbook; because the native workbook preview renderer ignored its configured axis minimum when exporting PNGs, the final four PNG previews are rendered reproducibly from the same filtered CSV by `render_top10_from40.py`. All four final previews were visually verified to show a 40.0 first tick, highest-first sorting, complete labels, and the established palette. Confidence: high.

Superseded on 2026-08-23: the first interactive English–Danish size view used a logarithmic transform for bubble area, which intentionally enlarged small models but did not preserve literal parameter-count area ratios.

The corrected interactive view uses outer bubble area directly proportional to total parameters and a nested solid inner area proportional to non-embedding parameters. Thus, for example, `Apertus-70B` has 59.83 times the outer area of `HRM-Text-1B`, exactly matching `70.60 / 1.18`. It retains English on the horizontal axis, Danish on the vertical axis, the Pareto frontier (`HRM-Mimir-v1`, `Apertus-70B`, and `Mixtral-8x22B`), and hover details for scores and parameter counts. The corrected layout was verified at 736 px and 360 px, in light and dark colour schemes, with no label overlaps or console errors. Confidence: high.

Static PNG exports of the literal-area nested-bubble view are stored in `outputs/filtered_no_munin_top10_union_charts_20260823/english_danish_size_bubbles/`. `01_english_danish_size_16_models.png` contains the filtered 16-model union at 2400×1600, `02_english_danish_size_all_50_models.png` contains every row in `summary_by_category.csv` at 3200×2300, and `03_english_danish_size_top10_overall.png` contains the ten highest `overall` scores across the full CSV at 2400×1600. All retain established model colours where assigned, directly label every plotted model, and show total versus non-embedding size through nested areas. All three PNGs were visually inspected for labels, axes, frontier, and clipping. Confidence: high.

A parallel three-PNG set is stored in `outputs/filtered_no_munin_top10_union_charts_20260823/danish_english_math_average_size_bubbles/`. Its horizontal score is `(english + math_code) / 2`, its vertical score is Danish, and it provides the same filtered-16, all-50, and top-10-overall populations and literal parameter-area encoding. The recalculated frontier consists of `HRM-Mimir-v1`, `Apertus-v1.5-8B`, and `Mixtral-8x22B`. All three outputs were visually verified for complete legends, labels, axes, frontier, and clipping. Confidence: high.

## Complete PNG Refresh — 2026-08-25

The current `summary_by_category.csv` contains 51 models. Applying the established European-focused exclusions before each category top 10 now yields an 18-model union: `Mistral-Small-4-119B` and `Mistral-Large-2411` enter the union, while the other retained models preserve their established colours. A complete flat set of 20 refreshed PNGs is stored in `outputs/benchmark_pngs_updated_20260825/`; it contains the ten standard ranking/size charts, four top-10 charts whose score axes start at 40, three English-versus-Danish nested-bubble charts, and three Danish-versus-average-English/Math nested-bubble charts. All files were regenerated from the current CSV and visually checked, including full-resolution checks of both 51-model plots. Confidence: high.

The previously blank size fields were resolved from official Mistral checkpoint metadata and architecture configuration. `Mistral-Small-4-119B` uses `params_B=119.40` from the checkpoint's exact `total_parameters=119401317952`; subtracting its untied input embedding and language-model head (`2 × 131072 × 4096`) gives `noemb_B=118.33`. `Mistral-Large-2411` uses `params_B=122.61`; its official 123B model configuration gives an exact dense parameter count of `122610069504`, and subtracting both untied `32768 × 12288` token matrices gives `noemb_B=121.80`. Sources: https://huggingface.co/mistralai/Mistral-Small-4-119B-2603/resolve/main/model.safetensors.index.json, https://huggingface.co/mistralai/Mistral-Small-4-119B-2603/blob/main/config.json, https://huggingface.co/mistralai/Mistral-Large-Instruct-2411/blob/main/config.json, and https://huggingface.co/mistralai/Mistral-Large-Instruct-2411. Confidence: high.

Run from the repository root:

```bash
/Users/petersk/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 outputs/build_benchmark_pngs_updated_20260825.py
```

## Danish–English/Math Size Charts Without the Mistral Family — 2026-08-25

A preserved three-PNG variant is stored in `outputs/danish_english_math_size_no_mistral_20260825/`. It removes every CSV model whose name identifies the Mistral ecosystem (`Mistral`, `Ministral`, `Mixtral`, `Devstral`, or `Codestral`), including named derivatives such as `Munin-Mistral3-8B` and `NorMistral-*`. This removes 15 rows from the current 51-row CSV and leaves 36 models in the all-model view. Confidence: high.

The middle population recalculates the union of the four category top-10 sets after both the established European-focused filters and the Mistral-family exclusion; the union falls from 18 to 13 models. The top-10-overall view is recalculated from all remaining non-Mistral-family rows. All three charts use Danish against `(English + Math & Code) / 2`, literal parameter-area scaling, nested total/non-embedding bubbles, and a population-specific Pareto frontier. Full-resolution visual inspection found complete labels, axes, legends, and no clipping. Confidence: high.

Run from the repository root:

```bash
/Users/petersk/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 outputs/render_danish_english_math_no_mistral.py
```

Superseded later on 2026-08-25: the first variant excluded the Mistral ecosystem but did not apply the requested Gemma/Qwen provenance filter and excluded all `Munin-*` models from its middle union.

The current regenerated variant is stored separately in `outputs/danish_english_math_size_european_no_mistral_20260825/`. Its filter precedence is: retain every `Munin-*` row, including Munin adaptations of Qwen and Mistral; otherwise exclude the Mistral/Ministral/Mixtral/Devstral/Codestral families, standalone Gemma and Qwen rows, and the previously excluded `CohereLabs-tiny-aya-global`. SmolLM rows are restored. This leaves 29 eligible rows, a recalculated four-category top-10 union of 14, and a recalculated top 10 overall. All three full-resolution PNGs were visually verified for labels, size encoding, axes, frontiers, and clipping. Confidence: high.

Run from `outputs/filtered_no_munin_top10_union_charts_20260823/`:

```bash
/Users/petersk/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node build_no_munin_charts.mjs
/Users/petersk/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 render_top10_from40.py
/Users/petersk/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 render_english_danish_size_bubbles.py
```
