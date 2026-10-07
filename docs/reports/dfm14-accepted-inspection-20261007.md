# DFM14 accepted calibration: independent spot inspection

Date: 2026-10-07. Reviewer: Codex, reading saved conversations directly; no new
Gemma judgments or GPU requests. This is an AI inspection, not native-speaker
certification. Language-specific grammatical assessments, particularly Irish,
Welsh, Basque and Maltese, have lower confidence than explicit format, arithmetic,
source-contradiction and tool-authorization findings.

## Selection and evidence

One accepted conversation from each of 16 languages x six families: **96**.
The reproducible sampler ranks accepted IDs by SHA256 of `20261007:<id>` within
each group, preferring calibration v2, with v1 fallback only if v2 is absent.
All 96 selected records actually came from **v2**. This is not a comparison of
v1 versus v2, nor an assessment of the untested v3 compact-grammar changes.

[Full evidence JSONL](dfm14-accepted-inspection-20261007.jsonl) contains the full
conversations, original sources/references, tool definitions, original positive
reviews, IDs, original result paths and SHA256 checksums. Exactly one record per
language/family makes the table below an unambiguous evidence index. Reproduce
selection into a new filename with:

```bash
python scripts/sample_dfm14_accepted_calibration.py \
  --output /tmp/dfm14-inspection-reproduced.jsonl --per-group 1
```

The population is an incomplete, interrupted calibration, not a random sample
of a completed production corpus. No acceptance flags were changed, no rows
were admitted to training and no production group is approved by this report.

## Assessment

* **P**: no material defect found in this inspection; not proof of correctness.
* **C**: concern, cleanup or closer review needed; not automatically a rejection.
* **F**: unsuitable as-is; material defect or severe language degradation found.

**34 P, 33 C, 29 F.** These counts describe the deliberately group-balanced
sample only. They are not estimates of production-wide false-accept rates.

| Language | Grounded | Math/code | Multi-turn | OpenHermes | Summary/rewrite | Tool dialogue |
|---|---|---|---|---|---|---|
| Arabic | P | P | C | P | C | P |
| Welsh | F | F | F | F | F | P |
| Basque | C | C | F | P | F | C |
| Irish | C | F | F | C | F | F |
| Galician | F | C | C | P | C | P |
| Hebrew | F | C | P | C | P | P |
| Hindi | P | C | P | P | F | F |
| Indonesian | C | C | P | C | F | F |
| Japanese | P | C | P | P | C | P |
| Korean | C | C | P | P | C | P |
| Macedonian | C | P | F | C | F | C |
| Maltese | F | F | C | F | F | F |
| Russian | C | C | F | P | F | P |
| Turkish | C | C | P | P | F | P |
| Vietnamese | P | F | C | P | C | P |
| Chinese | P | C | P | C | F | P |

## Main findings and priorities

1. **Whole-answer constraints are not enforced.** Summaries often contain the
   requested sentence(s), followed by an explanation of how the answer obeys
   the prompt. That explanation itself breaks the constraint. Russian asks
   exactly two sentences but adds a third paragraph; Indonesian asks one
   sentence but gets two paragraphs; Chinese asks <=200 characters but gets
   334 total characters, including 293 CJK characters.
2. **Tool structure does not establish user authorization.** Hindi asks to check
   ticket availability, but the assembled conversation reserves four tickets.
   Indonesian asks for parcel status, but the conversation redirects the parcel.
   The tool responses support the final claims, yet the actions were not asked
   for. Check intended action against the user request, not just schema and IDs.
3. **Model-facing instructions leak into assistant text.** Examples include
   literal `explanation:` fields, talking about 'the user' instead of answering,
   repeating reference code, and claiming the CPU verifies the calculation.
   Korean math/code explicitly says the CPU checks the final result.
4. **Source quality remains important even with faithful generation.** Several
   sources are category lists, navigation fragments, or damaged OCR. Galician
   source chronology contradicts itself; Hindi's source associates a purported
   1945 Pakistani premiership with events after independence. Faithfully
   repeating dubious source content does not establish useful factual training.
   These sources were not independently fact-checked on the web in this pass.
5. **Some languages need substantially stronger generation/review.** Welsh,
   Irish and Maltese show conspicuous corrupted wording. Maltese OpenHermes
   even contains Chinese characters inside an ordinary Maltese verb.
6. **Multi-turn completeness needs a final-turn check.** Irish and Russian
   conversations promise to write the requested document later instead of
   supplying it. Basque agrees to update a passage without producing it.

Prioritize deterministic whole-target constraints and action-intent checks;
separate generator instructions from student-facing answers; reject unusable
source windows before generation; recalibrate language/family groups separately.
Retain this sample as a regression set, but evaluate fixes on fresh examples too.
Do not claim a schema/whitespace transport fix resolves these content failures.

