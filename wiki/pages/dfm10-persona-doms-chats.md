---
type: Dataset Generation Runbook
title: DFM10 Persona and Domsdatabasen Chats
description: Production contract for audited Danish persona-seeded and pseudonymized legal multi-turn data.
tags: [dfm10, danish, conversation, legal, synthetic-data, audit]
status: stable
last_updated: 2026-08-30
confidence: high
---
# DFM10 Persona and Domsdatabasen Chats

## Source and output contracts

Two Danish multi-turn additions are admitted through generated-and-audited
derivatives, not as raw continuation data:

- `dfm10-danish-persona-chats` deterministically creates 25,000 candidates
  from all 5,000 `oliverkinch/danish-personas` seeds across five task focuses.
  Candidate lengths span three through seven assistant turns. The persona is
  only a seed for realistic needs; the assistant may not impersonate it or
  reveal name, address, or postcode. The production gate requires at least
  20,000 accepted rows with the planned per-length minimums. Every accepted
  candidate is retained and the final package uses repeat two.
- `dfm10-domsdatabasen-grounded-chats` creates 4,500 four- or five-turn
  candidates from nonempty `text_anonymized` fields in
  `alexandrainst/domsdatabasen`. The evidence excerpt is capped near 7,000
  characters and emphasizes procedural background, claims, reasoning, and
  outcome. The assistant must distinguish party claims from court findings,
  remain grounded, preserve pseudonymization, and avoid legal advice. The gate
  requires at least 3,000 accepted rows; every accepted candidate is retained
  at repeat one.

## Production execution

**Runtime status, 2026-08-30:** request preparation completed, but the latest
production launch stopped before generation because the GPU 0 vLLM server did
not become ready. All campaign-owned server processes exited; neither output
package is materialized. The failure log is
`logs/dfm10_persona_doms_chats_20260830T093708/runner.log`. A future launch can
reuse the prepared 25,000 persona and 4,500 Domsdatabasen requests.

**Superseded later on 2026-08-30:** the first shortest-work-first handoff then
failed because the `audit` environment lacked `pyarrow`; all 96 shards failed
before sending model requests. Installed `pyarrow==25.0.1` with `uv pip`, added
an explicit client dependency preflight, reset the atomic queue, and relaunched
with isolated stage logs under
`logs/dfm10_small_work_priority_20260830_v2/`. All eight Gemma servers became
healthy and the campaign began with eight concurrent Doms generation shards,
88 pending jobs, and zero failed jobs.

`scripts/dfm10_persona_doms_chats.py` prepares, generates, audits, verifies,
and builds the two sources. The prepared inventory has 25,000 persona requests
in 64 shards and 4,500 legal requests in 32 shards. Each shard must have
successful generation and audit records for at least 98% of requests.

`scripts/run_dfm10_persona_doms_chats_8gpu.sh` waits for the active Danish
lexical campaign lock, then launches one Gemma 4 31B OpenAI-compatible vLLM
server per GPU. Eight dynamic workers claim shards atomically and retry each
incomplete shard up to four times. Generation uses concurrency 64; audit is a
separate strict pass checking language, coherence, support, role distinction,
privacy, and training value.

After both gates pass, the runner:

1. builds all accepted rows without a post-audit size cap;
2. tokenizes both sources with the Gemma 4 template and 16 CPU workers;
3. materializes the two local Hugging Face export packages;
4. stops its vLLM servers.

It intentionally does not rebuild the DFM10 union, sample epochs, or upload to
the Hub. Those remain explicit follow-up operations after accepted-row review.
The runner waits only for its explicit worker/server PIDs during cleanup; a
bare shell `wait` is forbidden because the process-substitution logger would
otherwise keep the wrapper and campaign lock alive indefinitely.

## Paths

- Requests and resumable records: `data/dfm10_persona_doms_chats/`
- Persona source: `data/dfm10_danish_persona_chats_source/`
- Legal source: `data/dfm10_domsdatabasen_grounded_chats_source/`
- Tokenized persona: `data/tokenized_dfm10_danish_persona_chats/`
- Tokenized legal: `data/tokenized_dfm10_domsdatabasen_grounded_chats/`
- Local packages: `exports_dfm10/dfm10-{danish-persona-chats|domsdatabasen-grounded-chats}/`

Confidence is high for source counts and implementation behavior from local
request construction and tests. Final acceptance counts remain unknown until
the queued campaign completes.

## Completion update, 2026-08-30

The earlier statement that both packages were non-materialized is
**superseded for Domsdatabasen**. All 32 legal shards completed generation and
independent audit. Finalization retained 4,438 chats containing 19,985
supervised assistant turns and 7,714,485 rendered training tokens. Gemma-native
tokenization produced 19,985 examples with zero skips. The validated 4,438-row
package was uploaded as
`schneiderkamplab/dfm10-domsdatabasen-grounded-chats`; remote revision
`3150dfcfef013bac0efc23a60d9ae5dcfbe383e4` passed complete file-set
verification.

Persona remains active rather than complete. At the latest status check, all
25,000 requests were prepared, 56 of 64 generation shard files existed, and
20,388 generated records had been written. Publication and canonical-union
activation remain gated on the final acceptance threshold, tokenization, and
package validation.

**Superseded later in the same run:** all 64 persona shards reached their
completion-fraction gate, but final build retained only 1,834 seven-turn chats
against the 2,000-row per-length minimum. The package therefore remains
blocked and unpublished. The wrapper's second attempt resumes only missing
generation/audit records from the existing JSONL logs; it does not discard
successful model work. Do not weaken the gate silently. If completion retries
do not close the 166-row acceptance deficit, generate and independently audit
a targeted seven-turn top-up with new deterministic request IDs.

All three automatic completion retries subsequently exhausted after increasing
the accepted seven-turn count only to 1,852. Persona therefore remains a
non-materialized work-in-progress package. The retries preserved all successful
generation and audit records; a targeted top-up remains the required next
step.

**Superseded by owner decision, 2026-08-30:** 1,852 independently accepted
seven-turn chats were approved as sufficient. The production floor is now
1,850 for that length only; the 3/4/5/6-turn floors remain 2,000/4,000/8,000/
4,000. The original 25,000-candidate campaign and deterministic request IDs are
unchanged. This is an explicit acceptance-policy revision, not admission of
rejected rows.

Finalization then retained 22,284 persona chats across all lengths, containing
110,290 supervised assistant turns and 18,353,119 rendered training tokens.
Gemma-native tokenization produced 110,290 examples with zero skips. The
standalone package passed a complete 22,284-row recreation check and was
published as `schneiderkamplab/dfm10-danish-persona-chats` at revision
`ed6f54ad347a6e2d0ced84abafaa5d46bae83198`; its remote package manifest and
data-shard checksum match the local package. The canonical DFM10 union now
contains the persona task alongside Doms and all four Danish lexical tasks.

Canonical union writes are serialized with `data/.dfm10-union.lock`. The Doms
integration waits behind the pre-existing native-source union builder. A
second completion watcher waits for the validated persona package and then
performs another lock-protected rebuild, preventing the active persona campaign
from racing an unrelated union update.
