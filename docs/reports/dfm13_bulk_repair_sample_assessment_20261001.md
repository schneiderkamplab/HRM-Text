# Independent accepted-repair spot check

2026-10-01. Agent-authored manual review, read-only SQLite access, no model/GPU
calls. Authoritative web verification for Andersen and constitutional process;
one CPU numerical endpoint check. Active ledger and candidates unchanged.

Source: `logs/arena_audit/20261001-repairs-followup-v1/ledger.sqlite`, accepted
records with `correction.status=corrected`. Eight deliberately selected cases:
two AI-Arenaen cases (the reported seq9 and seq26) and six early corrected
Human-Preference-100k cases across Russian, Chinese, Spanish, Korean and English.
This is two-source diagnostic coverage, NOT a random sample or coverage of all
bulk sources. No full accepted-corpus cleanliness claim is warranted.

## Findings

| Seq | Topic | Independent assessment |
| --- | --- | --- |
| 9 | Andersen biography | Definite residual factual errors; hard hold recorded separately. |
| 26 | Short science-fiction story | No definite failure: Scandinavian prompt is language-ambiguous and answer is under 20 words. |
| 2606 | Image-generation prompt | Useful core eye-description prompts; repair generic platform overclaims and separate Midjourney-only `--ar` syntax from the shared Stable Diffusion example. Not a certified model/version-specific recipe. |
| 2609 | Unlimited presidential reelection | Repair conceptual confusion: eligibility for repeated elections does not remove electoral challenges. Clarify constitutional amendment procedure rather than imply unilateral presidential amendment. |
| 2613 | Chinese phrase fragment | Uncertain intent: answer silently expands the fragment into a longer phrase and calls that expression common. Ask whether the user means the original idiom/phrase instead of confidently attributing unstated intent. Not native-language gold. |
| 2616 | Normal random sampling | Definite numerical edge defect in inverse-CDF example: `random.random()` permits zero and `erfinv(-1)` returns negative infinity. Resample until `0 < u < 1`; Box-Muller example already guards zero. |
| 2625 | Korean naming explanations | Both descriptions satisfy the 100-character limit (91 and 90 including spaces/punctuation). Relevant to the supplied concepts. Explicit mention of covering half the shortfall could strengthen precision, but omission is not a clear failure for short promotional copy. Not native-language certification. |
| 2632 | Huckleberry Finn outline | Useful broad outline, but literary specifics/chronology need verification before a clean label: exact 1835-1845 range is asserted, feud is grouped after Wilks, and Mary Jane is described as kind to both Huck and Jim. These are verification targets, not newly established hard failures here. |

Sample-bound classification: **2 definite residual errors, 4 repair/verification
targets, 2 without a demonstrated failure on the inspected constraints**. A
verification target is not equivalent to a proven false acceptance.

## Andersen Hard Hold

Seq9, source ID `0ef5568e-0842-4ad0-81c2-b9d8ff095b22:a`, candidate hash
`b6c8dce23db9ac338148f1ac2af18de9b316f74be74c35257a717b9fac00c3f4`.

The accepted answer lists **Fyrtøjet (1840)** and **Den lille tinsoldat (1838)**.
The fresh review explicitly asserts that all listed work dates are correct.
SDU's H.C. Andersen Centre records first publication of *Fyrtøiet* on
**8 May 1835**, and identifies **Den standhaftige Tinsoldat (1838)**.
Sources: [bibliographic entry](https://andersen.sdu.dk/forskning/bib/bibpost.html?BibID=273)
and [canonical title/year](https://andersen.sdu.dk/forskning/motiver/tekststed.html?id=113&oph=1).

Machine-readable sidecar:
`docs/reports/dfm13_bulk_repair_independent_holds_20261001.json`.
This is an explicit exclusion recommendation, **not automatically enforced**:
the parent admission/export process must consume or reconcile it. No live
decision was overwritten, and no corrected answer was automatically admitted.

## Other Evidence and Minimal Follow-Up

- Seq2616: CPU evaluation with SciPy confirmed
  `sqrt(2) * erfinv(2 * 0.0 - 1) == -inf`. This is a deterministic boundary
  counterexample, not an empirical frequency estimate or GPU test.
- Seq2609: Article V assigns amendment proposal and ratification roles to
  Congress/conventions and states, not unilateral presidential action. See
  [National Archives constitutional text](https://www.archives.gov/founding-docs/constitution-transcript).
  The prompt is hypothetical, so conditional discussion is legitimate; the
  stronger intrinsic error is treating repeated reelection as freedom from
  electoral challenge.
- Seq26: do not manufacture a language violation from dataset origin alone.
  The literal prompt is `Skriv en science fiction historie på under 20 ord`.
  Norwegian wording in the response is not independently disqualifying without
  an explicit Danish requirement. Its length satisfies the request.
- Repairs need whole-target review, not only confirmation that the originally
  flagged defect changed. Check new/retained dates, named entities, numerical
  boundaries and explicit constraints. Do not treat a fresh `keep` as external
  verification or reuse this sample as an unbiased accuracy estimate.
