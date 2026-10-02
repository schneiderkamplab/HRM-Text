---
type: Report
title: DFM13 Search Reviewer Controls
description: Bounded decoder and factual control experiments on saved SearchArena answers.
status: draft
confidence: high
last_updated: 2026-10-01
tags: [dfm13, data, tool-use]
---
# DFM13 Search Reviewer Controls

Parent: [Arena Quality Review](dfm13-arena-quality-review.md).

## Fresh Review Applied And Targeted Retrieval Completed

### Targeted Sixteen-Query Supplement

### Parallel Budget And Recovery

The final high-concurrency paid batch and cached-only recovery are documented
in [Search Parallel Budget Recovery](dfm13-search-parallel-budget-recovery.md).
The total paid ceiling is exhausted at 200; no retry or refund is authorized.

The EOIR cached repair is prepared for independent review in
`data/dfm13/search-eoir-cached-repair-20261001-v2/queue.json` by
`scripts/dfm13_search_eoir_cached_repair.py`. Eight exact offset/hash-bound
selections preserve the purpose/form distinction, Salvadoran categories,
category-specific forum language, substantive standards and exceptions, both
USCIS/court legacy EOIR-40 clauses, and the cached 01/20/25 edition marker.
The last controller observation and final answer are new; original user/history
and native query are unchanged. All observations are from the existing full
cache, not from hidden teacher hints. The answer is explicitly agent-authored,
limited to the supplied NACARA instructions, and not an eligibility determination.
Final-answer-only student rendering fits 4096; no model/paid calls or admission.
Two exact-extraction regression tests pass. V1 remains as an earlier draft;
V2 removes an unsupported copy-versus-original wording choice in the USCIS
exception. Only V2 is the requested review queue. Original answer holds remain.

Subsequent CPU evidence review of the remaining four automated keeps is recorded
in `docs/reports/dfm13_search_targeted16_keeps_review_20261001.json`. These four
versions are now held for incomplete eligibility/context, unsupported legal
status, shifted relative-time framing, or incomplete-list/global-absence claims.
The cached Science source has a February 5 header, omitted by selection; its
two-month forecast cannot silently become a March 18 forecast. Cached USCIS
instructions contain the complete EOIR-40 post-June-1999 exception and scope of
the court-only clause; paragraph ranking selected isolated PDF lines instead.
This is an extraction-context failure, not necessarily missing paid evidence.

Inventory v9 supersedes v8 counts: 114/200 reservations, 97 completed full cached
responses (35,736,321 bytes), 17 unresolved reservations, 75 cached owners,
74 original tasks with candidates. There are 14 manually useful nonheld IDs,
15 automated-keep nonheld IDs and a 17-ID union; zero admitted. This is not a
human-certified success rate. No Search GPU client remains active.

Two separately authored cached-only drafts are prepared in
`data/dfm13/search-targeted-cpu2-20261001/queue.json`: Google Play (1338 student
tokens) and Bluetooth (1320). They preserve all learner history/observations,
remove unsupported workflow/legal-force assertions, disclose source limitations,
and mark final text as agent-authored rather than model-generated. Both await
independent review; their old hash holds remain. Four focused tests passed, with
real student rendering completed. No model or additional paid calls were made.

Completed under PID 2925504, which exited normally with a terminal runtime:
all sixteen queries attempted, campaign 98 -> 114 reservations (cap 200).
Twelve full responses cached; three oversized responses and one HTTP 422 remain
charged unresolved reservations, never refunded/retried. One completed response
had no relevant screened paragraphs. Eleven generation/review jobs finished:
five automated keeps, five needs-verification (missing supporting-page answer
citation), one reject (Llama citation points to DeepSeek). Zero admitted.
`docs/reports/dfm13_search_targeted16_completion_20261001.json` records counts
and a new hash-bound Google Play hold: the answer still recommends an unsupported
VPN/account workflow, and the reviewer accepts it as a logical workaround.
This spot check is not independent certification of the other four keeps.
No other processes changed, and no paid calls followed the sixteen attempts.
Accounting v8 additionally scans nested `generation/records` candidate folders
used by the last-slots and targeted supplement branches; v7 omitted those paths.
The new Google hold is consumed in
`data/dfm13/search-postbatch-accounting-20261001-v8/inventory.json`, including
metadata-only copies. Historical accounting snapshots remain unchanged.

`scripts/dfm13_search_targeted16.py` prepares the isolated root
`data/dfm13/search-targeted16-20261001`. Its sixteen explicit query/case pairs
address QEMU, private-club taxation, EOIR eligibility, dated model specifications,
scientist layoffs, Google Play country requirements, energy-decision research,
Russian mixing research, Cross Creek structure, Ngoc Lang contributions, Meizu
support, installed application sizes, Tarkir card rarity, Lynx camera APIs,
federal Bluetooth guidance and TTS restrictions. Poetry/optional creative
retrieval, private contact discovery, historical prices and the held tariff
retry are excluded. Each query records rationale, original source-as-of date,
source-domain scope and full attempt/cache provenance.

Preparation command: `python -m scripts.dfm13_search_targeted16 prepare`.
Secure parent handoff:
`/home/ucloud/miniforge3/envs/hrm/bin/python -m scripts.dfm13_search_targeted16 run-stdin`.
Write the existing credential plus newline to stdin; no secret argv, echo or
file. The child detaches and reports its PID. No idle credential waiter is
started by preparation. Log: `logs/arena_review/20261001/search-targeted16.log`.

