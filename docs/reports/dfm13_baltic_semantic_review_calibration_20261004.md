# Baltic semantic reviewer comparison, 2026-10-04

## Decision

Do not deploy the revised reviewer or release prior needs_verification (NV)
rows. The isolated comparison is complete, but reducing NV did not establish
reliable acceptance. Production, shared servers and admission gates are unchanged.

Root: `data/dfm13/baltic/semantic-review-calibration-20261004-v1`.
Adapter: `dfm12/baltic_semantic_review.py`; runner:
`scripts/calibrate_baltic_semantic_review.py`. PID2923965 completed all80 requests.
There were40 cases:12 authored paired controls,24 seeded old-NV samples
(two per language/family), and4 exposed diagnostic cases. The sampled population
contained15938 NV outcomes. This is not an unbiased production yield estimate.

## Strict terminal results

| Arm | Keep | Repair | Reject | NV | Technical/contract failure |
| --- | ---: | ---: | ---: | ---: | ---: |
| Current | 2 | 3 | 6 | 24 | 5 |
| Revised | 15 | 7 | 5 | 0 | 13 |

Current failures:5 syntactically valid JSON keeps with empty reason, rejected by
the application validator. Revised failures:12 such empty-reason keeps and1
repeated-text-loop failure. These are not semantic rejections or accepted rows.
No empty-reason salvage was applied; Boole owns that separate technical adapter.

All6 negative controls were rejected/repaired by both arms. Current good controls
had4 raw keep labels (contract failures) and2 false NV labels. Revised good
controls had6 raw keep labels, all contract failures. Thus revised raw semantic
control agreement is12/12, but strict positive-control success is0/6. Controls
do not cover a genuine essential-missing-fact NV positive; no reliable NV recall
claim is possible. Exposed controls are diagnostic, not an independent holdout.

## Independent targeted inspection

Case IDs below resolve to exact records in pinned `cases.json`. These are
targeted whole-record checks, not a claim of independent review of all24 random
cases or native-speaker certification.

| Case prefix | Finding | Disposition |
| --- | --- | --- |
| 000b47927c29 | Two requested historical mentions are supplied; old typo allegation repeats the identical phrase as its correction. | Supported content; revised raw keep remains technically held. |
| 00248c298b74 | Answer has exactly two sentences in one paragraph; current reviewer incorrectly claims three. | Supported content; revised raw keep remains technically held. |
| 0017c95be7d1 | Python reversal code is correct, but Latvian explanation contains multiple corrupted words, including `pievolejiet` and `pātniedziet`. Correct code does not excuse defective target prose. | Repair; revised valid keep is a false accept. |
| 001bf2286870 | Three-point comparison need not summarize every SWIFT/US detail, but answer contains corrupted `pretējska`. | Localized language repair; revised keep misses the defect. Do not automatically endorse the old completeness allegation. |
| 6888b115ac6b | Source says organizing demonstrations and publishing underground literature; answer says running literature publishing houses (`izdevniecību vadīšanu`). This adds a concrete organizational role. | Source-fidelity repair; revised valid keep is a false accept. |
| 66e8a963dab8 | Correct numeric result13, with ambiguous Lithuanian request mentioning boxes; cannot confidently classify boxed formatting as a material violation. | Do not use as a strong negative control; raw keep remains technically held. |

The rubric usefully distinguishes visible defects from unavailable essential
facts, but its leniency wording can outweigh whole-answer language and source
checks. A successor should explicitly preserve those checks before applying
brevity/style exemptions. It needs paired repaired positives for real defects
and a genuine missing-essential-fact control. No repository/case-specific answer
exceptions should be added. W4 must not inherit this unvalidated reviewer.

## Transport and provenance

Both arms use the same candidate and request settings, changing only the system
rubric: model `google/gemma-4-26B-A4B-it`, temperature0, max_tokens256,
`chat_template_kwargs.enable_thinking=false`, strict JSON response_format.
The saved request envelopes omit `include_reasoning`. Execution uses the existing
transport with frequency_penalty0.5 and four concurrent requests per endpoint,
across8800-8807, combined across both arms. No server or grammar state changed.
Raw stages and requests are retained. Valid JSON with an empty reason is an
application-contract failure, not evidence of grammar being disabled. Parent's
separate fixed-schema probes passed8/8 with each include_reasoning setting; that
does not change these semantic findings or authorize retrospective relabeling.

SHA256 pins:

- `cases.json`: `aa1e00aad90d5c2956ebf70e2deb1b66826296bfc61722e7ea34123d74fe9967`
- `requests.json`: `44bec5ddcea07119a115cdaa0441bc985043432a529a14230b8f6ee371e23bca`
- `summary.json`: `8ed33a44c302315fae96f9c9d8f740e1b6c068c2dc3e38fd6152bafbc8ac30e0`
- `manifest.json`: `b5430abd67f7c0b1def990c27e38019261e3b6fcd811ea8e929aeb0abbbf33b7`

Four focused CPU tests cover prompt-only isolation, balanced controls/hidden
labels, unchanged strict schema/keep predicates and deterministic sampling.
No old outcome, production pin, quota, candidate or quality hold was modified.
