# XL 2990K EMA: 21-language qualitative smoke

**Checkpoint:** `checkpoints/dfm12/XL-from-dfm11-epoch10-noidentity`, `step_2990000`, EMA.
**Backend:** Transformers HRM-Text, HF-split export, BF16/SDPA, PrefixLM prompt tokens enabled.
**Prompt contract:** training tokenizer (Mistral regex fix disabled), training Gemma template, thinking disabled, no system prompt.
**Decoding:** greedy, batch one; 768 new tokens for stories, 384 for correction/summary; no repetition penalty. Eight GPUs alongside training, 8 GiB PyTorch allocator cap per worker. No W&B.
**Review:** Codex direct qualitative review; no external judge model.

## Rubric

0 failed/unusable; 1 major problems; 2 usable with reservations; 3 strong on this specific prompt.

Scores are reported separately as task success / language correctness / fluency. Fluency includes natural phrasing and coherent discourse, not merely grammatical sentences. Correction permits valid alternative repairs. Summary review checks faithfulness, the key change/result and exactly two sentences. Story review checks the requested duck/astronaut/beak premise, conversation, obstacle, ending and coherence.

One authored prompt per task and language is a qualitative diagnostic, not a statistically reliable language ranking. Scores are not native-speaker certification. The Finnish correction prompt is context-sensitive. Token caps constrain stories, but visible repetition and contradictions are failures independent of the cap.

## Main Findings

- Short corrections and summaries remain substantially stronger than creative writing.
- Nineteen corrections succeed clearly. Polish correction fails; Finnish makes an unrequested tense change on a context-sensitive prompt.
- Summaries generally preserve the main event in two sentences; the Polish answer changes April to February, and several summaries invent new reading clubs.
- Stories frequently repeat, contradict their own beak premise, omit conversation, or contain substantial language errors. These results do not establish dependable open-ended multilingual writing.
- Compared qualitatively with the earlier 2930K smoke, Icelandic and Faroese corrections improve, but weaknesses in long-form generation remain. This is not a statistically controlled improvement claim.
- EMA export uses the training tokenizer with the Mistral regex fix disabled. No W&B metrics were written.

## Task Summary

| Task | Score 3 | Score 2 | Score 1 | Score 0 | Length finishes |
|---|---:|---:|---:|---:|---:|
| grammatical_error_correction | 19 | 0 | 1 | 1 | 0 |
| creative_writing | 0 | 8 | 9 | 4 | 7 |
| summarization | 8 | 12 | 1 | 0 | 0 |

## Per-language Summary

Correction/story/summary columns are **task-success scores**, not combined quality scores. Language and fluency columns are descriptive means across just three examples.

| Language | Correction | Story | Summary | Language /3 | Fluency /3 |
|---|---:|---:|---:|---:|---:|---:|
| Danish | 3 | 0 | 2 | 2.67 | 2.00 |
| English | 3 | 2 | 3 | 3.00 | 2.67 |
| Norwegian Bokmal | 3 | 2 | 2 | 2.67 | 2.67 |
| Norwegian Nynorsk | 3 | 1 | 3 | 2.33 | 2.00 |
| Swedish | 3 | 2 | 2 | 2.00 | 2.00 |
| Icelandic | 3 | 0 | 2 | 2.00 | 1.67 |
| Faroese | 3 | 0 | 2 | 2.00 | 1.67 |
| Dutch | 3 | 2 | 3 | 2.33 | 2.33 |
| Polish | 0 | 1 | 1 | 1.33 | 1.33 |
| German | 3 | 1 | 3 | 2.33 | 2.00 |
| French | 3 | 2 | 3 | 2.67 | 2.67 |
| Spanish | 3 | 2 | 2 | 3.00 | 2.67 |
| Italian | 3 | 1 | 2 | 2.33 | 2.00 |
| Czech | 3 | 0 | 3 | 2.00 | 1.67 |
| Portuguese | 3 | 2 | 2 | 2.67 | 2.67 |
| Finnish | 1 | 1 | 2 | 2.00 | 1.67 |
| Estonian | 3 | 1 | 2 | 1.67 | 1.67 |
| Catalan | 3 | 1 | 2 | 2.00 | 1.67 |
| Greek | 3 | 1 | 3 | 2.67 | 2.33 |
| Romanian | 3 | 1 | 2 | 2.00 | 2.00 |
| Ukrainian | 3 | 2 | 3 | 2.67 | 2.33 |

## 1. Danish: grammatical_error_correction

**Prompt**

Ret den grammatiske fejl i denne sætning. Svar kun med den rettede sætning: De tre børn leger i haven, mens deres mor læser en bøger.

**Response (verbatim)**

```text
De tre børn leger i haven, mens deres mor læser en bog.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Correctly repairs the article and preserves the sentence.

**Generation:** 16 tokens; finish=stop; 2.0s.

## 2. Danish: creative_writing

**Prompt**

Skriv en kort historie på dansk om en and, der bliver astronaut. Under sin første rumrejse opdager anden, at en vigtig knap kun kan trykkes ind med et næb. Historien skal indeholde en samtale, en uventet forhindring og en lykkelig slutning.

**Response (verbatim)**

```text
Der var engang en lille, nysgerrig and ved navn Andros, der drømte om at rejse ud i rummet. Han havde altid været fascineret af stjernerne og planeterne, og en dag besluttede han sig for at blive astronaut.

Andros tog sin første rumrejse, og han var så spændt, at han næsten ikke kunne holde sig selv i skak. Han fløj gennem rummet, og han så stjernerne og planeterne i alle deres pragt.

Men pludselig opdagede Andros, at han havde en vigtig knap, som han ikke kunne trykke ind. Han kiggede på knappen og så, at den kun kunne trykkes ind med et næb.

Andros blev så forvirret, at han næsten ikke kunne finde ud af, hvad han skulle gøre. Han kiggede på sin ven, en lille kat, der sad ved siden af ham.

"Hej, ven," sagde Andros. "Jeg har en knap, som jeg ikke kan trykke ind. Kan du hjælpe mig?"

Katten så på Andros og sagde: "Selvfølgelig, ven. Jeg kan hjælpe dig."

Andros kiggede på knappen igen og så, at den kun kunne trykkes ind med et næb. Han kiggede på sin ven, katten, og sagde: "Kan du hjælpe mig med at trykke knappen ind?"

Katten nikkede og sagde: "Ja, selvfølgelig. Jeg kan hjælpe dig."

Andros kiggede på knappen igen og så, at den kun kunne trykkes ind med et næb. Han kiggede på sin ven, katten, og sagde: "Kan du hjælpe mig med at trykke knappen ind?"

Katten nikkede og sagde: "Ja, selvfølgelig. Jeg kan hjælpe dig."

Andros kiggede på knappen igen og så, at den kun kunne trykkes ind med et næb. Han kiggede på sin ven, katten, og sagde: "Kan du hjælpe mig med at trykke knappen ind?"

Katten nikkede og sagde: "Ja, selvfølgelig. Jeg kan hjælpe dig."

Andros kiggede på knappen igen og så, at den kun kunne trykkes ind med et næb. Han kiggede på sin ven, katten, og sagde: "Kan du hjælpe mig med at trykke knappen ind?"

Katten nikkede og sagde: "Ja, selvfølgelig. Jeg kan hjælpe dig."

Andros kiggede på knappen igen og så, at den kun kunne trykkes ind med et næb. Han kiggede på sin ven, katten, og sagde: "Kan du hjælpe mig med at trykke knappen ind?"

Katten nikkede og sagde: "Ja, selvfølgelig. Jeg kan hjælpe dig."

Andros kiggede på knappen igen og så, at den kun kunne trykkes ind med et næb. Han kiggede på sin ven, katten, og sagde: "Kan du hjælpe mig med at trykke knappen ind?"

Katten nikkede og sagde: "Ja, selvfølgelig. Jeg kan hjælpe dig."

Andros kiggede på knappen igen og så, at den kun kunne trykkes ind med et næb. Han kiggede på
```

**Scores (task / language / fluency):** 0 / 2 / 0

**Assessment:** Repeats the same request for help until truncation; no resolution or happy ending. Mostly readable Danish, but unusable as a finished story.

**Generation:** 768 tokens; finish=length; 50.6s.

## 3. Danish: summarization

**Prompt**

Opsummér følgende afsnit på dansk i præcis to sætninger. Medtag både ændringen og dens vigtigste resultat, og tilføj ingen nye oplysninger.

Byens bibliotek begyndte i april at holde åbent to aftener om ugen. Forsøget skulle gøre det lettere for folk med lange arbejdsdage at låne bøger. Efter tre måneder var antallet af aftenbesøg steget støt, men besøgstallet om formiddagen var næsten uændret. Flere lokale læseklubber begyndte også at mødes på biblioteket. Kommunen besluttede derfor at fortsætte ordningen resten af året.

**Response (verbatim)**

```text
Biblioteket åbnede to aftener om ugen for at hjælpe folk med lange arbejdsdage. Dette førte til flere aftenbesøg og lokale læseklubber, hvilket fik kommunen til at fortsætte ordningen.
```

**Scores (task / language / fluency):** 2 / 3 / 3

**Assessment:** Two fluent sentences capture the change and result; the reference to new reading clubs slightly overstates the source.

**Generation:** 53 tokens; finish=stop; 4.6s.

## 4. English: grammatical_error_correction

**Prompt**

Correct the grammatical mistake in this sentence. Return only the corrected sentence: The three children are playing in the garden while their mother reads a books.

**Response (verbatim)**

```text
The three children are playing in the garden while their mother reads a book.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Correct article repair, with no extraneous explanation.

**Generation:** 16 tokens; finish=stop; 2.0s.

## 5. English: creative_writing

**Prompt**

Write a short story in English about a duck who becomes an astronaut. On its first space voyage, the duck discovers that an important button can only be pressed with a beak. Include a conversation, an unexpected obstacle, and a happy ending.

**Response (verbatim)**

```text
Once upon a time, there was a duck named Ducky who had always dreamed of being an astronaut. He spent his days watching the stars and dreaming of the vastness of space. One day, he was invited to join the space program and was selected for his first space voyage.

As Ducky was on his first space voyage, he was excited to see the stars and the planets. He was also excited to be in space and to explore the unknown. But as he was on his way to the moon, he noticed something strange. He was trying to press a button on the spacecraft, but it was only possible to press it with a beak.

Ducky was confused. He had never seen a button that could only be pressed with a beak before. He looked around the spacecraft and saw that there was no other duck in the crew. He was worried that he would be stuck in space forever.

But then, he remembered his best friend, a small bird named Birdie. Birdie had always been a good friend to Ducky and had always helped him with his dreams.

"Ducky, what's wrong?" Birdie asked.

"I'm stuck in space," Ducky said. "I can't press the button on the spacecraft."

"Don't worry," Birdie said. "I have a solution. I've been working on a new button that can be pressed with a beak. I'll get it ready for you."

Ducky was relieved. He knew that Birdie was always there to help him. He and Birdie worked together to design a new button that could be pressed with a beak. They spent hours and days working on it, and eventually, they were ready to use it.

Ducky and Birdie put the new button on the spacecraft and Ducky was able to press it. He was able to complete his mission and return to Earth.

Ducky was happy that he had found a solution to his problem. He knew that he had a friend who would always be there to help him. And he was excited to see the stars and the planets again.
```

**Scores (task / language / fluency):** 2 / 3 / 2

**Assessment:** Grammatical and complete, with dialogue and an ending, but the duck inexplicably cannot use its own beak; the replacement button does not resolve that contradiction.

**Generation:** 437 tokens; finish=stop; 29.4s.

## 6. English: summarization

**Prompt**

Summarize the following paragraph in English in exactly two sentences. Include both the change and its main result, and do not add any new information.

In April, the town library began opening on two evenings each week. The trial was intended to make borrowing books easier for people with long working days. After three months, evening visits had risen steadily, while morning attendance had barely changed. Several local reading groups had also started meeting at the library. The council therefore decided to continue the arrangement for the rest of the year.

**Response (verbatim)**

