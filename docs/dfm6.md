# DFM6 eval comparison

Values are percent-style scores where applicable. `—` means no comparable value. DFM6 checkpoint columns use local DFM6 artifacts. The DFM5-L 900K column is included immediately before the Original Sapient L comparison columns. Model-card L/XL values and Qwen3.5 comparison columns match the DFM5 report.

DFM6-XL-gas2 is evaluated with the Gemma-native chat template for standard vLLM prompts and for vLLM server based DFM/EuroEval jobs.

Original Sapient L uses EMA/default evaluation sources: full epoch-wise standard eval logs, epoch-wise EuroEval JSONL files, and the default/EMA local DFM-evals artifacts. The original DFM-evals artifacts are lite/sharded-local rows, so use them directionally for non-standard metrics. No `*_noema_*` artifacts are used.

Qwen3.5 9B official adjacent language benchmarks from the model card: MMLU-Pro 82.5, MMLU-Redux 91.1, C-Eval 88.2, SuperGPQA 58.2, GPQA Diamond 81.7, IFEval 91.5, IFBench 64.5, Global PIQA 83.2, WMT24++ 72.6. These are not inserted into the main rows because they are not the same benchmark/configuration as the HRM-Text standard table.

## Danish

| Metric | DFM6-XL-gas2 50K | DFM6-XL-gas2 100K | DFM6-XL-gas2 150K | DFM6-XL-gas2 200K | DFM6-XL-gas2 250K | DFM6-XL-gas2 300K | DFM6-XL-gas2 350K | DFM6-XL-gas2 400K | DFM6-XL-gas2 450K | DFM5-L 900K | Orig Sapient L e1 EMA | Orig Sapient L e2 EMA | Orig Sapient L e3 EMA | Orig Sapient L e4 EMA | Card L | Card XL | Qwen3.5 2B | Qwen3.5 9B |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| DaLA macro F1 | 38.3 | 39.5 | 52.5 | — | — | — | — | — | — | 36.6 | 3.8 | 0.4 | 0.1 | 0.4 | — | — | 36.4 | — |
| Danish Citizen Tests acc | 35.2 | 35.6 | 43.9 | — | — | — | — | — | — | 62.6 | 0.6 | 17.6 | 16.0 | 13.0 | — | — | 57.1 | — |
| GEC-DaLA exact match | 0.0 | 0.0 | 0.0 | — | — | — | — | — | — | 24.6 | 0.0 | 0.0 | 0.0 | 0.0 | — | — | 8.0 | — |
| Talemaader judged acc | 0.0 | 0.0 | 0.0 | — | — | — | — | — | — | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | — | — | 0.0 | — |
| IFEval-DA final acc | 31.1 | 39.5 | 48.8 | — | — | — | — | — | — | 49.1 | 22.8 | 31.4 | 20.5 | 28.4 | — | — | 56.0 | — |
| MultiWikiQA exact match | 0.0 | 0.3 | 0.5 | — | — | — | — | — | — | 70.5 | 0.0 | 0.9 | 5.4 | 9.1 | — | — | 49.2 | — |
| NordjyllandNews BERTScore | 87.0 | 87.3 | 87.5 | — | — | — | — | — | — | 88.4 | 85.0 | 86.3 | 86.6 | 86.4 | — | — | 86.2 | — |
| PIQA-da acc | 40.7 | 36.1 | 29.6 | — | — | — | — | — | — | 49.1 | 0.0 | 0.0 | 0.0 | 3.7 | — | — | 25.0 | — |
| WMT24++ en-da chrF++ | 26.9 | 28.2 | 30.0 | — | — | — | — | — | — | 52.4 | 20.3 | 23.3 | 23.8 | 24.9 | — | — | 45.7 | — |
| EuroEval Angry Tweets macro F1 | 45.1 | 52.2 | 51.6 | — | — | — | — | — | — | 70.4 | 30.1 | 33.5 | 35.7 | 28.1 | — | — | 57.8 | — |
| EuroEval ScaLA-da macro F1 | 34.1 | 33.9 | 35.3 | — | — | — | — | — | — | 62.0 | 34.1 | 44.3 | 44.1 | 38.7 | — | — | 37.1 | — |
| EuroEval DaNSK NER micro F1 | 1.9 | 22.8 | 31.1 | — | — | — | — | — | — | 39.1 | 0.0 | 0.0 | 0.0 | 0.0 | — | — | 28.6 | — |
| EuroEval MultiWikiQA-da F1 | 28.6 | 33.1 | 35.4 | — | — | — | — | — | — | 80.7 | 4.3 | 28.6 | 25.6 | 35.0 | — | — | 73.0 | — |
| EuroEval NordjyllandNews chrF++ | 31.5 | 31.2 | 30.8 | — | — | — | — | — | — | 31.2 | 1.0 | 21.7 | 20.6 | 18.2 | — | — | 36.1 | — |
| EuroEval Talemaader acc | 21.2 | 21.4 | 20.8 | — | — | — | — | — | — | 40.6 | 38.3 | 21.1 | 28.1 | 17.0 | — | — | 54.1 | — |
| EuroEval Citizen Tests acc | 38.9 | 39.2 | 39.8 | — | — | — | — | — | — | 62.2 | 31.3 | 40.2 | 43.1 | 40.1 | — | — | 54.4 | — |
| EuroEval HellaSwag-da acc | 25.5 | 25.1 | 25.2 | — | — | — | — | — | — | 45.5 | 24.8 | 23.8 | 25.5 | 26.7 | — | — | 41.6 | — |
| EuroEval IFEval-da instr acc | 37.0 | 46.0 | 55.2 | — | — | — | — | — | — | 54.8 | 28.1 | 27.4 | 30.0 | 28.3 | — | — | 58.6 | — |
| EuroEval VaLEU-da | — | — | — | — | — | — | — | — | — | — | 19.7 | — | 12.9 | 16.7 | — | — | 7.7 | — |
| **Danish average** | **29.1** | **31.7** | **34.3** | — | — | — | — | — | — | **51.1** | **18.0** | **22.3** | **22.5** | **22.1** | — | — | — | — |

