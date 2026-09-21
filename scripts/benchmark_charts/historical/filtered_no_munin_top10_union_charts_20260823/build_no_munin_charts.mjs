import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = path.resolve(".");
const sourcePath = path.resolve(outputDir, "../../summary_by_category.csv");
const csvText = await fs.readFile(sourcePath, "utf8");
const lines = csvText.trim().split(/\r?\n/);
const headers = lines[0].split(",");
const records = lines.slice(1).map((line, index) => {
  const values = line.split(",");
  const raw = Object.fromEntries(headers.map((header, i) => [header, values[i]]));
  return {
    sourceRow: index + 2,
    rank: Number(raw.rank),
    model: raw.model,
    params_B: Number(raw.params_B),
    noemb_B: Number(raw.noemb_B),
    english: Number(raw.english),
    danish: Number(raw.danish),
    math_code: Number(raw.math_code),
    overall: Number(raw.overall),
  };
});

const isExcludedModel = (model) => (
  /^(Qwen|Gemma|SmolLM3|Munin)/i.test(model)
  || model === "CohereLabs-tiny-aya-global"
);
const eligibleRecords = records.filter((record) => !isExcludedModel(record.model));

const palette = [
  ["Mixtral-8x22B", "#8DD3C7", "Pastel teal"],
  ["Apertus-v1.5-70B", "#FB8072", "Pastel coral"],
  ["Apertus-70B", "#80B1D3", "Pastel blue"],
  ["HRM-Mimir-v1", "#D32F2F", "Red"],
  ["Mixtral-8x7B", "#FDB462", "Pastel orange"],
  ["HRM-Text-1B", "#FCCDE5", "Pastel pink"],
  ["Mistral-Small-3.2", "#4169E1", "Royal blue"],
  ["EuroLLM-22B", "#BC80BD", "Pastel purple"],
  ["Apertus-v1.5-8B", "#CCEBC5", "Pastel mint"],
  ["EuroLLM-9B", "#FFED6F", "Pastel gold"],
  ["Apertus-8B", "#B3E2CD", "Pastel seafoam"],
  ["Devstral-2", "#FDCDAC", "Pastel peach"],
  ["Ministral-3-14B", "#F4CAE4", "Pastel rose"],
  ["Ministral-3-8B", "#E6F5C9", "Pastel pale green"],
  ["Ministral-3-3B", "#F1E2CC", "Pastel beige"],
  ["Mistral-Nemo", "#D5AAFF", "Pastel violet"],
];

const colorByModel = new Map(palette.map(([model, color]) => [model, color]));
const metrics = [
  { key: "english", sourceCol: "E", sheetName: "English Top 10", title: "Top 10 — English", fileName: "01_english_top10.png" },
  { key: "danish", sourceCol: "G", sheetName: "Danish Top 10", title: "Top 10 — Danish", fileName: "02_danish_top10.png" },
  { key: "math_code", sourceCol: "F", sheetName: "Math Code Top 10", title: "Top 10 — Math & Code", fileName: "03_math_and_code_top10.png" },
  { key: "overall", sourceCol: "H", sheetName: "Overall Top 10", title: "Top 10 — Overall", fileName: "04_overall_top10.png" },
];

const topSets = metrics.map(({ key }) => new Set(
  [...eligibleRecords].sort((a, b) => b[key] - a[key] || a.rank - b.rank).slice(0, 10).map((record) => record.model),
));
const union = new Set(topSets.flatMap((set) => [...set]));
if (union.size !== 16) throw new Error(`Expected 16 union models, found ${union.size}`);
for (const model of union) {
  if (!colorByModel.has(model)) throw new Error(`No colour assigned to ${model}`);
}

function excelColumn(oneBasedIndex) {
  let value = oneBasedIndex;
  let result = "";
  while (value > 0) {
    value -= 1;
    result = String.fromCharCode(65 + (value % 26)) + result;
    value = Math.floor(value / 26);
  }
  return result;
}

function lightenHex(hex, amount = 0.38) {
  const value = hex.replace("#", "");
  const channels = [0, 2, 4].map((offset) => Number.parseInt(value.slice(offset, offset + 2), 16));
  const lightened = channels.map((channel) => Math.round(channel + (255 - channel) * amount));
  return `#${lightened.map((channel) => channel.toString(16).padStart(2, "0")).join("").toUpperCase()}`;
}

