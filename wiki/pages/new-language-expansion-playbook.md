---
type: Playbook
title: New Language Expansion Recipe
description: Reusable language-addition recipe with quotas, native formatting, audit gates and sharded throughput-safe generation through publication.
status: draft
confidence: high
last_updated: 2026-10-06
tags: [data, multilingual, generation, audit, performance, dfm14]
---
# New Language Expansion Recipe

## Scope

The six core components are text transformations, 35K/70K synthetic
conversations, existing instruction/chat data, English parallel data, other
language parallel data, and separately curated DaLA. Identity data, independent
evaluation and accepted-only publication/assembly complete the operational
recipe. This playbook consolidates previous decisions; it does not launch a
campaign or authorize every candidate in the [DFM14 plan](dfm14-plan.md).

Historical implementation anchors: `dfm12/config.yaml`, `dfm12/prepare.py`,
`dfm12/budgets.py`, the [wave reference](language-extension-waves.md), and
[synthetic production quotas](dfm12-multilingual-quarter-production.md).
Old configuration defaults are not authoritative when superseded by a later
language/campaign decision. New pipeline recommendations below are requirements
to verify, not a claim that every historical runner already implements them.

## Components and Sizing

| Component | Usual allocation | Construction |
|---|---|---|
| Four transformations | Per language and task, 25% of the accepted, deduplicated Danish DynaWord reference rows | Broad document sampling; denoising/correction, real prefix continuation, span filling and paragraph reordering. |
| Synthetic conversations | 35K or 70K **accepted conversations**, not attempts or turns | Six task families; existing useful instruction breadth determines tier. |
| Existing chat/instructions | Source-specific, no universal row cap or repeat | Native useful data first; inspect translated/aggregated components and inherited overlap. |
| English translation | Pair cap: 25% of the sampled repaired English-Danish token reference | Both directions together; prefer direct high-quality parallel sources. |
| Other-language translation | Pair cap: 6.25% of the same reference, one quarter of the new English-pair cap | New language with existing languages and other new languages; direct pairs first, documented English pivot if necessary. |
| DaLA | Supplied training partitions; no universal new row quota | Acceptability and grammatical error correction from the separate curation workstream, quality-audited before release. |

Do not confuse rows, conversations, targets, unique sentence pairs and tokens.
`transformation_baseline()` in `dfm12/prepare.py` counts unique accepted chats
per Danish transformation task and rounds the configured fraction upward.
`opus_budget()` in `dfm12/budgets.py` reads **sampled repaired OPUS tokens, both
directions**, from the reference report. It deliberately refuses raw/stored
token totals. Pin that report and its hash; do not silently rebase budgets.
Translation fractions are caps, not minimums to fill with poor data.

**Correction (2026-10-06):** the reference to `opus_budget()` above is
superseded as implementation guidance. It sums cumulative report coverage and
can overstate per-epoch caps tenfold on the ten-epoch report. Use
`dfm12.token_accounting.inherited_budget()` and its verified receipt, as already
documented in [token accounting](dfm12-token-accounting.md). The intended
fractions and per-epoch basis are unchanged.

### Synthetic Family Quotas

| Family | 35K tier | 70K tier |
|---|---:|---:|
| Grounded instruction/QA | 10,000 | 20,000 |
| Multi-turn dialogue | 7,500 | 15,000 |
| OpenHermes-style adaptation | 7,500 | 15,000 |
| Summary/rewrite | 5,000 | 10,000 |
| Math/code | 3,000 | 6,000 |
| Native tool dialogue | 2,000 | 4,000 |
| **Total** | **35,000** | **70,000** |

Use 35K where independently accepted existing instructions cover enough domains
and task types; 70K where supply is narrow or scarce. Record the rationale.
Synthetic counts supplement existing data; they do not cap it. Preserve accepted
pilots and replenish after cross-shard deduplication. Do not meet a conversation
quota by multiplying identical examples or counting every assistant turn.

