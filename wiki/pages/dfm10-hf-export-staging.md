---
type: Runbook
title: DFM10 Hugging Face Export Staging
description: Reproducible local packaging and validation of DFM10 additions and repaired replacements without uploading them.
tags: [dfm10, datasets, hugging-face, export, repair]
status: stable
last_updated: 2026-08-30
confidence: high
---
# DFM10 Hugging Face Export Staging

## Production result

On 2026-08-29, `scripts/prepare_dfm10_hf_exports.py` initially materialized 25
local dataset repositories under `exports_dfm10/`. The subsequent OpenStax
production completion added `dfm10-openstax-mimir-sft`, bringing that published
staging set to 26 packages and 69,414,759 rows. Later the same day, three new
local packages expanded the current root manifest to 29 packages:
`dfm10-danish-framenet-sft`, `dfm10-danish-lexical-sentiment-sft`, and
`dfm10-tidsskrift-open-article-summaries`.

On 2026-08-30, the root inventory gained explicit non-materialized
`work_in_progress` records for the five active Mimir benchmark augmentation
programs:

- `dfm10-mimir-ifeval-verifier-sft`;
- `dfm10-mimir-answer-contract-calibration`;
- `dfm10-mimir-event-coreference-sft`;
- `dfm10-mimir-drop-reasoning-sft`;
- `dfm10-mimir-boolq-entailment-sft`.

These records have zero rows and shards, target row ranges, and
`materialized: false`. They reserve stable export identities and document the
production queue, but they are not empty Hugging Face packages and are not
ready for upload. `scripts/prepare_dfm10_hf_exports.py --refresh-inventory`
recreates the registrations. The generated inventory currently distinguishes
registered packages from materialized packages with separate counters; planned
zero-row records do not inflate materialized-package or row totals.

### Open Chats completion, 2026-08-30

The Danish Wikipedia and OpenStax grounded-chat campaign completed all 384
generation/audit shards with zero failed shards. Final materialization retained
49,787 Danish Wikipedia chats and 158,605 OpenStax chats. The OpenStax corpus
contains 847,838 supervised assistant turns and 245,295,063 rendered full-chat
tokens; canonical per-assistant-turn tokenization produced 847,838 examples
with zero skips. Both Hugging Face packages pass complete row recreation, and
`dfm10-openstax-open-chats` is now `ready_for_upload` rather than work in
progress. The canonical DFM10 tokenized tree includes both sources.

The union builder resolves tokenizer and chat-template paths before comparing
metadata. This accepts absolute and repository-relative spellings of the same
files while still rejecting genuinely different tokenizer/template metadata.

Every direct child package follows the established `sapient-synth-*` and
`transformations-*` repository shape:

- `README.md` with Hugging Face dataset-card frontmatter;
- `LICENSE.md` with an explicit upstream-license review boundary;
- `data/train-*.jsonl.gz` with chat `messages`, optional `condition` and
  `tools`, and row-level provenance;
- `metadata/manifest.json` with source, row, shard, byte, and checksum data;
- `metadata/validation.json` from a complete post-build row scan;
- `recreate_dataset.py` for standalone package validation.

The build preserves native multi-turn and tool-call messages. Flat
`instruction`/`response` and `prompt`/`target` sources are normalized to one
user and one assistant message. Files are deterministic gzip streams and
contain no symlinks. The preparation command itself performs no upload.

## Published packages

### MedQuAD English and Danish, 2026-08-31

The independently audited MedQuAD production corpus is published as two
separately selectable CC BY 4.0 packages. Each contains 12,472 rows, preserves
row-level source URLs, MedQuAD attribution, identifiers, medical metadata, and
audit decisions, and passed full local recreation plus remote file-set
verification. The English repository revision is
`96a12f8cebeb954abcadfe0c6c574aba1e029309`; the Danish translated-adaptation
revision is `8f044a6d7c7f05ed26f2cafc115d9ad37d1a75d8`.

### Doms and Danish lexical completion, 2026-08-30