const workbook = await Workbook.fromCSV(csvText, { sheetName: "Source" });
const source = workbook.worksheets.getItem("Source");
source.showGridLines = false;
source.freezePanes.freezeRows(1);
source.getRange("A1:H1").format = { fill: "#17324D", font: { bold: true, color: "#FFFFFF" } };
source.getRange("A:A").format.columnWidth = 8;
source.getRange("B:B").format.columnWidth = 30;
source.getRange("C:H").format.columnWidth = 14;
source.getRange(`C2:H${records.length + 1}`).format.numberFormat = "0.0";
source.tables.add(`A1:H${records.length + 1}`, true, "Top10SourceData");

const paletteSheet = workbook.worksheets.add("Palette");
paletteSheet.showGridLines = false;
paletteSheet.freezePanes.freezeRows(1);
paletteSheet.getRange("A1:D1").values = [["Model", "Hex colour", "Swatch", "Role"]];
paletteSheet.getRange(`A2:D${palette.length + 1}`).values = palette.map(([model, color, role]) => [model, color, "", role]);
paletteSheet.getRange("A1:D1").format = { fill: "#17324D", font: { bold: true, color: "#FFFFFF" } };
paletteSheet.getRange("A:A").format.columnWidth = 31;
paletteSheet.getRange("B:B").format.columnWidth = 14;
paletteSheet.getRange("C:C").format.columnWidth = 12;
paletteSheet.getRange("D:D").format.columnWidth = 22;
paletteSheet.getRange(`A2:D${palette.length + 1}`).format.rowHeight = 24;
for (let i = 0; i < palette.length; i += 1) {
  const color = palette[i][1];
  paletteSheet.getRange(`C${i + 2}`).format = {
    fill: color,
    borders: { preset: "outside", style: "thin", color: "#A0A0A0" },
  };
}
paletteSheet.tables.add(`A1:D${palette.length + 1}`, true, "ModelColourPalette");

const selectionSheet = workbook.worksheets.add("Selection Rules");
selectionSheet.showGridLines = false;
selectionSheet.getRange("A1:B1").values = [["Selection rule", "Value"]];
selectionSheet.getRange("A2:B7").values = [
  ["Excluded model prefix", "Qwen*"],
  ["Excluded model prefix", "Gemma*"],
  ["Excluded model prefix", "SmolLM3*"],
  ["Excluded model prefix", "Munin*"],
  ["Excluded exact model", "CohereLabs-tiny-aya-global"],
  ["Filtered top-10 union size", union.size],
];
selectionSheet.getRange("A1:B1").format = { fill: "#17324D", font: { bold: true, color: "#FFFFFF" } };
selectionSheet.getRange("A:A").format.columnWidth = 28;
selectionSheet.getRange("B:B").format.columnWidth = 30;
selectionSheet.tables.add("A1:B7", true, "SelectionRules");

function sourceFormula(column, sourceRow) {
  return `='Source'!$${column}$${sourceRow}`;
}

