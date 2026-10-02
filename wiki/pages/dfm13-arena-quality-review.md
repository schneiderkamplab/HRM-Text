---
type: Report
title: DFM13 Arena Candidate Quality And Context Review
description: Manual preferred-response samples and structural evidence for SearchArena and RepoChat integration.
status: draft
confidence: high
last_updated: 2026-10-01
tags: [dfm13, data, preferences, tool-use]
---
# DFM13 Arena Candidate Quality And Context Review

## Preferred-Response Audit Calibration (2026-10-01)

Completed the separately sealed 1000-example preferred-response calibration at
`logs/arena_audit/20261001-calibration1000-v1`: 883 validated responses (659 keep,
119 repair, 105 reject) and 117 invalid responses. The 129-case diagnostic
follow-up at `logs/arena_audit/20261001-followup129-v3` recovered 53 old invalids,
but retained 64 invalids and made one previously valid control invalid. Five
false-accept controls persisted; this is not a calibrated automatic admission
gate. No bulk run, export change or training admission followed.

Assistant spot-check reports: `calibration-review.md` in the baseline root and
`followup-review.md` in the follow-up root. These are not human/native gold or
corpus accuracy estimates. CPU-only `quote-index-proposals.json` records exact,
uniquely matching message-index proposals: 15 baseline and 13 follow-up responses
would pass the original validator after index-only correction. These per-run
counts may overlap; proposals remain unapplied and do not certify semantics.
Raw outcomes and seals remain unchanged. Focused tests: 29 passed across audit,
follow-up and quote-diagnostic suites. No further GPU requests were launched.

See [DFM13 plan](/pages/dfm13-plan.md). This review does not approve new sources
or change the running training mixture.

Detailed manual findings: repository file
`docs/reports/arena_candidates_review_20261001.md`; complete 15 sampled
conversations: `logs/arena_review/20261001/quality_samples.jsonl`.
Reproduction scripts: `scripts/review_dfm13_arena_candidates.py` and
`scripts/inspect_arena_tool_context.py`.

## Fresh RepoChat Calibration (2026-10-01)

The user authorized 100 fresh repository-tool trajectories, superseding the
earlier proposal-only status for this calibration, not production admission.
Implementation: `scripts/dfm13_repochat_calibration.py`; tests:
`tests/test_dfm13_repochat_calibration.py` (17 CPU tests, including an actual
local HTTP tool-call/result roundtrip, independent review, and receipt resume).
Root: `data/dfm13/repochat-calibration-100-20261001-v1`.

Selection uses explicit preferred sides, extracts only the first `[USER QUERY]`,
rejects redacted/ambiguous queries, and deduplicates repository/query pairs.
No historical assistant answer or retrieved context is sent to the teacher.
Deterministic repository-breadth-first reserves replace inaccessible or oversized
snapshots, recording exclusions in `preparation.json`. This availability filter
is selection bias, not a quality finding. Repositories are pinned to current
public HEAD, not represented as the historical battle revision. Pin receipts
retain the public Git ref advertisement hash and archive/file hashes.

Snapshot preparation executes no Git/repository code and sends no credentials.
Only fixed public GitHub hosts are fetched; redirects and proxy inheritance are
disabled. Downloads are capped at 128 MiB, expanded regular-file bytes at 1 GiB,
members at 100000, and individual readable UTF-8 files at 1 MiB. Links/devices,
traversal, sensitive filenames, and recognizable private-key/token content are
not exposed. This is conservative filtering, not a complete secret scanner.
Original license files remain in snapshots; no new repository license is inferred.

The only teacher tools are bounded `list_files`, literal `search_repository`,
and numbered `read_file`. Native OpenAI function definitions, assistant calls,
tool IDs/results, raw responses, and final messages are retained. No shell,
code execution, arbitrary network access, or credential tools exist. A fresh
independent review context evaluates correctness/grounding/relevance/safety;
it is same-model review, not human approval. Structural failures remain distinct
from reviewed quality rejection, and every outcome has `admission=false`.

