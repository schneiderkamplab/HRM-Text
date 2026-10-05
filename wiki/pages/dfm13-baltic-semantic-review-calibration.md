---
type: Experiment
title: DFM13 Baltic Semantic Reviewer Calibration
description: Isolated current-versus-revised compact reviewer comparison and the evidence preventing deployment.
tags: [dfm13, baltic, review, calibration]
status: draft
last_updated: 2026-10-04
confidence: high
---
# Baltic Semantic Reviewer Calibration

The2026-10-04 bounded comparison completed80 requests over40 cases at four
requests/server on existing8800-8807 endpoints. Root:
`data/dfm13/baltic/semantic-review-calibration-20261004-v1`.
It uses isolated `dfm12/baltic_semantic_review.py`, not a production replacement.

Current:2keep,3repair,6reject,24needs_verification,5technical failures.
Revised:15keep,7repair,5reject,0needs_verification,13technical failures.
The apparent reduction in verification holds is **not validation**: independent
checks found false keeps for corrupted Latvian prose and a source summary adding
the unsupported role of running publishing houses. All existing holds remain.

Twelve revised and five current failures are valid JSON keeps with empty reasons,
rejected by the application contract; the other revised failure is a repetition
loop. They are distinct from semantic defects and malformed JSON. Boole owns the
separate empty-rationale recovery. Neither include_reasoning nor server grammar
state was changed; saved requests pin the actual settings. Four CPU tests pass.

The12 paired controls,24 stratified old-NV samples and4 exposed diagnostics do
not establish population precision. Raw semantic labels improved on controls,
but all six revised good controls still failed the reason contract. A genuine
missing-essential-fact control is absent. Deployment remains blocked, including
use in the [Baltic-to-W4 handoff](dfm13-baltic-wave4-handoff.md).

Full counts, candidate IDs, independent examples and SHA256 pins are recorded in
`docs/reports/dfm13_baltic_semantic_review_calibration_20261004.md`.
No production modules, servers, training state or candidate admissions changed.
