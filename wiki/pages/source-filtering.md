# Source Filtering

Last updated: 2026-05-20  
Confidence: high  
Scope: Filtering downloaded sources before conversion/tokenization.

## Files

- Config: `config/data/source_filter.yaml`
- Builder: `scripts/build_filtered_source_tree.py`
- Input root: `data/downloads/datasets`
- Output root: `data/filtered_sources`

## Command

```bash
cd /work/dfm/HRM-Text
python scripts/build_filtered_source_tree.py --force
```

This creates a symlink tree. The Rust tokenizer should not consume this tree directly; conversion should run first.

## Denied Sapient Sources

Denied by exact/broad patterns:

- `sapient_cleaned/data/Platypus/reclor.jsonl`
- `sapient_cleaned/data/Platypus/scibench.jsonl`
- `sapient_cleaned/data/Platypus/scienceqa.jsonl`
- `sapient_cleaned/data_clustered/flan/**`
- `sapient_cleaned/data_clustered/tasksource/**`
- cache/git metadata

## Allow Overrides

Allow overrides run before deny patterns.

FLAN allow back:

- math/science reasoning: `gsm8k`, `mathqa`, `aqua`, `qasc`, `openbookqa`, `sciq`, `strategyqa`, `quartz`
- commonsense benchmarks: `copa`, `xcopa`, `piqa`, `hellaswag`, `story_cloze`, `winogrande`

Tasksource allow back:

- NLI/logic/reasoning: `fracas`, `conj_nli`, `temporal-nli`, `robust_nli_*`, `monotonicity-entailment`, `balanced-copa`, `nli_fever`, `ruletaker`, `WANLI`, `probability_words_nli_*`, `ConTRoL-nli`, `e-CARE`, `vitaminc_*`, `commonsense_qa_2.0`, `folio`, `naturallogic`, `add_one_rte`, `fig-qa`, `PARARULE-Plus`, `logiqa*`, `tomi-nli`
- science/medical/citation: `scicite`, `scifact*`, `scinli`, `citation_intent`, `scientific-exaggeration-detection`, `MedQA-USMLE-4-options-hf`, `medmcqa`, `wikimedqa_medwiki`

## Latest Reported Build

User reported:

```text
Allowed files:      1,525
Denied files:       4,073
Allowed bytes:      248,502,793,134
```

Earlier allow overrides recovered approximately:

- FLAN: 280 files, about 789 MB
- Tasksource: 40 files, about 99 MB

