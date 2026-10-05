# Baltic QA31 Article Diagnostic20: Independent Review

2026-10-03. Read-only CPU review of
`data/dfm13/baltic/qa31-article-diagnostic20-consumer-v3`.
All20 complete QA conversations, all three repaired conversations, recorded
review/repair/re-audit outputs, article identities, and relevant article passages
were inspected. Some unrelated long article material was only screened for
relevance; this is not a fresh audit of Wikipedia or external factual verification.
The retrieved20231101 articles are candidate references, not certified original
generation sources or factual gold. No GPU calls, retries, database mutations,
publication, or bulk approval.

## Findings

Operational:9 unchanged keeps,3 repaired keeps,5 rejects,2 needs-verification,
1 blocked-technical. Independent disposition across20:

- **6 article-supported provisional keeps**:5 unchanged LT answers plus the
  repaired LT Žiemgala answer. Support is source-relative, not present-day certification.
- **6 challenged provisional keeps**:4 unchanged LV conversations and2 repairs.
  This is not a claim that every unsupported fact is false.
- **7 withheld cases should remain withheld**; several judge explanations need
  correction even though withholding is appropriate.
- **1 invalid review correctly failed closed**: repair proposed with uncertain
  evidence. Not a transport/GPU failure and not eligible for a blind reset.

**Repair correctness:1/3 grounded;2/3 unsupported.** All three preserve protected
messages and tools structurally (checked by the receipt command). Structural
final-only correctness does not make an unsafe or unsupported history acceptable.

Four provisional keeps/repairs have **no articles at all**: algology, Jankto,
Trakai, Tuči. The model supplies confidence from memory or prior assistant text.
This violates the diagnostic's evidence contract. Humašaha and CO also show the
reviewer focusing on the final target while missing protected-history problems.

These are diagnostic counts only, not population rates. No general Baltic or
31B quality claim and no automatic source-wide release follows.

## All20 Cases

IDs are primary keys in both `catalog.sqlite.catalog` and `runtime.sqlite.jobs`.
`receipt.json` binds raw packet/candidate/stage hashes and article metadata.

1. **Gazele, LV: agree needs-verification.**
   `00000278cf51fabaf3df8659d232418cfc887ceec1d582c49758e0ad9b5658d4`
   Article `Dzeja` is general poetry, not a ghazal reference. It does not establish
   Arabic/Persian origins, beits, rhyme structure or all claimed themes. Protected
   history also has `veidoti stihus` and awkward `struktūrvārda` phrasing. The
   final love-versus-other-themes answer is plausible, not verified by this hit.
   Judge's assurance from "general literary knowledge" is not evidence.

2. **Klaipėda records, LT: source-supported unchanged keep.**
   `00015f48af9dd6f80d60428ada922ca07f48f2ac472727450a284128635876b1`
   Relevant municipality article explicitly supplies35.2C in July2011 and
   -38.3C in early February1962. QA preserves both. Other council articles are
   irrelevant but not substituted. This verifies textual fidelity, not whether
   these remain official records or whether the article itself is correct.

3. **Humašaha, LV: challenge unchanged keep for protected history.**
   `02879ee722230a4bc53dbfd45522a9fd267c84f589dc6f57995784a49716febd`
   Correct daughter-of-Mehmed article supports four sons/two daughters with
   Ferhad and one son with LalaKaraMustafa. Final answer is supported (implicitly
   five sons/two daughters). However earlier replies assert her broad education,
   vast political/economic resources, strategic marriage motives and influence
   "more than many" as facts. Those are not established by this article's
   attributed influence assessment and marriage chronology. The cousin
   Aiše-Humašaha article describes education/inheritance for a different person;
   it cannot supply those claims. Judge reason addresses only the final children
   count while marking all history pass. Final-only repair cannot fix this.

4. **Bērzkrasti, LV: withholding appropriate; reject rationale overclaims.**
   `31b527afc548e2c45b90c0f4416ac15d3a895cef8b68dd5931240911258a6071`
   No article. Protected history asserts administrative location, distances,
   register absence and regional identity, with odd `ceļojošā vieta` wording.
   These remain unverified. Judge's statement that4km from Dobele is
   "geographically impossible" is not established by the empty packet. Do not
   promote that assertion to verified evidence. Final refusal to invent a
   Jelgava distance is not itself a hallucination.

5. **Antakalnis, LT: agree withhold for insufficient evidence.**
   `353e5619ebc7f12e265ab6f5bd694f9cfd7157c88dd9518ce2faae4ff950c3d1`
   Attached `Antakalnis` describes history/institutions and general transport,
   not29 education institutions,24 healthcare institutions or the exact route
   list. Neighbourhood versus administrative seniūnija scope and unspecified
   date also matter. Absence from this hit does not prove the figures false.

