---
type: Runbook
title: Native Multilingual Tool Dialogue Contract
description: CPU-tested opt-in v4 tool paths with canonical user grounding and Gemma-native serialization.
tags: [dfm12, multilingual, tools]
status: draft
last_updated: 2026-09-27
confidence: high
---
# Native Multilingual Tool Dialogue

## Localized Final Revision, 2026-09-27

**Supersedes the JSON-only-final design below.** Native tools do not require a
JSON-only final assistant answer. That earlier implementation removed part of
the localization task; its structural test success was not a semantic-generation
fix. The current opt-in contract tag is
`native-tool-dialogue-v4-localized-final-v2`, still under `contract_version: 4`.
Old v4 draft specs with a different tag fail closed rather than being silently
reinterpreted. Version2/3 and historical artifacts remain unchanged.

Tool-path response schemas now require `final` natural-language prose alongside
the subtype-specific dialogue fields. Requests supply exact terminal evidence:
tool name/result, lookup-attempt count, success/error state, mock-only scope and
whether an action was executed. Single/clarify/retry finals explain only lookup
findings; error finals explain failure; multi finals may confirm only the action
supported by the result. No-call still requests a hypothetical explanation.
Calls, arguments, identifiers and results remain deterministic and validated.

Provenance binds the generated final to its terminal result message and records
`semantic_status: pending_review`. Unsupported action claims, contradictions,
wrong language and invented details must be rejected by the existing semantic
audits. CPU assembly deliberately does not claim multilingual semantic proof:
an unsafe generated final remains visible as a pending candidate, never a
structural autopass. No reviewer code or admission gate was changed.

Actual CPU preparation CLI (fresh output only):

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
TOKENIZERS_PARALLELISM=false /home/ucloud/miniforge3/envs/hrm/bin/python \
  -m dfm12.multilingual_tool_dialogue \
  --prepare-root data/dfm12/tool-dialogue-v4-localized-final-cpu-20260927-v1 \
  --language sv
```

This freezes thirty requests covering five domains and six subtypes, measured
teacher prompt budgets, actual student-template binding and implementation/input
pins. It makes **zero model calls**, supplies no generated answers and explicitly
sets generation/admission authorization false. This is a requests-only handoff,
not a runnable/calibrated pilot root. Parent-owned combined 2b/2c calibration must
consume the new `spec_for`/`request`/`assemble` contract in a separately prepared
root; no old failed calibration or exposure is reset by this preparation.

Verification: **278 multilingual tests passed**, including **59 focused native
tool tests**, real-template CPU rendering/token boundaries for all six subtypes,
required localized finals, terminal-evidence binding, pending semantic disposition
for unsupported claims, old-draft rejection and fresh-only CPU preparation.
No GPU work was started; live semantic quality remains unmeasured.

## Historical JSON-Final Draft, Superseded

The user requested a tool-dialogue repair using Gemma-native tool rendering and
OpenAI-compatible definitions. `dfm12/multilingual_tool_dialogue.py` implements
the opt-in **contract_version4** path; `multilingual_tasks.py` only dispatches
new v4 tool specs to it. Version2/3 generation/assembly semantics and defaults
are unchanged. No old root, result, manifest or approval receipt was rewritten.
Current-source hashes necessarily change; old pinned runs must not be silently
repinned or claimed resumable. The new module is in the shared
`multilingual_prepare_calibrated.IMPLEMENTATIONS` inventory, inherited by new
calibrated/quarantine manifests. No future run has been admitted or launched.

Six explicit paths replace the flat six-string contract:

- `single`: one lookup, terminal lookup JSON receipt, no action tool exposed.
- `clarify`: obtain the missing lookup field in a real user followup, then lookup.
- `multi`: lookup followed by the declared action, then its JSON receipt.
- `error`: one failed lookup, terminal error, no invented success or implicit retry.
- `retry`: one failed lookup followed by exactly one unchanged lookup retry.
- `no-call`: general hypothetical question/explanation, no calls or record data.

The first ten new slots cover all six paths; thirty slots cover all five domains
times all six paths. Teacher schemas request only applicable prose fields:
`user`; additionally `clarification`/`clarification_reply` for clarify or
`explanation` for no-call. No teacher-generated final success prose is accepted
on tool paths. The CPU assembles mapping-valued arguments, unique call IDs,
paired `role: tool` results and exact terminal JSON receipts. The actual local
Gemma-derived template supplies its own tool declarations/call/response tokens;
raw control tokens in data are rejected. No Mistral tokenizer fix or template
edit was made, and no reviewer contract was changed.

Canonical JSON request data is visibly appended to the correct user turn and
logged in argument-source provenance. Naturalized service/date prose need not
contain identical machine literals. This is explicit student-visible grounding,
not a semantic-equivalence shortcut: conflicting prose, wrong intent, wrong
language or clarification wording still requires rejection by semantic audit.
Lookup-derived action identifiers are explicitly linked to the matching result
field, not guessed from similar values or silently reclassified as user data.
Schemas, quantities, availability, argument/result equality and call/result
linkage are checked. External schema retrieval is forbidden. Original full
scenarios remain in provenance, while requests/reviewer-facing scenarios are
scoped to the actual subtype to avoid accidental action requirements.

Focused tests exercise all thirty domain/path combinations, naturalized Swedish
wording, missing-field timing, forged action IDs, quantity/type/result errors,
raw-token injection, version isolation and pin inventory. Real-template CPU
tests cover all six paths, native rendering, exact prompt-prefix token binding,
4096-token limits and final-assistant response boundaries. These are structural
tests, not evidence that a future teacher produces fluent/correct dialogue.
Training remains untouched; no GPU calls, servers or model-generated samples
were started for this repair. Read-only renderer findings can be checked against
these fixtures without changing the template or historical artifacts.

Verification: **275 multilingual CPU tests passed**, with two dependency
warnings. This includes 56 focused tool-dialogue tests. No live model test was
performed; future generation and admission still require their existing gates.
