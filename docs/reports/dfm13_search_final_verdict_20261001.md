# SearchArena Final Verdict

## Decision

Do not bulk-admit this campaign or treat automated keeps as usable training
data. It produced a small set of manually supported, context-fitting answer
candidates, but autonomous source selection, historical grounding, claim
support and reviewer reliability are not production-ready. No data has been
admitted or human-certified. All Search clients are terminal; no additional
GPU or paid work is scheduled.

## Frozen Accounting

Source: `data/dfm13/search-final-inventory-20261001/inventory.json`.
Original task IDs are the denominator; versions are never summed as tasks.
Candidate hashes, equivalent learner-content hashes, receipt pins, context
checks and contrary same-content reviews govern eligibility.

| Quantity | Count |
| --- | ---: |
| Authorized paid reservations consumed | 200 / 200 |
| Completed full cached responses | 113 |
| Unresolved/failed reservations, not refunded | 87 |
| Distinct original tasks with completed cache | 76 |
| Full cached response bytes | 51,219,988 |
| Original tasks | 100 |
| Tasks with saved candidates | 75 |
| Saved candidate versions | 372 |
| Distinct learner messages/tools contents | 347 |

HTTP success is not necessarily useful evidence. Reservations are counted
conservatively, not a claim that the provider billed each unsuccessful request.
The final 86-query batch had 16 completed responses, 69 HTTP 402 and one HTTP 422.
The 402 status indicates payment/credit failure; exact account cause is unknown
because the client did not retain error response bodies. No count reset/retry.

## Exclusive Task Dispositions

| Best eligible task disposition | Count |
| --- | ---: |
| Independently agent-reviewed useful exact version | 16 |
| Automated-only keep, independently unverified | 16 |
| Held, no eligible keep | 19 |
| Rejected, no eligible keep | 6 |
| Unresolved | 43 |
| Total | 100 |

There are 29 IDs with an eligible automated keep, but 13 overlap the manually
supported group. Thus the combined candidate pool is **32**, not 45. These
categories use manual support first, then automated keep, then holds, rejection
and unresolved status. A task may have held historical versions while a
separately reviewed corrected version is useful. Old holds never disappear.

The 16 manually supported candidates comprise:

- Ten source-based answers/explanations with useful supported content: Newsboat,
  linguistic inflection, Paisius source identification, Mattarella, baseball
  stitching, OpenShift, Takayama, SDXL diversity, Polish domain dispute and song
  identification. Individual receipt caveats still apply.
- Four bounded partial/clarification answers: Bluetooth jurisdiction/status,
  pharmacy evidence limitation, Qwen vendor benchmarks versus community
  reception, and Google Play country/app limitations.
- Two creative tasks with source-compatible framing: marketing ideas and a FOL
  crossword. Retrieval is not essential to those tasks.

This is **not 16 fully successful retrieval tasks**. At most ten are the current
manually supported source-answer subset, still requiring final provenance and
admission review. Cisco has useful new product evidence but localized citation
cleanup remains; it is not counted as a clean manually supported version.
The EOIR cached-clause draft awaits independent review.

Many repaired branches use controller-authored native search calls and
controller-selected exact cached evidence. They supervise the final answer
only. They are not verified model-generated search-policy trajectories, and
must not be advertised or masked as such.

## Repair Assessment

- Parallel86: 43 terminal tasks, 1 automated keep, 6 needs-verification,
  36 errors. Thirty-four errors were provider-failure/no-new-evidence cases,
  not a finding that relevant web evidence does not exist. Two were invalid
  generation actions.
- Owner-bound cached recovery: 26 tasks, 16 automated keeps, 6 needs-verification,
  1 reject, 3 invalid-action errors. Ten tasks lacked completed owner cache.
- Six scoped support/citation repairs: 1 automated keep, 5 needs-verification.
  Merely requesting citations did not resolve source support and URL drift.
- Final four-case repair: 2 needs-verification, 2 errors. No additional keeps.

Known weaknesses include fragmented PDF clauses, omission of source dates,
model/product-version conflation, unsupported legal or workflow assertions,
invented examples, and a reviewer accepting plausible but unsupported claims.
Do not force keeps or repair unsupported answers by inserting cosmetic links.

## Next CPU Work Only

Review exact-version manual candidates and the EOIR draft, preserving source
sections/headings/date context and full-provenance lineage. Keep unverified
automated candidates quarantined. Future paid work requires new authorization
and a systemic-provider-error circuit breaker; the current ceiling is exhausted.
No server changes or training actions are performed by this accounting task.