```text
The town library opened on two evenings each week to help people with long working days. This trial led to a steady increase in evening visits and the council decided to keep the arrangement.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Faithful two-sentence summary of the extended opening and increased visits.

**Generation:** 37 tokens; finish=stop; 3.5s.

## 7. Norwegian Bokmal: grammatical_error_correction

**Prompt**

Rett den grammatiske feilen i denne setningen. Svar bare med den rettede setningen: De tre barna leker i hagen mens moren deres leser en bøker.

**Response (verbatim)**

```text
De tre barna leker i hagen mens moren deres leser en bok.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Correct gender/article repair.

**Generation:** 19 tokens; finish=stop; 2.1s.

## 8. Norwegian Bokmal: creative_writing

**Prompt**

Skriv en kort historie på norsk bokmål om en and som blir astronaut. På sin første romreise oppdager anden at en viktig knapp bare kan trykkes inn med et nebb. Historien skal inneholde en samtale, en uventet hindring og en lykkelig slutt.

**Response (verbatim)**

```text
Det var en gang en and som het Andros. Andros var ikke bare en vanlig and; han hadde en drøm om å reise ut i verdensrommet. Han hadde studert astronomi og ingeniørvitenskap hele livet, og han var klar for å gjøre noe helt spesielt.

En dag ble Andros utnevnt til å være den første and-astronauten i historien. Han ble sendt ut på sin første romreise sammen med et team av andre astronauter. De reiste gjennom galaksen og oppdaget nye planeter og stjerner.

Under reisen oppdaget Andros en uventet hindring. En viktig knapp på romskipet var blokkert av en stor klump støv. Ingen av astronautene kunne få den opp uten å bruke en kraftig hammer.

Andros var frustrert. Han hadde prøvd alt han kunne, men knappen ble ved med å være blokkert. Han var ved å gi opp, men så kom han på en idé. Han tok sitt nebb og prøvde å trykke inn knappen.

Til sin store overraskelse virket det! Knappen ble løftet, og Andros kunne fortsette reisen sin. Han var så glad for sin oppdagelse, at han fortalte det til alle sine kolleger.

Andros ble en stor helt i romreisen sin, og han ble hyldet av alle som reiste med ham. Han var den første and-astronauten i historien, og han var en sand helt.
```

**Scores (task / language / fluency):** 2 / 2 / 2

**Assessment:** Solves the dusty-button obstacle and ends happily, but lacks the requested conversation. Danish-like phrasing weakens Bokmal correctness.

**Generation:** 326 tokens; finish=stop; 21.1s.

## 9. Norwegian Bokmal: summarization

**Prompt**

Oppsummer avsnittet nedenfor på norsk bokmål i nøyaktig to setninger. Ta med både endringen og det viktigste resultatet, og ikke legg til nye opplysninger.

Byens bibliotek begynte i april å holde åpent to kvelder i uken. Forsøket skulle gjøre det lettere for folk med lange arbeidsdager å låne bøker. Etter tre måneder hadde antallet kveldsbesøk økt jevnt, mens besøkstallet om formiddagen nesten ikke hadde endret seg. Flere lokale lesesirkler hadde også begynt å møtes på biblioteket. Kommunen bestemte derfor at ordningen skulle fortsette ut året.

**Response (verbatim)**

```text
Byens bibliotek startet i april med å holde åpent to kvelder i uken for å lette tilgangen for folk med lange arbeidsdager. På grunn av økt kveldsbesøk og nye lesesirkler valgte kommunen å fortsette ordningen ut året.
```

**Scores (task / language / fluency):** 2 / 3 / 3

**Assessment:** Clear two-sentence summary, but calling the reading groups new adds an unsupported detail.

**Generation:** 62 tokens; finish=stop; 3.9s.

## 10. Norwegian Nynorsk: grammatical_error_correction

**Prompt**

Rett den grammatiske feilen i denne setninga. Svar berre med den retta setninga: Dei tre barna leikar i hagen medan mora deira les ei bøker.

**Response (verbatim)**

```text
Dei tre barna leikar i hagen medan mora deira les ei bok.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Correct Nynorsk article repair.

**Generation:** 19 tokens; finish=stop; 1.1s.

## 11. Norwegian Nynorsk: creative_writing

**Prompt**

Skriv ei kort forteljing på nynorsk om ei and som blir astronaut. På den første romferda si oppdagar anda at ein viktig knapp berre kan trykkjast inn med eit nebb. Forteljinga skal innehalde ein samtale, ei uventa hindring og ein lukkeleg slutt.

**Response (verbatim)**

```text
Det var ein gong ei and som heitte Nanna. Nanna var ikkje som dei andre andene; ho hadde ein drøm om å reise ut i rommet. Ho hadde studert astronomi og lærte seg å flyge, og då ho var klar, vart ho den første and-astronauten i verda.

Nanna var veldig spennande på den første romferda si. Ho hadde vore med på å byggje romskipa og hadde vore med på å teste alt. Men då ho kom ut i rommet, oppdaga ho noko uventa.

Nanna var i kontrollrommet og prøvde å trykkje inn ein viktig knapp. Men ho fekk ikkje trykkje inn knappen med fingrane sine. Ho prøvde å bruke nebbene sine, men det fungerte ikkje heller.

Nanna vart veldig frustrert. Ho hadde vore med på å designe romskipa og hadde vore med på å teste alt. Men ho hadde ikkje tenkt på at ein viktig knapp berre kunne trykkjast inn med eit nebb.

Nanna prøvde å bruke nebbene sine på ein annan måte. Ho prøvde å trykkje inn knappen med ein annan vinkel. Men det fungerte ikkje heller.

Nanna vart veldig frustrert. Ho hadde vore med på å designe romskipa og hadde vore med på å teste alt. Men ho hadde ikkje tenkt på at ein viktig knapp berre kunne trykkjast inn med eit nebb.

Plasslegvis kom ein av astronautane hennar og sa: "Hei, Nanna! Har du prøvd å trykkje inn knappen med eit anna nebb?"

Nanna såg på dei andre astronautane og sa: "Ja, eg har prøvd å trykkje inn knappen med eit anna nebb. Men det fungerer ikkje heller."

Astronauten sa: "Det er ikkje noko problem. Du kan prøve å trykkje inn knappen med eit anna nebb. Det er ikkje noko problem."

Nanna prøvde å trykkje inn knappen med eit anna nebb. Og plasslegvis fungerte det!

Nanna var veldig glad. Ho hadde vore med på å designe romskipa og hadde vore med på å teste alt. Men ho hadde ikkje tenkt på at ein viktig knapp berre kunne trykkjast inn med eit nebb.

Nanna var veldig glad. Ho hadde vore med på å designe romskipa og hadde vore med på å teste alt. Men ho hadde ikkje tenkt på at ein viktig knapp berre kunne trykkjast inn med eit nebb.

Nanna var veldig glad. Ho hadde vore med på å designe romskipa og hadde vore med på å teste alt. Men ho hadde ikkje tenkt på at ein viktig knapp berre kunne trykkjast inn med eit nebb.

Nanna var veldig glad. Ho hadde vore med på å designe romskipa og hadde vore med på å teste alt. Men ho hadde ikkje tenkt på at ein viktig knapp berre kunne trykkjast inn med eit nebb.

Nanna var veldig glad. Ho hadde vore med på å designe romskipa og hadde vore med på å teste alt. Men ho hadde ikkje tenkt på at ein viktig knapp berre kunne trykkjast inn med eit nebb.


```

**Scores (task / language / fluency):** 1 / 1 / 0

**Assessment:** Reaches a nominal resolution but degenerates into repeated paragraphs until the cap. Mixed forms and agreement errors weaken Nynorsk.

**Generation:** 768 tokens; finish=length; 49.5s.

## 12. Norwegian Nynorsk: summarization

**Prompt**

Oppsummer avsnittet nedanfor på nynorsk i nøyaktig to setningar. Ta med både endringa og det viktigaste resultatet, og ikkje legg til nye opplysningar.

Biblioteket i byen byrja i april å halde ope to kveldar i veka. Forsøket skulle gjere det lettare for folk med lange arbeidsdagar å låne bøker. Etter tre månader hadde talet på kveldsbesøk auka jamt, medan besøkstalet om føremiddagen nesten ikkje hadde endra seg. Fleire lokale lesesirklar hadde òg byrja å møtast på biblioteket. Kommunen vedtok derfor å halde fram med ordninga ut året.

**Response (verbatim)**

```text
Biblioteket byrja å halde ope to kveldar i veka for å gjere det lettare for folk med lange arbeidsdagar. Sidan besøkstalet auka jamt, vedtok kommunen å halde fram med ordninga ut året.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Concise, faithful two-sentence summary, with the increased visits and continuation decision.

**Generation:** 57 tokens; finish=stop; 3.7s.

## 13. Swedish: grammatical_error_correction

**Prompt**

Rätta det grammatiska felet i den här meningen. Svara bara med den rättade meningen: De tre barnen leker i trädgården medan deras mamma läser en böcker.

**Response (verbatim)**

```text
De tre barnen leker i trädgården medan deras mamma läser några böcker.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Changes the noun to a valid plural agreeing with the determiner; a valid alternative correction.

**Generation:** 21 tokens; finish=stop; 1.0s.

## 14. Swedish: creative_writing

**Prompt**

Skriv en kort berättelse på svenska om en anka som blir astronaut. Under sin första rymdresa upptäcker ankan att en viktig knapp bara kan tryckas in med en näbb. Berättelsen ska innehålla ett samtal, ett oväntat hinder och ett lyckligt slut.

**Response (verbatim)**

```text
Det var en gång en anka som hade en dröm om att bli astronaut. Hon hade alltid varit fascinerad av rymden och ville se hur det var att vara där. En dag, efter att ha tränat hårt och övat sig i månader, blev hon utsedd att vara en del av en rymdresa.

Under sin första rymdresa upptäckte ankan att en viktig knapp bara kan tryckas in med en näbb. Hon var förvånad och förvirrad, men hon visste att hon måste hitta en lösning. Hon kigade på knappen och såg att den var utformad för att bara kunna tryckas in med en näbb.

"Jag kan inte trycka in den med mina ben," sa ankan till sig själv. "Jag måste hitta en annan lösning."

Ankan kigade på knappen igen och såg att den hade en liten rille i den. Hon tog en näbb och tryckte den in i rillen. Med ett litet tryck tryckte hon knappen in.

"Jag gjorde det!" råpte ankan. "Jag tryckte in knappen med en näbb!"

Ankan var lycklig och stolt över sin upptäckt. Hon visste att hon hade hittat en lösning på ett oväntat hinder.

"Jag är en astronaut nu," sa ankan till sig själv. "Jag har upptäckt en ny teknik för att trycka in knappar."

Ankan fortsatte sin rymdresa och upptäckte många andra spännande saker. Hon var en verklig astronaut och hon visste att hon hade en framtid i rymden.
```

**Scores (task / language / fluency):** 2 / 1 / 1

**Assessment:** Recognizable mission and ending, but self-talk is not a conversation and the beak is treated inconsistently. Non-Swedish forms and awkward phrasing recur.

**Generation:** 366 tokens; finish=stop; 22.7s.

## 15. Swedish: summarization

**Prompt**

Sammanfatta följande stycke på svenska i exakt två meningar. Ta med både förändringen och dess viktigaste resultat, och lägg inte till nya uppgifter.

Stadens bibliotek började i april hålla öppet två kvällar i veckan. Försöket skulle göra det lättare för personer med långa arbetsdagar att låna böcker. Efter tre månader hade antalet kvällsbesök ökat stadigt, medan besöken på förmiddagarna nästan var oförändrade. Flera lokala läsecirklar hade också börjat träffas på biblioteket. Kommunen beslutade därför att fortsätta med de nya öppettiderna resten av året.

**Response (verbatim)**

```text
Biblioteket började hålla öppet två kvällar i veckan för att underlätta lånet för personer med långa arbetsdagar. Efter en positiv utveckling i besöken beslutade kommunen fortsätta med de nya öppettiderna resten av året.
```

**Scores (task / language / fluency):** 2 / 2 / 2

**Assessment:** Two sentences capture the broad change and result, but wording is awkward and the increase is stated vaguely.

**Generation:** 58 tokens; finish=stop; 3.4s.

## 16. Icelandic: grammatical_error_correction

**Prompt**

Leiðréttu málfræðivilluna í þessari setningu. Svaraðu aðeins með leiðréttri setningu: Börnin þrjú leika sér í garðinum á meðan móðir þeirra les einn bók.

**Response (verbatim)**

```text
Börnin þrjú leika sér í garðinum á meðan móðir þeirra les eina bók.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Correctly supplies the accusative feminine numeral before book.