OpenHermes-style means adaptation using approved modernized sources/patterns,
not permission to restore raw OpenHermes to the training pipeline. Preserve
source IDs and audit translated facts, code and formatting.

### Supporting Components

- **Identity:** where requested, localize the verified Mimir identity knowledge
  and extended multi-turn variations, with roughly 2K accepted conversations
  per language as the previous extension goal. Independently verify factual
  names/roles/architecture and keep prompt-family holdouts. Its repeat is a
  run-specific choice, not implied by the synthetic 35K/70K tier.
- **Evaluation:** establish native instruction following, QA, knowledge,
  acceptability/correction and translation checks before generation. Use
  EuroEval only where actual datasets exist, otherwise explicit native suites.
- **Accounting:** measure accepted rows, unique source documents, rendered
  tokens, repeats and sampled per-epoch contribution separately.

## CPU Preparation

1. Inventory sources, licences/owner decisions, revisions, actual payload
   access, language/script variants, splits and source relationships. Distinguish
   a dataset card from an accessible usable payload.
2. Decode and normalize conservatively. Preserve paragraphs, equations, code,
   tool definitions and context. Detect bad OCR, navigation, empty text and
   truncation. Do not conflate related languages or rewrite spelling variants.
3. Sample broadly across source files, domains and document lengths, with
   deterministic seeds and stable document IDs. Cap repetitive domains and
   prevent a few long files from supplying almost all windows.
4. Create structured task records before tokenizer rendering. Store original
   text, transformation parameters, provenance and expected target separately.
5. Build input manifests and partitions in a single streaming source pass.
   Precompute indices/offsets needed by clients; avoid rescanning the corpus
   per request, client or GPU. CPU workers must have bounded memory and output
   queues even on a many-core host.

### Transformation Correctness

- Denoising/correction: corrupt a verified clean original, retain error types,
  positions and counts. Audit that the original really is grammatical and the
  corruption creates the intended task; not every character edit is an error.
- Prefix continuation: use a real contiguous prefix and continuation from one
  document. No invented adjacency between independent source rows.
- Span filling: retain exact removed spans and state whether the answer should
  be spans only or a reconstructed passage. Ensure prompt and target agree.
- Reordering: shuffle genuine contiguous paragraphs. If unavailable, use an
  explicitly labelled sentence/grouped-sentence task; never invent original
  paragraph structure or pretend shuffled independent records have one order.

### Parallel Data

Prefer curated human/institutional/editorial translations under the approved
public-domain/CC0/CC-BY-family policy; check exact corpus-version terms rather
than assuming OPUS implies one licence. Avoid low-quality mined alignments.
Render both directions with explicit language instructions. Keep one canonical
pair ID so directional exports do not double the unique-pair count.

For English-pivot matching, require trustworthy matched English content and
retain both legs, IDs and disambiguating context. Short generic English strings
are not sufficient join keys. Audit final language-pair equivalence. A model
translation is synthetic, not a human parallel pair. Report scarce-pair
shortfalls; do not silently weaken quality to fill a cap.

## Audit and Repair Contract

All newly admitted training rows need the appropriate quality gate; an upstream
quality label is not our audit receipt. Reuse a previous accepted decision only
when content, relevant provenance and audit policy are unchanged and verified.

| Input | Required review |
|---|---|
| Existing chat/instruction | Correct language, fluent answer, instruction satisfaction, factual/grounding quality, supported context, role/tool correctness and usefulness. |
| Transformations | Source quality, exact structural invariants, recoverability, intended error/order/span task and unambiguous answer contract. |
| Parallel pairs | Both language labels, semantic equivalence, alignment, completeness, names/numbers and direction symmetry. |
| Synthetic conversations | Every supervised answer and cross-turn consistency; source fidelity, varied task usefulness, tool arguments/results and verifiable math/code where feasible. |
| DaLA | Validate the acceptability label or correction against the producer record; minimal valid correction and language correctness. Audit linked tasks consistently. |
| Identity | Verified identity facts, team roles, no invented affiliations/names, fluent localization and holdout separation. |

