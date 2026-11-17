---
type: Technical Reference
title: DFM15 Metadata Routing Sidecar Preparation
description: CPU-only reconstruction of exact source token ranges and source-domain categories for the DFM15 epoch-zero MoE pilot.
status: draft
confidence: high
last_updated: 2026-10-20
tags: [dfm15, moe, metadata, provenance]
---
# DFM15 Metadata Routing Sidecar Preparation

## Source-Domain Recovery (2026-10-20, Later Update)

**Published and post-verified:** the new file
`incoming/mimir-xl-20261015/data/sampled_dfm15/epoch_0/category_id.npy`
has shape `(408412700,)` and dtype `uint8`. The publication receipt is
`data/category_preparation/dfm15-epoch0-source-domains-published-20261020/receipt.json`;
it records `status: verified`, `published: true`, and zero uncovered rows.
After publication, the live sidecar checksum, shape, dtype, and hard-link
identity were checked, and every tracked input's stat signature was unchanged.
Only this new sidecar was added to the sampled dataset. No active training,
scheduler, GPU, tokenizer, or configuration was touched. Epoch-zero data
preparation for the biased MoE pilot is complete; launching the pilot remains
a separate action.

The user clarified that metadata should use source/subdataset domains, not
per-example semantic judgments. The earlier requirement for a fully
authenticated token payload is **superseded**: documented assembly order,
source-header lengths, inventories, append/replacement receipts, and exact
boundary/row checks suffice. No token payload hashing or tokenizer execution
is needed. Ambiguous/general-purpose subdatasets are explicitly neutral;
missing source ownership remains an error.

`--recover-dfm15 --index-receipt <earlier census receipt>` reconstructs:

| Stage | Exclusive token boundary |
| --- | ---: |
| DFM11 sorted source stores | 223,595,843,215 |
| DFM12 inventory, sorted within group | 237,402,261,201 |
| DFM13 inventory, sorted within group | 248,562,536,687 |
| DFM14 original parts, sorted by sampler alias | 255,888,663,804 |
| Native-reasoning replacements, receipt order | 263,803,473,872 |
| Registered DFM15 additions, registry/part order | 263,979,771,785 |
| Answer-conditioning v1 | 263,981,319,962 |
| Answer-conditioning v2 / final store | 264,134,952,845 |

All boundaries match exactly. There are 38,877 nonempty source ranges.
Native repairs retain original source-domain labels and are checked against
their original offsets and lengths. Historical math-range anchors also match.
Conditioning v1 was important: its 1,250 variants occupy 1,548,177 tokens
between the registered additions and v2. Both retained `mapping.npz` files
are checked for exact old-span ownership and contiguous new offsets before
their appended intervals receive a math label. V2 has 521,883 variants.

The explicit `source-domain-v1` policy uses only source identifiers.
Math/code/tool-agentic families receive `1`; explicit language operations,
chat/conversation, summarization, and translation families receive `2`.
Mixed/general-purpose collections and uncertain identifiers receive `0`,
with a recorded rationale. No prompts or responses are decoded or judged.
The implementation records each part's resulting label, source name, bounds,
and rationale, so broad mixed collections can be refined later without
claiming example-level labels. Do not change the policy during a resume.

The new preparation output is
`data/category_preparation/dfm15-epoch0-source-domains-20261020/`.
Its full row verification passed: **408,412,700 rows, zero uncovered rows**,
and all four complete index-file hashes match the initial census.

| Category | Rows | Instruction + response token exposure |
| --- | ---: | ---: |
| 0: neutral / uncertain subdataset | 131,528,412 | 72,041,676,157 |
| 1: math / code / tool-agentic | 78,138,587 | 26,338,898,009 |
| 2: language / chat / summarization / translation | 198,745,701 | 36,136,056,568 |
| Total | 408,412,700 | 134,516,630,734 |