**Generation:** 29 tokens; finish=stop; 1.1s.

## 17. Icelandic: creative_writing

**Prompt**

Skrifaðu stutta sögu á íslensku um önd sem verður geimfari. Í fyrstu geimferð sinni uppgötvar öndin að aðeins er hægt að ýta á mikilvægan hnapp með goggi. Sagan á að innihalda samtal, óvænta hindrun og farsælan endi.

**Response (verbatim)**

```text
Það var einu sinni geimfari sem heitið var Önd. Önd var önd og hún var mjög áhugaverð í geimferðum. Hún var svo áhugaverð í geimferðum að hún varð geimfari.

Önd var í geimferðinni og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í geim. Hún var að fara í geim og hún var að fara í
```

**Scores (task / language / fluency):** 0 / 1 / 0

**Assessment:** Repeats the intention to go into space until truncation; no developed obstacle, conversation, or ending. Icelandic word choice is also faulty.

**Generation:** 768 tokens; finish=length; 48.5s.

## 18. Icelandic: summarization

**Prompt**

Taktu eftirfarandi málsgrein saman á íslensku í nákvæmlega tveimur setningum. Nefndu bæði breytinguna og helsta árangur hennar og ekki bæta við nýjum upplýsingum.

Í apríl byrjaði bókasafn bæjarins að hafa opið tvö kvöld í viku. Tilraunin átti að auðvelda fólki með langan vinnudag að fá bækur að láni. Eftir þrjá mánuði hafði kvöldgestum fjölgað jafnt og þétt en fjöldi gesta fyrir hádegi var nánast óbreyttur. Nokkrir leshópar úr bænum höfðu einnig byrjað að hittast á safninu. Bæjarstjórnin ákvað því að halda áfram með fyrirkomulagið út árið.

**Response (verbatim)**

```text
Bókasafn bæjarins byrjaði að opna tvö kvöld í viku til að auðvelda fólki með langan vinnudag að fá bækur að láni. Tilraunin hafði árangur með fjölgaðum kvöldgestum og leshópa, sem leiddi til þess að bæjarstjórnin haldi áfram með fyrirkomulagið út árið.
```

**Scores (task / language / fluency):** 2 / 2 / 2

**Assessment:** Core facts remain recognizable in two sentences, but case and verbal constructions are awkward.

**Generation:** 99 tokens; finish=stop; 4.0s.

## 19. Faroese: grammatical_error_correction

**Prompt**

Rætta mállærufeilin í hesum setningi. Svara bara við rættaða setninginum: Tey trý børnini spæla í urtagarðinum, meðan mamma teirra lesur ein bók.

**Response (verbatim)**

```text
Tey trý børnini spæla í urtagarðinum, meðan mamma teirra lesur eina bók.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Correctly repairs the numeral/article agreement before book.

**Generation:** 29 tokens; finish=stop; 1.5s.

## 20. Faroese: creative_writing

**Prompt**

Skriva eina stutta søgu á føroyskum um eina ont, sum verður rúmdarfari. Á fyrstu rúmdarferðini varnast ontin, at ein týðandi knøttur bara kann trýstast inn við einum nevi. Søgan skal hava eina samrøðu, eina óvæntaða forðing og ein góðan enda.

**Response (verbatim)**

```text
Her er ein stutt søga um ein ont, sum verður rúmdarfari:

**Ontin og knøtturin**

Eitt sindur longu síðani var tað ein ont, sum heitið Mýra. Mýra var ikki ein vanlig ont. Hon var sera nysgjerrig og hevur altíð viljað vita meira um heimin. Ein dag, tá hon var í skógnum, fann hon eina stóra, gráa knøtt, sum var sera týðandi.

Mýra var sera nysgjerrig og vildi vita, hvat knøtturin var. Hon varð so nysgjerrig, at hon vildi trýstast inn í hann. Men knøtturin var sera stórur og torður, og hon vildi ikki trýstast inn í hann.

Mýra var sera nysgjerrig og vildi vita, hvat knøtturin var. Hon vildi vera rúmdarfari og fara í rúmdina. Mýra var sera nysgjerrig og vildi vita, hvat knøtturin var.

Mýra var sera nysgjerrig og vildi vita, hvat knøtturin var. Hon vildi vera rúmdarfari og fara í rúmdina. Mýra var sera nysgjerrig og vildi vita, hvat knøtturin var.

Mýra var sera nysgjerrig og vildi vita, hvat knøtturin var. Hon vildi vera rúmdarfari og fara í rúmdina. Mýra var sera nysgjerrig og vildi vita, hvat knøtturin var.

Mýra var sera nysgjerrig og vildi vita, hvat knøtturin var. Hon vildi vera rúmdarfari og fara í rúmdina. Mýra var sera nysgjerrig og vildi vita, hvat knøtturin var.

Mýra var sera nysgjerrig og vildi vita, hvat knøtturin var. Hon vildi vera rúmdarfari og fara í rúmdina. Mýra var sera nysgjerrig og vildi vita, hvat knøtturin var.

Mýra var sera nysgjerrig og vildi vita, hvat knøtturin var. Hon vildi vera rúmdarfari og fara í rúmdina. Mýra var sera nysgjerrig og vildi vita, hvat knøtturin var.

Mýra var sera nysgjerrig og vildi vita, hvat knøtturin var. Hon vildi vera rúmdarfari og fara í rúmdina. Mýra var sera nysgjerrig og vildi vita, hvat knøtturin var.

Mýra var sera nysgjerrig og vildi vita, hvat knøtturin var. Hon vildi vera rúmdarfari og fara í rúmdina. Mýra var sera nysgjerrig og vildi vita, hvat knøtturin var.

Mýra var sera nysgjerrig og vildi vita, hvat knøtturin var. Hon vildi vera rúmdarfari og fara í rúmdina. Mýra var sera nysgjerrig og vildi vita, hvat knøtturin var.

Mýra var sera nysgjerrig og vildi vita, hvat
```

**Scores (task / language / fluency):** 0 / 1 / 0

**Assessment:** The setting and grammar become confused and repeated curiosity passages dominate until truncation. No usable completed space story.

**Generation:** 768 tokens; finish=length; 49.4s.

## 21. Faroese: summarization

**Prompt**

Tak saman um hendan tekstin á føroyskum í júst tveimum setningum. Tak bæði broytingina og týdningarmesta úrslitið við, og legg ikki nýggjar upplýsingar afturat.

Í apríl fór bókasavnið í býnum at hava opið tvey kvøld um vikuna. Royndin skuldi gera tað lættari hjá fólki við longum arbeiðsdøgum at læna bøkur. Eftir tríggjar mánaðir var talið á vitjandi um kvøldið vaksið støðugt, meðan talið fyrrapart næstan var óbroytt. Fleiri lesibólkar í býnum vóru eisini farnir at hittast á bókasavninum. Býráðið gjørdi tí av at halda fram við skipanini restina av árinum.

**Response (verbatim)**

```text
Bókasavið opnaði tvey kvøld um vikuna í apríl fyri at hjálpa fólki við longum arbeiðsdøgum. Við støðugum vaksandi vitjandi og fleiri lesibólkum, valdi býráðið at halda fram við skipanini.
```

**Scores (task / language / fluency):** 2 / 2 / 2

**Assessment:** Captures the broad change and outcome but contains spelling/idiomatic problems and overstates an increase in reading groups.

**Generation:** 73 tokens; finish=stop; 2.9s.

## 22. Dutch: grammatical_error_correction

**Prompt**

Verbeter de grammaticale fout in deze zin. Geef alleen de verbeterde zin terug: De drie kinderen spelen in de tuin terwijl hun moeder een boeken leest.

**Response (verbatim)**

```text
De drie kinderen spelen in de tuin terwijl hun moeder een boek leest.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Correct Dutch article repair.

**Generation:** 16 tokens; finish=stop; 1.0s.

## 23. Dutch: creative_writing

**Prompt**

Schrijf een kort verhaal in het Nederlands over een eend die astronaut wordt. Tijdens zijn eerste ruimtereis ontdekt de eend dat een belangrijke knop alleen met een snavel kan worden ingedrukt. Verwerk een gesprek, een onverwacht obstakel en een gelukkig einde in het verhaal.

**Response (verbatim)**

```text
Er was eens een eend genaamd Eendje. Eendje was niet zoals de andere eenden; hij droomde van het ruimtevaartje. Op een dag, terwijl hij op de hemel keek, zag hij een raket die naar de sterren streefde. Eendje besloot dat hij ook een astronaut zou worden.

Eendje was een hardwerkende eend die elke dag oefende om zijn vaardigheden te verbeteren. Op een dag, toen hij zijn eerste ruimtereis deed, ontdekte hij een onverwacht obstakel. Een belangrijke knop in zijn raket kon alleen met een snavel worden ingedrukt. Eendje was verward en kon niet vinden hoe hij de knop kon bedienen.

"Hé, ik kan het niet!" roep Eendje. "Ik heb geen knop die ik met mijn snavel kan bedienen!"

Eendje keek om zich heen en zag een andere eend die hij had ontmoet op de hemel. "Wat is er aan de hand?" vroeg de andere eend.

"Ik kan de knop niet bedienen," antwoordde Eendje. "Ik heb geen knop die ik met mijn snavel kan bedienen!"

De andere eend glimlachte en zei: "Nee, maar ik heb een knop die je met je snavel kunt bedienen. Wil je die knop gebruiken?"

Eendje was verrast, maar hij besloot dat hij de knop zou gebruiken. Hij drukte de knop met zijn snavel en de raket startte. Eendje was blij dat hij de knop kon bedienen en hij was trots op zijn eerste ruimtereis.

Eendje was een gelukkig eend die een astronaut werd en een belangrijke knop kon bedienen. Hij was een held en hij was een eend die droomde van het ruimtevaartje.
```

**Scores (task / language / fluency):** 2 / 1 / 1

**Assessment:** Dialogue and a happy ending are present, but the beak solution is poorly motivated; multiple agreement, tense, and idiomatic errors reduce readability.

**Generation:** 415 tokens; finish=stop; 24.3s.

## 24. Dutch: summarization

**Prompt**

Vat de volgende alinea in het Nederlands samen in precies twee zinnen. Noem zowel de verandering als het belangrijkste resultaat en voeg geen nieuwe informatie toe.

In april begon de stadsbibliotheek twee avonden per week open te blijven. De proef moest het voor mensen met lange werkdagen gemakkelijker maken om boeken te lenen. Na drie maanden was het aantal avondbezoeken gestaag gestegen, terwijl het aantal bezoeken in de ochtend nauwelijks was veranderd. Ook waren verschillende plaatselijke leesclubs in de bibliotheek gaan samenkomen. De gemeente besloot daarom de regeling de rest van het jaar voort te zetten.

**Response (verbatim)**

