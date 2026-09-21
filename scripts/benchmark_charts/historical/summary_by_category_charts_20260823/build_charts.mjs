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
  const row = Object.fromEntries(headers.map((header, i) => [header, values[i]]));
  return {
    sourceRow: index + 2,
    model: row.model,
    params_B: Number(row.params_B),
    noemb_B: Number(row.noemb_B),
    english: Number(row.english),
    math_code: Number(row.math_code),
    danish: Number(row.danish),
    overall: Number(row.overall),
  };
});
console.error("stage: parsed source");

const workbook = await Workbook.fromCSV(csvText, { sheetName: "Source" });
console.error("stage: imported csv");
const source = workbook.worksheets.getItem("Source");
source.showGridLines = false;
source.freezePanes.freezeRows(1);
source.getRange("I1").values = [["overall_per_noemb_B"]];
source.getRange("I2").formulas = [["=IFERROR(H2/D2,\"\")"]];
source.getRange(`I2:I${records.length + 1}`).fillDown();
source.getRange("A1:I1").format = {
  fill: "#17324D",
  font: { bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
};
source.getRange(`A2:A${records.length + 1}`).format.numberFormat = "0";
source.getRange(`C2:D${records.length + 1}`).format.numberFormat = "0.00";
source.getRange(`E2:I${records.length + 1}`).format.numberFormat = "0.0";
source.getRange(`A1:I${records.length + 1}`).format.rowHeight = 20;
source.getRange("A:A").format.columnWidth = 8;
source.getRange("B:B").format.columnWidth = 30;
source.getRange("C:I").format.columnWidth = 17;
source.tables.add(`A1:I${records.length + 1}`, true, "BenchmarkSource");
console.error("stage: formatted source");

const BLUE = "#2563EB";
const BLUE_LIGHT = "#93C5FD";
const RED = "#DC2626";
const RED_LIGHT = "#FCA5A5";
const MIMIR = "HRM-Mimir-v1";

const specs = [
  { sheetName: "English", fileName: "01_english.png", key: "english", sourceCol: "E", title: "English performance", axisTitle: "Score", numberFormat: "0.0" },
  { sheetName: "Danish", fileName: "02_danish.png", key: "danish", sourceCol: "G", title: "Danish performance", axisTitle: "Score", numberFormat: "0.0" },
  { sheetName: "Math and Code", fileName: "03_math_and_code.png", key: "math_code", sourceCol: "F", title: "Math & Code performance", axisTitle: "Score", numberFormat: "0.0" },
  { sheetName: "Overall", fileName: "04_overall.png", key: "overall", sourceCol: "H", title: "Overall performance", axisTitle: "Score", numberFormat: "0.0" },
  { sheetName: "Size", fileName: "05_size_b_params.png", key: "params_B", title: "Model size (B parameters)", axisTitle: "Billions of parameters", numberFormat: "0.0" },
  { sheetName: "Efficiency", fileName: "06_overall_per_noemb_b.png", key: "efficiency", sourceCol: "I", title: "Overall performance per B non-embedding parameters", axisTitle: "Overall score / B non-embedding params", numberFormat: "0.0" },
];

function sourceFormula(column, sourceRow) {
  return `='Source'!$${column}$${sourceRow}`;
}

function sortValue(record, key) {
  return key === "efficiency" ? record.overall / record.noemb_B : record[key];
}

function setSheetLayout(sheet, helperColumns) {
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  sheet.getRange(`A1:${helperColumns}1`).format = {
    fill: "#17324D",
    font: { bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
  };
  sheet.getRange(`A1:${helperColumns}${records.length + 1}`).format.rowHeight = 24;
  sheet.getRange("A:A").format.columnWidth = 30;
  sheet.getRange(`B:${helperColumns}`).format.columnWidth = 18;
  sheet.getRange("D:Q").format.columnWidth = 12;
}

function addPerformanceSheet(spec) {
  const sheet = workbook.worksheets.add(spec.sheetName);
  console.error(`stage: ${spec.sheetName} sheet`);
  const sorted = [...records].sort((a, b) => sortValue(a, spec.key) - sortValue(b, spec.key));
  sheet.getRange("A1:C1").values = [["Model", "Other models", "Mimir"]];
  const rows = sorted.map((record) => [
    sourceFormula("B", record.sourceRow),
    record.model === MIMIR ? "=\"\"" : sourceFormula(spec.sourceCol, record.sourceRow),
    record.model === MIMIR ? sourceFormula(spec.sourceCol, record.sourceRow) : "=\"\"",
  ]);
  sheet.getRange(`A2:C${records.length + 1}`).formulas = rows;
  sheet.getRange(`B2:C${records.length + 1}`).format.numberFormat = spec.numberFormat;
  setSheetLayout(sheet, "C");
  console.error(`stage: ${spec.sheetName} data`);

  const chart = sheet.charts.add("bar", {
    title: spec.title,
    titleTextStyle: { fontSize: 14 },
    hasLegend: true,
    legend: { position: "bottom", textStyle: { fontSize: 10 } },
    barOptions: { direction: "bar", grouping: "stacked", gapWidth: 45, overlap: 100 },
    xAxis: { axisType: "textAxis", orientation: "maxMin", textStyle: { fontSize: 9 } },
    yAxis: {
      min: 0,
      numberFormatCode: spec.numberFormat,
      title: { text: spec.axisTitle, textStyle: { fontSize: 10 } },
      textStyle: { fontSize: 9 },
      majorGridlines: { fill: "#D9E2EC", style: "solid", width: 0.5 },
    },
    dataLabels: { showValue: true, numberFormatCode: spec.numberFormat, textStyle: { fontSize: 8 } },
    from: { row: 1, col: 3 },
    extent: { widthPx: 1320, heightPx: 1480 },
  });
  const categories = `'${spec.sheetName}'!$A$2:$A$${records.length + 1}`;
  const otherSeries = chart.series.add("Other models");
  otherSeries.categoryFormula = categories;
  otherSeries.formula = `'${spec.sheetName}'!$B$2:$B$${records.length + 1}`;
  otherSeries.valuesFormatCode = spec.numberFormat;
  otherSeries.fill = { type: "solid", color: BLUE };
  const mimirSeries = chart.series.add("Mimir");
  mimirSeries.categoryFormula = categories;
  mimirSeries.formula = `'${spec.sheetName}'!$C$2:$C$${records.length + 1}`;
  mimirSeries.valuesFormatCode = spec.numberFormat;
  mimirSeries.fill = { type: "solid", color: RED };
  console.error(`stage: ${spec.sheetName} chart`);
  return sheet;
}

function addSizeSheet(spec) {
  const sheet = workbook.worksheets.add(spec.sheetName);
  const sorted = [...records].sort((a, b) => a.params_B - b.params_B);
  sheet.getRange("A1:E1").values = [[
    "Model",
    "No-embedding params",
    "Embedding params",
    "No-embedding params (Mimir)",
    "Embedding params (Mimir)",
  ]];
  const rows = sorted.map((record) => {
    const noEmb = sourceFormula("D", record.sourceRow);
    const emb = `='Source'!$C$${record.sourceRow}-'Source'!$D$${record.sourceRow}`;
    return [
      sourceFormula("B", record.sourceRow),
      record.model === MIMIR ? "=\"\"" : noEmb,
      record.model === MIMIR ? "=\"\"" : emb,
      record.model === MIMIR ? noEmb : "=\"\"",
      record.model === MIMIR ? emb : "=\"\"",
    ];
  });
  sheet.getRange(`A2:E${records.length + 1}`).formulas = rows;
  sheet.getRange(`B2:E${records.length + 1}`).format.numberFormat = "0.00";
  setSheetLayout(sheet, "E");

  const chart = sheet.charts.add("bar", {
    title: spec.title,
    titleTextStyle: { fontSize: 14 },
    hasLegend: true,
    legend: { position: "bottom", textStyle: { fontSize: 9 } },
    barOptions: { direction: "bar", grouping: "stacked", gapWidth: 45, overlap: 100 },
    xAxis: { axisType: "textAxis", orientation: "maxMin", textStyle: { fontSize: 9 } },
    yAxis: {
      min: 0,
      numberFormatCode: "0.0",
      title: { text: spec.axisTitle, textStyle: { fontSize: 10 } },
      textStyle: { fontSize: 9 },
      majorGridlines: { fill: "#D9E2EC", style: "solid", width: 0.5 },
    },
    dataLabels: { showValue: false },
    from: { row: 1, col: 5 },
    extent: { widthPx: 1320, heightPx: 1480 },
  });
  const categories = `'${spec.sheetName}'!$A$2:$A$${records.length + 1}`;
  const seriesSpecs = [
    ["No-embedding params", "B", BLUE],
    ["Embedding params", "C", BLUE_LIGHT],
    ["No-embedding params (Mimir)", "D", RED],
    ["Embedding params (Mimir)", "E", RED_LIGHT],
  ];
  for (const [name, column, color] of seriesSpecs) {
    const series = chart.series.add(name);
    series.categoryFormula = categories;
    series.formula = `'${spec.sheetName}'!$${column}$2:$${column}$${records.length + 1}`;
    series.valuesFormatCode = "0.00";
    series.fill = { type: "solid", color };
  }
  return sheet;
}

const chartSheets = [];
for (const spec of specs) {
  chartSheets.push(spec.key === "params_B" ? addSizeSheet(spec) : addPerformanceSheet(spec));
  console.error(`stage: added ${spec.sheetName}`);
}

const sourceCheck = await workbook.inspect({
  kind: "table",
  range: `Source!A1:I${records.length + 1}`,
  include: "values,formulas",
  tableMaxRows: 6,
  tableMaxCols: 9,
  maxChars: 7000,
});
console.log(sourceCheck.ndjson);

const drawingCheck = await workbook.inspect({ kind: "drawing", maxChars: 9000 });
console.log(drawingCheck.ndjson);

const errorCheck = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
  maxChars: 4000,
});
console.log(errorCheck.ndjson);
console.error("stage: inspections complete");

for (let i = 0; i < specs.length; i += 1) {
  const spec = specs[i];
  const sheet = chartSheets[i];
  const range = spec.key === "params_B" ? "F1:S55" : "D1:Q55";
  const preview = await workbook.render({ sheetName: sheet.name, range, scale: 1, format: "png" });
  await fs.writeFile(path.join(outputDir, spec.fileName), new Uint8Array(await preview.arrayBuffer()));
  console.error(`stage: rendered ${spec.sheetName}`);
}

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(path.join(outputDir, "summary_by_category_charts.xlsx"));
console.error("stage: exported workbook");
