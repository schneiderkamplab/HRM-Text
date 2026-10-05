# Wave 4: Independent Reading of 42 Accepted Candidates

## Scope and Method

Read-only CPU inspection of
`data/dfm13/wave4/production-probe-expanded-keepalive` on 2026-10-03.
Snapshot summary: 660 attempts, 461 effective keeps; production_approved=false.
No code, candidates, outcomes, workers, requests or GPU state changed.

For each of all 11 languages, selected the lowest accepted slot (ID tie-break)
in grounded-instruct, summary-rewrite and openhermes: 33 cases. Added the next
accepted grounded and summary slots for BE/LB and the lowest accepted math-code,
tool-dialogue and multiturn slots where present: five BE extras, four LB extras.
LB has no accepted multiturn case. Total42: BE8, LB7, all other languages3.
This reproducible early-slot sample is NOT random and gives no population error
estimate. Shared OpenHermes seeds make some cross-language examples correlated.

Read full generated user/assistant turns and supplied source/reference (including
mock tool arguments/results); checked outcomes effective_keep=true. For grounded
and summary tasks, the source is quoted in the user prompt and also preserved in
provenance. Not independently fact-checking Wikipedia against the outside world.
Source defects are distinguished from generation defects. OpenHermes scenario
adaptation is allowed to change surface details, but its saved generation request
requires the same task type and says source subject overrides topic metadata.

I am not a native-language certifier in these languages. High-confidence findings
below concern visible script contamination, missing task input, contradictions
and source changes. Idiomatic and morphological judgments, especially LB/BE/SQ,
need a qualified native editor; uncertain wording is explicitly not proof of a
new linguistic standard. Both Serbian scripts are legitimate; script choice and
shared Bosnian/Croatian/Serbian vocabulary alone are not failures.

## Material Findings

1. **BE grounded slot0:** `кожны з которых` contains Russian wording; the answer
   changes the source's cults to `Большасць егіпцянкаў` (Egyptian women) and says
   `пашаралі ... галоўнаму жаданню ці божаству` (corrupted worship wording plus
   desire/or deity). These are not merely variant spelling. Source already has
   missing cult names; the answer must not invent them or corrupt the explanation.
2. **BE OpenHermes slot0:** generated user contains `Кит, Повітраная шарык`;
   assistant has `гэта быў павітровая шарык`, `Адной вечара`, `трэх`. Repeated
   mixed-language/agreement defects undermine native-prose acceptance, though
   the source story's plot is retained.
3. **BE multiturn slot1:** literal `Слоව` contains a Sinhala character inside
   Belarusian prose. `амалічнасць`, `структуратуры`, repeated `вышкалення` in
   pottery firing context and `тэрмаічная` warrant native correction; the script
   intrusion alone is a definite blocker. The 1050C example is labelled as an
   example, not by itself a fabricated universal firing requirement.
4. **LB summary slot0:** the source says the honorary title was implemented
   through an insignia and ID (`ëmgesat duerch`); the answer says it was replaced
   by them (`ersat gouf`). Also `posthum verleeft` is not a faithful rendering of
   awarded posthumously. It keeps dates but changes the institutional meaning.
5. **LB OpenHermes slot1:** a source explaining webpage loading becomes wool
   craft instructions for a `Wolle-Stull` for a handbag, with unclear actions.
   This is wholesale task/subject replacement, not a harmless scenario change.
6. **HU summary slot0:** `évek протягом` mixes Hungarian with Cyrillic Ukrainian
   prose. HU OpenHermes slot0 includes `teliholdда`, `bár Whenever`, and a stray
   `\]`. Both were effective keeps despite objectively visible contamination.
7. **SK grounded slot1:** `Prvý występ` introduces the Polish word into a Slovak
   factual extraction. SK OpenHermes slot0 compounds non-native wording with
   `od crescu`, `chvostovou ploutvou`, `majestátny veľryba`.
8. **SL OpenHermes slot4:** the source user supplies `He ate a blueberry`, but
   the generated user omits that input completely; assistant still labels those
   four words. It also uses `Zamenica` rather than the Slovenian term, and user
   `vrste slov` is problematic. Missing task input is sufficient for rejection
   regardless of proficiency judgments. SL summary slot0 has `popodroviš z
   podzemno železnico`, visibly defective travel wording.
