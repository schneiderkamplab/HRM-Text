# Held QA/P3 Compact26 Re-audit

## Authorized Minimal Follow-up V2

**Terminal update:** PID2925997 exited after48/48 cases,68 distinct requests and70
raw responses (one format failure used all three attempts). No full group passed
or launched. QA22 outcomes:1 keep,7 reject,14 invalid; P3 26 outcomes:26 keep.
All8 previously negative P3 controls were marked keep/pass/pass. These are exposed
manual control disagreements, not a population false-accept rate or a claim that
every former language-only concern is equally severe. Definite counterexamples
remain: lost DNA negation, changed learned/acquired trait, omitted observation,
wrong sports team and answering counts instead of requested years.

QA has28 individual turn reviews returning keep with insufficient/unresolved
support (withheld by deterministic validation), plus one repeated issue-list format
failure. Thus effective zero QA false keeps is NOT evidence of a successful judge:
it is dominated by invalids. Example climate turn outputs keep plus unresolved
support despite relevant evidence. Effective positive recall is1/5 QA and8/8 P3;
the latter coexists with8/8 negative-control keeps. No native-gold claim.

P3 DNA raw response chooses reference8, source_fidelity=pass and answer_correctness=pass
with an empty reason; the source still says do NOT contain DNA while Latvian says
contain DNA. The wrong-sports-team control similarly returns both pass. Adding
dimensions and independent turn calls did not cause reliable contradiction checking.
No semantic resampling or further prompt tuning was performed. No sample approval
receipt was issued, since the precision prerequisite already failed. Fresh random
cases are preserved for inspection, not represented as independently cleared.
Both v1 and v2, all holds, and all original candidates remain intact.

After the v1 failure, the user authorized one minimal follow-up with independent
per-assistant-turn QA decisions and separate P3 fidelity/answer correctness.
`dfm12/held_source_reaudit_v2.py` preserves all v1 files and reuses its orchestration
through a private function namespace (no imported module mutation).32 focused
tests pass, including per-turn AND, exact indices, technical retry ceiling,
semantic-verdict stability and P3 correct-answer/failed-fidelity rejection.

Fresh root `data/dfm13/held-source-compact26-20261004-v2`, launched PID2925997;
log `logs/dfm13/held-source-compact26-20261004-v2.log`. Same28 exposed controls,
20 new deterministic random rows excluding all prior sample/control IDs.26B only,
same4/server cap, up to3 technical attempts, no semantic retries. Full conversations
remain in each independent target call; no earlier review is shown. Every target
must keep for a conversation keep. P3 question/options fidelity is independent
of answer correctness. Exact bounded reference indices replace long model-generated
quotes, avoiding the v1 quote-paraphrase format trap; this is not proof of entailment.

Keeps may have empty reasons. Nonkeeps require a concrete issue and explanation.
The recall threshold remains a diagnostic heuristic on fallible prior positives,
not native gold. Full-source groups remain gated on controls AND one bounded
independent fresh-sample review. No source hold is cleared by this runner.
The preceding preparation/launch description is historical; terminal results above
supersede the launch-pending state. Bulk approval remains false.

## Terminal Status

Authorized2026-10-04 source-aware diagnostic executed on existing8800-8807,
exact google/gemma-4-26B-A4B-it snapshot4d7ae4984b7db7de8f8457170b3f1a419ee76d52,
32K measured context, thinking disabled, no truncation, at most4 requests/server.
No server, publication registry or original source artifact changed. No31B calls.

Root `data/dfm13/held-source-compact26-20261004-v1`, PID2916950, terminal48/48:
28 exposed controls plus20 deterministic random rows. QA22:8 keep,7 reject,
2 repair,5 invalid. P3 26:14 keep,6 reject,6 invalid. Four no-reference rows were
deterministically rejected for unresolved evidence, not asserted factual falsity;
44 initial HTTP responses. Whole conversations and complete candidate references
were supplied, with prior verdicts stripped. Original QA118866 and P3 7680 counts
and packet hashes verified. No full re-audit or admission followed failed gates.

Technical successor `data/dfm13/held-source-compact26-technical-20261004-v1`,
PID2919065, also terminal. Two missing-issue format failures retried twice each
(three total attempts), verbatim requests. Both still fail format. Nonliteral
quotes/wrong selected references and valid semantic verdicts were not resampled.
All raw responses retained. Neither client remains live.

