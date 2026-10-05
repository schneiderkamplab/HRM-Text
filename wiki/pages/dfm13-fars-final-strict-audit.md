---
type: Experiment
title: DFM13 Fars Final Strict Audit
description: One-shot Persian summary fidelity calibration failed, excluding both summary components from final integration.
tags: [dfm13, persian, audit, exclusion]
status: stable
last_updated: 2026-10-04
confidence: high
---
# Fars Final Strict Audit

User policy: accept only what survives a reliable final strict audit; ignore the
rest, with no repairs or repeated calibration. The one bounded gate failed.
**Exclude `ParsiAI--FarsInstruct-fa-pn_sum` and
`ParsiAI--FarsInstruct-fa-wiki_sum` from this final integration.** No bulk audit,
accepted export, upload or integration was launched by this task. Other Fars
components, including persian_qa, and Latvian are outside this decision.

Root: `data/dfm13/fars-final-strict-controls-20261004-v1`.
New isolated runner: `scripts/audit_fars_final_strict.py`. The audit separately
checks source fidelity, required coverage and Persian readability, requesting a
source-versus-answer comparison first. It does not reuse the compact overall
keep rubric or show previous model verdicts, manual labels or correction notes.
The16 frozen controls comprise7 independently identified defects and9 cases
with no material issue identified, drawn from the existing independent sample.

PID2955005 completed16/16 on shared26B servers8800-8807, at two requests/server.
All inputs, complete raw responses, requests and implementation hashes survive.
Results: two false accepts, three correctly excluded negatives, four positive
passes, one positive exclusion and six contract failures. Thus ten requests
were schema-valid; the gate is not reliable even if contract failures were fixed.

Decisive false accepts, independently rechecked against the supplied article:

- Control0: source recommends buying adjacent seats; summary instead says
  selecting nonadjacent seats. Reviewer overlooked the relationship reversal.
- Control6: source says1313 households (`یکهزار و ۳۱۳`); target says1137
  (`۱۱۳۷`). Reviewer explicitly but incorrectly calls1137 source-supported.

All six technical failures returned a JSON object where `comparison` requires a
string. These are application-schema failures, not semantic rejections or proof
of a global grammar fault. No transport/server/include_reasoning change was made.
No response was silently coerced, retried or accepted. The positive exclusion
concerned ministry affiliation; it need not be resolved to establish failure
because the two material false accepts are decisive.

`assessment.json` and `complete.json` record terminal results.
`integration-disposition.json` is the hash-bound handoff to Tesla: zero final
accepted rows; preserve but exclude42140 staged pn_sum and13769 staged wiki_sum
rows (55909 total) from this release. The old staging receipt already had
admission=false; it remains untouched, as do all original candidates and holds.
There is no accepted export queue from this failed calibration.

User subsequently confirmed source-wide final exclusion: no future generation,
repair, re-audit or integration queue should reconsider these full sources without
new explicit authorization. `final-source-exclusion.json` records this policy,
including source IDs `dfm13_wave4_ParsiAI_FarsInstruct_fa_pn_sum` and
`dfm13_wave4_ParsiAI_FarsInstruct_fa_wiki_sum`. Existing hardcoded publication
guards in `dfm12.wave_publication_holds` already block both complete components;
they were verified and left unchanged. Historical pending-audit language does
not authorize another queue. No active Fars audit/repair consumer was found at
closure. Tesla/parent must retain the exclusion when building future queues;
no shared queue implementation or frozen artifact was rewritten here.

Three CPU tests passed: evidence-only request contents, strict fail-closed
dimension checks, and control-gate rejection of false accepts/technical errors.
The W4 watcher, Baltic production, shared servers and training were untouched.
