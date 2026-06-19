# DFM5 L eval comparison

Values are percent-style scores where applicable. `—` means no comparable value. Model-card L/XL values are only available for the standard README benchmarks. Qwen3.5 2B values use the local clean Qwen run artifacts where available, including the fixed GSM8K rerun, and fall back to HRM-Text arXiv v1 Table 4 for missing standard metrics. Qwen3.5 9B has official Qwen model-card results for adjacent newer benchmarks, but no same-suite HRM-Text standard row was found, so the table column is left unavailable.

Original Sapient L uses EMA/default evaluation sources: full epoch-wise standard eval logs, epoch-wise EuroEval JSONL files, and the default/EMA local DFM-evals artifacts. The original DFM-evals artifacts are lite/sharded-local rows, so use them directionally for non-standard metrics. No `*_noema_*` artifacts are used.

Qwen3.5 9B official adjacent language benchmarks from the model card: MMLU-Pro 82.5, MMLU-Redux 91.1, C-Eval 88.2, SuperGPQA 58.2, GPQA Diamond 81.7, IFEval 91.5, IFBench 64.5, Global PIQA 83.2, WMT24++ 72.6. These are not inserted into the main rows because they are not the same benchmark/configuration as the HRM-Text standard table.

## Danish

| Metric | DFM5-L 50K | DFM5-L 100K | DFM5-L 150K | DFM5-L 200K | DFM5-L 250K | DFM5-L 300K | DFM5-L 350K | DFM5-L 400K | DFM5-L 450K | Orig Sapient L e1 EMA | Orig Sapient L e2 EMA | Orig Sapient L e3 EMA | Orig Sapient L e4 EMA | Card L | Card XL | Qwen3.5 2B | Qwen3.5 9B |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| DaLA macro F1 | 33.8 | 0.0 | 0.0 | 0.0 | 0.0 | 12.7 | 10.4 | 44.5 | 27.2 | 3.8 | 0.4 | 0.1 | 0.4 | — | — | 36.4 | — |
| Danish Citizen Tests acc | 34.7 | 45.7 | 50.8 | 54.7 | 58.9 | 59.8 | 60.4 | 59.8 | 61.1 | 0.6 | 17.6 | 16.0 | 13.0 | — | — | 57.1 | — |
| GEC-DaLA exact match | 3.9 | 32.4 | 31.9 | 31.8 | 35.4 | 33.1 | 3.0 | 30.9 | 6.8 | 0.0 | 0.0 | 0.0 | 0.0 | — | — | 8.0 | — |
| Talemaader judged acc | 0.8 | 2.4 | 8.2 | 9.3 | 8.2 | 13.9 | 0.0 | 0.2 | 0.1 | 0.0 | 0.0 | 0.0 | 0.0 | — | — | 0.0 | — |
| IFEval-DA final acc | 26.5 | 31.8 | 40.3 | 44.6 | 44.9 | 45.4 | 50.5 | 49.7 | 45.4 | 22.8 | 31.4 | 20.5 | 28.4 | — | — | 56.0 | — |
| MultiWikiQA exact match | 55.4 | 74.3 | 75.9 | 74.6 | 76.1 | 75.4 | 72.7 | 67.4 | 70.9 | 0.0 | 0.9 | 5.4 | 9.1 | — | — | 49.2 | — |
| NordjyllandNews BERTScore | 88.6 | 89.1 | 89.3 | 88.8 | 88.9 | 88.4 | 88.6 | 88.1 | 88.6 | 85.0 | 86.3 | 86.6 | 86.4 | — | — | 86.2 | — |
| PIQA-da acc | 16.7 | 38.9 | 44.4 | 35.2 | 50.0 | 39.8 | 50.9 | 55.6 | 38.0 | 0.0 | 0.0 | 0.0 | 3.7 | — | — | 25.0 | — |
| WMT24++ en-da chrF++ | 42.1 | 49.0 | 50.3 | 51.2 | 50.9 | 50.0 | 49.3 | 49.5 | 50.6 | 20.3 | 23.3 | 23.8 | 24.9 | — | — | 45.7 | — |
| EuroEval Angry Tweets macro F1 | 19.6 | 42.4 | 58.8 | 64.5 | 62.6 | 64.8 | 67.9 | 66.4 | 66.6 | 30.1 | 33.5 | 35.7 | 28.1 | — | — | 57.8 | — |
| EuroEval ScaLA-da macro F1 | 34.0 | 42.8 | 50.0 | 56.3 | 63.9 | 66.2 | 68.0 | 70.5 | 70.7 | 34.1 | 44.3 | 44.1 | 38.7 | — | — | 37.1 | — |
| EuroEval DaNSK NER micro F1 | 7.8 | 13.1 | 27.0 | 24.8 | 34.7 | 32.8 | 34.7 | 36.1 | 35.8 | 0.0 | 0.0 | 0.0 | 0.0 | — | — | 28.6 | — |
| EuroEval MultiWikiQA-da F1 | 67.8 | 79.2 | 84.3 | 82.2 | 83.7 | 81.8 | 83.3 | 81.5 | 81.6 | 4.3 | 28.6 | 25.6 | 35.0 | — | — | 73.0 | — |
| EuroEval NordjyllandNews chrF++ | 27.9 | 33.0 | 32.6 | 34.7 | 35.0 | 35.5 | 35.4 | 32.5 | 33.6 | 1.0 | 21.7 | 20.6 | 18.2 | — | — | 36.1 | — |
| EuroEval Talemaader acc | 21.7 | 9.4 | 8.9 | 18.4 | 15.8 | 20.3 | 25.6 | 31.6 | 36.2 | 38.3 | 21.1 | 28.1 | 17.0 | — | — | 54.1 | — |
| EuroEval Citizen Tests acc | 39.3 | 47.0 | 50.7 | 53.0 | 56.3 | 56.1 | 52.1 | 55.2 | 55.9 | 31.3 | 40.2 | 43.1 | 40.1 | — | — | 54.4 | — |
| EuroEval HellaSwag-da acc | 24.9 | 26.3 | 30.4 | 33.1 | 37.8 | 36.4 | 42.4 | 43.1 | 44.3 | 24.8 | 23.8 | 25.5 | 26.7 | — | — | 41.6 | — |
| EuroEval IFEval-da instr acc | 31.2 | 37.4 | 46.0 | 49.4 | 51.1 | 50.4 | 56.9 | 54.8 | 51.5 | 28.1 | 27.4 | 30.0 | 28.3 | — | — | 58.6 | — |
| EuroEval VaLEU-da | 1.0 | 27.8 | 1.1 | 18.3 | 15.1 | — | 26.6 | — | 21.6 | 19.7 | — | 12.9 | 16.7 | — | — | 7.7 | — |
| **Danish average** | **32.0** | **38.6** | **43.3** | **44.8** | **47.5** | **47.9** | **47.3** | **51.0** | **48.1** | **18.0** | **22.3** | **22.5** | **22.1** | — | — | — | — |

