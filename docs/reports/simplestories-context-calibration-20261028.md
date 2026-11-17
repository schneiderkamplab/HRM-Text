# SimpleStories context calibration: development results

Reference: 200 complete conversations; 115 definite defects, 55 clear, 30 borderline. Labels are provisional assistant-manual reconciliations, not independent human certification.

| Fixed policy | Defects accepted unchanged | Clear withheld (including unresolved) | Retained / 200 | FA upper 95% | Withholding upper 95% |
|---|---:|---:|---:|---:|---:|
| majority | 51/115 | 23/55 | 100 | 52.4% | 53.8% |
| odin_confirmation | 58/115 | 18/55 | 116 | 58.5% | 44.6% |
| qwen_odin_unanimity | 24/115 | 46/55 | 41 | 28.1% | 91.2% |

| Policy | Accepted-set definite contamination | Unresolved | Accepted borderline |
|---|---:|---:|---:|
| majority | 51/100 (51.0%; upper 95% 59.6%) | 4/200 (2.0%; upper 95% 4.5%) | 17 |
| odin_confirmation | 58/116 (50.0%; upper 95% 58.0%) | 11/200 (5.5%; upper 95% 8.9%) | 21 |
| qwen_odin_unanimity | 24/41 (58.5%; upper 95% 71.6%) | 91/200 (45.5%; upper 95% 51.6%) | 8 |

Selected qualifying development policy: **none**.
No validation conclusion follows from this development sample. Production promotion remains blocked. If no policy qualifies, no 800-example validation sample is consumed.

All original versions, labels and votes are retained. v4 retains the Hindi danda sentence-segmentation fix and reuses only unchanged local Qwen/Flash votes after matching prompts, inputs and receipt hashes. Odin was rerun with corrected provider controls; its old votes are excluded.

## Individual judges (diagnostic)

| Judge | Defects accepted | Clear withheld | Unresolved conversations | Reported input tokens | Reported output tokens |
|---|---:|---:|---:|---:|---:|
| qwen27b | 27/115 | 44/55 | 7/200 | 1935446 | 3712 |
| flash | 62/115 | 20/55 | 0/200 | 1948377 | 3744 |
| odin | 54/115 | 11/55 | 0/200 | 2619090 | 3740 |

Corrected Odin requests use reasoning_effort=none and a 32-token total completion bound. The provider reports a one-token reasoning count with no reasoning text; every parsed response is checked against these limits. Earlier misconfigured Odin runs are retained separately and are not acceptance votes.

## Timing and usage

Published-price estimate from recorded Odin usage: development 16.46 DKK; repairs 20.91 DKK; old unsupported protocol 214.07 DKK; recorded total including preflights 251.46 DKK. This is not an invoice and excludes unrecorded failed/interrupted/retried usage and local GPU costs.
[Published model prices](https://odincore.ai/ajax/services); currency from [provider pricing UI](https://odincore.ai/docs/pricing).

qwen27b: 81.3 active-session seconds, 23.041 completed checks/second.
flash: 49.6 active-session seconds, 37.810 completed checks/second.
odin: 1145.0 active-session seconds, 1.637 completed checks/second.
Timings describe active sessions for the corrected protocol and exclude paused downtime and earlier unsupported-protocol runs. Historical imported partial sessions, where applicable, are reconstructed from telemetry.

## Repairs

Attempted 63; produced 63; audit-accepted 2; accepted and manually clear 0; definite residual defects among accepted repairs 2.
Blind manual inspection of all generated repairs: {'bad': 48, 'clear': 9, 'borderline': 6}. Residual-defect one-sided 95% upper bound among audit-accepted repairs: 100.0%.
Repair outcomes: {'reject': 61, 'accept': 2}. The immutable raw report calls all non-acceptance unresolved; diagnostics.json corrects that status distinction without changing acceptance.
This is separate repair accounting. It does not erase any original filtering error or qualify a failed filter. Borderline repairs are reported separately in the JSON report.

## Scope and failure diagnosis

User-side language, fidelity and instruction checks are counted separately in diagnostics.json. A check aimed at a user request can conflate request quality with answer fulfillment; this is a candidate explanation for over-withholding, not an established causal result. No prompts were adjusted using these outcomes.
Manual defect notes include accidental source corruption, clear grammar/spelling errors, unsupported rewrites, ambiguous/no-op transformations and failed local preservation. Overlapping criterion notes are diagnostic, not additional independent examples.
The available pool consists of historical CPU-passing generations. Any future validation must also exclude prior manually viewed examples beyond development; fresh sampling and class-count qualification cannot be inferred from these development results.

Verification: 28 focused/runtime/limiter tests passed. All six stage journals and receipts were read successfully (1,874 checks per development judge, 63 repair attempts, 819 checks per repair judge). The worker exited and its controller lock is available. Repository OKF validation retains one unrelated oversized concept and 15 existing link warnings.

Detailed language/task breakdowns, policy decisions and stage receipts are in `data/dfm16/expansion-v1/stories/quality-v3-qwen/context-calibration-v4/development`.