The SQLite reservation transaction enforces the shared 200 ceiling and this
batch's sixteen-query scope. Completed identical query/options cache hits cost
no new reservation; unresolved attempts cannot be retried automatically.
Retrieval finishes before generation/review at maximum eight per existing
endpoint, timeout 600 seconds, no server changes. Exact-domain checks reject
lookalikes; explicit future URL dates are excluded. Date search operators and
undated pages do not prove historical applicability. That limitation is visible
in the learner observation and requires claim-level review. Full responses stay
cached; complete selected paragraphs and the actual student budget precede
generation. Final-answer-only supervision masks controller-authored native
search and observations. Old candidates and hash holds are not overwritten.
No automatic admission. Sixteen focused tests passed, including concurrent
global-cap allocation, cache reuse, unresolved retries, scopes and preparation.

### Paid Cap Superseded By Explicit Authorization

On 2026-10-01 the user raised the total campaign ceiling from 100 to 200.
`scripts/dfm13_search_budget_policy.py` migrated the existing
`data/dfm13/search-jina-paid-campaign-20261001/cache.sqlite` in one SQLite
`BEGIN IMMEDIATE` transaction. All 98 reservations and full cached responses
remain; no refunds/reset. The authoritative `paid_search_policy` row contains
the authorization receipt; `cap-200-authorization.json` is its recoverable
sidecar. Idempotent migration returns the original receipt, not a new count.
Both base and scoped supplement reservations read the cap inside their existing
reservation transaction. Legacy databases without policy retain cap 100.
Scoped query/owner authorization and the nine-query supplement bound remain.

The last-slots client exited before code changes: two terminal outcomes,
Cisco automated keep and botany needs-verification (missing supporting answer
citation). Neither is admitted. Old sealed manifests/pins were not rewritten;
they describe historical code and must not be repinned for resume. New clients
must pin the new budget-policy helper as well as their execution dependencies.
Thirteen focused tests passed, including migration preservation/idempotency,
full-cap cache reuse, and concurrent base/supplement last-slot allocation.
The extra allowance is for targeted missing evidence, not blind expansion.

The fresh-eight receipt
`docs/reports/dfm13_search_fresh_nonheld_blind8_manual_assessment_20261001.json`
is now consumed by the accounting helper: five substantive holds and two
partial-answer cleanup holds are bound to exact candidate hashes, with identical
messages/tools copies also excluded. One supported identification is recorded as
manual support, not admission; its ancillary genre-description caveat remains
in the receipt. No prior hold is cleared.

Inventory v6 supersedes the v5 counts below without overwriting it:
`data/dfm13/search-postbatch-accounting-20261001-v6/inventory.json`.
There are 14 manually useful distinct IDs, 14 automated-keep distinct IDs and a
16-ID union, zero admitted. These overlapping categories include scoped partial
answers and creative tasks, not 16 verified retrieval successes.

Parent supplied the credential through secure stdin to detached PID 2916141.
Both targeted queries completed, caching full responses of 76,459 bytes
(botany) and 379,044 bytes (Cisco). The original campaign now has 98 reservations:
85 completed and 13 still marked reserved; all count toward the 100 ceiling.
`data/dfm13/search-lastslots2-20261001/retrieval-finished.json` records two ready
jobs, no exclusions. Runtime moved to bounded generation/review, one request per
endpoint, no further paid calls permitted. The remaining two slots are not
allocated. Log: `logs/arena_review/20261001/search-lastslots2-stdin.log`.
No scaling, admission, server changes or extra credential files. Ten focused
accounting/last-slots/stdin tests passed. Generation outcomes remain pending at
this checkpoint; cached retrieval success alone is not answer-quality approval.

## Fresh Nonheld Review Packet

`docs/reports/dfm13_search_asof_and_blind8_manual_assessment_20261001.json`
resolves the two as-of draft issues on their exact new bytes, marks the pharmacy
answer as a useful evidence limitation (not a successful price lookup), and adds
Korean-policy historical-evidence and TTS service/condition holds. Both the
`blind_packet` and `repairs` receipt sections are ingested explicitly; recognized
useful assessments do not clear any contrary hold on the same candidate bytes.

Immutable inventory v4 incorporates these dispositions; v5 additionally
propagates holds across metadata-only copies with identical messages/tools:
`data/dfm13/search-postbatch-accounting-20261001-v5/inventory.json`.
The manually useful pool is not an admission list or a count of fully answered
lookups; it includes bounded answers and creative tasks. Existing roots remain.

`scripts/dfm13_search_fresh_blind8.py` creates
`data/dfm13/search-fresh-nonheld-blind8-20261001/queue.json`:
eight nonheld, context-fit candidates with no exact-candidate manual overlap.
Seven task IDs are unseen in recorded prior manual JSON assessments and the
earlier 15-case Markdown assessment. One is a fresh candidate version for the
previously examined DHT-research task; it is not falsely labelled an unseen ID.
The seven new IDs concern Google Play country availability, EOIR-40, LLM-size
comparison, a historical tweet question, planned scientist cuts, vehicle weights,
and song identification. The deterministic selection seed is 2026100108.
No model verdict is included in the blind packets. All receipt/input and packet
hashes are pinned; exact holds and metadata-only held copies are excluded.

The previous packet's overlap is acknowledged, not counted as new independent
review. New receipt/manual support is not human/native certification and no
admission is authorized. The two-query paid launcher PID 2905510 remains healthy
and waiting for its missing protected credential, without inference or new
reservations; the campaign stays 96/100. No tariff retry or wider generation.
Final v5 counts: 13 manually useful distinct candidates, 21 automated-keep
distinct candidates, union 23, zero admitted. Full Search suite: 195 passed;
OKF: zero errors and warnings.