## Per-example notes

### Arabic (`ar`)

| Family | Status | Inspection |
|---|---|---|
| grounded-instruct | P | Correctly extracts only the three people with explicit occupations; extra caveat is wordy but preserves the filter. |
| math-code | P | 11*x+3=36; final boxed 3 is correct and matches final-answer-only request. |
| multiturn | C | Coherent crochet dialogue, but categorical advice that wooden/plastic hooks are better for beginners and thick wool is strenuous needs qualification. |
| openhermes | P | Exactly five relevant team-leader interview questions. |
| summary-rewrite | C | Expands bare biography categories into fluent prose; low-information seed and some current-tense assertions unsupported by categories. |
| tool-dialogue | P | Explains ticket lookup and explicitly distinguishes it from booking; no unnecessary call. |

### Welsh (`cy`)

| Family | Status | Inspection |
|---|---|---|
| grounded-instruct | F | Treats page categories as evidence about all films published by Andre Hugon; broken prompt/answer phrasing. |
| math-code | F | Correct reference function, but severely corrupted Welsh prose including `ffwyndl` and `gynumbers`; duplicated code and arbitrary test-case 'Final Answer'. |
| multiturn | F | Invents an unseen historical document, private factory ownership, location and two owners; no evidence supplied. Severe language degradation. |
| openhermes | F | Beach rewrite has corrupted wording such as `Aychwyerwch`, `tai eiran`, `hwythwy`; meaning and native quality unreliable. |
| summary-rewrite | F | Asked for two sentences; adds preamble, commentary and a literal `explanation` field. Broken Welsh throughout. |
| tool-dialogue | P | Lookup uses supplied clinic/date/service; reports the returned 10:30 slot without claiming a booking. |

### Basque (`eu`)

| Family | Status | Inspection |
|---|---|---|
| grounded-instruct | C | Mostly follows netbook source, but visibly awkward language and `Intel Intelen` repetition; outdated-source statements should remain attributed. |
| math-code | C | 156-20+17=153 correct; localized gardening/counter scenario is garbled and uses mixed `boxetan`. |
| multiturn | F | Claims the source supplies a county-town list when it has a category label; agrees to update content but never gives the requested revised text. |
| openhermes | P | Five plausible username suggestions; English usernames are permissible literals, not a language failure. |
| summary-rewrite | F | Turns a table of contents into assertions about emphasis/importance not in the source; malformed prose and non-bullet preamble despite bullets-only request. |
| tool-dialogue | C | Correct read-only semantics, but unnatural/corrupted wording (`eszertako`, `emitaik`) needs language repair. |

### Irish (`ga`)

| Family | Status | Inspection |
|---|---|---|
| grounded-instruct | C | Captures budget-deficit obligations but has substantial grammatical awkwardness and misspellings in both prompt and answer. |
| math-code | F | Reference affine code is correct; Irish task/explanation is substantially garbled, including loss of clear wording for duplicates and nonsensical cooking framing. |
| multiturn | F | Guesses a technical meaning from damaged OCR; then repeatedly promises a simplified rewrite without producing it after explicit confirmation. |
| openhermes | C | Tweet performs the task, but duplicated `is is` and poor vocabulary; unsupported promotional superlatives. |
| summary-rewrite | F | Exactly-two-sentences request gets duplicated summaries plus explanation; visibly degraded Irish. |
| tool-dialogue | F | Correct lookup arguments/count, but ticket/event request is corrupted (`fhicseanna`, `aíocht`); unsuitable language supervision without repair. |

### Galician (`gl`)

| Family | Status | Inspection |
|---|---|---|
| grounded-instruct | F | Source says Xuande restored eunuchs; answer says he reduced their power. Three-points-only request also gets pre/postamble and meta-explanation. |
| math-code | C | Correct divisible-by-9 code; repeated code, third-person generator-style explanation and unnecessary 'Final result: 18' for a test case. |
| multiturn | C | Faithful to fossil-DNA source, but turns disputed claims into confident conclusions and drops the source's reliability caveat. Needs factual/source review. |
| openhermes | P | Correct Python membership rewrite; contextual return statements inherit the user's code fragment rather than claiming a standalone program. |
| summary-rewrite | C | Football career summary substantially faithful; Spanish intrusions such as `trayectoria` and `a mitad` need language cleanup. |
| tool-dialogue | P | Reports temporary service failure without fabricating availability or taking action. |

### Hebrew (`he`)

