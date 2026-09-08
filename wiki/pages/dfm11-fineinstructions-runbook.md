---
type: Runbook
title: DFM11 FineInstructions Runbook
description: Source admission, setup, extraction, retrieval-index construction, and production gates for the DFM-owned FineInstructions pipeline.
tags: [dfm11, fineinstructions, synthetic-data, retrieval, provenance, runbook]
status: draft
last_updated: 2026-09-01
confidence: high
sources:
  - id: fineinstructions-paper
    resource: https://arxiv.org/abs/2601.22146
    title: "FineInstructions: Scaling Synthetic Instructions to Pre-Training Scale"
    author: org:FineInstructions
  - id: fineinstructions-artifacts
    resource: https://huggingface.co/fineinstructions
    title: FineInstructions model and dataset artifacts
    author: org:FineInstructions
  - id: dfm-fineinstructions-code
    resource: https://github.com/schneiderkamplab/fineinstructions
    title: DFM-owned FineInstructions implementation
    author: org:Schneider-Kamp-Lab
---
# DFM11 FineInstructions Runbook

## Purpose and boundary

The `fineinstructions` submodule reproduces the FineInstructions method with
DFM-owned inputs. It does not use rows from
`fineinstructions/fineinstructions_nemotron`,
`fineinstructions/real_queries`, or `fineinstructions/finetemplates`, and it
does not use the upstream FineTemplates FAISS index or reweighting statistics.

Two independently approved source pools are required:

- **query sources:** realistic user instructions from DFM instruction/chat
  datasets, used only to create new generic templates;
- **document sources:** raw or grounding documents already admitted by DFM
  policy, used to instantiate templates and ground answers.

The DFM sampling YAML is not a source-admission manifest. Prefixes and repeats
do not identify original fields, revisions, provenance, or legal bases. Build
and review a dedicated FineInstructions source manifest from the finalized DFM
source inventory before production extraction.

## Repository setup

The implementation is a separately versioned submodule:

```bash
cd /work/dfm/HRM-Text
git submodule update --init fineinstructions
git -C fineinstructions status --short --branch
git -C fineinstructions rev-parse HEAD
```

The initial implementation commit is `a4442c2`. At the time of this record it
exists locally but has not been pushed because non-interactive GitHub
credentials were unavailable. Push the submodule commit before committing and
pushing a parent gitlink that references it.

Install the CPU/configuration and test dependencies inside the submodule:

```bash
cd /work/dfm/HRM-Text/fineinstructions
uv sync --extra test
uv run pytest
```

Install retrieval dependencies only where index construction or search will
run:

```bash
uv sync --extra test --extra retrieval
```

Runtime artifacts belong under the parent repository's ignored `data/` and
`logs/` trees, never inside the submodule Git history.

## Artifact pins

`src/dfm_fineinstructions/artifacts.py` pins the learned stages:

| Stage | Repository | Revision |
|---|---|---|
| Query templatization | `fineinstructions/query_templatizer` | `4f556de33330ce8382079b04d254fe11cee71358` |
| Retrieval embedding | `fineinstructions/instruction_template_retrieval_embedding` | `e528b0b7e8194b86e5b908da914f1ea6e5787da7` |
| Template instantiation | `fineinstructions/template_instantiator` | `5a4c210791c5d232a264c5e115b942ca122297a1` |

The artifacts implement the learned tasks described by the paper, but their
Hugging Face cards currently declare no licenses. Record an explicit model-use
decision before downloading or serving them for production. This decision is
separate from every query/document source decision.

## Source manifest

Start from `fineinstructions/configs/dfm11.example.yaml`, but do not change its
placeholder sources to `approved` without reviewing them. Each source entry has
the following contract:

| Field | Meaning |
|---|---|
| `id` | Stable, unique provenance identifier |
| `roles` | `query`, `document`, or both after independent review |
| `paths` | Parent-repository-relative glob patterns |
| `format` | `jsonl`, `jsonl.gz`, or `parquet` |
| `admission` | `approved`, `review_required`, or `denied` |
| `provenance` | Human-readable origin and conversion receipt |
| `license_or_basis` | Recorded source-policy decision, not merely a Hub label |
| `revision` | Immutable source or conversion revision/hash |
| `query_fields` | Dotted paths containing standalone user queries |
| `messages_field` | Optional message-list path; only `role=user` is extracted |
| `document_fields` | Dotted paths containing grounding documents |
| `hash_keep_fraction` | Deterministic source-level sampling fraction |
| `max_rows` | Optional post-hash cap for a pilot |

Use original user requests as queries. Do not mine assistant answers as query
templates. Use authentic raw/grounding text as documents; do not recycle
synthetic assistant answers as the knowledge reservoir. Preserve English and
Danish source labels in provenance and measure balance after filtering.

Validate the manifest from the submodule:

```bash
cd /work/dfm/HRM-Text/fineinstructions
uv run dfm-fineinstructions validate-config configs/dfm11.yaml
uv run dfm-fineinstructions plan configs/dfm11.yaml
```

The validator is fail-closed. If any source participating in the requested role
is `review_required` or `denied`, extraction raises an error rather than
silently skipping it.

## Canonical extraction

The source paths are relative to `/work/dfm/HRM-Text`, while the CLI is normally
launched from the submodule. Pass `--base-dir ..` explicitly:

```bash
cd /work/dfm/HRM-Text/fineinstructions

uv run dfm-fineinstructions extract configs/dfm11.yaml \
  --role query \
  --base-dir ..

uv run dfm-fineinstructions extract configs/dfm11.yaml \
  --role document \
  --base-dir ..
```

Canonical JSONL is written atomically under:

```text
data/fineinstructions/dfm11/canonical/query/<source-id>.jsonl
data/fineinstructions/dfm11/canonical/document/<source-id>.jsonl
```

Each record retains a deterministic SHA-256 ID, kind, text, source ID,
revision, source path, and row number. Hash sampling is deterministic for the
configured seed. Record counts should be captured in a campaign receipt before
starting GPU work.

## Template generation

For every deduplicated canonical query:

1. render the bare query as the user message expected by the pinned
   `query_templatizer`; do not add an invented instruction around it;
2. require one parseable JSON object containing at least `template` and
   `compatible_document_description`;
3. preserve `source_query_id`, artifact repository/revision, decoding
   parameters, and attempt ID;
4. reject malformed `<fi>...</fi>` variables, nongeneric templates, leaked PII,
   language mismatch, protected-eval overlap, and near duplicates;
5. derive complexity/reweighting statistics from this new template bank rather
   than importing upstream statistics.

Resumable multi-GPU templatizer serving and production finalization are not yet
implemented. Do not represent the current package as production-complete until
this stage has atomic claims, retries, receipts, and validation.

## Build the DFM template index

The implemented index builder expects JSONL records matching the
`FineTemplate` contract:

```json
{"id":"...","source_query_id":"...","template":"Summarize <fi>topic</fi>","compatible_document_description":"A document explaining ...","generator_repo":"fineinstructions/query_templatizer","generator_revision":"4f556de33330ce8382079b04d254fe11cee71358"}
```

Build a new exact cosine-similarity FAISS index:

```bash
cd /work/dfm/HRM-Text/fineinstructions
uv run dfm-fineinstructions build-index \
  ../data/fineinstructions/dfm11/templates/final.jsonl \
  ../data/fineinstructions/dfm11/index \
  --batch-size 256 \
  --device cuda
```

The output contains `templates.faiss`, `templates.jsonl`, and `receipt.json`.
The exact `IndexFlatIP` implementation is appropriate for a pilot. Implement
and validate a scalable IVF index before a multi-million-template production
bank; do not silently change retrieval semantics.

Document search uses the pinned BGE-M3-derived encoder, one global embedding,
five Gaussian-pooled local embeddings, and a provisional cosine threshold of
`0.865`. The library API is currently available as
`dfm_fineinstructions.retrieval.DFMTemplateRetriever`; a resumable document
retrieval CLI remains pending.

## Instantiation and grounding

For each admitted document, retrieve six diverse compatible templates across
global/local coverage. Send the pinned instantiator this exact JSON-shaped user
content:

```json
{
  "instruction_template": "...",
  "document": "..."
}
```

The instantiator may return `null` for incompatibility; preserve that behavior
instead of forcing an example. Expand every `<excerpt>prefix<...>suffix</excerpt>`
marker only when it identifies exactly one source span. Reject ambiguous or
unresolved markers. Require at least 80% excerpt-derived answer content unless
a later documented ablation changes the contract.

Resumable multi-GPU instantiation is pending. It must record both template and
document IDs and must not lose row-level progress when a server or client is
restarted.

## Audit and final admission

The paper retained Flow-Judge scores >=4. DFM11 begins with the calibrated
equivalent of score 5, but an upstream score alone is insufficient. Final rows
must pass:

1. instruction/answer coherence and document grounding;
2. unambiguous excerpt and copied-span accounting;
3. PII, credentials, and contextual personal-data checks;
4. protected-evaluation decontamination at query, template, and pair levels;
5. exact and semantic deduplication against DFM11 and Magpie rows;
6. language and source/category balance checks;
7. task-aware math, code, tool, exact-format, and factual validators;
8. active Gemma-template rendering and context-length validation.

For token-controlled instruction pretraining, the generated pair-token budget
per source document must not exceed that document's token count. The paper
retrieved six candidates and retained approximately three pairs per document on
average under this rule.

Only after these gates pass should final `messages` rows be tokenized, assigned
a DFM11 prefix, capped/repeated, and included in sampling. Set the final token
weight from a bilingual source-stratified pilot and capability ablation, not
from the withdrawn upstream-corpus 3B proposal.

## Current checklist

| Stage | State |
|---|---|
| Submodule and package | Implemented locally at `a4442c2`; remote push pending |
| Strict source schema | Implemented |
| Canonical extraction | Implemented and unit-tested |
| Artifact pins and model I/O contracts | Implemented |
| Gaussian retrieval and pilot index | Implemented and unit-tested at the contract level |
| Reviewed DFM11 source manifest | Pending finalized DFM source-policy mapping |
| Multi-GPU templatization | Pending |
| Production deduplication/reweight calibration | Pending |
| Scalable retrieval campaign | Pending |
| Multi-GPU instantiation | Pending |
| Independent audit and task validators | Pending |
| Gemma rendering, tokenization, sampling | Pending |

Do not launch a large generation campaign until every preceding pending stage
has a receipt and the model-artifact use decision is recorded.
