# SearchArena Followup2: Independent CPU Assessment

Date: 2026-10-01. Agent-authored assessment of saved evidence, not externally
verified gold. No model calls, new web retrieval, code changes or campaign
mutations. Only this report was written.

## Scope and Counts

Root: `data/dfm13/search-calibration-100-20261001-followup2`.
`jobs.json` SHA256:
`55add48db592c7edecdd0ed9b0ff691481b7e21a13d8ab533fa12d276a7ed2d9`.
The root contains 74 outcomes: **20 keep, 40 needs_verification, 10 reject,
4 error**. `dispositions.json` is empty; counts here come from record outcomes.
This is the 74-case followup subset, not the original 100 or a population sample.

Inspected **15 distinct records**: all 10 rejects, the first two keep and first
two needs_verification records by lexicographically sorted record ID, plus the
Russian mixing-source needs_verification case encountered during initial
inspection. Compared original prompt/date, candidate answer, saved tool evidence
and review. Relevant saved excerpts were inspected, not every full upstream page.
IDs below are unique prefixes of record directory names in this root.

Among the 10 rejects: **1 clear false rejection, 8 with independently identifiable
trajectory defects, and 1 unsupported rejection rationale whose target still
needs substantive checking**. A real defect does not establish that `reject`
rather than `repair` is the correct disposition. Several explanations are wrong
even when withholding the answer is appropriate. Do not extrapolate these counts.

## All Ten Rejections

| Record ID prefix | Independent classification | Concrete evidence and action |
| --- | --- | --- |
| `0cfb74ac0aafb756` | True temporal defect | Original date is 2025-03-27. Answer presents completed 2024-25 league results and final goal counts as already known. Saved evidence itself dates the title event to April 27. Reject/repair the as-of-date answer. The reviewer should not call later retrieved material "simulated" merely because it postdates the original question. |
| `12490c9672e0c607` | True grounding defect; bounded repair plausible | Microsoft-layoff answer cites LinkedIn for AI infrastructure/automation/resource reallocation, but the actual supplied LinkedIn excerpt contains related-content/navigation material, not that claim. The disclaimer that this is broader context does not repair a non-supporting citation. Remove that bullet or retrieve relevant support; the other bullets are not thereby disproved. |
| `25bdd9ac2ec6eca6` | Mixed rationale, real support/task-fit problems | GRIN and Nace image URLs containing `2026/06` occur literally in retrieved text. Calling them invented or impossible at the 2026 retrieval date is wrong. Other named logo-page URLs are absent from the supplied results, and the answer supplies links rather than showing logos. The prompt asks to show logos with URLs. Repair unsupported entries and presentation; do not require official-company-only sources, which the user did not request. |
| `42c1b060f2f8dc97` | True temporal defect | Answer begins "As of April 15, 2025" yet lists November 2025 and July 2026 events as current tariff status. This is a direct internal/as-of contradiction. Later cached sources can be genuine but cannot establish the earlier state. No present-day legal/trade conclusion is being independently certified here. |
| `4f8af9d116f97fa0` | True unsupported-certainty/completeness defect; repair preferred | User asks for all mythics. Answer limits its list but claims eight names are explicitly confirmed as mythic rares. CoolStuffInc labels several cards; TCGplayer excerpt lists Ugin as a product without rarity and repeats Sarkhan image-alt text even for booster products. This does not establish the claimed rarity evidence. Reviewer contradicts itself about some CoolStuffInc cards, but its narrower TCGplayer support objection is valid. Do not infer a card's actual rarity from this review. Answer also refers to a "previous answer" absent from the learner conversation. |
| `74f0b1aaf4f4e102` | Clear false rejection | Takayama answer follows the saved source's "Access to Takayama Old Town" section, including address and station directions. Reviewer repeatedly acknowledges support, then explicitly says it will change to acceptance, while the structured verdict remains `reject` and unsupported claims are empty. Its hypothesis that the address must be an inn's is not evidence. Keep is defensible on this record. |
| `a1f76a3aee559da3` | True temporal defect, but reviewer argues the wrong issue | Original question is 2025-03-26 and says "earlier this week". Answer uses September 2026 prices. That is decisive. Negative monthly returns do NOT disprove a slight weekly recovery; the reviewer incorrectly treats the horizons as contradictory. The saved CNBC excerpt actually contains +0.44% five-day return. Repair date binding, not the general possibility of a short-term recovery. |
| `b528d9372edd86da` | True constraint/grounding defect | User explicitly requires below TWD200 and exclusion from the 2024 list, with inclusion years. Answer admits prices are absent, then infers the budget from Bib Gourmand status; supplied evidence describes a much broader TWD1000 three-course criterion. It includes an explicitly uncertain 2024-exclusion entry. Reviewer need not invent current restaurant prices to establish those defects. Several years ARE supplied, so its blanket missing-year complaint is overstated. |
| `ceffc54d13be026e` | True evidence deficit; reviewer medical correction not established | DHT-research answer adds clascoterone, PP405 and JAK/antibody discussion absent from the delivered pages, and has no answer citations. Those are concrete grounding gaps under this trajectory contract. Reviewer cannot establish that a drug is NOT being researched for hair loss merely by noting another approved indication. Saved support for the precise 2.1x figure is an unsourced commercial-page assertion, not a study record. Hold for evidence-quality/date checks; this report does not adjudicate clinical efficacy or indications. |
| `e19e0b36aca7eb8` | Unsupported rejection rationale; target not certified | Bluetooth reviewer says the answer is helpful, accurate and responsive, lists supporting evidence, and gives no unsupported claims, yet emits `reject`. That verdict is not justified by its reason. However, the answer cites an rctest page absent from the candidate's delivered search results and makes broad regulatory/exhaustiveness claims from commercial summaries. A proper source-based legal review is still needed; do not auto-promote this to keep just by flipping the verdict. |