| Family | Status | Inspection |
|---|---|---|
| grounded-instruct | F | Three substantive sentences followed by literal `', 'explanation':` debris; violates three-short-sentences output requirement. |
| math-code | C | Stable-unique reference is correct, but duplicated code/tests and imperatives telling the user to solve the task leak generation scaffolding. |
| multiturn | P | Answers questions about the supplied commentary with generally faithful references and coherent follow-ups. |
| openhermes | C | APA structure broadly useful, but punctuation is embedded on the wrong ends of literal Latin examples; should check bidirectional presentation. |
| summary-rewrite | P | Wrestling-event bullets track supplied outcomes and distinguish preliminary matches. Minor typo, no material defect found. |
| tool-dialogue | P | Describes availability lookup and explicitly says it does not book an appointment. |

### Hindi (`hi`)

| Family | Status | Inspection |
|---|---|---|
| grounded-instruct | P | Correct numbered extraction of supplied external-link titles, without invented URLs. Seed is low-information but task is valid. |
| math-code | C | Correct affine reference; overproduced explanation with repeated code and 'Result: Success' scaffolding. |
| multiturn | P | Five follow-ups about the supplied inauguration text are answered coherently and retain the 'alleged' qualification for violence. |
| openhermes | P | Correctly identifies `She` as the subject of the supplied English sentence, explained in Hindi. |
| summary-rewrite | F | Repeats the source's dubious 1945 premiership claim without qualification; adds an explanation after the requested three-bullet response. |
| tool-dialogue | F | User asks to check ticket availability; assistant reserves four tickets. Structured quantity/attendee data is not itself authorization to reserve. |

### Indonesian (`id`)

| Family | Status | Inspection |
|---|---|---|
| grounded-instruct | C | Correct candidate list, but unnecessary English-labelled `Explanation` about answer construction should not become the target style. |
| math-code | C | Correct range-span code, but three equivalent versions plus tests and awkward prose are unnecessarily repetitive. |
| multiturn | P | Location, road access and traditional house answers follow the supplied tourism passage. |
| openhermes | C | Swap-first/last code works for shown nonempty list but errors on empty input; add a guard or state the precondition. |
| summary-rewrite | F | One-sentence summary followed by a second explanatory paragraph; explicit output constraint violated. |
| tool-dialogue | F | User only requests parcel status; assistant redirects parcel to a locker without user authorization. |

### Japanese (`ja`)

| Family | Status | Inspection |
|---|---|---|
| grounded-instruct | P | Extracts the listed siblings and identifies the nephew and parent correctly. |
| math-code | C | Correct range-span reference, but repeated code blocks, execution instructions and `final_answer` containing test outputs pollute presentation. |
| multiturn | P | Coherent library-card guidance, qualifies branch compatibility and advises checking local exceptions. |
| openhermes | P | Produces a natural narrative rewrite preserving the beach/swimming/castle/lunch sequence. |
| summary-rewrite | C | Accurate three-sentence corporate summary plus an unnecessary fourth completion-notice sentence; request says approximately three, so not a hard failure. |
| tool-dialogue | P | Appropriately reports lookup failure without claiming book availability. |

### Korean (`ko`)

| Family | Status | Inspection |
|---|---|---|
| grounded-instruct | C | Distinguishes film settings from filming locations correctly, but desired bullet organization is only partly followed and includes a meta-explanation. |
| math-code | C | Correct clamp code; bizarre year range in scenario, repeated solution and explicit claim that CPU checks final result are scaffolding leakage. |
| multiturn | P | Iteratively produces and revises a child-friendly coding introduction as requested, with continuity across turns. |
| openhermes | P | Correct membership rewrite and explanation of why `s == 'a' or 'b'` is always truthy. |
| summary-rewrite | C | Substantive summary tracks the provided appellate text, but generated prompt identifies lower-court citation as the supplied ruling. Court-level provenance needs clarification. |
| tool-dialogue | P | Explains book lookup versus reservation without taking unnecessary action. |

### Macedonian (`mk`)

| Family | Status | Inspection |
|---|---|---|
| grounded-instruct | C | Correct factual answers; `factual QA` in user and `explanation:` in answer expose construction metadata. |
| math-code | P | 11*x+11=165 gives correct boxed 14; minor wording awkwardness does not change equation. |
| multiturn | F | Invents a recycling program's UI, 24-hour correction policy, next-month effective date and email workflow without a supplied policy or fictional-role setup. |
| openhermes | C | Narrative task completed, but grammatical errors such as `првиот тонови` need repair. |
| summary-rewrite | F | Exactly two sentences requested; gives two summary sentences plus a third meta-explanatory paragraph. |
| tool-dialogue | C | Missing-warehouse clarification works, but user's clarification already reveals exact stock count before the lookup. Synthetic evidence leakage weakens the example. |