## New-Generation Date Policy And Last Slots

For new production branches the answer date is the original question timestamp
only. Actual retrieval timestamps belong in metadata/provider receipts, not in
a controller `Current retrieval date` cue. Preserve original user text and
source dates. Remove only the recognized controller-added sentence. Source
selection must check claim-specific applicability: later retrospective evidence
can support a dated earlier event, but later current facts do not become earlier
facts. Uncertain applicability is held or explicitly bounded, not inferred from
source authority or a URL. No teacher-only factual hints. The machine-readable
policy is `data/dfm13/search-lastslots2-20261001/date-policy.json`.

The user authorized remaining paid slots for targeted high-likelihood gaps,
still within the original 100-call ceiling. Two planned queries only:

- Cisco IE1000: `site:cisco.com "IE 1000" "data sheet" managed industrial`.
  Require manufacturer-domain and exact-model evidence; do not borrow neighboring
  device specifications or infer historical availability from undated content.
- Botany: `"боярышник" "яблоко" "малина" "многокостянка" ботаника`.
  Seek species classification and distinguish whole fruit versus constituent
  fruitlets; no invented exam key.

`scripts/dfm13_search_lastslots2.py` is prepared under
`data/dfm13/search-lastslots2-20261001`. It reuses the atomic campaign reservation
database, permits no paid retries, caches full responses, filters observations
before generation, and preserves controller-authored search-call provenance.
Only final answers are targets; controller calls and observations are masked.
Student context remains 4096 with 1600 reserved and 1536 output allocation.
At most two candidates, one request per endpoint, no admission or broad scaling.

At preparation the key was absent from the environment and both established
protected credential paths. The detached launcher waits without spending or
inference for the protected credential file; no secret was printed or recovered
from unrelated processes. The remaining two of the four paid slots are
unallocated. The campaign remains 96/100 until actual reservations occur.
The focused three tests cover the global cap including failed reservations,
query scope and manufacturer-host/model filtering.
Detached PID 2905510 is verified `waiting_for_credential`, with
`inference_started=false`. Command:
`python -u -m scripts.dfm13_search_lastslots2 run`; log:
`logs/arena_review/20261001/search-lastslots2.log`. Full Search suite: 191 passed;
OKF: zero errors/warnings. No paid query or new answer is claimed completed.

Superseded operational state: at explicit user request the exact idle waiter
PID 2905510 was terminated after checking its command, starttime and waiting
receipt. `idle-waiter-stopped.json` records this; runtime now says
`stopped_awaiting_secure_stdin_handoff`. No servers or inference were interrupted.
The environment and two established protected provider paths were checked
without printing credentials; no key was available to this process. The parent
conversation's earlier supplied key is not denied or requested again.

