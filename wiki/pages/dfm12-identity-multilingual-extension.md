---
type: Runbook
title: DFM12 Identity Extension Across 21 Languages
description: CPU-prepared accepted-quota identity queue with corrected retained data, sealed exclusions and explicit activation coordination.
tags: [dfm12, identity, multilingual, queue]
status: draft
last_updated: 2026-09-29
confidence: high
---
# Identity Extension Across 21 Languages

## Completed, 2026-09-29

Generation and independent automated audit completed: **31286 new accepted**
plus **10714 retained** conversations, exactly **2000 per language across all
21 languages (42000 total)**. All active counts are zero and the runner exited.
Terminal non-accepted candidates: 820 duplicates, 1790 failed, 682 invalid,
225 audit-rejected. These are excluded from the accepted totals. Completion
receipt: `runs/1790654301-1046944-30232871/completion.json` under the prepared
root. This completes generation/audit, not packaging, publication or training.

## Completed-Queue Publication, 2026-09-29

**Completed:** all **21 public repositories / 42,000 conversations** uploaded
and remotely verified, exactly 2,000 rows per language. Nine existing identity
repositories were updated and twelve created. Completion time: Unix
1790657709.904658. `upload-completion.json`, `upload-receipts.json`, and
`final-receipt.json` under the authoritative export root record all revisions,
remote row counts, receipt hashes and test results. This supersedes earlier
publication-pending statements; no training integration was performed.

The user explicitly authorized export and upload of the completed 21-language
queue. `dfm12/export_identity_multilingual.py` builds a fresh accepted-only export
at `data/dfm12/identity21-export-20260929-v1`, without changing existing local
exports. Export/upload PID 2470359 (create time 1790657484.41) uses cached HF
credentials without recording secrets. Its log is
`data/dfm12/identity21-export-20260929-v1.log`.

**Authoritative local export for this extension:**
`data/dfm12/identity21-export-20260929-v1`. The older identity packages under
`exports_dfm12/` remain historical, unchanged source artifacts with smaller row
counts. Do not silently train from or republish those old packages as the new
2,000-per-language extension. This task does not register the new export in a
training catalog, alter sampling, or integrate it into a training pipeline;
that is separate explicit work.

Targets are the explicitly authorized
`schneiderkamplab/dfm12-identity-xl-full-bp-{language}` repositories: nine existing
repositories updated and twelve added. Existing card license fields are preserved;
the historical user-authorized generated-identity release policy is not replaced
with an invented blanket license. Updates use `parent_commit` revision guards.
Prior cards and a consistent queue snapshot remain local under `private/`, never
uploaded. Obsolete package files are replaced in the new repository revision;
previous revisions retain repository history.

Only native full-message training rows enter `data/`. Retained DA/EN rows are
explicitly labelled `corrected_v4_local_curated`, not all teacher-audited.
Other retained rows are labelled `retained_audited_original`, while new rows are
`new_automated_identity_audit`. Metadata contains per-record provenance, actual
new audit decisions, factual/runtime authority and source/content hashes.
No heldout, failed, invalid, duplicate or rejected queue candidates are exported.
The dedicated validator checks counts, schema, language, unique IDs and
conversation fingerprints, per-row provenance, audit keeps and file hashes.

`upload-receipts.json` records old/new revisions and per-repository verification.
Every file is downloaded at its committed revision and hash-compared; the remote
training file is parsed and independently checked for 2,000 unique conversations.
`upload-completion.json` is written only after all 21 repositories verify.
Combined exporter, queue, runner and legacy identity tests: **40 passed**.

## Live Runner, 2026-09-29

**Supersedes the preparation-only hold below.** The user explicitly authorized
launch and then overrode 32 clients/server with **512 per shared server**,
4,096 concurrent HTTP requests maximum over ports 8600 through 8607.
`dfm12/identity_multilingual_runner.py` launched detached as PID **1046944**
(create time 1790654300.74). All eight endpoints reported the expected Gemma
model with 16,384 context before activation. No server was restarted, stopped,
or owned by this runner; joint-production processes and code were untouched.

The sealed queue module, manifest and implementation pins were not edited.
`runner-authorization-512.json` records the explicit user override, runner hash,
manifest hash and identical before/after queue-module hashes. A narrowly scoped
runner-local activation transaction honors that receipt without changing the
legacy queue module's 32-client ceiling. Do not use its legacy `activate` CLI
to replay this 512-client authorization.

