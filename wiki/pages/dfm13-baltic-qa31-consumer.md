---
type: Runbook
title: Baltic QA31 Held-Source Consumer
description: Isolated full-record preparation and calibration-gated31B review, repair and fresh re-audit for held Baltic QA.
status: draft
confidence: high
last_updated: 2026-10-03
---
# Baltic QA31 Held-Source Consumer

`dfm12.baltic_qa31_consumer` prepares all118866 published held QA conversations
(12895 LT,105971 LV), validated against the exact bindings and receipt described
in [Baltic QA quality holds](dfm13-baltic-qa-quality-holds.md). Jason's files,
published data, source ledgers and shared gates are unchanged.

Packets retain complete published conversations and exact upstream records.
Primary Wikipedia articles are missing: original QA is not gold, and matching
it is not factual proof. The review must hold/reject essential unsupported claims
rather than fabricate. Every earlier assistant turn is reviewed. Automated repair
may change only the final supervised assistant target; protected history/tools
are immutable, and bad history cannot be excused by a clean final answer.

The isolated consumer privately reuses the Fars stage engine with Baltic adapters:
review, bounded supported repair, fresh-context whole-conversation re-audit.
Prior verdicts remain in sealed evidence, not model inputs. Raw stages and unknown
technical outcomes remain distinct from semantic rejects; no auto-admission exists.

Roots under `data/dfm13/baltic/`: `qa31-full-packets-v1`,
`qa31-full-preflight-v1`, `qa31-diagnostic20-consumer-v1`,
`qa31-full-consumer-v1`. Model/tokenizer is verified Gemma4-31B; original native
thinking template, no Mistral regex fix, planned32768 context with8192 output
reserve. Live Tesla endpoint model/snapshot/context validation remains mandatory.

Diagnostic identities are the existing20 exposed cases, not fresh gold. Their
labels and old audit votes are excluded from requests. Bulk launch requires a
hash-bound completed diagnostic report plus explicit owner semantic approval.
Neither catalog is GPU-launched during CPU preparation, and source-wide holds
remain active. Four clients/server by default, maximum eight; no server lifecycle.

**Superseded capacity ceiling, 2026-10-03:** the preceding maximum describes
the preserved v1 engine, not a permanent bulk limit. New isolated
`dfm12.held31_capacity_consumer` successors keep eight as the unprofiled ceiling
and diagnostic maximum. Bulk may use a validated live `wave31_capacity` profile
within an explicitly reserved existing wave allocation. No real capacity profile
or GPU run was produced during preparation. External clients require scheduler
accounting; a cooperative wave lock alone cannot govern frozen production.
Successors are `qa31-full-consumer-capacity-v2` (118866),
`qa31-diagnostic20-consumer-capacity-v2` (20), and the corresponding Fars
`wave4/fars-summary-31b-consumer-capacity-v2` (89296). Old roots remain unchanged.
The lifecycle parity and focused policy suite passed32 tests. Launch/approval
contract and Poincare matrix links are recorded in
`docs/reports/dfm13_held31_capacity_successors_20261003.md`.

CPU preparation is complete: all118866 packets preflighted successfully, zero
errors or truncation. Maximum prompt-plus-output total is17084 tokens, within
planned32768. Separate sealed catalogs contain20 diagnostic and118866 full rows;
both launch templates are disabled. Input/code/catalog pins were reverified.
Focused tests passed18/18; OKF validation reported no errors/warnings. Semantic
calibration and live endpoint verification are still pending, not certified.

Full policy, handoff format and commands:
`docs/reports/dfm13_baltic_qa31_consumer_handoff_20261003.md`.

## Article-Aware Successor Proposal

On 2026-10-03 the local article pilot found useful references but also homonyms,
snapshot mismatches and source-internal errors. Missing primary evidence in the
existing sealed roots remains unchanged; retrieved articles are not certified
original generation sources or factual gold. New isolated
`dfm12.baltic_qa31_article_adapter` accepts hash-bound full article attachments
and retains the minimal four-field review contract, without quote/span schemas.
Repair and fresh whole-conversation review use the same complete evidence;
unresolved material claims and unsafe source advice must not become admissions.

The adapter and existing consumer/capacity tests passed28 cases. Boole's fresh50
retrieval pilot and sealed retrieval handoff remain prerequisites to any new
successor root. No queue was prepared or launched. Full native31B preflight and
new semantic calibration are required; old budgets/approvals do not cover this
changed reviewer. Interface and integration caveats are in
`docs/reports/dfm13_baltic_qa31_article_adapter_handoff_20261003.md`.

**Preparation completed later2026-10-03:** Boole's full verified evidence-v2
enabled new sealed `qa31-article-full-consumer-v3` and
`qa31-article-diagnostic20-consumer-v3` roots. The prior pending-retrieval statement
is superseded; old roots and pins are preserved. All118866 full conversations
and all selected whole articles were measured with actual31B native tokenizer
using16 CPU workers.118369 fit;497 remain explicit nondispatchable context
overflows (33 LT,464 LV). All37653 no-hit rows remain, fit context, and are not
automatically rejected. Diagnostic20 all fit, including5 automated no-hit cases.
Zero truncations or GPU requests. Both roots passed pin verification;46 focused
tests pass. The root matrix now points to these successors. Use the new
`dfm12.baltic_qa31_article_consumer` to preserve article-aware review, repair and
fresh-review routing and the measured-capacity reservation gate. No GPU launch
until source audits drain and explicit31B handoff; semantic calibration remains
pending and source holds remain active. Exact hashes, commands and overflow
accounting: `docs/reports/dfm13_baltic_qa31_article_successors_20261003.md`.
