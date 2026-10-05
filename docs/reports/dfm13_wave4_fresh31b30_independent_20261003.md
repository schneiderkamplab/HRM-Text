# Fresh 31B comparison30: independent source-and-pair review

Date: 2026-10-03. Root: `data/dfm13/wave4/gemma31-fresh-comparison30-v5`.
CPU/read-only inspection of all 30 specifications, all outcomes, all 23 assembled
candidates, raw generations for the seven unassembled cases, and all 30 prior
26B candidate pairs. All 134 manifest input pins verified. No GPU work, candidate
mutation, production approval, native-speaker certification or admission.

## Conclusion

31B fixes some conspicuous 26B defects but does **not** establish reliable quality
across the proposed 13 languages. Short source extractions and the one tool case
look substantially better than long translations. Several automated keeps still
need language, source-fidelity or instruction repairs. Neither the 17 automated
keeps nor the seven contract failures is an adequate semantic score.

This is a deliberately selected diagnostic, not a random model comparison:
14 noncontrol cases and 16 controls; only 11 languages (be, lb, hu, sk, sl, hr,
fa, bg, bs, sr, sq). Latvian/Lithuanian are absent. It covers six families but
only one multiturn, one tool and two code cases. The repeated short story is the
same donor in multiple languages. Questions themselves are regenerated, so this
is paired by specification/source, not identical-question answer evaluation.
Do not extrapolate a production acceptance rate from it. Fresh12 and balanced234
need their own source-level review, especially long targets and actual prompts.

## Contract failures are not seven semantic failures

All seven invalid outputs are parsed JSON with an overlong `user` field. They
copied source text despite an explicit instruction that CPU inserts it. There
were no missing raw answers. Grounded/summary schema has `user.maxLength=900`,
`assistant.maxLength=2400`; generated strings total <=7000. Request wire format
is `json_object`, not an enforced per-field-length grammar.

| ID prefix | Language | Source chars | Generated user chars | Full duplicated-source student tokens | Raw-answer assessment |
|---|---|---:|---:|---:|---|
| 276f1583e9fd | hu | 2288 | 2433 | 2213 | Source-faithful cave summary; better than prior mixed-script answer. |
| 7ec26c9581f9 | sl | 1170 | 1275 | 911 | Three appropriate child-facing sentences; localized grammar `ob dvema rekam` needs correction. |
| 6d45c707a298 | hr | 847 | 1028 | 687 | Correct Jim Clark / Lotus-Climax / two-country extraction. |
| f58eae2c17f8 | bg | 861 | 965 | 999 | Bibliographic records faithful; malformed introductory word `Указанисанителната`. |
| 6f7c4e6140f4 | bg | 1583 | 1643 | 1190 | Source-faithful two-sentence painting summary. |
| a551399b56f5 | sr | 2393 | 2509 | 2085 | Mostly faithful, but `Избегурајте` malformed; requested all numbers yet omits source's two-decade period. |
| d8d72bb414b7 | sq | 2353 | 2427 | 1905 | Mostly source-derived but Arabic `في` intrudes in final bullet; `patë` also needs language repair. |

Token counts above are CPU diagnostics using the existing DFM11 renderer and
tokenizer on the hypothetical untrimmed user+CPU-source+assistant messages. They
are **not** successful assembly receipts or permission to accept the invalid raw
outputs. All seven are below 4096 even with duplication; length in characters is
not interchangeable with model tokens.

`data/dfm13/gemma31-balanced-execution-20261003-v2/wave4/generation-requests.json`
has 198 requests (the wave-four portion of balanced234). Its grounded request
uses the same no-copy instruction, 900/2400 schema and `json_object` wire mode.
Thus this is not demonstrably a historical-request-only artifact. Source windows
are intended to span roughly 500-2400 characters at complete boundaries, already
larger than the generated instruction's 900-character allowance. Source preflight
reserves 512 student tokens and final assembly separately checks every complete
untrimmed target against 4096. These are different checks with different purposes.

### Minimal corrective adapter proposal, not implemented

Keep the frozen contract unchanged. Add a versioned grounded/summary adapter
whose generated field is explicitly an **instruction**, <=900 characters, with
source supplied separately and inserted exactly once by CPU. Keep assistant,
total-generated-text, role, marker, semantic and full 4096-token checks. Do not
apply this to OpenHermes translation, where original user content must survive.

