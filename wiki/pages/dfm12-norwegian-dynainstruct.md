---
type: Runbook
title: DFM12 Norwegian DynaInstruct CPU Review and Staging
description: Pinned constituent evidence, conservative language and license decisions, and completed unaudited Norwegian staging.
tags: [dfm12, norwegian, data-preparation, licensing, decontamination]
status: draft
last_updated: 2026-09-25
confidence: high
sources:
  - id: composite
    resource: https://huggingface.co/datasets/danish-foundation-models/norwegian-dyna-instruct/tree/b7ea572dd64aa5d052e0086b57ad90da162db7d6
    title: Pinned Norwegian DynaInstruct release
  - id: magpie
    resource: https://huggingface.co/datasets/versae/magpie-qwen3-235B-A22B-bokmaal/blob/e47dc5c0f510425ec0ee064657467803e3477edf/README.md
    title: Pinned Magpie Bokmaal source card
  - id: samtale
    resource: https://huggingface.co/datasets/ltg/nb-samtale-conversations/blob/24e77f0b8f16fa45b63b0f5814c0918fce97567f/README.md
    title: Pinned NB Samtale conversation source card
  - id: reasoning
    resource: https://huggingface.co/datasets/pere/reasoning_norwegian/blob/214ce4bd6dc06156b7f930a8992cedd5a1cf3e1e/README.md
    title: Pinned punctuation restoration source card
  - id: publisher
    resource: https://www.nb.no/sprakbanken/en/resource-catalogue/oai-nb-no-sbr-85/
    title: National Library of Norway corpus publisher and CC0 declaration
---
# DFM12 Norwegian DynaInstruct

## Full NorQuAD/FLEURS Inclusion (2026-09-25)

**Superseded policy:** the owner's subsequent explicit instruction includes
all 1,886 Wikipedia-training NorQuAD QAs, not only the 815 passage-disjoint
subset, and all 1,457 FLEURS EN-to-Bokmal pairs despite their FLORES evaluation
origin. The earlier exclusion/recommendation statements below are historical;
they do not impose a current source hold or another user-approval gate on these
two pinned components. This overrides source admission only, not quality,
language, message-format or rendered-length requirements. No benchmark-clean
claim follows from inclusion. Scandi inclusion is separately owned by Poincare;
this adapter does not change Scandi outputs or shared readiness/audit files.

Completed isolated CPU root:
`data/dfm12/norwegian-benchmark-inclusion-20260925-v1/`.

| Component | Candidates | Native Gemma4 tokens | Maximum rendered length |
| --- | ---: | ---: | ---: |
| `norquad-wikipedia` | 1,886 | 1,353,422 | 1,153 |
| `fleurs-alpaca-en-no` | 1,457 | 121,637 | 187 |
| Total | 3,343 | 1,475,059 | |

All source rows survived structural/source checks, exact conversation dedup and
the actual <=4,096 Gemma4 render limit. Tokenizer skips and duplicate removals
are zero. Full user/assistant content is unchanged from the pinned composite;
no response truncation, paragraph reconstruction or attribution appended to
assistant targets occurs. These are **unaudited candidates, not accepted rows**.

### Evidence and Scoped Adapter

Implementation: `dfm12/norwegian_benchmark_inclusion.py`; independent verifier:
`dfm12/verify_norwegian_benchmark_inclusion.py`; tests:
`tests/test_dfm12_norwegian_benchmark_inclusion.py`.
Composite pin remains `b7ea572dd64aa5d052e0086b57ad90da162db7d6` and both Parquet
downloads match the pinned HF LFS SHA256 values in the earlier evidence tree.
Copied builders, cards and attribution are rehashed against the existing
Norwegian evidence receipt. The earlier benchmark-review inputs are also
rehash-verified and unchanged.

NorQuAD replays the original Wikipedia train JSON at
`701f7db6a51f0264a282ce1ff8e59580251b391e`: exact complete prompt, question and
first annotated answer span, including exact source offset. Composite IDs retain
the traversal index because original question IDs are not globally unique.
Wikipedia article URLs remain explicitly inferred and page revision unknown.
The per-row `benchmark_lineage` records exact passage/question matches against
the original validation/test union: **1,071 passage-overlap rows retained and
815 passage-disjoint rows retained**, with no question matches. This is not
article-level or semantic clearance. CC0 annotation and CC-BY-SA-3.0 passage
notices remain in provenance/attribution, outside model answer content.

