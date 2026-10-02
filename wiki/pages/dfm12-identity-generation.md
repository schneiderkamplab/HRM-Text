---
type: Runbook
title: DFM12 Identity Generation
description: Isolated nine-language identity generation and pilot quality audits on shared Gemma endpoints.
tags: [dfm12, identity, generation, audit, provenance]
status: draft
last_updated: 2026-09-25
confidence: high
---
# DFM12 Identity Generation

## Scoped Bulk Identity Audits: 2026-09-25

**Supersedes the earlier bulk-audit hold below for this frozen cohort only.**
The user explicitly authorized auditing the existing identity generations.
Generation finished with **8,931 done**, **69 failed**, **179 duplicates**,
**177 completed pilot audits** and **8,575 staged bulk audits**. No failed
generation was retried or reset by this operation.

Pilot review covered all nine languages, including multi-turn historical-v1
versus current-XL backpropagation questions. The **176 keeps / one rejection**
are not treated as native-speaker certification: the rejected Faroese limitations
answer contains broken phrasing, while a kept Icelandic example has questionable
technical terminology despite perfect judge scores. This uncertainty is recorded,
not silently promoted to a human quality approval. Review findings and exact
pilot evidence are in `bulk-pilot-review.json` and `bulk-pilot-snapshot.json`.

`bulk-audit-authorization.json` records user-authorized **automated identity
auditing only**, no human/native-speaker approval, no regeneration, no accepted
exports. It pins the exact cohort IDs and payload hashes, pilot-review hash,
fact registry and student-template pin. Activation changes only the existing
`audit-review-pending` stage to `audit-bulk`, retaining IDs, payloads and retry
history. Resume verifies the same cohort rather than adding work. Bulk workers
claim and recover leases only for `audit-bulk`; generation and pilot rows are
not touched. The student tokenizer/template hashes remain enforced on resume.

Detached bulk client PID **2011630** uses existing ports **8400..8407** with
**16 workers per endpoint**, 128 total and one SQLite broker. No server restart,
main audit modification, export, upload, W&B logging or final sampling occurred.
Verified running evidence: **394 completed bulk audits**, 126 running and 8,055
pending, with successful completions on every endpoint. These are progress counts,
not final acceptance totals. Existing 8,931/69 generation counts remained unchanged.

All artifacts below are under `data/dfm12/identity-9000-20260924-v1/`:

- `bulk-process.json`: exact detached launch command and PID.
- `bulk-runner.log`, `bulk-runtime.json`, eventual `bulk-completion.json`: execution.
- `bulk-before.json`, `bulk-verification.json`: generation/pilot integrity checks.
- `bulk-audit-authorization.json`: scoped, pinned operation authorization.

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.identity_gpu \
  --output data/dfm12/identity-9000-20260924-v1 --concurrency 16 \
  --authorize-bulk-audit \
  --pilot-review data/dfm12/identity-9000-20260924-v1/bulk-pilot-review.json \
  --endpoints http://127.0.0.1:8400/v1 http://127.0.0.1:8401/v1 \
  http://127.0.0.1:8402/v1 http://127.0.0.1:8403/v1 \
  http://127.0.0.1:8404/v1 http://127.0.0.1:8405/v1 \
  http://127.0.0.1:8406/v1 http://127.0.0.1:8407/v1