function addTopTenChart(metric, { sheetName, title, minScore }) {
  const topTen = [...eligibleRecords]
    .sort((a, b) => b[metric.key] - a[metric.key] || a.rank - b.rank)
    .slice(0, 10)
    .sort((a, b) => a[metric.key] - b[metric.key] || b.rank - a.rank);

  const sheet = workbook.worksheets.add(sheetName);
  sheet.showGridLines = false;
  const helperStartCol = 27;
  const helperEndCol = helperStartCol + palette.length;
  const startLetter = excelColumn(helperStartCol);
  const endLetter = excelColumn(helperEndCol);
  const headersRow = ["Model", ...palette.map(([model]) => model)];
  sheet.getRange(`${startLetter}1:${endLetter}1`).values = [headersRow];

  const formulaRows = topTen.map((record, rowIndex) => {
    const modelFormula = sourceFormula("B", record.sourceRow);
    const metricFormula = sourceFormula(metric.sourceCol, record.sourceRow);
    return [
      modelFormula,
      ...palette.map(([model]) => `=IF($${startLetter}${rowIndex + 2}=\"${model}\",${metricFormula},\"\")`),
    ];
  });
  sheet.getRange(`${startLetter}2:${endLetter}11`).formulas = formulaRows;
  sheet.getRange(`${excelColumn(helperStartCol + 1)}2:${endLetter}11`).format.numberFormat = "0.0";
  sheet.getRange(`${startLetter}:${startLetter}`).format.columnWidth = 30;
  sheet.getRange(`${excelColumn(helperStartCol + 1)}:${endLetter}`).format.columnWidth = 13;
  sheet.getRange(`${startLetter}1:${endLetter}1`).format = { fill: "#17324D", font: { bold: true, color: "#FFFFFF" } };

  const chart = sheet.charts.add("bar", {
    title,
    titleTextStyle: { fontSize: 14 },
    hasLegend: false,
    barOptions: { direction: "bar", grouping: "stacked", gapWidth: 55, overlap: 100 },
    xAxis: { axisType: "textAxis", orientation: "maxMin", textStyle: { fontSize: 11 } },
    yAxis: {
      min: minScore,
      max: 100,
      numberFormatCode: "0.0",
      title: { text: "Score", textStyle: { fontSize: 10 } },
      textStyle: { fontSize: 10 },
      majorGridlines: { fill: "#D9E2EC", style: "solid", width: 0.5 },
    },
    dataLabels: { showValue: true, position: "outEnd", textStyle: { fontSize: 10 } },
    from: { row: 1, col: 0 },
    extent: { widthPx: 1120, heightPx: 680 },
  });

  const categoryFormula = `'${sheetName}'!$${startLetter}$2:$${startLetter}$11`;
  for (let i = 0; i < palette.length; i += 1) {
    const [model, color] = palette[i];
    const column = excelColumn(helperStartCol + i + 1);
    const series = chart.series.add(model);
    series.categoryFormula = categoryFormula;
    series.formula = `'${sheetName}'!$${column}$2:$${column}$11`;
    series.valuesFormatCode = "0.0";
    series.fill = { type: "solid", color };
  }
  return { sheet, helperRange: `${startLetter}1:${endLetter}11` };
}

const chartSheets = metrics.map((metric) => addTopTenChart(metric, {
  sheetName: metric.sheetName,
  title: metric.title,
  minScore: 0,
}));

const from40ChartSheets = metrics.map((metric) => addTopTenChart(metric, {
  sheetName: `${metric.sheetName} from 40`,
  title: `${metric.title} — axis starts at 40`,
  minScore: 40,
}));

const unionRecords = eligibleRecords.filter((record) => union.has(record.model));
if (unionRecords.length !== union.size) {
  throw new Error(`Union record mismatch: ${unionRecords.length} records for ${union.size} models`);
}

const allUnionFileNames = {
  english: "07_english_all16.png",
  danish: "08_danish_all16.png",
  math_code: "09_math_and_code_all16.png",
  overall: "10_overall_all16.png",
};

