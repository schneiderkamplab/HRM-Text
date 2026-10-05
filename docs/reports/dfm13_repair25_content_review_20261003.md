# Repair25 Content Review

## Scope and Decision

2026-10-03: read all six fully materialized repaired conversations against their
source messages, plus failed repair outputs to diagnose preservation failures.
Root: `data/dfm13/gemma26-repair25-20261003-v3`. Original artifacts unchanged.
This is assistant semantic inspection, not native-speaker certification or an
unbiased benchmark: these25 were deliberately selected for known repair needs.
No new inference, admission, upload or runtime changes were made.

25 terminal:18 protected-content failures,1 repetition-loop failure,6 re-audited,
3 automated provisional keeps. Of those three, one has no material issue found;
two retain language defects. Do not interpret3/25 as successful repair yield.

## Six Materialized Candidates

Keys below identify outcomes/ and candidates/ files in the root. SHA256 binds
the inspected candidate bytes, not a proposed edited replacement.

| Case key | Candidate SHA256 | Assessment |
|---|---|---|
| c7cbcf3b96b773e4f7e2e71cd7446b52fcb248f19587b226d40ef6a779603d5e | 42c4ca07560d050b0d7bed1184df37e08f4c8d957365c956374f9ee82e393fde | BE magnet: no material issue found. One-sentence response preserves source examples and meaning. Automated keep agrees. High confidence on factual/task fidelity; no native certification. |
| 893352c287aeaf396c87338398d8d3c59b5cd3f28420d351fcac8910ea031d08 | 34edc85361163c446c87aa0b39eb0b8146fc332b45c973743a548f12e3c97442 | LT NLP: automated keep misses remaining agreement defects: prompt uses technologijos ... kurioje rather than the corresponding genitive relative form; repeated natūralaus kalbos should agree with feminine kalbos. Meaning remains intact. Repair incomplete, not factual hallucination. |
| 84af349a0493983ad9d39224a03ceb3e70c78f773f4c9ee084c0f12ac7ea9104 | ccb6b8fa63d51feafd613d5d38742ce76ef71e2bb9da8a9ac91744a1d7eb170e | SL carrots: answer preserves source meaning; prompt retains korenčkjev instead of korenčkov. Automated keep misses the prompt defect. Repair incomplete, not a wrong factual answer. |
| 50668ad140da8842f419b59fa15204585e7f50d5f7deb9ae67c9c20ba3a458e4 | 484aef05ca6c855655f7c282aa1d18f36215ceff687f88d56faae5d46f6c4997 | SQ brittle materials: litari (rope) is not cast iron; source translation remains wrong. Rejection supported. |
| cc93aac70e1d74706ecd247cfba115b45b31334639279cf5ce9128ca1f85252d | 7596ce04e4408285f01b7ff6cef5f935be81806bd7a1bbb6a6968367dadd32d7 | LB synonyms: Wuet remains malformed (Roserei or Wut would express anger); omits source vengeance/punishment clause. Main synonym answer is sensible. Language rejection supported; omission alone should not override correcting an overstrong source gloss. |
| cdb1f035f399e722f5b9e956a78cde21f4278cf85a35a99120f0616ba94e02d1 | e974565319b4e3fb59807b2b6a8ecb7b9155d928a2b1d60c4eb27a815e216abe | FA meal plan: coherent and responsive, but source examples still changed (breakfast avocado omitted, lunch tofu replaced with legumes), and bullets collapsed into spaces. Fidelity repair objective not completed. Provenance says adapt scenario, so these substitutions alone do NOT establish an intrinsically bad meal-plan answer; distinguish this selected repair objective from general adaptation policy. No medical validation claimed. |

## Preservation Failure Diagnosis

The13 code/JSON and5 boxed-answer failures are not evidence of18 wrong factual
answers. For example, LV126 and LB152 remain numerically correct but lose the
required box; HU72 becomes merely an opening brace. BE1039 and LT207 have
corrupted box syntax. These remain contract failures, not arithmetic failures.

All six tool repairs fail prompt JSON preservation. SK tickets and SL parcel
prose improve while JSON blocks disappear. FA parcel correctly changes current
locker location to an available destination, but drops its JSON block and adds
stray text. SQ removes the false current-location claim but still uses an
incorrect locker noun and loses JSON. LB parcel URL-encodes its JSON; LB library
drops JSON and retains poor prose. Native tool call/result objects were not
editable, but that does not make the whole repaired conversation valid.

Other examples: FA CSV replaces code with [code block] and retains the false
claim that a1 also indexes row2. BG plotting gets the axis explanation right but
omits user code and emits percent-encoded replacement code. BE sorting and SL
string search contain instruction deliberation/placeholders instead of code.
SR Hello World changes quotes and emits malformed single-line fenced content.
LV/LB math-code omit executable functions; LV also repeats its explanation.
No evidence here supports weakening the preservation gate. Exact decoding
root cause is not proven by these outputs alone.

## Practical Handoff

Continue already-authorized bulk generation under its existing acceptance and
source-quality gates; do not make this deliberately difficult repair cohort a
new universal calibration barrier. Keep the experimental repair path disabled
for automatic admission. Do not rerun this pilot or retrospectively alter its
receipts. The one BE result is a bounded favorable finding, not production
certification. If repair throughput is later prioritized, preserve protected
segments by construction and ask for scoped prose edits, rather than asking
the model to reproduce immutable code/JSON. That is a future implementation
option, not an executed or validated repair here.
