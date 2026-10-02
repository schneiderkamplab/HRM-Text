---
type: Runbook
title: Multilingual Calibration V6 Client
description: Parent-operated immutable calibration inputs and bounded borrowed-endpoint clients after indexed-review and generation repairs.
status: draft
last_updated: 2026-09-27
confidence: high
---
# Multilingual Calibration V6

**2026-09-27 diagnostic update:** controlled streaming and CPU benchmarks now
identify custom compact/bounded grammar problems beyond shared server load.
See [Generation Grammar Diagnosis](dfm12-generation-grammar-diagnosis.md).
Do not blindly restart the unchanged calibration contract.

## Per-Server Concurrency

On 2026-09-27 the user explicitly requested 32 concurrent requests per server.
`--concurrency-per-server 32` now creates 32 workers per assigned endpoint and
sets matching HTTP connection limits; the default remains one. Ports8600--8603
handle reviews and8604--8607 handle generation. Actual concurrency is bounded
by remaining work. Queue ownership and atomic per-case records prevent duplicate
case dispatch; 31 tests pass, including queue/resume tests at concurrency1 and32.

The timeout600 recovery also exhausted its four generation endpoints. Its four
timeout records were archived under `recovery/1790514441045883971/` before this
explicitly requested retry. Completed outcomes and semantic failures remain.
Only runner/test hashes changed, with old manifest/seal and a change receipt
retained. The new log is `client-concurrency32.log`. Shared server configuration
and foreign processes are unchanged. Greater concurrency is not evidence that
individual request timeouts are fixed; monitor the resulting throughput.

## Reporting Crash Recovery

Live slowdown snapshot after recovery: borrowed endpoints reported 184--195
running requests each, zero waiting, and 81--93% KV-cache usage. Four calibration
generation calls had about 470 seconds elapsed, 823--981 prompt tokens and a
4096-token output allowance. The client receives non-streaming responses, so
these observations do not distinguish per-request decoding from grammar
preparation or another server-side stall. Shared load and serialized generation
(one request per generation endpoint) constrain throughput; zero waiting does
not imply spare compute. Do not attribute the entire latency to contention
without per-request evidence.

Supersedes the running-resume claim below on 2026-09-27: PID3723947 crashed
when a generation failure stored `structure_valid: null` and the summary tried
to sum it. Explicit-true counters now handle nullable validity fields; all 30
calibration tests pass, including the new regression test. Semantic decisions,
prompts, and generation/review contracts are unchanged.

Under the exclusive run lock, the original manifest/seal and seven transport
failure stage/outcome records were archived in
`recovery/1790513525490313307/`. Its receipt records the old/new hashes of only
the runner and its test file. All other pins were verified unchanged before
resealing this explicitly authorized bug-fix recovery. These seven uncertain
transport attempts may have consumed inference already; retrying them is an
explicit recovery decision, not evidence they were never executed. Completed
reviews and semantic-invalid generations were retained. The resumed client is
PID3727232, `client-recovered.log`, request timeout600 seconds. No server or
training process was signalled. This is a recovery in progress, not a completed
or passed calibration.

## Timeout Diagnosis And Resume

PID3706773 exited normally with `phase=blocked_infrastructure`, not a traceback.
Four generation calls timed out after 180.20--180.58 seconds, one on each of
8604..8607. All four raw response receipts have `TimeoutError()`, null HTTP status,
and empty body. The client conservatively marked them `abort_status_unknown`,
opened each affected endpoint circuit immediately, and retired all four generation
workers. Separate review workers completed their queue; then the client exited
with 100 pending generation cases. This is the exact observed stop mechanism.

Affected IDs: `d2151e60...` (NB bullet summary, 8607), `8a1a7d04...`
(NB formal rewrite, 8606), `0e77a4c9...` (NB change requirements, 8605),
`11c1f05e...` (NB clarify ambiguity, 8604). Their complete IDs/specs and raw
receipts remain under `stages/`, `items.json`, and `raw/`. Empty non-streaming
bodies do not establish whether requests were queued, compiling grammar,
decoding, or completed after client cancellation. No server OOM/crash is proven.
Read-only server inspection showed continued successful requests and a GPU4
Triton bitmask-kernel compilation warning at12:35:28, but no request-ID linkage
establishes it as the cause. At diagnosis the eight servers reported146--156
running requests each and zero waiting; shared load is a possible contributor,
not a proven per-call root cause.

