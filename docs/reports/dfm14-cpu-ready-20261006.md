# DFM14 CPU Preparation and GPU Handoff

Status: CPU preparation complete for the instruction/grounding audit campaign and six-family generation calibration. No GPU calls, acceptance, publication, tokenization or training integration are claimed.

| Language | Instruction/chat candidates | Wikipedia documents | Added grounding rows | Audit-ready chat | Audit-ready transformations |
|---|---:|---:|---:|---:|---:|
| Irish | 54,730 | 11,358 | 18,684 | 54,693 | 73,086 |
| Maltese | 46,867 | 5,359 | 43,333 | 46,867 | 137,598 |
| Macedonian | 60,687 | 33,871 | 1,922 | 60,687 | 86,284 |
| Basque | 81,904 | 27,322 | 742 | 81,407 | 57,904 |
| Galician | 90,218 | 18,099 | 700 | 90,211 | 42,368 |
| Welsh | 46,968 | 17,771 | 646 | 46,968 | 45,485 |
| Russian | 80,048 | 150,439 | 124,272 | 80,043 | 675,095 |
| Turkish | 47,486 | 30,507 | 6,427 | 47,484 | 85,957 |
| Chinese | 30,634 | 59,874 | 115,510 | 30,591 | 435,738 |
| Arabic | 34,914 | 109,952 | 35,851 | 34,907 | 373,585 |
| Japanese | 41,261 | 143,806 | 9,400 | 41,261 | 324,250 |
| Indonesian | 20,778 | 50,694 | 1,966 | 20,778 | 101,297 |
| Korean | 97,288 | 39,288 | 22,746 | 97,285 | 157,112 |
| Hindi | 45,307 | 28,030 | 2 | 45,288 | 56,147 |
| Vietnamese | 168,637 | 26,019 | 4,702 | 168,606 | 66,335 |
| Hebrew | 43,316 | 76,833 | 52,872 | 43,316 | 371,983 |

Added grounding rows are Wikisource/EUR-Lex documents and EUbookshop paragraph windows; they are not interchangeable document counts. They are bounded samples, not full upstream sizes. All sources remain subject to semantic quality review.

Final audit: **4,080,616 rows in 8,216 chunks**, at most 500 rows/chunk, eight independent output partitions. Generation calibration: **9,600 requests**, 100 for each of six families in sixteen languages.

## Source Inventory

