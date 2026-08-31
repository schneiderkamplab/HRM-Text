---
type: Dataset Repair Runbook
title: DFM10 Danmarks Statistik BT Repair
description: Answer-matched prompt regeneration and strict full-corpus filtering for Danish official-statistics instruction data.
tags: [dfm10, danish, statistics, instruction, repair, audit]
status: draft
last_updated: 2026-08-29
confidence: high
---
# DFM10 Danmarks Statistik BT Repair

## Problem

`oliverkinch/danmarks-statistik-bt` contains 7,154 authentic target passages
from Danmarks Statistik, but its persona-conditioned backtranslated prompts
were generated merely *about* each topic. The 100-row DFM10 source audit found
61% usable rows, mean instruction/answer coherence 3.20/5, 47% instruction or
format mismatch, and 17% ungrounded/hallucinated scope. Typical prompts ask for
causes, implications, opinions, or unrelated cultural effects while the target
only reports official figures.

The authoritative targets are retained. DFM10 repairs the prompt-target
contract and does not rewrite statistics or explanatory passages.

## Repair contract

1. `scripts/repair_danmarks_statistik_bt.py prepare` inventories every source
   row and rejects only mechanically corrupt targets before generation.
2. `scripts/generate_danmarks_statistik_bt_prompts.py` uses Gemma 4 E4B to
   create one natural Danish prompt that the complete target answers directly.
   It must not request unsupported causes, consequences, opinions, advice,
   comparisons, side topics, or answer formats. It may reject targets that are
   indirect, truncated, or context-dependent.
3. Candidate construction uses the Gemma 4 native chat template and admits
   only complete prompt/target pairs fitting 4,096 tokens.
4. A separate full-corpus E4B audit rejects indirect responses, missing
   context, prompt leakage, malformed publication fragments, and any remaining
   scope mismatch. Production filtering is fail-closed: sampled audits and
   incomplete partition inventories cannot create the final corpus.
5. The old `oliverkinch_danmarks_statistik_bt__` prefix is disabled. The
   strictly accepted `danmarks_statistik_bt_repaired__` prefix retains repeat
   ten, matching the prior Danish weighting without sampling both versions.

## Commands and state

The CPU inventory completed on 2026-08-29 with all 7,154 rows prepared for
semantic prompt repair. The end-to-end runner waits until all eight GPUs are
free and does not terminate or preempt existing jobs:

```bash
cd /work/dfm/HRM-Text
setsid scripts/run_danmarks_statistik_bt_repair_when_free.sh \
  > logs/data_audits/danmarks_statistik_bt_repair_waiter.log 2>&1 &
```

Artifacts:

- requests: `data/danmarks_statistik_bt_repair/prompt_repair_requests.jsonl`
- generated prompts: `logs/data_audits/danmarks_statistik_bt_prompt_repair_20260829/`
- full coherence audit: `logs/data_audits/danmarks_statistik_bt_repaired_20260829/`
- filtered source: `data/converted_sources/danmarks_statistik_bt_repaired/`
- tokenized replacement: `data/tokenized_dfm10_danmarks_statistik_bt_repaired/`

**Superseded 2026-08-29:** final retained rows and tokens were initially pending
GPU generation and full auditing. The completed result is recorded below.

### 2026-08-29 execution recovery

The first E4B generation pass returned all 7,154 rows but 5,284 constrained
JSON responses ended in Gemma's whitespace/truncation pattern. Conservative
field recovery retained only complete `usable` and `prompt` values. A retry
reduced unresolved rows to five and produced 4,673 usable candidates plus
2,476 explicit generator rejections. The five persistent failures have already
exhausted repeated request-level retries and are fail-closed as terminal
generator rejections if one final attempt fails; they are never admitted.

A concurrent NordjyllandNews audit then occupied seven GPUs. Because its GPU2
partition was already complete, the continuation moved to GPU2 without
interrupting that audit. Eight audit clients share one E4B server with aggregate
concurrency 64. The continuation script is
`scripts/continue_danmarks_statistik_bt_repair_gpu2.sh`.

## Completed result

Completed 2026-08-29. Prompt generation resolved all 7,154 source rows: 2,480
were explicitly rejected by the generator, three of those after exhausted
retries; 50 generated prompts mentioned forbidden generation context and two
lacked terminal punctuation. This left 4,622 bounded candidates.