Before resuming, all 100 missing case IDs were checked against every saved raw
request: **zero had ever been sent**. All implementation/input pins still matched;
all eight endpoints again reported the exact teacher and16384 context. Original
summary snapshots are `status-before-resume-600.json` and
`report-before-resume-600.json`. Completed controls and terminal failures,
including all four unknown aborts, are not retried.

User authorized safely finishing missing infrastructure-blocked work. Launched
the existing pinned runner with `--request-timeout 600` (already supported),
unchanged `--deadline 21600` and the same eight bounded clients. Resume PID
**3723947**, log `client-resume-600.log`, same root. No code/manifest/request
mutation, no server restart, and no foreign signal was used.

Control result before resume: 242 recorded,239 valid reviews and3 invalid;
224 semantic agreements,6 false accepts,9 positive rejections,36 dimension
mismatches. Deterministic checks raise effective agreements to230, which must
not be presented as reviewer-only reliability. Generation was6 valid,2 invalid
outputs,4 unknown aborts,100 missing. Calibration is not passed and full35K
generation/admission remains blocked regardless of this resume.

## Live Launch, 2026-09-27

User explicitly authorized running the pilot and assigned this agent sole launch
ownership, superseding the earlier parent-only launch handoff below. Launched
the prepared root `data/dfm12/multilingual-calibration-v6-20260927` detached with
`setsid`; live client PID **3706773**, log `client.log` inside that root.
All prepared pins passed immediately before launch. All eight borrowed endpoints
8600..8607 reported the exact authorized Gemma teacher and 16384 context; their
full model/context receipts are retained in timestamped `health-*.json`.
No servers or GPU allocations were created, no foreign processes were signaled,
and the old 700-case quarantine was left unchanged.

Verified at client elapsed 52 seconds: **25 raw requests, 17 raw responses**,
covering all eight endpoints. Requests comprised 14 review and 11 generation
calls. Outcomes: ten valid control reviews, six assembled generation candidates
awaiting content review, and one invalid generation output; eleven terminal
outcomes, seventeen recorded. The first generation failure was
`GenerationFailure('empty_or_punctuation: 0.user')`, preserved after one attempt
with its raw response, not an infrastructure retry or silently repaired output.
These are launch-progress snapshots, not final quality results.

This run is the bounded **242 exposed controls plus 112 generation cases**
calibration/pilot. It is **not full 35K generation**, calibration is not yet
declared passed, and admitted rows/tokens remain zero. Monitor `status.json`,
`report.json`, `stages/`, `outcomes/`, and `raw/` for subsequent progress.
The command under Commands describes the launched client; do not run a second
copy while PID3706773 holds the root lock.

## Handoff State

Update after user authorization to continue CPU preparation: the input bundle
`data/dfm12/multilingual-calibration-v6-inputs-20260927` and immutable run root
`data/dfm12/multilingual-calibration-v6-20260927` are now prepared. All 242 controls
and 112 generation cases passed preparation. Three overlong translation source
candidates were rejected before sealing and replaced deterministically; their
exact reasons are recorded in `selection.json`. No sealed case was dropped.
The final combined suite passed 185 tests with two dependency warnings. All
prepared pins were independently rechecked. No live calibration was launched;
the parent owns `run` using the command below. The saved actual eight-endpoint
receipt used was the preceding infrastructure-retry run's
`borrowed-endpoint-verification.json`; every endpoint is rechecked at launch.

This supersedes the earlier unprepared handoff status in the next paragraphs.

Implemented `dfm12/multilingual_calibration_v6.py` and its dedicated tests.
No live input bundle or run root has been built by this agent. No endpoint
request, GPU allocation, server action or inference launch was performed.
The parent owns preparation and launch after adapter owners finish integration.
Existing [calibration results](dfm12-multilingual-calibration.md) remain unchanged.