## Selected Keep and Needs-Verification Cases

| Record ID prefix / outcome | Independent finding |
| --- | --- |
| `06cd049fcfe5677` / keep | Clear date-policy miss. Original prompt is 2025-05-09; answer discusses 2026 political tensions using a Verasight report published February 5, 2026 from December 2025 polling. It appropriately avoids predicting a precise outbreak, but the reviewer accepts later evidence as "current" without acknowledging the historical anchor. This is a false accept under the recorded date contract, not a claim that the later statistics themselves are false. |
| `0bdd931b4d9ce44` / keep | Broadly responsive Spanish battery-history summary supported by the delivered secondary sources. No decisive contradiction established by this bounded inspection. Historical-model/date conflation and categorical technology claims would benefit from specialist checking; this is not independent technical certification merely because the reviewer says all claims are supported. |
| `020d55a268a6b53` / needs_verification | Mechanical false hold for citation identity. The validator treats trailing `]` in `[https://lib.pravmir.ru/library/readbook/1118]` as part of the URL. Saved source actually contains "Slovo 38" and the requested six-item passage. The original reviewer says keep. Correct bracket parsing; no new search is needed to resolve this reported failure. |
| `032d2d0cdd945fa` / needs_verification | Not safe to promote after URL repair. Original reviewer says keep, but the answer asserts four Miller-Rabin bases 2,3,5,7 cover all 32-bit integers. A direct CPU counterexample is 3215031751 = 151*751*28351 < 2^32, which passes all four strong tests despite being composite. This disproves that supporting assertion; it does not alone settle the requested minimum below 10^9. Also, failure of one three-base choice does not prove all three-base choices insufficient. The final URL hold masks a real reasoning/correctness issue. |
| `b6dacbacc733ecc` / needs_verification | Reported URL mismatch is artificial: Markdown displays a Cyrillic URL but the actual link destination is its percent-encoded form, matching retrieved evidence. Parse link targets rather than treating display text as a separate unsupported citation. Nevertheless, answer substitutes search suggestions for the requested MHD bibliography and does not establish all full texts are accessible without registration. Fixing URL validation does not prove full task completion. |

The four-base counterexample was checked with local integer factorization
multiplication and modular exponentiation, not a model or network call. No
external medical, legal, financial or technical factual certification is claimed.

## Priority Fixes

1. **Bind time to the original task, not the retrieval date.** For relative-date
   questions, require evidence for the historical period or a clear inability to
   establish it. Do not turn later source publication into a claim the source is
   fabricated. Three rejected trajectories and one sampled keep show this issue.
2. **Handle verdict/reason contradictions explicitly.** Takayama and Bluetooth
   demonstrate incompatible final fields. Route contradictions to a small
   second-pass decision or manual queue; never silently accept from flattering
   prose or reject because the first JSON field says so.
3. **Fix citation parsing narrowly.** Strip surrounding Markdown delimiters;
   distinguish link destinations from labels; handle equivalent Unicode and
   percent-encoded paths without erasing meaningful query/path distinctions.
   This resolves two sampled artificial holds, not the other content issues.
4. **Improve evidence selection before answer regeneration.** TF-IDF windows
   select navigation/related links for the Microsoft example, and product image
   alt text is mistaken for card metadata. Prefer relevant article content,
   structured facts and accessible primary records. Preserve all existing raw
   evidence and offsets; do not invent missing passages.
5. **Check constraints and support before stylistic approval.** Restaurant budgets,
   complete enumerations, measured research claims and mathematical minima need
   specific evidence. Source agreement alone is not truth certification, and
   subjective inference is not automatically hallucination.
6. **Use bounded repairs, then re-audit.** Several rejects need deletion of one
   unsupported bullet or a date correction, not wholesale regeneration. Preserve
   original candidate/review lineage; no repaired answer becomes training-ready
   merely because this report identifies a repair path.

These findings support targeted pipeline/reviewer corrections, not a claim that
all 40 needs-verification outcomes are false holds or all 20 keeps are sound.
