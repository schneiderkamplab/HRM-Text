---
type: Report
title: DFM13 Arena Reviewer V4 Diagnostic
description: Stable evidence IDs and independent initial review calibration, without production admission.
status: draft
confidence: high
last_updated: 2026-10-01
tags: [dfm13, data, calibration]
---
# DFM13 Arena Reviewer V4 Diagnostic

Related context: [Arena quality review](/pages/dfm13-arena-quality-review.md).

V4 is a new isolated reviewer, not a mutation of v1/v3. It uses lossless
400-character evidence spans, strict JSON-schema output, two independent initial
contexts (neutral quality and skeptical material-claim review), and conditional
adjudication. Independence is contextual, not separate model expertise. Invalid
reviews fail closed; no exports or training admission are automatic.

Implementation: `scripts/dfm13_arena_reviewer_v4.py`. The separately pinned
`scripts/dfm13_arena_reviewer_v4_schema.py` corrects an initial transport problem
by including the enforced schema explicitly in prompt text. The first control
comparison remains preserved at `logs/arena_audit/20261001-v4-controls-modes`.
Corrected comparison: `logs/arena_audit/20261001-v4-schema-controls-modes`.

Thinking off/on each yielded ten valid final decisions and two review errors
on twelve exposed controls. Under the subsequent independent control reassessment,
both modes kept six acceptable controls, rejected the printer hard negative,
falsely kept the unsupported internal-process hard negative, and failed to produce
a valid final induction-control decision. Thinking-on additionally identified the
puzzle's unsupported inference. The former twelve rigid labels are not clean gold;
see `docs/reports/dfm13_calibration_control_review_20261001.md`.

The 129-case thinking-off diagnostic completed: 95 valid (25 keep, 22 repair,
48 reject), 34 review errors, 74 adjudications. It recovered 85 of 117 original
invalids, versus 53 in v3; this is structural recovery, not accuracy. Stage errors
are now chiefly verification/checklist inconsistencies, not copied-quote errors.
Detailed assistant assessment:
`logs/arena_audit/20261001-v4-diagnostic129-off/reviewer-review.md`.

The parent-provided forty-example set is reference-blinded but not unseen:
all forty occurred in the original 1000; one overlaps development129. Only its
`samples.jsonl` was read. The input/freezing adapter
`scripts/dfm13_arena_v4_blinded.py` leaves the reviewer unchanged and freezes
prediction/artifact hashes before reference access. Root:
`logs/arena_audit/20261001-v4-blinded40`. References remained unread until all
comparison predictions and semantic extraction rules were frozen; they have
since been opened for offline scoring only, without prompt changes or reruns.

The forty-case run completed: 33 valid decisions (28 keep, two repair, three
reject), seven review errors and seven adjudications. Predictions and raw/stage
artifacts are hash-frozen in `predictions-frozen.json`; receipt SHA256
`92910a0d7279f2748f017048ccc98e17c420df035f2b1a2c4fc3980a57263cbd`.
All receipt hashes verified. No v4 clients remain running.

## Frozen Semantic Comparison

The simple one-call verdict/reason variant completed 40 reference-blinded cases
plus 12 development controls without formatting failures. Root:
`logs/arena_audit/20261001-semantic52-v1`. Its prediction freeze and the separate
raw-semantic extraction freeze preceded reference access. Parseable v4 verdicts
remain separate from validation failures; four initial consensuses are retained
as unvalidated semantic decisions, while three disagreements stay unresolved.

Against the 32 definitive assistant-authored references, v4 semantic agreement is
16/29 resolved (three unresolved), with keep precision 11/20 (55%). Simple
agreement is 17/32, with keep precision 12/26 (46.2%). Eight uncertain references
are reported separately, not treated as factual negatives. Both reviewers miss
material visible defects and keep the invented-internals development control.
Neither is ready for automatic admission. These are reference-agreement figures,
not human-certified accuracy or population estimates.

Final report: `logs/arena_audit/20261001-semantic52-v1/reviewer-review.md`.
Machine-readable matrices and per-example joins: `reference-comparison.json`
in that root. No further experiments or production actions followed.

All calls borrow existing localhost 8800-8807 servers with alias dfm13-gemma4;
no server lifecycle, GPU allocation, exports or training changes. Production
readiness is **not established**.
