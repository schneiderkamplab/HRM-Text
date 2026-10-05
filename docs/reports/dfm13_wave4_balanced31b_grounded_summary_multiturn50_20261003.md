# Balanced 31B wave4: all 50 kept grounded/summary/multiturn cases

Date: 2026-10-03. Root:
`data/dfm13/gemma31-balanced-execution-20261003-v2/wave4`.
Scope is every `effective_keep=true` outcome in grounded-instruct,
summary-rewrite and multiturn, sorted by outcome filename. All 50 complete
conversations and their supplied source passages were independently read.
Other families belong to the separate reviewer; Baltic is outside this report.
No GPU work, frozen artifact changes, approvals or admission performed.

This is an agent content review, not native-speaker certification or a fresh
external fact check. Source-faithful medical, historical or technical statements
are not thereby verified as current advice. Prompt quality is part of the
conversation: a correct answer cannot excuse a corrupted generated user turn.

## Result

Blanket production readiness is **not established** by the automated keeps.
Concrete high-priority defects are fabricated institutional policies in Croatian
and Persian library dialogues, unsupported city-specific transport/app rules,
and an assistant promising external document/email work without tools or an
explicit roleplay frame. Short extractions generally preserve their requested
facts, but many generated user turns have avoidable language corruption and
source duplication. Some summaries inherit damaged or unsuitable source claims.

The table is the complete review inventory. `S` means no clear material defect
found, allowing noted minor polish; `R` means a specific localized repair is
needed before treating the conversation as clean data; `H` means hold for source
or scenario redesign rather than accepting the current candidate. These are
recommendations only, not pipeline admissions or mutations. Severity varies:
a misspelled word is not equivalent to fabricated policy.