| Language | Source | Prepared rows |
|---|---|---:|
| Irish | `CohereLabs/aya_collection_language_split` | 39,987 |
| Irish | `CohereLabs/aya_dataset` | 1,237 |
| Irish | `OPUS/EUbookshop` | 18,669 |
| Irish | `dennlinger/eur-lex-sum` | 15 |
| Irish | `jmcinern/Dolly-V2-gle` | 13,506 |
| Irish | `wikimedia/wikipedia` | 11,358 |
| Maltese | `CohereLabs/aya_collection_language_split` | 19,997 |
| Maltese | `OPUS/EUbookshop` | 42,397 |
| Maltese | `dennlinger/eur-lex-sum` | 936 |
| Maltese | `ptrdvn/kakugo-mlt` | 6,870 |
| Maltese | `saillab/alpaca_maltese_taco` | 20,000 |
| Maltese | `wikimedia/wikipedia` | 5,359 |
| Macedonian | `CohereLabs/aya_collection_language_split` | 39,987 |
| Macedonian | `MartinV/clement-mk-handwritten` | 700 |
| Macedonian | `saillab/alpaca_macedonian_taco` | 20,000 |
| Macedonian | `wikimedia/wikipedia` | 33,871 |
| Macedonian | `wikimedia/wikisource` | 1,922 |
| Basque | `BSC-LT/ALIA-2606-SFT` | 40,973 |
| Basque | `CohereLabs/aya_dataset` | 931 |
| Basque | `orai-nlp/MagpieEU` | 40,000 |
| Basque | `wikimedia/wikipedia` | 27,322 |
| Basque | `wikimedia/wikisource` | 742 |
| Galician | `BSC-LT/ALIA-2606-SFT` | 39,011 |
| Galician | `proxectonos/galician-gec-corpora` | 51,207 |
| Galician | `wikimedia/wikipedia` | 18,099 |
| Galician | `wikimedia/wikisource` | 700 |
| Welsh | `CohereLabs/aya_collection_language_split` | 19,997 |
| Welsh | `ptrdvn/kakugo-cym` | 6,971 |
| Welsh | `saillab/alpaca_welsh_taco` | 20,000 |
| Welsh | `wikimedia/wikipedia` | 17,771 |
| Welsh | `wikimedia/wikisource` | 646 |
| Russian | `CohereLabs/aya_dataset` | 421 |
| Russian | `IlyaGusev/ru_turbo_alpaca` | 20,000 |
| Russian | `IlyaGusev/saiga_scored` | 19,628 |
| Russian | `Vikhrmodels/GrandMaster-PRO-MAX` | 39,999 |
| Russian | `wikimedia/wikipedia` | 150,439 |
| Russian | `wikimedia/wikisource` | 124,272 |
| Turkish | `CohereLabs/aya_dataset` | 4,031 |
| Turkish | `bysismo/Turkish-Python-instruction` | 3,500 |
| Turkish | `halilibr/collected-turkish-instructions-v0.1` | 19,955 |
| Turkish | `merve/turkish_instructions` | 20,000 |
| Turkish | `wikimedia/wikipedia` | 30,507 |
| Turkish | `wikimedia/wikisource` | 6,427 |
| Chinese | `CohereLabs/aya_dataset` | 4,744 |
| Chinese | `FreedomIntelligence/evol-instruct-chinese` | 20,000 |
| Chinese | `m-a-p/COIG-CQIA` | 5,890 |
| Chinese | `wikimedia/wikipedia` | 59,874 |
| Chinese | `wikimedia/wikisource` | 115,510 |
| Arabic | `CohereLabs/aya_dataset` | 4,947 |
| Arabic | `FreedomIntelligence/evol-instruct-arabic` | 20,000 |
| Arabic | `arbml/CIDAR` | 9,967 |
| Arabic | `wikimedia/wikipedia` | 109,952 |
| Arabic | `wikimedia/wikisource` | 35,851 |
| Japanese | `CohereLabs/aya_dataset` | 6,259 |
| Japanese | `kunishou/databricks-dolly-15k-ja` | 15,002 |
| Japanese | `tokyotech-llm/Swallow-Instruct-v0.1` | 20,000 |
| Japanese | `wikimedia/wikipedia` | 143,806 |
| Japanese | `wikimedia/wikisource` | 9,400 |
| Indonesian | `CohereLabs/aya_dataset` | 778 |
| Indonesian | `FreedomIntelligence/evol-instruct-indonesian` | 20,000 |
| Indonesian | `wikimedia/wikipedia` | 50,694 |
| Indonesian | `wikimedia/wikisource` | 1,966 |
| Korean | `CohereLabs/aya_dataset` | 361 |
| Korean | `FreedomIntelligence/evol-instruct-korean` | 20,000 |
| Korean | `HAERAE-HUB/HR-Instruct-Math-v0.1` | 19,997 |
| Korean | `heegyu/open-korean-instructions` | 56,930 |
| Korean | `wikimedia/wikipedia` | 39,288 |
| Korean | `wikimedia/wikisource` | 22,746 |
| Hindi | `CohereLabs/aya_dataset` | 1,139 |
| Hindi | `FreedomIntelligence/evol-instruct-hindi` | 20,000 |
| Hindi | `ai4bharat/indic-align` | 24,168 |
| Hindi | `wikimedia/wikipedia` | 28,030 |
| Hindi | `wikimedia/wikisource` | 2 |
| Vietnamese | `BlossomsAI/merged_vietnamese_instruction_dataset` | 159,993 |
| Vietnamese | `CohereLabs/aya_dataset` | 8,644 |
| Vietnamese | `wikimedia/wikipedia` | 26,019 |
| Vietnamese | `wikimedia/wikisource` | 4,702 |
| Hebrew | `BrainboxAI/medical-training-il` | 3,334 |
| Hebrew | `CohereLabs/aya_collection_language_split` | 39,982 |
| Hebrew | `wikimedia/wikipedia` | 76,833 |
| Hebrew | `wikimedia/wikisource` | 52,872 |

## Remaining Gates

- Run native-language/semantic audit and repair/re-audit; do not train on candidates.
- Complete inherited and benchmark decontamination before admission.
- Calibrate synthetic quality before assigning/launching full accepted production quotas.
- Hindi's Wikisource supplement is especially weak; unresolved transclusions are removed, and Wikipedia remains its substantive grounding pool.
- Wikisource can contain historical spelling/religious/literary text; source-grounded generation must not present historical assertions as current facts.
- EUbookshop is reconstructed from tokenized XML and requires spacing/OCR review. Preserve original document/paragraph provenance.
- Gated/unavailable instruction sources and unsupported schemas remain explicit holds in the original preparation receipts.
- Separately managed DaLA, parallel-pair production and final release/sampling are not included in this readiness claim.

## Artifacts

- `data/dfm14/gpu-ready/manifest.json`
- `data/dfm14/gpu-ready/jobs.tsv`
- `data/dfm14/gpu-ready/readiness.json`
- `data/dfm14/generation-calibration-v1/manifest.json`
- Commands and recovery contract: `dfm14/README.md`.