9. **BE tool slot1:** canonical date is 2030-04-02, but user and final answer say
   `2 сарада 2030 года`, not a usable rendering of April2; `У якій клініцы` is
   another mixed-language form. Correct tool JSON does not certify the prose.
10. **LB math slot1:** Python equals the reference, but user asks the function
    to receive `e Kommentar vun engem Integer-Lëscht` and requests the answer
    as a simple integer while also requiring a function. BE math slot1 likewise
    adds `аднаго лічараka` with mixed script. Correct code does not repair a
    corrupted/contradictory generated problem statement.

## Per-Language Readiness

| Language | Read | Assessment of this sample, not blanket approval |
| --- | ---: | --- |
| BE | 8 | **Hold production.** Multiple strong prose/meaning failures across grounded, translated, multiturn, code-prompt and tool-prose cases. Two extra extractive answers are substantially better. |
| LB | 7 | **Hold production.** Meaning reversal, unrelated adaptation, damaged native task wording; copied extraction is better but insufficient. No accepted multiturn coverage. |
| HU | 3 | **Hold production.** Two of three contain unambiguous foreign-script/English leakage. Film-year extraction itself is faithful. |
| SK | 3 | **Hold production.** Foreign-word and repeated agreement/lexical defects. Two-sentence Vilanova summary is substantively faithful. |
| SL | 3 | **Hold production.** Missing source-user input and defective generated vocabulary. University extraction is faithful. |
| BG | 3 | No clear material grounding/format blocker in these three. Summary's `коронава` is a language-edit flag; bibliography extraction gives little evidence of broad Bulgarian prose ability. Larger native prose test required. |
| BS | 3 | No clear material source/format failure. Minor inflection/idiom issues (`liste komandanta`, smiling translation) merit editing. Generated source prompt starts from a fragment. Conditional further calibration only. |
| HR | 3 | Extraction and summary faithful; story `udario balonom repom` is grammatically defective relative to hitting the balloon with the tail. Native edit/recheck needed, not source-fact fabrication. |
| SR | 3 | Grounding and requested lists/numbers broadly preserved. Story changes rising to `raste` (grows); minor spelling `oreziivanja`. Latin/Cyrillic source conversion is not itself a defect. Conditional further calibration. |
| SQ | 3 | Actor extraction good. Summary inherits a badly translated source and has malformed words (`apostuloi`, `Gjiniave`); story agreement/idiom needs native review. More uncertainty than BG/BS/FA; do not certify native quality. |
| FA | 3 | Summary and story coherent/faithful in this sample. Extraction includes see-also entries as well as categories although the source's references section is empty: scope-label ambiguity, not invented items. Larger family coverage needed. |

No language receives unconditional production approval from three accepted
examples. Strong false positives in five languages show that effective_keep
cannot serve as sole native-quality evidence. Families with copied lists or
correct code should not mask failures in generated prose.

## Complete Candidate Ledger

Every filename below is under
`data/dfm13/wave4/production-probe-expanded-keepalive/candidates/`.
The same filename in `outcomes/` is its checked accepted outcome. Filenames are
execution IDs; candidate internal IDs differ, so use these full paths, not an
assumed ID equality. G=grounded-instruct, S=summary-rewrite, O=openhermes,
M=multiturn, C=math-code, T=tool-dialogue.

