---
type: Runbook
title: DFM10 DST Table Prompts Repair
description: Table extraction, target cleanup, exhaustive grounding audit, and fail-closed replacement of the inherited DST table-to-text source.
tags: [dfm10, danish, table-to-text, repair, grounding, audit]
status: draft
last_updated: 2026-08-29
confidence: high
---
# DFM10 DST Table Prompts Repair

## Finding

The inherited `oliverkinch/dst-table-prompts-bt` conversion is not safe to
sample unchanged. The raw source contains 3,043 prompt/target pairs. In 3,041
targets, authentic Danmarks Statistik article prose is followed by website UI,
publication metadata, navigation, contact information, or related boilerplate.
More importantly, inspection found article claims that are absent from the
paired markdown table. The generated prompt can also request unsupported
specifics. Cleaning the footer alone therefore does not establish grounding.

The DFM10 source-quality audit marked only 26 of its 100 sampled rows usable.
Treat this primarily as a table/article alignment and conversion defect, not as
evidence that Danish table-to-text supervision is intrinsically low value.

The subsequent exhaustive 31B audit was stricter and authoritative: only 133
of 3,016 cleaned candidates (4.41%) passed. Unsupported claims were the primary
problem for 2,739 rows; 130 were incomplete, five had prompt mismatch, and 142
received `primary_problem: none` although only 133 met every strict threshold.
Mean grounding was 1.60/5. This supersedes any inference that deterministic
footer cleanup would recover most rows.

## Repair contract

`scripts/repair_dst_table_prompts.py` extracts the exact markdown table using
the first table delimiter and the authoritative `meta.table_chars` length. It
replaces generated framing with one natural Danish instruction that explicitly
permits only claims derivable from the table. It strips the publication and UI
tail from the authentic response, rejects incomplete responses, and admits only
complete Gemma 4 native chat renderings of at most 4,096 tokens. The conversion
writes atomically and retains source row IDs.

The deterministic pass produced 3,016 candidates from 3,043 rows:

- 26 rows were rejected as incomplete after cleanup;
- one complete rendering exceeded the 4,096-token context;
- candidate rendered length has median 1,458 and maximum 3,728 tokens.

This is a candidate set, not a grounding decision. Every candidate is judged
against its table by Gemma 4 31B IT. Strict admission requires `complete` and
`usable_for_training`, language at least 3/5, coherence at least 4/5, grounding
at least 4/5, and training value at least 3/5. Audit coverage must be exactly
3,016 unique rows with no judge errors. `scripts/filter_repaired_dst_table_prompts.py`
then publishes only accepted rows.

## DFM10 replacement policy

The inherited `oliverkinch_dst_table_prompts_bt__` prefix is disabled with
`max_per_file: 0`. The accepted replacement is tokenized under
`dst_table_prompts_repaired__` using the Gemma 4 native template and currently
retains the former repeat of ten. Reassess that repeat after the final accepted
token count is known. `scripts/prepare_dfm10_data.sh` fails closed when the
full-corpus filter artifact is absent.

## Operations

The complete audit is partitioned eight ways with resumable JSONL writes,
exclusive partition locks, exact merge coverage, and atomic publication:

```bash
python scripts/repair_dst_table_prompts.py --force
python scripts/audit_repaired_dst_table_prompts.py prepare --samples 0 --partitions 8
setsid bash scripts/run_dst_table_prompts_audit_when_free.sh \
  > logs/data_audits/dst_table_prompts_repaired_20260829/queue.log 2>&1 < /dev/null &
WAIT_FOR_AUDIT=1 setsid bash scripts/finalize_dst_table_prompts_repair.sh \
  > logs/data_audits/dst_table_prompts_repaired_20260829/finalizer.log 2>&1 < /dev/null &
```

The launcher takes `/tmp/hrm-gpu-N.lock` and waits for a GPU with no compute
process; it must not evict unrelated training or evaluation.

**Superseded 2026-08-29:** the initial operational state had the full audit
queued behind training. That audit is complete. Its 4.41% strict retention is
materially too small, so `scripts/regenerate_dst_table_prompts.py` preserves
the 133 accepted authentic rows and partitions only the 2,883 rejected rows
for deterministic 31B target regeneration. **Update 2026-08-29:** all 2,883
replacement targets are now present. One small table repeatedly produced an
incomplete deterministic generation; it uses a documented, directly
table-derived two-sentence fallback. The fallback is not exempt from review.
**Completed 2026-08-29:** the independent audit of all 3,016 combined rows
accepted 2,909 (96.45%) and rejected 107. Mean scores were 4.99 language, 5.00
coherence, 4.94 grounding, and 4.93 training value. The primary rejected-row
problems were 97 unsupported claims, five language errors, and one incomplete
response. The strict filter and Gemma-native tokenization produced 4,111,556
unique tokens; repeat ten contributes 41,115,560 tokens per epoch, close to the
inherited source's former scale. `production_gate.json` is present. Both the
DFM10 preparation script and union builder require that marker. Do not weaken
grounding thresholds merely to recover volume.
