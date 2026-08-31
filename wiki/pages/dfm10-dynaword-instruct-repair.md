---
type: Runbook
title: DFM10 DynaWord Instruction Repair
description: Full-row audit, prompt-only regeneration, validation, and DFM10 replacement policy for the Oliver Kinch DynaWord instruction family.
tags: [dfm10, danish, dynaword, audit, repair]
status: stable
last_updated: 2026-08-28
confidence: high
---
# DFM10 DynaWord Instruction Repair

## Source diagnosis

The four `oliverkinch/da-instruct-dynaword*` datasets contain 70,081 synthetic
prompts paired with authentic Danish DynaWord passages. The raw targets are not
teacher generations. The principal defects are prompt/target semantic mismatch,
abrupt passage extraction, and OCR corruption. Exact target overlap across the
four variants leaves 64,685 unique raw targets.

The complete E4B first pass successfully judged 70,080 rows; one base-source
row repeatedly failed constrained JSON decoding and is conservatively excluded.
It marked 68,064 rows usable under the broad rubric. The stricter admission
plan classified 61,876 rows as clean, 4,303 as eligible for prompt-only repair,
3,004 as bad/corrupt targets, 897 as incomplete targets, and the repeated judge
failure as a drop.

Although 835 incomplete passages could be found verbatim in their parent
DynaWord documents, deterministic extension was rejected after inspection
exposed page headers, OCR splits, and numbered legal clauses at candidate
boundaries. The pipeline never rewrites or extends authentic targets.

## Prompt repair and second audit

Gemma 4 31B IT regenerated only the 4,303 mismatched prompts. The verified
serving path is the `hrm` environment's vLLM `0.23.1rc1` build; vLLM `0.27.1`
in the `audit` environment exhausted a 180 GB B200 while initializing dense
Gemma 4 31B and must not be substituted for this generator without a fresh
smoke test.

The E4B second pass judged all 4,303 repaired pairs with zero errors, marked
4,232 usable, and admitted 3,965 under the stricter requirement that all three
dimension scores are at least four. Final deterministic deduplication prefers
unchanged clean rows, removes exact pairs, and retains at most two distinct
prompts for an exact target.

## Authoritative corpus

The replacement contains 65,548 rows: 61,604 unchanged clean rows and 3,944
prompt-repaired/re-audited rows over 60,949 unique targets. Per-source retained
counts are:

| Hugging Face source | Final rows |
|---|---:|
| `oliverkinch/da-instruct-dynaword` | 36,625 |
| `oliverkinch/da-instruct-dynaword-hq` | 10,181 |
| `oliverkinch/da-instruct-dynaword-contemporary` | 7,843 |
| `oliverkinch/da-instruct-dynaword-contemporary-hq` | 10,899 |

Its four tokenized tasks contain 39,422,832 exact Gemma-rendered tokens:
5,066,402 prompt and 34,356,430 response tokens. Maximum rendered row length is
1,508 tokens. Exhaustive validation found no blank spans or duplicate pairs
and no target with more than two prompts.

DFM10 disables all four inherited `oliverkinch_da_instruct_dynaword*`
prefixes and enables only `dynaword_instruct_repaired__*` at repeat four. This
preserves the previous source-family weighting without teaching rejected rows.

## Artifacts and commands

```text
logs/data_audits/dynaword_instruct_repair_20260828/
logs/data_audits/dynaword_instruct_prompt_repair_20260828/
logs/data_audits/dynaword_instruct_prompt_reaudit_20260828/
data/dynaword_instruct_repair/
data/converted_sources/dynaword_instruct_repaired/
data/tokenized_dfm10_dynaword_instruct_repaired/
```

```bash
python scripts/prepare_dynaword_instruct_repair.py
bash scripts/run_dynaword_instruct_audit_8gpu.sh
python scripts/build_dynaword_instruct_repair_plan.py
bash scripts/run_dynaword_instruct_prompt_repair_8gpu.sh
python scripts/build_dynaword_instruct_repaired.py prepare-audit
RUN_ROOT=logs/data_audits/dynaword_instruct_prompt_reaudit_20260828 \
  SAMPLES=logs/data_audits/dynaword_instruct_prompt_reaudit_20260828/samples.jsonl \
  bash scripts/run_dynaword_instruct_audit_8gpu.sh
python scripts/build_dynaword_instruct_repaired.py finalize
python scripts/validate_dynaword_instruct_repaired.py
```

The first audit, generated prompts, second audit, admission plan, and validation
summary are immutable evidence for the final row set. Rebuilding tokenization
uses the DFM9 Gemma tokenizer and
`data_io/chat_templates/gemma4_native_chat.jinja`.
