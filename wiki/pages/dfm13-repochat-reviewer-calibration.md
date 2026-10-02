---
type: Runbook
title: DFM13 RepoChat Reviewer Calibration
description: Frozen RepoChat trajectories, reviewer controls, readiness checks, and scaling policy.
tags: [dfm13, repochat, calibration, review]
status: draft
last_updated: 2026-10-01
confidence: high
---
# DFM13 RepoChat Reviewer Calibration

Baseline context: [Arena quality review](dfm13-arena-quality-review.md).

### Independent Native Eight Dispositions (2026-10-01)

Boole's receipt `docs/reports/dfm13_repochat_native25_manual8_assessment_20261001.json`
supersedes any inference that the 13 automated passes were uniformly sound:
four useful supported cores, two partial-scope repairs, two confirmed false passes.
PyGyat wrongly denied `rizz` technical meaning despite its addition-token mapping;
DFDC wrongly denied augmentation-library use despite the training pipeline.
LlamaGym needs the environment reward call site/exact formula; LIDAR-Car needs
project-purpose/platform evidence rather than inference from filenames.
The four supported cores are not blanket admission: GetUser, for example, has an
unanswered chat branch. The review replayed 33 observations and rerendered 41
sample targets, all fitting 4K; semantic correctness remains a separate gate.

All review/candidate/source pins were reverified by new CPU-only
`scripts/dfm13_repochat_native25_dispositions.py`. Durable exact-hash state is
`data/dfm13/repochat-native-student25-20261001-v1/independent-disposition-v1/dispositions.json`:
17 native candidates = four supported cores, two independent hard holds, two
independent repair holds, two local retry holds, seven independent-review pending.
Zero admitted. `cpu-repair-evidence.json` beside it contains verified additional
source reads; `pending-seven-manual-packet.json` queues the seven unreviewed native
candidates with source pins and masks, omitting automated rationale to reduce anchoring.
The six held candidates remain outside that queue. The repair packet contains
source reads for the four independent repair findings. These reads are diagnostic
only, never retroactively appended to learner observations. Original trajectories,
outcomes and the 13 successful baseline candidates are unchanged. Five focused
disposition tests passed; no new model calls, process launch, or expansion.

### Native Twelve Failure Diagnosis and One Retry (2026-10-01)

The 12 failures in the student-context cohort were mutually exclusively:
three context-absence responses without tool use; four root/path-prefix mistakes;
two tool-round exhaustions; one student-context exhaustion; two requests for 50
lines against a 30-line schema. There were zero observed infrastructure failures,
output-length failures, or policy refusals. Four evidence-free cases treated `.`
as a literal dotfile prefix instead of the root; one budget failure also followed
that path, while another read long CSS sequentially. Flat listings consumed the
context budget in the remaining case.

User authorized one bounded retry of these failed IDs only. New isolated script
`scripts/dfm13_repochat_student12_retry.py` declares mounted-repository/root
conventions, treats `.`/`./` as root, returns immediate files/subdirectories,
reminds the teacher of the unchanged 30-line limit, and reserves a final-answer
turn. Generic steering only; no answer hints. Original successful 13 artifact
hashes are protected. Student 4K masks, source replay, evidence requirements, and
whole-answer review remain mandatory; no truncation or schema-limit weakening.

Root: `data/dfm13/repochat-native-student25-20261001-v1/generation-retry12-v1/`.
Client 2936415 finished. Four new candidates passed automated whole-answer review;
eight remain held: three evidence-free answers, two student-budget stops, and
three `stop` responses with neither content nor native tool calls. The latter
used only 26-39 completion tokens, so are not length failures; precise server
decoding/parser cause is unestablished. No additional attempt is queued.
The four candidates have 23 valid student targets, maximum 3,424 total tokens.

`ready.json` records diagnosis/selection/protected hashes;
`diagnosis-and-generation-report.json` and `terminal-report.json` record counts.
`manual-packet.json` contains all four candidates and two additional exact-hash
local concerns: Waynboot's architecture conclusion goes beyond README/module
evidence; DCIL's answer may need clarification of the semantic difference between
the two state lists. Automated passes do not clear these concerns. All original
13 candidates remain unchanged and under Boole's assigned sample review.
No expansion or admission; 39 focused tests passed; shared servers unchanged.

### Native Student-Context Cohort (2026-10-01)

Pending-seven independent receipt:
`docs/reports/dfm13_repochat_pending7_manual_assessment_20261001.json`.
Five useful supported cores, one partial (Snappy wrapper methods without the
underlying `fs_snapshot_*` implementation), and one confirmed false absence
(CMU Graphics mouse handling) were found. The legacy literal-dot-prefix search
problem explains the latter; pinned `cmu_graphics.py:1252-1254` contains the
mouse-button dispatch. All 31 sampled targets CPU re-rendered identically to
the packet, maximum 3225 tokens. No admission or earlier-hold clearance.

Independent eight-pass manual receipt:
`docs/reports/dfm13_repochat_native25_manual8_assessment_20261001.json`.
See Independent Native Eight Dispositions above for semantic findings.
The 41 re-rendered sample targets reached at most 2670 tokens; this validates
sampled mechanics, not blanket admission.

Following the independent grounded-eight findings, an exact CPU-authored Agnai
replacement now distinguishes clients exported by `srv/api/ws/redis.ts` from
messaging helpers re-exported by `srv/api/ws/index.ts`. New hash, source proof,
and successful automated whole-answer review are in
`repochat-qa-next-20261001-v1/grounded-repairs-v1/agnai-export-cpu-v1/`.
Independent manual clearance is still required. MergePath remains clarification.

