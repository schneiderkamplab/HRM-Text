---
type: Research
title: European Language Expansion Ranking
description: Five-axis, evidence-based prioritization of 28 additional European languages using Hugging Face text and post-training sources.
status: draft
confidence: medium
last_updated: 2026-09-26
tags: [multilingual, datasets, hf, dfm12, research, prioritization]
---
# European Language Expansion Ranking

Research snapshot: 2026-09-26. This is a source-discovery and prioritization
exercise, not a corpus admission decision or a native-speaker quality audit.
No new datasets, training changes or generation jobs are authorized by this page.
The earlier [multilingual pilot](dfm12-multilingual-extension-plan.md) remains
separate. See the [source inventory](european-language-expansion-sources.md) for
verified HF IDs, subset sizes and caveats behind these scores.

User policy (2026-09-26): new language extensions must pass **both** DaLA
feasibility and sufficient high-quality text/instruction supply. Scores cannot
compensate for failure of either gate; unresolved candidates are deferred.
See [joint priorities and mandatory eligibility](european-language-expansion-joint-priorities.md#mandatory-eligibility-policy).

## Scope

Rank additional languages, excluding the existing English, Danish, Dutch,
Polish, Swedish, Norwegian Bokmal/Nynorsk, Icelandic and Faroese expansion.
Russian and Turkish are included as transcontinental European languages.
Reach includes speakers outside Europe: a Europe-only objective would reduce
Portuguese/Spanish/Russian relative to German/Italian. Language reach is not
a judgment of cultural value or of the importance of supporting minorities.

This shortlist covers 28 plausible additions, not every European language.
Bosnian, Montenegrin, Macedonian, Belarusian, Luxembourgish, Breton, Occitan,
Sami varieties, Romani, Armenian and Georgian need a separate deeper inventory.
Do not infer that they lack resources merely because they are not ranked here.

## Five Scores And Weights

All five scores use a 0-5 scale, with half-point steps. They are analyst
estimates based on source cards, HF metadata/viewer statistics, provenance,
task coverage and accessibility, not measured model performance. A difference
under 3 composite points is not a robust ordering. Ties are not meaningful.

| Score | Weight | What earns a high score |
| --- | ---: | --- |
| R: language reach | 20% | Large potential speaker audience and broad cross-border use, globally rather than Europe-only |
| TQ: text quality | 20% | Native edited/educational/reference material; usable structure, provenance and documented cleaning; contemporary coverage |
| TA: text availability | 15% | Substantial accessible HF supply across domains, after plausible quality selection rather than raw crawl size |
| IQ: instruction quality | 30% | Credible human or well-curated synthetic answers; broad tasks, multi-turn and constraint following; documented construction |
| IA: instruction availability | 15% | Downloadable language-specific SFT/preference supply and task diversity; not a model's language claim or aggregate multilingual count |

`priority / 100 = 20 * (0.20*R + 0.20*TQ + 0.15*TA + 0.30*IQ + 0.15*IA)`

Quality receives half the weight because this project needs reliable teaching
examples more than another large noisy crawl. Text is useful primarily as
grounded transformation/QA seed material; this ranking does not reverse the
project's previous continuation-data policy or prescribe raw pretraining.

Reach bands: 5 = exceptionally broad global use; 4 = major language with a
large national and international audience; 3 = substantial national/regional
audience; 2 = smaller national/regional audience; 1 = small audience; 0.5 =
very small active speaker audience. Intermediate scores distinguish broad
bands, not an exact census calculation. The global context is supported by
[Instituto Cervantes](https://cervantes.org/es/sobre-nosotros/publicaciones/espanol-lengua-mundo-informe-2025),
[UNESCO on Portuguese](https://www.unesco.org/pt/days/portuguese-language),
[France Diplomatie on French](https://www.diplomatie.gouv.fr/fr/presse-et-ressources/decouvrir-et-informer/actualites/journee-internationale-de-la-francophonie-2026-le-francais-devient-la-4eme-langue-la-plus-parlee-au),
and the [European Commission's language survey](https://op.europa.eu/en/publication-detail/-/publication/1024ff67-8133-11ef-a67d-01aa75ed71a1).
These publications use different speaker definitions; their figures are not
combined as if they were a comparable census.

For the four data scores: 5 = exceptional breadth/supply with strong evidence;
4 = strong usable shortlist; 3 = viable with material auditing/conversion;
2 = limited or mainly weakly documented/translated supply; 1 = sparse verified
supply; 0 = none verified. IQ never exceeds 4 in this scan because we have not
independently audited representative language-stratified samples. Publisher
claims of "high quality" are not treated as an independent quality measurement.

## Ranking

| Rank | Language | R | TQ | TA | IQ | IA | Priority /100 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | Spanish | 5 | 4.5 | 5 | 4 | 5 | 92.0 |
| 2 | French | 5 | 4.5 | 5 | 4 | 4.5 | 90.5 |
| 3 | German | 4 | 4.5 | 5 | 4 | 4.5 | 86.5 |
| 4 | Portuguese | 4.5 | 4 | 5 | 3.5 | 4.5 | 83.5 |
| 5 | Russian | 4.5 | 3.5 | 4.5 | 3.5 | 4 | 78.5 |
| 6 | Italian | 3.5 | 4 | 4.5 | 3.5 | 4.5 | 78.0 |
| 7 | Czech | 2.5 | 4 | 4 | 4 | 4 | 74.0 |
| 8 | Ukrainian | 3 | 4 | 3.5 | 3.5 | 4 | 71.5 |
| 9 | Finnish | 2 | 4 | 3.5 | 4 | 4 | 70.5 |
| 10 | Turkish | 3.5 | 3.5 | 4 | 3 | 4 | 70.0 |
| 11 | Greek | 2.5 | 4 | 3.5 | 3.5 | 4 | 69.5 |
| 12 | Romanian | 2.5 | 3.5 | 3.5 | 3.5 | 4.5 | 69.0 |
| 13 | Catalan | 2 | 4 | 3.5 | 4 | 3.5 | 69.0 |
| 14 | Hungarian | 2.5 | 3.5 | 3.5 | 2.5 | 3 | 58.5 |
| 15 | Basque | 1 | 4 | 2.5 | 3.5 | 3 | 57.5 |
| 16 | Galician | 1.5 | 3.5 | 2.5 | 3.5 | 3 | 57.5 |
| 17 | Estonian | 1 | 3.5 | 3 | 3 | 3.5 | 55.5 |
| 18 | Bulgarian | 2 | 3.5 | 3 | 2.5 | 2.5 | 53.5 |
| 19 | Serbian | 2 | 3 | 3 | 2.5 | 3 | 53.0 |
| 20 | Croatian | 1.5 | 3.5 | 3 | 2.5 | 2.5 | 51.5 |
| 21 | Slovak | 1.5 | 3.5 | 3 | 2.5 | 2.5 | 51.5 |
| 22 | Lithuanian | 1.5 | 3.5 | 2.5 | 2.5 | 2.5 | 50.0 |
| 23 | Latvian | 1 | 3.5 | 2.5 | 2.5 | 3 | 49.5 |
| 24 | Albanian | 2 | 3 | 2 | 2 | 2 | 44.0 |
| 25 | Slovenian | 1 | 3.5 | 2.5 | 2 | 2 | 43.5 |
| 26 | Welsh | 0.5 | 3.5 | 2 | 2 | 1.5 | 38.5 |
| 27 | Irish | 0.5 | 3 | 1.5 | 2.5 | 1.5 | 38.0 |
| 28 | Maltese | 0.5 | 3 | 1.5 | 1.5 | 1.5 | 32.0 |

## Interpretation And Selection

**Best broad return: Spanish, French, German, Portuguese, Italian.** These
combine reach with multiple practical text and instruction sources. Russian
also ranks highly by global reach; its narrower verified SFT shortlist and
provenance review make Italian an equally reasonable operational choice.

**Best next tier: Czech, Ukrainian, Finnish, Greek, Romanian, Catalan.**
Czech has a documented native/translated instruction mixture. Finnish has
Poro2 plus translated DOLCI. Romanian has multiple translated task collections.
Catalan benefits substantially from BSC's ALIA native-seeded instruction work.

**Best strategic Nordic/Baltic addition: Finnish, then Estonian.** Estonian's
lower composite is mostly reach and lower verified quality confidence, not
absence of data. It has a 100,564-row local Magpie release and 248,718-row
summarization collection. Give these a native-speaker pilot before choosing
to generate a much larger synthetic corpus from scratch.

**Smaller languages with unusually useful support: Basque and Galician.**
BSC already supplies 59,359 and 56,724 ALIA rows respectively, before screening.
They have much better instruction prospects than population-only reasoning
would suggest. Their text pools are smaller and need source balancing.

**Generation-dependent tail:** Hungarian, Bulgarian, Slovak, Croatian,
Serbian, Lithuanian, Latvian, Slovenian and the remaining small languages.
Several have substantial texts or translated task banks, but a less convincing
broad, modern, well-documented chat collection. Prefer native-grounded tasks
and independently checked instruction pilots to mass Alpaca translation.

The ranking is sensitive to the objective: reducing reach weight raises
Finnish/Catalan/Basque; restricting reach to Europe raises German/Italian;
requiring strictly documented open text sources favors German Commons and
selected Common Corpus components over web/PDF-heavy shortlists. Do not encode
strategic Nordic priorities covertly as a higher data-quality score.

## Before Admitting Any Source

1. Pin revisions and count eligible train rows per actual language/variant.
   Never count the entire multilingual repository for each language.
2. Audit stratified random samples for source quality, answer correctness,
   native phrasing, multi-turn consistency, formatting and instruction types.
   The first pilot showed that same-model generation/auditing can falsely
   approve unnatural Faroese/Icelandic; use independent native review where
   feasible, not just another high self-score.
3. Split by original source IDs before translations/transformations. Dedup
   against DFM and across mixtures. Remove benchmark/test overlaps, including
   translated copies; preserve genuine training splits only.
4. Normalize semantic messages into the current Gemma template. Parse tools
   into structured calls/results. Do not train Qwen/Hermes wrappers verbatim.
   Exclude incompatible image-dependent turns and replace foreign self-identity.
5. Review component licenses and redistribution conditions. Dataset-level tags
   are not blanket permissions for all component texts. This scan is not a
   copyright/GDPR clearance, and there is no sixth hidden legal score.
6. Measure tokenizer fertility and accepted token supply per language before
   setting repeats. A million short QA rows is not a billion tokens of chat.