Use deterministic checks first and a calibrated language-capable judge next.
Recent campaigns use shared Gemma 4 26B A4B instruction servers; pin the exact
model/revision, prompts and decoding. Prefer concise non-thinking structured
reviews with short request-local IDs, decision/reason codes and only necessary
explanations. The same model can generate and judge with different prompts,
but agreement is not independent proof; check a human-reviewed calibration set
and use math/code validators when applicable. Escalate selected weak languages
or ambiguous cases rather than imposing expensive long reviews on every row.

Separate **accept**, **repair**, **reject**, **invalid review** and
**infrastructure failure**. Never count malformed output/timeouts as semantic
rejection or accept an incomplete answer just because generation ended.
Size output budgets for the actual protocol. Short local IDs map exactly to
canonical IDs; no fuzzy matching. Preserve valid batch members if another
member is malformed; retry only ambiguous/missing members.

Repairs must preserve the instruction and available evidence, correct the
identified defect, and receive a new audit before acceptance. Store lineage
from original to candidate to repaired version. Use bounded attempts and error
buckets; do not repeatedly retry genuine rejections indefinitely. Changes to
judge policy require versioned re-audit, not relabelling old decisions.

DaLA is externally curated: do not silently rewrite pairs/labels independently
of that workstream. Hold invalid pairs or use an explicitly agreed repair
contract and rerender linked acceptability/correction rows consistently.
Holdout pair IDs/labels remain excluded from training. Existing explicit owner
exceptions allowing underlying article/sitting overlap must stay documented;
do not claim document-disjoint evaluation in those cases.

## Throughput-Safe Execution

### Partition State, Not Just GPU Requests

For large future eight-GPU campaigns, use **eight independent ledger/output
shards**, with stable canonical-ID hashing and an immutable partition manifest.
Each shard has its own writer, transactions, leases and resume cursor. Prepare
all partitions in one source pass. Do not run eight clients through one hot
SQLite writer or have every client repeatedly scan the same large JSONL.

Shard IDs do not have to equal GPU IDs. Use many bounded work chunks, and allow
free endpoints to take work from other unfinished shards while retaining the
owning ledger and lease. Lease a task once, persist its result idempotently,
and merge disjoint terminal records. Test coverage/union parity and crash/resume
before production. Do not repartition a live campaign in place.

### Pipeline Stages

`prepare -> generate -> audit -> repair -> re-audit -> accepted selection`

Audit committed generated chunks while other chunks are generating; repair
and re-audit concurrently within the shared endpoint budget. There should be
no whole-dataset or language-wide barrier, and no request-batch barrier that
waits for the slowest response before replacing completed work. Final export
waits for all required terminal decisions, not interim provisional passes.

Use bounded queues between CPU preparation, HTTP submission and durable result
writes. A separate writer batches commits; synchronous JSON serialization,
fsync and huge database scans must not run in the networking event loop.
Progress uses incremental counters/read-only snapshots, not full-table scans
for every refresh. Larger mmap/cache limits do not fix serialized processing.

### Shared Servers and Clients

- Match the verified environment, CUDA/compiler and vLLM stack. Reuse healthy
  shared servers; retain compilation/CUDA graphs when supported. Do not change
  kernel backends or disable optimizations without a diagnosed reason.
- On fully available GPUs, recent campaign settings included 0.95 GPU-memory
  utilization and 1,024 maximum sequences/server. These are **examples, not
  universal safe defaults**; colocated jobs require an explicit joint budget.
- Start from a proven workload setting, e.g. 384 requests/server, then measure.
  Generation, audit and repair clients share one endpoint budget. Two clients
  at 384 each mean 768 total, not 384. Request concurrency, rows/request,
  server active sequences and KV-token capacity are different quantities.
- Use independent bounded HTTP pools per endpoint and multiple client processes
  when preparation/event-loop throughput is limiting. Do not retain thousands
  of idle connections in one shared cross-endpoint pool.