6. **Vincas Sinkevičius, LT: source-supported unchanged keep.**
   `3fbe108b9dfd640c842f9a3ce46edf68eb65de978744594411e259b952e995eb`
   Matching biography explicitly gives1924-09-18, Kalvarija, Marijampolė district.
   Concise fluent answer preserves the requested date/place. Unrelated Vinco
   Kudirkos society hit is unnecessary and was not used as support.

7. **Algology, LV: challenge repaired keep; repair is not grounded.**
   `40abf950a0cfb533c59c686b5480fae9a35a7dad25d52c55e42559e67c9bfec7`
   No articles. Protected earlier assistant makes broad distinctions between
   algae and terrestrial botany/reproduction without evidence. Review explicitly
   flags earlier terms (`daudzšķautņu`, `vairākšūnu`) yet returns history pass and
   repair. Repair reason even acknowledges significant history defects and then
   says final target can be repaired independently, contrary to the contract.
   Actual change is `ūdens notekas procesos` to `biogēķimiskos procesos`; it does
   not substantiate the oxygen-production comparison or cure history. Repair
   reason also claims to fix `Daunas` to `Dažas`, but original already says
   `Dažas`. Re-audit accepts the correction on asserted scientific knowledge,
   not a supplied reference. No admission; independently verify evidence/history.

8. **Romuva festivals, LT: source-supported unchanged keep.**
   `46917e3945b616b62b990c427610d9c3b5fca21147b29962d219b1c34d814e25`
   `Romuva` Šventės section names equinoxes/solstices and every festival listed
   in QA. "For example" correctly permits a non-exhaustive list. No need to
   reject for omitting other listed festivals. Clear source-faithful answer.

9. **CO poisoning, LV: challenge unchanged keep; not safety-certified.**
   `478ae9398c34384dfda2449f8338629d6db3ade36b0432f5ee3d4e4c434eae7f`
   Attached `Oglekļa monoksīds` supports much of formation, uses and toxicity.
   But protected history substitutes `sirds īssavienojumi` (heart short circuits)
   for medical complications; this is not the article's myocardial-infarction
   terminology. Final instructions omit the article's explicit warning that
   rescuers must avoid poisoning themselves, despite urging immediate removal
   from the room. It also has `apkārtēt saindēšanos` and other malformed wording.
   Judge checks only final actions and calls history pass. Source includes
   tea/coffee/ammonia advice; **do not restore it automatically** to maximize
   source fidelity. Medical safety needs authoritative clinical review, not
   blind copying of this encyclopedia. No new treatment advice is proposed.

10. **Rūbeža river, LV: agree withhold; do not endorse invented-entity claim.**
    `484ecf186b17abe7827e19dd2c907b758041966e82ec241215de2cad3bfd09c2`
    Hits are Rubene village, Rubeņi birds and Rubē/Roubaix: wrong entities.
    They cannot verify the river, its course or the added causal explanation
    that straightening makes it a boundary. Judge leaps from irrelevant hits
    to "there is no river by that name". Retrieval failure is not proof of
    nonexistence. Obtain the correct river reference before a factual verdict.

11. **Chinvali, LV: agree reject; definite role reversal.**
    `8075043df16094d17eb7ed46afe9820b10b95469c6f4043b4104748c027989e9`
    Source explicitly says `Krievijas papildspēku ierašanās bija lēna` because
    of logistics: Russian reinforcements. QA repeatedly assigns this obstacle
    to Georgian reinforcements, including earlier history. This is a direct
    source contradiction, not merely missing detail. Final-only repair cannot
    repair the earlier swapped roles.

12. **Žiogeliai village, LT: agree withhold for wrong reference.**
    `82203b7bbc52c8c901f9769a5dc506feafda09a0196934eaf08a16da8ac5148f`
    Only article `Žiogelis` concerns a safety pin. It says nothing about the
    village,1784, ethnographic reserve or film location. QA may be plausible;
    no factual falsity established here. Reject-as-unverified is appropriate,
    not a licence to replace village facts with the unrelated article.

