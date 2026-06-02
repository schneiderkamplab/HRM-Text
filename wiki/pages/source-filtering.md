# Source Filtering

Last updated: 2026-06-01
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

Current policy: for EU academic/non-commercial research by a qualifying
research organisation, the working copyright basis is the DSM Directive Article
3 text-and-data-mining exception when dataset access is lawful. Licensing,
ShareAlike, and benchmark adjacency are not blockers by themselves. GDPR/PII
risk involving non-public persons remains the hard exclusion criterion.

Denied by exact/pattern rules:

- `sapient_cleaned/data/Platypus/reclor.jsonl`
- `sapient_cleaned/data/Platypus/scibench.jsonl`
- high-GDPR/PII-risk Sapient FLAN user/chat/social/review/toxicity patterns,
  including tweet/twitter, dialog/persona/chat, hate/toxicity/offensive,
  SMS/email, Amazon/Yelp/IMDb/review-style sources, and similar user-generated
  text families.
- high-GDPR/PII-risk Sapient Tasksource user/chat/social/review/toxicity
  patterns, including tweet/twitter, WNUT, SMS/spam, hate/offensive/toxicity,
  dialogue/switchboard/MRDA/mutual/persona, and review-style sources.
- cache/git metadata

## Allow Overrides

Allow overrides run before deny patterns. They remain in the config for
documentation and for exact source recovery, but broad FLAN/Tasksource are no
longer denied solely because they are aggregators.

FLAN allow back:

- math/science reasoning: `gsm8k`, `mathqa`, `aqua`, `qasc`, `openbookqa`, `sciq`, `strategyqa`, `quartz`
- commonsense benchmarks: `copa`, `xcopa`, `piqa`, `hellaswag`, `story_cloze`, `winogrande`

Tasksource allow back:

- NLI/logic/reasoning: `fracas`, `conj_nli`, `temporal-nli`, `robust_nli_*`, `monotonicity-entailment`, `balanced-copa`, `nli_fever`, `ruletaker`, `WANLI`, `probability_words_nli_*`, `ConTRoL-nli`, `e-CARE`, `vitaminc_*`, `commonsense_qa_2.0`, `folio`, `naturallogic`, `add_one_rte`, `fig-qa`, `PARARULE-Plus`, `logiqa*`, `tomi-nli`
- science/medical/citation: `scicite`, `scifact*`, `scinli`, `citation_intent`, `scientific-exaggeration-detection`, `MedQA-USMLE-4-options-hf`, `medmcqa`, `wikimedqa_medwiki`

## Latest Reported Build

Latest rebuild after the 2026-06-01 harsh-robots exclusion update:

```text
Allowed files:      9,780
Denied files:       389
Allowed bytes:      806,841,101,662
```

Denied data files now split into:

- Sapient FLAN PII/social/chat/review/opinion/spam and harsh-robots residual:
  `364`
- Sapient Tasksource PII/social/chat/review/ReClor residual: `23`
- Sapient Platypus eval-only exclusions: `2` (`reclor`, `scibench`)

Harsh-robots FLAN exclusions added on 2026-06-01:

- `natural_questions_open` / `naturalquestion`, because Google disallows search
  endpoints and these are treated as search-derived.
- `msmarco`, because Bing disallows many search endpoints and these are treated
  as search-derived.
- `wmt` and `newscomm`, because `data.statmt.org` disallows `User-agent: *` at
  `/`.

`synquid/wildchat-100k-qwen-messages` remains included with a tight cap by
project decision, despite user-prompt PII risk, and should be scrubbed later.