User authorized 25 fresh prospective native QA cases, not bulk admission. Root:
`data/dfm13/repochat-native-student25-20261001-v1/`.
New implementation: `scripts/dfm13_repochat_student25.py`. Four CPU source workers
checked 28 public pinned sources: 27 ready, one blocked; first 25 eligible tasks
selected deterministically. Actual native list/search/read calls execute against
safe pinned snapshots. Teachers receive generic concise grounding instructions
and untouched source questions, without case-specific feedback or old answers.

The actual DFM11 tokenizer/template and metadata are pinned. Every full history
is student-rendered before another request, reserving 768 tokens under a 4,096
prompt-plus-target limit. Every assistant tool call/final answer is then rendered
as a singular target with the real training API; prompt masks and causal shift
are checked. Oversized histories/targets fail explicitly, without trimming or
history deletion. Tool reads use complete bounded lines with explicit pagination.

Both clients (2926457 fresh QA, 2926458 Agnai review) finished. All 25 rollouts ran:
**13 generated and automated-review passes**, seven evidence-free finals held,
two tool-round exhaustions, two invalid read-range calls, one student-budget
exhaustion. Automated passes are not independent manual approval.
`student-contract-verification.json` independently verifies original source
questions, native cycles, full tool-result replay against pinned files, rendering
and masks. All **61 assistant targets across 13 candidates** fit, maximum **2,670
tokens**. Candidate rows contain messages/tools/target indices; provenance and
review metadata remain separate. Prior grounded-eight derivative packets are
explicitly review-only, not native training rows, in
`prior-grounded8-training-disposition.json`.

Terminal counts: `summary.json`, `whole-answer-review/summary.json`, and
`completion.json`; deterministic eight-case manual selection: `manual-sample.json`.
Full eight-case native/manual packet: `manual-packet.json`; combined Poincare/parent
handoff: `parent-manual-handoff.json`, including the separate Agnai CPU draft.
The new Agnai answer SHA256 is
`dc0677d83b3785c3d33324c1dcf6dccaa3c1ea490e6bb54357014cd408ce9a71`.
`agnai-export-cpu-v1/independent-hash-dispositions.json` preserves the newer
independent holds on the preceding Agnai and MergePath hashes; automated review
does not clear them.
Thirty-six focused tests passed. Eight requests/server was the ceiling; shared
servers and training were unchanged. No hold release, upload, admission, or
automatic further cohort is authorized by these artifacts.

### Independent Grounded Eight Review (2026-10-01)

Current repaired hashes: 6 keep/1 localized repair/1 needs clarification.
Agnai now locates Redis correctly but says `clients` is re-exported by
`ws/index.ts`, which only re-exports messaging helpers. MergePath loss formulas
are fixed; its detached STD-gradient caveat remains unresolved. Automated
length failure is not semantic rejection. Receipt:
`data/dfm13/repochat-qa-next-20261001-v1/grounded-repairs-v1/independent-terminal-review.json`.
Report: `docs/reports/dfm13_repoqa_grounded8_terminal_review_20261001.md`.
Eight answer hashes, 24 artifact hashes and 16 supplemental reads verified.
No old hold release/admission; this is known-case repair evidence, not generalization.

### Grounded Eight Terminal Follow-Up (2026-10-01)

This supersedes the launch-only status below. Clients 2893684, 2904689 and
2910416 have all exited; no owned client remains. The original run produced five
answers and three `non_stop:length` failures, with all 8,192 tokens consumed by
reasoning in the first two failures. There was no controller-lock deadlock.
All four second-wave cases ran. Each of the three length-only failures received
one additive non-thinking generation retry (4,096-token limit), preserving the
original receipts and thinking-enabled independent whole-answer review. No
semantic rejection was retried, and shared servers were not changed.

All **eight cases now have complete answers**: seven known repairs plus one new
case. Seven automated whole-answer reviews passed. MergePath's whole-answer
review reached `non_stop:length`, so it has no successful automated verdict.
Its generated answer corrects squared cross-entropy and the aggregate norm but
omits the prior gradient-detachment caveat; independent manual assessment is
still required. These results do not release any of the 13 hash holds or authorize
scaling/admission. The 48-row filtered view is unchanged.

Authoritative operational receipt:
`data/dfm13/repochat-qa-next-20261001-v1/grounded-repairs-v1/terminal-report.json`.
Poincare/parent handoff: `terminal-manual-packet.json` in that same directory,
SHA256 `6805808e4e824bac2e88b2c93611ab5635f575d450a911b272521cb3a6ecc547`.
It includes all eight full answers, exact answer/trajectory hashes, retrieved
evidence, snapshot pins, and review outcomes. It supersedes the earlier two-wave
assignment packet for preferred answer selection, including the three retries.
Twenty-eight focused tests passed. Retry implementations are separate scoped
files; the original frozen runner and artifacts were not edited.

### Full Inventory and Grounded Repair Hold (2026-10-01)

CPU inventory: `data/dfm13/repochat-production-inventory-20261001-v1/`.
Pinned `inventory.json`, `availability.json`, `summary.json`, and
`production-plan.json` record 3,844 source rows, 1,840 unique eligible preferred
prompts before three task-level exclusions (1,837 after), and 60 exact eligible
duplicate rows. Prior inventories reserve 268 unique prompts; 226 were selected
for attempts. The remaining pool is 1,572. Eight CPU/network workers checked all
1,105 remaining repository URLs without archives, credentials, or Git execution:
1,029 public HEADs, 73 unavailable at probe time, three inconclusive failures.
Unavailable is not proof of private/deleted status.