## English

| Metric | DFM5-L 50K | DFM5-L 100K | DFM5-L 150K | DFM5-L 200K | DFM5-L 250K | DFM5-L 300K | DFM5-L 350K | DFM5-L 400K | DFM5-L 450K | Orig Sapient L e1 EMA | Orig Sapient L e2 EMA | Orig Sapient L e3 EMA | Orig Sapient L e4 EMA | Card L | Card XL | Qwen3.5 2B | Qwen3.5 9B |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ARC-C acc | 25.2 | 38.8 | 49.2 | 52.5 | 58.1 | 61.9 | 64.2 | 66.6 | 68.0 | 45.8 | 62.9 | 69.6 | 72.8 | 75.9 | 81.9 | 60.6 | — |
| BoolQ acc | 58.2 | 70.6 | 77.9 | 80.0 | 82.1 | 83.7 | 84.3 | 84.3 | 82.5 | 72.6 | 82.1 | 83.7 | 84.6 | 85.0 | 86.2 | 79.0 | — |
| DROP F1 | 20.2 | 46.8 | 64.4 | 70.6 | 74.0 | 74.6 | 75.3 | 76.8 | 77.4 | 58.7 | 73.6 | 76.4 | 78.2 | 78.6 | 82.3 | 29.5 | — |
| HellaSwag acc | 30.0 | 32.4 | 36.8 | 41.1 | 43.0 | 45.4 | 47.1 | 48.1 | 50.7 | 32.3 | 41.4 | 47.3 | 50.9 | 52.7 | 63.4 | 28.5 | — |
| MMLU acc | 29.5 | 38.0 | 42.9 | 46.2 | 47.6 | 49.8 | 50.6 | 51.6 | 52.5 | 41.8 | 50.7 | 53.2 | 55.2 | 56.6 | 60.7 | 27.3 | — |
| Winogrande acc | 50.8 | 50.1 | 54.9 | 58.6 | 61.0 | 62.1 | 63.1 | 62.1 | 63.6 | 54.2 | 64.2 | 66.5 | 66.7 | 67.6 | 72.4 | 51.9 | — |
| GovReport BERTScore | 8.8 | 8.8 | 8.8 | 8.8 | 8.9 | 8.9 | 8.9 | 8.8 | 8.8 | 5.5 | 5.5 | 5.6 | 5.7 | — | — | 85.3 | — |
| EuroEval SST-5 macro F1 | 46.7 | 53.1 | 65.8 | 64.9 | 67.5 | 67.1 | 72.4 | 71.3 | 70.6 | 67.2 | 66.0 | 70.0 | 71.0 | — | — | 64.8 | — |
| EuroEval ScaLA-en macro F1 | 45.6 | 45.4 | 52.0 | 45.9 | 61.3 | 67.3 | 72.8 | 72.9 | 77.0 | 42.3 | 50.9 | 49.7 | 67.6 | — | — | 73.5 | — |
| EuroEval CoNLL-en NER micro F1 | 7.4 | 30.9 | 46.5 | 49.4 | 50.0 | 54.5 | 60.0 | 56.5 | 55.9 | 0.0 | 0.0 | 0.0 | 0.0 | — | — | 51.6 | — |
| EuroEval SQuAD F1 | 68.8 | 85.2 | 85.9 | 86.9 | 88.1 | 88.9 | 89.0 | 88.1 | 89.8 | 86.8 | 90.7 | 91.4 | 91.8 | — | — | 80.7 | — |
| EuroEval CNN/DM chrF++ | 20.9 | 29.1 | 30.6 | 33.3 | 34.3 | 35.3 | 35.0 | 35.2 | 38.7 | 31.9 | 35.3 | 33.9 | 33.9 | — | — | 41.9 | — |
| EuroEval Life in UK acc | 28.4 | 38.1 | 41.0 | 44.4 | 45.4 | 44.0 | 47.7 | 50.5 | 50.6 | 39.3 | 48.5 | 52.6 | 54.3 | — | — | 71.1 | — |
| EuroEval HellaSwag acc | 22.0 | 25.3 | 32.8 | 34.6 | 46.3 | 42.4 | 46.2 | 46.2 | 49.4 | 32.7 | 39.0 | 48.0 | 50.7 | — | — | 48.6 | — |
| EuroEval IFEval instr acc | 46.7 | 57.8 | 64.8 | 61.4 | 67.2 | 65.7 | 70.4 | 67.3 | 66.6 | 32.3 | 36.1 | 35.0 | 38.8 | — | — | 73.2 | — |
| EuroEval VaLEU-en | 30.1 | 0.3 | 1.5 | 18.1 | 91.1 | 56.0 | 12.0 | 47.4 | 2.9 | 15.6 | 14.2 | 7.8 | 1.5 | — | — | 80.3 | — |
| **English average** | **33.9** | **43.4** | **50.3** | **51.9** | **55.7** | **56.8** | **59.1** | **59.1** | **60.1** | **42.9** | **49.8** | **52.2** | **54.8** | — | — | — | — |