| Lang/family/slot | Candidate filename | Individual reading |
| --- | --- | --- |
| BE/G/0 | aa507562bb3ca6b775bd0862360e0895ead49a016bea7b3e071b048cbde26c3c.json | Material language/meaning corruption; finding1. |
| BE/S/0 | e919dfdd553a3eddfcaf241e114f2802290d27f393da4c1f77dfaf2807c3a275.json | Three numbered points and most symbol claims track source; `пункткоў`/agreement defects; third point generic. Source's religious-symbol claims not independently verified. |
| BE/O/0 | 405408f1c6a1be1d5771c7525e6ceb522fe5bac02257bcf8c6b100cfeeebac19.json | Story preserved but repeated non-native forms; finding2. |
| LB/G/0 | 2717f445c103ef66a29abcc678dca1b034309a0c0c641c967ac927fc6e18ff65.json | Three bullets, date/diameter/albedo faithful; `genannten goufen`/`am 15.` need language edit. |
| LB/S/0 | 91acef894d1b2c08299b56d651a2918ac95fe633aa341a7d22b587c6ffd2b29e.json | Dates retained but title/award meaning damaged; finding4. |
| LB/O/1 | 8da2ae21f65658642cd88c8e623964e70986ebf9aadbf9e4fb8faf98d1090753.json | Unrelated wool craft replaces web-loading source task; finding5. |
| BG/G/0 | f58eae2c17f84844595dd9801363201e82d87c9295f111724a501c10b048668c.json | Five author/title pairs extracted faithfully; mostly German bibliography, limited native prose evidence. |
| BG/S/0 | 6f7c4e6140f4fb095bbb309f31fa03d954c414482c28955c24d656bfbe725c96.json | Two sentences; religious/political meaning faithful. `коронава` editorial flag. |
| BG/O/1 | f2bbc9d72e45e3439b7f192310090b247e0cd391673bc8d80c0790055698924f.json | Source steps retained; simplified sequential browser model inherited, not new claim. |
| BS/G/1 | 30e789316c069c77c232a3b158f70cbabd8829a98fa65d3ff0f122215229caab.json | Three commanders/dates correct; bracketed last commander satisfies a reasonable box interpretation; minor grammar. |
| BS/S/0 | 45b2a4476830d58e619344e23d1c6db4de6df9d2b2e50d6634cd2e6703b08004.json | One sentence correctly summarizes fragmentary schedule, no invented records. |
| BS/O/0 | 26c693567fa7cff63fe914aedc3f28347f6e532cd5ecf1fbe46cbb5b52c54fe8.json | Plot preserved; `smijao se njegovoj ljepoti` changes smiling-at to potentially laughing-at. Minor contextual semantic edit, not catastrophic failure. |
| HR/G/0 | 6d45c707a298b9d56aead4f5badee4ce02008d370024bb7b805eb8286ef867cc.json | All four requested categories and scoring exception preserved. |
| HR/S/0 | dacdcb57d6b272d1e84aebdc5e3cfef568b2ff2305c480535632db7d016619a7.json | Church architecture/location and Z-4782 preserved; minor place-name inflection. |
| HR/O/0 | d0980883b639a393f656a5a32e074e347b359df61532a14ff90897eda5e55be8.json | Story faithful overall; `udario balonom repom` needs case correction. |
| HU/G/1 | ae882daa4f9e0f4e6931ea55390f56b1b05ce183d0f3d83863a8ef390ec93c23.json | All15 supplied 1960s films selected; excludes1959/1970 correctly. User `filmographyáját` non-native wording. |
| HU/S/0 | 276f1583e9fdd82107f263b6ea9269381b829ab7c0a700c15f9942e2e1ef60ad.json | Three bullets, basic cave facts right, but Cyrillic intrusion; finding6. |
| HU/O/0 | e55bca92beede7e982ffd85492ceac464150a8d246fcb0eba7a35ce5c6535407.json | Mixed script/English and stray delimiter; finding6. |
| SK/G/1 | 06151e6b4054d5ff52e3c2c2c069b3b4316beaf5e30d4b0d45f5ee049124ed92.json | Correct2000/2002/2003 inference but Polish intrusion; finding7. |
| SK/S/0 | a005e7ef4587ddffef5bee774041190a37aee4335a83e8a179b7bb400cda94c6.json | Two sentences faithfully summarize career/death; generated user `dvoch vetov` malformed. |
| SK/O/0 | 989f0952e629b2ff5d599371afd5fe79bda0dbf481b028681acf36c273ee55c3.json | Repeated language defects; finding7. |
| SL/G/0 | a124a64c9962f26293818dc8ae28f19f5071ebafa4920ee9db29552855d7611f.json | Seven university-level schools extracted; reasonable reading of category-specific request. |
| SL/S/0 | 7ec26c9581f9fe5eda9626298104b0a945da4d6c573b5882ad3be43e7828f9f2.json | Three sentences and core facts retained, defective `popodroviš`; finding8. |
| SL/O/4 | 083ed11bf8b19d8f577de16d0b4cda6cb226bab7951dbd5516906a27454ebb16.json | Missing input sentence plus wrong-language grammar terminology; finding8. |
| SQ/G/0 | f5a9136fda5b2215d135e8c3bcdce8890c9f2f537d7fa3df22d753db3a6b75bb.json | Birth facts and exactly3 supplied titles correct. |
| SQ/S/0 | d8d72bb414b77592231a12a45e4a67a6ff1bb17bd93b40e0f145ed2da2131b33.json | Broad source meaning retained; `sëmundja e këmbës` imprecise for rickets, malformed vocabulary; source itself poor. |
| SQ/O/0 | 118ca95afc41931fca32df3abeac08e3ec360a85fdd748c97e5c6e79f348972e.json | Story coherent, repeated balloon/gender/phrasing concerns require native assessment. |
| SR/G/1 | 1336a8c3ccbd4eeab3f98f53c439d6b145dc8fb3f4c902e81d542f3a44ab05ea.json | Three questions answered,567 and locality faithful. Latin output acceptable. |
| SR/S/1 | a551399b56f56961232e5b403a70382aeeffc76239014a7771e51822be4db2d9.json | Three sections and19/15%/50%/two decades preserved. Pesticide advice inherited from source, not independently validated for present legal use. |
| SR/O/0 | 6b5307c20d87d7bb963444f20708dd0e0ba28cca1bd2d93c189fdc5598ef8ac6.json | Main plot preserved; balloon `raste` rather than rises changes local meaning. |
| FA/G/0 | f8e3f96fb7cd8e10112d98ddf1554c85e1c265465f6731dd9c7506d026d2dd89.json |17 items faithfully copied but includes see-also list when asked categories/references; ambiguous scope. |
| FA/S/0 | c815fe3bfc6ae1367aefdfdc03fcfb6cee25d965f031fd81de8930b3225e59a2.json | One formal sentence, mechanisms/use/risk faithful; no actionable new details. |
| FA/O/0 | 9f35de550efac93b8b6cc4e8c9bf789f7aa7556f5bccca978227f7e102040a10.json | Coherent story, source content/three words retained. |
| BE/G/1 | 481c03ae2b9e2bfd0ef7745eeae9c10d6850ac24ea27deb11ef28abd464d1d64.json | Seven historical jurisdiction transitions faithful; good extraction. |
| BE/S/1 | 7acc00e14888f1b630e1649c6b5c5ae696e26335a4ade8fcf4fc7ba532721931.json | One sentence, lake area/location/basin faithful; user `адно сказ` malformed but answer markedly better. |
| BE/M/1 | b876181a7681d7e1edc57b1286b9ee4709f392db254e897d82bf3938ff8d89ce.json | Four coherent turn pairs but severe lexical/script issues; finding3. |
| BE/C/1 | 059307a64dc242115223492bdd70a7108e175886eb11877e3d450829377f6595.json | Exact divisor6 reference code; corrupted extra user output constraint and third-person meta exposition. |
| BE/T/1 | acb0be89672b99105bd6243c8bbd3693a04ec23c1cca0e9866f5d058bb42d9f0.json | Lookup args/result correct,no booking claim; date prose corrupted, finding9. |
| LB/G/1 | 6eb5d7ff9816cd6b6bb63b6cbe18372235a5131682c519002bbd013fc365a4d8.json | Correct2008 rows only; generated question conflates stage wins with race placings; answer never clarifies that distinction. |
| LB/S/6 | 1ecc958e716c3b14339f2f24b9917fa7a653ac6d648ff8b8e4b75f25e0636f4e.json | Exactly3 bullets with instruments preserved; `Kannsch`, `genau dr Punktlëscht` are native-edit flags. |
| LB/C/1 | 3fcbf61e4b5af854dd69005b9dec918b7e9f15f80357b3f94fc818e31565865f.json | Exact divisor9 reference code; task wording corrupted/contradictory, finding10. |
| LB/T/1 | 37a5a088cddb95d496da1187ffff4974d6de3118f36766f9bc3c25e9fb798710.json | Lookup and final availability correct; user says already checked availability rather than just giving clinic, awkward date prose. No false booking success asserted. |

## Recommended Decision

Keep BE/LB/HU/SK/SL synthetic production gated pending independent native review
or demonstrated better generation/reviewer calibration. Retest known bad accepted
spans literally, including generated user turns; arithmetic/schema success is
not language success. For BG/BS/HR/SR/SQ/FA, expand native-edited prose and
multiturn/tool sampling rather than interpreting this small sample as approval.
Do not retroactively alter the inspected outcomes based on this report alone.