Three additional packages completed validation, publication, and remote
file-set verification:

| Package | Rows | Remote revision |
| --- | ---: | --- |
| `dfm10-domsdatabasen-grounded-chats` | 4,438 | `3150dfcfef013bac0efc23a60d9ae5dcfbe383e4` |
| `dfm10-danish-framenet-sft` | 37,135 | `ae3d62c1f05963d6b20b198754e2e37528150197` |
| `dfm10-danish-lexical-sentiment-sft` | 13,698 | `b7b7c4f0fecaf3c4e4b611d5f4cf1fb443899ad4` |

The lexical packages include their generated, independently audited natural
Danish interactions in addition to deterministic gold mappings. Their earlier
4,231- and 1,751-row local-only descriptions are **superseded**. The canonical
inventory now reports 61 materialized packages: 61 uploaded, zero ready for
upload, and six non-materialized work-in-progress registrations.

The first publication occurred before the resumable lexical stage filled its
last incomplete model records. The final package refresh added 16 FrameNet and
643 sentiment rows, so both repositories were republished at the revisions
shown above. A subsequent exact comparison of local and remote package
manifests found one more stale deterministic rebuild,
`dfm10-danish-wikipedia-open-chats`; its unchanged 49,787 rows were republished
at revision `2bc1cdddb90e7b84141594ce86211419e6a6d43a`. After these corrections,
all 61 uploaded package manifests match their local row counts, source bytes,
source-file inventories, data-shard sizes, and data-shard SHA-256 values. The
audit receipt is `logs/dfm10_ready_upload/remote_manifest_parity.json`.

**Persona completion:** explicit approval of the 1,852 accepted seven-turn
rows unblocked finalization. `dfm10-danish-persona-chats` now contains 22,284
audited chats and is published at revision
`ed6f54ad347a6e2d0ced84abafaa5d46bae83198`. The live inventory consequently
contains 69 registered package identities, 64 materialized packages, 62
uploaded packages, zero ready-for-upload packages, and seven WIP registrations.
Two WIP packages are materialized Tidsskrift outputs; five are non-materialized
Mimir plans. Published-package manifest parity is 62/62.

**Tidsskrift completion:** the grounded campaign passed its production gates
with 132,444 audited SFT rows and 23,213 audited chats (117,910 supervised
assistant turns). Both tokenized with zero skips, passed complete package
recreation, and were integrated into the canonical union. They are published
as `schneiderkamplab/dfm10-tidsskrift-open-sft` at revision
`65c1f79513e6b75bca40fb44cc5104b411066359` and
`schneiderkamplab/dfm10-tidsskrift-open-chats` at revision
`970eb53781406634121d2f00deab6ea77fde49ba`. The inventory now has 64
materialized and uploaded packages, zero ready packages, and five
non-materialized Mimir WIP registrations; remote manifest parity is 64/64.

The answer-contract campaign subsequently completed its 1,600-row stratified
E4B audit with 1,596 usable rows and no judge errors. Its deterministic 150,000
candidates remain non-materialized pending an explicit admission decision,
full validation, tokenization, and packaging.

### Ready-package publication, 2026-08-30

The owner approved publication of every package then marked
`ready_for_upload`. The resumable campaign uploaded and remotely verified all
24 packages (122,249,521,523 local bytes), including 13 policy-filtered Sapient
provenance partitions and 11 direct-source packages. Verification compared the
complete expected local file set for each package with its corresponding
`schneiderkamplab/<package>` repository and recorded the remote commit SHA in
`logs/dfm10_ready_upload/verified.jsonl`; all 24 passed. The canonical
`UPLOADED_PACKAGES` inventory now includes these repositories, so metadata
refreshes retain their `uploaded` status.

The first attempt exposed an invalid Hugging Face language value, `mixed`, in
the AI Arena card. It was stopped before verification, corrected to the
supported `multilingual` value in both the export specification and generated
card, and all 24 ready package cards were validated before the successful
restart. Use `scripts/upload_ready_dfm10_packages.sh` for an idempotent resume;
it skips only packages with a completed remote-verification receipt.