## Math & Code

| Metric | DFM5-L 50K | DFM5-L 100K | DFM5-L 150K | DFM5-L 200K | DFM5-L 250K | DFM5-L 300K | DFM5-L 350K | DFM5-L 400K | DFM5-L 450K | Orig Sapient L e1 EMA | Orig Sapient L e2 EMA | Orig Sapient L e3 EMA | Orig Sapient L e4 EMA | Card L | Card XL | Qwen3.5 2B | Qwen3.5 9B |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| GSM8k acc | 5.5 | 10.5 | 18.7 | 24.1 | 28.0 | 29.7 | 32.0 | 31.5 | 33.4 | 57.9 | 72.2 | 77.8 | 78.0 | 77.6 | 84.7 | 66.6 | — |
| MATH acc | 14.3 | 28.2 | 35.9 | 40.2 | 42.5 | 44.4 | 44.9 | 45.9 | 47.1 | 34.6 | 45.2 | 47.9 | 50.1 | 51.2 | 56.5 | 50.8 | — |
| HumanEval pass rate | 6.1 | 17.7 | 23.2 | 25.0 | 29.9 | 32.9 | 27.4 | 30.5 | 31.1 | 0.0 | 0.0 | 0.0 | 0.0 | — | — | 47.6 | — |
| EuroEval BFCL-v2 tool acc | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | — | — | 52.1 | — |
| **Math & Code average** | **6.5** | **14.1** | **19.5** | **22.3** | **25.1** | **26.8** | **26.1** | **27.0** | **27.9** | **23.1** | **29.4** | **31.4** | **32.0** | — | — | — | — |