Earlier CPU integration verification: 184 tests passed across v6, generation-v4,
indexed review and native tool dialogue, with two dependency deprecation warnings.
Receipt: `data/dfm12/multilingual-calibration-v6-tests-20260927.xml`.
The suite includes mocked full-queue execution/resume, raw-before-parse capture,
duplicate/nonfinite JSON rejection, context limits, unknown aborts, retry caps,
endpoint circuit breaking, source-selection exclusions and no admission.
These tests do not establish live model quality or successful real-source preparation.

## Owner Interfaces

- Harvey `01a0d229-6105-72b3-9f0c-14859405bfc0`: indexed `request(record)`,
  `keeps(review, record, deterministic=False)`, `deterministic_checks(record)`.
- Tesla `01a0d229-e148-71d3-985c-252d58faf43a`: non-tool generation-v4
  `request(spec, endpoint_models=actual_models_documents)`,
  `decode(spec, original_content, finish_reason)`, `assemble(spec, result)`.
- Poincare `01a0d277-f35a-71f2-a233-c9a32bd766af`: native tool path in
  `multilingual_tool_dialogue.py`, contract `native-tool-dialogue-v4-localized-final-v2`.

No direct messaging tool was available; interface updates were relayed through
the parent. Other owners' files were not modified. Existing explicit generation
and indexed-review grammars survive unchanged; tool response schemas receive
compact grammar transport while original schema checks remain on CPU.
Raw completion text is strictly parsed without normalization/repair; non-tool
generation additionally receives that exact text through Tesla's decoder.

## Prepared Coverage

`build-inputs` requires all seven seed files plus OpenHermes seeds and a saved
actual `/v1/models` document. One previously checked endpoint receipt is enough
for CPU preparation; launch independently verifies all eight endpoints.
Never manufacture a receipt from the expected model name/context.

The builder preserves all 242 routed controls byte-semantically, including their
records and ground-truth labels: 120 expected keeps and 122 expected rejections.
Prepared run items retain original split metadata but report every control as
known/exposed regression, not fresh labels or native-language gold.

Generation coverage is exactly 112 specifications: six tool subtypes for each
of NB, NN, IS, FO, NL, SV and PL (42), plus two examples per non-tool family per
language (70). Every non-tool subtype is represented across the combined pool,
not every subtype in every language. The five non-tool families are grounded
instruction, summary/rewrite, multi-turn, OpenHermes and math/code.

Selection is deterministic and bounded to 50 candidate slots per requested
language/family/subtype. Oversize/invalid sources are rejected before sealing;
every rejected slot/reason is in `selection.json`. No source is truncated.
Missing coverage fails preparation; nothing is silently dropped after sealing.
External custom spec bundles may contain 70..140 non-tool cases, but must satisfy
the same coverage checks and carry a matching selection receipt.

## Commands

Run from `/work/mimir/HRM-Text` with CPU thread bounds. The paths below are proposed
new roots, not already prepared artifacts. `MODELS` must point to the parent's
saved actual models response. Parent reruns tests after adapter changes.