The uint8 sidecar SHA256 is
`df51a0a811d8b477acdfdee82e1c4137f948241177f29b8c6d64d2ae0362e842`.
It preserves the exact sampled row order. Category 0 must have a zero metadata
bias row; categories 1 and 2 identify the two optional specialist preferences,
not extra experts. No active configuration has been changed.

The implementation uses vectorized range searches and per-chunk bincounts,
not one full chunk scan per source. Floating-point bincount sums are converted
to integer after each chunk; the explicit chunk-size bound guarantees exact
integer representation. Source/header inventories and supporting receipts are
retained in the manifest; input/index hashes and per-source exposure are in
the receipt. The token payload is still neither read nor hashed.

Reconstruction and isolated preparation:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/prepare_metadata_categories.py \
  incoming/mimir-xl-20261015/data/sampled_dfm15 \
  /tmp/dfm15-routing-recovered-20261020.json \
  data/category_preparation/dfm15-epoch0-source-domains-20261020 \
  --recover-dfm15 \
  --index-receipt data/category_preparation/dfm15-epoch0-20261020/receipt.json
```

The atomic publication pass repeats full row/index-hash verification:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/prepare_metadata_categories.py \
  incoming/mimir-xl-20261015/data/sampled_dfm15 \
  data/category_preparation/dfm15-epoch0-source-domains-20261020/category-manifest.json \
  data/category_preparation/dfm15-epoch0-source-domains-published-20261020 \
  --publish
```

Use fresh preparation/manifest paths for reruns; existing output directories
and existing published sidecars are intentionally never replaced.
Twenty-four CPU tests pass, including source-domain policy, a synthetic full
DFM11-to-DFM15 assembly, mismatch detection, and both conditioning-map checks.
This is an epoch-zero pilot artifact only; epochs 1 and 2 remain unprepared.

## Initial Outcome (Superseded)

**Historical initial result: blocked; no sidecar published at that point.**
The requested dense 2/2 MoE
preparation audited
`incoming/mimir-xl-20261015/data/sampled_dfm15/epoch_0`.
No GPU, tokenizer, training, scheduler, active configuration, token payload,
or existing sampled array was modified. No administrative locks were acquired.

The full CPU census found:

| Measurement | Rows | Token exposure |
| --- | ---: | ---: |
| All epoch-zero rows | 408,412,700 | 134,516,630,734 |
| Candidate math provenance | 7,842,993 | 2,427,474,498 |
| Missing exact source ownership | 400,569,707 | 132,089,156,236 |

Exposure counts instruction plus response lengths, including repeated sampled
rows. Shifted exposure is 134,108,218,034 tokens (one autoregressive shift per
row). The candidate math count matches the historical conditioning census,
but this is a consistency check, not proof of the entire provenance chain.
No language or neutral labels were fabricated for uncovered rows.

## Artifacts and Contract

Implementation: `scripts/prepare_metadata_categories.py`.
Tests: `tests/test_prepare_metadata_categories.py`.
Artifacts: `data/category_preparation/dfm15-epoch0-20261020/` contains
`category-manifest.json` and `receipt.json`, including per-source ranges,
classification rationale, counts, exposure, evidence SHA256s, complete NPY
index-file SHA256s, and before/after input-stat stability checks.

The token payload was **not hashed or scanned**: it is approximately 984 GiB.
The receipt explicitly distinguishes token-store shape/stat identity from
payload verification. Only its NPY header was read. The four index arrays
were fully scanned and hashed, using one process and 250,000-row chunks.
These hashes identify the audited row order; they do not prove source labels.

Category meanings:

* `0`: neutral or uncertain **domain of a known source**, with explicit rationale.
* `1`: math, code, or tool-agentic source.
* `2`: language, chat, summarization, or translation source.

Missing provenance is never silently assigned `0`. Both nonempty instruction
and response spans must fit the exact same source interval, even if two
different sources have the same category. An empty instruction has no source
ownership requirement. Overlap, invalid categories, signed negative indices,
out-of-bounds spans, empty responses, and rows over 4097 tokens are rejected.