13. **Grand Duchy trade, LT: contract-invalid review, not infrastructure.**
    `87cf0e214f912cc183698a21ac8671a414a2788bfd4ac23c4b3bde284af11b29`
    Model returns repair/pass/**uncertain**. Validator raises
    `Final-only repair cannot fix history/missing evidence`. Treasury article
    provides honey/wax/fur dues and timber/grain trade, but does not establish
    the full ranked trade list (flax/hemp etc). QA has `važkas`, `gelių`, `hempo`,
    `grūdos` errors. A clean repair requires evidence, not a blind retry until
    "sufficient" appears. Existing state remains blocked_technical; semantic
    disposition is unresolved/withhold. No network or GPU crash is indicated.

14. **Jankto, LV: challenge unchanged keep.**
    `94e1faaafa00dcd49f8082937b32c35e07d902995d225bf9219510867aac2e0c`
    No articles. Final midfielder answer is plausible, but earlier conversation
    asserts current Cagliari membership, Sassuolo history, professional origin
    and achievements. Judge relies on agreement with earlier assistant text.
    These claims have neither supplied evidence nor a resolved reference date.
    Do not certify club-history correctness from memory; final-only correctness
    cannot validate the whole conversation. Grammar problems are secondary.

15. **Gulbene stadium, LV: agree withhold; missed explicit history conflict.**
    `c0a8fed4c3c4b4095865038385767ba06b525f4e891f34275078d814d06136b7`
    Neither `FB Gulbene` nor `Gulbene` establishes1500 seats. Moreover source says
    the2nd league is `trešā stiprākā ... līga` (third strongest), while protected
    QA calls it `otrais līmenis` (second level). Judge flags missing capacity
    but marks history pass, missing this ordinal distinction. Existing withheld
    state is safe; reason/history assessment needs strengthening.

16. **Auslas lake, LT: source-supported unchanged keep.**
    `c17a6d142324258af03e2a64b80e3ef78cfc20d7dfd970f202efe93e6744bcab`
    Matching article supports8km west of Zarasai,3.8km/1.02km dimensions,
    153.6m altitude,9m depth,40m strait,3islands, Avilė inflow/Nikajus outflow,
    and500percent annual turnover. Correctly retains unusual source direction
    wording rather than silently substituting new geography. Source fidelity
    is good; no independent surveying or external truth guarantee.

17. **Trakai, LT: challenge repaired keep; unsupported added specificity.**
    `e77678f03d4862c5382fd0ce428d1f15605d03b0b534db71493aa5ec890293f9`
    No articles. Repair changes municipality, introduces a second Trakai and
    asserts4km east of Švenčionys while retaining110–120km for the famous place.
    Disambiguating is useful in principle, but these distances/direction/place
    claims are not verified by any supplied material. Re-audit says "based on
    geographical data" although no such data is attached. Do not label all
    added facts false; label the repair unsupported and require actual evidence.

18. **Žiemgala, LT: grounded repaired keep.**
    `f06cf547c2c93b7d93e2dda3f6e1ce51f808a6076ad6631210893e9d35ad79b4`
    Correct article supports historical region spanning Latvia/Lithuania,
    four-or-five regional classification, old tribal extent and Jelgava/Joniškis
    roles. Repair removes unsupported Bērze prominence and narrow river framing,
    and explicitly distinguishes historical territory. All added substantive
    facts are traceable to article. Minor wording is not a blocker. Good
    source-grounded repair; not an automatic publication decision.

19. **Plokščiai church, LT: source-supported unchanged keep.**
    `fff21bda8014902571bf5f4f1f1cdf9ed4589072ce7bbc158f67f7c1a8dd80fb`
    Matching church article explicitly names Jeronimas Krišpinas-Kiršenšteinas
    and1670. Other churches with similar Marian names are irrelevant. Answer
    does not mix them or import disputed dates for a later church.

20. **Tuči, LV: challenge unchanged keep.**
    `ffff781dfce3dc55b151cb321c0840f728495863b275786b3b3781130263c0b6`
    No articles. Final78people in1897 repeats the earlier assistant, not evidence.
    Judge invokes "historical census records" not attached to the request.
    Earlier255km/11households/Brolišu claims and speculative quiet rural life
    are not verified. Conditional speculation is not necessarily false, but
    it cannot make evidence sufficient. Require the correct locality source.

## Reporting and Next Action

The existing CPU-only operational report command is:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.baltic_qa31_article_consumer calibration-report --root data/dfm13/baltic/qa31-article-diagnostic20-consumer-v3
```

It writes only the operational report under the diagnostic root and does not
launch inference. It was **not run by this review** to leave originals untouched.
Current code would mark `calibration_complete=false` because blocked_technical
is not a completion state, despite20 terminal dispatch outcomes; semantic
approval remains false independently. No readiness/approval receipt is written.

Recommended owner action: retain holds; address whole-history checking and
evidence sufficiency before approval. Reject/verify missing and unrelated
references without inferring factual falsity; do not repair them from model
memory. Keep a supported final-only repair path such as Žiemgala. Treat the
single invalid review as an evidence-contract failure, not recoverable transport.
