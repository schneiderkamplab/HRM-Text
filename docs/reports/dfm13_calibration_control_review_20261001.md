# Independent Reassessment of Twelve Arena Controls

Date: 2026-10-01. Agent-authored CPU/source review, not human-certified gold.
Only this report was written. No GPU, judge rerun, dataset mutation or label
rewrite was performed.

## Method and Independence

Read the requested earlier manual report and original sampled conversations,
including the selected assistant target and preceding context. Did not inspect
old automated judge answers, dispositions, explanations or aggregate agreement
results. This is independent of the old judge, but not blind to the earlier
manual report because reading it was explicitly requested. Preference/model
metadata is not evidence of answer correctness.

Inputs:

- `logs/arena_review/20261001/uploaded_quality_samples.jsonl`, SHA256
  `aaa394162b62206dd7b1aeffd585ae29dd35a84ba57b5eedacacfca4c139b534`.
- `docs/reports/uploaded_arena_quality_review_20261001.md`, SHA256
  `c54450d8fa581556b5f8d84d0c70ee85e2abb126910da9451fe7b8c996235ffa`.

"False accept" below is conditional: accepting a target with a decisive defect
would be a false accept. Without reading the old judge outputs, this report
cannot assert which cases that judge actually accepted or calculate its rate.
These twelve selected controls do not estimate corpus-wide quality.

## Decision Summary

Use **three high-confidence material-error controls**, **six broadly acceptable
controls with differing editorial caveats**, and **three diagnostic/uncertain
cases**, rather than twelve rigid disposition labels. Java has verifiable local
code defects, but its overall keep-versus-repair boundary is less clean than the
three hard negatives. The puzzle has unsupported confidence, not an established
alternative correct answer. The phone recommendation lacks a reliable date.

| Source / ID suffix | Target index | Reassessment | Calibration treatment |
| --- | ---: | --- | --- |
| AI-Arenaen `5422691d-5e50-44a8-909e-6f4b884bd5fd:a` | 1 | Acceptable expanded draft; minor source-attribution embellishment | Keep or light editorial repair both defensible; not hard negative |
| AI-Arenaen `c90616aa-93fb-41dc-b526-7ca86fadc635:b` | 1 | Useful logging-policy draft with security-hardening omissions | Do not force repair/reject solely for missing exhaustive controls |
| AI-Arenaen `308f5e6d-79a2-4097-a3ce-7f979e5c642c:b` | 9 | Material unsupported claims about its own inference mechanism | High-confidence negative; accepting unchanged is a false accept |
| 100K `58a859437dfd4e41aad1567f5ac2c133:b` | 1 | Correct central advice; defective/underspecified selector example | Diagnostic code-repair case, not hard failure for using blocking workers |
| 100K `9fa8a86875584778823e3eca66cb8bf2:b` | 1 | Correct capital-role answer | Positive correctness control |
| 100K `53597585763d42758db829e019475abc:b` | 1 | Responsive encouragement | Positive task-fit control; avoid literalizing ordinary reassurance |
| 140K `a6460f5f-36f0-45b5-946c-22b2c7eeed8a:b` | 1 | Wrong printer specifications | High-confidence negative; accepting unchanged is a false accept |
| 140K `05a06fbd-71be-4c59-b2f1-a784850b003c:a` | 1 | Plausible, date-dependent phone advice | Uncertain; not a demonstrated factual negative |
| 140K `0d10d661-9ba2-45b2-ac06-2b732be70ef9:a` | 1 | Recognizes ambiguity, then overstates one interpretation | Diagnostic confidence/logic issue; avoid forced alternative-answer gold |
| 55K `1365787044:a` | 1 | Reasonable governance/MDM distinction | Positive correctness/usefulness control |
| 55K `2310055574:a` | 1 | Reasonable denial of Clippy identity | Positive direct-answer control; brevity is not failure |
| 55K `3641017749:b` | 3 | Incomplete correction followed by false material generalization | High-confidence negative; accepting unchanged is a false accept |

International IDs retain their original `arena_human_preference_<size>:` prefix
in the input; suffixes above are display abbreviations only.

## Three Decisive Negatives

### Model-internals explanation

