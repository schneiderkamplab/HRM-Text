---
type: Runbook
title: DFM12 Polish Instruction Staging
description: Pinned PLLuM access evidence, conservative adapters and isolated CPU-only unaudited preparation.
tags: [dfm12, polish, instructions, staging, provenance]
status: draft
last_updated: 2026-09-24
confidence: high
---
# DFM12 Polish Instruction Staging

## Scope and Ownership

This is isolated preparation, not approval for training or final sampling.
Code: `dfm12/polish.py`, `dfm12/polish_prepare.py`; tests:
`tests/test_dfm12_polish.py`. No shared registry/config, transformation modules,
training/evaluation/scheduler settings, or existing jobs were changed.
The parent agent owns indexing this focused page and updating aggregate status.

Related: [component preparation](dfm12-components.md) and
[addition status](dfm12-status.md). The snapshot below refines their earlier
"access/schema pending" Polish entries; those historical checks are superseded
by this dated review, not silently reinterpreted as successful access.

## Access and Rights Evidence

At 2026-09-24 06:53 UTC, the locally stored HF credential authenticated through
`whoami`. No credential value or account identity was printed or saved.
Pinned file requests used the authenticated HF client; no alternate mirrors,
gate acceptance, contact submission, or access-control bypass was attempted.

| Source | Pinned revision | Authenticated result |
| --- | --- | --- |
| pelcra/PLLuMIC | `509bd048c165ff91207ac7fb5db835ac0468a6a7` | Public README downloaded; `pllumic.json` returned GatedRepoError HTTP 403; automatic gate |
| pelcra/PLLuMIC-syn-ext | `1c3ab9e8437a83a22ed5741dbcb380ac0a7160d5` | Public README downloaded; synthetic JSONL returned GatedRepoError HTTP 403; manual gate |
| NASK-PIB/PLLuM-Align | `aa9ae3d4e0d4ffa7b5f52548928de20517122e4b` | Ungated; README and all three pinned JSONL files downloaded |

All three pinned cards declare **CC-BY-SA-4.0**. No separate LICENSE file or
held-out split is present in their pinned repository listings. Retain author
attribution, paper citation, original cards, modification provenance and
share-alike obligations; staging does not assert blanket relicensing or legal
clearance of every embedded quotation. The existing shared source holds stay
unchanged. Only accessible, screened rows are eligible for unaudited staging.