### Maltese (`mt`)

| Family | Status | Inspection |
|---|---|---|
| grounded-instruct | F | Damaged OCR source and generated corruptions such as `Asssoċjazzjoni` and `Ssweżiżi`; redundant explanation/final answer. |
| math-code | F | Correct reference code but severely degraded Maltese, German `Bitte`, and prompt ambiguity between selecting multiples and summing them. |
| multiturn | C | Main IMI information mostly preserved, but initially overgeneralizes 'some exchanges' to all and contains broken wording. |
| openhermes | F | Chinese characters embedded in Maltese user text (`nġ使其u`), widespread poor wording; correct bash command does not rescue language quality. |
| summary-rewrite | F | Converts parallel complaint into the reason no maladministration was found; reverses seeking information toward providing it, plus format/scaffolding problems. |
| tool-dialogue | F | Lookup count correct, but final `L-imfarrġament` is not an appropriate lookup-result expression; damaged request/answer language. |

### Russian (`ru`)

| Family | Status | Inspection |
|---|---|---|
| grounded-instruct | C | Useful faithful three-section answer; unnecessary explanation of how the answer was constructed. |
| math-code | C | Correct code and examples, but repeats solution and instructs user to implement/execute it; stray quote and generation-style text. |
| multiturn | F | Asked for the drafted revised section, promises it will be ready within an hour instead of providing it; invents deferred work. |
| openhermes | P | Relevant practical parent/child transport guidance; no material defect found. |
| summary-rewrite | F | Exactly two sentences requested; appends a third explanatory paragraph. |
| tool-dialogue | P | Clearly distinguishes information-only book lookup from reservation. |

### Turkish (`tr`)

| Family | Status | Inspection |
|---|---|---|
| grounded-instruct | C | Correct source-based Morelos extraction, but English `Explanation` plus third-person narration leaks construction metadata. |
| math-code | C | Correct multiples-of-four code; unnecessary test-result final answer and duplicate solution. |
| multiturn | P | Source-grounded population answers; explicitly declines to invent details of religious branches absent from text. |
| openhermes | P | Correct `if not var` explanation for the user's boolean example, with Python 3 print syntax. |
| summary-rewrite | F | Claims source contains cast/character information when only empty headings exist; copies the source after a single-sentence request. |
| tool-dialogue | P | Reports temporary ticket lookup failure without fabricating data. |

### Vietnamese (`vi`)

| Family | Status | Inspection |
|---|---|---|
| grounded-instruct | P | Correct three-part extraction about Tu Hac and the proposed marriage from the literary passage. |
| math-code | F | Arithmetic correct (17-1+8=24), but user asks for square brackets (`ngoặc vuông`) while answer uses LaTeX boxed notation. Localization changed the format contract. |
| multiturn | C | Fluent speaker guidance, but assumes an unspecified device/app supports exact Vietnamese commands and a 1-10 volume scale. |
| openhermes | P | Valid elementary C multiplication example with coherent explanation; not hardened input/overflow handling, which was not requested. |
| summary-rewrite | C | Three relevant bullets, but treaty wording conflates reserve placement with later scrapping; extra greeting/outro weakens exact-output discipline. |
| tool-dialogue | P | Explains required tracking/postcode inputs and correctly limits the operation to lookup. |

### Chinese (`zh`)

| Family | Status | Inspection |
|---|---|---|
| grounded-instruct | P | Correctly extracts time limits for different archival transfers and retains the extension exception. |
| math-code | C | Correct even-number sum code; redundant duplicate solution and instructions to execute it. |
| multiturn | P | Useful sequential drafting help that incorporates the user's requested leave details and prior conversation. |
| openhermes | C | APA overview useful, but converts a Chinese book title into English without preserving the original/transliteration or clarifying citation convention. |
| summary-rewrite | F | Exceeds <=200 characters (334 total, 293 CJK), adds explanation, and turns delisting into ceasing operations, which the source does not establish. |
| tool-dialogue | P | One retry after temporary lookup error, then accurately reports six units without an unauthorized action. |

## Deterministic cross-checks and limitations

All 16 math/code final outputs match the stored reference: four boxed numerical
answers, twelve final Python blocks whose parsed AST matches the reference AST.
No generated code was executed. The assembler inserts reference answers/code,
so this is an assembly-consistency check, **not independent proof of generated
reasoning quality**. Vietnamese proves a correct stored answer can still violate
the localized prompt's format. No statistical confidence claim or blanket
native-language approval follows from one example per group.

The reported P/C/F classifications are inspection notes, not modifications to
the source audit ledger. All original positive reviews and held-training flags
remain available for debugging and recalibration.