Parent confirmed all eight shared servers ready and tested a native function
roundtrip on port 8800. Model alias `dfm13-gemma4`, context 32768, native Gemma4
tool/reasoning parsers; requests set `enable_thinking=false`. No server changes
are owned by this script. Preparation and rollout commands:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/dfm13_repochat_calibration.py prepare
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/dfm13_repochat_calibration.py run --authorized --model dfm13-gemma4 --concurrency 16 --endpoints http://localhost:8800/v1,http://localhost:8801/v1,http://localhost:8802/v1,http://localhost:8803/v1,http://localhost:8804/v1,http://localhost:8805/v1,http://localhost:8806/v1,http://localhost:8807/v1
```

`ready.json` binds selection, snapshot receipts, and implementation. Run config
is pinned, controller uses an exclusive flock, and raw HTTP receipts are bound
to request hashes. Resume does not resample completed/rejected cases. Summary
counts are written only after all selected cases become terminal; failure does
not imply 100 successful trajectories. Preparation completed with 100 pinned
tasks, 16 inaccessible/oversized repository exclusions, and four additional
unsafe or unrelated task exclusions in `eligibility-exclusions/`. The latter
were found during prompt inspection; eligibility filtering is not a complete
safety classifier. All selected tasks are repository-breadth-first replacements
from the original deterministic reserve, not replacements for model failures.
Detached client PID `2692800` launched after parent authorization; exact start
ticks and command are in `launch.json`, with output in `runner.log`. Actual
native tool calls/results and independent reviews were persisted. The client
has exited and all 100 baseline trajectories are terminal: 59 reviewer passes,
2 reviewer rejections, 25 nonempty stopped answers without retrieved evidence,
1 empty stopped completion, and 13 tool-turn-budget failures. There were no
length finishes or transport failures. All 423 native calls have matching tool
results. `assessment.json` records per-case classifications and verified hashes;
`quality-assessment.md` under the calibration root gives assessed examples.

Reviewer passes are not quality acceptance: a deterministic random eight-pass
spot-check found three concrete grounding/completeness concerns (DXVK coverage
claims, Festival's supposedly exhaustive formats list, and an unverified signed
display-type concern). A separate parent-identified RTree example has an empty
Swift insertion method and incorrect global traversal cancellation despite its
pass. Baseline outcomes are unchanged, without retries or semantic replacement.
Recommended follow-up is a separate root with explicit inclusive read bounds,
better empty-path recovery, and claim-level completeness/API review. No data
was admitted, and no downloaded or generated repository code was executed.

### RepoChat Follow-Up Details

Paired trajectory improvements, reviewer-only correction, controls, and scale
readiness are maintained in [RepoChat reviewer calibration](dfm13-repochat-reviewer-calibration.md).

Three preferred/good conversations per source were inspected (Compar:IA,
HelpSteer3 preferences, Expert5K, PRISM), plus three HelpSteer3 human edits.
Compar:IA sampling is limited to the publisher's sample file. This is a
qualitative review, not a representative acceptance-rate estimate.

Useful instructional and creative examples coexist with invented factual
claims, broken code, violated duration constraints and unsupported booking
promises. Winning is not equivalent to correct. Human-edited and expert-voted
examples still need absolute-quality checks. Proposed priority is audited
Compar:IA/HelpSteer3, domain-verified Expert5K, then PRISM subject to license
policy. These remain proposals, not additions to `config/dfm13_sources.json`.

Full structural scan: SearchArena has 24069 rows, 8613 preferred sides, and
7556 preferred sides with citations. All 366087 entries are citation-label/URL
pairs, not original search queries or document bodies. No structured tool
calls/results are present. The public attribution analysis expects a separate
scraped-document file not found in its repository tree. Faithful native tool
SFT needs upstream traces or newly generated grounded rollouts.

RepoChat has 3844 rows and 2607 A/B winners; 2567 preferred conversations have
embedded source-file blocks. 2465 contain redactions in user context, sometimes
affecting code comments or identifiers. There are no structured tool calls.
Grounded answer SFT is possible after context/length/answer audits, retaining
actual source text. Native tool-action supervision requires new recorded
retrieval rollouts; do not invent historical calls from file names. Median
winner conversation length is 45545 characters, so length filtering matters.

The existing Gemma4 template supports OpenAI-shaped tools and native call/result
markers, but cannot recover missing actions or evidence. Target only the rated
answer; prior unapproved answers remain masked context.

## Multilingual Report Artifact

The existing `scripts/multilingual_family_report.py` generated
`docs/reports/multilingual_2900k_2950k.pdf`, using
`config/multilingual_family_report_2900k_2950k.json`. Eight family pages contain
table plus bar chart, with matched task populations, mean/min/max and change.
Reading comprehension is omitted by the unchanged >=18-language threshold:
only 10 languages have complete matched results; 11 MultiWikiQA task results
present at 2900K are absent from the 2950K artifact roots as of this snapshot.
This report is read-only and does not log to W&B.

## Uploaded Export Review And Audit Proposal

Follow-up on 2026-10-01: three examples per published export (12 total) were
manually inspected. All four export payload hashes matched the current HF
files. They contain 205242 examples in total. Details and each sample verdict:
`docs/reports/uploaded_arena_quality_review_20261001.md`. Full sampled messages
are in `logs/arena_review/20261001/uploaded_quality_samples.jsonl`; reproduce
with `scripts/sample_uploaded_dfm13_arena.py`.

Semantic problems also occur in these already published targets: an invented
description of internal model reasoning in Danish, faulty Java socket examples,
wrong printer specifications, and an incomplete correction of induction-pan
misinformation. Some other targets are useful as-is. No corpus-wide defect rate
can be inferred from twelve examples; these are not conversion failures.

Recommend a task-aware audit of all selected targets after a 400-row calibrated
pilot. Use keep/repair/reject/needs-verification, evidence-backed factual checks,
deterministic code/constraint checks, and separate infrastructure errors from
content verdicts. Repairs need independent review and preserved provenance.
Do not silently overwrite published preference-selected inputs or treat a
corrected answer as having received the original human preference vote.

RepoChat can be augmented with synthetic executable file-reading calls against
its embedded files, clearly labeled reconstructed. Stronger retrieval behavior
requires fresh tool rollouts against a pinned snapshot. SearchArena can seed
new real search/open-page trajectories with saved evidence and independently
verified answers; adding guessed calls around old answers does not recreate
DeepDive. Proposed pilot sizes: about 100 repository tasks and 300-500 search
tasks. These GPU/audit proposals are not launched or approved production jobs.

Also generated `docs/reports/multilingual_epoch10_2950k.pdf` using the existing
report script: eight matched-coverage family pages, table and chart together,
with the same reading-comprehension coverage caveat as the 2900K comparison.

## SearchArena Real-Search Calibration

On 2026-10-01 the user authorized 100 fresh search trajectories, not reuse of
old preferred answers. `scripts/dfm13_search_calibration.py` prepares a pinned
deterministic sample of self-contained first turns, preserves the original date
anchor, and withholds old answers, winner/model labels, and citation hints.
The basic screening yielded 12815 unique candidates, from which 100 were
selected; this is not a semantic suitability certification.

Provider probing found no Brave/Tavily environment credentials. DuckDuckGo HTML
returned HTTP 202 with a challenge and was not bypassed. Bing public RSS search
returned five ranked results; a real open-page probe fetched Python.org text.
Evidence: `data/dfm13/search-provider-probe-20261001/provider-probe.json`.
Search results may be weak or rate-limited; no URL-only fallback pretends to be
search. Public-only DNS resolution passes checked addresses directly to the
connector; redirects are separately checked, proxies disabled, bytes/time/steps
bounded. HTML visible text is normalized and bounded with truncation explicitly
recorded. Snippets and page text are untrusted evidence, not instructions.

Authorized detached client launched as PID 2687167, without server changes:

```bash
setsid /home/ucloud/miniforge3/envs/hrm/bin/python -u -m scripts.dfm13_search_calibration run \
  --root data/dfm13/search-calibration-100-20261001 \
  --concurrency-per-endpoint 1 --max-steps 8 --timeout 180 --trajectory-timeout 1200 \
  > logs/arena_review/20261001/search-calibration-100.log 2>&1 < /dev/null &