- No unconditional 2-second/10-ms sleeps in the successful dispatch path.
  Such sleeps throttle admissions, not directly in-flight concurrency. Tolerate
  small transient queues; apply bounded backoff to actual overload/errors.
- Tune in-flight requests against actual KV demand and throughput. Neither
  max-num-seqs nor idle KV percentage proves more concurrency will help.
  Do not chase 100% KV occupancy at the expense of preemptions, failures or
  accepted-row throughput.

### Measure and Diagnose

Measure at least a five-minute steady-state window after changes. Report per
endpoint and aggregate: completed requests/min, generated tokens/s, audited
rows/min, unique accepted conversations/min, active/waiting requests, KV usage,
GPU utilization, preemptions, failures, retries and durable-write backlog.

| Symptom | Check first |
|---|---|
| Idle GPU, empty request queue | Source preparation, queue claims, event-loop stalls, barriers and admission sleeps. |
| Client reports many in flight but server sees few | HTTP connection pools, client CPU, sockets and requests blocked on ledger/writes. |
| Uneven GPUs and long tails | Chunk sizing, source exhaustion, fixed shard-to-GPU affinity and failed client processes. |
| High KV/preemptions and lower throughput | Combined client load and long contexts/outputs; reduce pressure or route long tasks separately. |
| Slow accepted progress despite many completions | Acceptance yield, duplicate rate, repeated invalid reviews and repair backlog. |

ETA uses remaining accepted quotas and observed yield for generation, and
remaining rows/stages for audit/repair. Include CPU finalization and publication;
do not extrapolate a short easy-audit window to long multi-turn generation.

## Recovery, Export and Integration

On restart, preserve completed decisions and accepted content. Reconcile leases
and retry outage-affected unknown/failed work by explicit reason, not all repairs
or all generations. Retarget quotas under a drained controller lock and retain
predecessor manifests. Keep baseline and recovery together in the final dataset,
with provenance, not duplicate training sources.

Merge deterministically, deduplicate across shards and inherited datasets, and
replenish accepted shortfalls where approved. Export accepted-only rows with
stable IDs, source hashes, decision/repair lineage and accurate licences/cards.
Atomically publish complete manifests after shards finish. Replace previously
unaudited content in its existing repository when instructed; do not create
new repositories merely for a repair/recovery pass.

Validate native Gemma rendering, assistant supervision, tool schemas/results,
language prompts, target completion and context length before tokenization.
Do not truncate away answers or teach ChatML/Llama/Mistral delimiters.
Tokenize changed sources only; verify immutable receipts, counts, array bounds
and rendering parity. Assemble source repeats and token budgets explicitly;
sample only after the complete intended source list passes verification.

Release only campaign-owned servers after their last shared consumer finishes.
Use recorded PIDs/ownership, never broad process-name kills. Resume any agreed
training handoff only after required GPU work is terminal and owned GPU memory
has actually been released. Do not touch unrelated vLLM processes.

## Completion Checklist

- All six component statuses recorded, including honest unavailable/deferred parts.
- Accepted unique family quotas and shortfalls documented; no quota padding.
- Invalid reviews, outages and semantic rejects accounted for separately.
- Baseline/recovery merged, repaired rows re-audited, heldouts preserved.
- Native formatting verified; exports and upload receipts complete.
- Token counts, repeats, source pins and final sampling verified.
- Language evaluations ready; identity included only under the chosen scope.
- GPU consumers/cleanup/handoff completed and durable wiki records updated.

## Operational Evidence

- [HTTP pool bottleneck and measured recovery](dfm12-audit-client-throughput.md).
- [DaLA audit ledger bottleneck, local IDs and future queue partitioning](dfm13-dala-v2-audit.md).
- [Joint multilingual production](dfm12-joint-synthetic-production.md).
- [Identity extension](dfm12-identity-extension.md).
- [Fourth-wave preparation and operational links](fourth-language-extension-wave.md).