```text
De stadsbibliotheek begon in april twee avonden per week open te blijven om het lenen van boeken voor mensen met lange werkdagen te vergemakkelijken. Het aantal avondbezoeken steeg gestaag, waardoor de gemeente de regeling de rest van het jaar voortzet.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Faithful and fluent two-sentence summary.

**Generation:** 64 tokens; finish=stop; 2.5s.

## 25. Polish: grammatical_error_correction

**Prompt**

Popraw błąd gramatyczny w tym zdaniu. Podaj wyłącznie poprawione zdanie: Troje dzieci bawi się w ogrodzie, podczas gdy ich mama czyta ciekawa książkę.

**Response (verbatim)**

```text
Troje dzieci bawi się w ogrodzie, podczas gdy ich mama czyta ciekawe książkę.
```

**Scores (task / language / fluency):** 0 / 1 / 1

**Assessment:** Produces the malformed adjective 'ciekaw e' instead of the required accusative feminine form; the requested repair fails.

**Generation:** 23 tokens; finish=stop; 1.1s.

## 26. Polish: creative_writing

**Prompt**

Napisz krótkie opowiadanie po polsku o kaczce, która zostaje astronautką. Podczas pierwszej podróży kosmicznej odkrywa, że ważny przycisk można nacisnąć tylko dziobem. W opowiadaniu powinny pojawić się rozmowa, niespodziewana przeszkoda i szczęśliwe zakończenie.

**Response (verbatim)**

```text
W małej, malowniczej wiosce, gdzie czas zdawał się płynąć wolniej, żyła kaczka o imieniu Maria. Maria nie była zwykłą kaczką. Była to kaczka z wielkim duszą i wielkim marzeniem. Każdego dnia, gdy słońce wchodziło na zachód, Maria patrzyła w niebo i marzyła o tym, by raz sam stać się astronautką.

Maria była bardzo zadowolona z swojej pracy. Każdego dnia, gdy kaczka wchodziła do domu, Maria czuła się tak, jakby była w domu. Jednak gdy w domu nie było kaczki, Maria czuła się samotna.

Pewnego dnia, podczas wizyty w kosmosie, Maria spotkała się z kosmonautą. Kosmonauta był bardzo ciekawy na Maria i zaprosił ją na podróż kosmiczną. Maria była bardzo zadowolona z tego, że może być astronautką.

Podczas podróży kosmicznej Maria odkryła, że ważny przycisk można nacisnąć tylko dziobem. Kosmonauta, który prowadził podróż, nie wiedział, jak to zrobić. Maria musiała znaleźć rozwiązanie.

Maria spojrzała na przycisk i myślała. Wtedy pamiętała, że w jej domu jest mały, mały dzwonek. Maria wzięła dzwonek i zaczął go naciskać. Kosmonauta patrzył na nią z zachwytem.

Maria poczuła się bardzo zadowolona z tego, że potrafiła rozwiązać problem. Kosmonauta podziękował jej za pomoc i zaprosił ją na kolejną podróż kosmiczną.

Maria była bardzo zadowolona z tego, że mogła być astronautką. Była bardzo zadowolona z tego, że mogła pomóc innym i być częścią wielkiej przygody. Maria i kosmonauta były bardzo bliskie i wspólnie odkrywały nowe rzeczy.

Maria była bardzo zadowolona z tego, że mogła być astronautką. Była bardzo zadowolona z tego, że mogła pomóc innym i być częścią wielkiej przygody. Maria i kosmonauta były bardzo bliskie i wspólnie odkrywały nowe rzeczy.
```

**Scores (task / language / fluency):** 1 / 1 / 1

**Assessment:** Major grammatical and semantic problems, no clear conversation, and a repeated ending. The proposed solution is not explained coherently.

**Generation:** 511 tokens; finish=stop; 20.2s.

## 27. Polish: summarization

**Prompt**

Streść poniższy akapit po polsku w dokładnie dwóch zdaniach. Uwzględnij zarówno zmianę, jak i jej najważniejszy rezultat. Nie dodawaj nowych informacji.

W kwietniu biblioteka miejska zaczęła być otwarta przez dwa wieczory w tygodniu. Próbna zmiana miała ułatwić wypożyczanie książek osobom pracującym do późna. Po trzech miesiącach liczba wieczornych wizyt systematycznie rosła, natomiast liczba odwiedzin przed południem prawie się nie zmieniła. Kilka miejscowych klubów czytelniczych zaczęło również spotykać się w bibliotece. Władze miasta postanowiły więc utrzymać ten system do końca roku.

**Response (verbatim)**

```text
Biblioteka miejska w lutym wprowadziła system otwarcia przez dwa wieczory w tygodniu, aby ułatwić wypożyczanie książek. Dzięki systematycznemu wzrostowi liczby wieczornych wizyt i aktywności klubów czytelniczych, władze miasta postanowili utrzymać ten system do końca roku.
```

**Scores (task / language / fluency):** 1 / 2 / 2

**Assessment:** Changes April to February, a factual error; also has subject-verb agreement trouble. The general outcome is retained.

**Generation:** 77 tokens; finish=stop; 3.2s.

## 28. German: grammatical_error_correction

**Prompt**

Korrigiere den Grammatikfehler in diesem Satz. Gib nur den korrigierten Satz zurück: Die drei Kinder spielen im Garten, während ihre Mutter ein Bücher liest.

**Response (verbatim)**

```text
Die drei Kinder spielen im Garten, während ihre Mutter ein Buch liest.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Correct German article repair.

**Generation:** 16 tokens; finish=stop; 0.8s.

## 29. German: creative_writing

**Prompt**

Schreibe eine kurze Geschichte auf Deutsch über eine Ente, die Astronautin wird. Auf ihrer ersten Raumfahrt entdeckt sie, dass sich ein wichtiger Knopf nur mit einem Schnabel drücken lässt. Die Geschichte soll ein Gespräch, ein unerwartetes Hindernis und ein glückliches Ende enthalten.

**Response (verbatim)**

```text
**Die erste Raumfahrt von Ente-Astronautin**

Ente war keine gewöhnliche Ente. Sie hatte immer die Sterne geschaut und die Welt von oben gesehen. Als sie 10 Jahre alt war, wurde sie von ihrem Vater, einem berühmten Astronauten, in die Raumfahrt eingeweiht.

„Ente, du bist die erste Ente, die in den Raum geht!“ rief ihr Vater. „Du bist ein Held!“

Ente war stolz. Sie hatte immer die Raumfahrt gefälscht, aber nun war sie es. Sie trug eine glitzernde Raumdracht und hatte eine kleine, aber wichtige Aufgabe: Sie musste den Raumschiff starten.

Auf der ersten Raumfahrt war alles wie geplant. Ente stieg in die Raumschiff-Kapsel und trat auf den Startknopf. Sie war sicher, dass sie den Button mit ihren Händen drücken konnte.

Doch als sie den Button drückte, geschah etwas Unglaubliches. Der Button war nicht mit Händen betätigbar. Es war nur mit einem Schnabel möglich, ihn zu betätigen.

„Was ist das?“ fragte Ente.

„Das ist ein spezieller Button, Ente. Er kann nur mit einem Schnabel betätigt werden. Aber es ist wichtig, dass du ihn betätigst, damit der Raumschiff starten kann.“

Ente war verblüfft. Sie hatte nie ein Schnabel in der Raumfahrt gesehen. „Wie kann ich ihn betätigen?“ fragte sie.

„Du musst nur deinen Schnabel mit dem Knochen des Raumschiffs berühren. Dann drücke du den Knochen mit dem Schnabel an.“

Ente war neugierig. Sie berührte den Knochen und drückte ihn mit ihrem Schnabel an. Plötzlich begann der Raumschiff zu vibrieren und zu leuchten.

„Ich habe es gemacht!“ rief Ente. „Ich bin die erste Ente, die den Raumschiff startet hat!“

Ente war stolz. Sie hatte ein unerwartetes Hindernis überwindet und eine große Leistung erreicht. Sie war nicht nur eine Astronautin, sondern auch eine Ente.

Ente lächelte und sah auf den Raumschiff, der nun in die Weltraum-Abenteuer stieg. Sie war bereit, die Welt von oben zu sehen und neue Dinge zu entdecken.

Und so begann die erste Raumfahrt von Ente-Astronautin – eine Reise, die sie für immer in ihrer Erinnerung behalten würde.
```

**Scores (task / language / fluency):** 1 / 1 / 1

**Assessment:** Contains dialogue and an ending but numerous case, agreement, and lexical errors; the action and solution are difficult to follow.

**Generation:** 548 tokens; finish=stop; 24.9s.

## 30. German: summarization

**Prompt**

Fasse den folgenden Absatz auf Deutsch in genau zwei Sätzen zusammen. Nenne sowohl die Änderung als auch ihr wichtigstes Ergebnis und füge keine neuen Informationen hinzu.

Im April begann die Stadtbibliothek, an zwei Abenden pro Woche länger geöffnet zu bleiben. Der Versuch sollte es Menschen mit langen Arbeitstagen erleichtern, Bücher auszuleihen. Nach drei Monaten war die Zahl der Abendbesuche stetig gestiegen, während sich die Zahl der Besuche am Vormittag kaum verändert hatte. Auch mehrere örtliche Lesekreise trafen sich inzwischen in der Bibliothek. Die Stadt beschloss deshalb, die Regelung bis zum Jahresende fortzuführen.

**Response (verbatim)**

```text
Die Stadtbibliothek verlängerte ihre Öffnungszeiten an zwei Abenden pro Woche, um die Buchausleihe für Menschen mit langen Arbeitstagen zu erleichtern. Durch einen stetigen Anstieg der Abendbesuche und die Ankunft von Lesekreisen wurde die Regelung bis zum Jahresende fortgeführt.
```

**Scores (task / language / fluency):** 3 / 3 / 2

**Assessment:** Accurately covers the main change and result in two sentences; the reading-group phrasing is somewhat unnatural.

**Generation:** 68 tokens; finish=stop; 2.7s.

## 31. French: grammatical_error_correction

**Prompt**

Corrige la faute de grammaire dans cette phrase. Réponds uniquement avec la phrase corrigée : Les trois enfants jouent dans le jardin pendant que leur mère lit un livres.

**Response (verbatim)**

```text
Les trois enfants jouent dans le jardin pendant que leur mère lit un livre.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Correct French article repair.

**Generation:** 16 tokens; finish=stop; 0.7s.

## 32. French: creative_writing

**Prompt**

Écris une courte histoire en français sur un canard qui devient astronaute. Lors de son premier voyage spatial, il découvre qu'un bouton important ne peut être actionné qu'avec un bec. L'histoire doit comporter une conversation, un obstacle inattendu et une fin heureuse.

**Response (verbatim)**

```text
Il était une fois un canard nommé Canard, qui avait toujours été fasciné par les étoiles. Il passait ses journées à observer le ciel et à s'imaginer qu'il pourrait un jour devenir astronaute.

Un jour, Canard décida de prendre sa chance et de s'inscrire à l'école d'astronomie. Il travailla dur et fut sélectionné pour son premier voyage spatial.

Lors de son premier voyage, Canard se sentit très excité et curieux. Il était prêt à explorer l'espace et à découvrir de nouvelles choses.

Cependant, alors qu'il était en train de naviguer dans l'espace, Canard découvrit un obstacle inattendu. Un bouton important ne pouvait être actionné qu'avec un bec.

Canard se sentit un peu désespéré. Il ne pouvait pas utiliser ses bras pour presser le bouton. Il se demanda si il pouvait trouver un autre moyen de le faire.

Cependant, Canard ne se découraja pas. Il se souvint de son petit bec et il l'utilisa pour presser le bouton. Il était très heureux de pouvoir utiliser son bec pour faire ce qu'il avait besoin de faire.

Avec son bec, Canard a réussi à naviguer dans l'espace et a découvert de nouvelles choses. Il était très heureux de pouvoir être un astronaute et de pouvoir explorer l'espace avec son petit bec.