```

Uses borrowed ports 8800-8807, model alias `dfm13-gemma4`, native tools with
`tool_choice=auto`, and `enable_thinking=false`. Local Gemma4 native template
call/result rendering was CPU-tested. Context preflight uses 32768 tokens and
never truncates conversation history. Server native-tool integration and actual
grounding decisions must be checked in live receipts, not inferred from tests.

Each record stores model requests/raw responses, real tool outputs and source
URL/title/body/timestamp/hash evidence, candidate, separate grounding review,
and atomic terminal outcome. One exclusive client lock; terminal rows are not
retried, interrupted rows fail closed, and eight errors stop new dispatch in
that invocation. Review evidence must be literal saved-page and answer spans.
Automated keep is not human approval: all outputs remain quarantined, with no
export admission and student-window validation still pending. Twenty-five CPU
tests passed, including SSRF redirects/DNS, strict JSON, evidence matching,
source withholding, execution ordering and pin integrity. A quality-rate claim
must wait for completed trajectories and manual inspection of keep/reject cases.

### Provider Blocker And Corrected Client

Superseding the initial provider-viability inference above: one successful
Python.org probe did not establish query relevance. The first client completed
15 failed/non-trajectory attempts and stopped with 85 unstarted. Six HTTP 400
responses exposed a wire-format mismatch: OpenAI requires JSON-string tool
arguments, whereas local Gemma rendering requires mappings. Raw receipts remain
in the original root. V2 corrected this mismatch but exited at provider
preflight before any GPU request; PID 2690174 is no longer an active client.

Repeated Bing RSS probes returned unrelated results: a DeepSeek benchmark query
returned Danish probate pages; an Italy-president query returned dentists or
US presidents. The stricter saved two-query canary failed: Python asyncio
returned Reddit/Google Translate and Italy/Mattarella returned no usable
results. Evidence:
`data/dfm13/search-provider-relevance-probe-20261001/provider-probe.json`.
These are real fetched responses, but not useful grounding. No old citation
URLs were substituted. Jina search returned 401, Brave public search 429,
Mojeek 403 automated-access denial, Yahoo 500, and Google a consent page.
No access controls were bypassed. Relevant API environment credentials were
absent; no secrets were printed.

The final client adds explicit Brave API support (no silent fallback), saved
relevance-canary preflight before GPU requests, and, as subsequently authorized,
forces only the first native `search` call. The model still generates the query;
subsequent decisions use auto tool choice. Thirty CPU tests pass. The corrected
prepared 100-row root is `data/dfm13/search-calibration-100-20261001-v3-brave`,
with a local implementation snapshot. This root is NOT launched because the
required `BRAVE_SEARCH_API_KEY` is absent. Once supplied securely to its process:

```bash
setsid /home/ucloud/miniforge3/envs/hrm/bin/python -u -m scripts.dfm13_search_calibration run \
  --root data/dfm13/search-calibration-100-20261001-v3-brave \
  --concurrency-per-endpoint 1 --max-steps 8 --timeout 180 --trajectory-timeout 1200 \
  > logs/arena_review/20261001/search-calibration-100-v3-brave.log 2>&1 < /dev/null &
```

No useful 100-trajectory calibration or answer-quality rate has yet been
established. Zero independently reviewed completions; provider access/quality
is the blocker, not server readiness. Original roots remain diagnostic history,
not datasets approved for training or export. The Brave adapter follows its
[official API reference](https://api-dashboard.search.brave.com/api-reference/web/search/get).

Citation-gate correction (2026-10-01): the original substring test could accept
`https://trusted.example/article-fabricated` after opening only
`https://trusted.example/article`. It is superseded by CommonMark link parsing
plus exact parsed-URL membership for every link and plain HTTP(S) reference in
the answer, checked again by the review validator. Query strings and fragments
must also match; mixed valid/invalid links fail. Unsupported raw HTML fails
closed. Forty-three tests pass, including suffix, host, query, fragment,
reference-style, image and mixed-citation regressions. The new frozen prepared
root is `data/dfm13/search-calibration-100-20261001-v4-brave`; use this root rather
than repinning or resuming v3. It remains unlaunched pending provider access.
DuckDuckGo HTML was tested directly; Lite and the `ddgs` package were not.
`ddgs` is not installed in the client environment. No alternate DuckDuckGo
route was attempted to work around its observed challenge.

### Generation-Only Retry And Jina Support

