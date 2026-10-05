---
type: Report
title: DFM13 Source7 26B Calibration
description: Seven-case source-preserving adapter execution and independent assessment.
tags: [dfm13, multilingual, synthetic, calibration]
status: draft
last_updated: 2026-10-03
confidence: medium
---
# DFM13 Source7 26B Calibration

Part of [wave synthetic calibration](dfm13-wave-synthetic-calibration.md).

Readiness and launch supersession (2026-10-03): after the coordinator confirmed
all eight26B servers ready, detached client PID2699145 ran the seven cases to
completion in `data/dfm13/wave4/source-instruction-execution7-26b-v1`.
Canonical26B was advertised alongside the alias, so no pinned-code change was
needed. All seven generated and reviewed successfully: four automated keeps,
three semantic rejects, zero technical failures. Full source occurs once per
training user; all seven student renders fit4096 (519-1463 tokens). Twenty-two
tests and64 execution pins passed verification.

Independent whole-case inspection found two supported cases, four
language/grounding/constraint repairs and one minor bibliographic completeness
repair; no admission. Serbian drops a spelled-out two-decade quantity and
strengthens claims, while Albanian adds an unsupported motive despite automated
keeps. See the [casewise source7 report](../../docs/reports/dfm13_source7_26b_independent_20261003.md).

Original candidate/outcome files remain unchanged; the report is the additive
independent assessment. No server/training changes or further reruns occurred.
This is a selected seven-case diagnostic, not a population-quality estimate or
native-speaker certification.

## Bounded Repair Preparation

The user subsequently authorized one targeted assistant repair for each of the
five findings, retaining the two supported originals. CPU preparation is ready
at `data/dfm13/wave4/source7-repair5-compact-26b-v1` using the small
`dfm12.source7_repair` wrapper around the existing one-shot executor and Boole's
compact-review helpers. Original user/source/tool text is immutable; no source
errors may be silently fixed. Fresh review strips repair notes and prior verdicts.

43 focused tests pass;90 pins verify. All repair/review baseline requests fit
the26B context; repaired outputs must also satisfy the4096-token student budget
and2400-character assistant limit. Only one repair and one fresh compact audit
are allowed per case. Failed/unknown stages are held, not replayed. No admission.

GPU launch is pending explicit module-freeze confirmation, not server readiness.
See [freeze hash and launch handoff](../../docs/reports/dfm13_source7_repair5_handoff_20261003.md).
No repair request has been sent at this preparation checkpoint.
