# RepoChat recovery: all 24 controls assessed

## Decision

**Do not proceed to pilot or bulk with this reviewer.** The controls worker has
finished. The supervisor's automatic pilot handoff was cancelled without stopping
the controls. No pilot or bulk inference was launched. Training and shared servers
were not modified. No data is admitted.

Authority: `data/dfm13/repochat-recovery-20261001-v3/control-assessment.json` pins
the plan, final gate, all outcomes and independent review authorities. Raw analysis
and verdict request/response files remain under `controls/<id>/` in that root.

## Complete accounting

| Expected class | Correct verdict | Incorrect verdict | Operational failure | Total |
|---|---:|---:|---:|---:|
| Positive | 13 accepts | 0 false rejects | 1 | 14 |
| Negative | 3 rejects | 6 false accepts | 1 | 10 |
| Total | 16 | 6 | 2 | 24 |

There are 22 completed JSON verdicts. Agreement is 16/22 among verdicts, or 16/24
including unresolved operational failures. All six synthetic paired fixtures were
correct. Among the 18 real-repository manual controls, ten matched, six falsely
passed, and two had no verdict. **None of the six real-repository negative controls
with a verdict was rejected.** These are exposed diagnostics, not an unbiased
population estimate or an independent gold benchmark.

## What improved operationally

The two-request strategy generated complete typed verdicts for all 22 analyses
that returned. Eight of these analyses hit the deliberately bounded 2048-token
limit, but the independent 3072-token verdict allowance prevented them from
consuming the final-answer budget. No final JSON parsing or verdict-length failure
occurred in these 22. This improves completion, not semantic reliability.

Two analysis calls ended about 600 seconds after submission without a response:
positive SagerNet/sing-box (`858813c26098...`) and negative
yaohungt/Multimodal-Transformer (`dcf7dae6f04f...`). Their records contain empty
error strings; the timestamps match the configured 600-second aiohttp timeout,
but the exception class was not saved. They must not be counted as quality rejects.
Future logging should preserve exception type and stage. Do not silently retry or
rewrite these receipts. Total controls elapsed time was approximately 51 minutes.

The request-level semaphore also queued analysis calls before verdict calls,
explaining the long initial interval with zero completed verdicts. This was not an
idle/deadlocked worker. A future revision could bound whole control cases rather
than individual HTTP requests, without increasing shared-server concurrency.

## Six concrete false accepts

| Repository / answer hash prefix | Independent defect | New reviewer behavior |
|---|---|---|
| agnaistic/agnai / `17116893542b` | Claims Redis clients are re-exported from `ws/index.ts`; that file exports messaging helpers, not `clients`. | The analysis reads the exact exports but treats both declarations as confirmation; verdict approves the architecture wholesale. |
| vedalai/neuro-game-sdk / `fcc0a2368c6e` | Omits malformed action-data caveat, overstates immediate force actions, omits optional voice I/O. | Praises comprehensive coverage and treats omissions as unimportant parameters rather than checking the known scope/behavior claims. |
| edereynaldesaintmichel/mode_connectivity / `1d8b9c30678a` | Squared cross-entropy and aggregate norm are described inaccurately; scalar-tensor construction requires a detached-gradient caveat. | Notices squared cross-entropy but explicitly excuses it as a high-level description, and approves the loss explanation. |
| jstrieb/urlpages / `b78b649b65c0` | Availability claim omits dependence on an extant trusted decoder host. | Confirms matching README slogans but misses the qualifying host dependency. |
| ultimatemember/ultimatemember / `b66962cb02a1` | `um_user('ID')` selects the UM profile, not necessarily the logged-in current user. | Substitutes a common-pattern assumption for implementation verification and endorses the incorrect current-user prescription. |
| robertpakalns/VoxtulateClient / `e7058e54b124` | Infers preload/bridge/security and inventory behavior from README and filenames without relevant implementation. | Calls the speculation consistent; the analysis excuses unsupported import functionality because import/export is a common pair. |

These are not label contradictions introduced by the typed schema. The reasoning
itself rationalizes the questionable claims, and the final verdict consistently
passes them. More reasoning tokens or JSON repair alone does not address this.

## Positive and negative discrimination

