---
type: Plan
title: "Mimir Search"
description: Verifiable Danish and European search trajectories as a third DFM13 context-grounded dataset.
tags: [dfm13, search, evidence, synthetic, danish, european]
status: draft
last_updated: 2026-10-01
confidence: medium
---
# Mimir Search

## Latest Decision: Not Included in DFM13

On 2026-10-01 the user explicitly excluded Mimir Search, SearchArena and
RepoChat from DFM13. This supersedes the integration steps below. Preserve
research artifacts, but do not register, tokenize or sample this dataset into
DFM13. Generation remains paused under the preceding operational instruction.

## Scope and Decision

User-requested 2026-10-01: plan a third dataset alongside reconstructed
RepoChat and SearchArena trajectories. Half should be Danish, with European
relevance, 10% current topics and 90% stable knowledge. Subsequently on the same
date the user named it Mimir Search, set the language mix below and authorized
generation. Start a 200-accepted pilot using free primary-source retrieval and
a frozen search corpus. No additional paid Jina requests are authorized.

Proposed HF name: `schneiderkamplab/dfm13-mimir-search`.
Interpret Danish as Danish-language prompts and answers, not merely Danish
domains. The earlier proposed 50% English is superseded: use 25% English and
25% across the other 19 DFM12 languages. Record topic geography separately:
half Denmark-focused, half broader EU/cross-border, crossed with language so
Danish also covers EU matters and English also covers Denmark.

## Size and Composition

Propose a 200-accepted pilot, then 2,000, then 10,000 accepted trajectories.
These are scale gates, not commitments to spend or throughput estimates.

| Split | Stable | Current | Total at 10K |
|---|---:|---:|---:|
| Danish | 4,500 | 500 | 5,000 |
| English | 2,250 | 250 | 2,500 |
| Other 19 languages | 2,250 | 250 | 2,500 |
| Total | 9,000 | 1,000 | 10,000 |

Apply the same proportions at every gate. Count accepted unique trajectories,
not attempts. Do not fill difficult quotas by duplicating answers/translations.
Pilot quotas are 100 Danish, 50 English and 50 other-language examples, with
20 current-topic examples total. Allocate the 50 across all 19 languages (two
or three each), rather than calling English questions about Europe multilingual.
At 10K use 131 or 132 per other language. Balance the current quota across
languages as closely as integer counts permit; use native-language review.
Reserve 10% as held-out evaluation, grouped by document family, underlying fact,
question template and translated counterparts before generation. Heldouts are
never included in DFM13 training. Preserve proportions within each split.

Stable domains: science/environment (20%), history/culture/geography (20%),
official historical statistics and arithmetic (20%), institutions/public-service
concepts (15%), technical standards/open documentation (15%), and cross-border
comparisons (10%). These domain shares are independent of language and time.
Avoid personalized medical/legal/financial advice and sensitive personal data.

Current means explicitly dated questions about a release/development within
90 days of collection, balanced across science, environment, official statistics
and institutions. No live sports, stock prices, gossip or undefined 'latest'.
Every current answer names its as-of date. Stable statistics use a fixed period
and snapshot, never a latest-value query. Legal/service rules require a dated
version even when their underlying topic is durable.

## Sources and Retrieval

Start from primary, attributable sources: Statistics Denmark, Danish public
research institutions/museums and official agencies; Eurostat, EEA, EU research
and institutional publications. EUR-Lex may support narrowly factual dated
document questions, not personal legal recommendations. Each document needs
its own reuse/licence record; a government domain is not blanket permission.