Implementation: `dfm12/held_source_reaudit.py` and separate
`dfm12/held_source_reaudit_retry.py`; tests with matching names in tests/.
23 focused tests pass. Original v1 runtime remains frozen/hash-valid.

## Three Confirmed False Keeps

- QA `02879ee7...` Humasaha: final children count has a valid quotation, but earlier
  assistant assertions about education, resources, strategic motives and comparative
  influence are not established for this person. A related person's article is
  not evidence. The reviewer says all questions are supported but quotes only the
  final children count. Whole-history evidence failure remains.
- QA `478ae939...` CO: a true introductory gas description does not validate
  earlier medical wording about heart short circuits or the rescue advice's
  omission of the supplied warning against poisoning rescuers. This is an
  evidence/history/safety defect, not stylistic perfection. No new medical advice
  or external medical certification is offered by this review.
- P3 `e4ad9482...`: English option B says do NOT contain DNA; current Latvian says
  contain DNA. The selected C answer is correct, but an altered distractor means
  the translated task is not faithful. The review explicitly justifies keep by
  matching the answer key, missing the negation contradiction.

## Four Favorable Sample Findings

- QA `fff21bda...`: Ploksciai church. Correct relevant article explicitly names
  Jeronimas Krispinas-Kirsensteinas and1670. The sole answer preserves founder/date;
  other church hits were not used as support.
- QA `7fae0c3c...`: Filip Vujanovic. Full conversation preserves the supplied
 2003-2018 presidency,1998-2002 premiership, independence/term-count distinction,
  reelections and51.2 percent2013 vote. No material contradiction found.
- P3 `828a76c2...`: beach waves. All four options align with English; B correctly
  identifies sand washing away. No meaningful premise/negation loss found.
- P3 `12d48529...`: packing peanuts. Fewer particles in the same jar and the
  supplied packing-density premise support decreases. Question and answer align.

These four are manually inspected favorable candidates for an explicit small
salvage subset, NOT automatic admission, native gold or corpus clearance. Complete
IDs/request/outcome hashes/source bindings are in the sibling JSON receipt.

## Interpretation and Minimal Improvement

QA effective positive keeps1/5 is dominated by four nonliteral evidence strings:
at least the inspected climate answer is semantically supported but its quote is
a paraphrase. This is not four demonstrated false factual rejections. P3 positives
7/8 refer to prior no-hard-hold judgments, not verified gold. The80 percent
positive threshold is a heuristic recall guard, not a calibrated accuracy claim.
False keeps alone independently block bulk for both sources.

Keep changes small: require a status for EACH assistant turn, with a short named
unsupported/contradicted claim when it fails, rather than letting one good quote
stand for the entire conversation. For P3 require separate pairing/premise-options
fidelity and answer-correctness results; explicitly compare negation and options
before considering the answer key. Prefer short verbatim source anchors to long
paraphrased quotes. Do not add model-computed character offsets or treat successful
quote matching as semantic proof. These are recommendations, not another tuning
round or executed generation. Reject unresolved rows; preserve known holds.

Random-sample keeps were also read: P3 selected references generally support the
six kept answers, subject to the fallibility of WebQuestions answer keys. QA remains
more problematic: Dagestan turns260 enrolled students into260 participants in the
first graduation; Ogg adds an unsupported comparative audio-quality claim. The
Hoover row reproduces a suspect35.2-million-m3 figure from its article, illustrating
why source agreement is not external truth certification. No new exact exclusions
or global rules were applied from these additional observations.

## Commands

Historical completed launch (do not duplicate):
`python -m dfm12.held_source_reaudit run --root data/dfm13/held-source-compact26-20261004-v1`

Recovery command (fresh output required; completed, do not duplicate):
`python -m dfm12.held_source_reaudit_retry --parent data/dfm13/held-source-compact26-20261004-v1 --root data/dfm13/held-source-compact26-technical-20261004-v1`

Logs use the corresponding root basenames under logs/dfm13/. A bounded one-time
sample inspection bridge exists for a passing diagnostic, but was never issued:
both source gates fail. No waiting full-corpus worker remains.