function addAllUnionCategoryChart(metric) {
  const metricLabel = metric.title.replace("Top 10 — ", "");
  const sheetName = `${metricLabel} — all 16`;
  const sheet = workbook.worksheets.add(sheetName);
  sheet.showGridLines = false;
  const sorted = [...unionRecords].sort(
    (a, b) => a[metric.key] - b[metric.key] || b.rank - a.rank,
  );
  const helperStartCol = 27;
  const startLetter = excelColumn(helperStartCol);
  const helperEndCol = helperStartCol + palette.length;
  const endLetter = excelColumn(helperEndCol);
  sheet.getRange(`${startLetter}1:${endLetter}1`).values = [["Model", ...palette.map(([model]) => model)]];
  const formulaRows = sorted.map((record, rowIndex) => [
    sourceFormula("B", record.sourceRow),
    ...palette.map(([model]) => {
      const modelCell = `$${startLetter}${rowIndex + 2}`;
      return `=IF(${modelCell}=\"${model}\",${sourceFormula(metric.sourceCol, record.sourceRow).slice(1)},\"\")`;
    }),
  ]);
  sheet.getRange(`${startLetter}2:${endLetter}${sorted.length + 1}`).formulas = formulaRows;
  sheet.getRange(`${excelColumn(helperStartCol + 1)}2:${endLetter}${sorted.length + 1}`).format.numberFormat = "0.0";
  sheet.getRange(`${startLetter}1:${endLetter}1`).format = { fill: "#17324D", font: { bold: true, color: "#FFFFFF" } };

  const chart = sheet.charts.add("bar", {
    title: `Top-10 union (16) — ${metricLabel}`,
    titleTextStyle: { fontSize: 14 },
    hasLegend: false,
    barOptions: { direction: "bar", grouping: "stacked", gapWidth: 48, overlap: 100 },
    xAxis: { axisType: "textAxis", orientation: "maxMin", textStyle: { fontSize: 10 } },
    yAxis: {
      min: 0,
      max: 100,
      numberFormatCode: "0.0",
      title: { text: "Score", textStyle: { fontSize: 10 } },
      textStyle: { fontSize: 9 },
      majorGridlines: { fill: "#D9E2EC", style: "solid", width: 0.5 },
    },
    dataLabels: { showValue: true, position: "outEnd", textStyle: { fontSize: 9 } },
    from: { row: 1, col: 0 },
    extent: { widthPx: 1220, heightPx: 1050 },
  });
  const categoryFormula = `'${sheetName}'!$${startLetter}$2:$${startLetter}$${sorted.length + 1}`;
  for (let i = 0; i < palette.length; i += 1) {
    const [model, color] = palette[i];
    const column = excelColumn(helperStartCol + i + 1);
    const series = chart.series.add(model);
    series.categoryFormula = categoryFormula;
    series.formula = `'${sheetName}'!$${column}$2:$${column}$${sorted.length + 1}`;
    series.valuesFormatCode = "0.0";
    series.fill = { type: "solid", color };
  }
  return {
    sheet,
    fileName: allUnionFileNames[metric.key],
    helperRange: `${startLetter}1:${endLetter}${sorted.length + 1}`,
  };
}

const allUnionChartSheets = metrics.map(addAllUnionCategoryChart);

function addSizeChart() {
  const sheetName = "Size — 16 models";
  const sheet = workbook.worksheets.add(sheetName);
  sheet.showGridLines = false;
  const sorted = [...unionRecords].sort((a, b) => a.params_B - b.params_B || b.rank - a.rank);
  const helperStartCol = 27;
  const startLetter = excelColumn(helperStartCol);
  const seriesHeaders = palette.flatMap(([model]) => [`${model} — no embedding`, `${model} — embedding`]);
  const helperEndCol = helperStartCol + seriesHeaders.length;
  const endLetter = excelColumn(helperEndCol);
  sheet.getRange(`${startLetter}1:${endLetter}1`).values = [["Model", ...seriesHeaders]];

  const formulaRows = sorted.map((record, rowIndex) => [
    sourceFormula("B", record.sourceRow),
    ...palette.flatMap(([model]) => {
      const modelCell = `$${startLetter}${rowIndex + 2}`;
      return [
        `=IF(${modelCell}=\"${model}\",${sourceFormula("D", record.sourceRow).slice(1)},\"\")`,
        `=IF(${modelCell}=\"${model}\",'Source'!$C$${record.sourceRow}-'Source'!$D$${record.sourceRow},\"\")`,
      ];
    }),
  ]);
  sheet.getRange(`${startLetter}2:${endLetter}${sorted.length + 1}`).formulas = formulaRows;
  sheet.getRange(`${excelColumn(helperStartCol + 1)}2:${endLetter}${sorted.length + 1}`).format.numberFormat = "0.00";
  sheet.getRange(`${startLetter}1:${endLetter}1`).format = { fill: "#17324D", font: { bold: true, color: "#FFFFFF" } };

  const chart = sheet.charts.add("bar", {
    title: "Model size — dark: non-embedding, light: embedding (16-model union)",
    titleTextStyle: { fontSize: 14 },
    hasLegend: false,
    barOptions: { direction: "bar", grouping: "stacked", gapWidth: 48, overlap: 100 },
    xAxis: { axisType: "textAxis", orientation: "maxMin", textStyle: { fontSize: 10 } },
    yAxis: {
      min: 0,
      max: 160,
      numberFormatCode: "0.0",
      title: { text: "Billions of parameters", textStyle: { fontSize: 10 } },
      textStyle: { fontSize: 9 },
      majorGridlines: { fill: "#D9E2EC", style: "solid", width: 0.5 },
    },
    dataLabels: { showValue: false },
    from: { row: 1, col: 0 },
    extent: { widthPx: 1220, heightPx: 1050 },
  });

  const categoryFormula = `'${sheetName}'!$${startLetter}$2:$${startLetter}$${sorted.length + 1}`;
  for (let i = 0; i < palette.length; i += 1) {
    const [model, color] = palette[i];
    for (let segment = 0; segment < 2; segment += 1) {
      const column = excelColumn(helperStartCol + i * 2 + segment + 1);
      const series = chart.series.add(`${model} — ${segment === 0 ? "no embedding" : "embedding"}`);
      series.categoryFormula = categoryFormula;
      series.formula = `'${sheetName}'!$${column}$2:$${column}$${sorted.length + 1}`;
      series.valuesFormatCode = "0.00";
      series.fill = { type: "solid", color: segment === 0 ? color : lightenHex(color) };
    }
  }
  return { sheet, helperRange: `${startLetter}1:${endLetter}${sorted.length + 1}` };
}