The reviewer correctly retained the corrected causal-mask versus padding-mask
explanation, the corrected Neuro I/O answer, corrected avatar profile/login
distinction, and other supported repository explanations. It also caught all
three synthetic negatives: a cache-return contradiction, changing CSS despite an
exact-style constraint, and omitting descendant traversal from a requested tree
search. Thus it is not rejecting everything, but success on obvious local
counterexamples does not transfer to nuanced repository-level claims.

## Next recommendation

Keep all original artifacts and holds. Do not use these automated passes to
authorize the 288+3 audit recovery or 395 finalizations. A next reviewer experiment
needs concrete claim-to-declaration checking with full relevant qualifiers and
explicit distinction between source evidence and familiarity/inference, evaluated
on additional unexposed real-repository cases. Repeating generic reviewer wording,
enlarging thinking budgets, or weakening this gate is not justified by these
results. The answer-only finalization fix remains **untested on the 24-case pilot**;
its implementation must not be described as a demonstrated repair.

## Source Recheck and Control Validity

Follow-up CPU reinspection distinguishes raw expected-label disagreements from
independently confirmed semantic errors. This **qualifies the blanket six-false-
accept interpretation above**, without changing any original label or verdict.
Machine-readable authority: `control-disagreement-recheck.json` in the recovery
root. Four disagreements are clear false accepts; two are weaker negative controls:

- **Agnai: confirmed.** `srv/api/ws/index.ts:2` exports named messaging helpers,
  not clients. Its other `export * from './setup'` path was also inspected;
  `setup.ts` only exports `setupSockets`, not clients. Both key declarations were
  already present in the review packet. This is not a missing-evidence excuse.
- **Neuro: confirmed.** The packet includes the possible speaking delay at
  specification line 136 and malformed/non-schema data at 236-240. The answer's
  immediate-action and schema-matching descriptions are stronger than the source.
  The negative case does not depend on demanding every optional field or voice
  feature in an overview.
- **MergePath: confirmed.** The packet contains the squared cross-entropy and
  `torch.tensor` construction. The reviewer knowingly excuses the squared-loss
  difference despite the answer explicitly describing the optimization objective.
  This is not merely a naming/style disagreement.
- **Voxtulate: confirmed unsupported implementation pass.** The question asks how
  it specifically works. The packet does not contain the swapper implementation,
  so a claim of sufficient support is unjustified. Additional pinned-source
  inspection shows `src/utils/swapper.ts:62` uses
  `webContents.session.webRequest.onBeforeRequest`. Conditional words such as
  'likely' can label a hypothesis, but cannot establish the asserted implementation
  or secure bridge. This control properly tests unsupported certainty, not whether
  the reviewer guesses an unseen source implementation.
- **URLPages: weak hard-negative control.** The answer reproduces the README's
  'URL exists/page exists' data-persistence slogan, describes the decoder component
  and warns it is a toy, but omits the trusted/extant host qualifier. Adding that
  caveat is useful; for the broad 'What is this?' question, treating the omission
  as an unequivocal whole-answer rejection is debatable. Do not count this as
  equally strong evidence of reviewer failure as the four cases above.
- **UltimateMember: ambiguous control scope.** The source distinguishes selected
  UM profile from logged-in WordPress user. The query says 'current user' without
  defining which. The answer can be correct for the selected-profile context but
  is unsafe as an unconditional logged-in-user prescription. Clarification or a
  two-context answer is preferable. A revised diagnostic should explicitly ask
  for the logged-in user before assigning an unambiguous negative label. The
  current packet includes `um_profile`, but not the fuller `um_fetch_user` and
  `get_current_user_id` comparison inspected independently.

Thus the conservative result is **four confirmed false accepts, one minor
qualification/control-strength concern, one task-ambiguity concern, and two
operational failures**, not proof of six equally severe semantic failures. There
are still no observed false rejects. Removing both debatable controls would not
make the reviewer ready; the four clear failures retain the pilot/bulk hold.

Both technical failures occurred during analysis, before any verdict request.
The 600.3- and 601.0-second timings match the configured 600-second request timeout.
No response was saved, no JSON was parsed, and the preflight had already passed
the teacher context check. This is timeout-consistent operational failure, not a
bad expected label, refusal, schema failure, or recorded context overflow. Exact
exception identity cannot be recovered because the logger saved only `str(exc)`.
No retry was initiated during this recheck.