The exhaustive audit judged 4,620 candidates normally. Two rows exhausted four
judge attempts each and are explicitly represented as terminal fail-closed
rejections rather than silently dropped. The authoritative strict criterion
requires `usable_for_training`, `complete`, `primary_problem: none`, language
and training-value scores at least three, and coherence and grounding scores at
least four. It accepted 3,086/4,622 candidates (66.77%); 3,086/7,154 original
rows (43.14%) survive end to end. The principal rejection was prompt mismatch.

Tokenization produced 3,086 rows and exactly 762,189 Gemma-rendered tokens with
no skipped rows. At repeat ten, this source contributes 7,621,890 raw repeated
tokens per DFM10 epoch, replacing the legacy source's 18,862,480 tokens.

## Source-grounded recovery path

The downloaded `oliverkinch/danmarks-statistik-bt` Parquet retains a `sources`
record and a Danmarks Statistik URL for all 7,154 rows (3,447 unique URLs).
Rejected pairs can therefore be repaired against the complete underlying DST
article instead of asking a model to invent missing facts from the extracted
target passage. For example, source row `dst-001773-p00` links to
`https://www.dst.dk/nyt/33097`, whose live article contains tables and later
paragraphs omitted from the short target passage. A future recovery pass should
fetch and cache each URL, regenerate a strictly article-grounded pair, and
re-audit it; URL failures should remain fail-closed.

### Article recovery execution

Started 2026-08-29. The implemented recovery is additive: it preserves the
3,086 passage-grounded strict accepts and considers only the other 4,068 source
rows. CPU preparation extracted clean UTF-8 article context for 3,932 rows from
2,181 live DST URLs; 136 rows associated with 133 unavailable or insufficient
pages remain fail-closed. `oliverkinch/danmarks-statistik` is now an explicit
downloader dependency, while the live URL retained in every BT row supplies
article content omitted from its short source passage.

The recovery uses these scripts:

- `scripts/recover_danmarks_statistik_bt_from_articles.py` caches and extracts
  articles, constructs requests, bounds Gemma-native candidates, and preserves
  evidence and source URLs.
- `scripts/generate_danmarks_statistik_bt_article_recovery.py` generates both
  sides of a pair from the article without inventing missing figures.
- `scripts/audit_danmarks_statistik_bt_article_recovery.py` independently checks
  prompt completeness and answer claims against article evidence, then unions
  strict accepts by disjoint original source-row ID.
- `scripts/run_danmarks_statistik_bt_article_recovery_when_free.sh` waits for all
  GPUs, takes per-GPU locks, runs eight E4B servers, audits all candidates,
  writes `danmarks_statistik_bt_repaired_with_article_recovery`, and retokenizes
  the canonical DFM10 prefix. It does not preempt existing GPU work.

**Superseded 2026-08-29:** the first eight generation workers
processed all 3,932 requests, producing 2,156 valid records and 1,776 explicit
retryable errors. The errors are structured-output truncations, predominantly
missing `prompt` or `reason`, rather than source-fetch failures. Per operator
request, the parent was stopped before merge, audit, union, or tokenization and
its owned E4B servers were released. Resume must retry/replace the 1,776 error
records before merging; the partition files are not a complete recovery set.

### Completed 31B article recovery

The recovery was restarted from a clean root with Gemma 4 31B IT as generator
and an independent Gemma 4 E4B judge. Generation covered all 3,932 requests;
ten persistent structured-generation failures were represented explicitly as
terminal fail-closed rejects. The generator's own `usable` flag proved
unreliable and is retained only as provenance: it marked 3,731 substantive
pairs unusable while many of its 191 self-accepted rows were refusals.
Candidate construction therefore admitted every nonempty, bounded pair and
delegated the quality decision to the independent judge. It produced 3,827
auditable rows.

The independent audit completed exact coverage and accepted 2,541 rows under
the authoritative strict predicate. The additive union is disjoint by original
source-row ID and contains 3,086 passage-grounded baseline rows plus 2,541
article-grounded recoveries, or 5,627 rows total. Gemma-native tokenization
reconciled exactly with zero skipped rows and produced 1,282,988 unique
rendered tokens. At repeat ten, the repaired source contributes 12,829,880
tokens per DFM10 epoch.

Authoritative artifacts:

- generation: `logs/data_audits/danmarks_statistik_bt_article_generation_31b_20260829/`
- independent audit: `logs/data_audits/danmarks_statistik_bt_article_recovery_31b_e4b_20260829/`
- converted union: `data/converted_sources/danmarks_statistik_bt_repaired_with_article_recovery/`
- canonical token root: `data/tokenized_dfm10_danmarks_statistik_bt_repaired/`
Final recovery retention and token counts remain pending.
