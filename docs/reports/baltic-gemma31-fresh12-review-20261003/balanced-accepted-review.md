# Balanced Baltic: Accepted Grounded, Summary and Multi-Turn Review

2026-10-03, independent CPU content review. Root:
`data/dfm13/gemma31-balanced-execution-20261003-v2/baltic`.
Scope: **all10 effective_keep=true cases** in grounded-instruct, summary-rewrite
and multiturn;6 LT,4 LV;18 assistant turns read in full against specifications.
Other three families belong to Poincare. No GPU calls or data changes.
"Accepted" here means automated keep, not admitted/published training data.

## Disposition

**6 good,3 partial,1 material prompt-framing concern.** LT4good/2partial;
LV2good/1partial/1framing concern. These are bounded manual judgments, not a
population accuracy estimate or native-speaker certification. The framing
concern has moderate confidence because the word itself is ambiguous; numerical
and explicit source-fidelity checks have higher confidence. No blanket family
approval/rejection follows from these ten.

Seven single-turn examples copy the source into the generated user request,
then CPU assembly appends it again: all4 grounded and all3 summaries. This is a
generator instruction failure and avoidable duplication, **not seven factual
hallucinations**. The intact appended source remains available. Good below means
content is good despite this shared preparation defect and minor wording issues.

All candidate paths follow `ROOT/candidates/<full-ID>.json`; corresponding
`outcomes/<ID>.json` holds the automated decision. `balanced-pins.json` binds
all ten candidates/outcomes/requests and the source specification file.

## LT Cases

### Grounded1000000: Good
`960b9905fcdf83fd261b2a84c6487e066dc0701429e55be4a19d6806411680c1`

Source Europarl08-02-19 paragraph147. Answer identifies more effective contacts
between competent national authorities as the element preventing product-market
ban risks: `efektyvesni ryšiai ... kompetentingų valdžios institucijų`.
This is directly in the source, one sentence as requested, with no invented
regulatory requirement. Understandable LT. Duplicated source, but no substantive
source-fidelity defect found.

### Grounded1000001: Good
`3ca745b5ec69d92d2975b8fa3047de37e2b1657b3950cacfb465fece212776b4`

Source Europarl08-10-22 paragraph1427. One-sentence answer correctly attributes
self-regulation to airport competition and airlines' freedom to choose
destinations. It does not turn the author's conditional position into a claim
that all airports must be unregulated. Omitting22million/eight airports/150km is
reasonable for the asked explanation. Source duplicated; minor prompt-form
awkwardness does not alter meaning.

### Grounded1000002: Good With Limited Wording Weakness
`b6a786a60dae4716f372293200d263eecd49b495ebe00f89648e97aa034a8663`

Source Europarl10-05-05 paragraph914. Correctly gives30percent and the source's
warning about the emissions trading system. `gali būti pamiršta` is a literal,
weak rendering of the speaker's rhetorical "we can forget" rather than an
invented legal abolition. CO2-price detail is omitted, but the narrow question
is answered. Prompt typo `siūlama`, duplicated source; not a material false fact.

### Summary1000000: Partial, Not a Major False Accept
`55c001b12ea0eb2a8b3c764c350497b247d0d4c300f661e85c359f811fb8b4ec`

Source Europarl09-03-24 paragraph796. Two bullets retain abstention and tobacco
tax/public-health motivation. However the source says tax freedom **can** provide
an incentive (`gali būti paskata`); summary states higher taxes encourage quitting
without that qualification. It omits the proposed restriction on government tax
discretion, the specific reason for abstaining. This is compression/modality
loss, not fabricated policy. `laisvdidinti` is already in the supplied source,
not a new model error. The copied prompt and `naudodamas` are minor preparation/
grammar weaknesses. Do not reject merely because source OCR is imperfect.

### Summary1000001: Partial, Stance Weakened
`f929fcd787803f020b33872c1a414e7685aae24e292ba3a5d395788a6700d191`