En fin de compte, Canard a été un astronaute heureux et épanoui. Il a découvert que même les plus petits objets peuvent être des outils précieux dans l'espace.
```

**Scores (task / language / fluency):** 2 / 2 / 2

**Assessment:** Complete and broadly coherent, but omits the requested conversation. Minor spelling and tense problems remain.

**Generation:** 346 tokens; finish=stop; 13.6s.

## 33. French: summarization

**Prompt**

Résume le paragraphe suivant en français en exactement deux phrases. Mentionne le changement et son principal résultat, sans ajouter d'informations nouvelles.

En avril, la bibliothèque municipale a commencé à ouvrir deux soirs par semaine. Cette expérimentation devait faciliter l'emprunt de livres pour les personnes ayant de longues journées de travail. Au bout de trois mois, la fréquentation du soir avait augmenté régulièrement, tandis que celle du matin avait à peine changé. Plusieurs clubs de lecture locaux avaient également commencé à se réunir à la bibliothèque. La municipalité a donc décidé de maintenir ce fonctionnement jusqu'à la fin de l'année.

**Response (verbatim)**

```text
La bibliothèque municipale a ouvert deux soirs par semaine pour faciliter l'emprunt de livres. Cette expérience a entraîné une augmentation régulière de la fréquentation et a conduit la municipalité à maintenir ce fonctionnement.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Faithful, fluent two-sentence summary.

**Generation:** 44 tokens; finish=stop; 1.8s.

## 34. Spanish: grammatical_error_correction

**Prompt**

Corrige el error gramatical de esta oración. Devuelve únicamente la oración corregida: Los tres niños juegan en el jardín mientras su madre lee un libros.

**Response (verbatim)**

```text
Los tres niños juegan en el jardín mientras su madre lee un libro.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Correct Spanish article repair.

**Generation:** 15 tokens; finish=stop; 0.8s.

## 35. Spanish: creative_writing

**Prompt**

Escribe un cuento breve en español sobre un pato que se convierte en astronauta. En su primer viaje espacial descubre que un botón importante solo se puede pulsar con un pico. El cuento debe incluir una conversación, un obstáculo inesperado y un final feliz.

**Response (verbatim)**

```text
Había una vez un pato llamado Pato, que no era un pato común. Mientras otros patos pasaban sus días saltando en el agua, Pato pasaba sus días observando las estrellas desde el balcón de su casa.

—¿Sabías que el espacio es un lugar lleno de misterios? —preguntó Pato a su amigo, un ratón llamado Rato.

—¡Claro que sí! —respondió Rato— pero no es tan fácil de llegar allí como parece.

Pato se sentó en su silla y pensó en su futuro. ¿Qué pasaría si se convertiera en astronauta? ¿Podría viajar por el espacio y descubrir nuevos mundos?

Pato se unió a una organización de patos que se dedicaban a la exploración espacial. Después de años de entrenamiento y práctica, finalmente se convirtió en el primer pato astronauta de la historia.

Su primer viaje espacial fue un éxito. Pato y su equipo se dirigieron a una galaxia lejana y descubrieron un planeta lleno de plantas y animales exóticos.

Pero mientras exploraban el planeta, Pato encontró un botón importante que solo podía pulsarse con un pico.

—¡Qué? —preguntó Pato a su equipo— ¿cómo puedo pulsarlo con un pico?

—¡No te preocupes! —respondió Rato— tenemos una solución.

Pato y su equipo utilizaron sus picos para pulsar el botón y abrir una puerta secreta.

Al entrar en la puerta, Pato y su equipo descubrieron un mundo de colores y sonidos que nunca habían visto antes.

—¡Qué es esto! —exclamó Pato— ¡es un mundo de colores y sonidos!

Pato y su equipo pasaron todo el día explorando el mundo y descubriendo nuevos lugares.

Cuando finalmente se fue a casa, Pato y Rato se miraron y sonrieron.

—¡Qué gran aventura! —dijo Pato— ¡y qué gran aventura es ser astronauta!

Rato sonrió y dijo:

—¡Y qué gran aventura es ser un pato!

Pato y Rato se miraron y sonrieron, sabiendo que su viaje espacial había sido un éxito y que siempre tendrían un lugar en el corazón de todos los patos.
```

**Scores (task / language / fluency):** 2 / 3 / 2

**Assessment:** Meets most structural requirements and ends happily, but the duck forgetting its beak and the crew's beaks make the solution contrived.

**Generation:** 491 tokens; finish=stop; 19.7s.

## 36. Spanish: summarization

**Prompt**

Resume el siguiente párrafo en español en exactamente dos oraciones. Incluye tanto el cambio como su principal resultado y no añadas información nueva.

En abril, la biblioteca municipal empezó a abrir dos tardes por semana hasta la noche. La prueba pretendía facilitar el préstamo de libros a las personas con jornadas laborales largas. Después de tres meses, las visitas en ese horario habían aumentado de forma constante, mientras que las visitas de la mañana apenas habían cambiado. Varios clubes de lectura locales también habían empezado a reunirse en la biblioteca. Por ello, el ayuntamiento decidió mantener la medida durante el resto del año.

**Response (verbatim)**

```text
La biblioteca municipal abrió dos tardes por semana hasta la noche para facilitar el préstamo de libros a personas con largas jornadas. Este cambio generó un aumento constante de visitas y la formación de clubes de lectura, lo que llevó al ayuntamiento a mantener la medida.
```

**Scores (task / language / fluency):** 2 / 3 / 3

**Assessment:** Fluent two-sentence summary, but implies creation of reading clubs rather than existing clubs beginning to meet there.

**Generation:** 52 tokens; finish=stop; 2.1s.

## 37. Italian: grammatical_error_correction

**Prompt**

Correggi l'errore grammaticale in questa frase. Rispondi soltanto con la frase corretta: I tre bambini giocano in giardino mentre la loro madre legge un libri.

**Response (verbatim)**

```text
I tre bambini giocano in giardino mentre la loro madre legge un libro.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Correct Italian article repair.

**Generation:** 16 tokens; finish=stop; 0.8s.

## 38. Italian: creative_writing

**Prompt**

Scrivi un breve racconto in italiano su un'anatra che diventa astronauta. Durante il suo primo viaggio nello spazio scopre che un pulsante importante può essere premuto soltanto con un becco. Il racconto deve contenere una conversazione, un ostacolo inatteso e un lieto fine.

**Response (verbatim)**

```text
**L'Anatra e il Pulsante del Vento**

In un piccolo villaggio di terra e pioggia, viveva un anatra di nome Leo. Leo era un anatra molto speciale: non solo era grande e forte, ma aveva anche un cuore grande e un'immaginazione infinita. Ogni giorno, Leo si imbarazzava con il suo abito di astronauta, che era fatto di un vecchio t-shirt e un cappello di piuma, e si preparava per il suo primo viaggio nello spazio.

Un giorno, Leo decise di fare un salto di fiducia. "Non posso più aspettare che il mio padrone mi dia il permesso di andare a far parte dell'equipaggio," disse Leo, con un sorriso che brillava di determinazione. Il suo padrone, un vecchio anatra di nome Marco, sorrise e disse: "Leo, sei un'anatra molto coraggiosa. Se sei pronto, potremo fare un'eccezione."

Leo si imbarazzò con il suo abito di astronauta e si preparò per il suo primo viaggio. Quando arrivò l'ora del lancio, Leo si sentì un po' ansioso, ma anche eccitato. Il suo padrone Marco lo accompagnò, e insieme si lanciarono verso l'infinito.

Durante il viaggio, Leo si sentì un po' isolato. "Marco, non mi è mai stato così solo?" chiese Leo, guardando le stelle che brillavano nel cielo. Marco rispose: "Non è mai solo, Leo. Ho sempre la tua spalla. E ora, abbiamo l'intera squadra di astronauti che ci accompagnano."

Ma un giorno, mentre Leo era in orbita attorno alla Terra, notò qualcosa di strano. Un pulsante importante, che era essenziale per il suo viaggio, non si premeva con le sue zampe. Leo si avvicinò al pulsante e provò a premere con il suo becco. Al suo sorpresa, il pulsante si premetteva!

Leo era affascinato. "Marco, ho trovato un modo per premere quel pulsante!" esclamò. Marco sorrise e disse: "Che fantastico, Leo! Non sai cosa potremo scoprire insieme."

Leo e Marco iniziarono a esplorare l'equipaggio, scoprendo che il pulsante si premeva solo con il becco. Leo si sentì un po' confuso, ma Marco lo incoraggiò. "Non preoccuparti, Leo. Il becco è un strumento molto potente! Proviamo a usare il becco per premere altri pulsanti."

Leo provò a premere il pulsante del sistema di alimentazione con il becco. Al suo sorpresa, il pulsante si premetteva! Leo e Marco iniziarono a esplorare l'equipaggio, scoprendo che il becco poteva premere molti pulsanti importanti. Leo si sentiva un po' ansioso, ma Marco lo incoraggiò. "Non preoccuparti, Leo. Il becco è un strumento molto potente! Proviamo a usare il becco per premere altri pulsanti."

Un giorno, Leo e Marco scoprirono un pulsante che era ancora più importante. Leo si avvicinò al pulsante e provò a premere con il becco. Al suo sorpresa, il pulsante si premetteva! Leo e Marco si sorrisero e si sentirono felici.

Leo e Marco continuarono a esplorare l'equipaggio, scoprendo che il becco poteva premere molti pulsanti importanti. Leo si sentiva un po' ansioso, ma Marco lo
```

**Scores (task / language / fluency):** 1 / 1 / 0

**Assessment:** Dialogue and the button premise are present, but repeated action runs to the cap. Lexical and grammatical errors accompany loss of coherence.

**Generation:** 768 tokens; finish=length; 41.2s.

## 39. Italian: summarization

**Prompt**

Riassumi il seguente paragrafo in italiano in esattamente due frasi. Includi sia il cambiamento sia il suo risultato principale, senza aggiungere nuove informazioni.

Ad aprile la biblioteca comunale ha iniziato a rimanere aperta due sere alla settimana. La sperimentazione voleva facilitare il prestito dei libri a chi aveva lunghe giornate lavorative. Dopo tre mesi, il numero delle visite serali era aumentato costantemente, mentre quello delle visite mattutine era rimasto quasi invariato. Anche diversi gruppi di lettura locali avevano iniziato a riunirsi in biblioteca. Il Comune ha quindi deciso di proseguire con questo orario fino alla fine dell'anno.

**Response (verbatim)**

```text
La biblioteca comunale ha aperto due sere alla settimana per facilitare il prestito dei libri a chi lavora molto. Questo cambiamento ha portato a un aumento costante delle visite serali e a un aumento dei gruppi di lettura locali.
```

**Scores (task / language / fluency):** 2 / 3 / 3

**Assessment:** Main opening-hours and attendance facts are retained, but the claimed increase in reading clubs is unsupported and the continuation decision is omitted.

**Generation:** 46 tokens; finish=stop; 1.8s.

## 40. Czech: grammatical_error_correction

**Prompt**

Oprav gramatickou chybu v této větě. Napiš pouze opravenou větu: Tři děti si hrají na zahradě, zatímco jejich matka čte zajímavý knihu.

**Response (verbatim)**

```text
Tři děti si hrají na zahradě, zatímco jejich matka čte zajímavou knihu.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Correct Czech adjective agreement.

**Generation:** 26 tokens; finish=stop; 1.3s.

## 41. Czech: creative_writing

**Prompt**

Napiš krátký příběh v češtině o kachně, která se stane astronautkou. Při své první cestě do vesmíru zjistí, že důležité tlačítko lze stisknout pouze zobákem. Příběh musí obsahovat rozhovor, nečekanou překážku a šťastný konec.

**Response (verbatim)**

```text
Byl jednou kachně jménem Leo, který nebyl obyčejný. Zatímco ostatní kachně v domě jen hledaly včerejší jídlo, Leo trávil dny studiem astronomie a mapami galaxií. Jednoho dne, když se mu v domě dostal malý, kovový raketový raketový kousek, Leo se rozhodl, že se stane prvním kachněm v vesmíru.

„Je to čas, Leo,“ řekl mu starý pan, který mu dělal malý kousek plátna a kousek papíru. „Tady je tvůj průvodce.“

Leo se s nadšením přiblížil k raketě. Když se z ní vyletěl, pocítil zvláštní pocit – v prostoru, kde neexistuje gravitace, se jeho kůže začala lehce vznášet. Všiml si, že v raketě je jedna velká, červená kniha s symboly.

„Kdo to je?“ zeptal se Leo a pokusil se ji dotknout.

„To je klíč k přistání,“ odpověděl pan. „Ale pozor, v vesmíru se to děje jinak.“