Secure parent handoff target (one newline-terminated key on stdin):
`/home/ucloud/miniforge3/envs/hrm/bin/python -m scripts.dfm13_search_lastslots_stdin`.
The wrapper passes the key through an anonymous pipe to a detached child, not
argv, initial child environment, or a secret file. Only PID/log location is
printed. The child sets the provider environment in memory for retrieval and
clears it afterward. Log: `logs/arena_review/20261001/search-lastslots2-stdin.log`.
For an interactive terminal, hidden input can be supplied with:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -c 'import getpass,sys; sys.stdout.write(getpass.getpass("Jina key: ")+"\n")' | /home/ucloud/miniforge3/envs/hrm/bin/python -m scripts.dfm13_search_lastslots_stdin
```

The parent can instead write its existing in-memory credential to this command's
stdin directly. No credential should be put into a command argument or shell
history. Four focused stdin-validation tests pass. Cached review work is not
blocked; no new paid reservations occurred.

## Post-Batch Source And Date Hold

The remaining 44 finished with 20 automated keeps, 3 rejects, 13 holds and
8 technical errors. Independent review of eight purposively selected keeps
found one supported core, two partial syntheses and five substantive holds.
No further scaling is authorized. See the
[source/date diagnosis and bounded repair](../../docs/reports/dfm13_search_source_date_diagnosis_20261001.md)
for exact evidence, commands and limitations.

The tariff answer explicitly substituted October 2026 for an April 2025 question.
The controller exposed both dates; evidence ranking selected later material;
review treated matching source text as sufficient. A three-case new-root trial
replaces only the recognized controller current-retrieval-date sentence, retains
original user text, and puts exact factual passages and their scope in learner
observations. Root `data/dfm13/search-asof-scoped-repair3-20261001`, PID 2899302,
one request per endpoint. No broad rerun, paid retrieval, or admission.
The trial completed: two automated keeps, one held tariff answer. The tariff
answer still misinterprets retrospective evidence and imports later effects;
its new hash is held by `dfm13_search_asof_repair3_hold_20261001.json` under
`docs/reports`. No further automatic trial is queued. The other two require
independent review. Full Search tests passed 188; OKF validation is clean.

New exact-hash holds are enforced in
`data/dfm13/search-postbatch-accounting-20261001-v2/inventory.json`:
10 distinct manually useful context-fit candidates (two creative), 21 distinct
context-fit automated-keep candidates, union 23, zero admitted. These are not
23 certified successful retrieval tasks. Prior versioned evidence remains.
After the three-case trial, immutable accounting snapshot
`data/dfm13/search-postbatch-accounting-20261001-v3/inventory.json` retains the
new tariff hold: 10 manually useful distinct candidates, 23 automated-keep
candidates, union 25, zero admitted. The two additions are pending independent
review, not new certified successes. Paid reservations remain 96/100.

## Remaining Batch Independent Screening

The two cached CPU rewrites in `search-targeted-cpu2-20261001` are independently
reviewed in `docs/reports/dfm13_search_targeted_cpu2_manual_assessment_20261001.json`.
Both are useful scoped answers: Google Play now distinguishes community claims
from historically verified official rules and does not promise a VPN workaround;
Bluetooth identifies US NIST draft leads while asking jurisdiction and avoiding
unsupported binding-law claims. Neither fully completes the original lookup.
CPU renders match 1338/1320 tokens; no new hard hold was found on these bytes,
but no admission or automatic clearance of older holds is authorized.

New last-two-slot retrieval review is pinned in
`docs/reports/dfm13_search_lastslots2_manual_assessment_20261001.json`.
Cisco's new primary-source excerpts materially resolve the product-evidence
gap: IE1000 lightly-managed behavior and the IE2000-5000 families are supported,
with local citation assignments to tidy and no date-specific availability
certification. Botany remains held: the sources classify both apple and
hawthorn as pomes but supply no answer key; the model invents an exam preference
for apple and mislabels raspberry as an infructescence. New retrieval improved
evidence without guaranteeing correct synthesis. Older holds remain unchanged;
no admission is authorized.

Fresh nonheld follow-up receipt:
`docs/reports/dfm13_search_fresh_nonheld_blind8_manual_assessment_20261001.json`.
All eight current candidates were reviewed afresh (seven new IDs and one new
DHT version): one supported identification core, two useful partial answers
needing cleanup/clarification, and five substantive record holds. Principal
defects are historical-date substitution, undocumented Google Play workflows,
and an immigration jurisdiction excerpt promoted into an eligibility summary.
The lyrics identification is useful; the tweet and diesel-comparison answers
retain useful partial information but overstate evidence or leave ambiguity.
All eight CPU re-renders match saved counts, fit 1478-2670 tokens, and retain
the actual generation observations without hidden case-specific caution facts.
No earlier holds are cleared and no admission is authorized. This purposive
sample is not a population-wide error-rate estimate.

Follow-up receipt
`docs/reports/dfm13_search_asof_and_blind8_manual_assessment_20261001.json`
independently resolves the requested Qwen and Polish as-of repairs' prior
scope/date-evidence defects. Their CPU render totals are 2203 and 1573 tokens;
minor wording qualifications remain, and tariff stays explicitly held.
The postbatch blind-eight packet contains five exact-hash repeats, whose prior
receipts were reused rather than counted as new independent reviews. Its three
new cases yield one useful Grodno-price evidence limitation and two holds:
Korean trade analysis imports 2026 evidence into an April 2025 question, and
TTS recommendations overclaim unlimited access while omitting the observed
login condition. Because the packet includes three already-held exact hashes,
it is not a clean sample of the nonheld pool. No admissions are authorized.

The later `search-budgeted-remaining48-20261001` run has an independent
eight-domain sample of automated keeps in
`docs/reports/dfm13_search_remaining48_keeps8_manual_assessment_20261001.json`.
All eight CPU re-renders match saved records and fit 1554-2936 tokens; actual
generation prefixes retain the learner observations exactly after tool-argument
serialization normalization. Generic generation-only constraints introduce no
case-specific facts. Semantic review finds one supported core, two useful but
partial/qualification-needed syntheses, and five substantive record holds.
The clearest failure is an April 2025 tariff question explicitly answered for
October 2026. Other concerns are unsupported classification/specifications,
fan consensus inflation, and benchmarks/proposed benefits substituted for
reception/observed outcomes. These purposively diverse eight are not a random
error-rate estimate, and the receipt authorizes no admissions.

The eight jobs in `search-budgeted-remaining-batch1-20261001-v2` are terminal:
five complete answers and three 512-token incomplete outputs. Independent
assessment is hash-bound in
`docs/reports/dfm13_search_budgeted_batch1_v2_manual_assessment_20261001.json`.
It recommends advancing the remaining 48 as screened, bounded candidate
generation, not admission. SDXL and sermon analysis are broadly useful;
Kasamatsu needs localized citation/feasibility qualification. Waze treats a
2019 parameter as unqualified 2025 guidance and does not establish all-permit
behavior. The Polish domain-dispute answer gets its 2012 year from a
generation-only caution, not retained learner evidence: factual hints must
not disappear with generation-only instructions. Incomplete outputs remain
held; no silent completion, automatic repair admission or ledger changes.

## Budgeted Evidence And Local Attribution Corrections

On 2026-10-01 the independent four-draft assessment
`docs/reports/dfm13_search_cpu_corrections_v3_assessment_20261001.json`
found Newsboat and marketing useful with no material issue. Linguistics and
crossword needed only localized source-attribution corrections. This is agent
review, not human certification or admission. The immutable v3 drafts remain.

`scripts/dfm13_search_cpu_corrections_v4.py` replaces only the linguistics
sentence naming unsupported forum proposals and the crossword closing
attribution to evaluation/planning. It preserves the creative clues and all
other conversation/evidence content. New root:
`data/dfm13/search-heldout-cpu-corrections-20261001-v4`.
The queue binds parent/assessment hashes and new candidate hashes; student
render totals are 1475 and 1175 tokens. Review PID 2872242 uses the unchanged
critic-free reviewer on existing servers, at most one request per endpoint.
Historical holds are not automatically cleared.
Both new hash-bound reviews completed with automated `keep`, no reported
errors or unresolved findings. Linguistics hash:
`c6ed034a43e9da0d93d999781ef41644260a1cbec1c332a4e9e683dab4253763`;
crossword hash:
`bb37302d1cd9a2dfe09deb2fb299bb8dee5809b7385223881cfc5a9e1f6b0735`.
The review process exited; full outcomes and raw requests remain in that root.

The eight-case pilot `scripts/dfm13_search_budgeted_pilot.py` was launched as
PID 2870304 with `run --concurrency-per-server 8 --timeout 600`. Root:
`data/dfm13/search-budgeted-trajectory-pilot8-20261001`; log:
`logs/arena_review/20261001/search-budgeted-pilot8.log`.
It selects complete cached paragraphs before generation, preserves the actual
native search call and original user/date, and records exact cache offsets and
full-content hashes separately. This is an explicitly new cached-evidence
branch, not a fresh paid search or silent truncation of an old trajectory.
The student prompt budget reserves 896 tokens within 4096; only the new final
answer is supervised, with controller tool evidence masked.

All eight jobs terminated: six automated keeps, one needs-verification due to
missing answer citation (US election), and one incomplete generation
(metacognitive coding). Seven completed answers fit 1057-2787 student tokens.
Automated keeps still require independent semantic assessment; none is admitted.
No new paid retrieval occurred: the campaign remains at 96/100 reservations.
Existing servers and training were untouched. The two focused modules have
eight passing CPU tests, including exact-edit isolation and fail-closed anchors.
The complete Search test suite passed 173 tests; OKF validation passed with
zero errors and warnings.

Independent manual assessment of these seven completed pilot answers is in
`docs/reports/dfm13_search_budgeted_pilot8_manual_assessment_20261001.json`.
Four are broadly supported; the battery answer follows its source but retains
a technical-verification caveat. Two need correction or better evidence:
DeepSeek overclaims latestness and conflates Base with post-trained comparisons;
the election excerpts lack results/certification details, so adding a citation
alone is insufficient. Saved actual generation requests contain the same
observations as candidates, without old answers or additional source bodies.
Both v4 attribution fixes are independently resolved for their pinned new
bytes. This bounded agent review does not admit records or clear old holds.

## Reviewer Loop Recovery And Factual Controls

### Remaining-Candidate First Batch

The later independent gate receipt
`docs/reports/dfm13_search_budgeted_batch1_v2_manual_assessment_20261001.json`
authorizes remaining bounded candidate generation, not admission. It identifies
teacher-only factual leakage (the Polish ruling year), legacy Waze scope/date
overclaims, and three genuine 512-token truncations. These supersede any
interpretation that the first batch's automated keeps establish groundedness.

`scripts/dfm13_search_budgeted_remaining.py` removes case-specific teacher
cautions entirely. Only generic evidence, date, variant and attribution rules
are appended to actual teacher requests; original learner history is retained.
The answer limit is 1536, with 1600 student tokens reserved before selecting
complete cached paragraphs, inside 4096 total. Final rendering still fails
closed on overflow or incomplete generation; fragments are not silently repaired.
Remaining root: `data/dfm13/search-budgeted-remaining48-20261001`.
Isolated one-attempt retry root:
`data/dfm13/search-budgeted-truncation-retry3-20261001`.
The retry evidence is explicitly reselected before generation from the same
cached passages to free real answer space, with parent evidence hashes retained.
The runner executes the retry root then remaining root, sharing at most eight
requests per existing endpoint. Source matching and paragraph relevance ranking
are preparation checks, not assertions of factual sufficiency. Existing hard
holds and the three original pilot holds are retained. No paid calls or admission.
Preparation queued 44/48 remaining records; the four pre-existing independent
math/date hard holds were excluded explicitly in `screening.json`. Three
truncation retries were prepared separately. Detached PID 2887416 was launched
with `python -u -m scripts.dfm13_search_budgeted_remaining run`; log:
`logs/arena_review/20261001/search-budgeted-remaining48.log`. Runtime confirms
the retry stage started and the remaining stage is queued behind it, without
concurrent clients exceeding the per-endpoint bound. Full Search tests:
182 passed; OKF: zero errors and warnings.

The independent receipt
`docs/reports/dfm13_search_budgeted_pilot8_manual_assessment_20261001.json`
finds four original pilot answers broadly supported, qualifies battery-source
claims, identifies DeepSeek latestness/Base-versus-post-trained confusion, and
confirms missing election evidence. The two v4 attribution fixes are resolved
for their exact hashes, not admitted. Battery, DeepSeek and election are held
in the new batch's `manual-holds.json`, preserving candidate and receipt hashes.

`scripts/dfm13_search_budgeted_batch1.py` adds generation-only requirements for
dated latestness, exact variants/benchmark settings, qualified source claims,
and clearly labelled creative proposals. First-batch source selection covers
historical Polish names, German-division lesson design, hypothetical Japanese
racecourse amenities, the 2012 Polish domain dispute, SDXL fine-tuning,
Edwards literary analysis, href-file downloads, and Waze Live Map permits.
CPU inspection removed irrelevant racing tactics, literary subscription
navigation, teaching-site boilerplate, and preserved exact short permit syntax.
It does not assert that source selection establishes all answer-level facts.

The first preparation root
`data/dfm13/search-budgeted-remaining-batch1-20261001` was not launched and is
superseded by the screened
`data/dfm13/search-budgeted-remaining-batch1-20261001-v2`.
Launch: `python -u -m scripts.dfm13_search_budgeted_batch1 run`, PID 2881420;
log `logs/arena_review/20261001/search-budgeted-remaining-batch1-v2.log`.
Eight per-endpoint capacity on existing servers, eight jobs total, timeout 600.
Prompts span 861-3146 student tokens with 896 reserved inside 4096; full histories
and cached provenance remain. No paid retrieval, no server changes, no admission.
The remaining 48 are unlaunched pending independent review of these eight and
their own source selection. There is no automatic gate release. Three focused
tests passed; paid reservations remain 96/100.
The full Search suite passed 179 tests and OKF validation was clean. Initial
live verification found four completed reviews (three automated keeps and one
needs-verification) and five saved candidates; these are interim counters, not
manual acceptance. Per-record candidate/request/evidence files are available
for independent inspection as the bounded batch finishes.

### Two-Case Budgeted Retry And Scale Hold

The budgeted pilot's Russian coding answer stopped at exactly 512 generated
tokens with `finish_reason=length`, mid-sentence, not a transport error. The
election answer stopped normally but omitted source URLs and added an
unnecessary certification-date assertion. A single retry per case, retaining
identical cached observations and native history, was launched as PID 2875891:
`python -u -m scripts.dfm13_search_budgeted_retry run`.
Root: `data/dfm13/search-budgeted-retry2-20261001`; log:
`logs/arena_review/20261001/search-budgeted-retry2.log`.
Only the actual generation system request gains case-specific brevity/citation
instructions; the learner messages do not. Output stays capped at 512 tokens,
with the same exact student-context check and unchanged reviewer. No paid calls.
Three focused tests verify instruction isolation and refusal of unrequested IDs.
Both retries completed: Russian coding now has a complete, context-fit answer
and automated keep; election remains needs-verification because it again omitted
the requested citation. The bounded attempt is exhausted; no further automatic
retry or citation insertion is scheduled. Neither result is admitted.

CPU preparation only: `data/dfm13/search-budgeted-remaining-plan-20261001`
contains a source-hashed plan and reconciliation. The original inventory has
68 oversized finals; four later compact CPU drafts account for the difference
from the reported remaining 64. Eight are now in the pilot, leaving 56 for
individual relevance/date checks and exact budget selection. Cached native-call
matches and paragraph availability are recorded, not asserted to be sufficient
evidence. All generation flags are false; there is no bulk launch or watcher.
Manual pilot quality assessment must precede scaling. Paid reservations remain
96/100 and historical holds remain in force.

Terminal update: the critique-first run above finished with two correct rejects
and six adjudication errors. All critiques completed. Several adjudications
emitted long whitespace tails; partial JSON was not admitted. The paired
`data/dfm13/search-json-mode-probe-20261001` used the same saved six-virtue
answer/evidence, a simpler compact prompt, no penalties, and the same 2048-token
output limit. Both modes completed: JSON object used 52 output tokens, JSON
schema 55. Both passed strict CPU validation. This does not isolate schema,
penalty, or prompt as the sole cause of the earlier loops. Exact transmitted
payloads are saved as `actual-request.json`.

`data/dfm13/search-json-object-recovery-20261001` reused that completed control
and made five new adjudication calls. All six parsed and were kept; only four
were correct control outcomes. Combined with the two original successful
rejects, this gives 6/8 correct selected controls. Miller-Rabin and OpenAI release
chronology remained false accepts. This is not a production accuracy estimate.

The math adjudicator acknowledged the supplied composite counterexample but
still accepted the answer's false guarantee for all 32-bit integers. It also
failed to distinguish failure of one three-base set from proof of a minimum of
four bases. The chronology adjudicator falsely described the answer as treating
later releases as future: the unchanged answer actually says GPT-5 is current on
May 5, 2025, and describes May 14 as more recent. These are generation defects
as well as reviewer failures. Corrective generation must separate sufficient
bounds from minimum proofs and bind historical claims to the original question
date. An invented replacement model name is not a fix for missing history.

The bounded critic-free comparison completed in
`data/dfm13/search-critic-free-control-20261001`: 7/8 correct, three rejects and
five keeps, no errors. It removed the prior model critique and explicitly
evaluated false supporting claims, with unchanged answers/pages/CPU checks and
no expected labels in requests. The chronology false accept resolved, but math
still failed. Command: `python -u -m scripts.dfm13_search_critic_free_control`;
PID 2828125 exited. Log: `logs/arena_review/20261001/search-critic-free-control.log`.

A narrower two-case paired factual test completed in
`data/dfm13/search-plain-factual-control-20261001`, PID 2830416, command
`python -u -m scripts.dfm13_search_plain_factual_control`, log
`logs/arena_review/20261001/search-plain-factual-control.log`. The math failure
and good DeepSeek numeric control each receive an unconstrained plaintext
factual critique followed by compact JSON-object adjudication. At most four
calls, one request per endpoint, no new answers or retrieval, no penalty or
token-budget increase. CPU schema/citation validation remains strict. All
independent holds remain; no training admission or production scaling follows
these selected controls. Paid budget remains 96/100.

Terminal result: 1/2 correct, two keeps, no format errors. Both plaintext critic
and compact adjudicator falsely accepted the math answer. The critic expressly
said that agreement with the source made the four-base minimum logically sound
and discounted the verified counterexample because it exceeded the narrower
question range, despite the answer's explicit false broader guarantee. The
DeepSeek positive control passed. Removing structured decoding from critique
therefore did not fix factual reliability. PID 2830416 exited; raw critiques,
actual requests, responses and outcomes remain preserved. No further repeated
prompt experiment is scheduled on these same cases.

The concrete generation-repair requirement is a supported sufficient-bound
answer without an unsupported minimum claim, or an explicit unresolved minimum
where evidence is inadequate; merely repeating the cached source is unsafe.
Existing CPU-authored corrective drafts remain under
`data/dfm13/search-independent-hold-corrections-20261001/ledger.json` and are not
certified complete answers. Production needs a gate that respects demonstrated
counterexamples, plus held-out factual controls beyond these repeatedly tested
examples. Same-model critique/adjudication alone has not supplied that gate.

Verification: all 134 Search tests passed; OKF validation passed with zero
errors/warnings. No additional paid retrieval, server changes, or admission.

## Cached Defect Repairs And Heldout Work

The user requested moving beyond repeated controls. Eight report-directed
cache-only repairs ran under `data/dfm13/search-cached-defect-repairs-20261001`,
command `python -u -m scripts.dfm13_search_cached_repairs run
--concurrency-per-server 8 --timeout 600`, PID 2837767 (completed), log
`logs/arena_review/20261001/search-cached-defect-repairs.log`. All native search
queries matched saved paid responses; exact excerpt offsets/full-content hashes
and raw parsed cache snapshots were preserved. Correction hints were supplied
only to generation, not injected into learner user messages. Repaired candidates
target only the new final answer, not the previously generated search call.

Terminal: one automated keep and seven needs-verification, zero transport/format
errors. Six NV answers omitted citations; the logo answer linked image assets
rather than supporting observed pages. This is NOT seven merely mechanical
false holds. Mythic enumeration and restaurant price/exclusion evidence were
explicitly insufficient. Other outputs retained temporal or source-quality
defects. Independent inspection withheld the sole keep (Microsoft), which still
cited a July 2026 AI-investment report for an April 2025 question. The raw model
failed to identify several defects even when citation checks prevented a keep.
No extra paid queries were justified as likely to repair these specific gaps.

Two explicitly coding-agent-authored drafts were then prepared from exact cached
article passages, not presented as new teacher generations:

- Microsoft: remove later AI-investment explanations; distinguish reported cuts
  from a demonstrated motive and from elimination of the entire unit.
- Liverpool: explain early-season tactical clarity and collective work-rate from
  the club's September 10, 2024 Alisson interview; explicitly limit the account
  rather than using later transfers, tragedy, title or final scoring totals.

Both received automated keeps in
`data/dfm13/search-source-checked-drafts-20261001`. A final provenance check found
the Liverpool excerpt stopped before its Salah/Diaz supporting paragraph. The
exact missing cached paragraph was appended, answer unchanged, and one affected
review repeated in `data/dfm13/search-source-checked-drafts-20261001-v2`; it kept
again. The earlier insufficient-evidence snapshot remains immutable. Latest
100-ID ledger is that v2 root's `campaign-ledger.json`: the two drafts remain
pending independent manual review, six other repair cases independently held,
and all four earlier hard holds override model keeps. No automatic admission.
Commands: `python -u -m scripts.dfm13_search_source_checked_drafts` (PID 2842476)
and `python -u -m scripts.dfm13_search_liverpool_excerpt_completion` (PID 2844434),
both completed. Logs use corresponding hyphenated names under
`logs/arena_review/20261001/`.

### Blind Packet Provenance

The authoritative eight-case packet for Boole is
`data/dfm13/search-manual-heldout-20261001-v2/queue.json`, built by
`python -m scripts.dfm13_search_manual_packet`. It supersedes the first packet
under the repair root: the old reviewer inventory combined newer answer text
with older candidate conversations. V2 reads exact saved candidate files and
derives its answer AND evidence from their actual messages, with source hashes.
Missing candidate files use the explicitly identified original saved candidate,
never invented history. Tests enforce answer/conversation equality and refuse
URL-only evidence. Original outputs were not overwritten.

The eight cases cover Newsboat, language inflection, Portuguese marketing ideas,
German industrial switches, Cross Creek chronology, SDXL diversity, Indonesian
account naming, and a Spanish occupational-safety crossword. They are disjoint
from the recent repair/control sets, but not globally unseen by earlier model
reviews. Packets contain no model verdict or expected label; manual review is
pending, not fabricated certification.

An unchanged critic-free review of those exact packets completed under
`data/dfm13/search-heldout-cached-review-20261001`, PID 2846291, command
`python -u -m scripts.dfm13_search_heldout_cached_review`, log
`logs/arena_review/20261001/search-heldout-cached-review.log`. Eight bounded calls,
one per existing endpoint, no new generation, retrieval, prompt variant or
manual-review input. Paid usage stays 96/100; four slots remain unspent. No
production scale, server intervention, upload or training admission.

Terminal heldout results: four automated keeps (marketing ideas, language
inflection, Newsboat, Cisco switches), four needs-verification (crossword,
Indonesian account naming, Cross Creek chronology, SDXL diversity), zero errors.
The latter comprise two missing answer citations and two unobserved source URLs.
Raw model findings were empty in all eight cases: four citation-clear keeps
must not be mistaken for independent factual certification. The outcome field
`essential_evidence_sufficient=true` in this review-only wrapper is a controller
input, NOT a separately established evidence-sufficiency judgment. Boole's
blind assessment remains pending and should precede comparison with these
model dispositions. PID 2846291 exited.

The final source-checked v2 ledger covers 100 unique samples: 32 older automated
keep candidates (not admitted), two source-checked drafts pending manual review,
six independently held repairs, four original hard holds, and 56 without a
selected verified candidate. The latest eight review-only outcomes are separate
and do not auto-promote ledger rows. All four original hard holds have
`selected=null`, including the verified Miller-Rabin counterexample. The known
defective Microsoft automated keep was removed before recording its separate
source-checked draft. Paid cache remains 83 done plus 13 reserved/failed, total
96 charged slots; no paid requests were made during this turn. Full Search
suite: 148 tests passed. OKF validation: zero errors/warnings.

## CPU Training Contract And Independent Holds

Boole's completed blind assessment is
`docs/reports/dfm13_search_heldout8_receipt_20261001.json`: all eight require
correction or verification, not eight proven wholly false answers. The four
automated keeps above do not override it. Specific findings include later trend
or catalogue framing, unsupported debugging advice, speculative linguistic
causation, blocked pages, unobserved citations and invented book authorship.

`python -m scripts.dfm13_search_training_contract` produced
`data/dfm13/search-training-contract-20261001/{contract,inventory,holds}.json`.
This is CPU-only metadata, not accepted training data. It pins the student
Gemma4 tokenizer/template from `data/sampled_dfm11/metadata.json`, actual
`scripts/tokenize_chat_template.py`, `dataset_new.py`, candidate files and
independent-review receipt. Native schemas are exact search/open_page contracts;
unknown schemas, malformed arguments (including duplicate keys and NaN), orphan
responses and changed original user prompts fail closed. No external schema
references are fetched.

Important masking finding: the generic tokenizer reads singular
`target_message_index`, NOT a plural list. The contract expands each explicitly
approved index into a separate student view with full native messages/tools and
the singular selector. Prior assistant calls and returned evidence stay masked
when only a repaired final answer is targeted. Labels follow V1Dataset's actual
shift: the last prompt token predicts the first target token. No tool flattening,
stringified call substitution, history truncation or shared-tokenizer edits.
Full source/audit/provenance metadata belongs outside student columns. Existing
controller system messages remain preserved and flagged for policy review;
there is no silent removal of date context or injected replacement system text.

`holds.json` resolves the receipt's unique ID prefixes against its hash-pinned
queue, then binds every finding to exact candidate-content and, where available,
candidate-file hashes. These holds override even an admission-shaped receipt.
Unreviewed revisions have distinct hashes and require new independent approval;
an old keep never transfers. The helper `require_admission` also requires exact
candidate/target binding and positive independent-review, provenance and mask
receipts with no unresolved findings. No exporter CLI or accepted output was
invoked; admitted rows and training files written are both zero.

Snapshot counts across the original 100 tasks:

- 75 distinct owners have successful cached searches; 74 have saved candidates.
- 74 candidates passed native structural checks, but only six complete final
  answers fit the actual 4096-token student context without truncation.
- 61 selected native-call targets fit; they are NOT 61 approved retrieval tasks.
- 53 candidates passed this strict byte/excerpt provenance check. Remaining
  binding/excerpt representations require reconciliation, not a conclusion that
  all their content was fabricated. Byte identity also does not make a security
  challenge page substantive evidence or certify source factual quality.
- No exact selected-row duplicates; per-target prefix dedup found 135 unique
  targets out of 135. `scripts/dfm13_search_target_dedup.py` ignores later unused
  messages and normalizes call IDs, while preserving prompts/tools/target text.

### Concrete CPU Corrections

The authoritative new draft queue is
`data/dfm13/search-heldout-cpu-corrections-20261001-v3/queue.json`, prepared with
`python -m scripts.dfm13_search_cpu_corrections_v3`. Four individually authored
corrections address Boole's actual findings, without new model/paid calls:

| Case | Correction | Full student tokens |
| --- | --- | --- |
| Newsboat | Distinguish bounded-wait diagnosis from slow-download tolerance; remove unsupported terminal-debug claim; cite exact documented option rows. | 1748 |
| Linguistic inflection | Preserve the non-universal premise and explicit uncertainty/disagreement; do not assert complexity compensation as established. | 1494 |
| Portuguese marketing | Five concrete creative ideas without claiming 2026 trends were current in March 2025. | 1801 |
| Spanish crossword | Ten more specific thematic terms, explicit imagined textbook scope, citation to actually delivered FOL material. | 1178 |

All four retain actual native search calls, exact cached evidence windows and
final-answer-only targets. All have new-candidate review pending; original hash
holds remain unchanged. The first CPU preparation stopped on an exact heading
anchor mismatch and is explicitly blocked. V2 had a 4383-token Newsboat draft;
V3 selects complete relevant table rows rather than neighboring table material,
preserving the complete target and native history. No silent token truncation.

`readiness-summary.json` in the training-contract root distinguishes counts:
after these four corrections there are ten context-fitting representations for
distinct tasks, not ten approved successes. Five are potential source-based
answers still needing quality/provenance review (including the unresolved chess
comparison), two are creative tasks with optional retrieval, two are inability
answers, and one rests on blocked pages. Sixty-four other saved candidates still
exceed the student window; 26 tasks have no saved candidate. This does not certify
a whole-campaign substantive-answer count. There are zero admitted targets.
Paid usage remains 96/100; no GPU calls or prompt tuning in this CPU work.

Final verification: 165 Search tests passed, including the real student Gemma4
native-call/tool-response render and final-answer label-mask check; OKF passed
with zero errors/warnings. CPU preparation is complete; no background client was
launched during this work. The four corrected draft hashes await independent
review, and the other four heldout evidence gaps remain held.