```bash
export PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=2
PY=/home/ucloud/miniforge3/envs/hrm/bin/python
MODELS=data/dfm12/multilingual-quarantine700-20260927-infra-retry-v1/borrowed-endpoint-verification.json
INPUTS=data/dfm12/multilingual-calibration-v6-inputs-20260927
ROOT=data/dfm12/multilingual-calibration-v6-20260927
TESTS=data/dfm12/multilingual-calibration-v6-tests-20260927.xml

$PY -B -m pytest -q -p no:cacheprovider --junitxml="$TESTS" \
  tests/test_dfm12_multilingual_calibration_v6.py \
  tests/test_dfm12_multilingual_generation_v4.py \
  tests/test_dfm12_multilingual_review_indexed.py \
  tests/test_dfm12_multilingual_tool_dialogue.py

$PY -B -m dfm12.multilingual_calibration_v6 build-inputs \
  --root "$INPUTS" --seeds-root data/dfm12/multilingual-pilot-20260926-v3 \
  --endpoint-models "$MODELS"

$PY -B -m dfm12.multilingual_calibration_v6 prepare \
  --root "$ROOT" --controls "$INPUTS/controls.json" \
  --specifications "$INPUTS/specifications.json" --tests "$TESTS" \
  --endpoint-models "$MODELS"

$PY -B -m dfm12.multilingual_calibration_v6 run --root "$ROOT" \
  --endpoints http://127.0.0.1:8600/v1 http://127.0.0.1:8601/v1 \
  http://127.0.0.1:8602/v1 http://127.0.0.1:8603/v1 \
  http://127.0.0.1:8604/v1 http://127.0.0.1:8605/v1 \
  http://127.0.0.1:8606/v1 http://127.0.0.1:8607/v1 \
  --request-timeout 180 --deadline 21600
```

Preparation refuses existing roots and requires passing test XML containing all
four suites. `manifest.json` pins input selections, seeds, controls, actual teacher
tokenizer/template, student tokenizer/template/metadata, tests and explicit relevant
implementation files. `seal.json` pins the manifest. Unrelated DaLA/export modules
are not pinned. No dependency is changed to accommodate a prepared run.

## Execution And Resume

Only existing local endpoints 8600..8607 are allowed, exact model
`google/gemma-4-26B-A4B-it`, each advertising at least 16384 context. Teacher
tokenizer default is the cached snapshot `4d7ae4984b7db7de8f8457170b3f1a419ee76d52`.
The client uses the actual local chat render with thinking disabled and counts
full prompt plus output reserve, including indexed review evidence. No truncation,
no fake larger context and no legacy 8192-token measurement in this runner.

Four clients on 8600..8603 drain controls and generated-content reviews; four on
8604..8607 handle generation. One request per endpoint maximum. A slow generation
endpoint does not hold the review queue. Endpoint timeouts open that endpoint's
circuit instead of consuming all remaining rows. All-eight model/context preflight
must pass before any inference request. Health receipts are timestamped on every run.

At most three infrastructure retries per stage (four attempts total), and three
consecutive explicit infrastructure failures open an endpoint circuit. Only proven
pre-connect failures or explicit HTTP 429/503 rejections are retryable. HTTP 502/504,
timeouts, transport failures after connection, or interrupted in-flight calls are
`abort_status_unknown`; they are never automatically retried. Invalid JSON, length
stops, schema violations and semantic failures are not infrastructure retries.
Other HTTP rejections close that endpoint circuit and remain `http_rejected`,
not purported model-quality failures.

`stages/` persists request hashes, attempts, raw content/finish/usage, decoded output
and terminal state. `raw/` preserves request payloads and bounded full HTTP bytes
before parsing. `requests/` records payload/schema and actual prompt counts;
`candidates/` and `outcomes/` preserve assembly and assessment. `report.json` and
`status.json` provide progress, current client PID, pending rows and circuit state.

The CLI holds a ten-second-timeout root lock throughout execution. Repeating `run`
resumes pending proven-infrastructure work; completed stages and terminal unknown
outcomes are not reissued. Resume first verifies every pin. A failed/incomplete
stage does not authorize editing or resealing the original run.

## Interpretation

Reviewer semantic agreement, false accepts, positive rejections, invalid outputs,
dimension mismatches and deterministic vetoes are separate. Deterministic checks
also survive invalid reviewer outputs. Generation JSON validity, schema/content
validation, assembly and later semantic judgments are separate diagnostics.
Non-tool generation additionally separates schema validity from adapter text and
content-constraint checks; neither is a claim of factual correctness. Tool text
checks remain in schema/assembly and semantic review, not the non-tool-specific
content-constraint counter. Keep raw failure codes for finer investigation.

All reports have zero admitted rows/tokens, admission and bulk authorization false,
and no automatic successor. No result can launch 700/35K generation or modify
training. Parent owns any next decision and central wiki/index coordination.