Publication requires reviewed `provenance_status: verified`, hashed supporting
evidence, matching metadata/epoch/token count, expected hashes for all four
sampled index arrays, and complete row coverage. Prepared uint8 NPY output
lives outside the sampled dataset. `--publish` uses an atomic no-clobber hard
link and therefore requires the preparation directory on the same filesystem.
An existing sidecar is never replaced. Publication does not enable sampler
configuration. Input mutation during the scan or before publication aborts.

## Provenance Findings and Completion Path

`data_io/sample_tokenized.py` concatenates source token stores in sorted task
order and adds their offsets to sampled indices. Source names or equal row
counts alone are not row correspondence evidence.

`scripts/build_dfm15_full_sample.py` interleaves additions without preserving
global source row order. It deletes some assembly intermediates.
`scripts/condition_dfm15_math_answers.py` subsequently rewrites complete index
tuples to appended token variants. Exact provenance must account for these
transformations and the earlier native-reasoning replacement chain.

The transferred `data/dfm15/math-answer-conditioning-v2/source-ranges.json`,
`before.json`, `preparation.json`, and final sampled `validated.json` support
the partial candidate manifest. The appended conditioning interval contains
math variants according to the producer script. These receipts do not provide
a complete source-range map for the final mixture.

Local DFM11 reservoirs and native-reasoning repair inventories exist, as do
DFM14 inheritance/reconciliation receipts. Some remote inheritance references
explicitly record `reference_only_not_payload_hashed`. A complete authenticated
map of the transferred token store was not established during this task.
Do not turn the candidate manifest into verified provenance merely by
changing its status or copying the census hashes.

To unblock:

1. Recover the authoritative ordered source-token map for the inherited base,
   including DFM12/13/14 reconciliation and append boundaries. Bind that map
   to the transferred token store through original authenticated receipts or
   exact bounded streaming comparisons; total lengths alone are insufficient.
2. Replay provenance only for native-reasoning replacements, ordered DFM15
   additions, and conditioning old/new index mappings. Do not rerun tokenizers
   or rewrite the sampled arrays. Validate every transformation boundary.
3. Explicitly review source domains. Mixed or ambiguous sources receive `0`
   with a rationale, not a broad filename-based math/language guess.
4. Bind the verified map to the metadata and index hashes in the census,
   then run the strict builder into a fresh preparation directory.
5. Publish only when all checks pass. Any later epoch needs its own full
   aligned census and sidecar before homogeneous-category training uses it.

## Reproduction and Tests

Reproduce the partial audit without regenerating its manifest:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/prepare_metadata_categories.py \
  incoming/mimir-xl-20261015/data/sampled_dfm15 \
  data/category_preparation/dfm15-epoch0-20261020/category-manifest.json \
  data/category_preparation/dfm15-epoch0-recheck
```

Exit code `2` means a completed audit blocked publication; `receipt.json`
explains why. `--seed-transferred-math` creates a new partial candidate manifest
from the transferred receipts and is incompatible with `--publish`.
For a completed verified manifest, use the same command with a fresh output
directory and optionally `--publish`.

Thirteen CPU tests passed:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m pytest -q \
  tests/test_prepare_metadata_categories.py
```

Coverage includes exact non-source-sorted row order, exposure accounting,
empty instructions, immutable publication, source gaps, candidate status,
hash mismatch, cross-source spans, overlapping/noninteger ranges, negative
and out-of-bounds indices, invalid lengths, evidence tampering, input mutation,
and chunk-size invariance.

OKF validation was run and found one unrelated existing/concurrently edited
oversize concept, `model-architecture/request-shared-eval-scheduler.md`
(51,441 bytes), plus 15 unresolved artifact-link warnings. The new page and
index entry produced no validation findings; the other page was left untouched.

See [v2 metadata loading and bias semantics](model-architecture/hrm-text-v2-implementation.md)
and [expert execution semantics](model-architecture/hrm-text-v2-experts.md).
Those architecture/branch pages were intentionally not edited.
