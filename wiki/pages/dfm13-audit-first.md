---
type: Runbook
title: DFM13 Audit-First Processing
description: Compact audits and targeted repairs for multilingual additions.
status: draft
confidence: high
last_updated: 2026-10-03
tags: [dfm13, audit, multilingual]
---
# Audit-First Processing

Following the user's jjzha comparison, prefer compact non-thinking audits over
regenerating good existing conversations. Keep sound rows unchanged; return
keep, repair or reject with a short concrete reason. Reserve needs_verification
for essential unavailable evidence, not stylistic uncertainty. One targeted
repair receives a fresh review without the prior verdict. Unresolved defects
stay out of accepted exports.

Reuse `scripts/audit_dfm13_jjzha.py`'s structured reviewer pattern: 256 response
tokens, thinking disabled. Adapt scope to all supervised turns and retain source
evidence. Preserve deterministic transformation tasks and their audits. The
35K/70K new-conversation targets are unchanged; new generations use the same
compact audit/repair flow. Independent sampled content review checks systematic
defects without requiring perfect native-speaker certification or duplicative
model-review stacks before every production batch.

This supersedes the preference for increasingly elaborate calibration stacks,
not provenance, rights, context-length or known-quality holds. 26B-A4B remains
the default; archived31B comparisons are diagnostic evidence. See
[calibration history](dfm13-wave-synthetic-calibration.md).

## Client Feeding

The 2026-10-03 LV/Fars audit showed bursty GPU use with synchronous source I/O,
tokenization and per-row writes on its async network loop. The client now reads
source batches on one dedicated SQLite-owning thread, prepares requests and
writes results off-loop, and updates progress at most every two seconds.
Concurrency can change explicitly on resume without changing source pins.
The measured 32/server baseline was 28,709 terminal rows in 327.9 seconds,
about 5,253/min (not accepted rows). The subsequent 128/server run requires
its own measurement; do not claim a speedup from configuration alone.

New clients drain queued work on SIGTERM. The older live client lacked that
handler; interrupted requests remain explicitly unresolved and require retry,
never silent acceptance. Saved outcomes and original source holds survive resume.
