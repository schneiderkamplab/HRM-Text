# Benchmark chart sources

These tools render the tracked `summary_by_category.csv` snapshot (51 models).
They reproduce visualizations of recorded scores, not the evaluation runs that
produced the scores. See [the chart runbook](../../wiki/pages/benchmark-charts.md)
for metric definitions, selection rules and historical results.

## Current PNG suite

From the repository root, using Python 3.10+ and Pillow (validated with 11.3.0):

```sh
python3 -m venv logs/benchmark-chart-env
logs/benchmark-chart-env/bin/python -m pip install Pillow==11.3.0
logs/benchmark-chart-env/bin/python -m scripts.benchmark_charts.render_rankings
logs/benchmark-chart-env/bin/python -m scripts.benchmark_charts.render_european
```

The first command generates 20 PNGs in
`outputs/benchmark_pngs_updated_20260825/` (51 models, filtered union of 18).
The second generates three PNGs in
`outputs/danish_english_math_size_european_no_mistral_20260825/`
(29 eligible models, union of 14). Existing same-named PNGs are overwritten.
Generated files remain ignored; use a fresh output directory when changing input.

Optional environment variables:

- `BENCHMARK_CSV`: alternative CSV with the same columns.
- `BENCHMARK_OUTPUT_ROOT`: output root instead of `outputs/`.
- `BENCHMARK_FONT_REGULAR` and `BENCHMARK_FONT_BOLD`: explicit TrueType font paths.

The original macOS/XQuartz Arial paths are used when available. Otherwise,
install DejaVu Sans or set both font variables. Font and rendering-library
changes can affect layout and pixels; fonts are not bundled.

The renderers share `_bubbles.py` and `_common.py`; no source code is loaded
from ignored output directories. Python modules are internal tools, not a
public package API.

## Historical sources

`historical/` preserves four original spreadsheet builders and the earlier
40-baseline renderer without changing their calculations. This is archival
source, not a second maintained implementation. Spreadsheet builders require
`@oai/artifact-tool` from the original bundled spreadsheet runtime. That runtime
and the original August 23 CSV are not included. The current 51-row snapshot
cannot reproduce the older 50-row results and fixed population labels exactly.

Their relative paths assume the original layout under `outputs/`; restore a
builder to the matching output subdirectory and run there if investigating an
old result. The historical Python renderer also assumes the original Arial
paths. For current chart generation use the two module commands above, which
include the 40-baseline charts and have no spreadsheet-runtime dependency.