```

**Eight identity tests passed**, including scoped/idempotent activation,
tampered-review rejection and preservation of generation rows during bulk lease
recovery, alongside the existing training-template pin and generation tests.

The user explicitly authorized **1,000 generation requests each** for EN, DA,
NL, NB, NN, SV, IS, FO and PL: **9,000 requests**, not 9,000 accepted records.
This run uses the existing eight `google/gemma-4-26B-A4B-it` endpoints on
8400..8407, at **16 concurrent requests per endpoint** total across generation
and identity-pilot audits. It starts no servers, changes no full-audit/export
process, performs no final sampling and logs nothing to W&B.

The selected profile is `xl-full-bp` from `dfm12/identity_facts.yaml`: 16 layers
in each L/H module, two H cycles with three L cycles each, full backpropagation
through this profile's module passes. Historical v1 facts remain explicitly
historical. Names, organizations and training-team facts come from the registry,
not inferred affiliations. The registry is copied and hashed in the run.
See [DFM12 components](/pages/dfm12-components.md) for the established contracts.

## Run and Gates

Generation completed on 2026-09-24: 8,931 successful requests, 69 exhausted
failures, and 179 exact duplicate conversations removed. This leaves 8,752
unique conversations: 177 pilot audits done and 8,575 bulk audit jobs staged
but gated on pilot review. `completion.json` is the authoritative receipt;
the generation client exited normally. No accepted identity export yet.

Implementation: `dfm12/identity_gpu.py`, reusing `identity.requests`, `jobs.Queue`,
the independent fact-grounded audit prompt and the project training renderer.
The isolated run is `data/dfm12/identity-9000-20260924-v1/`. Exact argv/PID are in
`process.json`; output is in `runner.log`, status in `runtime.json`, and SQLite
preserves requests/results/events. `enqueue.json` verifies exactly 1,000 per
language. All **180** original unexecuted generation-pilot job IDs occur within
these 9,000; the old queue remains untouched and has no newly launched client.
`legacy-pilot-id-reuse.json` records that check. There are not 9,180 new requests.

`authorization.json` records user-authorized staged generation only, separate
from training acceptance and from pilot approval. No `pilot-approval.json` is
fabricated. Slots 0..19 per language get independent `audit-pilot` jobs after
valid generation; other generations get `audit-review-pending` jobs that these
clients never execute. Bulk identity quality auditing requires actual pilot
review. All generated examples require quality audit before export. Full turns,
profile and fact-registry context survive; exact chat duplicates are tracked
separately and do not receive duplicate audit requests. One broker owns SQLite.

## Training Template Incident

Initial client **1688248** used the cached teacher serving template with the
shared student renderer. Its assistant-prefix check returned `None`, surfaced
as the misleading `rendered_context_does_not_fit` even on tiny conversations.
The identical short Q&A failed that setup but rendered as **29 tokens** using
`data/sampled_dfm11/metadata.json`'s `tokenizer_info`. This was infrastructure
failure, not evidence that generated conversations exceeded context.

Only the identity client was asked to drain. The corrected client loads the
existing pinned training template under `data/dfm11_tokenizer`; no global
tokenization/template code or Mistral regex was changed. The integration test
uses the real pinned template. **Five tests passed**, covering exact request
counts/profile, full turns/facts, duplicate handling, pilot/bulk-audit isolation,
and successful real training-template rendering. A real one-request generation
smoke test is required before bulk resumption. Infrastructure recovery must
record affected IDs and prior attempts/errors, and must not reset unrelated
malformed-JSON or other model failures indiscriminately.

## Verified Recovery and Active Run

The real smoke generation succeeded in Danish, with **589 rendered training
tokens**, and was committed to the existing 9,000-job queue before bulk resume.
`training-template-smoke.json` retains the actual messages and validation.
`training-template.json` pins tokenizer, template and metadata SHA-256 hashes;
future resume refuses changes rather than overwriting the receipt. A copy of the
student template is retained as `student-chat-template.jinja`. The fifth test
explicitly verifies this fail-closed resume behavior.

`template-recovery.json` identifies exactly **230** rows whose last error was
the wrong-template `rendered_context_does_not_fit`, preserving their **713 prior
attempts**, original statuses and errors. Only those rows had their retry budgets
restored. Existing event history remains, with explicit infrastructure-recovery
events appended. Two unrelated malformed-JSON failures were left unchanged.
No server, full-audit queue or exporter was stopped or modified.

Resumed detached client PID: **1694370**, with exact command in `process.json`;
new output is `runner-resume.log`. Original argv/PID is preserved in
`process-before-template-fix.json`. Verified after resume: **116 generation
completions**, successful generations on **all eight endpoints**, and **106
completed independent pilot quality audits**. These are progress counts, not a
claim of 1,000 accepted conversations per language. The scoped generation
authorization remains separate from actual identity pilot review and acceptance.

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.identity_gpu \
  --output data/dfm12/identity-9000-20260924-v1 \
  --concurrency 16 --authorize-9000-staged-generations \
  --endpoints http://127.0.0.1:8400/v1 http://127.0.0.1:8401/v1 \
  http://127.0.0.1:8402/v1 http://127.0.0.1:8403/v1 \
  http://127.0.0.1:8404/v1 http://127.0.0.1:8405/v1 \
  http://127.0.0.1:8406/v1 http://127.0.0.1:8407/v1
```

Use this command only to resume after the active client exits; `.run.lock`
prevents a second client in the same snapshot. The coordinating parent should
index this focused page; central status/index files were not edited here.
