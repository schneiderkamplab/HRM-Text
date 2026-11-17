---
type: Runbook
title: SimpleStories role-specific checks and paired source pilot
description: Diagnostic matched controls and generation from original versus manually cleaned development seeds.
tags: [dfm16, audit, simplestories, calibration]
status: draft
confidence: high
last_updated: 2026-10-28
---
# Role-specific checks and source-quality pilot

User authorized this follow-up after the [context calibration](dfm16-story-calibration.md)
failed. It is development only, with no validation sampling or production admission.
Implementation: [pilot adapter](../../scripts/dfm16_role_pilot.py).
Artifacts: `data/dfm16/expansion-v1/stories/quality-v3-qwen/role-source-pilot-v1`.

Frozen before votes: 28 manually authored clean/defective pairs, seven per language
(Danish, English, Hindi, Japanese). Each pair targets one obligation: source
language, source coherence, request validity, corrected-answer grammar, grounded
answer fidelity, a legitimate superseding revision, or exact paragraph preservation.
The 56 targets are not 56 independently sampled whole conversations. Target labels
are provisional assistant-manual assessments. Some preceding turns only provide
context and are not themselves being certified as clean training examples.

Every judge (Qwen27B, Flash-Next, Odin) sees both the legacy generic criterion and
a role-specific prompt on the same target. References and pair labels never enter
payloads. The legacy seed check has language only; its comparison against the new
coherence check therefore changes both coverage and prompt. Outcomes cannot isolate
wording alone. Full context is retained; verdicts are plain accept/reject, non-thinking,
no JSON constraint and at most one retry. Odin uses documented completion controls,
64 concurrency and 100 actual sends per rolling minute including retries. Local
clients use 128 concurrency. Existing servers are reused without modification.

Generation: 32 first attempts, four tasks (QA, summary, rewrite, revision) × four
development seed families × two conditions. H001's unexplained map references are
changed to letters; H101's Hindi grammar/translation defects are corrected manually.
H051 English and H151 Japanese seeds remain identical across conditions to expose
stochastic variability. The complete seeds were reread before generation. Danish
retains the original English source-to-Danish generation setup. This does not test
native Danish seeds. Four task outputs sharing one seed are not independent source
replicates. The comparison cannot establish a population-level source-cleaning effect.

Generation reuses the existing Flash request/settings, removing only the unsupported
claim that every supplied seed has been independently screened, identically in both
conditions. First completions and CPU failures are retained; no selective regeneration
or repair. Complete generated conversations are inspected manually without judge
verdicts. Original seed defects, generated user/source defects and assistant errors
will be recorded separately. These new generations are not automatically admitted.

Initial verification: four focused tests pass for paired controls, label exclusion,
provider protocol, intentional correction/revision scope and retaining CPU failures.
Run state and final results are pending below.

## Matched-control results, 2026-10-28

All 112 requests per judge completed. Fully correct pairs (legacy → role):
Qwen 16→23/28, Flash 19→24/28, Odin 20→21/28. Role prompts gave Qwen
0/28 clean withheld but 4/28 defective accepts plus one unresolved; Flash 3/28
clean withheld and 1/28 defective accepts; Odin 7/28 clean withheld and no
defective accepts. These are small synthetic targeted checks, not a qualified
whole-conversation gate. Request-validity pairs remain weak (Qwen 1/4, other
judges 0/4). Odin also rejects three valid paragraph-preservation targets.

A possible evidence-scoping confound: the request-validity controls provide a
background seed as well as a different explicit source inside the user request.
Judges may evaluate the seed instead of the explicitly supplied transformation
source. This is a hypothesis, not an explanation established by binary votes.
Do not erase this failure or retrospectively reclassify the controls. A later
ablation should distinguish background seed from the authoritative source while
retaining full context. No prompt change has been made to this frozen run.

## Completed generation and interpretation, 2026-10-28

The earlier pending state is superseded: all 32 first attempts completed, yielding
29 parseable conversations and three JSON/turn-count failures. Complete provisional
manual inspection found **8 clear, 21 defective, 3 unresolved**. Twenty outputs
introduce a new definite defect; one defective output only copies a defective
source. Five copy defective source passages (overlap with new errors allowed).
Eleven parseable outputs fail the existing deterministic contract. Labels were
blind to generated-output judge verdicts (none were requested), but input condition
was visible. Do not describe this as a condition-blind or human-certified experiment.

The cleaned condition has 4/16 clear, and the original condition also 4/16 clear.
English and Japanese seeds are identical between conditions; differences there
are stochastic replicates, not cleaning effects. There are only two genuinely
changed seed families, so no causal or population claim follows from these totals.

New failure examples: an English QA answer says before departure while its own
quoted chronology says after; Danish introduces grammar errors from cleaned
English input; Hindi introduces `दिए गए कहानी` in a new user request; rewrites
overshoot lengths or invent facts; revision generations lack distinct paragraphs.
These are not all inherited bad seeds, and additional review alone is insufficient.

Role-specific Flash results look promising on simple targets (1/28 defective
accepts, 3/28 clean withheld), but upper one-sided 95% bounds are 15.9% and 25.4%,
respectively. No whole-conversation target is demonstrated. Keep production held.
Recommended next development change: vetted native request templates with explicit
source identity, one response/edited paragraph per generation, mechanical assembly
for preservation/undo, and deterministic length admission. Compare against current
whole-conversation generation before a new untouched holdout. This is a proposed
next experiment, not an implemented or deployed generator change.

See [final diagnostic report](../../docs/reports/simplestories-role-source-pilot-20261028.md)
and [manual notes](../../docs/reports/dfm16-role-generation-manual.json).
32 focused/runtime/limiter tests pass. Recorded Odin list-price estimate is
0.2075 DKK, excluding possible unrecorded failures/retries and local GPU cost;
113 actual HTTP sends (112 review rows plus runtime endpoint discovery) completed
under the 100-per-rolling-minute cap. Four stage
receipts are verified; controller exited and lock released. Repository OKF retains
one unrelated oversized concept and 15 pre-existing missing-link warnings.
