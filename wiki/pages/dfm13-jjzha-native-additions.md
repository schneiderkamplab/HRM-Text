---
type: Reference
title: DFM13 jjzha Native Additions and Audit
description: Pinned train-only conversions, source-specific quality checks and waiting shared-server clients.
status: draft
confidence: high
last_updated: 2026-10-03
tags: [dfm13, data, gemma, audit]
---
# DFM13 jjzha Native Additions and Audit

Source inventory: <https://huggingface.co/jjzha/datasets>. Pins and all deferred
source decisions are in `config/dfm13_jjzha_sources.json`. This supersedes the
unexecuted preparation state in [the DFM13 plan](dfm13-plan.md).

| Source | Prepared rows | Status / checks |
| --- | ---: | --- |
| jjzha/skillspan | 3,713 | Registered repeat 1; English skills/knowledge extraction |
| jjzha/kompetencer | 740 | Registered repeat 1; Danish skills/knowledge extraction |
| jjzha/green | 7,612 | Registered repeat 1; English job-entity extraction |
| jjzha/dutch-central-exam-mcq | 1,206 | Registered repeat 1; Dutch MCQ, train only |
| jjzha/imdb-dutch-instruct | 24,780 | Pending 500-row deterministic quality sample |
| jjzha/croco-translated-data | 195,821 | Pending full target-quality audit, 11 languages |

User approved source-specific checks, not a blanket model audit of all six.
Structured sources receive BIO/answer-index validation, split screening and
manual spot checks. IMDb requires sampled Dutch fluency/coherence/sentiment
review; without aligned English originals it is not a translation-fidelity
certification. CroCo needs full correctness, language, instruction-following
and unsupported-premise review. No unaudited IMDb/CroCo rows are active additions.

## Representation and Screening

`scripts/prepare_dfm13_jjzha.py --register` has downloaded pinned source files
under `data/downloads/datasets/jjzha_*` and written conversions under
`data/converted_sources/dfm13_jjzha`. Every source has file hashes, source
revision, row provenance, exclusions and counts. No data upload or final
sampling was performed. MATH remains repeat 5 and previous additions are preserved.

Messages remain structured, with one final assistant target and native Gemma
rendering; no foreign chat-template tokens are injected. BIO tasks request JSON
with labelled spans and zero-based, end-exclusive token offsets, retaining
source tokens explicitly to avoid lossy detokenization. Dutch MCQ answers map
the documented 1-based number to a letter plus the original answer text.
No explanations or rationales are invented.

Own-source held-out normalized-input overlap is removed, including 1,012
SkillSpan rows, 21 Kompetencer, 16 Green and 119 IMDb. Input duplicates are
removed separately. Orphan/conflicting BIO continuations exclude 1 Kompetencer
and 1,037 Green rows; no guessed label repair. Retained gold annotations are not
guaranteed perfect: a manual Green sample contains a broad skill span crossing
a capitalization boundary. Repeat 1 and preserved provenance limit amplification.
Three reproducibly sampled examples per source were reviewed with seed 20261002.
All 13,271 registered rows passed the native tokenizer's single-target adapter;
a real native-template test verifies prompt/target tokenization.

The Dutch exam source explicitly partitions INCLUDE development/test examples;
only its train parquet is converted. This is not full inherited-corpus or fuzzy
decontamination. The Danish citizenship-exam source is excluded because it
repackages our evaluation domain without an established safe training partition.

CroCo starts with 220,000 rows. Hold 23,870 tool-bearing rows for a dedicated
native-tool converter, rather than silently discard function fields. Also
exclude 296 normalized duplicates and 13 invalid text records. Original raw
files are retained. The plain-text audit covers Danish, Dutch, English, French,
Galician, German, Irish, Italian, Maltese, Spanish and Welsh. No claim is made
that source labels alone establish absence of benchmark overlap; inspect source
provenance before any audited release/admission.
The candidate manifest records 19 source families, including 9,337 FLAN-derived
translations. Audit acceptance alone must not override existing source-denial
or benchmark-overlap policies. Inherited English Dolci/Tulu/math overlap also
needs checking before release; translations are not automatically duplicates.

## Waiting Audit Client

### Authorized Repair and Release (2026-10-03)

Supersedes the earlier no-release state below: the user authorized repair,
re-audit, export, upload and DFM13 registration. The completed concise retry
left 196,135 valid reviews and 186 errors: 134,230 keeps, 13,958 repairs,
47,638 rejects and 309 verification holds. Original reviews remain immutable.

`scripts/finalize_dfm13_jjzha.py --concurrency 128 --upload` was launched detached
with log `logs/dfm13/baltic-audit-3081500/jjzha-finalize.log`. State, original
audit snapshot, request evidence and release receipts live under
`data/dfm13/jjzha-finalize`. The client uses the existing eight shared servers,
leaving Baltic at 384/server; no server, training or scheduler changes.