One executor thread owns SQLite and the pinned `NativeRenderer`; four separate
file-I/O threads write complete response/error receipts off the HTTP event loop.
Only `finish_reason=stop` responses are parsed with existing `response_json`
and submitted through the existing queue's `submit` contract. Incomplete and
transport failures use `fail`, never fabricated successful completions. Audits
remain prioritized. SIGTERM/SIGINT stops new generation claims, lets in-flight
generation finish, and drains its audits; no shared server signals are sent.
The queue flock prevents concurrent identity consumers. Interrupted running
rows fail startup pending explicit reconciliation rather than being replayed.

Receipts under the prepared root:

- `runner-process.json`: detached PID/create-time/argv and test count.
- `runner.log`: acceptance events and operational errors.
- `runner-current.json`: active run directory.
- `runs/1790654301-1046944-30232871/launch.json`: pins, endpoint health and baseline.
- The run directory's `runtime.json`, `responses/`, `errors/`, and eventual
  `completion.json`: live ledger statistics and per-stage response evidence.

**34 CPU tests passed** across runner, queue and existing identity contracts,
including explicit 512 authorization, rejection above 512, unchanged sealed
module, response completeness, and generation-stop/audit-drain behavior.

Live launch verification at Unix 1790654403 recorded **3,809 new accepted
conversations across all 21 languages**, 2,291 active candidate slots and 6,379
attempts. Original 10,714 retained conversations and all frozen pins remained
unchanged. `launch-verification.json` pins the first accepted generation/audit
response pair, each with `finish_reason=stop`, plus exact process identity.
The subsequent `endpoint-failure-review.json` confirms accepts from all eight
endpoints. Its timestamped failure inventory was 152 generation JSON parse
failures, two audit JSON parse failures, and one generation ValueError
(`Incomplete response: length`; six such failures at the next inspection). These
outputs are excluded, not repaired or silently replayed. Counters are interim;
the live ledger and runtime receipt supersede this launch snapshot.

Exact launch shape (already running; do not launch a duplicate):

```bash
CUDA_VISIBLE_DEVICES='' python -B -u -m dfm12.identity_multilingual_runner --root data/dfm12/identity-multilingual-2000-20260928-v1 --authorization data/dfm12/identity-multilingual-2000-20260928-v1/runner-authorization-512.json --concurrency 512 --timeout 600
```

## Scope and Current State

Historical CPU preparation state, superseded operationally by the launch above.

The user requested approximately 2,000 accepted conversations per language
across 21 languages. Preparation is CPU-only. This does not authorize a GPU
launch, server changes, a joint-production change, training, or publication.

Module: `dfm12/identity_multilingual_queue.py`.
Prepared root: `data/dfm12/identity-multilingual-2000-20260928-v1`.
Manifest SHA-256:
`00726f437f5abdc574994dfccf8be6b800addbf960ec4083dad51c468113d953`.

Verified initial state: **31,286 queued requests, activation false, zero
attempts, zero active jobs and zero newly accepted conversations**. Existing
retained inventory is 10,714 conversations; cumulative target is 42,000.
Requests are candidates, not promised accepts. No inference runner is included
or launched by this CPU queue module. Main-thread coordination remains required.

## Inventory and Shortfall

| Language | Retained | New Accepts Needed |
| --- | ---: | ---: |
| DA | 1,969 | 31 |
| EN | 1,981 | 19 |
| NL | 980 | 1,020 |
| NB | 964 | 1,036 |
| NN | 961 | 1,039 |
| SV | 979 | 1,021 |
| IS | 956 | 1,044 |
| FO | 947 | 1,053 |
| PL | 977 | 1,023 |
| DE | 0 | 2,000 |
| FR | 0 | 2,000 |
| ES | 0 | 2,000 |
| IT | 0 | 2,000 |
| CS | 0 | 2,000 |
| PT_PT | 0 | 2,000 |
| FI | 0 | 2,000 |
| EL | 0 | 2,000 |
| RO | 0 | 2,000 |
| UK | 0 | 2,000 |
| ET | 0 | 2,000 |
| CA | 0 | 2,000 |