function addEfficiencyChart() {
  const sheetName = "Overall per Size";
  const sheet = workbook.worksheets.add(sheetName);
  sheet.showGridLines = false;
  const sorted = [...unionRecords].sort(
    (a, b) => a.overall / a.noemb_B - b.overall / b.noemb_B || b.rank - a.rank,
  );
  const helperStartCol = 27;
  const startLetter = excelColumn(helperStartCol);
  const helperEndCol = helperStartCol + palette.length;
  const endLetter = excelColumn(helperEndCol);
  sheet.getRange(`${startLetter}1:${endLetter}1`).values = [["Model", ...palette.map(([model]) => model)]];
  const formulaRows = sorted.map((record, rowIndex) => [
    sourceFormula("B", record.sourceRow),
    ...palette.map(([model]) => {
      const modelCell = `$${startLetter}${rowIndex + 2}`;
      return `=IF(${modelCell}=\"${model}\",'Source'!$H$${record.sourceRow}/'Source'!$D$${record.sourceRow},\"\")`;
    }),
  ]);
  sheet.getRange(`${startLetter}2:${endLetter}${sorted.length + 1}`).formulas = formulaRows;
  sheet.getRange(`${excelColumn(helperStartCol + 1)}2:${endLetter}${sorted.length + 1}`).format.numberFormat = "0.0";
  sheet.getRange(`${startLetter}1:${endLetter}1`).format = { fill: "#17324D", font: { bold: true, color: "#FFFFFF" } };

  const chart = sheet.charts.add("bar", {
    title: "Overall / non-embedding size — 16-model union",
    titleTextStyle: { fontSize: 14 },
    hasLegend: false,
    barOptions: { direction: "bar", grouping: "stacked", gapWidth: 48, overlap: 100 },
    xAxis: { axisType: "textAxis", orientation: "maxMin", textStyle: { fontSize: 10 } },
    yAxis: {
      min: 0,
      max: 80,
      numberFormatCode: "0.0",
      title: { text: "Overall score / B non-embedding params", textStyle: { fontSize: 10 } },
      textStyle: { fontSize: 9 },
      majorGridlines: { fill: "#D9E2EC", style: "solid", width: 0.5 },
    },
    dataLabels: { showValue: true, position: "outEnd", textStyle: { fontSize: 9 } },
    from: { row: 1, col: 0 },
    extent: { widthPx: 1220, heightPx: 1050 },
  });
  const categoryFormula = `'${sheetName}'!$${startLetter}$2:$${startLetter}$${sorted.length + 1}`;
  for (let i = 0; i < palette.length; i += 1) {
    const [model, color] = palette[i];
    const column = excelColumn(helperStartCol + i + 1);
    const series = chart.series.add(model);
    series.categoryFormula = categoryFormula;
    series.formula = `'${sheetName}'!$${column}$2:$${column}$${sorted.length + 1}`;
    series.valuesFormatCode = "0.0";
    series.fill = { type: "solid", color };
  }
  return { sheet, helperRange: `${startLetter}1:${endLetter}${sorted.length + 1}` };
}

const sizeChart = addSizeChart();
const efficiencyChart = addEfficiencyChart();