Later on 2026-08-30, the owner lifted the remaining publication hold on five
fully validated and audited materialized packages:
`dfm10-bornholmsk-parallel`, `dfm10-cor-sem-sft`,
`dfm10-danish-book-ads-sft`, `dfm10-diem-historical-modernization`, and
`dfm10-sks-tei-sft`. All five were uploaded and passed complete remote file-set
verification. Their receipts and remote commit SHAs are appended to
`logs/dfm10_ready_upload/verified.jsonl`. Bornholmsk card metadata was corrected
before publication to use ISO language `da`; dialect identity remains in its
description and row provenance.

### Remaining-work priority, 2026-08-30

The remaining model-backed WIP is ordered by finishable workload rather than
the older launch chronology. `scripts/run_dfm10_small_work_priority_queue.sh`
waits for the active Tidsskrift campaign without consuming GPUs, then runs:

1. the 29,500-request Doms/persona campaign, whose atomic queue sorts all 4,500
   Doms shards before the 25,000 persona requests;
2. the 47,854-prompt Danish lexical generation/audit campaign;
3. the 150,000-row Mimir answer-contract audit.

Each stage receives three wrapper-level attempts. Exhausting one stage is
recorded but does not prevent later stages from running. The former standalone
answer-contract waiter was stopped before launching this serialized queue. Its
current log root is `logs/dfm10_small_work_priority_20260830/`.