Statistics Denmark documents programmatic access and attribution-based reuse
in its [StatBank API documentation](https://www.dst.dk/en/Statistik/hjaelp-til-statistikbanken/api).
The [EU data portal API documentation](https://dataeuropa.gitlab.io/data-provider-manual/api-documentation/)
offers discovery infrastructure; check provider-specific rights before publishing
evidence. Prefer reproducible structured-data queries for numeric verification.

1. CPU-build a diverse source/task inventory, licence map, language/geography/
   time quotas and heldout groups. Store oracle evidence separately from teacher
   messages; it can verify the result but must not reveal the answer to the agent.
2. Generate natural questions with no forced answer embedded. Agent must choose
   search queries and which results to open using declared tools.
3. Cache-first search: project existing full responses into bounded search results.
   New discovery requests, if later authorized, use at most five snippets and a
   25K provider token budget. Fetch only selected pages, with separate explicit
   per-page and per-trajectory budgets. Never automatically retrieve ten full PDFs.
4. Pilot defaults: at most three search calls and three page reads, 4K retrieved
   tokens/page and 12K total retrieved tokens before student-context filtering.
   These are ceilings, not targets. Provider usage and response bytes are recorded;
   local truncation is not a billing cap. No 4K example may silently lose evidence.
5. Preserve immutable retrieved bytes/hash, canonical URL, retrieval/publication/
   effective dates, status, query/settings and usage. Build Jina-like title/URL/
   content records from real evidence, explicitly marking excerpts/paraphrases.
   Preserve numbers, negations and qualifying clauses; retain source-span mapping.
6. Replay trajectories offline from frozen responses for exact reproducibility.
   A frozen-index pilot must be labelled as such, not claimed as unrestricted web
   search. Report cache hits, actual provider requests and billed usage separately.

The existing SearchArena 200-reservation cap remains exhausted. This plan must
not reset that ledger. Any new paid campaign needs its own approved cost budget.

## Tasks and Native Supervision

Suggested task mix: single-source factual lookup 30%, two-source synthesis 25%,
numeric/table lookup and calculation 20%, definitions/procedures 15%, and evidence
conflict or justified clarification 10%. Most should have answerable questions;
abstention must reflect actual missing/conflicting evidence, not a lazy shortcut.

Use Gemma 4 native multi-turn messages and OpenAI-compatible tool definitions.
Supervise valid assistant tool calls and grounded final answers, never tool-result
tokens. Calls must have executed, with matched IDs and real outputs. Controller-
inserted calls can produce final-answer-only examples but cannot be labelled
autonomous tool policy. Do not expose reviewer notes or hidden teacher reasoning.
An internal 'Use search' retry is allowed; keep it out of exported user prompts
and record that intervention. Validate the exact rendered student token length.

Propose 80% examples fitting 4K and 20% fitting 8K, separately tagged; adjust only
after measuring evidence sufficiency. Store complete trajectories and route by
supported context, never truncate tool evidence to force acceptance.

## Verification and Quality Gates

- Require a claim ledger: material assertion, exact supporting evidence span(s),
  entailment verdict and date scope. Presence of a URL is not evidence of support.
- Deterministically check numeric results, units, source dates, tool IDs, observed
  citations, schema, rendered masks/context, duplicates and split leakage.
- Independent reviewer sees question, answer and evidence, not teacher rationale
  or desired label. Reject invented references, unsupported implementation/facts,
  contradicted qualifiers and answers to a different question.
- Build paired correct/incorrect controls with wrong dates, swapped entities,
  unit errors, missing negation and superficially plausible unsupported claims.
  Controls include valid concise answers so extra strictness does not reward
  unnecessary rejection. Keep evaluation controls outside prompt-tuning examples.
- One targeted repair with the same observed evidence, then re-audit. No fabricated
  citations, silent evidence replacement or repeated retries until accepted.
- Pilot: manually assess at least 50 stratified outputs and all control failures.
  Provisional scale gate: at least 95% fully supported in that sample, zero known
  critical fabrication, at least 95% control agreement and <=5% false rejection.
  Report sample sizes and uncertainty; this is not a guarantee of population quality.

Track accepted/minute, generated tokens, request latency, KV occupancy,
preemptions, paid tokens per accepted example and repair/reject causes. Estimate
GPU hours and final retrieval budget from the pilot rather than borrowing the
bulk arena audit rate. Reuse shared servers without disrupting training or other
campaigns; adapt global concurrency to measured KV capacity.

## Deliverables and Order

Superseded sequencing: user authorized starting Mimir Search while RepoChat
reviewer calibration and cached SearchArena salvage continue. Share the existing
TP8 service, beginning with one request in flight and coordinated capacity.
CPU source inventory/question templates and the frozen-source pilot start now. Next:
200-example pilot, independent review and cost report; 2K gate; proposed 10K.
Export accepted-only JSONL/parquet, native messages/tools, bounded evidence and
provenance with source-specific redistribution handling. Publish a data card with
language/topic/time/split counts, review limitations and actual search cost.
Register as a distinct DFM13 source only after acceptance. Do not replace either
RepoChat or SearchArena, and do not merge their counts into this dataset.

Related: [DFM13 plan](dfm13-plan.md),
[SearchArena cache and budget recovery](dfm13-search-parallel-budget-recovery.md),
[RepoChat full campaign](dfm13-repochat-full-campaign.md).