Lexical triage: 192 descriptive QA candidates (184 accessible across 163 repos;
161 distinct normalized query strings), 239 usage questions, 759 unclassified,
312 construction/change holds, 67 exhaustive/security holds, three safety holds.
Non-English prompts remain available for manual review. Prompt inspection found
23 bounded QA candidates, including 15 accessible nonlexical additions, making
199 prospective accessible QA candidates. None is source/quality approved.
Planning allowance: **100-200 additional candidate attempts**, low confidence,
not accepted yield. Proposed preparation uses four distinct-repo workers (max
eight), one writer per repo, recorded commits, safe extraction and existing
128 MiB compressed/1 GiB expanded/1 MiB per-file/100,000-member caps. This is
capacity planning only: scaling remains stopped after the fresh manual findings.

`repochat-qa-next-20261001-v1/grounded-repairs-v1/holds.json` applies 13 exact
answer-hash holds, including the corrected Agnai draft. Its
`filtered-candidates.json` is the current **48-row unadmitted view**; the previous
55-row artifact remains historical and requires the newer holds before use.
No original hold is cleared by a corrected draft's verdict.

New `scripts/dfm13_repochat_grounded_repairs.py` uses verified source reads and
a concise generation contract: material claims reference retrieved files/lines;
documented purpose, implemented behavior and inference are distinguished;
architecture guessing and unsupported guarantees are prohibited. First wave:
Agnai, Neuro game API, multimodal padding, and one new pinned `rswier/c4` overview.
Four remaining known repairs follow. Independent whole-answer review receives
evidence without correction feedback. Results remain derivative evidence packets,
not native training trajectories, and automated review is advisory.

Detached client PID 2893684 (start ticks in `grounded-repairs-v1/launch.json`)
started four real requests on ports 8800-8803, with at most four simultaneous
generation requests. Seventeen focused tests passed at launch. Track per-wave
summaries and `runner.log`; completion is not claimed here. Shared servers,
training, and historical artifacts remain unchanged. No admission or scaling.

### Corrected Three And Fresh Twelve (2026-10-01)

Whole-answer CPU review, superseding any implication that the claim pilot's
8/8 clears complete answers: corrected drafts 2 keep/1 repair (Agnai still
misplaces Redis); fresh twelve from filtered-55 yield 5 keep/6 repair/1 needs
clarification. No admission or hold release. Material issues include causal
versus padding masks, selected-profile versus logged-in identity, and exact
MergePath loss. Claim checker was not rerun on these twelve: these are manual
findings, not a new checker accuracy measurement. Exact hash-bound receipts:
`data/dfm13/repochat-qa-next-20261001-v1/readiness/independent-corrected3-review.json`
and `independent-fresh12-review.json`. Report:
`docs/reports/dfm13_repoqa_corrected3_fresh12_review_20261001.md`.

### Fresh Eight-Pass Manual Review (2026-10-01)

Independent hash-stratified inspection of eight distinct repositories from
`repochat-qa-next-20261001-v1/eligible-74` (65 passes, nine failures) recommends
three retains, three confirmed localized repairs and two grounding/wording
repairs. Full prompts, 41 retrieved tool responses and final answers were read;
no repository code was executed. Confirmed errors concern the Agnai Python
entrypoint, IDSHV transfer-search algorithm, and OneCode Socket.IO option names.
OS isolation and DINO register wording need narrower claims, not blanket rejection.
Original labels and admission remain unchanged. This is not a population
accuracy estimate. Pins/full-message packet/JSON findings:
`data/dfm13/repoqa-pass-manual8-20261001-v1/`.
Detailed report: `docs/reports/dfm13_repoqa_pass_manual8_20261001.md`.

### RepoChat V2 Paired Follow-Up

User-authorized follow-up uses new `scripts/dfm13_repochat_calibration_v2.py`
and `tests/test_dfm13_repochat_calibration_v2.py`; the v1 implementation and
artifact root remain unchanged. Root:
`data/dfm13/repochat-calibration-100-20261001-v2`. The same 100 task IDs and
repository commits provide a paired comparison, not a fresh held-out estimate.
Four separate reviewer-only controls reuse the known-negative v1 RTree, DXVK,
Festival, and display-type answers. No old answer is shown to a fresh rollout.

Tool changes: read uses `start_line` plus bounded `line_count` (1..120), returns
`next_start_line` and clipping information; list returns immediate directories
and an exact pagination cursor. Empty results suggest broader navigation;
identical repeated valid calls receive a warning then terminate on the third
attempt. Evidence is required before finalization (`tool_choice=required`
until a nonempty read/search result), and structural failures stay separate
from reviewer rejection. The review explicitly assesses completeness and API
grounding, requires specific issues for rejection, and rejects inconsistent
verdict/issue combinations. All outcomes remain unaudited calibration artifacts
with `admission=false`, not production approvals.

Budgets are 16 rollout turns, 6144 output tokens, eight CPU tool threads, and a
hard four HTTP requests per endpoint across both generation and reviews. The
shared bulk Arena campaign was already using 512/server, so no server or
training changes were made. All eight `8800..8807/v1` endpoints reported model
`dfm13-gemma4`. The native template uses `enable_thinking=false`.