FLEURS replays all paired English/Norwegian transcriptions from pinned Google
FLEURS `en_us`/`nb_no` train TSVs at
`70bb2e84b976b7e960aa89f1c648e09c59f894dd`. Provenance retains Ruter revision
`932b5122f77e3566b90806e0eb1b4c1e746213d5`, original row index and FLEURS sentence
ID, FLORES origin/license revision, split names and all attribution fields.
1,442 English matches are exact; 15 preserve the composite's already documented
ASCII-quote removal, not a new cleanup. Human Bokmal targets match verbatim.
The two-language source label `[nob, eng]` is preserved, with target `nb` justified
only by this source's verified `nb_no` pairing. The shared multilingual-label
guard remains unchanged and still rejects generic ambiguous inputs.

Every FLEURS row retains `known_evaluation_origin: true`,
`evaluation_origin: FLORES-101 dev/devtest`, the unsuccessful gated FLORES+
comparison status, and the warning that subsequent FLORES/FLEURS evaluation is
not clean held-out evaluation. CC-BY-SA-4.0 text lineage and Google/Ruter CC-BY-4.0
notices are retained. **Known contamination is annotation for the teacher, not
a source hold under the explicit owner override.** `audit_payload` serializes
the complete candidate including these metadata; tests verify that delivery.

Deduplication uses the existing normalized full-conversation fingerprint within
both additions and against 11,048 previously staged Norwegian conversations
(original eligible staging plus the explicit inclusive integration). Exact
duplicates were zero. This does not claim global/inherited/Scandi or semantic
deduplication; those combined routes remain with their owners.

### Integration and Audit Handoff

- `integration.json`: completed version-1 additive integration, using the
  parent's exact component names; no existing components superseded.
- `sources.json`: two complete candidate/receipt entries for the new audit
  queue owner. No main, PL/IS or other existing audit manifests were changed.
- `authorization.json`: full-source policy, no source hold, audit queue explicitly
  authorized, and unchanged quality gates.
- `candidates/{norquad-wikipedia,fleurs-alpaca-en-no}/candidates.jsonl` and
  `receipt.json`: intact messages, separate attribution, lineage, source hashes,
  counts and token totals.
- `tokenized_unaudited/`: actual native Gemma4 arrays and completion receipts.
- `inputs.json`, `downloads/`, `evidence/`, `process.json`: immutable-source
  checksums, archived evidence and CPU process provenance (PID 2049934, exited).
- `verification.json`: completed independent source replay and equality of
  **every prompt and answer token ID** against the stored arrays, exact dedup,
  input hashes and <=4,096 rendered lengths. No metadata enters assistant targets.
- `handoff-tesla.json`: addressed to Tesla
  `01a0d229-e148-71d3-985c-252d58faf43a`, with completed integration/source paths
  and checksums and request to enqueue immediately in new scoped queues.

This worker has no direct agent-messaging tool. The completed paths were reported
in conversation and the addressed handoff was written; **queue creation/watcher
activation is owned by Tesla, not claimed completed by this CPU worker**. There
is no pending inclusion approval. Do not duplicate or mutate running main/PL/IS
queues or servers to consume these additions.

```bash
CUDA_VISIBLE_DEVICES='' OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.norwegian_benchmark_inclusion \
  --output data/dfm12/norwegian-benchmark-inclusion-20260925-v1 \
  --dedup-manifest data/dfm12/norwegian-inclusive-20260924-v1/integration.json

CUDA_VISIBLE_DEVICES='' OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.verify_norwegian_benchmark_inclusion \
  --root data/dfm12/norwegian-benchmark-inclusion-20260925-v1
```

Preparation refuses existing roots; use a new output path for another run.
The focused adapter plus Norwegian/disposition/core regressions passed **103
tests**. Coverage includes full overlap admission, teacher metadata delivery,
verbatim prompts/targets, source-label/attribution/span rejection, quote handling,
unchanged shared multilingual/template guards, immutable roots and actual render
overflow rejection. No GPU, final sampling, accepted export, or training/eval
changes were performed. Parent maintains shared readiness/status/index updates.

