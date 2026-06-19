# DFM5 Slack table paste files

Slack DMs do not support true tables. Slack Canvas table paste is more reliable from a rich clipboard source, such as a rendered browser table or spreadsheet, than from raw Markdown or TSV text.

Recommended path:

1. Open a Slack Canvas.
2. Open `docs/dfm5_slack_tables/dfm5_slack_tables.html` in a browser.
3. Drag-select one rendered table, including the header row.
4. Copy it.
5. Paste into the Canvas.

Fallback path:

1. Open one TSV file in a spreadsheet application.
2. Copy the populated cells from the spreadsheet.
3. Paste into the Canvas.

Files:

- `docs/dfm5_slack_tables/dfm5_slack_tables.html`: rendered HTML tables for browser copy/paste into Slack Canvas
- `docs/dfm5_slack_tables/dfm5_danish_slack_table.tsv`: Danish, 20 data rows x 15 columns
- `docs/dfm5_slack_tables/dfm5_english_slack_table.tsv`: English, 17 data rows x 15 columns
- `docs/dfm5_slack_tables/dfm5_math_code_slack_table.tsv`: Math & Code, 5 data rows x 15 columns
- `docs/dfm5_slack_tables/dfm5_all_slack_tables.tsv`: all tables in one TSV file, separated by section labels and blank lines. Use only if pasting into a spreadsheet first.