For legacy source-echo recovery, permit only a provable exact source copy (or an
explicitly specified reversible newline representation) to be separated from
the instruction. Preserve raw response and hashes, record the transformation,
require remaining instruction <=900, and reassemble/review the full conversation.
Do not strip fuzzy partial quotations or globally unescape arbitrary backslashes.
Several outputs corrupt copied source words, so automatic exact-copy recovery
will legitimately fail on those. Such cases need bounded instruction regeneration
or an explicit hold, not deletion guessed by a regex. If accepting a user field
already containing the source is preferred, budget source+instruction separately
and suppress the second CPU insertion only after verified source identity.

Tests must cover exact echo, escaped newlines, mutated/partial source refusal,
quotes/backslashes, source inserted once, instruction bound, source hashes,
assistant preservation, OpenHermes exclusion, and actual 4096-token overflow.
Do not blanket-remove maxLength or truncate to achieve the 91K production target.

## All 30 independent pair assessments

`Supported` below means no clear material semantic defect found in this inspection,
not native certification or approval. Localized repair is distinct from wholesale
regeneration. IDs are unambiguous prefixes of pairs.json keys. Invalid raw cases
remain contract-held regardless of the semantic assessment.

| # / ID | Language/family | Independent 31B assessment and comparison with 26B |
|---|---|---|
| 0 aa507562bb3c | be grounded | Broad comparison supported by supplied religion passage; fewer malformed words than 26B. User redundantly copies source and literal newline escapes; normalization still needed. Missing names in source must not be invented. |
| 1 405408f1c6a1 | be OH | Major language repair: `бязмежныміяне`, `салечыў`, agreement defects and mixed `шарик`. Same broad story as donor, but not clean Belarusian. 26B was also badly damaged; not a solved case. Automated rejection appropriate. |
| 2 b876181a7681 | be multiturn | Reject current wording: repeated broken `прыгожы »`, mixed endings and poorly formed craft terminology. Conversation progresses but cannot serve as clean language data. 26B also had malformed terminology and script intrusion; different generated scenarios prevent a precise factual A/B claim. |
| 3 059307a64dc2 | be code | Reference-equivalent correct code for divisor six, negatives, empty list and no mutation. Repair user-facing prose: speaks about 'the user', mislabels generator as list generator and has `уходны`. Better prompt than 26B's incompatible single-number request, but automated keep is not polished completion quality. |
| 4 acb0be89672b | be tool | Supported protocol: asks missing clinic before lookup, arguments/results match, reports availability without falsely booking. Correct April date replaces 26B's malformed `2 сарада`. Strong localized improvement; only one tool case. |
| 5 91acef894d1b | lb summary | Repair despite automated keep. All digit dates retained, but source's **two** laurel leaves becomes uncounted leaves despite all-number instruction. `Ruiersäit`, `vergeen`, `eingefúrt` need language work. 26B also flawed and incorrectly described badge/card as replacing title; 31B improves that relation but is not clean. |
| 6 8da2ae21f656 | lb OH | Large source-task improvement: web-loading donor now preserved, whereas 26B substituted unrelated incoherent craft instructions. Local language defects remain (`loufe`, `fertig`, awkward behavior sentence). Source's sequential/all-files simplification is inherited, not new 31B hallucination; source fidelity alone does not establish technical completeness. |
| 7 3fcbf61e4b5a | lb code | Correct reference code, but violates code-only request with meta narration, including explicit localization commentary. Mixed `Bitte`, `berechnet`; repair. Both models show same meta-answer pattern. Automated rejection appropriate. |
| 8 276f1583e9fd | hu summary | Contract hold only for source echo; raw summary grounded and materially cleaner than 26B's `протягом` intrusion. Preserve distinction between useful answer and invalid wrapper. |
| 9 e55bca92beed | hu OH | Reject current language: `kézholdból`, fused `teliholdvált`, English `wonderful`; 26B also mixed Cyrillic/English. No broad improvement sufficient for long-form Hungarian. |
| 10 06151e6b4054 | sk grounded | Supported extraction: 2000 last, 2002 last, no participation since 2003. Fixes 26B Polish `występ`. User source echo is still a formatting defect. |
| 11 989f0952e629 | sk OH | Repair despite keep: changes crescent to **new moon**, and `mesiac vždy usmieval` lacks reflexive form. 26B was worse (`crescu`, `ploutvou`), but relative improvement is not correctness. |
| 12 083ed11bf8b1 | sl OH | Repair despite keep: donor past 'ate' becomes present `je` rather than past construction; `zaimnik`/`imennik` are not clean Slovenian POS labels. No need to force an English article into Slovenian, but tense and correct labels matter. 26B omitted the user sentence and mixed terminology; 31B partially repairs it. |
| 13 7ec26c9581f9 | sl summary | Contract hold; raw answer fulfills three sentences and main content, with localized case grammar issue. Prior 26B had invented-looking `popodroviš`; not proof of native fluency. |
| 14 481c03ae2b9e | be grounded | Dates/administrative succession source-faithful, but `кароткіе`, `увёлся` are regressions versus cleaner 26B list. Automated language rejection defensible. |
| 15 2717f445c103 | lb grounded | Answer's discovery date and 107 km diameter supported. Generated question awkward (`Wéiert`); prior question was also awkward. Answer-only quality cannot certify the whole conversation. |
| 16 6d45c707a298 | hr grounded | Contract hold; raw three-field extraction supported and prior answer also supported. Does not establish improvement over already-good 26B. |
| 17 9f35de550efa | fa OH | Story meaning substantially retained. Reviewer calls `ماهی کامل` 'full fish', but indefinite suffix on moon makes this a lexical/morphological ambiguity rather than established absurd fish hallucination. Fluent Persian review needed; do not automatically overturn rejection or count as confirmed model failure. Prior 26B phrasing `ماه کامل` avoids ambiguity. |
| 18 f58eae2c17f8 | bg grounded | Contract hold plus malformed introduction; copied bibliography otherwise faithful. Prior 26B cleaner. German titles are legitimate quoted source, not wrong-language contamination. |
| 19 6f7c4e6140f4 | bg summary | Contract hold; two-sentence raw summary supported and no conspicuous material regression. |
| 20 f2bbc9d72e45 | bg OH | Source-faithful web-loading sequence; more natural opening than 26B's `бекграунда`. The source itself over-simplifies rendering order; treat as inherited-source limitation, not certification of a technical tutorial. |
| 21 30e789316c06 | bs grounded | Answer correctly identifies Steinmetz and dates. Generated copied source corrupts words (`Pđešadijski`, `logištički`), while CPU also inserts clean source. Repair prompt duplication/corruption; prior 26B was already grounded. |
| 22 45b2a4476830 | bs summary | Supported one-sentence dates/topic summary, comparable to 26B. Redundant source copy remains. |
| 23 26c693567fa7 | bs OH | Localized translation repair despite keep: rising becomes `nastavio rasti` (continued growing); donor means upward movement. Prior 26B `dizati` preserved this better. No reason to reject fictional lunar travel itself. |
| 24 1336a8c3ccbd | sr grounded | Supported exact 2011/567 extraction. Prior 26B also correct; Cyrillic vs Latin script is not itself a defect. |
| 25 a551399b56f5 | sr summary | Contract hold plus malformed verb and missing two-decade qualifier under all-number instruction. 26B retained that qualifier. Source pesticide claims are historical supplied text, not independently checked current advice. |
| 26 6b5307c20d87 | sr OH | Localized semantic/grammar repair: `nastavio da raste` changes rising to growth; `jedan divni` awkward agreement. 26B shares growth mistranslation, so no material repair of that issue. |
| 27 f5a9136fda5b | sq grounded | Requested role Rıza Soylu and birth year 1942 both supported. Prior 26B also source-faithful on its different question. |
| 28 d8d72bb414b7 | sq summary | Contract hold plus Arabic intrusion `في`; language repair required independently of source echo. Source is itself damaged Albanian and warrants upstream quality screening. |
| 29 118ca95afc41 | sq OH | Repair despite keep: `hënë në tremujore` does not faithfully express crescent moon (quarterly/three-month wording); some awkward clauses. Prior 26B's `hark` was closer in this respect. |

## Practical implications for fresh12 and balanced234

1. Report contract validity, whole-conversation semantic fitness, native-language
   uncertainty and automated-review correctness as separate axes.
2. Prioritize short grounded answers and actual tool invariants for assessment,
   but inspect generated user turns too: copied source and corrupted instructions
   can hide behind a correct assistant answer.
3. Long OpenHermes translations remain the main visible weakness: mixed-language
   intrusions, malformed words and small-but-real meaning changes. These are not
   fixed by a larger user-field limit.
4. Check requested numbers written in words, verb tense, upward movement versus
   growth, and code-only constraints. Reviewers often inspect an opening span and
   miss the decisive later defect; no new brittle exact-span gate is proposed.
5. Keep native-speaker uncertainty explicit, especially Persian morphology and
   Luxembourgish idiom. This review establishes concrete counterexamples, not a
   complete proficiency ranking or permission for 13-language production.

No frozen production module/schema, artifact, admission flag or source registry
was changed by this review.