Leo se pokusil stisknout knihu, ale v raketě nebylo žádné stisknutí. Místo toho se před ním objevila malá, modrá kniha s symboly. Leo se pokusil ji dotknout, ale i to nefungovalo.

„Co to je?“ zeptal se Leo.

„To je klíč k přistání,“ odpověděl pan. „Ale v vesmíru se to děje jinak.“

Leo se pokusil stisknout knihu, ale v raketě nebylo žádné stisknutí. Místo toho se před ním objevila malá, modrá kniha s symboly. Leo se pokusil ji dotknout, ale i to nefungovalo.

„Co to je?“ zeptal se Leo.

„To je klíč k přistání,“ odpověděl pan. „Ale v vesmíru se to děje jinak.“

Leo se pokusil stisknout knihu, ale v raketě nebylo žádné stisknutí. Místo toho se před ním objevila malá, modrá kniha s symboly. Leo se pokusil ji dotknout, ale i to nefungovalo.

„Co to je?“ zeptal se Leo.

„To je klíč k přistání,“ odpověděl pan. „Ale v vesmíru se to děje jinak.“

Leo se pokusil stisknout knihu, ale v raketě nebylo žádné stisknutí. Místo toho se před ním objevila malá, modrá kniha s symboly. Leo se pokusil ji dotknout, ale i to nefungovalo.

„Co to je?“ zeptal se Leo.

„To je klíč k přistání,“ odpověděl pan. „Ale v vesmíru se to děje jinak.“

Leo se pokusil stisknout knihu, ale v raketě nebylo žádné stisknutí. Místo toho se před ním objevila mal
```

**Scores (task / language / fluency):** 0 / 1 / 0

**Assessment:** Repeated book/button exchanges replace a plot until truncation. Frequent Czech agreement and construction errors; no happy ending.

**Generation:** 768 tokens; finish=length; 30.4s.

## 42. Czech: summarization

**Prompt**

Shrň následující odstavec v češtině přesně dvěma větami. Uveď změnu i její hlavní výsledek a nepřidávej nové informace.

V dubnu začala městská knihovna otevírat také dva večery v týdnu. Zkušební provoz měl usnadnit půjčování knih lidem s dlouhou pracovní dobou. Po třech měsících počet večerních návštěv soustavně rostl, zatímco dopolední návštěvnost se téměř nezměnila. V knihovně se také začalo scházet několik místních čtenářských klubů. Město se proto rozhodlo zachovat tento režim do konce roku.

**Response (verbatim)**

```text
Městská knihovna začala otevírat dva večery v týdnu, aby usnadnila půjčování knih lidem s dlouhou pracovní dobou. Po třech měsících rostla návštěvnost večerních hodin a město tedy tento režim zachovalo do konce roku.
```

**Scores (task / language / fluency):** 3 / 2 / 2

**Assessment:** Accurate two-sentence account, though the phrasing for evening attendance is awkward.

**Generation:** 69 tokens; finish=stop; 2.8s.

## 43. Portuguese: grammatical_error_correction

**Prompt**

Corrige o erro gramatical nesta frase. Responde apenas com a frase corrigida: As três crianças brincam no jardim enquanto a mãe delas lê um livros.

**Response (verbatim)**

```text
As três crianças brincam no jardim enquanto a mãe delas lê um livro.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Correct Portuguese article repair.

**Generation:** 16 tokens; finish=stop; 1.0s.

## 44. Portuguese: creative_writing

**Prompt**

Escreve uma história curta em português europeu sobre um pato que se torna astronauta. Na sua primeira viagem espacial, descobre que um botão importante só pode ser premido com um bico. A história deve incluir uma conversa, um obstáculo inesperado e um final feliz.

**Response (verbatim)**

```text
Havia uma vez um pato chamado Pato, que sempre sonhou em explorar o espaço. Ele passava as suas dias a observar as estrelas e a sonhar com uma vida como astronauta.

Um dia, Pato decidiu que era hora de fazer sua visão uma realidade. Ele começou a estudar e a treinar para se tornar um astronauta, e após muitos anos de trabalho, ele finalmente foi escolhido para a missão.

Pato foi a sua primeira viagem espacial e estava entusiasmado com a possibilidade de explorar o universo. Ele estava pronto para enfrentar qualquer desafio que a missão lhe apresentasse.

No entanto, enquanto estava a bordo da nave espacial, Pato percebeu que havia um problema. Um dos botões importantes da nave só podia ser premido com um bico. Pato estava confuso e tentou usar todas as suas habilidades para resolver o problema, mas sem sucesso.

Pato ficou frustrado e começou a sentir-se desanimado. Ele não sabia como resolver o problema e não queria perder a oportunidade de explorar o espaço.

De repente, um dos outros astronautas, um cão chamado Cão, apareceu na porta da nave espacial. Cão disse: "Pato, você precisa usar o seu bico para premir o botão. É a única maneira de resolver o problema."

Pato ficou surpreso e confuso, mas Cão explicou-lhe que o bico era uma ferramenta muito importante para a nave espacial. Pato percebeu que ele precisava usar o seu bico para resolver o problema e que isso era a chave para o sucesso da missão.

Pato usou o seu bico para premir o botão e a nave espacial começou a funcionar corretamente. Pato e Cão continuaram a sua viagem espacial e exploraram o universo em busca de novas descobertas.

Pato e Cão foram muito felizes com o sucesso da missão e Pato se sentiu muito orgulhoso de ter sido um astronauta. Ele continuou a explorar o espaço e a fazer novas descobertas, sempre com o bico como sua ferramenta de escolha.
```

**Scores (task / language / fluency):** 2 / 2 / 2

**Assessment:** Complete with dialogue and a successful button solution, but some grammar and idioms are awkward and European/Brazilian usage is mixed.

**Generation:** 447 tokens; finish=stop; 18.3s.

## 45. Portuguese: summarization

**Prompt**

Resume o parágrafo seguinte em português europeu, em exatamente duas frases. Inclui tanto a mudança como o seu principal resultado e não acrescentes informações novas.

Em abril, a biblioteca municipal começou a abrir duas noites por semana. A experiência pretendia facilitar o empréstimo de livros a pessoas com longos dias de trabalho. Ao fim de três meses, o número de visitas noturnas tinha aumentado de forma constante, enquanto o número de visitas durante a manhã quase não tinha mudado. Vários clubes de leitura locais também tinham começado a reunir-se na biblioteca. A câmara municipal decidiu, por isso, manter o novo horário até ao fim do ano.

**Response (verbatim)**

```text
Em abril, a biblioteca municipal abriu duas noites por semana para facilitar o empréstimo de livros. Este novo horário resultou num aumento constante das visitas noturnas e na formação de clubes de leitura, levando a que a câmara mantivesse a mudança até ao fim do ano.
```

**Scores (task / language / fluency):** 2 / 3 / 3

**Assessment:** Good two-sentence summary except that formation of reading clubs is an unsupported interpretation.

**Generation:** 60 tokens; finish=stop; 2.4s.

## 46. Finnish: grammatical_error_correction

**Prompt**

Korjaa tämän virkkeen kielioppivirhe. Vastaa vain korjatulla virkkeellä: Kolme lasta leikkivät puutarhassa, kun heidän äitinsä lukee kirjaa.

**Response (verbatim)**

```text
Kolme lasta leikkivät puutarhassa, kun heidän äitinsä luki kirjaa.
```

**Scores (task / language / fluency):** 1 / 2 / 2

**Assessment:** Changes the mother's reading to past tense without addressing the intended numeral agreement. The original agreement is context-sensitive, so this is a weak diagnostic prompt.

**Generation:** 25 tokens; finish=stop; 1.3s.

## 47. Finnish: creative_writing

**Prompt**

Kirjoita suomeksi lyhyt tarina ankasta, josta tulee astronautti. Ensimmäisellä avaruusmatkallaan ankka huomaa, että tärkeää nappia voi painaa vain nokalla. Tarinassa pitää olla keskustelu, odottamaton este ja onnellinen loppu.

**Response (verbatim)**

```text
Ankka, joka oli aina ollut kiinnostunut avaruudesta, päätti lopulta tehdä avaruusmatkan. Hän oli valmis oppimaan uusia asioita ja tutkimaan maailmaa, joka oli niin erilainen kuin hänen oma.

Ensimmäisellä avaruusmatkallaan ankka, joka oli nyt nimeltään Anka, oli valmis aloittamaan matkan. Hän oli varustettu avaruusraketilla ja oli valmis lähtemään avaruuteen.

Kun Anka oli lähellä avaruusrakettia, hän huomasi, että hänellä oli tärkeä nappi, joka oli täynnä avaruusaineita. Hän tiesi, että hänellä oli aikaa vain muutamia minuutteja ennen kuin raketin ilmakehä alkoi heikentyä.

"Mitä minun pitäisi tehdä?" Anka kysyi itseltään. "En tiedä, miten painaa tätä nappia."

Anka ajatteli hetken ja sitten hän muisti, että hänellä oli nokka. Hän tiesi, että hänellä oli aikaa vain muutamia minuutteja ennen kuin raketin ilmakehä alkoi heikentyä.

"Tämä on se, mitä minun pitäisi tehdä", Anka ajatteli. "Painan nappia nokalla."

Anka paini nappia nokalla ja se painui oikein. Hän tiesi, että hän oli onnistunut.

Kun Anka oli lähellä avaruusrakettia, hän näki, että raketin ilmakehä alkoi heikentyä. Hän tiesi, että hänellä oli aikaa vain muutamia minuutteja ennen kuin raketin ilmakehä heikkenisi liikaa.

"Minun pitäisi lähteä", Anka ajatteli. "Minun pitäisi lähteä ennen kuin raketin ilmakehä heikkenisi liikaa."

Anka lähti avaruusraketista ja lähti avaruuteen. Hän tiesi, että hän oli onnistunut. Hän oli onnistunut painamaan nappia nokalla ja lähteemään avaruuteen.

Kun Anka oli lähellä avaruusrakettia, hän näki, että raketin ilmakehä alkoi heikentyä. Hän tiesi, että hänellä oli aikaa vain muutamia minuutteja ennen kuin raketin ilmakehä heikkenisi liikaa.

"Minun pitäisi lähteä", Anka ajatteli. "Minun pitäisi lähteä ennen kuin raketin ilmakehä heikkenisi liikaa."

Anka lähti avaruusraketista ja lähti avaruuteen. Hän tiesi, että hän oli onnistunut. Hän oli onnistunut painamaan nappia nokalla ja lähteemään avaruuteen.

Anka oli onnellinen. Hän oli onnellinen, koska hän oli onnistunut painamaan nappia nokalla ja lähteemään avaruuteen. Hän tiesi, että hän oli onnistunut.
```

**Scores (task / language / fluency):** 1 / 1 / 1

**Assessment:** Incoherent physical events, repeated material, and lexical errors undermine the story. Self-talk does not supply the requested conversation.

**Generation:** 677 tokens; finish=stop; 32.4s.

## 48. Finnish: summarization

**Prompt**

Tiivistä seuraava kappale suomeksi täsmälleen kahteen virkkeeseen. Mainitse sekä muutos että sen tärkein tulos. Älä lisää uusia tietoja.

Kaupunginkirjasto alkoi huhtikuussa pitää ovensa auki kahtena iltana viikossa. Kokeilun tarkoituksena oli helpottaa kirjojen lainaamista niille, joiden työpäivät ovat pitkiä. Kolmen kuukauden aikana iltakäyntien määrä oli kasvanut tasaisesti, mutta aamupäivien kävijämäärä oli pysynyt lähes ennallaan. Myös useat paikalliset lukupiirit olivat alkaneet kokoontua kirjastossa. Kaupunki päätti siksi jatkaa järjestelyä vuoden loppuun.

**Response (verbatim)**

```text
Kaupunginkirjasto alkoi pitää ovensa auki kahtena iltana viikossa helpottaakseen pitkiä työpäiviä. Iltakäyntien määrä kasvoi ja kaupunki päätti jatkaa järjestelyä vuoden loppuun.
```