## English

| Metric | DFM6-XL-gas2 50K | DFM6-XL-gas2 100K | DFM6-XL-gas2 150K | DFM6-XL-gas2 200K | DFM6-XL-gas2 250K | DFM6-XL-gas2 300K | DFM6-XL-gas2 350K | DFM6-XL-gas2 400K | DFM6-XL-gas2 450K | DFM5-L 900K | Orig Sapient L e1 EMA | Orig Sapient L e2 EMA | Orig Sapient L e3 EMA | Orig Sapient L e4 EMA | Card L | Card XL | Qwen3.5 2B | Qwen3.5 9B |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ARC-C acc | 27.6 | 37.2 | 48.0 | — | — | — | — | — | — | 71.6 | 45.8 | 62.9 | 69.6 | 72.8 | 75.9 | 81.9 | 60.6 | — |
| BoolQ acc | 43.7 | 69.4 | 76.0 | — | — | — | — | — | — | 86.0 | 72.6 | 82.1 | 83.7 | 84.6 | 85.0 | 86.2 | 79.0 | — |
| DROP F1 | 4.5 | 4.4 | 4.7 | — | — | — | — | — | — | 78.4 | 58.7 | 73.6 | 76.4 | 78.2 | 78.6 | 82.3 | 29.5 | — |
| HellaSwag acc | 27.4 | 31.7 | 38.2 | — | — | — | — | — | — | 55.4 | 32.3 | 41.4 | 47.3 | 50.9 | 52.7 | 63.4 | 28.5 | — |
| MMLU acc | 31.0 | 37.2 | 43.0 | — | — | — | — | — | — | 55.1 | 41.8 | 50.7 | 53.2 | 55.2 | 56.6 | 60.7 | 27.3 | — |
| Winogrande acc | 49.2 | 53.0 | 57.5 | — | — | — | — | — | — | 66.8 | 54.2 | 64.2 | 66.5 | 66.7 | 67.6 | 72.4 | 51.9 | — |
| GovReport BERTScore | 83.8 | 85.4 | 86.0 | — | — | — | — | — | — | 86.1 | 5.5 | 5.5 | 5.6 | 5.7 | — | — | 85.3 | — |
| EuroEval SST-5 macro F1 | 32.4 | 46.2 | 66.0 | — | — | — | — | — | — | 72.8 | 67.2 | 66.0 | 70.0 | 71.0 | — | — | 64.8 | — |
| EuroEval ScaLA-en macro F1 | 36.8 | 35.6 | 62.0 | — | — | — | — | — | — | 71.9 | 42.3 | 50.9 | 49.7 | 67.6 | — | — | 73.5 | — |
| EuroEval CoNLL-en NER micro F1 | 12.9 | 34.2 | 43.4 | — | — | — | — | — | — | 61.8 | 0.0 | 0.0 | 0.0 | 0.0 | — | — | 51.6 | — |
| EuroEval SQuAD F1 | 25.3 | 28.2 | 41.6 | — | — | — | — | — | — | 88.8 | 86.8 | 90.7 | 91.4 | 91.8 | — | — | 80.7 | — |
| EuroEval CNN/DM chrF++ | 33.9 | 35.8 | 38.8 | — | — | — | — | — | — | 37.8 | 31.9 | 35.3 | 33.9 | 33.9 | — | — | 41.9 | — |
| EuroEval Life in UK acc | 29.0 | 29.0 | 29.2 | — | — | — | — | — | — | 48.9 | 39.3 | 48.5 | 52.6 | 54.3 | — | — | 71.1 | — |
| EuroEval HellaSwag acc | 21.5 | 22.2 | 22.0 | — | — | — | — | — | — | 49.6 | 32.7 | 39.0 | 48.0 | 50.7 | — | — | 48.6 | — |
| EuroEval IFEval instr acc | 47.4 | 49.8 | 55.5 | — | — | — | — | — | — | 68.2 | 32.3 | 36.1 | 35.0 | 38.8 | — | — | 73.2 | — |
| EuroEval VaLEU-en | 4.9 | 23.9 | 2.8 | — | — | — | — | — | — | 46.4 | 15.6 | 14.2 | 7.8 | 1.5 | — | — | 80.3 | — |
| **English average** | **33.7** | **40.0** | **47.5** | — | — | — | — | — | — | **66.6** | **42.9** | **49.8** | **52.2** | **54.8** | — | — | — | — |