The bounded pipeline reviews the rest of IMDb (superseding sampled-only admission),
retries original errors once through the new pipeline, repairs only designated
final assistant targets, and independently reviews replacements in a fresh context.
Generator: non-thinking, up to 8,192 output tokens; concise reviewer: non-thinking,
256 tokens. Unresolved, rejected, malformed and over-context results stay excluded.
The four structured sources retain their existing source-specific validation,
not a falsely claimed blanket model audit. FLAN/Tasksource translations without
narrow allowlist provenance stay excluded: 9,337 CroCo rows. Tool-bearing rows
remain held for a separate native-tool conversion. This is not exhaustive fuzzy
decontamination of inherited corpora.

Initial eligible work: 13,116 repairs and 24,466 audits; 142,089 accepted rows
including the structured sources. Accepted replacements require a recorded keep
re-audit. A single writer and exclusive process lock protect state. Stopping with
unfinished GPU work prevents publication; transport retries are bounded.

After GPU work, the same process exports native structured chat JSONL and cards
under `exports_dfm13/dfm13-jjzha-*`, uploads to matching
`schneiderkamplab/dfm13-jjzha-*` repositories, verifies remote file sizes at the
returned commit, and atomically updates `config/dfm13_sources.json` at repeat 1.
No matching repositories existed at launch. No final sampling or tokenization
is implied by registry integration. `release.json` is the completion receipt;
until it exists with `uploaded_and_integrated`, publication is still pending.

Focused tests cover context-preserving repairs, invalid template rejection,
source-policy holds, and accepted-only export selection.

Early repair spot checks caught IMDb replacements introducing a third
"mixed/neutral" class despite binary prompts. No release had occurred. The
client was stopped by its exact PID without touching servers or Baltic; 721
IMDb repair outcomes were archived and reset to their original targets. The
repair prompt now requires exactly `positief` or `negatief`, or a verification
hold if ambiguous; deterministic checks enforce that at repair and export.
The detached pipeline resumed with these constraints.

Concise retry update, 2026-10-03: the first complete pass ended with 192,015
valid reviews and 4,306 errors (4,302 truncated responses, four JSON errors).
Sampled failures included lengthy calculations and whitespace loops. User
authorized retrying only those errors using `concise-verdict-first-256-v1`:
non-thinking, verdict/issues/reason JSON, fixed issue labels, one short reason,
256 output tokens. Native schema has no string-length bounds; retained content
checks and explicit uncertainty prevent treating brevity as automatic acceptance.
Earlier completed reviews are untouched. Retry history archives prior failed
results and attempts transactionally; new outcomes identify their reviewer mode.
Manifest predecessor: `manifest.before-concise-256.json`. Concurrency stays
128/server; log `logs/dfm13/baltic-audit-3081500/jjzha-concise-retry.log`.

Update 2026-10-03: the user superseded the inherited thinking reviewer for
remaining rows with non-thinking auditing (`enable_thinking=false`, 1,024 output
tokens). Verdict schema and content checks remain unchanged. Completed thinking
reviews are preserved; new outcomes carry `reviewer_mode=nonthinking-1024-v1`.
The prior pinned manifest is saved as `manifest.before-nonthinking-1024.json`,
and the active manifest records the authorized transition and updated client hash.
Client concurrency remains 384/server on the eight shared compiled servers;
log: `logs/dfm13/baltic-audit-3081500/jjzha-nonthinking.log`.
The historical launch below used the earlier thinking settings.

`scripts/audit_dfm13_jjzha.py` reuses the existing reason-first thinking reviewer
and schema. Full CroCo plus a deterministic 500-row IMDb sample are indexed in
`data/dfm13/jjzha-audit/ledger.sqlite` (196,321 jobs). The sources and reviewer
dependencies are hash-pinned. Client uses a single-process lock and one ledger
writer, so competing clients fail rather than duplicate dispatch.

A detached client was launched on 2026-10-02, PID 249986 at launch:

```bash
python scripts/audit_dfm13_jjzha.py run --wait-servers --concurrency 256
```

It polls every 30 seconds for **all eight** servers on localhost ports 8800-8807
with served model ID `dfm13-gemma4`. It does not start, stop or modify any server,
training process or scheduler. Unrelated servers with another model ID are not
used. If the shared servers return under different ports/alias, restart this
client with explicit `--ports` / `--model` matching the intended Gemma reviewer.
Concurrency is 256 per server. Transport failures get up to three attempts;
invalid/truncated reviews remain errors, not acceptance. Context overflow is
recorded as preflight-blocked, never silently truncated. Retry stored errors
explicitly with `--retry-errors` after fixing the cause.

Progress: `data/dfm13/jjzha-audit/progress.json`; journal: `reviews.jsonl`;
log: `client.log`. A `STOP` file in that directory requests a graceful stop.
The client never auto-admits keep/repair labels. Inspect the IMDb sample and
CroCo dispositions first; repairs require independent re-audit. There has been
no GPU audit yet while the expected shared servers are unavailable.

Verification: 13 focused conversion/client tests pass. No GPU allocation or
training changes were made.
