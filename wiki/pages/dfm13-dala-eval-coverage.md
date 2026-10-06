---
type: Report
title: DaLA Evaluation Coverage Snapshot
description: Actual legacy and accepted-v2 DaLA evaluation coverage traced to manifests and completed Inspect headers.
status: stable
last_updated: 2026-10-06
confidence: high
---
# DaLA Evaluation Coverage Snapshot

Read-only TODO4 audit: [detailed report](../../logs/diagnostics/dala_eval_coverage_20261006.md)
and [machine evidence](../../logs/diagnostics/dala_eval_coverage_20261006.json).
The machine report pins its live-plan snapshot and records UTC capture time;
Tesla owns concurrent TODO2 language additions, so later plan changes supersede
the snapshot rather than retroactively changing its findings.

At capture,21 languages have planned and completed acceptability/GEC tasks:
Danish legacy sources plus20 September30 pinned multilingual test pools.
Latest completed results at step3150000 were checked through163 successful
Inspect shard headers. Danish acceptability is `giannor/dala:test`; GEC is
`giannor/dala_gen_v3`, configuration `gec_dala`, test. These are not the DFM13
accepted compact-v2 publication. The20 retain1000 pairs/2000 samples per task.

All34 languages have separate accepted compact-v2 packages with test and
validation views. Thirteen additional languages have prepared accepted-v2
test/representative eval selections/configs but no jobs in the captured plan.
Adding those13 does not migrate the existing21 to accepted-v2 evaluation.
Old and new populations must not be equated merely from version-like filenames.

Training integration manifests are train-only; historical test manifests
provide same-producer exclusions, not whole-corpus decontamination. The old
English producer manifest records known source-label errors. Article overlap is
permitted by existing policy and was not treated as a violation. No plans,
task implementations, datasets, or GPU processes were changed by this audit.
