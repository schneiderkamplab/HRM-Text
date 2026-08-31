---
type: Runbook
title: DFM10 GovReport Repair
description: Complete-report, token-aware GovReport summarization conversion and grounding audit.
tags: [dfm10, govreport, summarization, grounding, data-quality]
status: stable
last_updated: 2026-08-29
confidence: high
---
# DFM10 GovReport Repair

## Superseded conversion

The inherited `dfm4_govreport_summarization__` conversion is not suitable for
DFM10. It retained the full reference summary while character-truncating the
report prompt, so the target routinely summarized facts absent from the model
input. The DFM10 source audit marked 73/100 sampled targets unusable. This is a
converter grounding failure, not a rejection of the underlying
`ccdv/govreport-summarization` source.

## Repaired contract

[`scripts/repair_govreport_summarization.py`](/../scripts/repair_govreport_summarization.py)
creates the isolated `govreport_summarization_repaired__` path. It:

1. cleans but never truncates either report or reference summary;
2. renders the exact Gemma 4 chat prompt and target before admission;
3. requires the complete pair to fit 4,096 tokens;
4. caps the response at 1,024 tokens;
5. rejects incomplete summaries and summaries longer than half their report;
6. deduplicates exact normalized summaries within each source shard; and
7. publishes Parquet and metadata files atomically.

The deterministic rebuild retained 1,845/17,517 candidate rows. It excluded
15,265 context-overflow pairs, 263 overlong summaries, 92 incomplete summaries,
47 excessive summary/report ratios, two within-file duplicates, two cross-file
duplicates, and one short row.

Every candidate was then judged by Gemma 4 E4B. The full-corpus audit completed
all 1,845 rows with zero judge errors and marked 899 usable. The published
filter is intentionally stricter than the judge's boolean: it requires
`usable=true`, a complete target, language quality at least 3, coherence and
grounding at least 4, and training value at least 3. This retained 891 rows
(48.29%) with per-row provenance under
`data/converted_sources/govreport_summarization_grounded`.

The final independent audit sampled 100 published rows from each source shard.
It marked 199/200 usable (99.5%), cleared the 90% gate, and had zero judge
errors. Mean language/coherence/grounding/training-value scores were
4.325/4.930/4.385/4.445. The first server startup lost a GPU-allocation race
with an unrelated training smoke; the resumable launcher subsequently waited
for a free GPU and used 0.70 vLLM memory utilization.

The tokenized output under `data/tokenized_dfm10_govreport_repaired` contains
2,987,781 token IDs across 891 targets, has a maximum rendered length of
exactly 4,096, and uses tokenizer/template metadata identical to DFM9. DFM10
samples it with `repeat: 2`, for 5,975,562 pre-index tokens per epoch, and
sets the superseded `dfm4_govreport_summarization__` prefix to zero.

## Commands

```bash
python scripts/repair_govreport_summarization.py --workers 2 --force

python scripts/audit_repaired_govreport.py prepare \
  --input-dir data/converted_sources/govreport_summarization_repaired \
  --audit-dir logs/data_audits/govreport_summarization_repaired_full_20260828 \
  --samples-per-file 0
AUDIT_DIR=logs/data_audits/govreport_summarization_repaired_full_20260828 \
  PORT=8590 setsid -f scripts/run_repaired_govreport_audit_when_free.sh

# Run the full audit, then publish only the strict accepted rows.
python scripts/filter_repaired_govreport.py --force

# Stage only Parquet files: provenance JSONL is metadata, not training data.
mkdir -p data/dfm10_govreport_repaired_sources/govreport_summarization_repaired
for source in data/converted_sources/govreport_summarization_grounded/*.parquet; do
  ln -s "$(realpath "$source")" \
    "data/dfm10_govreport_repaired_sources/govreport_summarization_repaired/$(basename "$source")"
done

python scripts/tokenize_chat_template.py \
  data/dfm10_govreport_repaired_sources \
  --tokenizer-path /work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json \
  --chat-template data_io/chat_templates/gemma4_native_chat.jinja \
  --output-dir data/tokenized_dfm10_govreport_repaired \
  --workers 2 --force

python scripts/audit_repaired_govreport.py prepare \
  --input-dir data/converted_sources/govreport_summarization_grounded \
  --audit-dir logs/data_audits/govreport_summarization_grounded_final_20260828 \
  --samples-per-file 100
AUDIT_DIR=logs/data_audits/govreport_summarization_grounded_final_20260828 \
  PORT=8592 setsid -f scripts/run_repaired_govreport_audit_when_free.sh
```

The durable audit artifacts are:

```text
logs/data_audits/govreport_summarization_repaired_full_20260828/
logs/data_audits/govreport_summarization_grounded_final_20260828/
data/converted_sources/govreport_summarization_grounded/filter_summary.json
data/converted_sources/govreport_summarization_grounded/filter_provenance.jsonl
```

The launcher owns and tears down only its selected judge server. It uses a GPU
lock plus a second free-GPU check to avoid data races with other launchers.

## Deferred 8K+ corpus

On 2026-08-29, a separate complete-document conversion was prepared for a
future long-context DFM10 version. With an 8,192-token pair limit and a
2,048-token response limit, it retains 7,742/17,517 rows before semantic
auditing, compared with 1,845 candidates under the 4K contract. Its candidate
root is `data/converted_sources/govreport_summarization_repaired_8k`.

This corpus is intentionally **not** being audited, tokenized into production,
or linked into the current DFM10 union now. It is reserved for a long-context
DFM10 variant. When activated, it must pass the exhaustive E4B audit and
strict publication workflow in `scripts/run_govreport_8k_repair_when_free.sh`;
the 4K and 8K representations must not be sampled together as duplicates.