The initial Andersen-only publication state is **superseded as of 2026-08-29**.
All 26 staged packages are now public under the
[`schneiderkamplab/dfm10-*`](https://huggingface.co/datasets/schneiderkamplab)
namespace, including
[`dfm10-openstax-mimir-sft`](https://huggingface.co/datasets/schneiderkamplab/dfm10-openstax-mimir-sft),
[`dfm10-andersen-modernization`](https://huggingface.co/datasets/schneiderkamplab/dfm10-andersen-modernization),
and all four `dfm10-folketingets-dokumenter-*` families. The Andersen package
contains the 1,068-row training split only; its 119-row zero-shot evaluation
split remains excluded.

The upload used Hugging Face's resumable large-folder API with eight workers.
A post-upload API audit compared every remote repository against its local
manifest: all expected cards, license notices, validators, manifests,
validation receipts, and data shards are present. The audit covered 69,414,759
rows and 27,163,247,201 compressed data bytes with no missing files, size
mismatches, or LFS SHA-256 mismatches.

### Local-only additions

An exact Hugging Face API comparison on 2026-08-29 found 29 packages in the
current local root manifest and 26 `schneiderkamplab/dfm10-*` dataset
repositories. The following three packages have not been uploaded:

| Package | Rows | Compressed bytes | Upstream |
| --- | ---: | ---: | --- |
| `dfm10-danish-framenet-sft` | 4,231 | 776,659 | `dsldk/dansk-frame-net` |
| `dfm10-danish-lexical-sentiment-sft` | 1,751 | 202,717 | `dsldk/danish-sentiment-lexicon` |
| `dfm10-tidsskrift-open-article-summaries` | 9 | 31,021 | `tidsskrift.dk` OAI-PMH metadata and PDFs |

The two lexical packages are pending an additive refresh. Their export specs
include both the existing eight-label rows and separately generated,
independently audited natural Danish interactions. Do not publish stale local
package counts while this refresh is running. The root
`exports_dfm10/manifest.json` marks both packages explicitly as
`work_in_progress`, with a reason, and repeats them in its top-level
`work_in_progress` inventory. The export generator owns these fields so future
partial or complete rebuilds preserve the marker.

Each package's standalone `recreate_dataset.py` validator passes. Unlike the
published 26-package set, these additions currently lack
`metadata/validation.json`; generate and retain the normal validation receipt
before upload. The remote namespace contains no additional `dfm10-*` package
that is absent from the local manifest.

**Publication hold (2026-08-29):** do not upload
`dfm10-tidsskrift-open-article-summaries` yet. Keep the package local until the
hold is explicitly lifted, even though its validator and row-level open-license
checks pass. This hold does not apply to the two Danish lexical packages.

**Current filesystem correction (2026-08-30):** the three-directory inventory
above is superseded. `dfm10-tidsskrift-open-article-summaries` remains in the
root manifest, but its package directory is no longer present. It is therefore
a stale manifest entry, not a currently uploadable local package. The only
package directories absent from the live Hugging Face namespace are
`dfm10-danish-framenet-sft` (4,231 rows) and
`dfm10-danish-lexical-sentiment-sft` (1,751 rows). Both standalone validators
pass, neither has been uploaded, and both still lack
`metadata/validation.json`. Reconcile the root manifest before treating its
package count as the current publication inventory.

**Superseded later on 2026-08-30:** a subsequent inventory refresh removed the
stale Tidsskrift manifest entry and added the completed
`dfm10-mimir-grounded-expanded-sft` directory and manifest entry. The current
29-package inventory has three local-only packages: Mimir is
`ready_for_upload`, while FrameNet and lexical sentiment are
`work_in_progress`. The other 26 are marked `uploaded`.

### Status-field semantics

The root manifest currently marks exactly two packages with
`status: work_in_progress`: `dfm10-danish-framenet-sft` and
`dfm10-danish-lexical-sentiment-sft`. The root `work_in_progress` array repeats
the same two names and the same pending additive-generation/audit reason. The
other 27 manifest entries have no `status` field; they are unmarked, not
explicitly `ready` or `complete`. Package README frontmatter contains no status
field and applies the generic `repaired` tag to every package, including the
two WIP packages. The root README's statement that every direct child is
upload-ready therefore conflicts with the explicit WIP state and must not be
used as the completion authority.

**Superseded 2026-08-30:** the export builder and refreshed root inventory now
assign an explicit status to every package. The 26 repositories verified in
the live `schneiderkamplab` namespace are `uploaded`; the validated local-only
`dfm10-mimir-grounded-expanded-sft` package is `ready_for_upload`; and the two
Danish lexical packages remain `work_in_progress`. The root README reports the
same 26/1/2 split. Package-card `repaired` tags remain descriptive rather than
publication state.

**Expanded Mimir package, 2026-08-30:** the finalized evaluation-gap
augmentation is staged locally as `dfm10-mimir-grounded-expanded-sft`. It
contains 732,763 English chat rows in three deterministic gzip shards
(371,168,350 compressed bytes; 1,507,586,751 source bytes). The standalone
full-row validator reports `{"rows": 732763, "valid": true}` in
`metadata/validation.json`, all shard checksums are recorded in the package
manifest, and the root manifest contains an identical package entry. The
package retains upstream dataset, document, URL, date, license, generation,
and independent-audit evidence under row-level metadata. Its mixed-source
license remains `other`; publication requires preserving and applying each
row's upstream terms. It has not been uploaded.

**Superseded later on 2026-08-30:** the expanded Mimir package was uploaded to
`schneiderkamplab/dfm10-mimir-grounded-expanded-sft`. Remote revision
`0aa47052e1436ce6ded1e63b86335fae521cc773` contains all eight expected package
files. File sizes and the LFS SHA-256 object IDs of all three data shards match
the local package manifest. The refreshed root inventory therefore records 27
uploaded packages, zero ready-for-upload packages, and the same two
work-in-progress Danish lexical packages.

The root inventory now also records `dfm10_sampling_repeat` explicitly for
every package. The ten intentionally amplified packages use the values in
`data_io/prefix_config_dfm10.yaml`; every other package records the conservative
one-pass default. These are DFM10 mixture weights, not recommendations imposed
on users of the standalone Hugging Face datasets.

**Grounded-chat WIP registration, 2026-08-30:** the root manifest records the
three active conceptual dataset efforts as four package-level WIP entries:
`dfm10-danish-wikipedia-open-chats`, `dfm10-openstax-open-chats`,
`dfm10-tidsskrift-open-sft`, and `dfm10-tidsskrift-open-chats`. Tidsskrift SFT
and chats are separate Hugging Face release units despite sharing one source
campaign. No empty package directory is created; each becomes upload-ready only
after generation, independent audit, hard size gates, and packaging succeed.
Refresh root-only registrations without touching package data using:

```bash
python scripts/prepare_dfm10_hf_exports.py --refresh-inventory
```

## Rebuild

```bash
cd /work/dfm/HRM-Text
nice -n 10 ionice -c2 -n7 \
  /home/ucloud/miniforge3/envs/hrm/bin/python \
  scripts/prepare_dfm10_hf_exports.py \
  --workers 64 \
  --force
```

`--workers` uses independent processes. There are currently 29 package jobs,
so values above 29 do not increase active package-level concurrency. A partial rebuild
can repeat `--dataset <package-name>` and omits `--force` to reuse completed
packages. The builder writes each package to a temporary sibling and renames
it only after all shards, checksums, metadata, and cards are complete.

The root `exports_dfm10/manifest.json` is the authoritative package inventory.
`exports_dfm10/inherited_hf_audit.json` records the inherited-source check.

## ArXiv summary package

On 2026-08-30 the inherited `dfm4_arxiv_paper_summarization` task was
materialized as `dfm10-arxiv-paper-summarization-sft`. The package contains one
gzip JSONL shard with 213,354 rows and 217,828,007 compressed bytes. A complete
post-build scan passed, and an independent canonical hash comparison confirmed
that every condition, instruction, and response is byte-equivalent to the
eight converted training Parquets.

The preparatory join reads the eight matching Common Pile raw shards and adds
arXiv ID, URL, authors, date, per-record licence, source shard/row, and pinned
Hub revision. All 213,354 IDs matched uniquely. The retained licence counts are
189,714 CC BY 4.0, 3,668 CC BY 3.0, 10,364 CC BY-SA 4.0, 8,292 CC0, and 1,316
public-domain rows.

**Superseded 2026-08-30:** the package is no longer merely
`ready_for_upload`. It was uploaded publicly as
`schneiderkamplab/dfm10-arxiv-paper-summarization-sft` at Hub commit
`f8b5b81d54e2ace242916b8f1dbd7dcc5248cb09`. Post-upload inspection found the
expected six package files plus `.gitattributes`; the remote compressed shard
is exactly 217,828,007 bytes.

Rebuild only this package with:

```bash
python scripts/prepare_dfm10_arxiv_summarization_export_source.py --workers 4 --force
python scripts/prepare_dfm10_hf_exports.py \
  --dataset dfm10-arxiv-paper-summarization-sft --workers 1 --force
python exports_dfm10/dfm10-arxiv-paper-summarization-sft/recreate_dataset.py
```

## Exact-artifact materialization backlog

Materialize a source when reproducing the trained representation requires
filter decisions, generation/audit outputs, joins, branch expansion, or
structured tool parsing. Routine deterministic field-to-chat mapping from a
pinned Hub revision does not justify another repository by itself.

| Priority | Proposed exact artifact | Why the upstream repository is insufficient | Publication state |
| --- | --- | --- | --- |
| 1 | `dfm10-{glaive,toolace,xlam}-native-tool-use` | Custom parsers normalize schemas and names, recover structured calls, assign call IDs, and reject malformed trajectories; the DFM7 audit validates the converted forms, not the raw repositories. | Not materialized as standalone packages. |
| 1 | `dfm10-natural-instructions-filtered-sft` | The DFM9 build excludes 96 PII-sensitive task files and constructs prompts from task definitions and inputs. | Not materialized. Preserve task identity and the exclusion manifest. |
| 1 | `dfm10-ai-arena-udtraek-sft` | Each arena pair is split into two independently supervised conversation branches while preserving system prompts, model names, and conversation IDs. | Not materialized. |
| 1 | `dfm10-croco-munin-chosen-sft` | The preference corpus is converted to SFT using only the chosen user/assistant trajectory. | Not materialized. |
| 1 | `dfm10-numinamath-valid-sft` | Only rows whose problem and solution validity flags both equal `Yes` are retained and assigned the chain-of-thought contract. | Not materialized. |
| 1 | `dfm10-nemotron-terminal-sft` | Native role-preserving conversations require source-relative materialization because repeated upstream basenames previously collided. Assistant-prefix expansion belongs exclusively to the tokenizer. | Native source materialized: 366,154 conversations, 3,101,906 assistant turns, 29 files, zero skipped rows. Tokenization and upload-package staging are in progress. |
| 1 | `dfm10-danish-{framenet,lexical-sentiment}-sft` | Public GitHub lexical resources are converted into gold supervision and await additive generated natural questions plus independent audit. | Existing package directories remain `work_in_progress`. |
| 1 | `dfm10-tidsskrift-open-{sft,chats}` | OAI/PDF acquisition, row-level licence gating, extraction, generation, and independent grounding audit cannot be reproduced from one ready-made Hub dataset. | Registered work in progress; final packages are not materialized. |
| 2 | DFM10-safe Sapient source packages, partitioned by provenance family | The active corpus is a policy-selected subset of the large Sapient mirror, with thousands of file-level allow/deny decisions and format conversions. A single monolithic release would obscure mixed licences and be very large. | Materialize locally by provenance/licence family; upload only after per-family release review. |

Agreement-backed LexDK and DBC should remain exact internal artifacts rather
than public Hugging Face packages. Existing repaired DFM10 sources, Folketing
transformations, Andersen, OPUS, DynaWord/Common-Pile transformations,
OpenStax/Mimir, Danish Wikipedia chats, and DFM8 synthetic families are already
materialized in published `schneiderkamplab` repositories and are not part of
this backlog.

### Native Terminal Corpus replacement

Decision, 2026-08-30: DFM10 must contain no flattened prior chat turns. The
legacy `nemotron_terminal_corpus__*` tasks inherited from DFM9 are therefore
excluded by `scripts/build_tokenized_dfm10_tree.py`. Their replacement is
`nemotron_terminal_corpus_native__*`, built from all 29 selected upstream
Parquets with native `messages` roles and source-relative paths. One stored row
is one original conversation; `scripts/tokenize_chat_template.py` creates one
training example per assistant turn. A regression test verifies that preceding
assistant turns remain assistant messages in later prompts.

The ordinary DFM10 context remains 4,096 tokens. Terminal tokenization uses
`--max-seq-len 4096`: for each assistant target it retains the largest fitting
suffix beginning at a complete user-message boundary, pins an initial system
message, and never clips the target. Terminal traces also pin the first user
task before the newest terminal-output suffix. For one-request tool traces, it
retains the request plus the newest complete call/result suffix. Targets
that still cannot fit are deferred to the later 8K/16K/32K stages documented in
the [long-context dataset inventory](/pages/long-context-dataset-inventory.md).
The same native 4K policy applies to DeepDive and repaired DOLCI trajectories.
DFM10 sampling additionally uses `default_long_context=drop`, preventing
silent response truncation in inherited single-turn or not-yet-retokenized
sources.

Sapient provenance packages fail closed on malformed structures but skip and
count source rows with empty instructions or empty targets. Manifests record
`source_rows`, `skipped_rows`, and `skip_reasons`; this was required by an empty
`tasksource/conll2000.parquet` target at source row 6,228.

The old sampled DFM10 corpus at 101,731,426,509 tokens per epoch predates this
replacement and is stale until the native tokenized union is resampled.

### Native replacement export versions (2026-08-30)

The root `exports_dfm10/manifest.json` records stable artifact versions,
intended Hub IDs, training-rendering versions, and superseded task prefixes for
the native replacement set:

| Package | Artifact version | Upload state | DFM10 training replacement |
| --- | --- | --- | --- |
| `dfm10-deepdive-gemma4-tool-use` | `2026-08-29-native-source-v1` | Source package already uploaded; the 4K renderer changed without destructively rewriting the package | New native DeepDive addition; one target per assistant turn |
| `dfm10-dolci-tool-use-repaired` | `2026-08-29-native-source-v1` | Source package already uploaded; package metadata records the new `2026-08-30-complete-message-4k-v2` rendering | Replaces `dolci_instruct_sft_tool_use__`, `dolci_instruct_sft_tool_use_sa__`, and `dolci_native_tool_use__` |
| `dfm10-nemotron-terminal-sft` | `2026-08-30-native-v1` | New package, recorded as `ready_for_upload` after materialization | Replaces `nemotron_terminal_corpus__` |
| `dfm10-sapient-*-filtered-sft` | `2026-08-30-policy-filtered-v1` | New per-provenance packages; materialized packages become `ready_for_upload`, unfinished packages remain visible as WIP | Exact policy-selected Sapient partitions; not one monolithic mixed release |

The exported DeepDive, DOLCI, and Terminal packages retain complete native
conversations so they can be re-rendered for later 8K/16K/32K stages. The 4K
window belongs to DFM10 tokenization and is recorded under
`training_rendering`; it is not baked destructively into the upload rows.

`scripts/build_tokenized_dfm10_tree.py` is the integration authority. It
excludes all four superseded base prefixes before linking replacements and
fails if any such task leaks into the completed union. The sampler config also
assigns the legacy prefixes a zero cap as a second fail-closed guard. Do not
resample DFM10 until the native Terminal and repaired DOLCI tokenizers have
completed and the union has been rebuilt. Tokenizer readiness is represented
by an atomically renamed `completion.json`; the early-written
`tokenizer_info.json` and `processing_info.json` files are not completion
signals. `scripts/finalize_dfm10_when_ready.sh` gates on all three native
replacement receipts.

## Inherited source availability

Exact Hugging Face API lookups on 2026-08-29 resolved all 159 dataset IDs in
the exhaustive DFM8 inventory and all nine explicit DFM9 additions. Thus all
168 inherited Hugging Face source repositories remain available. Locally
created DFM8 derivatives such as `sapient-synth-*`, `transformations-*`, the
DFM8 synthetic families, and the repaired English/Danish OpenHermes datasets
are included in those resolved IDs.

Two inherited corpora are deliberately not on Hugging Face: Lex.dk and DBC.
Both are supplied through Danish Foundation Model agreements. The new repaired
DBC corpus is likewise excluded from `exports_dfm10/`; do not infer public
redistribution permission from its use in DFM10.

### Full lineage availability audit, 2026-08-30

An authenticated exact-ID Hub audit reconciled the exhaustive predecessor
inventory, the live DFM10 tokenized union, every published DFM10 artifact, the
additional DFM10 upstream repositories, and the six Common Pile repositories
used by expanded Mimir. All 207 distinct Hugging Face dataset repositories
resolved: 159 DFM8 repositories, nine DFM9 additions, 28 exact published DFM10
artifacts, 23 DFM10 Hub upstreams, and six Mimir Common Pile upstreams, with
overlap removed in the 207 total. Eight repositories are gated but accessible
with the project token; none is private. The machine-readable result is
`logs/data_audits/dfm10_hf_remote_availability_20260830/report.json`.

This does **not** yet satisfy the stronger requirement that every exact active
non-agreement training artifact be independently downloadable from Hugging
Face. Three current DFM10 artifacts remain absent:

- `dfm10-danish-framenet-sft`; its original source is the public GitHub
  repository `dsldk/dansk-frame-net`, while the converted package remains work
  in progress;
- `dfm10-danish-lexical-sentiment-sft`; its original source is the public
  GitHub repository `dsldk/danish-sentiment-lexicon`, while the converted
  package remains work in progress;
- `dfm10-tidsskrift-open-sft`; the current union contains the nine-row gold
  Tidsskrift source, but the complete generated/audited package remains work in
  progress and no exact package is on the Hub.

The original Andersen corpus is a public GitHub repository rather than a
Hugging Face dataset, but its exact converted training artifact is published as
`schneiderkamplab/dfm10-andersen-modernization`. The same artifact-level
coverage exists for the non-Hub Folketing, immutable OpenStax, and OpenLogic
sources through their published DFM10 packages. Therefore LexDK and DBC are the
only intentional agreement exceptions, but the three work-in-progress
artifacts above are current remote-rebuild gaps that must be closed before
claiming complete Hub reproducibility.

## Resolved provenance and licensing

- `dfm10-openstax-mimir-sft` contains 50,000 accepted rows grounded in 61
  immutable official OpenStax books. Gemma 4 31B generated five task families
  from grounded passages, and every retained row scored at least 4/5 on every
  independent audit dimension. It retains row-level title, URL, revision, and
  attribution metadata and is staged as CC BY 4.0.
- `dfm10-mimir-grounded-expanded-sft` contains 732,763 accepted rows across
  Technical/STEM, professional domains, compositional reasoning, grounded
  factual QA, and MCQ answer-contract calibration. Gemma 4 31B generated and
  independently audited the rows; exact benchmark decontamination found no
  matches. The source mix is license-heterogeneous, so row-level provenance
  and licensing remain authoritative.
- Andersen modernization comes from
  `ogierMontanus/hcandersenDk_data_2024`, an extract of the `hcandersen.dk`
  TEI/XML corpus. Local extraction pairs each historical Danish work with its
  `_modern.xml` edition and creates paragraph-aligned modernization chats. The
  upstream corpus declares GNU AGPLv3 and requires preservation of the
  work-level scholarly credits in TEI headers.
- Folketing task families derive from Rigsarkivet handover 14004. The official
  catalog publishes the source under CC BY 4.0, naming Folketinget as creator
  and Rigsarkivet as publisher.

## Scope decisions

The staging set includes active local DFM10 additions and repaired production
replacements. It excludes:

- the original Alexandra Nordjylland conversion, which is disabled in favor
  of the grounded repaired package;
- Alexandra DaCoref, which final source reconciliation disables;
- agreement-backed DBC and Lex.dk data.

The initial exclusion of OpenStax because it was absent from the final union
manifest is **superseded as of 2026-08-29**: its accepted 50,000-row production
corpus and 16-shard source tree subsequently completed. Packages with a single
verified license now declare it directly (`cc-by-4.0` for OpenStax and
Folketing; `agpl-3.0` for Andersen). Mixed or unresolved packages retain
`license: other`; packaging does not grant a new license over upstream
material.

## Verification

### Mimir answer-contract publication, 2026-08-30

The 150,000-row `dfm10-mimir-answer-contract-calibration` package passed full
local schema validation and was published to
`schneiderkamplab/dfm10-mimir-answer-contract-calibration`. Exact local file-set
verification succeeded at remote revision
`4ed7c561de4f3ca5cf4b87401f4f720c24c81007` (six expected files, all present).
It is tokenized with zero skipped rows, integrated in the canonical DFM10 union
at repeat one, and changes the union task count from 15,734 to 15,737 together
with other concurrently finalized sources.

The published production build completed a full decompression and schema scan
of every row. After the OpenStax addition it verifies 69,414,759 rows across 26
packages, manifest equality, shard counts, 168 inherited Hub repositories, and
zero symlinks. The later three local-only additions pass their standalone
validators but are not yet part of that remote verification receipt. Validate
an individual package with:

```bash
python exports_dfm10/<package-name>/recreate_dataset.py
```

This staging record complements the
[DFM10 production replacement inventory](/pages/dfm10-repaired-datasets.md)
and [final source reconciliation](/pages/dfm10-final-source-reconciliation.md).