DA/EN retain the complete corrected v4 local corpus, not obsolete originals
plus duplicate expansions. Their audited original export counts were 969 and
982; v4 also includes agent-authored CPU-validated curated additions and one
deduplication. Counting those authorized retained rows toward the target does
**not** retroactively declare them teacher-audited or native-language gold.
The manifest reports both counts and labels their baseline kind explicitly.
The other seven existing languages use validated accepted export rows, not
1,000 presumed accepts from the original generation request count.

## Provenance and Quality

The v4 correction chain is reconstructed and verified before preparation.
Accepted export manifests, actual data rows and metadata are validated and
pinned. `retained/<language>.jsonl.gz` contains exact existing record snapshots;
the source packages, databases, v4 corpus and heldouts remain unchanged.

`recipe.json` combines v2 expansion and v3 repair topic/fact identifiers with
the original fact registry and v4 runtime correction. It preserves organization
versus training-team leadership, scratch weights versus checkpoint continuation,
historical versus current tokenizer/template claims, layer versus module-pass
counts, scoped uncertainty, number formatting and concise compound answers.
It does not feed heldout wording or heldout answers into generation requests.
NB and NN are separate standards; `pt_pt` explicitly means European Portuguese.

The SQLite queue seeds exclusions from all original accepted conversations,
including superseded DA/EN variants, and all corrected retained conversations.
It rejects both identical conversation fingerprints and repeated normalized
user-question sequences within a language. Its **452 normalized prompt hashes**
exclude v4 heldout/development questions and the sealed 40-conversation,
80-turn composition holdout. Exact exclusion is not proof of semantic disjointness.

Generated candidates must pass role/turn validation, duplicate and heldout
checks, and the existing pinned native training renderer. A separate factual,
language/coherence/usefulness identity audit uses the existing `audit_payload`
and `validate_audit` contract. No heuristic substitutes for that audit.
CPU preparation itself admits no new training data.

## Queue Integration

`queue.sqlite` contains `targets`, `jobs`, `metadata`, `seen`, `prompts` and
`heldouts`. Stable slots begin at 100000, separate from historical slots.
Targets count retained plus newly accepted conversations, not generation requests.
SQLite immediate transactions reserve quota and credit accepted results once.
Pending audits are prioritized and preserve completed generation.
Rejected/invalid/failed candidates are terminal; replenishment creates a new
slot, bounded at six candidates per initial language deficit. Failed rows are
never silently reset. Running work is not lease-replayed after a crash; it
requires explicit operational reconciliation.

CPU commands:

```bash
python -m dfm12.identity_multilingual_queue status --root data/dfm12/identity-multilingual-2000-20260928-v1
python -m dfm12.identity_multilingual_queue verify --root data/dfm12/identity-multilingual-2000-20260928-v1
```

After endpoint/resource coordination, provide an explicit JSON authorization
with `manifest_sha256`, `scope: identity_extension_generation_and_audit`,
`coordination_complete: true`, `authorized_by`, `endpoints`, and
`concurrency_per_endpoint` (1..32). Then:

```bash
python -m dfm12.identity_multilingual_queue activate --root data/dfm12/identity-multilingual-2000-20260928-v1 --authorization <coordinated-receipt.json>
```

Activation changes only queue metadata; it starts no network or GPU process.
A separately coordinated worker must verify pins at startup, enforce that
receipt's endpoint/concurrency limits, and consume `Queue.claim(owner)`.
The returned payload has the existing `{record, request}` shape. Submit only
complete, parsed responses using `Queue.submit(id, owner, stage, result,
renderer)`, with `identity_extension.NativeRenderer` using the pinned student
metadata for generation. Transport/incomplete responses go to `Queue.fail`.
The worker must not pass partial/truncated responses as complete results.
The old `identity_gpu` runner is not a drop-in consumer: its nine-language
pilot/bulk activation assumptions differ. No automatic export is wired here.

## Validation

22 CPU tests passed across the new queue and existing identity GPU-contract
tests, without network/GPU execution. Tests cover coordination gating, exact
language labels, factual context, two-broker quota safety, audit priority,
duplicate and heldout exclusion, bounded replacement, ownership, payload drift,
render failures, invalid audits, idempotent audit credit and overwrite refusal.
The prepared queue's frozen file/source/implementation pins were verified.

See [DA/EN corrected extension](dfm12-identity-extension.md) and
[original identity generation](dfm12-identity-generation.md) for inherited policy.