Superseding forced first-tool selection on 2026-10-01, the user chose native
auto tools plus one explicit prompt retry. If a model returns an answer before
any search call, the controller retries once with `Use search.\n\n` prepended
to a generation-only copy of the original user message. The failed answer is
not conversation context. The steering remains on generation continuations,
but candidate/reviewer user prompts retain the original byte-for-byte text.
No string stripping is used; user-authored `Use search.` remains intact.
Actual request receipts and a separate steering receipt preserve the change.
A second no-search answer still fails, and failed real search calls do not
trigger this steering retry.

`--search-provider jina` now selects the documented `s.jina.ai/?q=` JSON API
using `Authorization: Bearer` from `JINA_API_KEY` and `Accept: application/json`.
It parses the `code`/`data` envelope, records the real query and full raw response
snapshot, and returns ranked URLs/titles plus bounded extractive snippets.
Authorization headers are never receipts; authenticated redirects are refused,
and a credential unexpectedly echoed in a response prevents persistence.
No API fallback or paid requests occurred during implementation. `open_page`
remains the direct DNS/redirect-checked reader, not a Jina Reader fallback around
blocked pages. Official references: [Reader/Search documentation](https://jina.ai/reader/)
and [JSON mode](https://github.com/jina-ai/reader#json-mode).

Fifty-one CPU tests pass. The newly pinned ready root is
`data/dfm13/search-calibration-100-20261001-v5-jina` (same 100 prompts), with the
generation-only retry and exact citation checks. It is not launched while key
configuration is pending. Once the authorized key is supplied securely:

```bash
setsid /home/ucloud/miniforge3/envs/hrm/bin/python -u -m scripts.dfm13_search_calibration run \
  --root data/dfm13/search-calibration-100-20261001-v5-jina --search-provider jina \
  --concurrency-per-endpoint 1 --max-steps 8 --timeout 180 --trajectory-timeout 1200 \
  > logs/arena_review/20261001/search-calibration-100-v5-jina.log 2>&1 < /dev/null &
```

Provider preflight must succeed before any model request. Paid-provider
availability and 100-trajectory quality assessment remain unverified.

### Authorized Capped Jina Campaign

Superseding the key-pending state, the user authorized at most 100 paid Jina
searches on 2026-10-01. Frozen root:
`data/dfm13/search-calibration-100-20261001-v6-jina-capped`.
Client PID 2732602 was verified alive, detached via `subprocess.Popen` with
`start_new_session=True`, using existing ports 8800-8807 at one trajectory per
endpoint. No server changes. Log:
`logs/arena_review/20261001/search-calibration-100-v6-jina-capped.log`.
The supplied credential was entered with terminal echo disabled and inherited
via environment only; it is not stored in source, argv, receipts, or logs.

The campaign SQLite ledger is
`data/dfm13/search-jina-paid-campaign-20261001/cache.sqlite`. An immediate
transaction durably reserves each exact query/options cache miss before any
paid network request. Reservations, including failed/interrupted attempts,
count toward the fixed 100 limit across restarts. At most one new paid query
per sample preserves coverage; any sample can reuse an exact cached query.
No paid preflight canaries consume the allowance. Outstanding reservations are
not automatically retried or refunded. Full raw Jina JSON, including bundled
page content, is stored in the cache and separate provenance snapshots.
`open_page` reuses bundled content before attempting an additional direct page
fetch; only the model-facing excerpt is bounded, never the cached payload.

Fifty-four focused tests pass, including durable restart/cap enforcement,
per-sample allocation, full-cache round trip and network-free bundled-page
reuse. `progress.json` reports outcome counts and cache statuses. Initial live
inspection confirmed a paid reservation and generation requests; successful
provider responses and final grounding decisions require live receipts.
The operator command (with the already authorized credential in environment)
is the v5 command above with root changed to v6-jina-capped and matching log
name. Outputs remain quarantined despite paid-provider authorization.

Live verification after launch: four successful full Jina responses cached
(1529733 raw bytes), one further paid reservation in flight, five total charged
reservations out of the hard 100 cap. The first real query concerned Newsboat
reload/connect failures and returned matching troubleshooting/documentation.
Jina returned ten results in that response: all ten, including full content,
remain cached although only five bounded results were exposed to the model.
Four early outcomes were non-trajectories because the model answered without
successfully opening a page; zero completed grounding reviews at this snapshot.
One invented/unlisted open-page URL was correctly refused. These are real
calibration findings, not successful admissions. PID 2732602 remained alive
and subsequent rows continued; consult progress/cache for current counts.

### Bundled Evidence And Citation Retry Correction

The v6 non-trajectory outcomes exposed a controller mismatch: complete Jina
page content was cached, but only snippets were shown, followed by a mandatory
open-page gate. Per user correction, v7 search observations included bounded
page content with its exact hash/provenance; only that delivered text entered
review evidence. No open-page call is needed when search already delivered
sufficient text. Prior real native calls and paid responses were replayed,
not replaced with invented calls. However, many model answers genuinely omitted
URL citations; inspection of raw final responses confirmed this was not solely
a citation-parser bug. An Israel-postal-code trajectory reached review but had
nonliteral reviewer evidence spans.

V9 supersedes v7 and the prepared-but-unlaunched v8. Live client PID 2740414:
`data/dfm13/search-calibration-100-20261001-v9-cited`; log:
`logs/arena_review/20261001/search-calibration-100-v9-cited.log`.
Only the owned Search clients were replaced; shared servers and bulk audit
were untouched. The same campaign ledger remains authoritative. At initial
v9 verification: 24 full responses cached (7846043 bytes), three unresolved
reservations counted against the cap, 27/100 total. Eight prior native search
calls were replayed without additional paid calls.

For a final answer with missing/invalid links, v9 retries once with the exact
generation-only prefix `Cite sources with exact URLs.`. This request has
`tool_choice=none`, preventing additional retrieval. User prompts in candidates
remain unchanged. The original answer and exact steering request are retained.
If citations remain defective, the candidate is preserved and semantically
reviewed, but cannot become an automated keep. Nonliteral evidence spans are
also recorded with the original reviewer decision as `needs_verification`,
not discarded as an infrastructure failure. This changes disposition handling,
not the exact-URL or evidence-validation checks. Sixty focused tests pass,
including cached-call replay, delivered-versus-hidden evidence, no mandatory
open call, citation-only no-tool requests, and prompt preservation.

Initial v9 live review verified three completed decisions: Italian president
in 2023 kept after the citation-only retry supplied exact retrieved URLs;
Kehilat Eden house number 27 rejected because the answer did not establish the
requested address's code; Paisius source-attribution answer retained as
needs-verification because the semantic reviewer said keep but its evidence
spans were nonliteral. These are automated calibration dispositions, not human
certification or admission. The three reused existing paid query responses.

### Cached-Only Correction And Reaudit Follow-Up

V9 completed all 100 rows: 72 reviewed (1 keep, 22 reject, 49
needs-verification), 23 non-trajectories, and 5 errors. The paid campaign had
75 full responses cached and 12 unresolved reservations, totaling 87/100.
Substantive problems included historical-date drift and unsupported facts;
many needs-verification rows instead had mechanical evidence-span defects.

On explicit user authorization, `scripts/dfm13_search_followup.py` prepared
`data/dfm13/search-calibration-100-20261001-followup1`: 74 jobs, comprising 19
reaudits without answer rewriting and 55 evidence-bound corrections followed
by independent reaudits. One existing keep is unchanged. Twelve rows lack
delivered page evidence and thirteen lack a saved trajectory; these remain
explicitly blocked. The follow-up uses only saved observations and cannot make
paid search calls.

Detached client PID 2760272 was verified alive with the Jina credential removed
from its environment, using existing servers 8800-8807 at one request per
endpoint and 600-second request timeouts. No server or bulk-audit changes.
Log: `logs/arena_review/20261001/search-cached-followup1.log`.
Initial ETA is 20-45 minutes under shared bulk load, not a measured completion
promise. Runtime/progress files and per-row raw requests/responses make actual
dispatch and completion inspectable.

Repairs must explicitly say whether saved evidence is sufficient. Unsupported
or historically unverifiable answers remain unresolved. Independent review
sees the original question/date, proposed answer and saved passages, not the
repairer's verdict. Semantic review uses supporting URLs and unsupported-claim
lists instead of exact-quote formatting; automated keeps still require exact
retrieved citation URLs and no unsupported claims. Source artifacts and
attempts remain intact; no training/export admission is granted. Sixty-eight
combined calibration/follow-up CPU tests pass.

### Full-Cache Diagnostic Versus Reviewer Uncertainty

A subsequent read-only inspection found that early follow-up needs-verification
counts conflate real gaps, excerpt omissions, and reviewer over-caution. No
further repair loop was launched. Reproduce the bounded full-cache inspection
with `python -m scripts.dfm13_search_cache_diagnostic`; artifact:
`data/dfm13/search-full-cache-diagnostic-20261001/evidence.json`. It retains
source URLs, complete-response/content hashes, exact character offsets and
context windows from the full paid-response cache. These newly exposed excerpts
were NOT shown in the earlier model requests and must not retroactively justify
their judgments.

- DeepSeek: official cached report Table 3, around character 75000, reports
  GSM8K EM 89.3, 8-shot, for DeepSeek-V3-Base. Prefix truncation hid it. A future
  targeted correction must preserve the base-model/settings distinction rather
  than claim an unspecified latest chat-model score.
- Meizu: Android Headlines specification text starts around character 29000,
  beyond the supplied prefix; the 200MP claim appears in the title and later
  body. Evidence cropping and reviewer over-caution both contributed. Current
  pricing/support claims remain separate questions.
- Metacognitive intervention: demanding a previously published exact
  programmer-specific example is inappropriate for a requested constructed
  example. Claims of measured efficacy would still need support.
- Text-to-speech: refusal solely because benign instructions use a jailbreak
  wrapper is an overrefusal. Unlimited/free/no-trial product claims still need
  evidence; correcting the refusal is not blanket approval of the answer.
- Postal code: inspected full cached pages do not establish house number 27;
  number 1's postal code and an unexecuted interactive locator are not substitutes.
- Taipei restaurant prices: numeric matches alone do not establish the joint
  price/year/removal criteria; keep unresolved pending entity-specific evidence.

At the diagnostic snapshot, follow-up had 23/74 terminal (18 reviewed, five
unresolved), all needs-verification. This is not a demonstrated 100% semantic
failure rate. The one prior automated keep remains unchanged; no additional
training-ready or human-approved rows are claimed. Paid calls remain zero for
the follow-up; source/cache/provider processes and servers were not modified.

Live latency diagnosis (2026-10-01): at 33/74 terminal, all eight Search workers
were active (one per endpoint), not one globally serial worker. Completed-row
median latency was 58.8 seconds, mean 76.0, max 178.2; two outstanding rows
had multi-minute tails. Read-only vLLM metrics showed 427-443 running and 74-89
waiting requests per endpoint, KV usage 99.1-99.95%, and cumulative preemption
counters 217-348 per engine (not a measured current preemption rate). Search
shares these heavily loaded servers with bulk work. Its prompts are substantial:
median repair input 12623 tokens and reaudit input 11907; output medians 623
and 353 respectively. All 53 inspected completed model responses stopped
normally, so observed completions do not indicate runaway generation loops.

Quality is separate from latency: of 28 completed reaudits, 27 returned a
semantic needs-verification verdict and only one was mechanically downgraded.
Five additional repairs declared insufficient evidence. Thus raising Search
concurrency would not fix the over-cautious rubric or omitted source excerpts
and could add queue pressure. No client/server settings were changed during
this diagnostic.

### Search concurrency override and full-cache replay, 2026-10-01

The user explicitly superseded the one-worker-per-endpoint setting with eight.
New client `scripts/dfm13_search_followup_v2.py` exposes
`--concurrency-per-server 8` (64 workers across ports 8800-8807), timeout 600.
Detached PID 2776562 was launched with this setting; its durable command and
configuration receipt is
`data/dfm13/search-calibration-100-20261001-followup2/launch.json`, and its log is
`logs/arena_review/20261001/search-cached-followup2.log`.
It waits for followup1's completion marker before reviewer controls and dispatch.
The previous client was 73/74 terminal at handoff: its final in-flight request
is allowed to finish rather than killed or duplicated. No servers were changed.

All 74 followup jobs have new cached-evidence replay snapshots, with exact
source-text offsets and full-content hashes. No new paid calls are permitted;
the client environment excludes the Jina key. Four synthetic reviewer controls
must pass before dispatch; outputs remain quarantined. The excerpt ranking is
not a guarantee of factual completeness: the prepared DeepSeek excerpts still
do not include the known 89.3 table value, so this case cannot be described as
resolved by the new extraction. Preserve insufficient-evidence decisions.
Focused Search tests: 76 passed, including worker multiplicity, invalid
concurrency rejection, tail extraction offsets and blocked-page exclusion.

Transition verified at 07:35 UTC: old PID 2760272 exited naturally with all
74 outcomes (53 reviewed, 12 unresolved, nine errors; no keeps). All four
new live reviewer controls passed, including both supported-answer keeps and
both incorrect-fact rejects. PID 2776562 entered running state at eight workers
per endpoint; initial dispatch receipts show work on every port, with the first
two outcomes already persisted. This supersedes the waiting state above.

Completed followup2 diagnosis: 74 terminal, 20 keeps, ten rejects, four errors,
40 needs-verification. The latter includes seven unresolved repairs, not seven
additional rows. Of 33 reviewed needs-verification outcomes, 16 fail exact URL
matching, eight have no recognized citation, seven cite an unobserved source in
the review, and only two are direct semantic uncertainty (historical model dates).
These are automated keeps, not certification or admission.

Concrete defects and remaining gaps:
- URL parser includes closing square brackets in five failed URL strings
  (one also includes Japanese punctuation). Example 020d55a2 ends `1118]`.
  Other failures are not all parser bugs: generated product/homepage links and
  example.com placeholders are currently treated as evidence citations too.
- Bluetooth e19e0b36 is rejected despite an entirely approving rationale and
  no unsupported claims; reviewer verdict/rationale consistency needs repair.
- Liverpool 0cfb74ac uses completed-season results for a March 2025 question;
  Microsoft 12490c96 attributes substantive claims to navigation-only LinkedIn
  text. These demonstrate genuine generation/date/grounding problems.
- DeepSeek 64b59e0d remains unresolved because ranked excerpts omitted the
  known full-cache benchmark table. Improve term/table-aware selection with
  headers and model-variant context, without inventing results.
- Postal house 27 (93ba45a2), unavailable eBay listings (e559987e), Cross Creek
  chapter order (d4fc6d00), and MarkText install size (f911a4e7) lack the requested
  evidence in delivered passages; no blanket keep is justified.
- Error b0d5dab9 is an HTTP 400 context overflow: 30721 input plus 2048 requested
  output exceeds 32768. Other errors occur during incomplete structured outputs.
Next bounded corrections should separate cited evidence from ordinary destination
links, repair URL punctuation without prefix matching, enforce date anchoring,
and re-review only affected rows using the same cache. No new paid calls made.

CPU-only punctuation rescore is recorded separately in
`data/dfm13/search-citation-rescore-20261001/receipt.json`: four keeps restored,
24 keeps / 36 needs-verification / ten rejects / four errors. The fifth malformed
URL still points to an unobserved image, so remains blocked. Original outputs
are unchanged; 86 focused tests passed at this revision.

The user then requested reviewer improvement before any further answer generation.
The prepared eight-case temporal repair was NOT launched. Instead, reviewer-only
PID 2786132 runs `scripts/dfm13_search_reviewer_v3.py run
--concurrency-per-server 8 --timeout 600` on all 74 saved answers, root
`data/dfm13/search-reviewer-v3-20261001`, log
`logs/arena_review/20261001/search-reviewer-v3.log`. There are no generation or
paid-search calls. Missing new candidates use explicitly labeled saved repair
answers or prior answers, not fabricated completed trajectories.

The reviewer emits typed findings from which the controller derives the verdict.
Bundled real Jina page content is recognized without mandatory open_page calls.
Fresh retrieval does not make post-prompt documents inherently fabricated;
explicit historical questions still retain their requested dates and old answers
are not relabeled current. URL equivalence is limited to host/default-port,
unreserved encoding, and page fragments; paths, reserved encoded separators and
query values remain distinct. No prefix matching or invented sources is allowed.
Thirteen focused new reviewer/citation tests passed. Production readiness remains
unproven pending this saved-answer assessment and actual trajectory-gap review.

### Completed Reviewer Pass and Bounded Recovery

Reviewer v3 finished all 74: 25 keep, 37 needs-verification, five reject, seven
errors. All 37 holds were validator outcomes (14 missing recognized citation,
23 URL mismatches), not 37 independently established factual gaps. Neither this
fact nor a positive model rationale establishes correctness: independent
assessment in `docs/reports/dfm13_search_trajectory_assessment_20261001.md`
found a historical-date false accept and a CPU-disproved mathematical assertion.

Destination-aware CPU parsing (`scripts/dfm13_search_links_v4.py`) ignores URL
display labels inside Markdown links and classifies fenced-code URLs separately.
It still requires an answer citation to actual supporting observed evidence;
unclassified outside-source navigation links remain held. The receipt at
`data/dfm13/search-links-v4-20261001/receipt.json` has 27 mechanically clear rows,
including two newly cleared, but explicitly does NOT certify them. Those two
are Liverpool (known historical-date defect) and a Russian bibliography (remaining
task-completeness concerns). Source boundaries were not relaxed.

PID 2792191 retried seven failed reviews with identical answers and page bodies,
omitting duplicate excerpt copies: three keep, one needs-verification, three
remaining length errors. The remaining errors are verified whitespace loops,
not context overflows. PID 2797536 performs one changed-parameter retry only,
`scripts/dfm13_search_review_loop_retry.py`, frequency penalty 0.5, output budget
3072 with explicit prompt+output+512 context check. No paid search or generation.

PID 2796015 runs `scripts/dfm13_search_targeted_repair_v4.py run
--concurrency-per-server 8`, root `data/dfm13/search-targeted-repair-v4-20261001`,
log `logs/arena_review/20261001/search-targeted-repair-v4.log`. Four targeted live
controls passed before dispatch of 24 bounded repairs. An earlier control run
was 3/4 because its positive fixture asked for an image link but supplied none;
that failed fixture remains preserved, and the corrected fixture asks about
document publication/retrieval chronology. No gold expectation was silently
flipped. Aggregate active Search requests, including the three review retries,
were at most four/server initially and three/server at the checked snapshot.

New extraction preserves offsets and adds technical-table context. The DeepSeek
case now includes the real 89.3 value, 8-shot setting and DeepSeek-V3-Base heading.
However, automated keep outcomes remain suspect: repaired case 51c2360a claims
GPT-5 flagship status in May 2025, and 032d2d0c still overclaims a mathematical
minimum. The calibration repair prompt includes a CPU-verified Miller-Rabin
counterexample globally; this is teacher-hint provenance, NOT independent
generalization, and must become case-specific before production. No admission.

CPU production inventory is
`data/dfm13/search-production-cpu-readiness-20261001-v1/manifest.json`, generated
by `scripts/dfm13_search_production_readiness.py`. Source parquet has 24069 rows,
not 24069 eligible/verified examples. Cache has 75 completed unique queried
owners plus 12 unresolved charged reservations (87/100 total). This phase permits
zero new paid calls. It cannot yield 100 fresh independently searched trajectories
from that cache, and the remaining budget is not spent automatically. Production
is explicitly blocked on quality dispositions and retrieval coverage.

### Terminal Bounded Campaign Snapshot, 08:04 UTC

Targeted repair v4 finished 24/24: ten automated keep, 13 needs-verification,
one reject, no errors. The three whitespace-loop retries finished: one keep,
two needs-verification, no errors. Thus all seven reviewer-error cases now have
a completed review across their bounded recovery lineage. No new paid requests
were made, and all owned Search clients from these runs are terminal.

Final unique-sample lineage ledger:
`data/dfm13/search-campaign-ledger-20261001-final/ledger.json` covers all 100
original samples without summing repeated attempts. It selects 35 automated-keep
candidate lineages, places three independently identified cases on hold, and
leaves 62 without a selected passing candidate. This is NOT 35 independently
certified training rows. Every historical outcome remains linked and unchanged;
later negative review of the same candidate invalidates earlier selection.

The 13 repaired-row holds break down into five unobserved-review-source cases,
one missing/unobserved support case, four unclassified hyperlinks, and three
missing answer citations. The single reject is the logo-list case, where the
reviewer still misinterprets later document dates, while unsupported URLs/task
presentation also require checking. The ledger includes an exact per-row needs
list, cached source URLs, original timestamp, proposed query where appropriate,
and classification separating retrieval from purely mechanical work.

One of the four hyperlink cases was subsequently cleared CPU-only: Japanese
prose immediately after `[URL]` was consumed by the plain-URL scanner. New
`scripts/dfm13_search_links_v5.py` bounds that bracketed URL without changing
candidate text or tolerating URL-prefix matches. Receipt:
`data/dfm13/search-cjk-citation-rescore-20261001/receipt.json`. This is one extra
mechanical clearance, not silently added to the 35 selected lineages.
All focused Search tests now pass: 107 tests.

The user permits up to the remaining 13 charged searches within the original
100 ceiling where necessary. None were spent on missing citation syntax or
navigation links. Cache still has 75 successful searches and 12 unresolved
charged reservations. Even 13 additional successes can produce at most 88
distinct successfully searched owners under that ceiling, not a fresh 100.
The CPU needs list proposes nine evidence-oriented queries, but several first
require checking already cached full documents; it is not an executed retrieval
queue or authorization to exceed the existing campaign cap.

### Authorized Nine-Query Supplement

The user explicitly authorized nine proposed evidence queries under the original
100-call ceiling. `scripts/dfm13_search_supplement9.py` uses the SAME SQLite
`searches` ledger, `BEGIN IMMEDIATE`, and a scoped supplementary reservation
table; the previous 87 rows are retained. It permits one additional query for
each of nine explicitly listed owners and refuses unknown queries, cap overflow,
and unresolved-query retries. Existing completed identical queries are reusable
without another charge. Six focused budget/hint-scope/credential tests passed;
the complete Search suite reached 113 passing tests.

Detached PID 2806416 runs the supplement at a maximum eight requests/endpoint,
root `data/dfm13/search-supplement9-20261001`, log
`logs/arena_review/20261001/search-supplement9.log`. The already supplied credential
was passed through hidden stdin into the child environment only, never saved in
source, command arguments or a credential file. A private-file waiting mechanism
exists but was not needed. No server or training processes were changed.

At 08:14 UTC all nine paid attempts had finished: eight successful full responses
cached, one HTTP 422 (HelpX host-specific query) retained as charged failure with
no retry. Global accounting is now 96 reservations: 83 successful responses and
13 unresolved/failed reservations. Four slots remain, not automatically spent.
Successful distinct owners remain 75 because these are supplementary queries for
existing cases, not fresh examples. Fresh-100 coverage is therefore not achieved.

Eight new-evidence repair/reaudit cases are running after retrieval. The actual
supplemental searches are controller-planned, not falsely described as teacher-
generated search calls; this provenance is retained, and their controller call
is excluded from target message indices (final answer only). Full raw Jina
responses, excerpt offsets, query, cache hash and observed native tool messages
are preserved. Latest stage receipt is `stage-status.json`; the initial runtime
label was stale during the three preliminary cached corrections.

Three independent holds were also retried with case-specific corrective hints,
not a global mathematical hint. All three received automated keeps but repeated
the known incorrect math/date assertions; their independent holds remain.
`data/dfm13/search-independent-hold-corrections-20261001/ledger.json` instead
contains explicitly agent-authored conservative corrections, with CPU-verified
factorization/strong-test evidence and additional full-cache support for the
2,7,61 sufficient bound. It does not claim a minimum-base proof or invent a
historically latest model. These are corrective drafts, not certified complete
answers or automatically admitted training rows.

Supplement terminal update (08:16 UTC): all 12 outcomes persisted, PID 2806416
exited. Six automated keeps, five needs-verification, one retrieval error.
Four of those keeps remain independently held: the original three and the SBUX
case, which again answers the historical March 2025 question with September 2026
prices. Fresh retrieval did not establish the requested historical dates.
The two other new keep candidates concern Polish name elements and OpenShift
deployment; neither is independent factual certification.

The post-supplement unique ledger is
`data/dfm13/search-campaign-ledger-20261001-post-supplement/ledger.json`: 36
selected automated-keep candidate lineages, four independent holds, 60 without
a selected passing candidate, covering exactly 100 unique IDs. All original
outcomes remain preserved. Final report and per-query dispositions are in
`docs/reports/dfm13_search_supplement9_outcome_20261001.md`. No additional paid
calls are scheduled. Budget remains 96/100; distinct successful owners remain
75. Supplement pins and final-answer-only target indices were checked. Seven
supplement tests pass, including two concurrent reservations competing for the
last global slot: exactly one succeeds and total stays at 100.

### Critique-First Calibration

The user authorized a small eight-case reviewer experiment, not production
scaling. `scripts/dfm13_search_critique_adjudication.py` prepares four known false
accepts (Miller-Rabin, OpenAI release chronology, societal-disruption chronology,
SBUX historical prices) and four provisionally inspected nontrivial controls
(DeepSeek base-model score, Takayama access, six-virtue textual attribution,
German history lesson design). Saved answer and evidence bodies are unchanged.
Original requirements/time anchor are separate from answer and retrieval date.
The math counterexample and calendar comparisons are computed on CPU and supplied
as explicit checks; they are not invented model observations.

Detached PID 2816265 runs the frozen eight-case root
`data/dfm13/search-critique-adjudication-20261001`, log
`logs/arena_review/20261001/search-critique-adjudication.log`, command
`python -u -m scripts.dfm13_search_critique_adjudication run
--concurrency-per-server 8 --timeout 600`. It reuses `Model.ask`, at most 16
model calls, frequency penalty 0.5, output budget 2048, no paid retrieval or
answer generation. Critic and adjudicator use separate inference contexts and
different existing endpoints, but the SAME model weights; this is not
independent model-family certification. Typed confirmed/unresolved/dismissed
findings determine the verdict; no free-form verdict label, quote IDs or span
offset requirements. Gold expectations are recorded separately and never sent
to either model. Six focused tests passed. No automatic admission is permitted.

### Reviewer Loop And Factual Controls

See [Search Reviewer Controls](dfm13-search-reviewer-controls.md) for decoder
recovery, persistent mathematical false acceptance, and bounded factual tests.

## Original-Keep Manual Spot Check (2026-10-01)

User-requested deterministic original-keep review: **7 retain, 2 localized
repair concerns, 1 unresolved factual estimate**. Full IDs, methods and findings:
`docs/reports/dfm13_original_keep_manual10_20261001.md`. Pinned samples/receipts:
`data/dfm13/original-keep-manual10-20261001-v1/`. Quotas 3/3/2/2 cover all four
bulk sources; all source hashes and ten ledger identities verified. Concerns:
unsupported internship details and a 16-versus-17-byte example. No population
error-rate or repair-effectiveness claim; corrected answers were not inspected.
Parent/Epicurus handoff only, with no active output, GPU or admission changes.