## Historical NorQuAD And FLEURS Review (2026-09-25, Superseded Admission)

Owner requested review, not automatic admission. No source/audit manifest or
training admission was changed. Reproduce the CPU-only exact-text review with
`python -m dfm12.review_norwegian_benchmarks`; evidence and checksums are in
`data/dfm12/norwegian-benchmark-review-20260925/review.json`.

NorQuAD's pinned converter selects 1,886 answerable Wikipedia training QAs
from upstream revision `701f7db6a51f0264a282ce1ff8e59580251b391e`, not its news,
validation or test files. It uses a context/question instruction and shortest
answer text; this is legitimate training-partition supervision in principle,
not automatically test-answer leakage because it belongs to a benchmark.

Exact whitespace-normalized comparisons against all-source original validation
and test (472 QAs each), independently repeated against `ltg/norquad` revision
`be5b02011e6d8752797e75452732c36a3475b657`, found:

| Reference | Training questions matched | Training passages matched (rows) | Context+question matched |
| --- | ---: | ---: | ---: |
| Validation | 0 | 903 | 0 |
| Test | 0 | 271 | 0 |
| Union | 0 | 1,071 | 0 |

Recommendation: retain **815 passage/question-disjoint candidates** for a future
quality audit, rather than blanket admission of all 1,886. These are candidate
counts, not accepted/exported additions. Passage sharing is weaker evidence than
question/answer leakage, but conservative passage isolation is practical here.
Article-level, semantic/translated and full-suite screening remain unperformed.
The installed EuroEval configuration references `EuroEval/norquad-mini`, which
returned 404 with current credentials; its exact payload was not cleared by this
review. The original and current public-mirror split comparisons agreed exactly.