| Index / ID prefix | Language / family | Disposition | Whole-conversation evidence and remedy |
|---|---|---|---|
| 0 004bea27f649 | be summary | R | `ўзнагародалі`, `ўставілі бюст` need language correction. Summary puts both orders under posthumous award although source explicitly dates only Hero title as posthumous; retain source attribution scope. |
| 1 01cb9acbac42 | hr multiturn | H | Invents ten-item limit, 14-day loan, extensions and daily fee for an unidentified library; speaks as its employee. No fictional frame supplied. Ask which library or explicitly author a hypothetical policy scenario. `prepisati` also wrong for intended enrollment. |
| 2 038a3a350f13 | fa summary | S | Three bullets preserve acquisition share, reported price uncertainty and leadership dates. Source's executive-title wording is itself imperfect; no independent current corporate claims verified here. |
| 3 0a11b9f0e8be | hu summary | S | Two-sentence name summary retains name day, origin and absence from top 100 in two decades. No invented frequency count. |
| 4 126c5820fb72 | fa grounded | S | Birth date, country and four occupations match passage. Does not infer a more specific birthplace from unrelated categories. |
| 5 170422efd189 | hu multiturn | R | First answer asks child to imagine instantaneous travel over any distance, then says finite; later corrects instantaneous-sunlight misconception it helped create. Replace contradictory analogy with consistently finite travel time; minor `tellik` typo. Approximate solar delay not the primary defect. |
| 6 219683ac4630 | fa multiturn | S | Tracks classical to electric, 15-minute practice, jazz then pop/vocals; final equipment retains electric-guitar context. Some phrasing and generalizations can be polished, no decisive state-tracking error found. |
| 7 30e2e9fbc820 | bs multiturn | R | Unsubstantiated 'currently dominant/most effective' framing and categorical motivation benefit need qualification, not invented evidence. `razumljanje` malformed. Follow-up reference to microlearning is otherwise coherent. |
| 8 32be712e8f41 | hr multiturn | S | Correct piano antecedent and consistent practice discussion. 20-40 minutes should read as a suggestion, not universal optimum; low-stakes polish rather than demonstrated material falsehood. |
| 9 36a506448e2d | bs grounded | H | Faithfully repeats source `DL=95,8 * 106`, but exponent formatting is damaged/ambiguous in source. Do not present as a verified usable astronomy formula; repair source representation with provenance first. |
| 10 3a8ed63393c9 | sl grounded | R | Answer's 1921/1930 extraction supported. User starts English `Iz provided source`; remove mixed-language scaffold and duplicated source. |
| 11 45767672d98c | bs multiturn | R | Sensible contextual follow-ups and qualified club pricing. Local language repairs `odrasnoj`, `govornikima`; no need to regenerate the entire scenario. |
| 12 4d0a750fe295 | sq multiturn | R | Coherent adaptable family budgeting, no guaranteed returns. Repair morphology `përcaktonini` and phrasing; do not treat example percentages as a rigid requirement. |
| 13 593ec1c0fe07 | lb grounded | R | Film dates/budget/receipts/Oscars supported, but user corrupts source (`Lützebuerg`, `üm dé`) and answer mixes `kam`, `premiere ginn`. Repair whole conversation, not just correct numbers. |
| 14 597c26fd9234 | lb grounded | S | Lists all nine finalists exactly as source, not just the three winners. Appropriate concise answer. |
| 15 61e5f2e6d499 | fa summary | S | Retains capacity, dates, ten revisions and 91% vote; summary order matches supplied standard-development history. Source-limited, not current standards guidance. |
| 16 6938ecf27499 | hu summary | R | Core literary idea preserved but `megugoráljuk`/`végrejutásra` garble the final explanation. Source says expressions originate in Ars Poetica; 'works made it famous' is looser. Local rewrite needed. |
| 17 6f4abdc34637 | bg grounded | S | Exactly two sentences; filming places/year and three creators source-faithful. Source's unrelated dubbing typo not propagated into answer. |
| 18 6fd68ca4fe45 | be grounded | R | Five entities and 1954-1989 qualifier correctly retained. User `пунктами` needs localized Belarusian repair; source duplication should be removed by the proposed adapter. |
| 19 742ac0a062e9 | sk summary | R | Three child-facing sentences, but adds 'solved very difficult mathematical problems' where source describes research areas/medal. Safer paraphrase: studies difficult problems. Source opening is truncated and lacks the person's name; do not invent it. |
| 20 79f210e75acc | hu summary | R | Capacity and opening date supported. `A lételt` is malformed intended facility noun; capacity phrasing awkward. Preserve historical future tense as source-relative, not verified present stadium status. |
| 21 7c65617a861c | bs grounded | S | Correct one-sentence 1991/287 population extraction. No invented missing ethnic breakdown. |
| 22 80f83f5d7d7b | sk multiturn | R | Sauce/vegetable antecedents and sequence coherent. Repair `cibuliu`, `zmikla`; child-suitability statement should not sound universal across unspecified ages/allergies. No claim of clinical safety verified. |
| 23 894b2b4e1fdb | hr grounded | R | Answer matches five wars and 19 stars as supplied; user `U kojim su ... sudjelovao` grammatically broken and copied source introduces case error. Historical source accuracy not independently certified. |
| 24 8eb473d9f320 | sr multiturn | R | Helpful article progression, but 'infinite flexibility' and unsupported causal history of digital standardization should be qualified as framing, not established facts. Repair `sintizatora` terminology. |
| 25 907e12ee73a2 | sq grounded | H | Source itself corrupts federation to FMN and carries German `Achte` into location; assistant faithfully repeats both. Repair/audit source before reuse; do not infer a new location or federation from this passage. |
| 26 912b3eb6fd50 | sl grounded | R | Membership, location and category-derived 1992 match source. User `dveh povedicev` malformed; correct prompt grammar. |
| 27 97d0fea58ccd | be multiturn | R | Paper density specified in grams without area, categorical glue-stick dismissal, unsupported nonwarping special-glue guarantee, and `тонкі ... леза` agreement. Supply units/qualifications and repair language. |
| 28 9966822e3b8f | sr grounded | R | Correct Calvados answer, but `Извозните текст извoра` is malformed/mixed-script instruction. Clean user turn instead of accepting answer-only quality. |
| 29 9c03350624e7 | sk summary | H | Source-faithful three-bullet herbal uses, but therapeutic claims for liver/gallbladder/wounds remain unverified and are presented as practical benefits. Use explicit source-attributed traditional claims or audited safer source; no medical endorsement from this review. |
| 30 9c7269755bce | hu grounded | R | Correct rowing/lawyer answer; copied user source invents typos `ezüsütérmes`, `nélkülli`, `szüllett`, and `válaszd meg` is wrong task wording. Repair prompt; retain clean pinned source once. |
| 31 a03fd9e655ed | sk grounded | R | Nonprofit/music-industry answer supported. `Odpoveste` in request needs local grammar correction; not a semantic fact failure. |
| 32 a6aa6b1a3719 | sl multiturn | R | Good clarification of course type/location, but `kompleksne poročila`, `urotnimi`, `z tujci` need language repair. Avoid categorical proficiency threshold for drafting contracts. |
| 33 aeb5d25e74c0 | lb multiturn | H | Without explicit roleplay/tools, assistant promises to update project documents and email them tomorrow. Also German intrusions `Technischen`, `Zeitplang`, `Entwicklung`, `Gerne` and malformed deadline word. Reframe as a fictional dialogue or offer an actual draft, not external-work promises. |
| 34 b94a9040f66a | sq summary | R | Alternatives/foundation uncertainty retained, but source 'as appears from an epigram' becomes a fact 'proved' by it. Preserve evidential qualifier. Subject name is absent from source and correctly not fabricated. |
| 35 bef5c80c0044 | bg grounded | S | Exact two Latin expressions and their meanings preserved. Latin quotation is appropriate source content, not language contamination. |
| 36 cc473ca54d22 | be grounded | S | Two-point comparison retains 1960 origin and named Belarus applications without new numerical claims. Source contains merged word; answer avoids it. |
| 37 cc4c40761618 | bs multiturn | H | No city supplied, yet recommends tram routes as best, asserts driver/kiosk sales and free app download. Ask city/system or make hypothetical; `vašenoj` also malformed. Conditional app availability does not justify unconditional free pricing. |
| 38 d413b45721ed | lb grounded | R | River hierarchy answer supported. User mixes `Source`, `sagen`, `lag`; assistant `sengersäits` spelling should be normalized. |
| 39 d806c3568744 | sq summary | S | Single-sentence group/region/artistic activity summary supported. Leadership presented source-relatively; no external verification of current office-holder implied. |
| 40 d9400168cbdf | bg multiturn | R | Blanket superiority of traditional soft-skill instruction is unsupported and overlooks blended approach's own in-person component. 'Systems provide realtime data' also overgeneralized. Qualify by design/integration and outcomes; conversation continuity otherwise intact. |
| 41 dee8cba10ca0 | lb summary | R | Dates/book/three adaptations supported; `donnerunter am bekannten` clear malformed/German-influenced phrasing. Repair rather than dropping historical content. |
| 42 df9f07d36f9c | hr summary | S | Three bullets correctly preserve tier, ten teams, 18 rounds and champion Vir. |
| 43 e4a75198b5be | bg summary | S | Two sentences honor explicitly requested past tense and retain names/popularity areas; tense change here is requested, not a hallucinated historical shift. |
| 44 e51df19a864c | sr grounded | R | Two correct facts and two sentences, but user `два кратких реченица` is incorrect agreement. Repair prompt. |
| 45 e8598806ffcd | bs grounded | R | Facts supported; user requests political views and three works in list form, but political views supplied as prose. Local format repair, not factual rejection. |
| 46 f44529e73368 | bg summary | S | Three source-grounded bullets preserve learning/media/stereotyping explanation. Do not infer a diagnosis or treatment recommendation from this summary. |
| 47 f61e8714c7de | sq multiturn | S | Coherent short email/follow-up coaching, qualified two-day reminder. Minor `i konkret` polish; no external send claim. |
| 48 fa29b62b31bd | bg multiturn | R | Proposed QR poster does not resolve access for older neighbors unable to use online channels, yet promises reach to everyone. Include readable offline essentials or personal contact; avoid categorical environmental superiority. `излишно хабеж` also malformed. |
| 49 fdfa97e5b409 | fa multiturn | H | Invents child's/parent's required IDs, branch eligibility, late-fee documentation and lost-book replacement policy for unidentified library. Ask location/library or explicitly frame policy as hypothetical; do not retain as universal rule. |

## Next actions, not approvals

- Freeze exact candidate hashes with these dispositions before any repair; a
  repaired text needs a new hash and whole-conversation review.
- Treat H source/scenario cases as redesign/clarification, not one-word cleanup.
- Implement any source-echo correction separately from semantic repair; the
  fresh30 report specifies bounds and exact-copy safeguards. Do not loosen the
  student4096 limit or silently remove evidence to improve acceptance counts.
- Many R cases are prompt-only/local language repairs. This does not make all
  failures equally severe and does not justify discarding all short grounded QA.
- Remaining families and both Baltic languages need their assigned independent
  reviews before anyone claims all balanced234 automated keeps were assessed.

Companion `dfm13_wave4_balanced31b_grounded_summary_multiturn50_20261003.json`
records exact IDs, hashes and table classifications. It is a review report only;
the frozen run's pending independent-review queue and admission fields are not
rewritten.
