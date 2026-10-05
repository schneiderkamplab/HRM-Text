# Baltic 31B Fresh-12 Independent Content Review

Reviewed 2026-10-03, CPU only. Root:
`data/dfm13/baltic/gemma31-fresh-comparison12-v3`.
Baseline: `data/dfm13/baltic/production-probe-coherence` (26B).
All 12 specifications/source pairs, all 9 assembled conversations, all 12 raw
generation responses, all outcomes, and all baseline conversations were read.
The missing baseline LT story candidate was reviewed in its raw response.
No GPU calls, admission, publication, or changes to original artifacts.

## Summary

Manual whole-example disposition: **2 good, 4 partial, 6 materially defective**.
LT: 2 good / 2 partial / 2 defective. LV: 0 good / 2 partial / 4 defective.
"Partial" means understandable/useful content with a specified defect, not an
automatic admission. These judgments include user prompts, not only assistant
answers. Native fluency is not certified: clear corruption and source mismatch
have higher confidence than subtle stylistic judgments.

Operational results remain **9 valid, 5 automated keeps, 3 invalid**. All three
invalid responses are parseable JSON, rejected for user strings exceeding 900
characters after copying source text. The stored system request explicitly says
the CPU inserts the source and not to copy it. This is not a broken JSON parser
or a clean false rejection: all three also have content/language concerns.

The 31B model improves LT multi-turn grounding and removes most English from LT
math, but it does not consistently fix Baltic generation. Both translated stories
remain unusable; LV math is an automated false accept at the complete-example
level. This selected, historical, non-randomized set cannot establish population
rates or approve production. The running balanced234 is a separate experiment.

## Case-by-Case

IDs below are the **pair/outcome filenames**, not the internal candidate `id`.
Candidate files are `ROOT/candidates/<ID>.json`; invalid cases only have raw
generation bodies. Raw response numbers refer to prefix
`raw/4de0ec201d7f442580908041eb3b81b3-` in ROOT.

### 1. LT Grounded: Defective; Worse Than 26B

`102b6e5ae69b31b2adc3bcaa35bd4dc4f39f1ec529edca668a34852288b7317f`
Raw000001; invalid, no assembled candidate.
Source gives Pažaislis1664–1832 and Vygrių1667–1800. The response preserves the
dates, but corrupts names/forms: `Paųaislio`, `Veiklūū laikotarpis`, and inserts
Korean `두` into the Lithuanian user request. It redundantly copies and corrupts
the source. Baseline gives the correct dates/locations in understandable LT,
with a smaller grammar problem (`punktinę sąrašą`). Numeric fidelity alone does
not rescue the new whole example. High confidence.

### 2. LT Math: Partial; Clear Prompt-Language Improvement

`7ce203b62a40f29f2d6b80a35498d6716d7eb869a35c9192c9202bb20ec77fe7`
Raw000002; valid, automated keep.
`21 kartais 9` uses an awkward/wrong multiplication form; `skaičiumi bokse` is
unnatural boxing terminology. Operation remains understandable, and the raw
explanation correctly derives189+7=196. Baseline was predominantly English
after `Sveiki`. New prompt is substantially closer to the target language but
not polished native text. Boxed196 is CPU-assembled from the reference, not
independent evidence that the model generated the final answer correctly.

### 3. LT Multi-Turn: Good; Improved

`28bbbd89cf7b5e2b7a8874f559e4594ff73bf9d95031dd52be60959f2f12e450`
Raw000003; valid, automated keep.
All three answers track the supplied Danube speech: regional development,
regret about no separate financial program while accepting cohesion-policy
placement, and the Baltic macroregion/environment example. In particular,
`Jis apgailestauja ... tačiau kartu pripažįsta` retains the source's nuance.
Baseline's `išvalyti regionų skirtumus` conflated cleaning the Danube with
reducing regional differences. New text avoids that confusion. Minor wording
preferences do not make a material defect. High grounding confidence.

### 4. LT OpenHermes: Defective; Still Unusable

`45e11813b7e10def9b9c49fe6ae707de906398bf61a24f49ea8f6a4aaf461e58`
Raw000004; valid, automated reject.
Source words are Moon, Whale, Balloon. New user substitutes `Mėnuo, Valas,
Žadutis`; the story repeats `žadutį`, `potrykštė`, `pakylaujo`, and other malformed
forms. The balloon concept is no longer faithfully translated. Basic narrative
order survives, not usable language. Old raw also had severe corruption and an
overlong English-containing prompt; new schema validity is not semantic success.
Old raw: `raw/3099bf2bafe44e0290eeea7db22167d7-000003.response.json`.

### 5. LT Summary: Partial; Mostly Grounded, New Time Drift

`ad8d308c1ea939f86468ef0e7729299711de7fda88909e69c1a684778fb12101`
Raw000005; valid, automated reject.
Three bullets correctly emphasize institutions, leadership, and recovery.
However `nei buvo prieš šimtmetį` changes the source's explicit1937 comparison
to "a century ago" without establishing the speech date. The user also recopies
the source with `institucijos` replacing `institucijas`, then assembly appends
the original again. This is a bounded fidelity/format defect, not wholesale
hallucination. Baseline avoided the relative date but added European Council
cooperation as a goal. Neither is an unqualified improvement. The judge's
assertion that1937 was87years ago is itself ungrounded in the source date.