const paletteCheck = await workbook.inspect({
  kind: "table",
  range: `Palette!A1:D${palette.length + 1}`,
  include: "values,formulas",
  tableMaxRows: 25,
  tableMaxCols: 4,
  maxChars: 9000,
});
console.log(paletteCheck.ndjson);

for (const metric of metrics) {
  const topEndLetter = excelColumn(27 + palette.length);
  const sheetCheck = await workbook.inspect({
    kind: "table",
    range: `'${metric.sheetName}'!AA1:${topEndLetter}11`,
    include: "values,formulas",
    tableMaxRows: 12,
    tableMaxCols: 23,
    maxChars: 10000,
  });
  console.log(sheetCheck.ndjson);
}

for (const extra of from40ChartSheets) {
  const sheetCheck = await workbook.inspect({
    kind: "table",
    range: `'${extra.sheet.name}'!${extra.helperRange}`,
    include: "values,formulas",
    tableMaxRows: 12,
    tableMaxCols: 20,
    maxChars: 10000,
  });
  console.log(sheetCheck.ndjson);
}

for (const extra of [sizeChart, efficiencyChart]) {
  const sheetCheck = await workbook.inspect({
    kind: "table",
    range: `'${extra.sheet.name}'!${extra.helperRange}`,
    include: "values,formulas",
    tableMaxRows: 24,
    tableMaxCols: 45,
    maxChars: 12000,
  });
  console.log(sheetCheck.ndjson);
}

for (const extra of allUnionChartSheets) {
  const sheetCheck = await workbook.inspect({
    kind: "table",
    range: `'${extra.sheet.name}'!${extra.helperRange}`,
    include: "values,formulas",
    tableMaxRows: 24,
    tableMaxCols: 23,
    maxChars: 12000,
  });
  console.log(sheetCheck.ndjson);
}

const drawingCheck = await workbook.inspect({ kind: "drawing", maxChars: 7000 });
console.log(drawingCheck.ndjson);
const errorCheck = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
  maxChars: 4000,
});
console.log(errorCheck.ndjson);

const palettePreview = await workbook.render({ sheetName: "Palette", range: `A1:D${palette.length + 1}`, scale: 1.2, format: "png" });
await fs.writeFile("/tmp/filtered_top10_model_palette_preview.png", new Uint8Array(await palettePreview.arrayBuffer()));

const pngDir = path.join(outputDir, "all_10_pngs");
await fs.rm(pngDir, { recursive: true, force: true });
await fs.mkdir(pngDir, { recursive: true });

for (let i = 0; i < metrics.length; i += 1) {
  const preview = await workbook.render({ sheetName: chartSheets[i].sheet.name, range: "A1:N36", scale: 1.2, format: "png" });
  await fs.writeFile(path.join(pngDir, metrics[i].fileName), new Uint8Array(await preview.arrayBuffer()));
}

const from40Dir = path.join(outputDir, "top10_from_40");
await fs.rm(from40Dir, { recursive: true, force: true });
await fs.mkdir(from40Dir, { recursive: true });
for (let i = 0; i < metrics.length; i += 1) {
  const preview = await workbook.render({ sheetName: from40ChartSheets[i].sheet.name, range: "A1:N36", scale: 1.2, format: "png" });
  const fileName = metrics[i].fileName.replace(".png", "_from40.png");
  await fs.writeFile(path.join(from40Dir, fileName), new Uint8Array(await preview.arrayBuffer()));
}

const sizePreview = await workbook.render({ sheetName: sizeChart.sheet.name, range: "A1:P58", scale: 1.1, format: "png" });
await fs.writeFile(path.join(pngDir, "05_size_16_models.png"), new Uint8Array(await sizePreview.arrayBuffer()));
const efficiencyPreview = await workbook.render({ sheetName: efficiencyChart.sheet.name, range: "A1:P58", scale: 1.1, format: "png" });
await fs.writeFile(path.join(pngDir, "06_overall_per_noemb_16_models.png"), new Uint8Array(await efficiencyPreview.arrayBuffer()));

for (const extra of allUnionChartSheets) {
  const preview = await workbook.render({ sheetName: extra.sheet.name, range: "A1:P58", scale: 1.1, format: "png" });
  await fs.writeFile(path.join(pngDir, extra.fileName), new Uint8Array(await preview.arrayBuffer()));
}

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(path.join(outputDir, "filtered_no_munin_union_charts.xlsx"));
