# Independent CPU assessment of the 76-case 31B comparison

2026-10-03. Root: `data/dfm13/wave4/gemma31-quality-comparison`.
All **76 done**, **46 keep / 30 reject**. The preparation manifest's
`prepared_not_started` is historical; live read-only database state supplied these
counts. No manifests, approvals, candidates, reviewers or GPU processes changed.

## Scope and bindings

Read all 76 reviewer decisions and fully inspected 15 selected raw conversations
with their supplied source/reference/tool evidence: zero-based index positions
1,4,6,9,14,26,29,33,40,45,51,55,66,70,71. This deliberately includes all five
documented controls and suspicious disagreements, not a random quality sample.
No population precision/recall estimate or broad native-language certification.
Previous `original_keep` values were not treated as gold labels.

All 76 candidate file hashes verified. The review records' messages and source
match their candidate files, and every serialized request contains exactly that
record with model `google/gemma-4-31B-it`. The system explicitly asks to inspect
ALL generated user and assistant prose. These checks establish prepared-request
integrity, not an independent reconstruction of server-side tokenizer rendering.
The stored results are parsed judgments, not a newly executed review.

Hash-bound snapshot/receipt:
`data/dfm13/wave4/gemma31-quality-independent-assessment-20261003/`.
Snapshot SHA256:
`9a9c3fbf219a927c659bd31759922478a75da491a1e094d314362cc574e66502`.
It binds every complete job ID, candidate path/hash, payload hash and result/hash.
Candidate filename prefixes below resolve through that snapshot/index.

## Concrete false accepts

1. **SL summary, `7ec26c9581f9` (index26, control), keep 5/5/5.**
   The assistant adds `zgodnji` (early) to the Kremlin description, where the
   supplied text only says Kazan has a beautiful Kremlin. It also retains
   `z podzemno` rather than `s podzemno`; the generated user says `za otoka`
   where the child-summary task calls for `za otroka`. The dates/persons otherwise
   follow the source. This is a missed source modifier and copy-editing defect,
   not a claim that the whole factual answer is wrong.
2. **LB summary, `91acef894d1b` (index29), keep 5/5/5.**
   Source: the honorary title was implemented/expressed through an insignia and
   identity card (`ëmgesat duerch`). Answer: it was replaced by them (`ersat`).
   That changes the relationship between the title and its insignia. The answer
   also contains malformed wording such as `posthum verleeft` and the unfinished
   construction `vun der Regering zougewisen konnt`. Preserving the dates does not
   make this a faithful professional rewrite.
3. **LT grounded, `102b6e5ae69b` (index66, control), keep 5/5/5.**
   Generated user has `punktinę sąrašą`, an agreement error; `sąrašą` is masculine
   and requires `punktinį`. The assistant's monastery dates/places follow the
   supplied passage. This is a whole-generated-conversation copy-edit failure,
   **not an assistant factual failure**. Severity is lower than the source errors.

Additional concerns, not added to the definite count: SK multiturn `080ee1e1869c`
(index1) includes malformed wording (`aký mal ... vzdelanie`, `zverhl`) and
unsupported rhetorical embellishment about understanding Roman weaknesses; LB
grounded `2717f445c103` (index6) returns a numbered list despite asking for a text
block, but the prompt also asks for a list, making that formatting label debatable.

## False rejection and invalid rationales

- **Clear false rejection: SR tool dialogue `363f1372d76f` (index9).**
  Reviewer calls `Proverio` Ijekavian and contrasts it with `proverim`. Both are
  Ekavian; the Ijekavian contrast would involve `provjer-`. The actual trajectory
  faithfully uses book-778/branch-11, receives available=true/copy-778, and reports
  availability without inventing a reservation. No substantive defect found in
  this inspected conversation. This judgment is an assessment, not admission.
- **Invalid semantic rationale: SQ summary `d8d72bb414b7` (index45).**
  Reviewer treats higher socioeconomic *needs* as contradicting lower
  socioeconomic *status*. Those are not inverse claims about the same quantity.
  The source itself is poorly formed and the generated prose has additional
  language issues, so do not turn this into an unconditional keep or count it as
  a proven globally clean row. The stated factual rejection is unsound.
- **Invalid script rationale: BE summary `e919dfdd553a` (index55).**
  Reviewer calls `таксама` Chinese characters; it is Cyrillic and a Belarusian
  word meaning also. There is no Chinese text in the cited phrase. Other wording
  and grammar remain reviewable, so this proves a fabricated rationale, not that
  every part of the candidate merits acceptance.
- **Correct reject, extra wrong claim: BS grounded `cc94255e9728` (index40).**
  Long explanation violates the final-number-only request. But the answer -20.5
  is consistent with rounding the reviewer's own -20.48 calculation under the
  interpreted 10^6 distance. Calling that calculation incorrect is not justified;
  the source's plain-text `106` also deserves notation caution.
- **Correct reject, overreaching rationale: LT math `7ce203b62a40` (index70).**
  Generated prompt is predominantly English despite the Lithuanian task, a valid
  quality problem. The bare boxed 196 is mathematically correct and follows the
  explicit final-number/boxed request; lack of greeting is not another defect.

## Controls and useful reviewer successes

**Three of five documented controls rejected; two passed.** Independent inspection
supports the three rejects: LV `a5a1569f442b` lists 33 studio-album entries but
answers31; LB `1da1bc527cdb` incorrectly applies the original symbolism to both
sculpture and plaque; BE `405408f1c6a1` contains visibly degraded generated wording.
The two misses are the SL and LT controls above. These five are diagnostic
references, not a representative native gold benchmark.

Useful additional successes: LB math `e2fda245e2c0` (index51) rejects a reference
answer56 because the actual generated question asks 23 trips at twice10 euros,
which gives460 under that reading. It correctly prioritizes the actual question
over the stale arithmetic reference. SL `a124a64c9962` (index33) requests yellow
circles and receives plain black bullets: rejecting the unmet explicit formatting
request is defensible even though the reviewer wrongly calls it a negative
constraint. All seven listed school names are present.

## Operational implication

The reviewer catches meaningful source errors but is not a reliable native gold
oracle: false accepts coexist with invented dialect/script objections. Do not
equate `keep` plus uniform5 scores with independent quality approval. Do not
silently flip rejected rows based on this report either.

Minimal durable next calibration targets: faithful attribution in paraphrases;
generated-user grammar separate from assistant correctness; valid dialect forms;
higher need versus lower status; correct numeric-only answers; rounded arithmetic.
Require reasons to quote an actual defect and distinguish grammatical, factual
and instruction dimensions. Recheck fresh outputs independently, especially
source-grounded summaries and LB/SL/LT prose. This report does not assess the
running fresh30 generation and supplies no production approval.