### 6. LT Tool: Good; Slight Language Improvement

`1220acc7fe2a155a8ecd5b4d4e06a4515adb91a7e882d2fbb88a181a0e6159e3`
Raw000006; valid, automated keep.
Lookup book-197 at branch-10 returns available=true/copy-197; final states exactly
those facts, with no reservation or invented action. Linked call_1, object
arguments, function name, tool_call_id and JSON tool return are consistent.
`Kopijos numeris` is less idiomatic for a library copy than `egzemplioriaus`, but
understandable, not a blocker. Baseline `10-oje filiale` had a clearer grammar
problem. The CPU builds the call/return sequence; this tests localized prose,
not autonomous model tool execution.

### 7. LV Grounded: Defective Whole Example; Good Assistant Extraction

`a5a1569f442b32501a48fee3aa2aba3ee1b4bf3aab5d9d4b1ec409b3ea20307d`
Raw000007; invalid.
Assistant correctly extracts the1994/2019 honors, Watford connection, and first
three albums. User copying introduces extensive corruption absent in source:
`gadä`, `viñu`, repeated `D Džons`, escaped U+0012 controls, and literal backslash-n
sequences. Thus length rejection does not hide a clean whole example. Baseline
has cleaner user text but claims31 albums where the supplied list contains33.
New extraction avoids that arithmetic error but is not usable end-to-end.

### 8. LV Math: Defective Prompt; Automated False Accept

`04f9297775a56b7059fe9a2a1d308c87ff80f0452bc85f940ad5199007654bfe`
Raw000008; valid, automated keep.
`ciparu kaste rūtņainoslyēnakumos` is garbled rather than a natural output-format
instruction. 7*2+12 and raw derivation are correct. Baseline also had an awkward,
internally confused money/day story; the new version simplifies that but does
not solve language quality. The judge cites only `\\boxed{26}`. That reference
answer is CPU-assembled, so this keep does not validate the generated prompt.

### 9. LV Multi-Turn: Defective; No Reliable Improvement

`3ac948c8df70335d521643f820d00f72f900db01d8ccde505ab55d6531611ccc`
Raw000009; valid, automated reject.
`nabadzīgākajās novīlēs` and `tirdzlojusumi` are conspicuous lexical corruption.
First answer adds resource-use claims not stated in source. Last answer retains
the debt/speculation warning; not every turn is wrong. Baseline also had weak
language (`patvērtību`, `nesliktību`) and explanatory additions. The judge's
translation of `novīlēs` as "apartments" is not adopted as evidence; the actual
defect is unsupported/malformed wording, not that asserted dictionary meaning.

### 10. LV OpenHermes: Defective; Still Unusable

`c1e45c5fcb7e56a4f24ff8cc29090a4a22f944a4875169db2dae4d76b4324319`
Raw000010; valid, automated reject.
Examples: `Vaļvis`, `sīva mēneša`, `pilnmoonam`, `noklava`. Story structure remains
recognizable, but pervasive malformed/mixed-language forms prevent native-quality
use. Baseline `Vaļģis`, `zināsmība` and broken punctuation were also defective.
Judge says the correct term is also `pilnmoonam`; that self-contradictory repair
advice is not reliable. Rejection is supported independently by the full text.

### 11. LV Summary: Partial Content; Contract-Invalid

`bd01f2f0af3e55d4e91db4c9b8b319890320b8f6b645f17111f2f841111c2497`
Raw000011; invalid.
Most content follows the supplied historical ETA account, but user `pārliecini
šo tekstu formālāvā stilā` is malformed/misworded and needlessly copies source.
`vairāku simtu cilvēku upuri` is awkward and risks changing "hundreds affected"
into a stronger casualty claim; do not confidently label this a precise death
count. Linking independence demands with `līdz2010` can imply they ended then,
which the source does not establish. The response is cleaner than baseline's
`Konflikta saknes:}`, `förē`, `Mieringa`, but not ready as-is. Source-relative
"ceasefire still in force" must not be treated as independently current news.

### 12. LV Tool: Partial; Faithful, Grammar Regression

`f4925709ad3def71cc0f6c0565a07be119c143434fb924915a7cca7bbbc25bd6`
Raw000012; valid, automated keep.
All identifiers, availability and call linkage match the mock scenario; no
unsupported reservation. User `filiāli ... ir pieejams grāmata` has case/gender
errors; final `filiālī` is weaker than baseline `filiālē`. These are limited
grammar defects, not a fabricated action. Baseline was cleaner. As with LT,
tool structures are CPU-assembled, not generated tool-use evidence.

## Validator and Review Caveats

Both tool outcomes have `content_constraints_valid=false` but `effective_keep=true`.
The local client skips the non-tool generator decoder for tool-dialogue and the
outcome defaults the absent flag to false (`multilingual_calibration_v6.py`).
Separate argument-schema, unique-call and result-link checks all pass. This is
a reporting/flag-semantics inconsistency, not proof of bad tool content; reconcile
it before treating these fields as a universal admission predicate.

No silent raw fallback or maxLength relaxation is recommended. A future isolated
probe could verify prompt-only generation/source insertion and ensure full-user
language review, while preserving this failed evidence. No runtime was changed.

`pins.json` binds this report and all reviewed source, candidate, outcome, raw
response and request artifacts. The manifest explicitly disallows admission.