Focused baseline-plus-v2 tests: 34 passed, including native HTTP roundtrip,
receipt-only resume, read/count bounds, navigation recovery, strict review
booleans/consistency, and separation of old negative controls from generation.
Detached PID `2761520` launched with:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/dfm13_repochat_calibration_v2.py prepare
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/dfm13_repochat_calibration_v2.py run --authorized --per-endpoint 4
```

`launch.json` contains the exact PID/start ticks, command, and implementation
hash. `ready.json` pins both implementation files, source selection, snapshot
receipts, and control transcripts. Operational output is `runner.log`. The
client was stopped by exact owned PID after over ten minutes without a first
rollout response. All four reviewer controls finished: RTree/Festival rejected,
DXVK falsely passed, display-type verdict inconsistent and failed closed.
`interruption.json` and `control-assessment.md` preserve that disposition.
There were no completed fresh rollout responses to overwrite.

Superseded operationally by `scripts/dfm13_repochat_calibration_v3.py`, root
`data/dfm13/repochat-calibration-100-20261001-v3`, PID `2771351`. V1 and V2
implementations/artifacts are preserved. Installed
`vllm/tool_parsers/gemma4_engine_tool_parser.py` declares
`supports_required_and_named=False` and documents a forced-JSON/native-syntax
conflict. V3 returns to native `tool_choice=auto`, keeps the evidence gate,
and records one explicit harness reminder if the teacher answers prematurely.
Before evidence, output is bounded to 768 tokens; after evidence it retains
the 6144-token answer budget. No failed baseline sample is silently replaced.

The unchanged four review requests reuse pinned raw V2 responses with request
hash validation and explicit `review-cache-provenance.json`; controls no longer
block rollout launch. V3 has a hard three requests/server, leaving a spare
slot for diagnostics within the parent's four/server cap. All 100 paired cases
are scheduled; 24 first requests were confirmed submitted via `request-events/`
and exact client sockets. Request starts are flushed to `runner.log`.
Baseline/V2/V3 tests: 51 passed.

Do not misdiagnose the subsequent wait as a lock deadlock: the controller holds
one nonblocking lock and waits in `ep_poll` with established HTTP connections.
A fresh-session native-auto 128-token diagnostic itself timed out after 300s,
so connection reuse or forced tool choice alone does not explain latency.
A separate force-closed streaming probe received HTTP 200 in 8ms, then waited
for model output. Parent measured 3380 running/757 waiting server requests,
97-100% KV utilization, and 49 preemptions in 30s. Shared queue/decode pressure
is therefore a material blocker. V3 remains pending with bounded 1800s/request
deadlines, not idle or waiting on an approval/calibration gate. No shared
server, bulk campaign, or training process was signaled.

Subsequent explicit user authorization raised V3 to eight requests/server.
Only owned PID `2771351` was stopped; the exclusive controller lock protected
the operational config update from `per_endpoint=3` to `8`. Prior config,
launch identity, and request-start events were archived under
`operations/increase-to-eight-20261001/`; authorization and before/after hashes
are in `authorization.json`. Source pins and model/quality settings did not
change. PID `2776162` was launched, and `verification.json` proves eight
established connections to each of the eight endpoints and preservation of
all existing artifact hashes. The parent concurrently reduced bulk admission
to 384/server. Real rollout responses then began arriving (31 at first check),
supporting shared KV/queue pressure as the prior latency cause rather than an
idle client gate. Superseded completion status: all 100 finished, with 83
automated reviewer passes, eight reviewer rejections and nine failures. These
are not admission approvals. All 436 native calls have matching results;
read-range errors fell from 55 to zero. The nine failures comprise three empty
answers, one no-evidence answer, one output-length stop, two tool-budget limits,
one repeated-call abort and one reviewer-contract inconsistency. The latter is
a reviewer failure, not a failed generation.

### RepoChat Reviewer-Only Correction (2026-10-01)

The user requested reviewer repair before further generation. Frozen V3 answers
are preserved. `scripts/dfm13_repochat_rereview.py` re-reviews only saved complete
responses, using typed defects, support findings and exact message-ID/quote
validation. Approval is derived locally, never a separate model label. The
rubric explicitly checks complete implementations, bounds and missing algorithms,
declared API signatures, and evidence for repository-wide negative claims.
Five exposed negative controls (four historical counterexamples plus OpenCV)
and a supported positive control are diagnostic, not an unbiased held-out set.
Failed controls leave all subsequent comparisons uncalibrated; admission is false.

The first reviewer-only attempt returned malformed contracts and was stopped
by exact owned PID 2787055 without touching shared servers. The second attempt
uses strict JSON-schema output in new root
`data/dfm13/repochat-rereview-100-20261001-v2`, at eight requests/server on
8800-8807. Focused contract tests: 15 passed. No repository answer is regenerated.

Independent manual trajectory gaps already established: DXVK gives unsupported
repository-wide coverage claims after README-only retrieval; the OpenCV answer
indexes N-1 optical-flow entries across N frames and omits its promised temporal
filter despite calling the implementation complete. Both were false accepts.
Fresh RTree still has missing implementation, now correctly rejected; Festival
exhaustiveness remains unresolved because the fresh trajectory exhausted its
tool budget. The display answer now reads the actual int32 API signature, fixing
the prior type-inference error. These are distinct from reviewer schema failures.
No scale launch is justified by the old 83-pass count alone.

Superseded reviewer contract (same day): exact quote-ID and six-dimension
nesting added fragility without resolving false accepts. The user requested a
simple substantive quality gate. Current reviewer-only attempt is
`data/dfm13/repochat-rereview-100-20261001-v3` (PID 2791247 at launch), with
strict schema `support`, typed `findings`, and `rationale`; no span gate or
separate model verdict. Fourteen focused tests and 65 combined RepoChat tests
passed. Initial live results pass the positive control but incorrectly pass
RTree and OpenCV negatives. This is a semantic calibration failure, not an
infrastructure or parser failure. A focused reasoning-enabled critic probe
is being evaluated; the production scale gate remains closed meanwhile.

CPU production inventory, pinned in that root's
`production-candidate-inventory.json`: 3844 source rows, 1840 deterministic
eligible unique prompts before task-level exclusions; after excluding the 100
calibration prompts and three additional task exclusions, 1737 prompts across
1231 repositories remain. The next bounded 1000 are listed but not launched
or snapshot-validated. Availability, public access and snapshot size safeguards
can reduce that number. All new answers would retain native read-only tools,
immutable source provenance, eight requests/server, strict terminal checks and
independent review. No old preferred answers are exposed to generation.

The simplified reviewer then falsely passed four known-negative controls, so
owned PID 2791247 was stopped before the saved-answer batch dispatched. This
supersedes the planned full re-review above; no scale was launched. The user
requested a bounded reasoning comparison. New script
`scripts/dfm13_repochat_review_probe.py`, PID 2795848 at launch, compares thinking
on/off at 8192 output tokens on exactly two exposed negatives (RTree and OpenCV),
four requests total. Root:
`data/dfm13/repochat-review-thinking-controls-20261001`. Reviewer input separates
the original request, final answer and retrieved source, excluding generator
system prompts and harness reminders. The rubric explicitly disallows excusing
missing implementation because the task is complex. No exact-span requirements
remain. Fifteen reviewer/probe tests pass. Shared servers remain untouched.

## Readiness Results And Context Fix

The two-control comparison completed: thinking off and on both reject RTree
and OpenCV, but thinking on additionally identifies OpenCV's N versus N-1
indexing failure. A separate thinking-off check accepts both supported positive
controls, rejects the independent Bazel case, and falsely passes Invoice,
DXVK and Festival. Display fails operationally with context overflow. Therefore
three of four successfully reviewed known-negative cases are false passes;
production remains blocked. The independent cases are now exposed diagnostics,
not an untouched held-out accuracy estimate. No rubric was tuned on their text.

Display's context failure was measured via the existing server tokenizer:
ASCII-escaped JSON inflated input to 33768 tokens; equivalent UTF-8 JSON uses
10749. `scripts/dfm13_repochat_review_saved.py` now serializes losslessly with
`ensure_ascii=False`, preflights input plus 8192 output tokens against 32768,
and saves HTTP error bodies. No source or answer is truncated. A fresh small
thinking-on check of the same five cases plus two positives launched as PID
2801424 under `data/dfm13/repochat-review-readiness-thinking-20261001`.
The original answers and all prior results remain unchanged. No scale launch.

## Requirements-First Comparison

The user requested extraction of explicit requirements before the reviewer sees
an answer, followed by checking each requirement against the answer and source.
`scripts/dfm13_repochat_review_requirements.py` implements this in a separate
eight-case diagnostic root
`data/dfm13/repochat-review-requirements-20261001-v1` (PID 2803910 at launch).
Five deficient candidates and three independently assessed nontrivial supported
candidates are compared. The extraction stage sees only the original request;
the thinking-enabled verifier receives its requirements and has the existing
pinned native list/search/read tools, never execution or credentials. It checks
preservation constraints by comparing actual source, not generic similarity.
Six verification turns maximum, source hashes checked on reads, no answer
regeneration, no exact-span gate. Findings distinguish localized repair from
larger incompleteness; verdicts remain derived locally. Twenty-four focused
reviewer/requirements tests pass. There is one request per endpoint in this
small comparison, below the eight-per-endpoint ceiling even alongside the
separate five-case thinking check. No shared servers or training were changed.

## Completed Checks And Narrow QA Launch

The thinking-only five-case readiness check finished with four known-negative
false passes (Invoice, Bazel, DXVK, Festival), one output-length failure
(display), and both basic positives passed. Requirements-first finished with
the three nontrivial supported answers passed, DXVK rejected, Bazel and Festival
still falsely passed, and Invoice/display verification hitting output length.
The DXVK rejection also contains an unsupported assumption that coverage is
incomplete; a reject label does not make every finding correct. These outcomes
do not establish a reliable gate for complex code or exhaustive claims.

The user authorized a narrower quarantined QA experiment, conditioned on scoped
controls. In `data/dfm13/repochat-simple-qa-controls-20261001`, all three real
navigation/overview positives pass and both synthetic contradicted-source
negatives reject; two basic positive controls also pass. The real positives
are independently assessed in
`docs/reports/dfm13_repochat_trajectory_assessment_20261001.md`. These small,
exposed controls are not population-level precision evidence.

CPU lexical inventory produced 68 unused candidates. Manual whole-prompt scope
review excluded 21 mixed-intent, implementation/API, external-comparison or
exhaustive requests without rewriting their questions. Six additional
repositories failed public access or download-size limits: 1ffycat/FbkiBot and
mbramani/gem-track (401), DS4SD/docling, EpicGames/MetaHuman-DNA-Calibration,
continuedev/continue and robusta-dev/holmesgpt (size cap). No padding or unsafe
download-cap relaxation was used. Result: **41 tasks, 40 pinned repositories**.

`scripts/dfm13_repochat_simple_qa.py` launched PID **2815559** under
`data/dfm13/repochat-simple-qa-68-20261001-v1`; the name records the initial
candidate cap, not the final task count. `scope-plan.json`, `preparation.json`,
`ready.json`, `scope-readiness.json`, and `launch.json` preserve exclusions,
commits/hashes, test controls and process provenance. At the first live check,
161 request starts covered all eight endpoints and 122 rollout responses were
saved. Maximum eight requests per endpoint, native read-only tools, no new
servers. The reused rollout's legacy screen is explicitly not admission;
a separate thinking-enabled 8192-token review runs automatically afterwards
under `independent-review/`. Fresh manual sampling remains required before any
admission. No export/upload or complex-code scale is authorized by this receipt.

## Targeted Repairs

The user separately authorized additive repairs of three concrete failures.
`scripts/dfm13_repochat_targeted_repair.py` launched PID **2809552** under
`data/dfm13/repochat-targeted-repair-20261001-v1` using ports 8805-8807, one
request per endpoint. Original answers remain frozen and unsupervised; feedback
and original hashes are retained. Source checks confirm Invoice's existing JSON
parsing and changed CSS literals, Bazel's `${GFLAGS_TARGET}` and nested platform
header, and OpenCV's N versus N-1 indexing issue. CPU AST inspection additionally
confirms unused `low_freq`/`high_freq`; no generated code was executed.

First completed repair is Bazel: gflags, platform headers and cross-package
visibility are now included. Runtime/gflags labels are explicitly placeholders,
so this remains a scoped integration template, not a compiled/verified build.
Other repairs and independent assessment are pending. No new generic judge
tuning cycle or complex-code production was launched. Combined RepoChat CPU
tests: **85 passed**. All outputs remain `admission=false`.

Generation subsequently completed all 41 QA tasks; the independent thinking
audit is running. A fresh deterministic five-case manual sample is recorded in
the QA root's `manual-assessment.md`: two broadly supported summaries, two
qualification/local-repair cases and one clear incorrect claim. SillyTavern's
answer denies any static Google model list after reading only the dynamic
fetch helper, but pinned `public/index.html` contains `model_google_select`
with literal options. Facefusion correctly identifies the final output path
but conflates temporary merge output with final output. Real-ESRGAN's correct
discriminator location does not establish a general image-quality metric.
Thus scoped controls are not a population guarantee; no further scale or
admission follows automatically from this batch.

All three repair attempts are now terminal: Invoice and Bazel generated,
OpenCV hit output length before any verified native read. Invoice now preserves
JSX/styles through a handler-only patch but still overstates its stale-closure
guarantee. Both generated repairs are being independently reviewed by PID
2820506 under the repair root's `independent-review/`, using original requests
and new tool evidence without revealing repair feedback. Manual findings live
in that root's `manual-assessment.md`. No repository code was executed.

## QA Completion And Narrow Repairs

The 41-task thinking review completed: 38 structurally reviewed, comprising
36 pass labels and two rejections; three reviews failed output-length limits.
The legacy 41/41 screen is not a quality result. No rows are admitted.
An additional deterministic six-pass manual sample is recorded in
`data/dfm13/repochat-simple-qa-68-20261001-v1/manual-pass-assessment-20261001-v2.md`.
All six core descriptions have source support, with bounded qualifications for
Onlook implementation advice, Scratchpad efficacy claims, and opta_sd setup.
This does not erase the earlier clear SillyTavern false acceptance.

Parent relayed Boole's separate eight-answer check: six supported, substantive
XMOS grounding repair and minor WinUtil safety qualification. Additive runner
`scripts/dfm13_repochat_qa_repairs.py`, PID **2832232**, writes
`data/dfm13/repochat-qa-repairs-20261001-v1`. Both new answers completed and
fresh independent thinking reviews started. WinUtil removes the maximum-safety
guarantee. XMOS removes USB configuration but still needs qualification of its
external algorithm-source claim; a pass label cannot override that manual caveat.
Original answers, receipts and pinned implementations remain unchanged.

The 68 inventory was not 68 scope-approved tasks: 21 were mixed/complex and
six further repositories failed safe preparation, leaving 41 original attempts.
CPU-only preparation of the held 21 produced 18 snapshots and three size-cap
failures under `data/dfm13/repochat-remaining-68-20261001-v1`; that full mixed
batch was **not launched**. A second scope review admits only three prompts
to bounded descriptive diagnostics: LangGraph purpose/usage, NotDijkstra
purpose/example usage, and a non_empty_continuous use case. This supersedes
their earlier conservative scope hold, not the other exclusions.

`scripts/dfm13_repochat_qa_extension.py`, detached PID **2833004**, writes
`data/dfm13/repochat-qa-extension-20261001-v1`. Actual native-tool responses
were observed on ports 8800-8802. It automatically reviews saved answers with
thinking enabled, at most eight requests/server. Thus 44 original inventory
tasks are attempted/in progress, six originally eligible source failures remain,
and 18 remain scope-held. All outputs stay quarantined (`admission=false`);
no repository code execution, upload, server restart or training changes.
Combined focused CPU tests: **90 passed**.

### Next Descriptive QA Cohort

The two repair reviews are complete, both labeled pass; XMOS's manual caveat
still applies. The three-case extension is complete: two passes, one source-
insufficiency rejection (LangGraph). Manual inspection additionally qualifies
NotDijkstra convergence and catches overbroad non_empty_continuous conversion
claims; its checked constructors and missing NonEmptyVec repr attribute do not
support the blanket README-derived assurance. Details are in the extension
root's `manual-assessment.md`. All remain quarantined.

User authorized a bounded next cohort without further feedback. From 1,669
unused eligible-source prompts, 100 whole prompts were manually selected for
descriptive overview/source-reading QA, excluding code changes, exhaustive
audits, speculative comparisons and private context. New runner
`scripts/dfm13_repochat_qa_next.py` and three CPU tests preserve all historical
implementations. CPU snapshot preparation PID **2836045** writes
`data/dfm13/repochat-qa-next-20261001-v1`; unavailable/oversize repositories
remain explicit shortfalls, without replacement or relaxed safety caps.

Only the first eight source-ready tasks may run initially with native read-only
tools and independent thinking review. The remainder requires a separate
`manual-gate.json` bound to the ready receipt and evidence hashes. Manual checks
must verify source support and conditional claims rather than use reviewer pass
rate as a proxy. Generation retains the explicit instructions not to speculate,
not to infer exhaustive coverage, and to state limitations honestly. No private
repository context, code execution, automatic admission or server changes.

Preparation completed with **89 source-ready tasks and 11 access/size failures**
from the 100 selected prompts. The first eight were launched separately;
`first-launch.json` and `first-runner.log` preserve the detached client identity
and live requests. The remaining 81 are blocked on manual source assessment,
not automatically released by reviewer labels. Focused tests: **93 passed**;
OKF validation: zero errors/warnings. Prior three-case and two-repair reviews
are terminal before this new inference launch.

First-wave PID **2838750** completed generation and independent thinking review:
seven reviewed pass labels and one preserved `final_empty` generation failure
(linuxwacom). Positive controls passed. `first/boole-manual-sample.json` is the
eight-case independent assessment handoff, deliberately omitting model verdicts;
`first/manual-evidence-pins.json` pins 20 trajectory/snapshot/report artifacts.
Local inspection of all seven answers supports their core descriptions but
qualifies DeepClaude's implied accuracy benefit, scrcpy's USB-debugging rule
(OTG exception), and DCIL's segment termination description. It does not claim
an independent Boole assessment has occurred. See `first/local-manual-assessment.md`.
The remaining 81 stay gated pending the separate manual sample and scope
assessment receipts; no `manual-gate.json` release has been written.

The pending-receipt state above is superseded: Poincare's
`docs/reports/dfm13_repochat_next_source_assessment_20261001.json` verifies
**74 eligible, seven held** out of 81. Boole's
`docs/reports/dfm13_repochat_next8_gate_20261001.json` records six broadly
supported answers, one localized scrcpy OTG correction and one missing final,
and permits generation but not blanket admission. Both receipts, original
selection, snapshot commits and evidence file hashes were verified.

New `scripts/dfm13_repochat_qa_filtered.py` avoids changing the frozen all-81
runner. Exact eligible-ID filtering, provenance/hash checks, a pinned independent
manual gate, and the shared campaign lock protect launch. Detached PID **2851682**
runs only those 74 under `repochat-qa-next-20261001-v1/eligible-74`; parent root
`filtered-launch.json`, `filtered-manual-gate.json` and `filtered-runner.log`
record release and actual requests. Native responses were observed across all
eight endpoints. Maximum eight requests/server, independent thinking review,
conditional source claims, read-only tools and `admission=false` remain unchanged.
The seven held IDs are not queued through the legacy `rest` command.

User additionally authorized a narrow scrcpy OTG qualification repair and one
fresh Wacom retry. `scripts/dfm13_repochat_first_wave_followup.py`, detached PID
**2852442**, waits for the filtered run's completion and lock release (bounded
two hours), then runs both separately with fresh independent reviews. Root:
`repochat-qa-next-20261001-v1/first-wave-followup`; `queue.json` pins originals
and authorization, `launch.json` records exact process identity. Waiting avoids
exceeding eight requests/server through concurrent clients. Originals remain
unchanged; no automatic retries, admissions or shared-server modifications.

### Terminal Readiness Handoff

`scripts/dfm13_repochat_readiness_report.py` is CPU-only and refuses to publish
until both the filtered run and targeted followups have terminal receipts.
Detached watcher PID **2858437**, bounded three hours, writes under the campaign's
`readiness/` directory: `summary.json`, `fresh-manual-sample.json`, and
`parent-assignment-ready.json` requesting parent assignment to Boole. It samples
up to 12 new independent-review passes across overview, navigation and
implementation-explanation strata, with original prompts, answers, tool evidence,
trajectory hashes and pinned snapshot paths; model verdicts are omitted from
the manual packet. This cohort has English prompts, so non-English coverage is
explicitly a gap, not inferred from repository names or code language.

Readiness statistics distinguish generation failures, review failures and
semantic rejections; measure actual tool-bearing assistant turns, individual
tool calls/results/errors, and answer character/word distributions; and retain
the 11 source failures, seven scope holds and earlier known manual issues.
The watcher never admits rows or manufactures a readiness result on timeout.

User requested an immediate independent sample before terminal readiness:
`readiness/poincare-fresh-sample.json` contains 12 stratified cases from the
44 independent-review passes available at selection, not the legacy screen's
65 pass labels. `poincare-assignment-ready.json` requests parent assignment to
Poincare. It is an early frozen sample, not a complete-population estimate.

All 74 generations ended: 65 complete answers, seven `final_empty`, one output
length failure and one repeated identical listing cursor. Inspection of raw
responses found the seven empty finals had absent content but a populated
reasoning field (four textual outputs and three marker-only outputs); the
length failure also spent its 8192-token budget in reasoning. This is observed
API behavior, not a proven parser root cause. Reasoning is never promoted into
an answer. `failed-nine-finalization/cause-inspection.json` pins the evidence.

User authorized one additive attempt for exactly these nine failures. New
`scripts/dfm13_repochat_failure_finalization.py`, queued PID **2863775**, waits
for the earlier followups, preserves the 65 complete generations, and requests
a typed final answer from original prompts and verified source observations.
It performs additional bounded CPU source reads, uses thinking-enabled output,
fails closed on budget/empty/non-stop output, and independently reviews each
result. These derivative artifacts are explicitly review-evidence packets,
not replayable native conversations or admitted training rows.

The CPU readiness watcher was stopped by verified owned identity to fix a
string-versus-bytes hashing bug, then restarted as PID **2863776** with additive
`readiness/launch-v2.json`; old receipt preserved. It now waits for the nine-case
review as well. Shared inference processes and frozen campaign code were not
modified. Focused source-read/failure-selection tests pass.

### Manual Holds Supersede Pass Labels

`docs/reports/dfm13_repoqa_pass_manual8_20261001.md` and its pinned JSON under
`data/dfm13/repoqa-pass-manual8-20261001-v1/` found three retain cases, three
confirmed localized errors (Agnai entrypoint, IDSHV routing algorithm, OneCode
option keys), and two grounding concerns (OS_32Bit isolation and DINOv2 spatial
features). This sample was selected from the legacy 65-pass population, not a
claim that all 65 passed the newer independent thinking review.

User prohibits further scale until checks improve. New CPU helper
`scripts/dfm13_repochat_manual_claim_repairs.py` writes five exact answer and
trajectory hash holds under `manual-claim-repairs/holds.json`, three additive
localized correction drafts, and a claim-to-source verification handoff.
Original artifacts remain unchanged and **no hold is cleared**. Exact source
text/hashes accompany each hold. Agnai's separate Redis-location rejection also
remains unresolved by the entrypoint correction. OneCode's documented options
and Infinity default were independently checked against
[official Socket.IO v4 documentation](https://socket.io/docs/v4/client-options/).

The technical nine-case queue remains authorized; semantic held cases are not
silently added to it. Future validation must compare concrete claims to exact
source and fresh controls, not rely only on a general positive review. Latest
CPU readiness watcher PID **2869663**, receipt `readiness/launch-v3.json`, includes
these hash-bound holds and `further_scale_allowed=false`; preceding owned CPU
watcher was stopped by exact PID/start-time verification, never a shared server.

Both first-wave followups completed and independently passed: scrcpy now
explicitly states the OTG debugging exception, and Wacom produced a complete
fresh answer. The nine-case finalizer initially encountered a CPU packaging
error for a tool-only failed trajectory (`StopIteration` from assuming a final
assistant existed). No completion request was submitted in that failed preflight.
Its ready receipt was archived as `ready-preflight-failure.json`, with
`preflight-fix.json` recording hashes and evidence. Direct original-request/tool-
evidence packaging now passes tests against all nine actual failures.
Relaunch PID **2877239**, `failed-nine-finalization/launch-v2.json` and
`runner-v2.log`, submitted all nine requests across ports 8800-8807. Each remains
one bounded technical attempt followed by independent review; original 65
completed generations and the five semantic holds are unchanged.

### Practical Candidate And Claim Checks

The three localized correction drafts now have a complete independent manual
packet with original questions, new answer hashes, source text/hashes and known
residual issues: `manual-claim-repairs/independent-manual-packet.json`, with
`independent-manual-assignment-ready.json` requesting parent assignment. No
independent human verdict on these new hashes has been asserted. Original hashes
remain held even if a later corrected hash is cleared.

New `scripts/dfm13_repochat_claim_checker.py` fixes one eight-case pilot before
execution: three original false claims, their three corrected claims, and two
source-grounded good controls (CoinCalc purpose and heatmap IDW). Expected labels
are omitted from model requests. It evaluates claim-to-source support, not broad
answer positivity; no repeated rubric tuning or exact-span contract. Queued PID
**2880558** waits for the technical nine-case review, then uses one request per
endpoint. Root `claim-checker-pilot/` pins controls and rubric. These exposed
diagnostics are not a population precision estimate and cannot clear whole-answer
holds or authorize admission.

CPU writer `scripts/dfm13_repochat_filtered_candidates.py`, PID **2881245**,
waits for terminal readiness, then writes `filtered-candidates/candidates.jsonl`
and a sealed manifest. It retains original independent-review passes excluding
the exact held answer/trajectory hashes; all non-passes are excluded. Every row
is explicitly `filtered_candidate_not_admitted`. Correction drafts and derivative
technical-retry evidence packets remain separate pending suitable validation;
no broad-corpus perfection claim or automatic admission is required to produce
this useful filtered candidate artifact.

All nine technical finalizations completed and independently passed review;
scrcpy and Wacom followups also passed. Terminal readiness artifacts are present.
Original74 accounting remains 58 independent passes, four rejections, three
review failures and nine original generation failures; retries are additive,
not retroactive changes to those counts. Actual original74 totals: 280 tool
turns/calls, four tool errors, median three turns (p90 seven, max14); median
answer length 1,813 characters/254 words, with incomplete answers counted as
zero. Eleven snapshot failures and seven scope holds remain explicit.

`filtered-candidates/candidates.jsonl` is complete with **55 unadmitted original
candidates**, excluding 19 non-pass/held cases. Three of the five manual holds
intersected the 58-pass pool; the other two were already non-passes. The nine
technical retry packets and three localized drafts remain separate. No upload,
training integration or admission occurred.

The fixed claim pilot completed **8/8 expected verdicts**: three original false
claims rejected, three corrected claims supported, two good controls supported.
`manual-claim-repairs/new-hash-claim-validation.json` binds each corrected answer
hash to its narrow claim verdict. Original holds remain; whole-answer manual
adjudication is pending, especially Agnai's separate Redis issue. This exposed
diagnostic result is not a calibrated whole-corpus precision claim.

`readiness/fresh-manual-sample-v2.json` provides 12 further stratified candidates
from a pool of40 after excluding prior sampled IDs and held/non-pass candidates.
`parent-assignment-ready-v2.json` requests independent assignment; all prompts
are English, so no non-English stratum is claimed. The earlier packets remain
preserved rather than overwritten.