Primary sources: [PLLuMIC card](https://huggingface.co/datasets/pelcra/PLLuMIC),
[synthetic extension card](https://huggingface.co/datasets/pelcra/PLLuMIC-syn-ext),
[Align card](https://huggingface.co/datasets/NASK-PIB/PLLuM-Align).
Pinned cards and SHA256 receipts are preserved locally under
`data/dfm12/polish_unaudited/downloads/` and `access-review.json`.

## Schema and Conservative Policy

PLLuMIC's card documents a JSON array of conversations with message-level
sequence numbers, task categories, language labels and source references.
The synthetic extension uses JSONL and derives from organic PLLuMIC examples;
it is not independent provenance. Neither gated payload was inspected locally.
Adapters for those two sources are tested against their documented schema only;
real-row/schema, identity and overlap review remains blocked on authorized access.
Only a documented empty leading system placeholder may be removed. All real
turns remain in order; sequence anomalies, non-Polish labels, tools, embedded
templates and identity categories are held, not repaired or flattened.

Observed Align payloads:

| File | Pair rows | Unique chosen conversations | Duplicate chosen rows |
| --- | ---: | ---: | ---: |
| dialogs.jsonl | 1,989 | 874 | 1,115 |
| ranking.jsonl | 1,818 | 519 | 1,299 |
| rating.jsonl | 500 | 500 | 0 |

There are 1,893 raw unique chosen conversations, with no exact full-conversation
duplicates across the three files. Dialogue rows have 2 to 36 messages;
1,754 raw rows are multi-turn. All observed chosen/rejected histories match.
Rating detail values have heterogeneous types, so line-wise JSON is used instead
of imposing a single Arrow schema. Metadata is retained outside model messages.
Files are **unsplit releases**, not evidence of benchmark-safe training splits.

Align keeps full chosen history and emits `target_message_index` for **only the
final preferred assistant turn**. Earlier assistant history is context, not
certified preferred supervision. No rejected response is emitted. Identical
chosen/rejected answers, mismatched histories, invalid ratings, tools and
embedded templates are rejected. Rating rows require a finite 1..5 scale,
chosen >=4 and strictly better than rejected.

Identity-tagged IDs/messages and conservative identity/brand textual matches
are held without replacing model names. This intentionally over-filters some
innocent brand discussions and does not certify absence of all identity claims.
`neut-nonpl` IDs are held. `polqa`, `toxigen`, and `antropic` prefixes are held
for benchmark/inherited-provenance review, not declared decontaminated merely
because the repository has no explicit test split. Polish language fluency,
factuality and safety still require row-level auditing.

## Rendering and Deduplication

The actual raw tokenizer and Jinja template come from
`data/sampled_dfm11/metadata.json`, with SHA256 hashes in each run receipt.
The renderer uses the shared Gemma4 training functions with thinking disabled,
without AutoTokenizer or any Mistral regex fix. Full context must render within
4,096 tokens; overlength conversations are rejected before invoking the shared
tokenizer, so its context-trimming fallback cannot shorten these inputs.

Deduplication uses the repository's normalized role/content SHA256 fingerprint,
across eligible Polish sources and within each source. The inherited check
streams available message-form JSONL/Parquet under `data/converted_dfm11` and
`data/dfm11_source_cache`, retaining file hashes, counts and unsupported-schema
counts. It excludes matching full conversations, not similar prompts or
translated/paraphrased/partial dialogue matches. Not all inherited DFM11 raw
sources are locally available; packed sampled token files are not a complete
recoverable conversation index. Gated-source overlap and concurrent Polish
Dolci outputs remain outside this run's verified coverage.

## Run and Evidence

Detached tmux session: `dfm12-polish-20260924`. Command from repository root:

```bash
CUDA_VISIBLE_DEVICES="" TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=1 \
OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.polish_prepare \
  --run staging-20260924-v1 --workers 4
```

Four workers were chosen because other CPU preparation campaigns were active.
The CLI caps tokenizer workers at 16 and holds an isolated single-writer lock.
Run directories are immutable: use a fresh name for a reviewed rerun; never
overwrite a previous receipt or confuse partial output with completed staging.

- Log: `data/dfm12/polish_unaudited/preparation-20260924-v1.log`.
- Run: `data/dfm12/polish_unaudited/staging-20260924-v1/`.
- `access-review.json`: authenticated access outcomes and downloaded SHA256s.
- `receipt.json`: lifecycle, tokenizer hashes, per-source counts and tokenization completion.
- `rejections.jsonl`: file/ordinal and rejection reasons, not discarded answer text.
- `overlap.json`: per-file inherited comparison progress and final coverage.
- `candidates.jsonl`: full provenance and audit-pending conversations after exclusions.
- `tokenizer_inputs/`: chat-only shards retaining target indices.
- `tokenized_unaudited/`: preparation output, never accepted or sampled data.

Initial conversion completed: **4,307 input pairs; 1,607 unique candidates**, of
which **743 are multi-turn**. Counts before inherited comparison:

| Outcome | Rows |
| --- | ---: |
| Repeated eligible chosen conversations | 2,055 |
| Identity/brand text review | 67 |
| Identity category | 47 |
| Benchmark/inherited provenance hold | 295 |
| Explicit non-Polish category | 212 |
| Identical preference answers | 7 |
| Full-context render/length rejection | 13 |
| Embedded chat templates | 4 |

At this initial snapshot the inherited scan was running; no final tokenized
count is asserted here until the run receipt reports `complete_unaudited`.
Both gated sources have zero downloaded payload rows and zero candidates.
No audit jobs, teacher requests, GPU work, accepted exports or final sampling.

## Verification and Remaining Work

The combined suite passed **71 tests** (23 Polish, 48 unchanged base DFM12).
An isolated pipeline integration test covers duplicate removal,
retention of final-target indices through tokenizer input creation, and refusal
to overwrite an existing run. Re-run with:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m pytest \
  tests/test_dfm12_polish.py tests/test_dfm12.py -q
```

OKF validation was run and reported only three missing immediate-child index
links: this page plus concurrently added `dfm12-island-instruct.md` and
`dfm12-norwegian-dynainstruct.md`. Index changes are deliberately delegated to
the parent. At the handoff check, inherited comparison had completed 14 of 71
local files (653,740 conversations), with zero exact overlaps; tokenization was
still pending that scan. This is progress evidence, not the final scan total.

Remaining: authorized gated-file access, real-row testing of both PLLuMIC
adapters, full cross-source/inherited and held-out-overlap review, language and
quality audits, and parent indexing/status handoff. The synthetic extension's
organic seed relationship cannot be cleared by exact deduplication alone.

## Main PLLuMIC Access Granted, 2026-09-24

**Superseded for main PLLuMIC only:** the 06:53 UTC HTTP 403 result and the
card-only schema limitation above. Following the user's access update,
authenticated forced download of the same pinned `pllumic.json` succeeded.
Payload SHA256: `7ed5a875773eb8745f64e6a7133ddee35f2d2709895bedc233f1ee43fba7f2ae`.
No gate was bypassed. **Syn-ext is explicitly deferred**, not retried or waited
on; main-only selection performs no network request for either syn-ext or Align.

The real JSON contains **703 conversations and 1,278 assistant turns**, not
1,278 separate conversations. All 3,259 message language labels are `pol`.
There are 584 empty leading system placeholders and 119 real system messages;
254 raw conversations are multi-turn, with 3 to 19 messages including system.

**Superseded schema assumption:** the provisional adapter treated `seq` as
a unique message number. All organic rows instead number instruction pairs:
system `-1`, then user/assistant `0,0,1,1,...`. The main-source adapter now
validates that exact observed pattern and retains original order, content and
message provenance. Syn-ext's unverified adapter has not been generalized on
the basis of another release's schema. Regression tests include the authorized
real main payload and anomaly rejection.

Main conversion produced **596 unique eligible conversations**, including
**179 multi-turn**: 60 identity/brand-review holds, 46 identity-category holds,
and one full-context render/length rejection. No within-source duplicates were
found among eligible rows. Every retained assistant turn is an SFT target;
this differs intentionally from Align's final-preferred-response-only policy.

Isolated main run:

```bash
CUDA_VISIBLE_DEVICES="" TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=1 \
OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.polish_prepare \
  --root data/dfm12/polish_unaudited/pllumic-access-20260924 \
  --run staging-main-v1 --source pllumic --workers 4 \
  --overlap-file data/dfm12/polish_unaudited/staging-20260924-v1/candidates.jsonl
```

Session: `dfm12-pllumic-main-20260924`. Log:
`data/dfm12/polish_unaudited/pllumic-access-20260924/preparation-main-v1.log`.
All new receipts, candidates and pretokenization live under
`data/dfm12/polish_unaudited/pllumic-access-20260924/staging-main-v1/`.
The prior Align run remains untouched and its existing receipt now confirms
1,607 candidates, 926,968 rendered tokens and completed unaudited tokenization.
Its candidate SHA256 remains
`dc86de69cfdfcc80cfd8bc4c682b938decb3eeade516ce4483de0b43fbedd02e`.

The main run rechecks available inherited chats and the prior Align candidate
file; it does not reuse Align's zero-overlap result as evidence for PLLuMIC.
At launch it had completed conversion and was scanning inherited inputs before
tokenization. Completion evidence is added below once verified.

### Verified Main Completion

The main run subsequently completed as `complete_unaudited`; its detached tmux
session exited. No Polish preparation job from this turn remains running.
The final candidate SHA256 is
`eedc2257b8fdfb7fc8274cf4a1893d2cb77284acbca21efc58490ce74c21ddc3`.

| Verified output | Count |
| --- | ---: |
| Downloaded organic conversations | 703 |
| Retained conversations | 596 |
| Retained multi-turn conversations | 179 |
| Retained nonempty system messages | 57 |
| Tokenized assistant targets | 1,006 |
| Rendered training tokens, including repeated context | 548,519 |
| Skipped tokenizer targets | 0 |
| Maximum individual training-example length | 3,276 |

The comparison scanned **72 files / 7,585,588 rows**, including the prior Align
candidates: **6,320,095 comparable message-form rows**, **1,265,493 unsupported
schema rows**, and **zero exact full-conversation overlaps**. Unsupported rows
were counted, not silently treated as verified nonduplicates. Exact comparison
does not cover paraphrases, translations, dialogue prefixes, unavailable
inherited data or concurrent Dolci preparation. Those limitations remain for
later corpus-level review.

`verification.json` independently checks every saved NumPy prompt/response token
segment against untrimmed rendering of its original retained history, verifies
target counts and token totals, rechecks tokenizer/template and candidate
hashes, and confirms the prior Align candidate hash is unchanged. This verifies
full multi-turn preservation and no tokenizer trimming; it is not a content
quality audit. `schema-review.json` at the new work-root level records real-row
schema statistics and retained source-reference evidence (152 distinct refs).

Final artifacts within `staging-main-v1/`:

- `receipt.json` and `verification.json`: completed counts and token-level checks.
- `candidates.jsonl`: all 596 unaudited conversations with provenance.
- `tokenized_unaudited/pllumic/`: NumPy token/offset arrays and completion metadata.
- `overlap.json`: file hashes, comparison counts and unsupported-schema coverage.
- `rejections.jsonl`: 107 holds/rejections with file ordinals and reasons.
- `access-review.json`: successful main access; syn-ext and Align explicitly
  deferred with `network_attempted: false` for this main-only run.

The updated Polish and base DFM12 suites pass **77 tests**. OKF validation now
finds no issue with this page; the final check reports missing index entries for
the separately owned `dfm12-scandi-translated-instruct.md` and
`dfm12-structure-preserving-reordering.md`. No shared index/status
was changed here. No GPU, final sampling, accepted export or audit work was
performed. Syn-ext stays deferred by user direction, not a blocker to this
completed organic staging component.