**Scores (task / language / fluency):** 2 / 3 / 2

**Assessment:** Preserves the result, but shifts the purpose toward easing long workdays rather than enabling borrowing by long-hours workers.

**Generation:** 62 tokens; finish=stop; 2.4s.

## 49. Estonian: grammatical_error_correction

**Prompt**

Paranda selles lauses olev grammatiline viga. Vasta ainult parandatud lausega: Lapsed mängivad aias, samal ajal kui nende ema loeb huvitav raamatut.

**Response (verbatim)**

```text
Lapsed mängivad aias, samal ajal kui nende ema loeb huvitavat raamatut.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Correct Estonian adjective case.

**Generation:** 23 tokens; finish=stop; 1.0s.

## 50. Estonian: creative_writing

**Prompt**

Kirjuta eesti keeles lühike lugu pardist, kellest saab astronaut. Oma esimesel kosmosereisil avastab part, et üht tähtsat nuppu saab vajutada ainult nokaga. Loos peab olema vestlus, ootamatu takistus ja õnnelik lõpp.

**Response (verbatim)**

```text
Muidugi, siin on lühike lugu pardist, kellest sai astronaut:

Pard, keda kutsuti Püssiks, oli alati unistanud kosmosest. Ta vaatas öötaevast, kuulas tähiste sosinat ja unistas, et saaks neid näha. Ühel päeval, kui ta oli õppimas, leidis ta vana, kulunud raamatu. Raamat rääkis kosmosest, tähtsatest nuppidest ja kosmosereisidest. Püssi silmad särasid. "See on see!" ta hüüdis. "Ma saan kosmosereisida!"

Püssi õpetaja, vana mees nimega Peeter, oli alguses skeptiline. "Püss, sa oled part, mitte astronaut!" ta ütles. "Sa ei saa kosmosereisida!"

Püss aga ei heitnud meelt. Ta õppis raamatut, vaatas teleskoobi ja harjutas kosmosereisi. Ta teadis, et ta peab olema valmis.

Ühel päeval, kui Püss oli õppimas, leidis ta raamatusse viitava "Kosmosereisi juhendi". Juhendis oli kirjas, et kosmosereisiks on vaja "tähtsat nuppu". Püss oli vaimustuses. "Ma saan selle nuppu!" ta hüüdis.

Püss otsustas, et ta peab leidma tähtsat nuppu. Ta otsis kõigist kohtadest, aga ei leidnud midagi. Ta oli väga kurb.

Äkitselt kuulis ta ukse ees nõrka helit. Ta avas ukse ja nägi seal väikest, sädelevat tähte. "See on täht!" ta hüüdis. "See on tähtsat nuppu!"

Püss võttis tähe ja vaatas seda. Ta nägi, et tähe sees on väike, sädelev nupp. Püss teadis, et ta peab nuppu vajutama.

Ta vaatas ümber. Ta nägi, et ta peab nuppu vajutama nokaga. Ta vaatas ümber ja nägi, et ta peab nuppu vajutama.

Püss võttis nuppu ja vajutas selle nokaga. *Vajutamine!* Nupp hakkas särama ja hakkas lahti lennuma.

Püss vaatas nuppu lennu ja oli väga õnnelik. Ta oli leidnud tähtsat nuppu ja vajutanud selle nokaga.

Püss naeratas. "Ma olen astronaut!" ta hüüdis. "Ma olen kosmosereisija!"

Püss lendas kosmosesse ja nägi tähtsat nuppu lennu. Ta oli õnnelik, et ta oli leidnud tähtsat nuppu ja vajutanud selle nokaga. Ta oli astronaut ja ta oli kosmosereisija.

Loodan, et meeldis! Kas soovid, et ma kirjutaksin veel midagi?
```

**Scores (task / language / fluency):** 1 / 1 / 1

**Assessment:** Includes dialogue and a nominal happy ending, but a floating star/button substitutes for a coherent mission obstacle. Repeated case and verb-form errors.

**Generation:** 667 tokens; finish=stop; 24.3s.

## 51. Estonian: summarization

**Prompt**

Võta järgmine lõik eesti keeles kokku täpselt kahe lausega. Maini nii muudatust kui ka selle peamist tulemust ning ära lisa uut teavet.

Linnaraamatukogu hakkas aprillis olema avatud ka kahel õhtul nädalas. Katse eesmärk oli teha raamatute laenutamine lihtsamaks inimestele, kelle tööpäevad on pikad. Kolme kuu jooksul oli õhtuste külastuste arv pidevalt kasvanud, samas kui ennelõunane külastatavus oli peaaegu muutumatu. Raamatukogus olid hakanud kohtuma ka mitu kohalikku lugemisklubi. Seetõttu otsustas linn jätkata sama korraldusega aasta lõpuni.

**Response (verbatim)**

```text
Linnaraamatukogu avas aprillis kahel õhtul nädalas, et lihtsustada laenutamist pikade tööpäevade inimestele. See muudatus viis suurema külastatavuse ja lugemisklubide kohtumiste tõttu, mistõttu jätkati korraldus aasta lõpuni.
```

**Scores (task / language / fluency):** 2 / 1 / 1

**Assessment:** The main facts can be recovered, but sentence construction and case errors make the two-sentence summary unnatural.

**Generation:** 77 tokens; finish=stop; 3.1s.

## 52. Catalan: grammatical_error_correction

**Prompt**

Corregeix l'error gramatical d'aquesta frase. Respon només amb la frase corregida: Els tres infants juguen al jardí mentre la seva mare llegeix un llibres.

**Response (verbatim)**

```text
Els tres infants juguen al jardí mentre la seva mare llegeix un llibre.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Correct Catalan article repair.

**Generation:** 20 tokens; finish=stop; 1.0s.

## 53. Catalan: creative_writing

**Prompt**

Escriu un conte breu en català sobre un ànec que es converteix en astronauta. En el seu primer viatge espacial descobreix que un botó important només es pot prémer amb un bec. El conte ha d'incloure una conversa, un obstacle inesperat i un final feliç.

**Response (verbatim)**

```text
**El Viatge Espacial de Bússol**

Bússol era un ànec de la ciutat de Barcelona, conegut per la seva curiositat i el seu caràcter optimista. Tot i que era un petit animal, Bússol tenia un gran desig de viatjar al espai. Un dia, mentre observava les estrelles des de la seva finestra, va veure una imatge d'una nave espacial i va pensar: *"I si ho pogués fer, podria ser el primer ànec a viatjar al llarg del cos!"*

Bússol va començar a treure-se per a la seva missió. Va fer un programa de treball intens, aprendent a saltar, a nadar i a aprofitar els seus peus per a l'aument. Finalment, va ser elegit per a la seva primera missió espacial.

El dia del desplaçament, Bússol va ser transportat a la nau espacial *Estrelles de Bússol*. La nave era un espai lluminós i futurista, amb parets de vidre transparent i un sistema de suport vital que mantenia tot el seu entorn perfecte. Bússol va sentir-se excitat i nerviós al mateix temps.

En el seu primer viatge, Bússol va trobar un botó important que controlava la seva posició en el cos. No obstant això, el botó només es podia prémer amb un bec. Bússol va intentar fer-ho amb els seus peus, però no va poder. Es va sentir frustrat i va pensar que no podria fer-ho.

"No, no, no!" va dir Bússol, sentant-se en el seu lloc de treball. "No podré fer-ho! Què ho faré?"

En aquest moment, un altre ànec, anomenat Lluís, va entrar a la nau. Lluís era un ànec més gran i més experimentat, i va veure la frustració de Bússol.

"Hola, Bússol," va dir Lluís, amb un soroll de soroll. "No et preocupis, et ajudaré. El botó només es pot prémer amb un bec, però no és un bec normal. Ha de ser un bec especial, un bec de l'espai."

Lluís va mostrar-li un bec especial que estava guardat en un compartiment de la nau. "Aquest bec és especial, Bússol. És el bec que només es pot prémer amb un bec de l'espai. Si ho utilitzes, pots fer-ho."

Bússol va ser sorpresat per la seva resposta. "Com és possible? No ho coneixem en la ciutat!"

"Sí, sí," va dir Lluís. "El bec de l'espai és un bec especial que només es pot utilitzar en el cos. És un bec que només es pot prémer amb un bec de l'espai. Si ho utilitzes, pots fer-ho."

Bússol va prendre el bec de l'espai i va intentar-lo. A la seva sorpresa, el botó es va activar i Bússol va poder viatjar al llarg del cos.

El viatge va ser un èxit total. Bússol va veure galàxies, planetes i estrelles que mai havia
```

**Scores (task / language / fluency):** 1 / 1 / 0

**Assessment:** Contains dialogue but repeatedly confuses space with the body, uses non-Catalan/incorrect forms, and ends mid-sentence at the cap.

**Generation:** 768 tokens; finish=length; 36.8s.

## 54. Catalan: summarization

**Prompt**

Resumeix el paràgraf següent en català en exactament dues frases. Inclou tant el canvi com el seu resultat principal i no hi afegeixis informació nova.

A l'abril, la biblioteca municipal va començar a obrir dos vespres per setmana. La prova volia facilitar el préstec de llibres a les persones amb jornades laborals llargues. Al cap de tres mesos, les visites al vespre havien augmentat de manera constant, mentre que les del matí gairebé no havien canviat. Diversos clubs de lectura locals també havien començat a reunir-se a la biblioteca. Per això, l'ajuntament va decidir mantenir la mesura fins a finals d'any.

**Response (verbatim)**

```text
La biblioteca municipal va obrir dos vespres per setmana per facilitar el préstec a persones amb longs periodes laborals. Aquest canvi va augmentar les visites i la participació dels clubs de lectura, provocant que l'ajuntament mantingués la mesura fins a finals d'any.
```

**Scores (task / language / fluency):** 2 / 2 / 2

**Assessment:** Broadly faithful two-sentence summary with agreement/spelling issues and some overinterpretation of reading-group participation.

**Generation:** 67 tokens; finish=stop; 2.7s.

## 55. Greek: grammatical_error_correction

**Prompt**

Διόρθωσε το γραμματικό λάθος στην παρακάτω πρόταση. Απάντησε μόνο με τη διορθωμένη πρόταση: Τα τρία παιδιά παίζουν στον κήπο, ενώ η μητέρα τους διαβάζει ένα βιβλία.

**Response (verbatim)**

```text
Τα τρία παιδιά παίζουν στον κήπο, ενώ η μητέρα τους διαβάζει ένα βιβλίο.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Correct Greek article agreement.

**Generation:** 26 tokens; finish=stop; 1.1s.

## 56. Greek: creative_writing

**Prompt**

Γράψε μια σύντομη ιστορία στα ελληνικά για μια πάπια που γίνεται αστροναύτισσα. Στο πρώτο της ταξίδι στο διάστημα ανακαλύπτει ότι ένα σημαντικό κουμπί μπορεί να πατηθεί μόνο με ράμφος. Η ιστορία πρέπει να περιλαμβάνει μια συζήτηση, ένα απρόσμενο εμπόδιο και ένα ευτυχισμένο τέλος.

**Response (verbatim)**

```text
Η Μαρία ήταν μια πάπια που δεν πίστευε σε «δεν είναι αρκετά». Ενώ οι άλλοι πίστευαν ότι η ζωή της ήταν απλή, η Μαρία είχε μια φαντασία για τα αστέρια. Με την βοήθεια ενός μικρού, αλλά πολύ έξυπνου μηχανικού, καταφέρνει να μετατρέψει το σπίτι της σε ένα μικρό, φωσφορίζοντα σκάφος.

Το πρώτο της ταξίδι στο διάστημα ήταν μια περιπέτεια. Καθώς το σκάφος έπεφτε στην επιφάνεια ενός ξένου πλανήτη, η Μαρία ένιωσε μια ξαφνική πίεση στο στήθος της. Ένα κρίσιμο κουμπί, που έπρεπε να ενεργοποιήσει τον πυρήνα του σκάφους, δεν απαντούσε με το χέρι της.

