# DFM5 L eval comparison

Values are percent-style scores where applicable. `—` means no comparable value. Model-card L/XL values are only available for the standard README benchmarks.

Original Sapient L uses EMA/default evaluation sources: full epoch-wise standard eval logs, epoch-wise EuroEval JSONL files, and the default/EMA local DFM-evals artifacts. The original DFM-evals artifacts are lite/sharded-local rows, so use them directionally for non-standard metrics. No `*_noema_*` artifacts are used.

## Danish

| Metric | DFM5-L 50K | DFM5-L 100K | DFM5-L 150K | DFM5-L 200K | DFM5-L 250K | Orig Sapient L e1 EMA | Orig Sapient L e2 EMA | Orig Sapient L e3 EMA | Orig Sapient L e4 EMA | Card L | Card XL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| DaLA macro F1 | 33.8 | 0.0 | 0.0 | 0.0 | 0.0 | 3.8 | 0.4 | 0.1 | 0.4 | — | — |
| Danish Citizen Tests acc | 34.7 | 45.7 | 50.8 | 54.7 | 58.9 | 0.6 | 17.6 | 16.0 | 13.0 | — | — |
| GEC-DaLA exact match | 3.9 | 32.4 | 31.9 | 31.8 | 35.4 | 0.0 | 0.0 | 0.0 | 0.0 | — | — |
| Talemaader judged acc | 0.8 | 2.4 | 8.2 | 9.3 | 8.2 | 0.0 | 0.0 | 0.0 | 0.0 | — | — |
| IFEval-DA final acc | 26.5 | 31.8 | 40.3 | 44.6 | 44.9 | 22.8 | 31.4 | 20.5 | 28.4 | — | — |
| MultiWikiQA exact match | 55.4 | 74.3 | 75.9 | 74.6 | 76.1 | 0.0 | 0.9 | 5.4 | 9.1 | — | — |
| NordjyllandNews BERTScore | 88.6 | 89.1 | 89.3 | 88.8 | 88.9 | 85.0 | 86.3 | 86.6 | 86.4 | — | — |
| PIQA-da acc | 16.7 | 38.9 | 44.4 | 35.2 | 50.0 | 0.0 | 0.0 | 0.0 | 3.7 | — | — |
| WMT24++ en-da chrF++ | 42.1 | 49.0 | 50.3 | 51.2 | 50.9 | 20.3 | 23.3 | 23.8 | 24.9 | — | — |
| EuroEval Angry Tweets macro F1 | 19.6 | 42.4 | 58.8 | 64.5 | 62.6 | 30.1 | 33.5 | 35.7 | 28.1 | — | — |
| EuroEval ScaLA-da macro F1 | 34.0 | 42.8 | 50.0 | 56.3 | 63.9 | 34.1 | 44.3 | 44.1 | 38.7 | — | — |
| EuroEval DaNSK NER micro F1 | 7.8 | 13.1 | 27.0 | 24.8 | 34.7 | 0.0 | 0.0 | 0.0 | 0.0 | — | — |
| EuroEval MultiWikiQA-da F1 | 67.8 | 79.2 | 84.3 | 82.2 | 83.7 | 4.3 | 28.6 | 25.6 | 35.0 | — | — |
| EuroEval NordjyllandNews chrF++ | 27.9 | 33.0 | 32.6 | 34.7 | 35.0 | 1.0 | 21.7 | 20.6 | 18.2 | — | — |
| EuroEval Talemaader acc | 21.7 | 9.4 | 8.9 | 18.4 | 15.8 | 38.3 | 21.1 | 28.1 | 17.0 | — | — |
| EuroEval Citizen Tests acc | 39.3 | 47.0 | 50.7 | 53.0 | 56.3 | 31.3 | 40.2 | 43.1 | 40.1 | — | — |
| EuroEval HellaSwag-da acc | 24.9 | 26.3 | 30.4 | 33.1 | 37.8 | 24.8 | 23.8 | 25.5 | 26.7 | — | — |
| EuroEval IFEval-da instr acc | 31.2 | 37.4 | 46.0 | 49.4 | 51.1 | 28.1 | 27.4 | 30.0 | 28.3 | — | — |
| EuroEval VaLEU-da | 1.0 | 27.8 | 1.1 | 18.3 | 15.1 | 19.7 | — | 12.9 | 16.7 | — | — |
| **Danish average** | **32.0** | **38.6** | **43.3** | **44.8** | **47.5** | **18.0** | **22.3** | **22.5** | **22.1** | — | — |

## English

