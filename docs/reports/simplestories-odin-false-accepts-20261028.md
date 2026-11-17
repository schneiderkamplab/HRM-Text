# Odin accepted-text spot-check, 2026-10-28

## Method

Reviewed 20 texts accepted by Odin for BOTH language and coherence. One text
per language/task cell (DA/EN/HI/JA x creative/QA/revision/rewrite/summary),
selected with seed 20261028. Within each cell, sample a parent conversation
uniformly, then one accepted assistant response. This avoids overweighting
parents with more revisions. Selection pools combine the v2 and v3 samples.

Reproduce with `python -m scripts.sample_odin_accepted_review`. Exact text,
parent IDs and turn indexes are in
`data/dfm16/expansion-v1/stories/quality-v3-qwen/odin-accepted-manual-sample.jsonl`.
No new API calls. This is assistant linguistic inspection, not native-speaker
certification. No source passages or user instructions were supplied in this
review, so source fidelity and instruction compliance are deliberately ungraded.

## Findings

| Cell | Assessment of the accepted prose |
|---|---|
| DA creative | Clear missed language error: "korridorerne uhyggelige stille" should use adverb "uhyggeligt stille". |
| DA QA | No clear standalone prose defect found; source grounding unassessed. |
| DA revision | Awkward "mellem duften" imagery; stylistic concern, not counted as a clear material failure. |
| DA rewrite | Minor missed spelling error: "kæmpe stor" instead of "kæmpestor". |
| DA summary | No clear standalone prose defect found; source grounding unassessed. |
| EN creative | Coherent fictional rescue story; no clear prose defect found. |
| EN QA | Understandable cause/effect explanation; source grounding unassessed. |
| EN revision | Coherent magical-mirror story; prior edit compliance unassessed. |
| EN rewrite | Coherent virtual-world conflict; preservation of original events unassessed. |
| EN summary | Fluent summary; source grounding unassessed. |
| HI creative | Understandable magical-library story; no clear material prose defect found. |
| HI QA | Odd word choice "गड़गड़ाहट" for bees (rumbling rather than buzzing); lexical concern, kept separate from clear failures. |
| HI revision | Coherent discovery narrative; no clear material prose defect found. |
| HI rewrite | Understandable leadership narrative; some awkward phrasing, not counted as a clear material failure. |
| HI summary | Understandable confrontation summary; source grounding unassessed. |
| JA creative | Coherent story about an extinct butterfly; no clear material prose defect found. |
| JA QA | Fluent short answer; source grounding unassessed. |
| JA revision | Coherent vignette with comic ending; requested revision unassessed. |
| JA rewrite | Clear coherence concern: the opening assigns camouflage/foresight to the narrator "in contrast to him", then immediately calls the octopus unmatched at hiding; ending redistributes these skills again. |
| JA summary | Fluent short summary; source grounding unassessed. |

Two clear missed issues in 20 accepted texts, plus one minor spelling issue.
These counts are not an estimate of corpus-wide false acceptance: cells are
equally sampled rather than population weighted, labels are exploratory, and
the sample is small. Also distinguish bad texts among accepted outputs from
the fraction of all genuinely bad texts that a judge accepts; the latter needs
an independently labeled bad-example denominator.

## Implication

Odin catches confirmed defects missed by Mimir, but is not sufficient as the
sole gate with the current broad yes/no questions. Tolerating some false
rejections does not establish low false acceptance. Prioritize recall of real
defects: calibrate against known bad examples and randomly sampled accepts,
include user-supplied source paragraphs as separate prose units, and check
source/answer fidelity and revision compliance in a separate contextual pass.
Keep deterministic instruction checks. No model-specific threshold or production
admission change is made on the basis of this small review.

## Updated API policy

Owner override supersedes adaptive doubling: fixed concurrency **64**, at most
**180 HTTP requests in any rolling 60 seconds**. `--requests-per-minute` can
lower that cap. The gate is at actual HTTP dispatch, not row admission, so GET
preflights and retried POSTs count too. HTTP 429 causes a shared cooldown, not a
concurrency reduction. The default 180 follows the observed request allowance;
the provider's window semantics remain unconfirmed. Other independent clients
sharing the key can still consume the account quota. This limiter is scoped to
this runner and does not change local vLLM audit defaults. No new paid run was
started to implement this policy.