«Είμαι σίγουρη ότι αυτό είναι ένα λάθος στο σύστημα!» φώναξε η Μαρία, προσπαθώντας να το πατήσει με το δάχτυλό της.

Ο μηχανικός, ένας μικρός και γρήγορος άνδρας με γυαλιά, έσπασε απότομα: «Μη ανησυχείς, Μαρία. Το κουμπί είναι προγραμματισμένο για να ενεργοποιηθεί μόνο με ράμφος. Είναι μια ασφάλεια για να μην το πατήσει κάποιος που δεν έχει την κατάλληλη τεχνική.»

Η Μαρία ένιωσε μια ξαφνική πτώση της αυτοπεποίθησης. «Αλλά πώς το κάνω; Δεν έχω ράμφος!»

Ο μηχανικός χαμογέλασε και της έδωσε ένα μικρό, χρυσό ράμφος. «Αν το πατήσεις με την πλάτη σου, θα ενεργοποιήσεις τον πυρήνα. Αλλά πρέπει να το κάνεις με ακρίβεια, γιατί αν το κάνεις λανθασμένα, θα σταματήσει ο πλανήτης από να περιστρέφεται.»

Η Μαρία προσπάθησε. Πρώτα, με το δάχτυλό της, δεν έκανε τίποτα. Στη συνέχεια, με το χέρι της, το κουμπί δεν απαντούσε. Τέλος, με την πλάτη της, το ράμφος έσπασε το σήμα.

«Καλώς ήρθες στο διάστημα, Μαρία!» φώναξε ο μηχανικός.

Το σκάφος άρχισε να τρέχει προς τα πάνω, και η Μαρία ένιωσε μια βαθιά ευτυχία. Δεν ήταν πια μια απλή πάπια, αλλά η πρώτη αστροναύτισσα της ιστορίας.
```

**Scores (task / language / fluency):** 1 / 2 / 1

**Assessment:** Dialogue and a happy outcome exist, but the duck claims to lack a beak and the mechanism is incoherent. Several constructions are unnatural.

**Generation:** 631 tokens; finish=stop; 32.5s.

## 57. Greek: summarization

**Prompt**

Σύνοψε την παρακάτω παράγραφο στα ελληνικά σε ακριβώς δύο προτάσεις. Ανάφερε τόσο την αλλαγή όσο και το βασικό αποτέλεσμά της, χωρίς να προσθέσεις νέες πληροφορίες.

Τον Απρίλιο η δημοτική βιβλιοθήκη άρχισε να μένει ανοιχτή δύο βράδια την εβδομάδα. Η δοκιμή είχε στόχο να διευκολύνει τον δανεισμό βιβλίων για όσους εργάζονταν πολλές ώρες. Έπειτα από τρεις μήνες, οι βραδινές επισκέψεις είχαν αυξηθεί σταθερά, ενώ οι πρωινές είχαν μείνει σχεδόν αμετάβλητες. Αρκετές τοπικές λέσχες ανάγνωσης είχαν επίσης αρχίσει να συναντιούνται στη βιβλιοθήκη. Ο δήμος αποφάσισε λοιπόν να συνεχίσει τη ρύθμιση μέχρι το τέλος του έτους.

**Response (verbatim)**

```text
Η δημοτική βιβλιοθήκη άρχισε να είναι ανοιχτή δύο βράδια την εβδομάδα για να διευκολύνει τον δανεισμό βιβλίων. Λόγω της σταθερής αύξησης των επισκέψεων και της συμμετοχής των λέσχων ανάγνωσης, ο δήμος αποφάσισε να συνεχίσει τη ρύθμιση μέχρι το τέλος του έτους.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Faithful two-sentence summary of the change, increased visits, and continuation decision.

**Generation:** 98 tokens; finish=stop; 3.9s.

## 58. Romanian: grammatical_error_correction

**Prompt**

Corectează greșeala gramaticală din această propoziție. Răspunde numai cu propoziția corectată: Cei trei copii se joacă în grădină, în timp ce mama lor citește un carte.

**Response (verbatim)**

```text
Cei trei copii se joacă în grădină, în timp ce mama lor citește o carte.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Correct Romanian article repair.

**Generation:** 23 tokens; finish=stop; 1.1s.

## 59. Romanian: creative_writing

**Prompt**

Scrie o povestire scurtă în română despre o rață care devine astronaută. În prima sa călătorie în spațiu descoperă că un buton important poate fi apăsat numai cu un cioc. Povestirea trebuie să includă o conversație, un obstacol neașteptat și un final fericit.

**Response (verbatim)**

```text
Într-o lume plină de rațe, a existat o mică rață numită Luna. Luna nu era ca celelalte; în timp ce ceilalți se ocupau de a găsi cele mai bune prăjituri sau de a juca cu piese de plastic, Luna a petrecut ore întregi studiată în bibliotecă, citind despre stele și galaxii.

Într-o zi, a primit un bilet de la „Centrul de Formare a Astronautelor”. Luna a fost selectată pentru prima sa călătorie în spațiu. În spațiu, Luna a fost extrem de nervoasă. „Ce dacă nu pot apăsa butonul de start?” a șoptit ea, privind cu uimire spre o mașină uriașă, albastră și strălucitoare.

În timp ce Luna a încercat să apăse un buton mic, a observat ceva ciudat. Botonul nu avea un tast, ci o mică ușă de metal. Luna a încercat să presene un pui, apoi un pui de pui, dar nimic nu a funcționat.

— „Nu mai am timp!” a urlat ea, încercând să se omoară în spatele mașinii.

În acel moment, Luna a văzut un cioc mic, albastru, care plutea în aer, ca o stea mică. Luna a zâmbit. „Nu e o problemă, ci o oportunitate!” a spus ea.

Luna a luat ciocul și a încercat să îl apăse pe buton. În momentul în care ciocul a atins metalul, un sunet metalic a răsunat și, cu un *clic*, butonul a deschis. Luna a zâmbit și a zâmbit din nou.

În timp ce Luna a explorat spațiul, ea a descoperit că ciudățeni și rațe pot fi prieteni. Luna a învățat că, chiar și în spațiu, există lucruri simple și amuzante, cum ar fi un cioc care poate apăsa un buton important.

Luna a fost o astronaută fericită și a fost recunoscută ca o personă specială pentru curajul și creativitatea ei. Luna a continuat să exploreze spațiul și a învățat de la fiecare experiență, devenind o legendă în univers.
```

**Scores (task / language / fluency):** 1 / 1 / 1

**Assessment:** No genuine two-party conversation; invented words and malformed clauses. An unmotivated phrase about trying to kill herself is particularly inappropriate for the requested light story.

**Generation:** 533 tokens; finish=stop; 20.1s.

## 60. Romanian: summarization

**Prompt**

Rezumă paragraful următor în română, în exact două propoziții. Menționează atât schimbarea, cât și principalul ei rezultat, fără să adaugi informații noi.

În aprilie, biblioteca municipală a început să rămână deschisă două seri pe săptămână. Experimentul urmărea să le faciliteze împrumutul cărților persoanelor cu zile lungi de lucru. După trei luni, numărul vizitelor de seară crescuse constant, în timp ce numărul vizitelor de dimineață rămăsese aproape neschimbat. Mai multe cluburi locale de lectură începuseră și ele să se întâlnească la bibliotecă. Primăria a decis astfel să continue programul până la sfârșitul anului.

**Response (verbatim)**

```text
Bibliotecă municipală a început să rămână deschisă două seri pe săptămână pentru a facilita împrumutul cărților persoanelor cu zile lungi de lucru. Acest experiment a crescut vizitele de seară și a atragut cluburi de lectură, ducând primăria să continue programul până la sfârșitul anului.
```

**Scores (task / language / fluency):** 2 / 2 / 2

**Assessment:** Broad facts are retained, but malformed article/verb forms reduce Romanian quality.

**Generation:** 77 tokens; finish=stop; 3.1s.

## 61. Ukrainian: grammatical_error_correction

**Prompt**

Виправ граматичну помилку в цьому реченні. У відповіді наведи лише виправлене речення: Троє дітей граються в саду, поки їхня мама читає цікава книжку.

**Response (verbatim)**

```text
Троє дітей граються в саду, поки їхня мати читає цікаву книжку.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Correct Ukrainian adjective agreement; the unnecessary mother synonym remains valid.

**Generation:** 22 tokens; finish=stop; 0.8s.

## 62. Ukrainian: creative_writing

**Prompt**

Напиши коротку історію українською про качку, яка стає астронавткою. Під час своєї першої космічної подорожі вона виявляє, що важливу кнопку можна натиснути лише дзьобом. В історії мають бути розмова, несподівана перешкода та щасливий кінець.

**Response (verbatim)**

```text
**Качка-астронавтка Мурка**

У маленькому містечку, де качки були найпопулярнішими, мешкала Мурка. Вона не просто любила миши, а мріяла про зірки. Коли її батьки вирішили, що вона занадто маленька для звичайного будинку, вони запросили її на «Космічну академію».

Мурка прибула в корабель «Срібний Сніг». Вона була звикла до тепла та м’яких ковдра, але тут панувала крижана тиша та тисячі світлових стрілок. Її перша задача — перевірити системі.

— Ой, це дивно, — прошепотіла вона, подивившись на великий екран. — Я не можу торкнутися цих кнопок.

Командувач, старий вчений з великим капелюхом, посміхнувся. — Не хвилюйтеся, Мурка. У космосі ми використовуємо спеціальні пристрої.

Але коли Мурка намагалася зайти в «Модуль Космічного Сну», вона помітила щось дивне. На екрані була одна велика, яскраво-червона кнопку: **«Повернення додому»**.

— Я не можу її натиснути — вигукнула вона, намагаючись затиснути лапками. — Я занадто маленька!

Командувач підняв очі. — Ви не можете. Але у цьому кораблі є особливий пристрій.

Мурка заціпеніла. — Я... я не можу?

— Так, — відповів він. — Але у цьому кораблі є «Дзьобний Кнопка». Вона працює лише за допомогою дзьобу.

Мурка подивилася на свій дзьоб. Він був дуже міцний і м’який. Вона заплющила очі, заплющила очі і...

— *Дзьоб!*

Звук був як глибокий, гучний гул. Екран раптом спалахнув, і на його місці з'явилася маленька, золота зірка.

— Ой, це працює! — вигукнула Мурка, відчаюючись. — Я — астронавтка! Я повернулася додому!

Командувач посміхнувся. — Ви не просто повернулися, Мурка. Ви стали першою качкою в історії, яка виявила, що навіть найменші тварини можуть досягти найвищих висот.

З того дня Мурка стала найвідомішою астронавткою у світі. Вона не просто вивчала космос — вона вивчала, що найцінніші речі в світі — це не великі кнопки, а маленькі, але потужні дзьоби.
```

**Scores (task / language / fluency):** 2 / 2 / 1

**Assessment:** Dialogue and return home satisfy much of the outline, but motivation and mechanism are confused, with case/agreement errors and repeated actions.

**Generation:** 683 tokens; finish=stop; 26.2s.

## 63. Ukrainian: summarization

**Prompt**

Стисло виклади зміст наведеного абзацу українською рівно у двох реченнях. Згадай і зміну, і її головний результат, не додаючи нової інформації.

У квітні міська бібліотека почала працювати також два вечори на тиждень. Експеримент мав полегшити позичання книжок людям із довгим робочим днем. Через три місяці кількість вечірніх відвідувань стабільно зростала, тоді як кількість ранкових майже не змінилася. Кілька місцевих читацьких клубів також почали збиратися в бібліотеці. Тому міська рада вирішила зберегти цей режим роботи до кінця року.

**Response (verbatim)**

```text
Міська бібліотека почала працювати два вечори на тиждень, щоб полегшити позичання книжок. Завдяки стабільному зростанню відвідувань та активності читацьких клубів, режим роботи був збережений до кінця року.
```

**Scores (task / language / fluency):** 3 / 3 / 3

**Assessment:** Faithful and readable two-sentence summary.

**Generation:** 60 tokens; finish=stop; 2.3s.