Source Europarl08-06-17 paragraph103. Three short bullets preserve approval,
later improvement, and urgency because people suffer/die. `Nebūtinai reikia
blokuoti procesą` (not necessarily necessary to block) weakens the source's
strong opposition to further delay for a tiny compromise. No reversed event or
invented casualty is asserted. Prompt `paprastu kalba` is an agreement error.
Useful gist with a bounded stance/grammar defect, not wholesale hallucination.

### Multi-Turn1000000: Good
`e06fffa06e7f0a4fd5e6563fcb8db872c3aa9b4725e5436ebff5d23bb2506bcb`

Source Wikipedia lt:476835/ZAZ-965. All three turns preserve the supplied numbers:
about1800rubles;322166units;3330x1395x1450mm;2023mm wheelbase;610kg;MeMZ-9650.75L,
rear mounted. Requirements narrow naturally from price/production to dimensions
then engine. The answer names the original engine explicitly; omission of later
MeMZ-9660.9L is not a false claim that no later variant existed. Coherent LT and
no invented specification found. No duplicate source here.

## LV Cases

### Grounded1000000: Good
`7eb4dbd5faa09acc7c10462347dfb6f49b0a03f9b18b15f2b9f02df9501880f1`

Source Europarl07-09-27 paragraph412. One sentence correctly retains approximately
70percent of EU GDP, low consumer confidence, and clear provider obligations to
protect consumers. `maksimizētu` is stylistically heavy, not incorrect content.
Prompt `Lūdzu, sniegt` and register switching are minor; source duplicated.
No invented duty or false statistic identified.

### Summary1000000: Good With Minor Naturalness Issues
`9bd5064e6a883b0be2e5a9021ee7638628736fe61f389f9720c9b762df35a577`

Source Europarl09-11-11 paragraph1004. Exactly two sentences preserve goodwill
and responsibility on both sides and elections as an opportunity to correct
Zelaya/Micheletti's political/legal mistakes. `izrīkošanai`, `cerību pildīšanai`
and name inflection are less natural than alternatives, but meaning remains
clear; this is not pervasive gibberish. Does not assert the election already
succeeded. Duplicated source is the main preparation defect.

### Multi-Turn1000000: Partial, Source-Entailment Qualification
`300a7e68a15285a54348e87475dd3b137575bce1299fd8ffaf10ede720c3782b`

Source Wikipedia lv:169337/JamesFranco. Correctly distinguishes the127Hours Oscar
nomination from the two specified Golden Globe wins, and correctly identifies
Freaks and Geeks. First answer adds `taču balvu viņš neieguva` (he did not win):
the supplied excerpt explicitly establishes nomination, not an explicit denial
of a win. This may be externally true, but this review does not verify outside
facts; safer source-only wording is "the text says nominated, not won". Do not
label it a proven historical falsehood. User `ieguvęs` has a non-Latvian ending;
the assistant's other two turns are clear and source-supported.

### Multi-Turn1000002: Material Prompt-Framing Concern
`c84bc14bfdf5354a1f67c9b62d7d34ea7273be77d1f40474e7a79f1c07e7818f`

Source Europarl11-02-14 paragraph411. Source describes a **funding culture** moving
from grants toward business loans, with business plans, guarantees, venture
capital and SME counts. Initial user asks `attiecībā uz kultūras finansēšanu`
(regarding financing culture), which reads as **cultural-sector funding** rather
than the culture of financing enterprises. The first answer repeats the source
literally and never resolves that domain ambiguity; the assigned subtype is
"clarify ambiguity", but the remaining turns are straight extraction questions.
This is a prompt/relationship error, not an invented SME number. All later facts
are faithful: sound business plans, KIP guarantees/venture capital, >100000 helped
so far and >300000 expected by completion. Minor `palīdzēti ... MVU` grammar does
not drive the concern. Recommend clarifying the financing-practice meaning in
the first question and requiring a fresh review before admitting this example;
no artifact was edited here. Confidence moderate, not a blanket LV-family hold.

## Narrow Follow-Up

Keep full-user language and source-frame review, not only answer-quote checks.
Test prompt-only generation because source duplication recurs despite the
explicit instruction. A narrowly reviewed correction could address the LV
funding-culture question and the three partials; do not silently repair this
calibration or infer blanket production readiness. Rights/access holds are a
separate issue and are not model-quality verdicts.