The target says, literally, "Jeg searcher i min træningsdata" and presents a
step-by-step search-and-combine procedure as what happens when it answers.
The conversation supplies no retrieval tool, training-corpus access or evidence
for that mechanism. This is not merely a harmless statement that learned
patterns influence generation: it claims a concrete action and privileged
knowledge about implementation. It also asserts an English internal pipeline
and causal loss of cultural nuance without establishing that mechanism.

Important qualification: the user reports seeing an English reasoning preamble.
Do not mark that observation false or insist the model never generated English
analysis. The failure is converting visible English text into confident claims
about training composition, inference-time corpus search and internal causality.
Repair should distinguish observed text from unknown implementation. Rejecting
the original target or repairing those claims are both valid dispositions.

### HP E60055

The answer calls the printer an MFP equivalent to M430f and describes two
500-sheet trays. HP's E60055 specifications instead list a 100-sheet
multipurpose feeder and a 550-sheet input feeder. The capacities alone are
sufficient to establish material error, without adjudicating every claimed UI
menu or firmware-dependent priority rule. The caveat about firmware does not
repair the wrong hardware description. [HP E60055 specifications](https://support.hp.com/us-en/product/product-specs/hp-laserjet-managed-e60055-series/9364921),
[HP Tray 2 instructions](https://support.hp.com/us-en/document/c05584101/1000).

The direct specifications page failed to open in this review, but the search
index of that official page exposed the capacities; the official Tray 2
instruction title independently specifies 550-sheet trays. Evidence confidence
is high for this narrow contradiction, not for an invented replacement recipe.

### Carbon steel versus stainless steel

Judge target index 3, not just the earlier claim that carbon steel only works on
gas. The target acknowledges an error but then claims stainless steel is more
universally/reliably induction-compatible because of its alloy composition.
That is not the appropriate material rule: magnetic construction matters, and
austenitic stainless steel is nonmagnetic. Manufacturer guidance identifies
induction-compatible carbon-steel ranges and distinguishes stainless types or
magnetic bases. [De Buyer materials guide](https://www.debuyer.com/en/content/27-guide-to-materials),
[De Buyer carbon-steel range](https://www.debuyer.com/en/619-steel-frying-pans).

Do not replace this with "every carbon-steel pan always works": the manufacturer
also lists a range exception. A good correction should acknowledge the earlier
error, explain the magnetic-base requirement and defer to the specific pan's
compatibility marking. The target's new universal tendency claim is the defect.

## References That Need Softer or Narrower Labels

### Logging policy: earlier rejection threshold was too strict

The user asks for a draft, not a certified policy or an exhaustive compliance
assessment. The answer explicitly requests organization-specific adaptation,
uses placeholders, conditions retention on requirements, and says logging
must be proportional to risk and need. Its parenthetical "ingen minimal logning"
is awkward, but does not necessarily instruct maximal data collection: it can
mean adequate security coverage. It does not explicitly order password or token
contents to be logged. Logging access to sensitive data is not the same as
logging the sensitive payload itself.

Passwords, access tokens and raw session identifiers need explicit exclusions
or appropriate transformation in an operational policy. That is a worthwhile
hardening edit, particularly since this draft requests session IDs. OWASP
supports this improvement, but it does not turn every incomplete policy draft
into a definite false answer. [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html).
Keep-with-caveats or repair is reasonable; mandatory rejection and a claimed
legal violation are not justified by the supplied task/evidence.

### Word puzzle: underdetermination, not an alternative secret answer

Neither backwards-to-forwards nor table-to-chair is literal character reversal.
Thus the target's final claim that `rac` is the most likely answer "based on the
given rules" is unsupported. But it also explicitly acknowledges ambiguity and
offers conditional interpretations. A charitable reader may treat the final
choice as a guess in an informal puzzle, not a claim of logical necessity.

Prefer an ambiguity-handling diagnostic: recognize no unique solution follows,
offer a labeled guess or ask for the intended rule. Repairing the overconfident
closing sentence is appropriate. Do not define a different vehicle word as
gold, label the whole answer factually false without qualification, or force an
exact keep/reject disposition when judging the same response.

### Phone recommendation: historical uncertainty, not present-day falsity

The original prompt has no date and the sampled export metadata supplies no
battle timestamp. A model name with a date-like suffix is not the conversation
date. The response names real models, frames "best" as preference-dependent,
and explicitly warns that UK prices fluctuate. Samsung's dated March 11, 2024
announcement put the A35 at GBP339/389, supporting at least that recommendation's
historical plausibility. [Samsung UK launch announcement](https://news.samsung.com/uk/galaxy-a55-5g-and-galaxy-a35-5g-awesome-innovations-and-security-engineered-for-everyone).

This does not validate every listed model's price, availability or comparative
camera claim at the unknown response date. Conversely, age or present prices
cannot prove the historical answer wrong. Remove from hard negative controls;
recover a reliable timestamp and dated evidence before imposing factual labels.
An unverified recommendation may need verification for admission without being
a proven model false accept. Do not rewrite it as current advice under the old ID.

### Java: local defects, but the asynchronous criticism needs correction

The selector sample never establishes that `socket` has an associated channel;
ordinary `new Socket(...)` objects need not have one. It also unconditionally
cancels the registration after each event and never re-registers it. That is
not a functioning persistent read-event loop as presented. Oracle documents
both the channel prerequisite and cancellation semantics. [Socket.getChannel](https://docs.oracle.com/en/java/javase/18/docs/api/java.base/java/net/Socket.html#getChannel()),
[SelectionKey.cancel](https://docs.oracle.com/en/java/javase/18/docs/api/java.base/java/nio/channels/SelectionKey.html#cancel()).

However, the snippets are alternative sketches with omitted application code,
not one executable program; do not claim an unconditional observed null-pointer
failure or say this code was executed. Blocking I/O and `CompletableFuture`
workers genuinely can avoid busy waiting. Moving blocking work to another thread
is not, by itself, a failure of this user's request. `join()` blocks rather than
busy-spins. Distinguish asynchronous task execution from asynchronous socket I/O.
Prefer a code-repair diagnostic with the exact offending API usage. A reviewer
that calls the answer entirely correct misses defects, but a task-level keep
versus repair label is less certain than the three hard negatives above.

## Positive Controls and Editorial Caveats

- **Municipal rewrite:** the user explicitly requests expansion and a role-play
  draft. Explanatory examples, a greeting and a contact invitation are appropriate.
  Attributing the statutory citation specifically to the citizen adds an
  unsupported detail, so a light grounding edit is reasonable. Do not treat
  benign draft expansion as fabricated real-world action, or declare a legal
  conclusion: this review assesses source fidelity, not current entitlement law.
- **South African capitals:** Pretoria/administrative, Cape Town/legislative,
  and Bloemfontein/judicial with the Supreme Court of Appeal are directly
  supported by [South African government information](https://www.gov.za/about-sa/south-africas-provinces).
  Do not confuse the Supreme Court of Appeal with the Constitutional Court.
- **Chinese encouragement:** the user requests comfort, not diagnosis. The
  response is warm and task-relevant. Its optimism could be less absolute, but
  no crisis or clinical context demands a scripted escalation. Avoid turning
  ordinary encouragement into a hallucination rejection. This is not native
  expert linguistic certification.
- **Governance/MDM:** the high-level distinction between policies/roles and
  management of core entities is suitable for the question. Architectural
  nuances about physical centralization or organizational ownership need not
  be required in a basic overview. Repetition is editorial, not decisive error.
- **Clippy:** the short denial and generic assistant description fit the
  question. It makes no specific conflicting provider claim. Low information
  density is expected for a simple identity question, not grounds for rejection.

## Calibration Changes Recommended

1. Score the three decisive negatives on the specific error and non-acceptance
   of the unchanged target; permit either grounded repair or rejection.
2. Keep Java and the puzzle as diagnostic issue-detection controls, separate
   from strict disposition agreement. Require evidence for the narrow defect.
3. Exclude phones from factual binary agreement until a date is established.
   Treat uncertainty as uncertainty, not an automatic incorrect answer.
4. Allow logging-policy and municipal-draft keep/light-repair disagreement.
   Do not teach maximal completeness or literalism as the acceptance threshold.
5. Label only decisive dimensions. A correctness/grounding defect does not
   automatically imply bad language, irrelevance or safety failure. Leave
   ambiguous dimensions unlabeled rather than forcing independent positives.
6. After freezing these references, join to old judge decisions separately by
   exact source ID and target index. Report hard-control errors separately from
   diagnostic disagreements; do not claim an independently measured false-accept
   rate from this report. Use fresh controls for subsequent prompt evaluation:
   these twelve are now development examples, not untouched held-out gold.