## Math & Code

| Metric | DFM6-XL-gas2 50K | DFM6-XL-gas2 100K | DFM6-XL-gas2 150K | DFM6-XL-gas2 200K | DFM6-XL-gas2 250K | DFM6-XL-gas2 300K | DFM6-XL-gas2 350K | DFM6-XL-gas2 400K | DFM6-XL-gas2 450K | DFM5-L 900K | Orig Sapient L e1 EMA | Orig Sapient L e2 EMA | Orig Sapient L e3 EMA | Orig Sapient L e4 EMA | Card L | Card XL | Qwen3.5 2B | Qwen3.5 9B |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| GSM8k acc | 44.9 | 60.0 | 73.5 | — | — | — | — | — | — | 38.7 | 57.9 | 72.2 | 77.8 | 78.0 | 77.6 | 84.7 | 66.6 | — |
| MATH acc | 14.1 | 22.6 | 25.7 | — | — | — | — | — | — | 49.3 | 34.6 | 45.2 | 47.9 | 50.1 | 51.2 | 56.5 | 50.8 | — |
| HumanEval pass rate | 4.9 | 9.8 | 11.0 | — | — | — | — | — | — | 36.6 | 0.0 | 0.0 | 0.0 | 0.0 | — | — | 47.6 | — |
| EuroEval BFCL-v2 tool acc | 0.0 | 0.0 | 0.0 | — | — | — | — | — | — | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | — | — | 52.1 | — |
| **Math & Code average** | **16.0** | **23.1** | **27.6** | — | — | — | — | — | — | **31.2** | **23.1** | **29.4** | **31.4** | **32.0** | — | — | — | — |
