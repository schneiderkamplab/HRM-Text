# SimpleStories role and source diagnostic pilot

Development only. References are provisional assistant-manual assessments; no validation or production admission.

## Matched targeted checks

| Judge | Prompt | Defective targets accepted / 28 | Clean targets withheld / 28 | Both members correct / 28 pairs |
|---|---|---:|---:|---:|
| odin | legacy | 4 | 5 | 20 |
| odin | role | 0 | 7 | 21 |
| qwen27b | legacy | 0 | 12 | 16 |
| qwen27b | role | 4 | 0 | 23 |
| flash | legacy | 6 | 3 | 19 |
| flash | role | 1 | 3 | 24 |

These are targeted synthetic controls, not whole-conversation false-acceptance estimates. Each language contributes seven pairs. Source coherence adds coverage absent from the legacy seed check; differences are not attributable to wording alone.

| Check | Qwen old → role pairs correct | Flash old → role | Odin old → role |
|---|---:|---:|---:|
| source_language | 2 → 4 / 4 | 3 → 4 / 4 | 3 → 4 / 4 |
| source_coherence | 2 → 3 / 4 | 2 → 4 / 4 | 3 → 4 / 4 |
| request_validity | 0 → 1 / 4 | 0 → 0 / 4 | 0 → 0 / 4 |
| answer_language | 4 → 3 / 4 | 4 → 4 / 4 | 4 → 4 / 4 |
| answer_fidelity | 4 → 4 / 4 | 4 → 4 / 4 | 4 → 4 / 4 |
| answer_constraint | 4 → 8 / 8 | 6 → 8 / 8 | 6 → 5 / 8 |

## First-attempt generation

| Language / input | Clear | Defective | Borderline | No candidate |
|---|---:|---:|---:|---:|
| da/original | 0 | 3 | 0 | 1 |
| da/clean | 0 | 3 | 0 | 1 |
| en/original | 2 | 2 | 0 | 0 |
| en/clean | 1 | 3 | 0 | 0 |
| hi/original | 0 | 4 | 0 | 0 |
| hi/clean | 1 | 3 | 0 | 0 |
| ja/original | 2 | 1 | 0 | 1 |
| ja/clean | 2 | 2 | 0 | 0 |

| Language / input | Generated turns clear | Generated turns defective | Generated turns borderline |
|---|---:|---:|---:|
| da/original | 0 | 3 | 0 |
| da/clean | 0 | 3 | 0 |
| en/original | 2 | 2 | 0 |
| en/clean | 1 | 3 | 0 |
| hi/original | 0 | 4 | 0 |
| hi/clean | 1 | 3 | 0 |
| ja/original | 2 | 1 | 0 |
| ja/clean | 2 | 2 | 0 |

Newly introduced definite defects: 20 outputs; copied defective source passages: 5 outputs (overlap allowed). Three missing candidates remain unknown semantically.

Whole-example labels include supplied seed quality. Separate `defect_locations` distinguish original input, generated user/source, assistant, and deterministic contract failures. No generation was repaired or retried.

Only Danish H001 (English source with an unexplained map) and Hindi H101 changed between conditions. English H051 and Japanese H151 are identical-source stochastic controls. Four task outputs per seed are correlated. This tiny convenience experiment cannot establish a population-level cleaning benefit.

## Interpretation and next development step

Role-specific checks help on these simple controls, especially Flash, but do not qualify a filter. Flash has 1/28 defective accepts and 3/28 clean withheld; the corresponding one-sided 95% upper bounds are 15.9% and 25.4%. Request validity and authoritative-source selection remain unresolved design problems.
Clean inputs do not prevent generation errors. The English clean-condition QA answer says before departure while quoting a sequence that places the event after departure. Danish generation introduces malformed grammar from cleaned English source. Hindi generation introduces दिए गए कहानी even with a grammatical source. Eleven of 29 parseable conversations fail the existing deterministic contract before any semantic judgment.
Recommended next development change: use vetted native-language request templates and an explicit authoritative source; generate one answer or one edited paragraph per request; construct preservation and selective undo mechanically; count lengths before acceptance. Compare that staged generator against the current whole-conversation generator on additional development seeds. Keep the simpler role-specific checks, but test source-selection explicitly before any new holdout. No such new generator or production policy has been deployed here.

## Operations and limits

Recorded Odin usage estimate: 0.2075 DKK at the previously retrieved provider list prices; not an invoice, excludes missing retry/failure usage and local GPU cost. Actual sends capped at 100 per rolling minute, including retries. Local concurrency 128, Odin 64. Existing shared runtime, journals and receipts used; servers unchanged.

Verification: 32 focused/runtime/limiter tests passed. All three control stages and the generation stage completed with verified receipts. The worker exited and controller lock was released. Repository OKF validation retains an unrelated oversized concept and 15 pre-existing link warnings.

Prompts, references, inputs and code were frozen before votes in `design.json`. Full per-language/criterion control metrics and one-sided confidence bounds are in `control-report.json`; pair totals, not overlapping checks, are the diagnostic comparison unit. Validation remains untouched.
