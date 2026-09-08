# Koolbardi Danish and English: 20-conversation review

Reviewed 2026-09-08. Full transcripts: `conversations.md`; full rows and provenance: `rows.jsonl` in this directory. Reproduce using `scripts/sample_koolbardi_review.py`.

## Method and limitations

Ten conversations per language, uniformly sampled without replacement from the published local packages, using seed `20260908:<language>`. Sampling units are full conversations, not expanded assistant targets. All turns were read. Judgments below are manual qualitative assessments, not independent model audit scores or estimates of corpus-wide defect rates. Positive stored audit verdicts did not prevent the observed problems.

## Danish

| ID | Topic | Judgment | Evidence |
|---|---|---|---|
| DA01 | Placemaking | Usable, minor caveats | Coherent conceptual explanation and follow-up; overconfident normative generalizations and awkward translated terminology. |
| DA02 | Volunteering | Usable, minor edits | Practical multi-turn planning and pitch; minor grammatical errors and optimistic assumptions about available programs. |
| DA03 | Balcony gardening | Repair | Useful beginner scaffolding, but later user turns contain stray quote/brace serialization debris. Some horticultural advice also needs verification. |
| DA04 | Workshop pedagogy | Usable, minor edits | Concrete activities and a consistent 120-minute agenda; minor grammar and overly universal pedagogical claims. |
| DA05 | Travel invitation rewrite | Usable, fidelity caveat | Good iterative rewriting; requested wording is paraphrased and an earlier detail disappears. Not a clean example of exact edit preservation. |
| DA06 | Beginner Python | Usable, safety caveat | Encourages copies and dry-run printing before moving files. The claim that erroneous code cannot damage the computer is too absolute. |
| DA07 | Danish pop critique | Repair | Malformed mixed-script artist name; critique largely validates the user's sweeping historical thesis rather than testing it. |
| DA08 | Cybersecurity policy | Specialist review | Useful MFA/isolation/restoration advice mixed with categorical patching and incident-response prescriptions that lack context. |
| DA09 | Nordic literary speech | Repair | Final answer recommends an unverified, apparently fabricated author/title ("Aleksis Kiroves" / "Jordens skaebne"). One requested concrete work is instead a generic photograph suggestion. Earlier rewriting is useful. |
| DA10 | Limfjord field journal | Usable, minor edits | Concrete observation tasks and worksheet; a final reflection question is grammatically/semantically malformed. |

## English

| ID | Topic | Judgment | Evidence |
|---|---|---|---|
| EN01 | Arts-center email workflow | Usable with caveats | Practical templates and coherent follow-ups; inconsistent urgency prioritization and invented illustrative venue facts should be clearly marked as examples. |
| EN02 | Introductory control systems | Repair | Useful feedback analogy, but describes a dehumidifier as blowing cold air during normal drying. Standard operation reheats the dried air. |
| EN03 | Workplace conflict | Review | Useful coaching scripts; categorical advice not to intervene in the moment needs exceptions for harmful conduct. |
| EN04 | Inclusive workplace survey | Review | Good initial extraction, then unsupported denial of unwritten workplace rules and an absolute confidentiality promise. |
| EN05 | SQLite radio logger | Repair | Time-triggered flushing is promised but absent from code. Measurement timestamps are assigned on batch insertion, losing acquisition times. Explanations of pooling, transactions and WAL also overclaim. |
| EN06 | Robotics safety checklist | Safety review/repair | Structured checklist, but burn-cooling advice specifies at least 10 minutes, below NHS guidance of 20. Emergency terminology is reused for ordinary debugging. |
| EN07 | Control-system lesson critique | Repair | Praises inaccurate teaching: overshoot conflated with instability; sensor sensitivity confused with response speed. |
| EN08 | Italian phrase classification | Repair | Formal/casual criteria shift between turns; the same neutral-politeness rationale yields inconsistent classifications. Grammatical explanations also need checking. |
| EN09 | Homemade fertilizer | Factual review/repair | Confident nutrient, acidity/buffering and dilution claims without evidence or plant diagnosis. Should not be treated as reliable horticultural supervision without verification. |
| EN10 | Volunteer policy critique | Review | Produces organized policy, but replaces warmth with unnecessary formality and treats conversational pronouns as unprofessional despite the user's stated tone goal. |

## Interpretation

Language fluency and multi-turn continuity are generally good. The dialogues supply useful planning, rewriting, explanation and tutoring examples. They are not uniformly high-quality factual or instruction-following supervision: fluent overconfidence, premise agreement, factual errors and missed constraints survive the audits. Similar synthetic style recurs across both languages: elaborate initial prompts, flattering follow-ups, numbered advice and escalating elaboration. This sample does not demonstrate diversity in disagreement, correction, terse requests, native tool use or verified mathematics.

English has more flagged content in this particular draw, but ten conversations per language cannot justify a population quality ranking or different language caps.

## Recommendation, not applied

Retain both sources but provisionally sample approximately half the conversations per epoch in DFM11-post, balanced across topic, interaction mode, complexity and length, rotating coverage across epochs. Preserve all turns of selected conversations. Do not increase repeats. Prefer repair/filtering to simply throwing away useful dialogues; validate a larger stratified sample (100-200 conversations per language) before deciding on a permanent cap.

Current repeat-one exposure is 2.704B Danish plus 2.611B English tokens including repeated conversation prefixes: 5.316B, approximately 14.89% of the 35.708B post mix and 22.22% of its behavior component. Halving this exposure and recomputing the 33% anchor share would yield approximately 31.74B total tokens, of which Koolbardi would be approximately 8.37%. These are proportional estimates, not a completed resample. No sampling configuration was changed.

## External checks

- Dehumidifier operation: [GE Appliances](https://products.geappliances.com/appliance/gea-support-search-content?contentId=35770). Normal exhaust is warm; cold air can occur during defrost, which is not the example's scenario.
- Burn cooling: [NHS burns and scalds](https://www.nhs.uk/conditions/burns-and-scalds/) recommends 20 minutes of cool running water.
- Stable step response may include overshoot: [MathWorks StepTracking](https://au.mathworks.com/help/control/ref/tuninggoal.steptracking.html).
- [Finnish Literature Society](https://tietava.finlit.fi/7-veljesta/ohjeita-ja-opastusta/ohjeita/) identifies Aleksis Kivi and Seven Brothers. The sampled alternative author/title was not corroborated; absence from search is not proof of nonexistence.