FLEURS-Alpaca contains 1,457 EN->NO pairs. Its pinned builder traces them to
FLEURS train, but the [official FLEURS card](https://huggingface.co/datasets/google/fleurs)
states that its 2,009 parallel sentences originate from FLORES dev/devtest.
Speech-training split names do not make those sentences new text-training data.
The composite's own datasheet explicitly warns against FLORES/FLEURS evaluation
after training on this subset. **Recommendation: keep excluded**, retaining
future multilingual translation-benchmark validity. This is a contamination
decision, not a newly imposed DynaInstruct license veto. An attempted independent
FLORES+ exact-text comparison returned gated 403; no row-level matches to FLORES+
are claimed. Published lineage and the pinned converter suffice for this
conservative recommendation, but do not prove overlap with our current WMT task.

This refines the earlier blanket NorQuAD/FLEURS exclusion rationale below;
the operational exclusion itself remains unchanged pending an inclusion decision.

Completed on 2026-09-24: **5,307 unaudited staging conversations**, comprising
4,657 NB and 650 NN, and **2,675,108 rendered tokens**. Nothing is accepted,
audited, sampled into DFM12, or added to a training/evaluation configuration.
This constituent-specific review supersedes the earlier blanket review-held
description for the eligible staging rows only. Shared catalog approval remains
unchanged; this is not approval for training inclusion.

Related: [component preparation](dfm12-components.md),
[shared status snapshot](dfm12-status.md), [DFM12 plan](dfm12-plan.md),
[OKF rules](/schema.md).

## Decisions and pinned evidence

### User supersession: include unknown and mixed standards, 2026-09-24

**Superseded by explicit user instruction:** the final omission policy below
is no longer the current preparation decision. Include all 4,496 punctuation
rows and all 1,245 mixed Samtale pairs as unaudited material without guessing
a Norwegian standard. Historical omission/license/preparation receipts remain
unchanged; the new outputs are disjoint additions, not replacements.

Completed additive root: `data/dfm12/norwegian-inclusive-20260924-v1/`.
All **5,741 rows** passed conversion, exact-overlap and full-conversation dedup
checks against original Norwegian staging and each other, then pre-tokenized
to **1,757,549 tokens**. There were zero rejections and zero tokenizer skips.
Original **5,307 rows / 2,675,108 tokens** remain byte-identical. Combined staging
is **11,048 rows / 4,432,657 tokens**, still unaudited and unaccepted; the five
original overlength Magpie rejections remain unchanged.

Both additions use `language: no`, not false `nb`. Punctuation records carry
`norwegian_standard: unknown` and ordered `message_languages: [no, no]`.
Mixed Samtale records carry `norwegian_standard: mixed`, ordered `nb`/`nn`
message labels, and `speaker_variants` with the original speaker IDs, `bm`/`nn`
orthography and normalized language. Speaker labels and content were verified
against pinned originals. Observed composite labels remain in provenance;
the hardcoded reasoning `nob` is not treated as reliable standard evidence.
Licenses and attribution remain preserved, with no license blocker.

Implementation: `dfm12/norwegian_inclusive.py`; focused tests:
`tests/test_dfm12_norwegian_inclusive.py`. Shared conversion rules and language
configuration were not broadened. A narrow change in `dfm12/audit_readiness.py`
admits generic Norwegian only for these pinned constituents with the explicit
user policy and validated unknown/mixed metadata. Metadata stays outside
student messages. **57 tests passed** across inclusive, original Norwegian,
disposition and audit-readiness tests.

Audit owner handoff: `data/dfm12/norwegian-inclusive-handoff-20260924.md`.
Pass `data/dfm12/norwegian-inclusive-20260924-v1/integration.json` using
`--integration-manifest` on the owner's next readiness refresh. It has two
new component keys, empty `supersedes`, checksummed candidate receipts and
`resolves: [norwegian-variant-holds]`. The latter resolves the preparation
policy only, not variant certainty, quality, or contamination clearance.
Discovery was verified to retain both original Norwegian components.
`verification.json` records full-row schema/dedup/student-isolation validation
and rehashing of the 20 original outputs. No shared audit snapshot or queue was
refreshed, sampled, activated or overwritten by this work.

No direct agent messaging capability was available, so Tesla delivery or
acknowledgement is not claimed. The parent must forward the handoff or supply
the integration path to the audit owner. Preparation and validation completed
with one CPU worker and empty CUDA visibility; no processes remain running.
No GPUs, teacher audits, final sampling, or training/evaluation changes.

### Final held-subset disposition, 2026-09-24

**Superseded:** the remaining open variant hold described below is now an
explicit omission for this preparation, under the user's final disposition
request. No new variant evidence is inferred. All 4,496 punctuation rows are
omitted with `unsupported_nb_nn_variant`; all 1,245 mixed Samtale pairs are
omitted with `mixed_nb_nn_speaker_orthography`. The latter were already rejected
and are not additional losses. License blockers are zero. Earlier receipts and
the dated review narrative below are preserved as history.

Machine-readable final authority for this subset:
`data/dfm12/norwegian-20260924/final-variant-disposition.json`. It records all
5,741 omitted source IDs, zero-based Parquet ordinals, original labels, canonical
row SHA-256 hashes, source pin, reason codes, evidence/review hashes, and the
20 preserved output hashes. Assigned variants are null, never guessed. The
reasoning source's hardcoded `nob` is recorded as an observed label, not trusted
variant evidence. Pinned upstream speaker orthography was rechecked for every
Samtale row, including the mixed pairs.

Accounting: **11,053 downloaded = 5,307 unchanged staged + 5,741 omitted + 5
overlength rejections**. Tokens remain **2,675,108**; newly staged rows and
remaining held rows are both zero. This closes the CPU held-subset disposition,
not quality auditing or benchmark clearance. NorQuAD and FLEURS remain excluded.
Existing staging stays unaudited and unaccepted. No GPUs, sampling, delegation,
shared configuration changes, or existing output rewrites were performed.

Implementation: `dfm12/norwegian_disposition.py`; separate regression tests:
`tests/test_dfm12_norwegian_disposition.py`. The append-only command takes the
existing run lock, verifies pinned evidence and original/review receipts,
rehashes all 20 existing outputs, reconciles counts, and refuses overwrite.
Validation rebuilds the entire manifest and requires exact equality. Commands:

```bash
CUDA_VISIBLE_DEVICES='' OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.norwegian_disposition --root data/dfm12/norwegian-20260924
CUDA_VISIBLE_DEVICES='' OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.norwegian_disposition --root data/dfm12/norwegian-20260924 --validate
```

Creation PID 964769 exited successfully, using one CPU worker. Full manifest
validation succeeded. Both Norwegian test files passed **35 tests** together.
No necessary process remains running. Shared index/status updates remain owned
by the parent; link this page and use the final disposition instead of the
historical open-hold status.

Composite source: `danish-foundation-models/norwegian-dyna-instruct`, revision
`b7ea572dd64aa5d052e0086b57ad90da162db7d6`, source key `dyna-instruct-no`.
The isolated runner verifies this against `data/dfm12/sources.lock.json` without
editing it. Composite cards, builders, attribution sidecars, LICENSE, upstream
cards/data, and license texts are retained with URL/SHA-256 receipts.[^composite]

| Constituent | Preparation decision | Evidence and remaining limitation |
| --- | --- | --- |
| `magpie-qwen3-bokmaal` | Prepare as unaudited NB | Upstream revision `e47dc5c0f510425ec0ee064657467803e3477edf` explicitly names Bokmål and Apache 2.0, Qwen3-235B-A22B, Magpie, and no external seeds. Every composite conversation matches the pinned original fields. The builder's generic Norwegian classifier does not itself establish variant purity; upstream explicit Bokmål provenance supports staging, with quality/variant audit still pending. |
| `nb-samtale-pairs` | Prepare single-variant NB/NN pairs only | Upstream revision `24e77f0b8f16fa45b63b0f5814c0918fce97567f` and the publisher declare CC0. Every pair's text, distinct speaker IDs, and `bm`/`nn` orthography were checked against pinned originals. Mixed variants are rejected, not assigned by majority or assistant language. Speech turns can lack context and are not necessarily good assistant supervision. |
| `reasoning-norwegian` | Hold all rows for variant evidence only | Upstream revision `214ce4bd6dc06156b7f930a8992cedd5a1cf3e1e` declares `en`/`no`; all 6,245 upstream train rows lack language/orthography fields. Composite builder hardcodes `nob`. All 4,496 attribution URLs point to `no.wikipedia.org`, useful provenance but not an independent row-level variant audit. Supported NB/NN identification remains required. Upstream CC BY-SA 3.0 versus composite 4.0 claims are retained as provenance, not blockers under the 2026-09-24 authorization. This is punctuation/capitalization restoration, not general reasoning supervision. |
| NorQuAD / FLEURS | Excluded | No Parquet downloaded or converted. Cards/builders/attribution were retained for review only. NorQuAD is benchmark-derived even though the builder selects its Wikipedia training partition. FLEURS text derives from FLORES-101 dev/devtest. |

The upstream license and language claims are source evidence, not independent
legal clearance or a completed language-quality audit.[^magpie][^samtale][^reasoning][^publisher]
Do not blanket-relicense outputs under the composite repository's Apache code
license. Retain the selected constituents' original licenses, source IDs and
attribution references. Held-source attribution is retained for review.

## Explicit license authorization update, 2026-09-24

The user's `data/dfm12/norwegian-license-authorization-20260924.md` authorizes
all DynaWord/DynaInstruct licenses in all languages. **Superseded:** the initial
2026-09-24 punctuation decision held both variant evidence and the upstream
CC BY-SA 3.0/composite 4.0 discrepancy. The license component is now removed;
the original claims and dated receipt remain preserved, without relicensing.
All current code decisions explicitly have `license_blocker: false`.

The CPU continuation downloaded the pinned upstream `train.jsonl` (51,425,543
bytes; SHA-256 `63868e248b867b71e3c56e86c14fa854a3b387596464b2023f690675bd7ea2a8`,
matching its upstream LFS hash). It inspected every one of 6,245 rows: none
contains `language`, `lang`, or `orthography`. All 4,496 selected composite
rows matched upstream responses/corrupted text and article/paragraph
attribution; all passed the builder's lexical-preservation check. Their
variant remains unsupported beyond the hardcoded composite label and URL
provenance, so **4,496 remain held for a non-license reason**. Generic
Norwegian and `no.wikipedia.org` alone are not mapped to NB by this adapter.

Additional exact overlap diagnostics on those held rows found zero rows whose
`original_text`, `corrupt`, or `text_result` exactly matched any normalized
field from the pinned validation/test files. This does not establish semantic
decontamination or general benchmark clearance. NorQuAD/FLEURS stay excluded.

The current decision receipt is
`data/dfm12/norwegian-20260924/license-review-20260924/review-receipt.json`.
It supersedes **only the license-blocking interpretation** of the original
receipt, carries the authorization hash and preserved source-license claims,
and references checksummed existing eligible outputs. Nothing was overwritten
or duplicated: **new prepared rows 0; total prepared rows 5,307; total tokens
2,675,108; license rejections 0**. All remain unaudited and unaccepted.
The original implementation was archived as
`implementation-before-license-authorization.py`, matching the original
preparation receipt's implementation hash.

Continuation PID **594490** completed successfully at 06:57:14 UTC. It used
one CPU worker, empty CUDA visibility and single-thread libraries. Before
continuation, load was 107.96/102.47/82.13, available memory 1.5 TiB and disk
2.0 PiB. No other jobs or shared files were changed. The updated focused test
suite passed **22 tests**, including license authorization, preservation of
conflicting source metadata, and rejection of unsupported variant inference.
The follow-up verification rehashed 20 original output files, 31 original
evidence files, and two new review files, confirmed the original receipt and
archived implementation, reacquired the lock, and confirmed PID 594490 exited.
Its record is `license-review-20260924/verification.json`. Follow-up OKF
validation reported three missing index links: this page (expected),
`dfm12-island-instruct.md`, and `dfm12-polish-instructions.md`; zero warnings.
The latter two are concurrently authored pages outside this worker's ownership.

Reproduce the append-only reassessment on an original completed root:

```bash
CUDA_VISIBLE_DEVICES='' OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false /home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.norwegian license-review --root data/dfm12/norwegian-20260924
```

The review directory now exists, so this command refuses another write to it.
Current authorization does not waive variant, quality, format, contamination,
audit, or acceptance checks. No eligible unfinished preparation job remains.

## Actual schemas, labels, and counts

All three selected Parquet files have `id`, `source`, `added`, `created`, `task`
as strings; `messages` as a list of `{role: string, content: string}`;
`language` as a list of strings; and `token_count` as int64. That upstream
token count uses Llama 3, not the DFM11 tokenizer; staging recomputes counts.

Upstream Magpie schema is `category/system/instruction/response`; Samtale is
`id/messages/speakers/source_type`, with orthography inside speaker records.
Inspected reasoning held-out JSONL fields are `url`, `paragraph_number`,
`corrupt`, `corrupt_level`, `original_text`, `text_result`, `reasoning`, `text`.

| Constituent | Downloaded/scanned | Actual labels | Staged / pre-tokenized | Rejections or hold | DFM11 tokens |
| --- | ---: | --- | ---: | --- | ---: |
| Magpie | 1,822 | 1,822 `[nob]` | 1,817 NB | 5 over 4,096 rendered tokens | 2,170,552 |
| Samtale | 4,735 | 2,840 `[nob]`; 650 `[nno]`; 624 `[nob,nno]`; 621 `[nno,nob]` | 3,490: 2,840 NB + 650 NN | 1,245 mixed-variant pairs | 504,556 |
| Punctuation | 4,496 | 4,496 `[nob]`, hardcoded by composite | 0 | 4,496 held for supported variant identification only | 0 |
| Total | 11,053 | No generic label is inferred as NB | 5,307 | 1,250 rejected + 4,496 held | 2,675,108 |

Three Parquet downloads total 15,278,733 bytes; their hashes match pinned HF
LFS SHA-256 values. All 6,557 Magpie/Samtale rows match their upstream content
and labels before staging filters. Whitespace-normalized full-conversation
deduplication runs jointly across both eligible constituents: **zero duplicate
rejections** among otherwise eligible rows. It does not cover other DFM12
components or inherited DFM11. No assistant response is truncated. Tokenizer
skips are zero and array example/token totals match conversion totals.

## Benchmark limits

Exact screening compares eligible full messages against 1,426 distinct
whitespace-normalized `original_text`, `corrupt`, and `text_result` fields from
500 pinned reasoning validation/test rows. There are **zero exact hits in
that limited screen**. Held-out files live only in the evidence directory,
outside tokenizer inputs. Case, punctuation, substrings, translated variants,
paraphrases, and shared source articles are not screened by that equality test.

No claim is made that benchmarks are clear. NorQuAD/FLEURS are excluded by
source selection; their benchmark text was not exhaustively compared with the
eligible corpora. Synthetic Magpie can reproduce memorized evaluation content
despite seed-free generation. Wikipedia-derived punctuation material may
share articles/passages with other tasks; selecting upstream train alone
would not establish decontamination. Samtale can overlap speech evaluations
using the same corpus. Semantic decontamination, broader benchmark comparison,
cross-component deduplication and human/teacher quality review remain pending.

## Operations and receipts

Implementation: `dfm12/norwegian.py`; tests: `tests/test_dfm12_norwegian.py`.
Output root: `data/dfm12/norwegian-20260924/`.

- `evidence-receipt.json`: 31 downloaded evidence/data files, exact URLs,
  hashes, sizes, source pin, and upstream LFS hashes where available.
- `preparation-receipt.json`: decisions, per-constituent counts/schemas,
  staging/output hashes, tokenizer/template hashes, benchmark scope, and
  explicit `accepted: false`, `audit_status: unaudited`.
- `downloads/data/`: review downloads of the three selected constituents.
- `staging_unaudited/{magpie-qwen3-bokmaal,nb-samtale-pairs}/part-00000.jsonl`:
  conversations with provenance and explicit unaudited status.
- `tokenized_unaudited/`: separate per-constituent arrays and completion records.
- `evidence/composite/`, `evidence/upstream/`, `evidence/licenses/`: retained
  cards, source builders, original content, attribution, and licensing evidence.
- `progress.jsonl`, `preparation.log`, `resources.json`: isolated operational
  records; `.run.lock` prevents concurrent writers.
- `verification.json`: independent rehash of all 31 evidence/download files
  and 20 staging/tokenization files, normalized-chat uniqueness, token-array
  bounds/totals, released lock, and exited process checks.

The evidence process PID was **574165**; preparation PID was **579337**.
Both completed and exited; preparation completed at 06:51:33 UTC. No
necessary preparation job remains running. CPU capacity at startup: affinity
384 CPUs and cgroup quota 384 CPU equivalents; load 66.42/80.72/63.62;
1.7 TiB available memory and 2.0 PiB available disk. Later load increased to
114.32, so workers stayed at **one**. CUDA visibility was empty, with BLAS,
Arrow, Rayon and tokenizer concurrency limited. No GPU queries, audits,
training, evaluation, or final sampling were run; other jobs were untouched.

Commands, from repo root (new output roots only):

```bash
CUDA_VISIBLE_DEVICES='' OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false /home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.norwegian evidence --root data/dfm12/NEW-NORWEGIAN-ROOT
CUDA_VISIBLE_DEVICES='' OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false /home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.norwegian prepare --root data/dfm12/NEW-NORWEGIAN-ROOT
CUDA_VISIBLE_DEVICES='' OPENBLAS_NUM_THREADS=1 /home/ucloud/miniforge3/envs/hrm/bin/python -m pytest tests/test_dfm12_norwegian.py -q
```

Existing evidence/staging/tokenized paths are refused rather than overwritten.
A failed partial run requires investigation and a new isolated output root.
The 15 focused tests passed; the real full preparation independently checked
every eligible upstream row and conversion/token-array count. Receipts were
rehashed after completion. OKF validation returned two missing index links:
this page (expected until parent indexing) and concurrently created
`dfm12-island-instruct.md`; zero warnings. No other errors were reported at
that check. Shared indexes were intentionally left to the parent.

Parent handoff: add `[DFM12 Norwegian DynaInstruct](dfm12-norwegian-dynainstruct.md)`
to `wiki/pages/index.md`, link this review from shared DFM12 status/components,
and record it in `wiki/log.md` if desired. Those shared files, shared config,
catalog, source lock, and paragraph-repair-owned modules were not edited.

[^composite]: Pinned composite release, retained cards, builders and Parquet schema.
[^magpie]: Pinned Magpie upstream card and original JSONL.
[^samtale]: Pinned NB Samtale upstream card and original speaker records.
[^reasoning]: Pinned reasoning upstream card and composite attribution.
[^publisher]: National Library of Norway resource catalogue, retrieved 2026-09-24.