| Metric | DFM5-L 50K | DFM5-L 100K | DFM5-L 150K | DFM5-L 200K | DFM5-L 250K | Orig Sapient L e1 EMA | Orig Sapient L e2 EMA | Orig Sapient L e3 EMA | Orig Sapient L e4 EMA | Card L | Card XL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ARC-C acc | 25.2 | 38.8 | 49.2 | 52.5 | 58.1 | 45.8 | 62.9 | 69.6 | 72.8 | 75.9 | 81.9 |
| BoolQ acc | 58.2 | 70.6 | 77.9 | 80.0 | 82.1 | 72.6 | 82.1 | 83.7 | 84.6 | 85.0 | 86.2 |
| DROP F1 | 20.2 | 46.8 | 64.4 | 70.6 | 74.0 | 58.7 | 73.6 | 76.4 | 78.2 | 78.6 | 82.3 |
| HellaSwag acc | 30.0 | 32.4 | 36.8 | 41.1 | 43.0 | 32.3 | 41.4 | 47.3 | 50.9 | 52.7 | 63.4 |
| MMLU acc | 29.5 | 38.0 | 42.9 | 46.2 | 47.6 | 41.8 | 50.7 | 53.2 | 55.2 | 56.6 | 60.7 |
| Winogrande acc | 50.8 | 50.1 | 54.9 | 58.6 | 61.0 | 54.2 | 64.2 | 66.5 | 66.7 | 67.6 | 72.4 |
| GovReport BERTScore | 8.8 | 8.8 | 8.8 | 8.8 | 8.9 | 5.5 | 5.5 | 5.6 | 5.7 | — | — |
| EuroEval SST-5 macro F1 | 46.7 | 53.1 | 65.8 | 64.9 | 67.5 | 67.2 | 66.0 | 70.0 | 71.0 | — | — |
| EuroEval ScaLA-en macro F1 | 45.6 | 45.4 | 52.0 | 45.9 | 61.3 | 42.3 | 50.9 | 49.7 | 67.6 | — | — |
| EuroEval CoNLL-en NER micro F1 | 7.4 | 30.9 | 46.5 | 49.4 | 50.0 | 0.0 | 0.0 | 0.0 | 0.0 | — | — |
| EuroEval SQuAD F1 | 68.8 | 85.2 | 85.9 | 86.9 | 88.1 | 86.8 | 90.7 | 91.4 | 91.8 | — | — |
| EuroEval CNN/DM chrF++ | 20.9 | 29.1 | 30.6 | 33.3 | 34.3 | 31.9 | 35.3 | 33.9 | 33.9 | — | — |
| EuroEval Life in UK acc | 28.4 | 38.1 | 41.0 | 44.4 | 45.4 | 39.3 | 48.5 | 52.6 | 54.3 | — | — |
| EuroEval HellaSwag acc | 22.0 | 25.3 | 32.8 | 34.6 | 46.3 | 32.7 | 39.0 | 48.0 | 50.7 | — | — |
| EuroEval IFEval instr acc | 46.7 | 57.8 | 64.8 | 61.4 | 67.2 | 32.3 | 36.1 | 35.0 | 38.8 | — | — |
| EuroEval VaLEU-en | 30.1 | 0.3 | 1.5 | 18.1 | 91.1 | 15.6 | 14.2 | 7.8 | 1.5 | — | — |
| **English average** | **33.9** | **43.4** | **50.3** | **51.9** | **55.7** | **42.9** | **49.8** | **52.2** | **54.8** | — | — |

## Math & Code

| Metric | DFM5-L 50K | DFM5-L 100K | DFM5-L 150K | DFM5-L 200K | DFM5-L 250K | Orig Sapient L e1 EMA | Orig Sapient L e2 EMA | Orig Sapient L e3 EMA | Orig Sapient L e4 EMA | Card L | Card XL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| GSM8k acc | 5.5 | 10.5 | 18.7 | 24.1 | 28.0 | 57.9 | 72.2 | 77.8 | 78.0 | 77.6 | 84.7 |
| MATH acc | 14.3 | 28.2 | 35.9 | 40.2 | 42.5 | 34.6 | 45.2 | 47.9 | 50.1 | 51.2 | 56.5 |
| HumanEval pass rate | 6.1 | 17.7 | 23.2 | 25.0 | 29.9 | 0.0 | 0.0 | 0.0 | 0.0 | — | — |
| EuroEval BFCL-v2 tool acc | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | — | — |
| **Math & Code average** | **6.5** | **14.1** | **19.5** | **22.3** | **25.1** | **23.1** | **29.4** | **31.4** | **32.0** | — | — |
