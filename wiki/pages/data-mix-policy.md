# Data Mix Policy

Last updated: 2026-06-17
Confidence: high  
Scope: Dataset inclusion policy for academic/non-commercial HRM-Text training.

## Hugging Face Export Uploads

Added on 2026-06-17. Confidence: high from successful uploader exit and
`huggingface_hub` repository inspection.

The local `export-upload/` tree currently maps one-to-one to 82 public Hugging
Face dataset repositories under `schneiderkamplab`:

- 12 previously uploaded post-training datasets were updated in place:
  Common Pile denoising/reordering/prefix/span tasks, Danish DynaWord
  denoising/reordering/prefix/span tasks, and the four
  `transformations-*` datasets.
- 70 new Sapient-exclusion synthetic replacement datasets were uploaded as
  `sapient-synth-*` repositories.

All 82 repositories were verified via the Hub API with `repo_type="dataset"`;
each returned `private=False`. The upload was run from `/work/dfm/HRM-Text`
with:

```bash
python scripts/upload_export_upload_to_hf.py \
  --org schneiderkamplab \
  --root export-upload \
  --log logs/hf_export_upload_all_82_20260617.log
```

Do not store the Hugging Face token in repo files or wiki pages.

## Expansion Policy for Common Pile and Danish DynaWord Exports

Added on 2026-06-18. Confidence: high for the policy decision and local export
layout; medium for source availability until the source Parquet mirrors are
reconfirmed or re-downloaded.

The eight existing `common-pile-*` and `danish-dynaword-*` Hugging Face
datasets should be expanded in place, not published as `v2`, `diverse`, or
renamed variants. These datasets have not yet been consumed externally, so the
published repos can be updated freely.

Expansion rules:

- keep the current uploaded rows as accepted seed rows;
- sample additional source rows from other available files/components in
  `common-pile` and `danish-foundation-models/danish-dynaword`;
- use source-balanced and length-balanced sampling instead of a prefix scan;
- generate the same four task families: denoising, span filling, prefix
  continuation, and paragraph reordering;
- judge the new candidate rows with the same audit workflow;
- concatenate only accepted new rows with the existing accepted upload rows;
- update the same HF dataset repos and README/audit summaries in place.

Local note: `export-upload/` contains the compact uploaded rows, while
`export/` still contains larger generated data and audit artifacts. The compact
chat rows contain only `messages`, so future expansion should track source
provenance in aggregate metadata/audit summaries and should preserve the
existing accepted rows byte-for-byte unless there is an explicit cleanup
decision.

Preparation update, 2026-06-18. Confidence: high from local script execution
and Parquet metadata inventory. The expansion prep script is:

```bash
cd /work/dfm/HRM-Text
python scripts/prepare_common_dynaword_expansion.py
```

It writes a timestamped runbook under:

```text
logs/data_audits/common_dynaword_expansion/<timestamp>/
```

The 2026-06-18 runbook at
`logs/data_audits/common_dynaword_expansion/20260618T103912/` found 477
Common Pile source Parquet files across 12 source families and 45 DynaWord
source Parquet files across 45 source families. It also wrote
`target_tokens_by_dataset.json`, which raises the expansion audit targets to
200M estimated tokens for denoising/span/prefix tasks and 100M for paragraph
reordering tasks.

`scripts/rebalance_export_audits.py` now accepts
`--target-tokens-by-dataset <json>` so expansion audits can continue beyond the
old 100M/50M completion thresholds. `scripts/prepare_export_upload_from_export.py`
copies selected rebuilt `export/` folders into `export-upload/` as physical
copies, not links, before in-place HF upload.

## Export-Upload Transformation Datasets

Added on 2026-06-17. Confidence: high from local file inspection, JSONL row
counts, and exact matching against generation metadata.

The four synthetic transformation datasets have been prepared as standalone
HF-uploadable folders under `export-upload/`:

```text
export-upload/transformations-danish-danish
export-upload/transformations-danish-english
export-upload/transformations-english-danish
export-upload/transformations-english-english
```

Each folder contains copied gzip JSONL data, `README.md`,
`audit_summary.json`, `accepted_selection_summary.json`,
`generation_config.json`, local seed files, and a self-contained
`recreate_dataset.py`. There are no symlinks in these four upload folders.

The exported rows use the standard post-training chat schema:

```json
{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
```

The rows themselves contain only `messages`. Actual task/source provenance is
therefore tracked in aggregate in `audit_summary.json["actual_contents"]`,
reconstructed by exact matching of exported chat messages against accepted
generation metadata after whitespace normalization. All exported rows matched
generation metadata and no unmatched rows were found.

Row counts:

| Dataset | Rows | Files | Accepted regeneration rows |
|---|---:|---:|---:|
| `transformations-danish-danish` | 208,117 | 250 | 0 |
| `transformations-danish-english` | 211,401 | 250 | 0 |
| `transformations-english-danish` | 246,288 | 409 | 1,260 |
| `transformations-english-english` | 248,474 | 388 | 997 |

The actual source clusters are:

| Dataset | Main actual source clusters |
|---|---|
| `transformations-danish-danish` | Danish DynaWord 146,043; Laerebogen 33,837; Danish Wiki Instruct 8,740; smaller Oliver Kinch, LexDK, and DOAB/Statistics sources |
| `transformations-danish-english` | Danish DynaWord 147,925; Laerebogen 34,378; Danish Wiki Instruct 9,132; smaller Oliver Kinch, LexDK, and DOAB/Statistics sources |
| `transformations-english-danish` | DFM4 scientific/arXiv summarization seeds 237,965; DBC 7,671; `facebook/asset` 369; LexDK 283 |
| `transformations-english-english` | DFM4 scientific/arXiv summarization seeds 238,221; DBC 9,535; `facebook/asset` 366; LexDK 352 |

The task families are the same across the four packages: exact sentence
summary, past-tense rewrite, child-friendly simplification, numbered fact
extraction, and non-copy rewrite. Per-task row counts are recorded in each
folder's `README.md` and `audit_summary.json`.

## Synthetic Replacements for DFM5-Excluded Sapient Sources

Added on 2026-06-12. Confidence: high for source identification,
initialization, and active launch; medium for final inclusion until generated
rows are inspected after the run finishes.

The 321 original Sapient source files excluded from DFM5 are not reintroduced
verbatim. Instead, the current experiment creates synthetic anonymized
replacement datasets under `synth/`, one folder per excluded source file. The
intent is to preserve broad task coverage while removing direct dependence on
the problematic original text.

Local source audit artifacts:

```text
logs/data_audits/dfm5_excluded_original_sapient_sources.tsv
logs/data_audits/dfm5_excluded_original_sapient_tasks.tsv
logs/data_audits/dfm5_excluded_original_sapient_tasks.summary.json
```

Per-row policy:

- generate a new anonymized `condition` / `instruction` / `response` row with
  Gemma 4 31B IT served by vLLM;
- judge the candidate with the same model;
- keep only rows where the judge accepts task preservation, PII replacement,
  low textual overlap, and useful training quality;
- reject rows with unchanged PII-like strings or high local 5-gram overlap.

The initialization command created all 321 per-source folders and manifests:

```bash
cd /work/dfm/HRM-Text
python scripts/synthesize_anonymized_sapient_exclusions.py --init-only
```

The 8-GPU run is managed in tmux session `sapient_anonymization_8gpu`.
Current active run after the high-priority/concurrency update:

```text
logs/sapient_anonymization_20260613T074509
```

Earlier log root `logs/sapient_anonymization_20260612T185643` records the
superseded failed launch where vLLM imported DeepGEMM and required `CUDA_HOME`.
The launcher now disables DeepGEMM for this run.

Resume correction, 2026-06-12: the initial sharded implementation appended all
workers for a source into the same `data/train.jsonl.gz`, which corrupted the
gzip stream. The corrupted early `Platypus_reclor` files were quarantined in:

```text
synth/Platypus_reclor.jsonl/corrupt_20260612T214749/
```

The active run now writes shard-specific files such as:

```text
synth/<source>/data/train.shard00000of00008.jsonl.gz
synth/<source>/rejected/rejected.shard00000of00008.jsonl.gz
```

Quality gate tightened on 2026-06-12: accepted rows require all judge booleans
to be true (`keep`, `substantially_different`, `pii_changed`,
`low_textual_overlap`, `task_preserved`, `quality_ok`) plus the local
5-gram/PII heuristic. A local audit before resuming found that all 469 already
accepted ReClor rows passed this stricter condition.

Priority narrowed on 2026-06-13: the active campaign no longer attempts all
321 excluded sources. It uses the explicit 40-file `high40` priority list:
ReClor/SciBench, QReCC dialogue QA, AESLC email summarization, iDebate opinion
abstracts, selected Niv2 summarization/NewsComm/MS MARCO/DialogRE tasks,
Tasksource sarcasm, and Tasksource ReClor. Huge WMT/translation and broad
review/sentiment/social sources are excluded from this generation campaign.
The active run uses concurrency `8` per GPU worker; vLLM logs show
`Running: 8 reqs` per GPU server.

Superseding runtime detail, 2026-06-13. Confidence: high. The active high40
campaign was restarted with `CONCURRENCY_PER_SHARD=128` and `MAX_NUM_SEQS=128`
after adding per-GPU vLLM/Triton/TorchInductor cache directories. A follow-on
`repeat30` priority set was added to
`scripts/synthesize_anonymized_sapient_exclusions.py` for 30 high-repeat-like
remaining sources: paper-review tasks 264/265/266, deceptive-opinion-spam
tasks 902/903, selected NewsComm translation tasks 1371/1373/1374/1375/1376/1377,
Rotten Tomatoes opinion abstracts, and Allegro review tasks 634/635, each in
fsopt/zsopt variants where present. The watcher command below waits for the
current high40 workers and vLLM servers on ports 8900-8907 to exit, then
launches the repeat30 run with the same 8-GPU settings:

```bash
cd /work/dfm/HRM-Text
tmux new-session -d -s sapient_anonymization_repeat30_after_high40 \
  'cd /work/dfm/HRM-Text && scripts/watch_and_run_sapient_repeat30.sh'
```

As of 2026-06-13 09:28 Europe/Berlin this watcher is active. A fresh
30-second measurement found high40 had `96,366` rows remaining and repeat30
has `77,464` rows, for `173,830` remaining rows total. At the measured
`1,836 rows/min` total throughput, the joint ETA was about `95 min`
(`1.6 h`). Confidence: high for row counts and local process state; medium for
ETA because source lengths and rejection retries vary.

Update, 2026-06-13 10:14 Europe/Berlin. Confidence: high. As high40 shards
finished on GPUs 3 and 4, those high40-owned vLLM servers were stopped and a
separate opportunistic repeat30 two-GPU run was launched in tmux session
`sapient_anonymization_repeat30_gpus34` via:

```bash
cd /work/dfm/HRM-Text
scripts/run_sapient_repeat30_opportunistic_gpus34.sh
```

This uses ports `8913` and `8914` and processes repeat30 shards `3/8` and
`4/8`. The full repeat30 watcher
`scripts/watch_and_run_sapient_repeat30.sh` was updated and restarted so it
waits for any opportunistic repeat30 workers/servers before launching the full
8-GPU repeat30 run.

Update, 2026-06-13 10:21 Europe/Berlin. Confidence: high. The coarse
all-at-once repeat30 watcher was superseded by per-GPU recovery/reuse logic.
Because the original high40 launcher owned and cleaned up its vLLM child
servers, stopping that launcher caused the remaining high40 workers/servers to
exit. The run is resumable from shard-specific accepted/rejected row IDs, so a
recovery chain was launched in tmux session
`sapient_anonymization_recover_high40_then_repeat30`:

```bash
cd /work/dfm/HRM-Text
scripts/run_high40_then_repeat30_remaining_gpus.sh
```

This starts vLLM servers on ports `8900`, `8901`, `8902`, `8905`, `8906`,
and `8907`, resumes high40 shards `0/8`, `1/8`, `2/8`, `5/8`, `6/8`,
and `7/8`, then runs the matching repeat30 shards on the same servers.
Repeat30 shards `3/8` and `4/8` continue in
`sapient_anonymization_repeat30_gpus34` on ports `8913` and `8914`.

Bug found and fixed, 2026-06-13. Confidence: high. The anonymization script's
Parquet iterator initially yielded row indices local to each PyArrow record
batch. Because the batch size is 2048, generated `source_row_id` values
repeated every 2048 rows for Parquet sources. This made resume accounting
incorrect for interrupted/restarted Parquet files: rows in later batches could
be counted as `skipped_existing` even though only an earlier batch-local row ID
was present. The code now uses a cumulative offset in
`iter_source_rows()` so future Parquet `source_row_id`s are global row indices.
Existing rows written before this fix may contain duplicate `source_row_id`
values for Parquet sources; affected missing/skipped row IDs cannot be
reliably reconstructed from those IDs alone. A diagnostic TSV was written to
`logs/data_audits/high40_missing_or_skipped_row_ids.tsv`, but it reflects the
old duplicate-ID limitation and should not be treated as exact provenance.

Clean rerun decision, 2026-06-13. Confidence: high. The current partial
repeat30 outputs were also started before the global Parquet row-index fix, so
they were not reliable for source-to-synthetic row mapping even though they had
no `skipped_existing` resume contamination. The decision is to rerun all
Parquet-based high40 sources and all repeat30 sources from scratch with the
patched script. Old outputs are quarantined, not deleted.

The clean rerun is managed by:

```bash
cd /work/dfm/HRM-Text
tmux new-session -d -s sapient_anonymization_clean_parquet_repeat30 \
  'cd /work/dfm/HRM-Text && scripts/rerun_high40_parquet_and_repeat30_clean.sh'
```

This writes task manifests:

```text
logs/data_audits/high40_parquet_sources_all.txt
logs/data_audits/repeat30_sources.txt
```

and then runs:

1. all high40 Parquet sources (`38` files);
2. validation for duplicate/missing IDs, skipped-existing counts, and 8 shard
   summaries;
3. all repeat30 sources (`30` files);
4. the same validation for repeat30.

The rerun started on 2026-06-13 at 10:56 Europe/Berlin in tmux session
`sapient_anonymization_clean_parquet_repeat30`. Initial log:
`logs/sapient_anonymization_clean_high40_parquet_repeat30_20260613T105618.log`.

High40 inclusion update, 2026-06-13. Confidence: high. The accepted rows from
the re-synthesized high40 campaign are now included in the DFM5 tokenized union
under a separate `synth_high40__` prefix. They are intentionally not linked
under original Sapient task prefixes, so sampling can cap/repeat generated
replacement data independently from original Sapient data.

The active tokenizer input tree is:

```text
data/synth_high40_sources/
```

It is built from accepted files only:

```text
synth/<source>/data/train.shard*.jsonl.gz
```

The tree builder merges the eight accepted shard files for each source into one
cleaned `train.jsonl.gz` per source, keeping only `condition`, `instruction`,
and `response`.

Superseded intermediate state. One high40 source initially had zero accepted
rows and was skipped:

```text
flan__niv2_fsopt_data__task1370_newscomm_classification.parquet
```

Inspection of that skipped source on 2026-06-13. Confidence: high. All `4,835`
rows were attempted, and each row reached the configured `3` attempts. The main
failure was the local 5-gram overlap heuristic rather than the LLM judge:
`heuristic_keep` failed on `14,468` attempts. The task is a language
classification task with a repeated option list and short multilingual snippets,
so many otherwise-valid rewrites still retained enough repeated prompt wording
or target text to exceed the overlap gate. The judge also flagged some copied
text (`1,430` attempt-level `copied_text` failures), but most judge records had
`primary_failure_type: none`. Operational failures were minor by comparison:
`11` no-JSON responses, `10` timeouts, and a few JSON parse errors.

Recovery update, 2026-06-13. Confidence: high. The overlap heuristic was fixed
to remove repeated enumerated label inventories before computing the local
5-gram overlap ratio while still recording raw overlap for audit. Existing
rejected attempts for the skipped high40 source were then reprocessed with:

```bash
cd /work/dfm/HRM-Text
python scripts/recover_synth_rejections_with_current_heuristic.py \
  flan__niv2_fsopt_data__task1370_newscomm_classification.parquet --force
```

This recovered `4,137` accepted rows and left `698` rows rejected. The high40
merged/tokenized source set now contains all `40` source files.

Commands that worked:

```bash
cd /work/dfm/HRM-Text
scripts/tokenize_synth_high40.sh
scripts/tokenize_synth_repeat30.sh
python scripts/build_tokenized_dfm5_tree.py --force
```

Resulting local counts:

```text
data/synth_high40_sources/manifest.json:
  source_count: 40
  linked_source_count: 40
  input_file_count: 320
  output_file_count: 40
  row_count: 190,464

data/tokenized_dfm5_synth_high40:
  tokenized source tasks: 40
  accepted samples: 190,464
  tokens: 63,956,698

data/synth_repeat30_sources/manifest.json:
  source_count: 30
  linked_source_count: 30
  input_file_count: 240
  output_file_count: 30
  row_count: 63,783

data/tokenized_dfm5_synth_repeat30:
  tokenized source tasks: 30
  accepted samples: 63,783
  tokens: 23,679,295

data/tokenized_dfm5/union_manifest.json:
  synth_high40_linked_tasks: 40
  synth_repeat30_linked_tasks: 30
  total_tasks: 13,360
```

Sampling policy in `data_io/prefix_config_dfm5.yaml`:

```yaml
- prefix: "synth_high40__"
  repeat: 1
- prefix: "synth_repeat30__"
  repeat: 1
```

Tokenizer bug fix discovered during this inclusion. Confidence: high. The
synthetic `.jsonl.gz` shard files can contain multiple gzip members because
some shards were appended/resumed. Python `gzip` reads these correctly, but the
Rust tokenizer previously used `flate2::read::GzDecoder`, which only read the
first gzip member. This made the first high40 tokenization produce only one
sample per shard (`312` samples total). The tokenizer now uses
`flate2::read::MultiGzDecoder`, and a smoke test on
`train.shard00000of00008.jsonl.gz` for `Platypus_reclor` produced `613`
samples instead of `1`.

## Objective

Replace or supplement Sapient's original cleaned corpus with a cleaner, more controllable mix while preserving HRM-Text's PrefixLM training format:

```text
instruction span + response span
```

This repo does not currently train on raw documents as ordinary causal-LM pretraining. Raw text must be converted to continuation rows:

```text
condition = direct
instruction = ""
response = document chunk
```

Primary evaluation goal, clarified on 2026-06-01: data-mix changes should aim
to be strong across all currently run evaluations, not just Danish evaluations.
This includes English factual/reasoning/reading-comprehension benchmarks
(`MMLU`, `Winogrande`, `ARC-C`, `BoolQ`, `DROP`, `HellaSwag`, `MATH`,
`GSM8k`), Danish dfm-evals (`danish-citizen-tests`, `dala`, `gec_dala`,
`wmt24pp-en-da`, `multi_wiki_qa`, `piqa`, `ifeval-da`,
`generative-talemaader`, summarization tasks such as `NordjyllandNews`), and
code/human-eval style tasks. Treat drops in any of these families as a
data-balance regression unless an ablation intentionally trades one family
against another.

## Continuation Data

Only Danish continuation data is currently allowed:

- Include: `danish-foundation-models/danish-dynaword`
- Exclude: Common Pile. Common Pile was removed from the downloader manifest.

Recommended continuation share: capped auxiliary slice, roughly 5-10% of total tokens if used.

## Sapient Cleaned Policy

Sapient cleaned data is included only after source filtering.

Broad exclusions:

- ReClor
- SciBench
- ScienceQA
- most FLAN
- most Tasksource

Narrow FLAN/Tasksource allow overrides are documented in [[pages/source-filtering]].

## Include / Prefer

Academic/non-commercial use permits CC-BY-NC sources, but provenance and GDPR/PII concerns still matter.

Good instruction/reasoning sources:

- Sapient non-denied cleaned sources
- `synquid/danish-verifiable-reasoning`
- `synquid/translation-100k`
- `synquid/ifbench-train`
- Oliver Kinch Danish instruction/backtranslation, QA, summarization, and translation sources with public/OPUS provenance:
  - `oliverkinch/instruct-bt` is now approved for the DFM mix after row-level
    access and schema verification on 2026-05-27.
  - Added open sources: `multi-wiki-qa-high-quality-subset`, `eur-lex-sum-instruct`, `machine-translation-da-{en,uk,ar}`, `danmarks-statistik-bt`, `tidsskrift-dk-bt`, `doab-da-bt`, `danish-university-portals-bt`, `eur-lex-bt`, `dynaword-bt`, and `dst-table-prompts-bt`.
- AllenAI Dolci SFT variants
- AllenAI Tulu SFT/persona/reasoning variants
- Nemotron instruction/SWE/terminal/agentic/multilingual, capped by objective
- DynaWord as the only raw continuation source
- Local DBC/LexDK/OPUS instruction-style additions under `data/downloads/datasets`: DBC abstracts/reviews/Faktalink/Forfatterweb, LexDK articles, and OPUS Danish-English translation shards when both language sides are present. These are converted to supervised bibliographic/article-writing/translation tasks, not empty-instruction raw continuation.

Gated sources not downloaded in the earlier `--exclude-gated` run, but intended
for the DFM mix once explicitly downloaded with an authorized token:

- `danish-foundation-models/laerebogen`
- `synquid/wiki-instruct-da`
- `oliverkinch/instruct-bt`
- `synquid/mt-da-deepseek`
- `synquid/wildchat-100k-qwen-messages`, tightly capped because it is generated
  answers to WildChat prompts.

## Oliver Kinch Source Policy

Reviewed on 2026-05-21 from Hugging Face dataset metadata, cards, and sample schemas.

Include:

- Public Danish backtranslation/instruction datasets where targets come from CC-BY, EU legal, DST, DOAB, university portal, tidsskrift.dk, or DynaWord-style public provenance.
- Public Danish QA from Wikipedia-derived `multi-wiki-qa-high-quality-subset`.
- Danish translation pairs from `machine-translation-da-en`, `machine-translation-da-uk`, and `machine-translation-da-ar`, with sampling caps because `da-en` is much larger than the other additions.

Exclude by default:

- Raw Oliver Kinch document corpora such as `danish_wikipedia`, `eur-lex`, `tidsskrift-dk`, `tidsskrift-dk-en`, `danmarks-statistik`, `danish-university-portals`, `doab-da`, and `dst-table-prompts`; the current plan allows only Danish DynaWord as raw continuation data.
- `oliverkinch/dsk-bt`; the card says it is derived from non-public internal DSK material and is not intended for public redistribution.
- `oliverkinch/da-bird`; useful as an evaluation/text-to-SQL benchmark, but its Harbor task layout and CC-BY-SA inherited BIRD tasks make it a poor fit for the current mixed training corpus.
- `oliverkinch/dynaword-no-bt`; Norwegian rather than Danish.
- Small/no-license synthetic/demo datasets (`life-in-the-uk-multiple-choice`, `synthetic-qa`, `synthetic-qa-context-qa`, `mt_da_uk`) unless separately justified.

Confidence: medium for source-card safety; high for local manifest/converter support after `py_compile` and downloader dry-run.

## Exclude / Avoid

- AllenAI WildChat was removed from the downloader manifest by decision.
- Common Pile was removed from the downloader manifest by decision.
- Raw non-Danish continuation corpora should not be used in the current plan.
- Local DBC raw/crawl/continuation files are denied by default. Only the instruction-style DBC, LexDK, and OPUS families listed above are allowlisted.

## Sampling Shape

For a 40B-token target, a reasonable target allocation remains:

- 35-45% math/reasoning/STEM
- 25-35% Danish instruction/chat/translation
- 10-20% general instruction/chat
- 5-15% code/SWE/terminal/agentic
- 0-10% Danish raw continuation

Use token-budgeted sampling rather than row-count caps alone.

## DFM Mix

Decision on 2026-05-27. Confidence: high for local schema/access checks and
manifest/config edits; medium for the exact caps until sampled analytics are
measured.

The DFM mix is the next mixed-corpus target:

- Name: `dfm`
- Sampling config: `data_io/prefix_config_dfm.yaml`
- Intended output: `data/sampled_dfm`
- Training data config: `config/data/dfm.yaml`
- Target size: about 28B tokens per epoch
- Content: safe filtered Sapient sources plus all approved additional sources,
  including gated Danish instruction sources where access is available.

`synquid/wildchat-100k-qwen` is superseded by
`synquid/wildchat-100k-qwen-messages`. The messages variant was row-accessible
with an explicit HF token on 2026-05-27 and uses a `messages` JSONL schema that
the existing converter supports. It is included only with a tight
`50,000`-row cap per file. `oliverkinch/instruct-bt` was also row-accessible on
2026-05-27 and uses a `messages` Parquet schema supported by the existing
converter.

## DFM2 Raw-Text Task Mix

Decision recorded on 2026-05-30. Confidence: high for the target policy and
verified local DFM2 sample outputs.

Superseded clarification, 2026-05-30: `X` is not the entire current DFM
direct/instruction-style corpus. In this context, `X` is the existing
approximately `2.8B` DynaWord direct/continuation-token slice per epoch. Keep
that existing direct slice and add `5X` additional raw-text-derived task tokens.

DFM2 should keep the current DynaWord direct/continuation token budget as `X`,
then add raw-text-derived objectives with the following covered-token budgets:

- `X` existing direct/continuation tokens, preserving the current DynaWord
  plain-text signal.
- `X` continuation-task tokens where each example gives a non-trivial document
  prefix as instruction/context and trains the model to generate the suffix.
  The prefix should be randomly selected between `25%` and `75%` of the chunk.
- `X` denoising-task tokens where the instruction contains corrupted text and
  the response is the clean original text. Corruption should affect about
  `10%` of words, using a mix of word swaps, deletions, replacements, and
  random inserted words after selected words.
- `3X` autoregressive span-filling tokens. The instruction contains the full
  text with masked spans; the response rewrites the full clean text, filling in
  the masked spans.

Total DFM2 raw/plain-text-derived target size is therefore `6X` covered tokens
for the DynaWord-derived component if `X` is measured over sampled covered
tokens. With `X ~= 2.8B` per epoch, the new additions are about `14B` tokens per
epoch and the total DynaWord-derived component becomes about `16.8B` tokens per
epoch. The added `5X` part is split as `1X` prefix-continuation, `1X`
denoising, and `3X` span filling, with span filling intentionally dominating
the self-supervised additions.

Implemented and sampled locally on 2026-05-30:

- Generator: `scripts/generate_dfm2_dynaword_tasks.py`
- Sampling config: `data_io/prefix_config_dfm2.yaml`
- Training data config: `config/data/dfm2.yaml`
- Generated converted sources: `data/converted_sources_dfm2_dynaword_tasks`
- Generated tokenized sources: `data/tokenized_dfm2_dynaword_tasks`
- Tokenized union: `data/tokenized_dfm2`
- Sampled output: `data/sampled_dfm2`
- Analytics: `data/show_analytics_dfm2.md`

The final implementation avoids `repeat: 2` for generated DynaWord task
families because repeating can duplicate rows. Instead it creates two unique
prefix-continuation variants, two unique denoising variants, and six unique
span-fill variants. The generated tokenization was run with exactly one
tokenizer worker.

Verified DFM2 sampled totals:

- `metadata.total_length`: `42,317,252,803` tokens per epoch.
- Global unique tokens sampled: `71,801,166,164 / 95,130,241,400` across four
  epochs.
- Retained direct DynaWord slice: `11,255,771,693` covered tokens across four
  epochs, or `2,813,942,923` per epoch. This is `X`.
- Generated DynaWord task additions: `56,253,792,196` covered tokens across
  four epochs, or `14,063,448,049` per epoch. This is `4.998X`.

Measured generated additions by objective:

| Objective family | Covered tokens / epoch |
|---|---:|
| Prefix continuation v1 | `1,320,302,625` |
| Prefix continuation v2 | `1,320,302,124` |
| Denoising v1 | `1,456,506,751` |
| Denoising v2 | `1,456,578,755` |
| Span fill v1 | `1,418,307,269` |
| Span fill v2 | `1,418,288,911` |
| Span fill v3 | `1,418,277,059` |
| Span fill v4 | `1,418,307,269` |
| Span fill v5 | `1,418,305,179` |
| Span fill v6 | `1,418,272,107` |

## English Eval Remediation Hypothesis

Recorded on 2026-05-31. Updated on 2026-06-12. Confidence: medium for causal
attribution, high for local source-filter facts.

Problem: DFM/DFM2 improves Danish coverage but can underperform the original
Sapient run on English factual/commonsense/reading-comprehension evaluations
such as `MMLU`, `Winogrande`, `ARC-C`, `HellaSwag`, `DROP`, and `BoolQ`.

Local evidence:

- Original Sapient sampling had broad `flan` as the largest component:
  `23,896,311,328` covered tokens across four epochs, or `42.6%` of the
  original covered-token budget. It also had `tasksource` at `617,688,319`
  covered tokens.
- The source filter now denies broad `sapient_cleaned/data_clustered/flan/**`
  and `sapient_cleaned/data_clustered/tasksource/**`, with narrow allow
  overrides only for selected math/science/commonsense/reasoning tasks.
- The denied FLAN/Tasksource space included many English benchmark-adjacent
  instruction families: ARC, BoolQ, DROP, SQuAD, TriviaQA, Natural Questions,
  SuperGLUE/GLUE, ANLI/SNLI/MNLI, CoQA/QuAC, summarization/news, dialogue, and
  broad commonsense tasks.
Superseded, 2026-06-12: the older claim that `scienceqa.jsonl` is denied is
stale. Current DFM4 source filtering includes ScienceQA. The current Platypus
denials are only `reclor.jsonl` and `scibench.jsonl`, plus the Tasksource
ReClor recast.

Likely explanation:

- `MMLU` loss is probably mostly factual/world-knowledge and broad
  instruction coverage loss, not just missing exact MMLU-style rows.
- `ARC-C`, `BoolQ`, and `DROP` loss is likely direct removal of related
  QA/reading-comprehension formats from broad FLAN.
- `Winogrande` and `HellaSwag` are partially protected because narrow FLAN
  allow overrides include `winogrande` and `hellaswag`, but the current caps
  may still be much smaller than the original broad FLAN exposure.

Updated DFM4 assessment, 2026-06-12:

- The direct FLAN train-derived sources for `Winogrande`, `HellaSwag`,
  `ARC`, `BoolQ`, `DROP`, `RACE`, `TriviaQA`, `SQuAD`, and several
  commonsense/science families are included by current source filtering.
- The excluded original Sapient files most likely to hurt these English evals
  are indirect support sources rather than the exact benchmark families:
  Natural Questions and MS MARCO for factual/open QA and BoolQ-like reading;
  ReClor and SciBench for hard reasoning/science transfer; dialogue/social
  commonsense families for Winogrande/HellaSwag-style pragmatics; and broad
  review/sentiment/opinion classification for general instruction-following and
  classification calibration.
- WMT/newscomm exclusions are mainly a translation/multilingual loss and are
  not expected to be first-order drivers for Winogrande, HellaSwag, ARC, BoolQ,
  or MMLU, except through general English exposure.

Per-source risk review for the first four high-impact excluded families,
2026-06-12. Confidence: high for local excluded-file counts and source-filter
state; medium for upstream provenance/GDPR judgments from dataset cards/papers.

1. Natural Questions / MS MARCO: `10` excluded Sapient FLAN files. Natural
   Questions files are derived from real Google search queries with Wikipedia
   answers. MS MARCO files are derived from real Bing queries, web passages,
   and human-written answers. Provenance risk is medium/high because project
   policy treats Google/Bing search-derived data as harsh-robots/relevant-path
   cases; MS MARCO terms also disclaim ownership of underlying web documents.
   GDPR/PII risk is medium because queries are anonymized/aggregated but still
   originate from real users and can contain personal or sensitive facts.
   Affected local files: the four `natural_questions_open` FLAN variants, two
   NIV2 `naturalquestion_answer_generation` variants, and four NIV2
   `msmarco_answer_generation` / `msmarco_question_generation` variants.

2. ReClor / SciBench: `3` excluded files:
   `sapient_cleaned/data/Platypus/reclor.jsonl`,
   `sapient_cleaned/data/Platypus/scibench.jsonl`, and
   `sapient_cleaned/data_clustered/tasksource/reclor.parquet`. ReClor says
   passages come from websites/books not owned by the dataset authors and is
   non-commercial research only. SciBench says problems are sourced from
   instructional/college textbooks. Provenance/copyright risk is high; GDPR/PII
   risk is low. They remain excluded as eval-only/provenance-sensitive sources.

3. Dialogue/chat: `82` excluded files. This bucket includes QReCC/wiki_dialog
   FLAN variants, DailyDialog/dailydialog, PersonaChat/persona, AirDialogue,
   Deal-or-No-Deal, CaSiNo, Curiosity Dialogs, DialogRE, DREAM, MUTUAL,
   Dialogue NLI, MRDA, and Switchboard recasts. Provenance risk varies:
   QReCC combines NQ/TREC/QuAC-style sources and a large web-passage retrieval
   collection; DailyDialog is human-written and CC-BY-NC-SA; other dialogue
   datasets range from crowd-written/role-play to conversation transcripts.
   GDPR/PII risk is medium/high because many files contain human or simulated
   conversations, named entities, personal preferences, or relationship facts.
   Even synthetic/crowd-written chat can encourage memorization of realistic
   personal profiles. Current project policy keeps this bucket excluded.

4. Social/toxicity/emotion/sarcasm: `97` excluded files. This bucket includes
   TweetEval/twitter/tweet QA/emotion/sarcasm files, HateXplain, HateEval,
   hate_speech_offensive, implicit-hate, Dynahate, Civil Comments/Jigsaw,
   GoEmotions, CrowdFlower text emotion, WNUT, and Twitter financial news
   sentiment. Provenance risk is medium: some datasets are CC0 or benchmark
   releases, but many are social-platform posts, comments, or rehosted user
   content with platform/API constraints. GDPR/PII risk is high because the
   text is generated by real users, often includes handles, names, URLs,
   identity attributes, abusive content, or event-specific sensitive opinions.
   Civil Comments is better documented and CC0, but still contains public
   comments from identifiable contexts; TweetEval/HateXplain-style sources
   remain excluded under the non-public-person personal-data policy.

DFM5 policy adjustments, 2026-06-12. Confidence: medium.

DFM5 baseline intent update, 2026-06-12. Confidence: high for local filter
inspection and file counts; medium for whether each current exclusion remains
final policy. DFM5 should be the mix that includes all locally available
original Sapient cleaned sources except sources still explicitly excluded by
`config/data/source_filter.yaml`, plus later non-Sapient additions. With the
current source-filter semantics (`allow_overrides` wins before `deny`),
Sapient cleaned data files are:

Superseded by the applied reconsideration immediately below.

```text
allowed: 4,835
denied:    378
```

Current denied Sapient categories by file count:

```text
FLAN reviews/opinion/email:                  154 files, ~123.16 GB
FLAN dialogue/chat/persona:                   66 files, ~0.19 GB
FLAN toxicity/hate/emotion/comments:          56 files, ~0.05 GB
FLAN WMT / News Commentary harsh-robots:      42 files, ~64.33 GB
FLAN Twitter/TweetEval/social:                20 files, ~0.03 GB
Tasksource social/toxicity/emotion/spam:      16 files, ~0.02 GB
FLAN SMS/spam:                                 6 files, ~0.01 GB
FLAN Natural Questions / NQ Open:              6 files, ~0.05 GB
FLAN MS MARCO:                                 4 files, ~0.01 GB
Tasksource dialogue/chat/transcripts:          3 files, small
Platypus ReClor/SciBench:                      2 files, ~0.01 GB
Tasksource reviews/opinion:                    2 files, small
Tasksource ReClor:                             1 file, small
```

Important policy conflict to resolve before final DFM5 sampling: earlier DFM5
notes proposed including Natural Questions / Natural Questions Open subject to
PII inspection, but the current filter still denies local Sapient NQ/NQ-Open
FLAN transforms as a harsh-robots/search-derived family. MS MARCO remains
under review and is also denied. WikiDialog, DREAM, and MuTual have already
been allow-overridden for DFM5 despite broader dialogue deny patterns, so they
are not part of the 378 denied files.

DFM5 source-filter reconsiderations applied, 2026-06-12. Confidence: high for
local filter dry-run and exact allow-overrides. `config/data/source_filter.yaml`
now allow-overrides the accepted factual QA and lower-risk dialogue/role-play
families:

```text
natural_questions_open
naturalquestion
dailydialog / daily_dialog
personachat
deal_or_no
casino
air_dialogue
wiki_dialog
dream
mutual
tasksource/mutual.parquet
```

The first seven entries above were newly added in this update; WikiDialog,
DREAM, and MuTual were already applied earlier. The broad deny rules remain as
defaults for unreconsidered chat/search/social sources. Dry-run verification
was followed by rebuilding the filtered source symlink tree:

```text
Input:          data/downloads/datasets
Allowed files: 10,605
Denied files:     328
Allowed bytes: 820,913,796,916
```

Rebuild log: `logs/build_filtered_source_tree_dfm5_reconsiderations_20260612.log`.

Sapient-only data-file counts after the update:

```text
allowed: 4,885
denied:    328
```

Remaining denied Sapient categories:

```text
FLAN reviews/opinion/email:                  154 files, ~123.16 GB
FLAN toxicity/hate/emotion/comments:          56 files, ~0.05 GB
FLAN WMT / News Commentary harsh-robots:      42 files, ~64.33 GB
FLAN dialogue/chat/persona residual:          22 files, ~0.09 GB
FLAN Twitter/TweetEval/social:                20 files, ~0.03 GB
Tasksource social/toxicity/emotion/spam:      16 files, ~0.02 GB
FLAN SMS/spam:                                 6 files, ~0.01 GB
FLAN MS MARCO:                                 4 files, ~0.01 GB
Tasksource dialogue/chat/transcripts:          3 files, small
Platypus ReClor/SciBench:                      2 files, ~0.01 GB
Tasksource reviews/opinion:                    2 files, small
Tasksource ReClor:                             1 file, small
```

Verification found no denied files matching the reconsidered NQ/NQ-Open,
DailyDialog, PersonaChat, Deal-or-No-Deal, CaSiNo, AirDialogue, WikiDialog,
DREAM, or MuTual terms. MS MARCO remains under review and denied.

Remaining-denied reconsideration pass, 2026-06-12. Confidence: high for local
file lists and sampled local rows; medium for policy recommendations.

Potentially includable after an explicit DFM5 decision:

- `msmarco`: `4` FLAN/NIV2 files, about `0.01 GB`. Local rows retain only
  transformed `instruction`, `response`, and `condition`, not source URLs. The
  sampled examples are factual web-passage QA. Main residual risk is Bing/web
  provenance rather than obvious PII in the transformed rows. If included, use
  the original generic FLAN cap or a tighter DFM5 cap.
- `qrecc`: `4` FLAN dialogue files, about `0.05 GB`. It is conversational QA
  with web/Wikipedia-style retrieval origins. Local samples looked noisy, so
  include only if we value conversational QA coverage and accept quality
  review/capping.
- `curiosity_dialogs`: `6` FLAN files, about `0.025 GB`. Information-seeking
  dialogue; sampled rows looked like generic factual dialogue rather than
  private personal chat. Candidate for inclusion with generic FLAN caps.
- `dialogue_nli`: `1` Tasksource file, about `0.002 GB`. Persona-style NLI
  statements; conceptually close to PersonaChat, which DFM5 already accepts.
  Candidate for inclusion if we accept persona-like synthetic/crowd-written
  sentences.
- `newscomm`: `14` FLAN files, about `0.024 GB`. Translation/classification
  from News Commentary. It remains denied under the earlier harsh-robots/source
  route rationale, but it is small and translation-oriented; include only if
  that source-route concern is relaxed.

Generally keep excluded:

- Review/opinion/email/user-product corpora, especially Amazon/Yelp/IMDb/app
  reviews/AESLC/opinion abstracts: large user-authored text, highest remaining
  byte share, and easy to replace with cleaner instruction/summarization data.
- Twitter/TweetEval/social, SMS/spam, WNUT, hate/toxicity/offensive/emotion,
  GoEmotions, Civil Comments, and related comment datasets: user text with
  protected attributes, names/handles/URLs, abuse, or event-specific sensitive
  opinions.
- `dialogre`, `pragmeval_mrda`, and `pragmeval_switchboard`: transcript or
  TV/script/dialogue-extraction style sources with named speakers and weaker
  marginal value.
- `wmt`: very large translation block (`28` files, about `64.3 GB`) and still
  covered by the harsh-robots/source-route rationale. Prefer OPUS and approved
  Danish/translation sources unless explicitly relaxing that rule.
- ReClor and SciBench: remain explicit project exclusions.

- Include Natural Questions / Natural Questions Open for DFM5, unless row-level
  PII inspection finds actual personal data in the questions. The rationale is
  that the rows are mostly search-style factual questions and Wikipedia-derived
  answers; the remaining practical risk is PII in query text rather than
  ordinary copyright/licence terms.
- Keep MS MARCO under review rather than include automatically. Local Sapient
  MS MARCO Parquet transforms retain only `instruction`, `response`, and
  `condition`, so source URLs/domains are not available locally. The sampled
  rows contain generic Bing web snippets such as government benefits, health,
  pension/finance advice, company profiles, BBB/D&B-style pages, and technical
  passages. Upstream MS MARCO says passages come from real web documents
  retrieved by Bing and warns that Microsoft may not own underlying document
  rights.
- Keep ReClor and SciBench excluded for DFM5.
- Include DailyDialog and lower-risk role-play/negotiation dialogue sources for
  DFM5: DailyDialog/dailydialog, PersonaChat/persona, Deal-or-No-Deal,
  CaSiNo, and likely AirDialogue after final file-pattern review. Continue to
  exclude QReCC/wiki_dialog, MUTUAL, Switchboard/MRDA, DialogRE, DREAM, and
  other dialogue sources that are web-retrieval, transcript-like, or
  named-entity-heavy unless separately approved.
- Continue excluding Tweet/Twitter/hate/toxicity/emotion/sarcasm sources for
  now. Civil Comments/Jigsaw is lower-provenance-risk than Twitter data because
  it is CC0 and documented as public comments without user IDs, but it remains
  GDPR/PII-sensitive: free-form comments can include names, URLs/contact links,
  political opinions, protected-class references, insults/threats, and
  article/timestamp context. If ever included, use tight caps plus PII/URL/name
  scrubbing and avoid examples likely to reproduce comments verbatim.

Refinement on MuTual / WikiDialog / DREAM, 2026-06-12. Confidence: medium.

- WikiDialog is not a GDPR-heavy source: upstream describes it as synthetic
  information-seeking dialogue grounded in English Wikipedia. The main reasons
  to keep it out are scale/control and synthetic quality. Local Sapient
  WikiDialog transforms are very large (`4.15M`, `1.24M`, `2.08M`, and
  `0.62M` rows across four Parquet files), sometimes awkwardly reconstruct
  previous dialogue from a response, and would inject a large amount of
  Wikipedia-style synthetic dialogue unless capped and reviewed separately.
- MuTual is based on Chinese student English listening comprehension exams, and
  local rows are multiple-choice continuation tasks. GDPR risk is low; the
  stronger arguments for exclusion are benchmark-style/eval-adjacent training
  and limited marginal value once HellaSwag/Winogrande/DailyDialog/persona/
  negotiation data are included. It can be reconsidered as an optional tightly
  capped reasoning-dialogue source if benchmark adjacency is accepted.
- DREAM is also exam-derived dialogue reading comprehension. GDPR risk is low,
  but it is a named benchmark with direct train/dev/test style tasks and
  multiple T0/NIV2 transforms in Sapient. Keep excluded if preserving clean
  dialogue-RC evaluation boundaries matters; otherwise it is an optional
  capped source for dialogue reasoning rather than a privacy exclusion.

Superseded later on 2026-06-12 by project decision: include MuTual, WikiDialog,
and DREAM for DFM5 with original Sapient sampling caps.

Implementation note, 2026-06-12. Confidence: high. `config/data/source_filter.yaml`
now allow-overrides:

- `sapient_cleaned/data_clustered/flan/*wiki_dialog*.parquet`
- `sapient_cleaned/data_clustered/flan/*dream*.parquet`
- `sapient_cleaned/data_clustered/flan/*mutual*.parquet`
- `sapient_cleaned/data_clustered/tasksource/mutual.parquet`

No DFM4/DFM5 sampling override was added for these families. They therefore
inherit the original generic Sapient caps already used by the sampling config:
FLAN files match `sapient_cleaned__data_clustered__flan__` with
`max_per_file: 5_000`; Tasksource MuTual matches
`sapient_cleaned__data_clustered__tasksource__` with `max_per_file: 10_000`.
Dry-run verification after the edit reported `10,555` allowed files and `378`
denied files, and all local MuTual, WikiDialog, and DREAM files matched
`allowed`.

Candidate remediation mix:

- Add a small English open-text self-supervised slice, initially `5-10B`
  covered tokens per epoch, from cleaner Common Pile components rather than
  broad web text. Prefer filtered/public-domain/open-license components such as
  Wikimedia, StackExchange, PubMed, arXiv abstracts/papers, USGPO/regulations,
  USPTO, public-domain books/reviews, and Library of Congress material. Avoid
  YouTube/IRC/social-chat components by default because of PII/GDPR and
  conversation-quality risks.
- Convert this slice with the same objective family as DFM2, but in English:
  direct continuation, prefix continuation, denoising, and span filling. This
  should help language modeling, factual recall, and reading-comprehension
  robustness without reintroducing the broad FLAN aggregate.
- Upscale existing approved English instruction sources before re-admitting
  risky Sapient aggregates: `allenai_tulu_*`, `dolci_*`,
  `nemotron_instruction_reasoning_off`, `allenai_if_sft_verified`, selected
  `nemotron_multilingual`, `no_robots`, and retained allowed FLAN/Tasksource
  science/commonsense tasks.
- For benchmark-adjacent train data, make an explicit policy distinction:
  using official train splits of ARC/BoolQ/DROP/HellaSwag/Winogrande is useful
  for capability recovery but should be marked as benchmark-adjacent and kept
  separate from “clean generalization” runs. If included, hash-dedupe against
  evaluation prompts and report it clearly.

Recommended first ablation:

- Keep DFM2 unchanged.
- Add `5B` covered tokens per epoch of English Common-Pile-derived
  self-supervised tasks from the cleaner components above.
- Add `2-4B` covered tokens per epoch by raising caps on approved English SFT
  sources.
- Optionally add a tightly capped, benchmark-adjacent train-only slice for
  ARC/BoolQ/DROP/HellaSwag/Winogrande only in a separate run label.

## DFM3 English Recovery Mix

Decision recorded on 2026-05-31. Confidence: high for local repo
implementation and Common Pile inventory dry-run; medium for final token
proportions until DFM3 is downloaded/tokenized/sampled and
`data/show_analytics_dfm3.md` is inspected.

DFM3 is the combined remediation run:

- Base: DFM2.
- Add selected Common Pile raw text with DFM2-style objectives using
  `X ~= 2.8B` covered tokens per epoch, matching the DFM2 DynaWord direct
  slice.
- Add another approximate `14B` covered tokens per epoch by raising caps for
  already approved English/multilingual instruction data most likely to help
  English factual, commonsense, and reading-comprehension evals.

Common Pile raw-objective target:

- `1X` direct continuation.
- `1X` prefix continuation, with 25-75% prefix.
- `1X` denoising, with about 10% word corruption.
- `3X` span filling, implemented as three span-fill variants.

Not included in DFM3: paragraph reordering. The DFM2 and DFM3 generators only
emit direct continuation, prefix continuation, denoising, and span-filling
families. A safe follow-up is an additive DFM4-style task source that samples
multi-paragraph documents from both DynaWord and selected Common Pile, shuffles
paragraph order while preserving paragraph contents, and asks the model to
restore the original order. Use response text as the original correctly ordered
document rather than only an index sequence, so target-only training still
teaches fluent reconstruction. Confidence: high for current absence; medium for
the proposed mix until implemented and sampled.

Summarization follow-up candidates:

- Already included/local instruction-style summarization includes DBC abstracts
  and the Oliver Kinch Danish EUR-Lex summarization manifest entry.
- Common Pile `arxiv_abstracts_filtered` contains standalone abstracts, while
  `arxiv_papers_filtered` contains full paper text with abstract-like sections.
  These can be paired by arXiv id or section-extracted to create paper-to-
  abstract summarization tasks, subject to per-record license filtering.
- Common Pile `pubmed_filtered` contains full PubMed Central article text with
  license metadata and can often support article-to-abstract or intro/body-to-
  abstract tasks if an abstract section can be extracted robustly.
- Common Pile `uspto_filtered` has patent text where early summary/object
  sections may be extractable, but this is weaker and noisier than arXiv/PubMed.
- External HF candidates that need explicit license/provenance checks before
  inclusion: `ccdv/pubmed-summarization`, `ccdv/govreport-summarization`,
  `billsum`/`FiscalNote/billsum`, `allenai/multi_lexsum`, `bigbio/multi_xscience`,
  and `laion/Scientific-Summaries`. Avoid news-web summarization corpora such as
  CNN/DailyMail, XSum, and Multi-News by default because they are more likely to
  reintroduce copyrighted-news risk. Confidence: medium.

## DFM4 Paragraph Reordering And Summarization

Decision recorded on 2026-06-01. Confidence: high for local implementation and
final sampled analytics.

DFM4 is DFM3 plus six additive task families:

- `dfm4_dynaword_paragraph_reorder__`: paragraph reordering from DynaWord,
  targeting about `2.8B` covered tokens per epoch.
- `dfm4_common_pile_paragraph_reorder__`: paragraph reordering from selected
  Common Pile, targeting about `2.8B` covered tokens per epoch.
- `dfm4_arxiv_paper_summarization__`: arXiv paper-to-abstract summarization
  extracted from locally downloaded Common Pile arXiv papers, targeting about
  `2.8B` covered tokens per epoch.
- `dfm4_govreport_summarization__`: GovReport summarization from
  `ccdv/govreport-summarization`, capped conservatively with `repeat: 2`
  because this source is small and unique coverage will be much smaller than
  exposure coverage.
- `dfm4_wiki_cat_sum_summarization__`: Wikipedia/WikiSum-derived
  summarization from `GEM/wiki_cat_sum`, capped conservatively with `repeat: 2`
  because this source is also relatively small and repeated exposure should not
  dominate.
- `dfm4_laion_scientific_summaries__`: structured scientific summarization
  from the arXiv slice of `laion/Scientific-Summaries`, enlarged to absorb the
  remaining summarization budget.

Summarization length policy adjustment, 2026-06-01. Confidence: high for local
schema/length samples; medium for final token proportions until DFM4 analytics
are inspected.

- LAION Scientific-Summaries full structured responses are usually too long
  for the current 4k-context training format. A local sample showed median
  full-response length around `14k` characters, leaving no document budget under
  the response-preserving length policy. The generator is therefore adjusted to
  use the full structured summary only when it naturally fits; otherwise it
  falls back to a compact response from `executive_summary`, `key_results`, and
  `three_takeaways`, and finally to abstract-to-`key_results` or
  abstract-to-`three_takeaways` tasks when document-to-summary does not fit.
- GovReport is not problematic because of source quality; the risk is
  conversion quality. Its summaries are often long relative to 4k context, so
  response preservation can leave too little source document. With `repeat: 2`,
  GovReport is a small auxiliary source, but DFM4 analytics should confirm that
  converted rows retain useful document context.
- WikiCatSum has short enough targets in local samples and should work with the
  current document-trimming policy.
- Common Pile arXiv paper summaries do not have the LAION full-structured-
  response problem. A local sample found `## ABSTRACT` extraction in about
  `69%` of the first `4,000` sampled records from two shards; abstracts had
  median length around `965` characters and median remaining document budget
  around `1,735` characters.

The new HF downloader entries are:

- `govreport_summarization`: `ccdv/govreport-summarization`,
  `document/train-*.parquet`.
- `wiki_cat_sum`: `GEM/wiki_cat_sum`, `main_splits/train-*.jsonl`.
- `laion_scientific_summaries`: `laion/Scientific-Summaries`,
  `data/arxiv/*.parquet` only by default. The HF card reports `cc-by-4.0` and
  LLM-generated structured summaries; use this as a synthetic-data source.

Local inventory on 2026-06-01:

```text
govreport_summarization:        435.4 MB,     3 files
wiki_cat_sum:                     5.4 GB,     4 files
laion_scientific_summaries:     142.7 GB, 4,008 files
Total selected HF bytes:        148.6 GB
```

Implemented local paths:

- Generator: `scripts/generate_dfm4_tasks.py`
- Tokenized union builder: `scripts/build_tokenized_dfm4_tree.py`
- Sampling config: `data_io/prefix_config_dfm4.yaml`
- Training data config: `config/data/dfm4.yaml`
- Stage script: `scripts/prepare_dfm4_paragraph_and_summarization.sh`

Superseded: the first DFM4 sampled analytics used four epochs and the earlier
single-window paragraph-reorder generation. The current sample below supersedes
those four-epoch numbers.

Current DFM4 sampled analytics, verified 2026-06-01:

- `data/sampled_dfm4/metadata.json` reports `total_length=72,007,089,569`
  tokens per epoch and `max_seq_len=4097`; sampling was run with `epochs=5`.
- `data/show_analytics_dfm4.md` reports `360,035,447,845` covered tokens
  across five epochs, or `72,007,089,569` covered tokens per epoch.
- DFM4 additive category exposure across five epochs:
  - `dfm4_common_pile_paragraph_reorder`: `7,919,193,665` covered tokens.
  - `dfm4_laion_scientific_summaries`: `7,320,261,295` covered tokens.
  - `dfm4_dynaword_paragraph_reorder`: `3,205,404,709` covered tokens.
  - `dfm4_wiki_cat_sum_summarization`: `1,141,780,940` covered tokens.
  - `dfm4_arxiv_paper_summarization`: `725,773,415` covered tokens.
  - `dfm4_govreport_summarization`: `25,075,850` covered tokens.
- The final GovReport contribution is intentionally tiny; the conservative
  `repeat: 2` keeps it auxiliary because long summaries make conversion quality
  less reliable at 4k context.
- The final LAION contribution is much larger than the original broken
  full-structured-summary conversion would have been, but still far below the
  requested residual summarization budget because only short-enough or compact
  summary forms are retained.

Important caveat: the user asked for `2.8GB` per epoch, interpreted here as
the standing project target of approximately `2.8B` covered/exposure tokens per
epoch. The sampler is row-capped, not byte-capped, so exact budgets require
post-sampling analytics inspection and cap tuning.

Length-policy plan retained for near-term execution:

- Keep `sample_tokenized.py` truncation as a final guard only.
- Add conversion/generation-time length policy by task type.
- Raw continuation is safe as empty-instruction response-only data.
- Prefix continuation should trim prefix if needed, but preserve a non-trivial
  suffix/response.
- Reconstruction tasks such as denoising, span fill, and paragraph reorder
  should enforce response space at least equal to instruction payload space
  plus prompt overhead; generated chunks should be about half-context by char
  proxy unless token-aware fitting is added.
- Summarization should keep the summary response intact when possible, trim the
  source document to leave room for the response, and drop rows whose summary
  alone is too long.
- Translation should preserve target parity with source; drop or split very
  long pairs instead of truncating target aggressively.
- Extractive QA should cap context or trim around answer spans when available;
  reserve a small fixed answer budget.
- Chat/tool/agent/SWE data should trim oldest history/logs first and never let
  history erase the assistant response.
- Generic instruction/output rows should be response-priority: trim instruction
  first, drop or split overlong responses.
- Add sampler analytics for dropped/truncated rows and truncated response
  tokens per task before treating sampled caps as final.

Current cap/repeat recommendations before DFM4 sampling:

- Cap `sapient_cleaned__data_clustered__flan__cot_` explicitly rather than
  leaving it uncapped through prefix overlap. The concern is not that the data
  is intrinsically low quality, but that it is benchmark-adjacent, template
  heavy, and can make English eval gains less clean/broader if it silently
  dominates retained FLAN.
- Keep DFM4 GovReport and WikiCatSum exposure conservative. The previous
  `repeat: 8` and `repeat: 6` are superseded by `repeat: 2` for both sources.
  Shift the remaining summarization budget to LAION Scientific-Summaries and
  arXiv paper summarization.
- Preserve the intended self-supervised objective ratio: direct continuation,
  prefix continuation, denoising, and paragraph reordering are each `1X`
  families, while span filling is `3X` in aggregate. For Common Pile, this means
  either leave all three span-fill variants at the same per-file cap as the
  direct/prefix/denoise families, or reduce all of those family caps together.
  Do not reduce span-fill variants below the other Common Pile raw-objective
  families.
- For DFM4, `X = 1.4B` covered/exposure tokens per epoch is the chosen
  controlled target for the additive raw-objective families. This gives roughly
  `9.8B` tokens/epoch across direct continuation, prefix continuation,
  denoising, paragraph reordering, and aggregate span filling (`3X`). Based on
  DFM3 analytics, the starting Common Pile caps are `5k` rows/file for
  direct/prefix continuation and `2.5k` rows/file for denoising and each
  span-fill variant. This preserves the `3X` aggregate span-fill budget because
  there are three span-fill variants. DFM4 paragraph-reorder starting caps are
  `30k` rows/file for DynaWord and `2.5k` rows/file for Common Pile, pending
  DFM4 analytics because paragraph reordering is also a reconstruction-style
  objective with higher tokens/row.
- `synquid_danish_verifiable_reasoning` and `oliverkinch_instruct_bt` are both
  set to `repeat: 5` for DFM4. This keeps useful Danish reasoning/instruction
  signal without the heavier duplicate exposure from the earlier
  `synquid_danish_verifiable_reasoning` `repeat: 20`.
- Consider reducing `laerebogen_with_followups` repeat from `2` to `1` if DFM4
  becomes too large or too Danish-instruction-heavy; DFM3 analytics show it is
  already a large Danish instruction component at about `5.1B` exposure tokens
  per epoch.
- Consider reducing `nemotron_multilingual` from `250k` max/source to
  `100k-150k` unless multilingual transfer is explicitly prioritized; DFM3
  analytics show it is one of the largest non-Danish instruction components at
  about `8.9B` exposure tokens per epoch.
- Post-DFM4 assessment: `nemotron_multilingual` is probably not the most
  efficient source for recovering English MMLU/ARC-C/BoolQ/DROP-style scores.
  The local README says it is translated from Nemotron Math, Competitive
  Programming, and Science into German, Spanish, French, Italian, Japanese,
  and Chinese; prompts/answers are in the target language while reasoning
  traces remain English. It is useful for multilingual STEM/code/math transfer
  and may help reasoning robustness, but it is not English factual/world
  knowledge, English commonsense, or English reading-comprehension coverage.
  In DFM4 it contributes `35,754,497,240` sampled tokens across four epochs
  (`13.4%` of category exposure, `19.3%` of response exposure), which is large
  relative to its expected direct benefit for MMLU/ARC-C. For an English eval
  recovery run, prefer lowering this cap and reallocating some budget to
  English instruction/reasoning/QA sources such as `nemotron_instruction`,
  Dolci/Tulu, selected retained FLAN/Tasksource benchmark-adjacent train
  families, and clean English raw-text objectives. Confidence: high for local
  schema/analytics; medium for transfer-effect prediction.
- DFM4 adjustment after that assessment: `nemotron_multilingual__` is reduced
  to `max_per_file: 50_000`. The reclaimed budget is reallocated to diverse
  English instruction/reasoning sources and benchmark-adjacent Sapient FLAN
  train-derived families. `allenai_big_reasoning_traces`,
  `allenai_verifiable_reasoning_*`, `natural_reasoning`,
  `principia_collection`, `textbook_reasoning`, `webinstruct_verified`,
  `nemotron_instruction_reasoning_off`, Dolci SFT/no-tools, and Tulu SFT caps
  were raised moderately rather than using large repeats. Confidence: high for
  config edits; medium for expected eval impact.
- For academic/non-commercial training, RACE and TriviaQA are now accepted as
  benchmark-adjacent sources with explicit caps. The source filter admits RACE
  reading-comprehension files and TriviaQA/Trivia question files from the
  Sapient FLAN tree, plus ARC, BoolQ, DROP, SQuAD, ANLI, MNLI,
  GLUE/SuperGLUE, HellaSwag, Winogrande, OpenBookQA, QASC, SciQ,
  StrategyQA, Quartz, COPA/XCOPA, PIQA, and StoryCloze train-derived families.
  Superseded on 2026-06-01 for harsh robots: Natural Questions Open and
  MS MARCO are excluded again.
  `stereoset_classification_race` remains excluded because "race" there is
  the protected-attribute sense, not the RACE reading-comprehension benchmark.
  Confidence: high for local file matching; medium for source-card risk.
- Relationship to the original Sapient mix, 2026-06-01. Confidence: high for
  local analytics/config inspection; medium for impact prediction. The original
  Sapient sample was dominated by broad FLAN: `23.90B` covered tokens across
  four epochs (`42.6%`), with `SYNTH` at `14.27B` (`25.4%`) and `tasksource`
  at `0.62B` (`1.1%`). DFM4 caps are deliberately not a row-for-row recreation
  of that mix. The `20k` per-file caps on selected FLAN benchmark-adjacent
  families are intended to recover ARC/BoolQ/DROP/SQuAD/TriviaQA/RACE/NLI/
  commonsense formats while keeping each source bounded. Superseded for harsh
  robots: NQ/MS MARCO/WMT/News Commentary are now excluded. The
  generic FLAN fallback is lower (`5k` per file), so newly allowed broad
  residual FLAN remains auxiliary. Tasksource remains tightly capped (`10k`,
  with `race-c` at `20k`). Repeats are used mainly for small, trusted Danish
  sources and small summarization sources; large English recovery sources use
  caps rather than repeats to increase diversity and avoid duplicate exposure.
  The existing `data/show_analytics_dfm4.md` predates the latest cap changes
  and still shows old exposure such as `nemotron_multilingual` at `35.75B`
  across four epochs; rerun sampling is required for final DFM4 exposure
  numbers after the current config changes.
- Current remaining source-filter exclusions after the Article 3/GDPR policy
  update, computed by `python scripts/build_filtered_source_tree.py --dry-run`
  on 2026-06-01. Confidence: high for local filter evaluation. Intended filter
  result after the later review/spam/ReClor tightening: `9,832` allowed data
  files and `337` denied data files. The denied data files are `312` Sapient
  FLAN files matching user/chat/social/review/opinion/spam/toxicity PII-risk
  patterns, `23` Sapient Tasksource files matching similar PII-risk or ReClor
  eval-only patterns, and two explicit Platypus eval-only exclusions:
  `reclor.jsonl` and `scibench.jsonl`. `scienceqa.jsonl` is now included.
- Legal/policy reassessment for non-commercial EU academic training with an
  intent to publish open weights, 2026-06-01. Confidence: medium; this is not
  legal advice. The working basis is Article 3 scientific-research TDM, not
  ordinary open-license reuse. Under that basis, lawful access and secure copy
  handling matter more than permissive licensing, and contractual limits that
  contradict Article 3 are not treated as blockers. ScienceQA is included under
  this rationale. ReClor and SciBench remain excluded by project decision for
  training and may be used later for evaluation. Included sources that deserve
  extra notation before open-weight publication are mainly those with possible
  personal data: chat, social-media, user reviews, toxicity/offensive speech,
  and similar non-public-person text. Sources that are acceptable under this
  policy should not be downweighted merely because Sapient downweighted them
  differently; use caps for corpus balance and duplicate-exposure control.
- Clarified policy update, 2026-06-01. Confidence: medium. The current project
  decision is that the EU DSM Directive Article 3 research TDM exception is the
  working copyright basis when a qualifying research organisation has lawful
  access to the dataset/content. Under that basis, licensing terms, ShareAlike,
  non-commercial terms, and benchmark adjacency are not blockers by themselves;
  GDPR/PII risk involving non-public persons remains the hard constraint.
  Article 3 also requires appropriate security for TDM copies retained for
  scientific research. ReClor and SciBench stay excluded from training by
  project decision and may be used later for evaluation. ScienceQA is included
  under the lawful-access/TDM rationale unless later legal review rejects that
  basis. For allowed FLAN files, the default target is to match Sapient-original
  per-file exposure: generic FLAN `max_per_file: 5_000`, FLAN CoT uncapped as
  in the original config, generic Tasksource `max_per_file: 10_000`, and
  Platypus `repeat: 10`. DFM4 is much larger than Sapient original and excludes
  the PII-risk files, so allowed FLAN should no longer dominate percentage-wise.
- Lawful-access clarification, 2026-06-01. Confidence: medium. Do not treat
  "available on Hugging Face" as sufficient proof of lawful access. The stronger
  Article 3 case is content accessible without login or technical circumvention
  from an apparently lawful source, such as the rightsholder/original publisher
  website, open-access repository, authorised institutional subscription, or
  official dataset host. If IXL/source educational content used by ScienceQA is
  visible on the IXL site without login or circumvention, that is treated as a
  strong lawful-access basis for Article 3 research TDM even if website terms
  purport to forbid training, because Article 7 makes contractual provisions
  contrary to Article 3 unenforceable. Third-party mirrors remain weaker unless
  there is evidence they are authorised or the same content is lawfully
  accessible from an original/public source.
- Robots.txt clarification, 2026-06-01. Confidence: medium. For Article 3
  scientific-research TDM, robots.txt is not an Article 4-style rights
  reservation mechanism and should not by itself defeat the exception. It is
  still operational evidence about whether the source is trying to constrain
  automated access and whether a collection method is respectful/non-abusive.
  For Article 4 general TDM, machine-readable reservations for public online
  content matter directly. IXL's robots.txt allows ordinary `User-agent: *`
  access to science skill pages but disallows `GPTBot`, `CCBot`, and
  `Applebot-Extended`; this supports public page access for ordinary browsing
  but not generic bot training under Article 4. The checked IXL science skill
  pages return HTTP 200 without login and describe "free questions"; their HTML
  includes an unauthenticated practice model and daily-practice-limit logic, but
  the question text itself is loaded dynamically rather than embedded in the
  static HTML. Treat IXL as publicly browsable with no login for at least some
  practice access, but verify exact ScienceQA-source question accessibility if
  we need source-by-source evidence.
- Bot-specific robots.txt interpretation, 2026-06-01. Confidence: medium. A
  robots.txt exclusion for named AI crawlers such as `GPTBot`, `CCBot`, or
  `Applebot-Extended` should be treated as strong evidence of a rights
  reservation/opt-out for Article 4 general TDM by those agents, and as an
  operational signal not to use those agents for collection. It is not the same
  as a login wall, paywall, anti-circumvention control, or global disallow for
  ordinary browsing. Current EU practice is unsettled, but the Article 3
  scientific-research exception does not contain Article 4's rights-reservation
  mechanism, and German LAION litigation commentary indicates that Article 3 may
  still apply to scientific-research TDM even where an Article 4 opt-out would
  matter for general/commercial TDM. For this project, bot-specific robots
  exclusions do not by themselves make no-login public human access unlawful,
  but they do argue against direct broad crawling with the excluded agents.
- Full-site/relevant-path robots.txt interpretation, 2026-06-01. Confidence:
  medium. If `User-agent: *` disallows the full site or the relevant source
  path, do not directly crawl that source for corpus construction. For Article 4
  this is a strong machine-readable rights reservation. For Article 3 it still
  is not an opt-out mechanism, but it weakens the lawful-automated-access case
  and should require another lawful access route such as an official dataset
  download, authorised institutional subscription, API/license, or manual/public
  inspection for verification rather than automated harvesting. A public page
  that can be viewed manually without login can still support source
  verification, but direct automated collection against a relevant
  `User-agent: *` disallow should be avoided.
- LAION TDM decision relevance, 2026-06-01. Confidence: medium. The Hamburg
  Regional Court's 2024 Kneschke v. LAION decision treated LAION's dataset
  creation as covered by Germany's Article 3 scientific-research TDM
  implementation, rather than needing Article 4. This supports the project
  distinction between Article 3 research TDM and Article 4 general/commercial
  TDM opt-outs. It is not a CJEU ruling and should not be read as a blanket
  clearance for commercial model training or unrestricted redistribution of
  source content, but it supports treating research dataset preparation as TDM
  where access is lawful and the actor qualifies for Article 3.
- Systematic inclusion/exclusion reconsideration, 2026-06-01. Confidence: high
  for local filename/filter audit, medium for legal classification. Current
  policy keeps ScienceQA and most FLAN/Tasksource benchmark, exam, translation,
  news-summarization, and reasoning files included under the Article 3 lawful
  access/TDM rationale, unless they raise non-public-person GDPR/PII risk. It
  excludes direct user/chat/social/review/opinion/spam/toxicity families such
  as Twitter/tweets, dialogs, PersonaChat, QReCC/wiki_dialog, SMS/spam,
  Amazon/Yelp/IMDb/app/book/product reviews, opinion spam, CivilComments,
  hate/offensive/toxicity, and similar Tasksource recasts. ReClor stays
  training-excluded in both Platypus and Tasksource forms by project decision;
  SciBench stays training-excluded. Superseded for harsh robots on 2026-06-01:
  News Commentary is excluded. Other news summarization files such as
  CNN/DailyMail, XSum, MultiNews, Newsroom, and Gigaword are included for now
  because the current hard filter is GDPR/PII plus harsh full-site/relevant-path
  robots cases rather than copyright licensing alone, but they should remain
  documented as Article 3-dependent sources rather than permissive-license
  sources.
- Web/chat/robots review, 2026-06-01. Confidence: high for local dataset-card,
  sample, regex, and robots.txt observations; medium for legal classification.
  Common Pile sources are accepted for DFM4 by project decision and no longer
  need source-by-source exclusion just because they are raw web-derived
  components. `synquid/wildchat-100k-qwen-messages` remains the riskiest
  current Danish chat source: the local card says it is generated Qwen answers
  to WildChat prompts, and a simple local scan of 99,688 user-prompt rows found
  65 email-like matches, 2,052 phone-number-like matches, 1,797 URL matches,
  and 4,619 rows matching address/name/contact words. Many matches are benign
  false positives, but examples include prompts about collecting name, address,
  and email for orders and prompts naming family members. Project decision:
  keep this source included, but capped tightly, and treat it as a priority
  candidate for later PII scrubbing.
  `TIGER-Lab/WebInstruct-verified` is Apache-2.0 and locally consists of
  228,736 web-sourced verifiable QA rows across math, physics, chemistry,
  business, finance, economics, history, biology, and related subjects. Its
  card explicitly says the authors traced WebInstruct data back to original web
  pages and re-crawled question-answer pairs; keep it as high-value reasoning
  data, but mark it Article-3/source-route dependent because per-row source
  URLs are not present in the local Parquet schema. `HuggingFaceH4/no_robots`
  is not a robots.txt issue despite its name: it is a 9,500-row human-annotated
  CC-BY-NC instruction dataset. The issue is that the card leaves source data,
  annotator identity, and personal/sensitive information as "More Information
  Needed"; a local regex scan found 9 email-like matches and 37 phone-like
  matches, including a prompt whose task is to redact PII. Keep it capped as a
  small human instruction source, but do not treat it as provenance-clean.
- Representative robots.txt review for FLAN news/web summarization and web
  QA/search, 2026-06-01. Confidence: high for fetched robots.txt files; medium
  for mapping many-source datasets to representative domains. Checked domains:
  CNN, Daily Mail, BBC, New York Times, Washington Post, The Guardian, Reuters,
  wikiHow, English Wikipedia, Google, Bing, `statmt.org`, and `data.statmt.org`.
  CNN, Daily Mail, BBC, New York Times, Washington Post, The Guardian, and
  wikiHow did not show full-site `User-agent: *` disallow in the fetched files,
  but most explicitly disallow named AI crawlers such as GPTBot, CCBot,
  Applebot-Extended, ClaudeBot/anthropic-ai, or similar. Under the current
  Article 3 research policy this is not by itself an exclusion, but it argues
  against direct fresh crawling with those agents. Reuters is harsher:
  `User-agent: *` disallows `/`, so Reuters-derived news content should rely on
  an official dataset/subscription/source route, not direct web crawling.
  Google and Bing do not globally disallow all ordinary crawling, but both
  disallow search endpoints (`/search` and many search-like paths), so Natural
  Questions/MS MARCO should be treated as official-dataset-route sources rather
  than something to recreate by crawling search result pages. English Wikipedia
  is comparatively clean for article-derived QA/summarization: no full-site
  `User-agent: *` disallow was observed, though API/special paths are
  restricted. `statmt.org` had no full-site disallow, but `data.statmt.org`
  disallowed `/`; WMT/news-commentary files should therefore be treated as
  official dataset downloads, not direct automated crawling from `data.statmt`.
- Harsh robots exclusion update, 2026-06-01. Confidence: high for local filter
  output. Project decision: keep `synquid/wildchat-100k-qwen-messages` capped,
  but exclude the harsh robots cases from Sapient FLAN. `source_filter.yaml`
  now denies `natural_questions_open`/`naturalquestion`, `msmarco`, `wmt`, and
  `newscomm` FLAN files. The corresponding allow overrides and DFM4 sampling
  cap entries for Natural Questions Open and WMT were removed. Rebuilding the
  filtered source tree produced `9,780` allowed files, `389` denied files, and
  `806,841,101,662` allowed bytes. Verification found zero
  `natural_questions_open`, `msmarco`, `wmt`, or `newscomm` Parquet files under
  `data/filtered_sources/sapient_cleaned/data_clustered/flan`.
- Sapient-original cap/repeat equivalence for DFM4, 2026-06-01. Confidence:
  high for config inspection. For Sapient-origin files that remain included,
  DFM4 generally keeps the original Sapient sampling rule rather than an exact
  token quota: `SYNTH` uses `max_per_file: 20_000`, FLAN CoT remains uncapped
  via the `cot_` prefix, ordinary FLAN uses `max_per_file: 5_000`,
  `dmmath`/`ampsmathematica`/`tasksource`/`openmathinstruct2`/`acereason`/
  `openthoughts2`/`sudoku_extreme` keep the original caps, and
  Sapient `Platypus` plus Sapient `no_robots` keep `repeat: 10`. The explicit
  benchmark-adjacent FLAN entries in `prefix_config_dfm4.yaml` mostly restate
  the same `5_000` per-file cap before the generic FLAN fallback; they are not
  higher than the original FLAN cap. This means retained files should have
  comparable exposure to the original under the same sampler, modulo stochastic
  sampling/boundary effects and token length distribution. Excluded files have
  zero exposure, and newly added non-Sapient DFM/DFM2/DFM3/DFM4 sources use
  their own caps/repeats and substantially increase the total epoch size.
- Non-Sapient DFM4 cap/repeat review, 2026-06-01. Confidence: high for local
  config and existing `data/show_analytics_dfm4.md`; medium for final numbers
  until DFM4 is resampled after the latest filter/config edits. Most added
  sources are reasonable, but several deserve attention. The existing analytics
  predate the latest `nemotron_multilingual__ max_per_file: 50_000` reduction;
  with 18 local converted files, the current cap should be far smaller than the
  old `8.9B` covered tokens/epoch shown in analytics and is probably reasonable.
  `laerebogen_with_followups repeat: 2` is still large at about `5.1B` covered
  tokens/epoch in the old analytics; reduce to `repeat: 1` if DFM4 should give
  more room to English factual/commonsense data. DFM2 DynaWord objectives are
  balanced as intended: prefix continuation and denoising are each about one
  unit, and span filling is about three units. DFM3 Common Pile objectives have
  the right 1:1:1:3 shape but at only about `1.5B` covered tokens/epoch per
  unit, not the original `2.8B`; increasing caps would make sense only if we
  deliberately want a larger English raw-objective share. DFM4 summarization
  and paragraph-reordering additions underfill several targets: arXiv
  summarization and DynaWord paragraph reordering are limited by generated row
  volume rather than sampler caps, while WikiCatSum could reach the intended
  ~`0.45B` covered tokens/epoch by increasing `repeat` from `2` to about `4`.
  GovReport remains tiny even with `repeat: 2` and should stay auxiliary rather
  than be repeated aggressively. Small Danish Oliver Kinch/Synquid sources with
  high repeats are mostly negligible in token share and can remain unless we
  want to reduce exact duplicate exposure for aesthetic/data-diversity reasons.
- OPUS and high-repeat inventory, 2026-06-01. Confidence: high for config and
  analytics inspection. OPUS Danish-English is small in DFM4 because
  `opus__` has `max_per_file: 200_000` and the local converted OPUS source is a
  single large file (`58,522,141` rows, `5.3G` converted Parquet). The sampler
  therefore draws only about `200k` rows/epoch, producing about `20.6M` covered
  tokens/epoch despite the source containing about `6.0B` converted tokens.
  Repeats greater than 2 in the Sapient-original portion of DFM4 are
  `sapient_cleaned__data__Platypus__ repeat: 10` and
  `sapient_cleaned__data__no_robots.jsonl repeat: 10`. Repeats greater than 2
  outside Sapient-original are: `dbc__dbc-faktalink repeat: 20`,
  `dbc__dbc-farfatterweb repeat: 20`, `lexdk__ repeat: 10`,
  `oliverkinch_instruct_bt__ repeat: 5`,
  `synquid_danish_verifiable_reasoning__ repeat: 5`,
  `synquid_ifbench_train__ repeat: 10`,
  `oliverkinch_multi_wiki_qa_high_quality__ repeat: 20`,
  `oliverkinch_eur_lex_sum_instruct__ repeat: 20`,
  `oliverkinch_dst_table_prompts_bt__ repeat: 10`,
  `oliverkinch_tidsskrift_dk_bt__ repeat: 10`,
  `oliverkinch_dynaword_bt__ repeat: 8`,
  `oliverkinch_danish_university_portals_bt__ repeat: 10`,
  `oliverkinch_danmarks_statistik_bt__ repeat: 10`,
  `oliverkinch_doab_da_bt__ repeat: 10`,
  `oliverkinch_eur_lex_bt__ repeat: 10`, and standalone
  `no_robots__ repeat: 10`.
- DFM4 non-Sapient cap update, 2026-06-01. Confidence: high for config edit;
  medium for token estimates until resampling. `data_io/prefix_config_dfm4.yaml`
  was adjusted so no repeat exceeds `10`. OPUS Danish-English was raised from
  `max_per_file: 200_000` to `10_000_000`; based on the old analytics, this
  should raise OPUS from about `20.6M` to roughly `1.0B` covered tokens/epoch if
  sampling remains close to linear. DFM3 Common Pile self-supervised caps were
  scaled to approximately match DFM2 DynaWord unit sizes with clean round caps:
  direct/prefix continuation `5_000 -> 10_000` rows/file and denoising/span-fill
  variants `2_500 -> 5_000` rows/file. This should move each Common Pile unit
  from about `1.5B` to about `3.0B` covered tokens/epoch, preserving the
  1:1:1:3 objective shape. Repeats clipped from above 10:
  `dbc__dbc-faktalink 20 -> 10`, `dbc__dbc-farfatterweb 20 -> 10`,
  `oliverkinch_multi_wiki_qa_high_quality 20 -> 10`, and
  `oliverkinch_eur_lex_sum_instruct 20 -> 10`. Repeats increased to 10:
  `oliverkinch_instruct_bt 5 -> 10`,
  `synquid_danish_verifiable_reasoning 5 -> 10`, and
  `oliverkinch_dynaword_bt 8 -> 10`.
- Paragraph-reorder scaling assessment, 2026-06-01. Confidence: high for local
  generator/config/analytics inspection; medium for impact prediction. The
  DFM4 paragraph-reorder generator is context-conservative: it trims source
  text to about half the context-char budget, requires at least three
  paragraphs, uses at most eight paragraphs, and rejects rows where the
  scrambled instruction would crowd the response. Therefore context length is
  not the main blocker. The current blocker is row volume and duplicate
  exposure. Existing analytics show DynaWord paragraph reorder at about
  `0.16B` covered tokens/epoch (`0.058X`) and Common Pile paragraph reorder at
  about `0.66B` covered tokens/epoch (`0.24X`). DynaWord has only `243,318`
  generated rows, so raising only the sampler cap can at most move it to around
  `0.08X`; reaching `0.25X` would require roughly four shuffled variants per
  eligible row, and reaching `1X` would require too many near-duplicate
  variants. Common Pile has `2,443,026` generated rows and is capped at
  `2,500` rows/file; raising the cap toward the generated maximum of `6,000`
  rows/file can grow it to roughly `0.55-0.60X` without new generation. Reaching
  `1X` would require regenerating more rows per Common Pile file and/or adding
  variants. Recommended conservative target: raise Common Pile paragraph
  reorder first; keep DynaWord paragraph reorder small unless we intentionally
  generate a small number of alternate shuffles and accept response
  duplication.
- Paragraph-window improvement idea, 2026-06-01. Confidence: high for current
  code behavior and local tokenization, medium for expected gain. Superseded:
  `generate_dfm4_tasks.py` previously trimmed text before paragraph splitting
  and then used the first up to eight paragraphs. It now splits the full
  cleaned document into paragraphs first, samples deterministic contiguous
  paragraph windows that fit the reconstruction budget, and shuffles each
  window. The current DFM4 sample uses regenerated DynaWord paragraph-window
  tasks plus the existing complete Common Pile paragraph tokenization. A full
  Common Pile paragraph-window regeneration was started but stopped because it
  became slow on large shards; do not treat the partially regenerated Common
  Pile converted tree as complete.

Remaining excluded Sapient original clusters after the DFM4 filter expansion,
measured by original Sapient sampled exposure across four epochs:

| Cluster | Original sampled tokens | Benchmark value | Problem level | Covered elsewhere |
|---|---:|---|---|---|
| Miscellaneous FLAN/NIV2 task soup | `13.47B` | Medium: broad instruction following and task format diversity | Medium/high: broad aggregator, mixed provenance, many tiny/generated task transforms | Partly by Tulu, Dolci, Nemotron instruction, DFM raw-objective tasks |
| Translation/multilingual | `2.15B` | Low/medium for English evals; useful for translation/multilingual | Medium: many WMT/multilingual components with varied provenance; WMT/news-commentary now excluded for harsh robots | Mostly by OPUS, Synquid/Oliver Kinch translation, Nemotron multilingual |
| Classification/sentiment/toxicity | `1.18B` | Low for MMLU/ARC/DROP; some general classification skill | Medium/high: reviews/social/toxicity datasets can have PII and web provenance | Partly by Tulu/Dolci/general instruction |
| Conversational QA/RC left out, e.g. CoQA/QuAC/MSMARCO/ROPES | `1.01B` | Medium/high for reading comprehension, lower direct eval overlap than DROP/SQuAD/NQ | Medium/high: web/dialog sources and some ambiguous provenance; MS MARCO and NQ now excluded for harsh robots | Partly by SQuAD/DROP/CoQA/QuAC/ROPES plus Common Pile objectives |
| Paraphrase/grammar/generation | `0.96B` | Low/medium; helps linguistic robustness | Low/medium to medium depending source; less core to target evals | Partly by Tulu/Dolci and direct instruction data |
| NLI/GLUE/SuperGLUE still excluded, mostly SNLI/eSNLI and residual tasks | `0.69B` | Medium for entailment/reading robustness | Medium: benchmark-adjacent and mixed upstream licenses | Partly by admitted ANLI/MNLI/RTE/SuperGLUE plus Tasksource NLI |
| News/web summarization | `0.67B` | Medium for summarization, low for MMLU/ARC | High: copyrighted news/web summarization risk | Covered by DFM4 LAION/arXiv/GovReport/WikiCatSum and DBC summaries |
| Commonsense/story residual, e.g. CREAK/ECQA/SenseMaking/Social/Cosmos | `0.56B` | Medium/high for HellaSwag/Winogrande/common sense | Medium: benchmark-adjacent, some web/social/story provenance | Partly by admitted HellaSwag/Winogrande/COPA/PIQA/StoryCloze/QASC |
| Platypus denied: ReClor, SciBench, ScienceQA, and Tasksource ReClor | `0.30B` | Medium for reasoning/science | High: textbook/web/exam/source-rights concerns and benchmark contamination | Partly by ARC/OpenBookQA/SciQ/QASC, science summaries, reasoning data |
| Dialog/chat residual | `0.29B` | Low/medium; chat robustness, not core evals | Medium/high: dialogue/web provenance and possible PII | Covered by Tulu/Dolci/Nemotron agentic and approved chat data |
| Tasksource residual eval-adjacent | `0.07B` | Low/medium | Medium: recast/mixed provenance | Partly by admitted Tasksource NLI/logic/medical/science |
- `nemotron_agentic` currently has `max_per_file: 800k`, but DFM3 analytics
  show about `1.4B` exposure tokens per epoch, much smaller than
  `nemotron_multilingual`; lower it only if truncation/long-history analytics
  show poor response retention.
- `allenai_tulu_v2_sft_long_mixture` currently has `max_per_file: 1.5M`, but
  the actual DFM3 exposure was only about `0.6B` tokens per epoch because the
  local file has about `532k` rows. It is not currently a large token-share
  problem, but it remains a long-context/truncation-risk source.
- Consider lowering `allenai_tulu_v2_sft_long_mixture`,
  `nemotron_agentic`, and `nemotron_swe` or marking them `long_context: drop`
  after adding truncation analytics, because they are prompt/history-heavy and
  are likely to suffer response truncation.
- Keep small high-value Danish tasks repeated, but avoid further increasing
  `synquid_danish_verifiable_reasoning`, `synquid_wiki_instruct_da`,
  `oliverkinch_*_bt`, and DBC repeats until DFM4 analytics show the new
  English summarization/reordering additions have not diluted Danish too much.

Selected Common Pile sources added to the downloader manifest under group
`common_pile`:

- `common-pile/wikimedia_filtered`
- `common-pile/wikiteam_filtered`
- `common-pile/stackexchange_filtered`
- `common-pile/pubmed_filtered`
- `common-pile/arxiv_abstracts_filtered`
- `common-pile/arxiv_papers_filtered`
- `common-pile/usgpo_filtered`
- `common-pile/regulations_filtered`
- `common-pile/uspto_filtered`
- `common-pile/project_gutenberg_filtered`
- `common-pile/public_domain_review_filtered`
- `common-pile/library_of_congress`

Local dry-run inventory on 2026-05-31:

```text
Selected Common Pile bytes: 275.1 GB
Selected files: 480
```

The largest selected components are `common_pile_uspto_filtered` (`137.9 GB`),
`common_pile_pubmed_filtered` (`40.6 GB`),
`common_pile_stackexchange_filtered` (`32.5 GB`),
`common_pile_wikimedia_filtered` (`20.1 GB`), and
`common_pile_library_of_congress` (`16.8 GB`).

Implemented local paths:

- Downloader manifest: `scripts/download_training_datasets.py`
- Common Pile raw-text conversion: `scripts/convert_filtered_sources.py`
- Generator: `scripts/generate_dfm3_common_pile_tasks.py`
- Tokenized union builder: `scripts/build_tokenized_dfm3_tree.py`
- Sampling config: `data_io/prefix_config_dfm3.yaml`
- Training data config: `config/data/dfm3.yaml`
- Stage script: `scripts/prepare_dfm3_english_recovery.sh`

The DFM3 sampling config raises the approved English/multilingual instruction
caps for `nemotron_*`, `dolci_*`, `allenai_tulu_*`,
`allenai_big_reasoning_traces`, `allenai_if_*`, `allenai_verifiable_*`, and
other already approved English reasoning/instruction families. Based on DFM2
analytics, fully uncapping the already present approved English-ish families
can add roughly `12.9B` covered tokens per epoch; the new config also includes
approved-but-not-yet-sampled manifest entries such as `natural_reasoning`,
`principia_collection`, `textbook_reasoning`, `webinstruct_verified`,
`allenai_code_meta_reasoning`, and `allenai_rlvr_ifeval` so the sampled
addition can approach the requested `14B` after download/conversion.

## Original Plus Mixed Danish Instruction Rich

Verified locally on 2026-05-24 from:

- `data/show_analytics_original_sapient.md`
- `data/show_analytics_original_plus_mixed_danish_instruction_rich.md`
- `data/tokenized_original_plus_mixed/union_manifest.json`

The `original_plus_mixed_danish_instruction_rich` sample preserves the original Sapient portion almost exactly, then adds mixed/Danish sources on top.

Source union facts:

- `data/tokenized_original_plus_mixed/union_manifest.json` records `original_tasks: 5212`.
- All `5212` original Sapient tokenized tasks are present in the original+mixed union.
- `mixed_tasks_added: 226`.
- `include_mixed_sapient: false`, so duplicate Sapient tasks from the mixed tree are skipped rather than added twice.

Covered-token comparison across 4 epochs:

| Sample | Original Sapient covered tokens | Global covered tokens |
|---|---:|---:|
| `sampled_original_sapient` | `56,140,714,711` | `56,140,714,711` |
| `sampled_original_plus_mixed_danish_instruction_rich` | `56,140,181,363` | `110,736,199,356` |

Difference in the original Sapient portion: `-533,348` tokens, about `0.00095%`. This is consistent with sampling/shuffling boundary effects, not intentional reweighting of the original subset.

Per-category ratios for original Sapient categories in `original_plus_mixed_danish_instruction_rich` versus `original_sapient`:

| Category | Ratio |
|---|---:|
| `Platypus` | `1.000000` |
| `SYNTH` | `1.000000` |
| `acereason` | `0.999996` |
| `ampsmathematica` | `0.999924` |
| `dmmath` | `0.999944` |
| `flan` | `0.999960` |
| `openmathinstruct2` | `1.000217` |
| `openthoughts2` | `0.999905` |
| `sudoku_extreme` | `1.000000` |
| `tasksource` | `0.999956` |
| `textbookreasoning` | `1.000000` |

Task/file-level comparison:

- Matching original tasks: `5212 / 5212`
- Missing original tasks: `0`
- Exact same covered-token count: `2645 / 5212`
- Within `10,000` tokens: `4738 / 5212`
- Within `100,000` tokens: `5193 / 5212`
- Largest observed task difference: `openmathinstruct2__cot.parquet`, about `+902,328` covered tokens, ratio `1.000279`.

Conclusion: use `original_plus_mixed_danish_instruction_rich` when the goal is to keep the original Sapient training signal essentially unchanged while adding roughly `54.6B` extra covered tokens over 4 epochs from the mixed/Danish additions.

Confidence: high.

## DFM5 Danish Token Accounting

Added on 2026-06-17. Confidence: high for local analytics parsing and token
counts from `data/show_analytics_dfm5.md`.

For the current DFM5 sample, `data/show_analytics_dfm5.md` reports
`128,605,312,816` total unique candidate tokens and `178,029,895,476` covered
tokens across 5 epochs, i.e. about `35.606B` tokens per epoch.

Strictly Danish monolingual/reference-style sources have about
`5,232,200,438` unique candidate tokens:

- Danish DynaWord export objectives: `300,492,627`
- Danish instruction/reference sources (`dbc`, `laerebogen`, `lexdk`,
  `oliverkinch_*` Danish BT/reference/instruction, `synquid_*` Danish
  instruction tasks): `4,727,840,172`
- `transformations-danish-danish`: `203,867,639`

Danish-involved sources, including cross-lingual Danish translation and
transformation tasks but excluding the maybe-multilingual
`synquid_wildchat_100k_qwen_messages`, have about `15,282,372,741` unique
candidate tokens. Including that maybe-multilingual WildChat slice gives about
`15,502,966,407` unique candidate tokens.

Current DFM5 per-epoch sampled exposure is lower because of caps/repeats:

- strict Danish monolingual/reference-style: about `4,368,304,924`
  tokens/epoch;
- Danish-involved including cross-lingual, excluding maybe-multilingual
  WildChat: about `6,448,926,031` tokens/epoch;
- Danish-involved including maybe-multilingual WildChat: about
  `6,534,845,485` tokens/epoch.

Clarification added on 2026-06-17. Confidence: high. The DFM5-linked Danish
available-token pool should be read from `data/show_analytics_dfm5.md`, not by
blindly scanning every Danish-looking directory under `data/tokenized_mixed`,
because that root still contains legacy `danish_dynaword__...` files that are
not linked into DFM5. The DFM5-linked source clusters are:

| Cluster | Files | Available tokens |
|---|---:|---:|
| OPUS Danish-English translation | `1` | `6,037,616,160` |
| Oliver Kinch Danish translation | `4` | `3,541,450,520` |
| Laerebogen with follow-ups | `7` | `2,563,212,663` |
| DBC articles/reviews | `24` | `1,800,302,760` |
| Synthetic transformations Danish-English / English-Danish | `659` | `355,640,602` |
| Danish DynaWord synthetic objectives | `475` | `300,492,627` |
| Synquid WildChat Qwen messages (maybe multilingual) | `1` | `220,593,666` |
| Synthetic transformations Danish-Danish | `250` | `203,867,639` |
| Synquid Danish instruction/reasoning | `4` | `202,263,632` |
| Synquid Danish translation/MT | `2` | `115,465,021` |
| Oliver Kinch Danish BT/reference/instruction | `10` | `88,741,738` |
| LexDK encyclopedic articles | `1` | `73,319,379` |

## Expert Export Upload Packaging

Added on 2026-06-17. Confidence: high for local file layout and validation.

The `export/` folders mix original generated data, judge-filtered data, and
historical audit run directories. For HF-style upload, create clean copies
under `export-upload/` rather than uploading `export/` directly.

For audited datasets such as `common-pile-denoising`, the upload payload should
use only the accepted rows from:

```text
export/<dataset>/audited/data/
```

as the top-level:

```text
export-upload/<dataset>/data/
```

The original unfiltered `export/<dataset>/data/` and historical
`audit_*` folders are local provenance/intermediate artifacts and should not be
part of the normal training-data upload. The full audit JSONL is not a clean
per-row annotation for the filtered upload files because its stable row IDs
point to original unfiltered coordinates such as
`common-pile-denoising/train-xxxxx.jsonl.gz:<line>`. A compact
`audit_summary.json` is more appropriate in the upload copy unless we also
publish the unfiltered data or embed provenance IDs in each filtered row.

First clean upload copy created:

```text
export-upload/common-pile-denoising/
  README.md
  recreate_dataset.py
  audit_summary.json
  data/train-*.jsonl.gz
```

Local validation:

- copied with `cp --reflink=never`; no symlinks;
- sampled source/upload files have different inodes and `nlink=1`;
- `477` data shards;
- `254,565` uploaded accepted rows;
- Superseded detail: `audit_full/audit.jsonl` alone has `62,603` audited rows,
  `61,786` keep, and `817` drop. This is only one audit component and should
  not be described as the final filtering audit.

Follow-up on 2026-06-17. Confidence: high for local file inspection and
validation commands. The clean upload copy is:

```text
export-upload/common-pile-denoising/
```

It is named with the Common Pile export family even though its accepted rows
currently come only from Common Pile's arXiv abstract/paper families. The
upload copy contains `254,565` accepted rows across `7` non-empty
`data/train-*.jsonl.gz` shards. Its `recreate_dataset.py` is now denoise-only:
the previous reusable prefix-continuation/span-filling/paragraph-reordering
generation and judge-audit branches were removed, and the CLI no longer exposes
an objective selector. Local validation passed with:

```bash
python -m py_compile export-upload/common-pile-denoising/recreate_dataset.py
python export-upload/common-pile-denoising/recreate_dataset.py --help
python export-upload/common-pile-denoising/recreate_dataset.py audit --help
```

The same packaging strategy was applied to:

```text
export-upload/danish-dynaword-denoising/
```

Confidence: high for local file inspection and validation commands. This
upload copy contains only the accepted judge-audited Danish DynaWord denoising
rows from `export/danish-dynaword-denoising/audited/data/`. The original
generated export had `1,854,932` rows across `90` gzip files. The audit covered
`69,907` rows, accepted `65,518`, and rejected `4,389`; the remaining generated
rows are not included because they had no explicit accepted audit decision. The
clean upload keeps only the four non-empty accepted shards:

```text
data/train-00000.jsonl.gz
data/train-00001.jsonl.gz
data/train-00002.jsonl.gz
data/train-00003.jsonl.gz
```

The `recreate_dataset.py` in this upload copy is Danish denoise-only, defaults
to `--language da`, and uses the prompt style `Gendan den oprindelige tekst.`.
Local validation passed with:

```bash
python -m py_compile export-upload/danish-dynaword-denoising/recreate_dataset.py
python export-upload/danish-dynaword-denoising/recreate_dataset.py --help
python export-upload/danish-dynaword-denoising/recreate_dataset.py audit --help
python -m json.tool export-upload/danish-dynaword-denoising/audit_summary.json
```

Follow-up on 2026-06-17. Confidence: high for local shard/source-order
inspection. The accepted rows in `export-upload/danish-dynaword-denoising` come
only from the first four generated shards, which map to the first four Parquet
files in sorted DynaWord source order:

| Generated shard | Source Parquet | Accepted rows |
|---|---|---:|
| `train-00000.jsonl.gz` | `data/adl/adl.parquet` | `28,730` |
| `train-00001.jsonl.gz` | `data/ai-aktindsigt/ai-aktindsigt.parquet` | `29,011` |
| `train-00002.jsonl.gz` | `data/botxt/botxt.parquet` | `524` |
| `train-00003.jsonl.gz` | `data/cellar/cellar.parquet` | `7,253` |

The original generated shards `train-00004` and later have no accepted rows in
the clean upload package. The generator was capped at about `30,000` generated
rows per source shard; the audit/filter output then kept only accepted row ids.

Follow-up on 2026-06-17. Confidence: high. The
`export-upload/danish-dynaword-denoising/README.md` structure and
`audit_summary.json` core fields were aligned with
`export-upload/common-pile-denoising/`: same Contents/Sources/Example/Filtering/Recreate
section pattern, same `format: "chat messages"` value, same `task:
"denoising"` value, and the same audit count field layout. The only extra JSON
field retained for Danish is `accepted_rows_by_source_file`, because the upload
is materially limited to four effective source Parquet files.

Follow-up on 2026-06-17. Confidence: high for local audit JSONL parsing,
accepted-data row counts, and validation commands. The same clean upload
packaging strategy was applied to the remaining paragraph-reordering,
span-filling, and prefix-continuation exports:

| Upload dataset | Files | Uploaded rows | Audited rows | Rejected rows | Effective source families |
|---|---:|---:|---:|---:|---|
| `export-upload/common-pile-prefix-continuation` | `19` | `619,911` | `740,695` | `120,784` | `common-pile/arxiv_abstracts_filtered`, `common-pile/arxiv_papers_filtered`, `common-pile/library_of_congress` |
| `export-upload/common-pile-span-filling` | `7` | `253,715` | `279,201` | `25,486` | `common-pile/arxiv_abstracts_filtered`, `common-pile/arxiv_papers_filtered` |
| `export-upload/common-pile-paragraph-reordering` | `16` | `86,328` | `182,122` | `95,794` | `common-pile/arxiv_papers_filtered`, `common-pile/project_gutenberg_filtered` |
| `export-upload/danish-dynaword-prefix-continuation` | `2` | `105,317` | `110,396` | `5,079` | `danish-foundation-models/danish-dynaword` |
| `export-upload/danish-dynaword-span-filling` | `2` | `54,968` | `56,315` | `1,347` | `danish-foundation-models/danish-dynaword` |
| `export-upload/danish-dynaword-paragraph-reordering` | `3` | `55,340` | `211,870` | `156,530` | `danish-foundation-models/danish-dynaword` |

For each folder, only non-empty accepted shards from `export/<dataset>/audited/data`
were copied to `export-upload/<dataset>/data`. Each folder has an aligned
`README.md`, `audit_summary.json`, and `recreate_dataset.py`; validation passed
with `python -m json.tool`, `python -m py_compile`, `recreate_dataset.py
--help`, `recreate_dataset.py audit --help`, and accepted-row recounts matching
`audit_summary.json`.

Correction/update on 2026-06-17. Confidence: high. The clean upload README and
`audit_summary.json` for `export-upload/common-pile-denoising` now include the
HF judge model ID and the de-duplicated all-audit rejection breakdown. The
audit model is recorded as `google/gemma-4-31B-it`, served locally under the
OpenAI-compatible vLLM alias `posttrain-gemma-teacher`. The upload filter used
`11` audit JSONL files. After de-duplicating by stable original row id, the
combined audit records:

| Audit outcome | Rows |
|---|---:|
| audited | `267,479` |
| accepted/uploaded | `254,565` |
| rejected by audit | `12,914` |

The original unfiltered export had `19,043,379` rows; `18,788,814` rows are not
included in the upload because the clean upload contains only the audited
`keep=true` set. That excluded count is not equivalent to judged-bad rows; it
also includes rows outside the selected audited keep set.

Rejected rows by primary failure type:

| Failure type | Rows |
|---|---:|
| `low_value_trivial` | `5,873` |
| `incoherent_or_ocr` | `3,158` |
| `response_mismatch` | `2,969` |
| `url_or_reference_dump` | `671` |
| `task_not_meaningful` | `75` |
| `other` | `64` |
| `metadata_boilerplate` | `62` |
| `empty_or_too_short` | `22` |
| `wrong_language` | `20` |

Name/content update on 2026-06-17. Confidence: high. The accepted
`common-pile-denoising` upload subset maps entirely to Common Pile arXiv
abstracts/papers (`79,101` accepted abstract rows and `175,464` accepted paper
rows). The clean upload package is:

```text
export-upload/common-pile-denoising/
```

Its README is intentionally short and upload-focused. The machine-readable
`audit_summary.json` records `dataset: common-pile-denoising`; the README notes
that the accepted rows currently come from Common Pile arXiv abstract/paper
sources.
The filtered folder originally contained one gzip shard per original source
file, including `470` empty gzip shards. Those empty shards were removed from
the clean upload copy, leaving `7` non-empty `data/train-*.jsonl.gz` files with
`254,565` rows.

Upload-card review on 2026-06-17. Confidence: high from local validation. All
12 current `export-upload/*` folders were reviewed for user-facing correctness,
relevance, and concision. README files were regenerated into a consistent
short structure covering contents, actual accepted sources, filtering counts,
one example, and recreation commands. Transformation dataset cards now describe
actual exported source clusters reconstructed from generation metadata rather
than the broader seed inventory. `audit_summary.json` for the four
transformation exports now also records those actual source clusters in
`accepted_rows_by_source_family` and `source_datasets`. Recreate script help
text was checked and missing top-level descriptions were added for the
paragraph-reordering, span-filling, and prefix-continuation scripts. Validation
passed for JSON parsing, Python compilation, `--help`, row/schema recounts,
and no symlinks or `__pycache__` directories remain under `export-upload/`.

HF upload attempt on 2026-06-17. Confidence: high from local API output. Upload
to `schneiderkamplab/*` was attempted with the Hugging Face API, using each
`export-upload/<name>` folder as one dataset repo. The first repo creation
failed before any data transfer:

```text
403 Forbidden: no rights to create a dataset under namespace schneiderkamplab
```

The token identified a user that belongs to the `schneiderkamplab` org, and
the target dataset repos did not already exist. The likely blocker is missing
org role/permission or token write scope for dataset repo creation. No token was
written to disk or the wiki. Local log:

```text
logs/hf_export_upload_20260617.log
```

Reusable uploader added:

```bash
cd /work/dfm/HRM-Text
HF_TOKEN=... python scripts/upload_export_upload_to_hf.py \
  --org schneiderkamplab \
  --root export-upload
```

Retry on 2026-06-17 with the explicitly provided token failed at the same
first `create_repo` call with the same 403. No files were uploaded. The uploader
now also supports `--skip-create` for the case where the 12 dataset repos are
created manually in the org first:

```bash
HF_TOKEN=... python scripts/upload_export_upload_to_hf.py \
  --org schneiderkamplab \
  --root export-upload \
  --skip-create
```

Superseding update on 2026-06-17. Confidence: high from successful local
Hugging Face API upload and `repo_info` visibility checks. The 12 original
`export-upload/*` dataset folders were uploaded to public dataset repos under
`schneiderkamplab`. `repo_info` reported `private=False` for all 12 repos. The
write-capable token was passed through `HF_TOKEN`; no token was written to disk
or the wiki. Upload log:

```text
logs/hf_export_upload_20260617.log
```

Synthetic Sapient-exclusion upload preparation, 2026-06-17. Confidence: high
from local script output and validation. The 70 accepted synthetic replacement
datasets from `export-synth/` were copied into direct `export-upload/` children
for later HF upload:

```text
export-upload/sapient-synth-high40-*
export-upload/sapient-synth-repeat30-*
export-upload/sapient-synth-upload-manifest.json
```

The copy was created with:

```bash
cd /work/dfm/HRM-Text
python scripts/prepare_export_synth_upload.py --force
```

Validation results:

- `70` upload dataset folders: `40` high40 and `30` repeat30.
- `254,247` accepted chat-format rows.
- No symlinks in the copied folders.
- All `70` copied `recreate_dataset.py` scripts compiled and validated their
  local `data/train-*.jsonl.gz` files.
- Six overlong source-derived names were shortened in the upload repo folder
  names to satisfy the Hugging Face 96-character repo-id limit; the manifest
  retains each original `dataset_id` and `original_task_name`.

Export packaging update, 2026-06-17. Confidence: high from local validation.
The synthetic upload folders now join all per-dataset shards into one file:

```text
export-upload/sapient-synth-*/data/train.jsonl.gz
```

There are exactly `70` such files, one per synthetic dataset. The upload repo
folder names no longer include the internal `high40`/`repeat30` campaign names;
that campaign group is retained only in metadata. The README structure now
matches the earlier 12 upload datasets more closely: HF YAML front matter,
Contents, Generation, License, and Recreate. The synthetic README text uses
`anonymous`, not `anonymized`, says `PII absence`, and describes overlap
precautions as creating new synthetic examples that preserve task type/skill,
not rewrites or copies of provenance rows. Each folder also contains
`LICENSE.md`, `metadata/manifest.json`, `metadata/summary.json`, and a
self-contained `recreate_dataset.py` that rebuilds/validates the single-file
layout. The license note states that the datasets that inspired these
recreations may have different licensing conditions, while the included rows
are fully synthetic recreations with no or minimal wording overlap and judged
to be free of PII. Validation after this change: all `70` recreate scripts
passed and recounted `254,247` rows.

The 12 earlier `common-pile-*`, `danish-dynaword-*`, and `transformations-*`
upload datasets were also updated to use Apache-2.0 HF front matter and
`LICENSE.md`. Their README bodies were otherwise left unchanged; no synthetic
provenance caveat was added to those 12.

The uploader now supports `--include-glob`, so these synthetic datasets can be
uploaded without re-uploading the earlier 12 datasets:

```bash
cd /work/dfm/HRM-Text
HF_TOKEN=... python scripts/upload_export_upload_to_hf.py \
  --org schneiderkamplab \
  --root export-upload \
  --include-glob 'sapient-synth-*' \
  --log logs/hf_export_upload_sapient_synth_20260617.log
```

## DFM5 GSM8k Lag Source Audit

Last updated: 2026-06-15
Confidence: high for local audit files and analytics rows; medium for causal
interpretation.
Scope: Original Sapient sources omitted from DFM5 and their likely relevance
to GSM8k-style performance.

The local omitted-task audit shows `321` original Sapient tasks excluded from
DFM5, with `1,407,414,834` original covered tokens over four epochs
(`351,853,709` tokens/epoch). A keyword scan for explicit math/science/logic
terms among omitted tasks found only `91,628,200` original covered tokens over
four epochs (`22,907,050` tokens/epoch), dominated by ReClor, SciBench, and
TweetQA-like tasks rather than GSM8k-style arithmetic:

```text
Platypus__reclor.jsonl                         47,467,200 covered tokens
tasksource__reclor.parquet                      4,693,360 covered tokens
Platypus__scibench.jsonl                        5,165,960 covered tokens
TweetQA/QReCC/MS MARCO-style QA residuals       remaining matched tokens
```

The obvious original Sapient GSM8k/math/science families are not omitted:
`gsm8k`, `mathqa`, `aqua`, `openbookqa`, `qasc`, `sciq`, `strategyqa`, and
`quartz` are allow-overridden and present in `data/show_analytics_dfm5.md`.
A keyword comparison of those included families gives about the same exposure
per epoch in original Sapient and DFM5:

```text
original Sapient keyword set: 736,505,857 covered tokens / 4 epochs
DFM5 keyword set:             920,611,503 covered tokens / 5 epochs
both are about 184M tokens/epoch
```

Therefore, the current best explanation for DFM5-L's early GSM8k lag is not a
missing direct GSM8k/math source from the original mix. More plausible causes
are dilution by the much larger DFM5 epoch, loss of high-leverage non-math
instruction/formatting effects, differences in EMA/checkpoint dynamics, or the
need for more GSM8k-like elementary arithmetic post-training.

## DFM4 Danish Source Breakdown

Last updated: 2026-06-12
Confidence: high
Scope: DFM4 sampled data analytics from `data/show_analytics_dfm4.md`.

`data/show_analytics_dfm4.md` reports `360,035,447,845` covered tokens across
five sampled epochs, or `72,007,089,569` tokens per epoch. Danish-specific
sources in DFM4 account for about `134,864,875,503` covered tokens across five
epochs, or `26,972,975,101` tokens per epoch (`37.46%` of DFM4).

Category totals:

| Category | Tokens/epoch | Five-epoch covered tokens | Share of DFM4 |
|---|---:|---:|---:|
| DynaWord self-supervised tasks | `14.063B` | `70.317B` | `19.53%` |
| Danish instruction/reference/chat | `6.842B` | `34.210B` | `9.50%` |
| Raw Danish continuation | `2.814B` | `14.070B` | `3.91%` |
| Translation | `1.725B` | `8.625B` | `2.40%` |
| Oliver Kinch Danish BT/instruction/reference | `0.887B` | `4.437B` | `1.23%` |
| DynaWord paragraph reordering | `0.641B` | `3.205B` | `0.89%` |

Largest individual Danish sources/tasks by per-epoch tokens:

| Source/task | Category | Tokens/epoch |
|---|---|---:|
| `laerebogen_with_followups` | Danish instruction/reference/chat | `5.126B` |
| `danish_dynaword` | Raw Danish continuation | `2.814B` |
| `dfm2_dynaword_denoising` / `v2` | DynaWord self-supervised tasks | `1.457B` each |
| `dfm2_dynaword_span_fill_v1..v6` | DynaWord self-supervised tasks | about `1.418B` each |
| `dfm2_dynaword_prefix_continuation` / `v2` | DynaWord self-supervised tasks | `1.320B` each |
| `opus` | Translation | `1.032B` |
| `lexdk` | Danish instruction/reference/chat | `0.733B` |
| `dfm4_dynaword_paragraph_reorder` | DynaWord paragraph reordering | `0.641B` |
| `oliverkinch_tidsskrift_dk_bt` | Oliver Kinch Danish BT/instruction/reference | `0.482B` |
| `dbc` | Danish instruction/reference/chat | `0.405B` |
| `synquid_wiki_instruct_da` | Danish instruction/reference/chat | `0.383B` |
| `oliverkinch_machine_translation_da_en` | Translation | `0.315B` |
| `oliverkinch_dynaword_bt` | Oliver Kinch Danish BT/instruction/reference | `0.212B` |
| `oliverkinch_machine_translation_da_ar` | Translation | `0.162B` |
| `synquid_translation_100k` | Translation | `0.108B` |
| `oliverkinch_machine_translation_da_uk` | Translation | `0.101B` |
| `synquid_danish_verifiable_reasoning` | Danish instruction/reference/chat | `0.093B` |
| `synquid_wildchat_100k_qwen_messages` | Danish instruction/reference/chat | `0.086B` |
| `oliverkinch_dst_table_prompts_bt` | Oliver Kinch Danish BT/instruction/reference | `0.055B` |
| `oliverkinch_multi_wiki_qa_high_quality` | Oliver Kinch Danish BT/instruction/reference | `0.048B` |
| `oliverkinch_danish_university_portals_bt` | Oliver Kinch Danish BT/instruction/reference | `0.027B` |
| `oliverkinch_danmarks_statistik_bt` | Oliver Kinch Danish BT/instruction/reference | `0.023B` |
| `oliverkinch_eur_lex_bt` | Oliver Kinch Danish BT/instruction/reference | `0.020B` |
| `oliverkinch_instruct_bt` | Oliver Kinch Danish BT/instruction/reference | `0.017B` |
| `synquid_ifbench_train` | Danish instruction/reference/chat | `0.015B` |
| `synquid_mt_da_deepseek` | Translation | `0.007B` |
| `oliverkinch_eur_lex_sum_instruct` | Oliver Kinch Danish BT/instruction/reference | `0.002B` |
| `oliverkinch_doab_da_bt` | Oliver Kinch Danish BT/instruction/reference | `0.001B` |

## Kept Sapient Original Sampling Exposure

Last updated: 2026-06-12
Confidence: high
Scope: Current filtered Sapient source tree after the DFM5 policy update,
measured against `data/show_analytics_original_sapient.md` at the original
Sapient sampling rate.

The current filtered tree under `data/filtered_sources/sapient_cleaned`
contains `4,892` symlinks, of which one is `README.md`. The remaining `4,891`
data files match original Sapient task names in
`data/show_analytics_original_sapient.md`; `321` original analytics tasks are
not kept by the current source filter.

At the original Sapient sampling rate:

| Subset | Covered tokens over 4 epochs | Tokens/epoch |
|---|---:|---:|
| Full original Sapient | `56,140,714,711` | `14,035,178,678` |
| Current kept Sapient subset | `54,733,299,877` | `13,683,324,969` |
| Currently excluded `321` tasks | `1,407,414,834` | `351,853,709` |

The kept subset preserves about `97.49%` of the original Sapient sampled-token
exposure. The excluded `321` tasks account for about `2.51%` of the original
sampled-token exposure, despite being large in raw bytes, because many broad
FLAN/tasksource files were capped by the original prefix config.

Update, 2026-06-12. Confidence: high. The concrete DFM5 exclusion lists were
materialized locally from `data/show_analytics_original_sapient.md` minus the
current symlink-derived task set in `data/filtered_sources/sapient_cleaned`:

```text
logs/data_audits/dfm5_excluded_original_sapient_tasks.tsv
logs/data_audits/dfm5_excluded_original_sapient_sources.tsv
logs/data_audits/dfm5_excluded_original_sapient_tasks.summary.json
```

The `321` excluded original Sapient tasks break down as `298` FLAN tasks, `21`
Tasksource tasks, and `2` Platypus tasks. By broad policy reason/name pattern:
`46` are translation/news/search, `160` are reviews/opinions/email, `102` are
social/toxicity/PII-risk, `20` are dialogue/chat/user-conversation, and `3`
are eval/book/textbook-risk. These buckets are explanatory groupings; the
source of truth is the TSV list.

## DFM5 Danish Include Set

Last updated: 2026-06-12
Confidence: high
Scope: DFM5 policy/config decision implemented locally in
`data_io/prefix_config_dfm5.yaml`, `config/data/dfm5.yaml`, and
`scripts/build_tokenized_dfm5_tree.py`.

DFM5 keeps the current source-filtered Sapient subset at original Sapient task
names and original Sapient sampling rates, then adds the following Danish
families:

- `laerebogen_with_followups`
- `lexdk`
- `opus`
- all currently tokenized `oliverkinch_*` datasets, including translation
  datasets because the decision was phrased as `oliverkinch_*`
- all currently tokenized `synquid*` datasets, including translation and
  WildChat-Qwen messages because the decision was phrased as `synquid*`
- local `dbc` converted instruction/reference datasets
- exported Danish DynaWord task datasets:
  `export/danish-dynaword-denoising`,
  `export/danish-dynaword-paragraph-reordering`,
  `export/danish-dynaword-prefix-continuation`, and
  `export/danish-dynaword-span-filling`

DFM5 intentionally does not link the older raw `danish_dynaword__`,
`dfm2_dynaword_*`, or `dfm4_dynaword_paragraph_reorder__` tokenized tasks. The
four exported DynaWord task datasets supersede the older internal DynaWord task
trees for this mix. Update, 2026-06-12: `lexdk__` and `opus__` are now included
explicitly after user approval.

## DFM5 Non-Danish And Export Additions

Last updated: 2026-06-12
Confidence: high for implemented config/tree-builder changes; medium for token
targets until `data/show_analytics_dfm5.md` is generated.
Scope: DFM5 policy/config decision implemented locally in
`data_io/prefix_config_dfm5.yaml` and `scripts/build_tokenized_dfm5_tree.py`.

DFM5 also includes:

- Reduced Nemotron SFT: `nemotron_multilingual__`, `nemotron_swe__`,
  `nemotron_agentic__`, and `nemotron_instruction_reasoning_off__`, capped to
  target about `3.1B` tokens per epoch instead of the larger DFM4 exposure.
- DOLCI SFT at the DFM4 rate: `dolci_instruct_sft__`,
  `dolci_instruct_sft_no_tools__`, `dolci_instruct_sft_tool_use__`, and
  `dolci_instruct_sft_tool_use_sa__`.
- Reduced AllenAI/Tulu/reasoning/math/science plus extra `no_robots__`, capped
  to target about `3.1B` tokens per epoch for that family.
- DFM4 summarization tasks from `data/tokenized_dfm4_summarization`:
  `dfm4_arxiv_paper_summarization__`, `dfm4_govreport_summarization__`,
  `dfm4_wiki_cat_sum_summarization__`, and
  `dfm4_laion_scientific_summaries__`.
- Accepted-only export datasets from Common Pile and Danish DynaWord raw-task
  exports, plus accepted transformation exports:
  `common-pile-{denoising,paragraph-reordering,prefix-continuation,span-filling}`,
  `danish-dynaword-{denoising,paragraph-reordering,prefix-continuation,span-filling}`,
  and `transformations-{danish-danish,danish-english,english-danish,english-english}`.

The tokenized DFM5 tree builder was rebuilt on 2026-06-12 after export
tokenization and linked `4,891` kept Sapient tasks, `54` selected Danish mixed
tasks, `139` Nemotron/DOLCI/AllenAI/no_robots tasks, `4,019` DFM4
summarization tasks, and `4,187` accepted export tasks, with no missing kept
Sapient tasks. Total linked task dirs: `13,290`.

DFM5 sampling completed on 2026-06-12 with `epochs=5` and
`concat_workers=1`. Confidence: high. Outputs:

```text
sampled dataset: data/sampled_dfm5
analytics:       data/show_analytics_dfm5.md
stderr log:      logs/sample_dfm5.stderr.log
metadata.total_length: 39,298,245,221 tokens per epoch
```

Final high-level DFM5 sampled distribution per epoch:

| Bucket | Tokens/epoch | Share |
|---|---:|---:|
| Kept original Sapient | `13,682,970,219` | `34.82%` |
| Danish mixed additions | `9,454,480,428` | `24.06%` |
| AllenAI/Tulu/reasoning/no_robots | `5,294,402,580` | `13.47%` |
| Nemotron SFT | `3,752,921,296` | `9.55%` |
| DOLCI SFT | `3,158,545,564` | `8.04%` |
| DFM4 summarization | `1,842,578,300` | `4.69%` |
| Accepted Common Pile exports | `1,115,715,036` | `2.84%` |
| Accepted transformation exports | `696,139,171` | `1.77%` |
| Accepted Danish DynaWord exports | `300,492,627` | `0.76%` |

The 12 accepted export datasets contribute `2,112,346,834` sampled
tokens/epoch after context filtering/truncation. Danish mixed additions plus
accepted Danish DynaWord exports contribute `9,754,973,055` tokens/epoch
(`24.82%`), not counting Danish-English transformation exports or Danish rows
inside multilingual/non-Danish buckets.

DFM5 Lærebogen accounting, inspected locally on 2026-06-12. Confidence: high.
Only the `with_follow_ups` config of `danish-foundation-models/laerebogen` is
downloaded/used locally. It consists of seven Parquet shards with a `messages`
column and `1,294,336` conversation rows. Those rows contain `5,163,949`
assistant turns and `5,163,949` user turns, about `3.99` assistant turns per
conversation. The converter expands each assistant turn into one PrefixLM
training example, so the tokenized tree has `5,163,949` Lærebogen examples.
Superseded 2026-06-12: `data_io/prefix_config_dfm5.yaml` originally set
`laerebogen_with_followups__ repeat: 2`, which sampled `10,326,446`
Lærebogen examples per epoch and `5,126,425,326` covered tokens per epoch.
The repeat was removed on 2026-06-12, so the intended next DFM5 resample should
have about `2.563B` Lærebogen tokens/epoch instead. The current
`data/sampled_dfm5` still reflects the older `repeat: 2` run until it is
rebuilt.

DFM5 repeat audit on 2026-06-12. Confidence: high for current analytics. After
removing the Lærebogen repeat, the largest remaining repeat-driven expansions
are `lexdk__ repeat: 10` (`0.733B` tokens/epoch, saving `0.660B` if set to 1),
`oliverkinch_tidsskrift_dk_bt__ repeat: 10` (`0.482B`, saving `0.434B`),
`synquid_wiki_instruct_da__ repeat: 2` (`0.383B`, saving `0.191B`),
`oliverkinch_dynaword_bt__ repeat: 10` (`0.212B`, saving `0.191B`), and
`dfm4_wiki_cat_sum_summarization__ repeat: 2` (`0.228B`, saving `0.114B`).
All other active repeat rules save less than `0.1B` tokens/epoch if reduced to
one, except `synquid_danish_verifiable_reasoning__` at about `0.084B`.

Update 2026-06-12. Confidence: high. The largest repeat-driven Danish
additions were reduced before the next DFM5 resample:

```text
laerebogen_with_followups__: repeat 2 -> 1
lexdk__: repeat 10 -> 2
oliverkinch_tidsskrift_dk_bt__: repeat 10 -> 2
oliverkinch_dynaword_bt__: repeat 10 -> 2
synquid_danish_verifiable_reasoning__: repeat 10 -> 2
```

Expected reduction relative to the first DFM5 sample is roughly `3.3B`
tokens/epoch, dominated by Lærebogen (`~2.56B`), LexDK (`~0.59B`), and the two
Oliver Kinch backtranslation sources (`~0.56B` combined), with a small
Verifiable Reasoning reduction (`~0.075B`).

Reduced-repeat DFM5 resampling completed on 2026-06-12. Confidence: high.
Superseded on 2026-06-13 by the resample that also includes accepted
`synth_high40__` and `synth_repeat30__` replacement sources.

```text
sampled dataset: data/sampled_dfm5
analytics:       data/show_analytics_dfm5.md
stderr log:      logs/sample_dfm5.stderr.log
metadata.total_length: 35,518,233,884 tokens per epoch
```

Reduced-repeat DFM5 high-level distribution per epoch:

| Bucket | Tokens/epoch | Share |
|---|---:|---:|
| Kept original Sapient | `13,683,037,112` | `38.52%` |
| Danish mixed additions | `5,674,796,733` | `15.98%` |
| AllenAI/Tulu/reasoning/no_robots | `5,294,404,864` | `14.91%` |
| Nemotron SFT | `3,752,524,478` | `10.57%` |
| DOLCI SFT | `3,158,545,564` | `8.89%` |
| DFM4 summarization | `1,842,578,300` | `5.19%` |
| Accepted Common Pile exports | `1,115,715,036` | `3.14%` |
| Accepted transformation exports | `696,139,171` | `1.96%` |
| Accepted Danish DynaWord exports | `300,492,627` | `0.85%` |

Selected reduced Danish sources now contribute:

```text
laerebogen_with_followups:          2,563,212,663 tokens/epoch
lexdk:                                146,638,758 tokens/epoch
oliverkinch_tidsskrift_dk_bt:          96,377,264 tokens/epoch
oliverkinch_dynaword_bt:               42,450,474 tokens/epoch
synquid_danish_verifiable_reasoning:   18,643,694 tokens/epoch
```

DFM5 resampling with synthetic replacements completed on 2026-06-13.
Confidence: high. This is the current `data/sampled_dfm5` state.

```bash
cd /work/dfm/HRM-Text/data_io
ionice -c2 -n7 nice -n 10 python sample_tokenized.py \
  tokenized_path=../data/tokenized_dfm5 \
  output_path=../data/sampled_dfm5 \
  epochs=5 \
  concat_workers=1 \
  prefix_config_path=prefix_config_dfm5.yaml \
  > ../data/show_analytics_dfm5.md \
  2> ../logs/sample_dfm5.stderr.log
```

Outputs:

```text
sampled dataset: data/sampled_dfm5
analytics:       data/show_analytics_dfm5.md
stderr log:      logs/sample_dfm5.stderr.log
metadata.total_length: 35,605,979,095 tokens per epoch
sampled size:    821G
epoch dirs:      epoch_0 through epoch_4
```

The current resample adds accepted synthetic replacement data at one pass per
epoch:

```text
synth_high40:   63,956,698 tokens/epoch
synth_repeat30: 23,679,295 tokens/epoch
```

The total DFM5 epoch is therefore about `35.606B` tokens. At
`global_batch_size=196,608`, this is about `181,101` optimizer steps per epoch
and about `905,504` steps for the 5-epoch sampled dataset, before any final
partial-batch handling in the trainer.

Operational caveat from 2026-06-12: the current tool namespace temporarily lost
the normal `/work/dfm/HRM-Text` path while older processes still held the
checkout open via `/proc/<pid>/cwd`. A `WORKERS=2` tokenizer run using the
normal `/work` path failed with many `No such file or directory` reads once
that path disappeared. This was a mount/path-visibility issue, not evidence
that the accepted export files are broken; direct inspection through
`/proc/478730/cwd` still showed the audited files present and non-broken.

Dry build without the exported DynaWord tokenized tree, verified on 2026-06-12:

```text
sapient_linked_tasks:       4,891
danish_mixed_linked_tasks:     52
danish_export_linked_tasks:     0
total_tasks:                4,943
sapient_missing_tasks:         []
```

The export datasets are `messages` JSONL.GZ. The Rust tokenizer now supports
`.jsonl.gz` rows with a `messages` list and emits one `direct` row per assistant
turn. A one-shard smoke tokenization from
`export/danish-dynaword-paragraph-reordering` produced `tokens.npy` and all
index arrays successfully. Confidence: high.

Clarification, 2026-06-12. Confidence: high. The four exported Danish
DynaWord folders' current `data/*.jsonl.gz` files are not accepted-only
filtered outputs. They are deterministic generated export rows. The
`audit_full/audit.jsonl` and `audit_rebalance_*/audit.jsonl` files record
`keep`/`drop` decisions. To train only accepted rows, first run the export
folder's filter command to create an `audited/` tree and tokenize that filtered
tree instead. `scripts/tokenize_dfm5_danish_exports.sh` currently tokenizes the
`data/` subdirectories only; it avoids audit sidecar JSONL files but does not
apply audit decisions.

## Controlled Transformation Data Gap

Recorded on 2026-06-04. Confidence: medium for causal attribution; high for
local smoke-test symptoms.

Smoke generations from the original Sapient L epoch-4 checkpoint and the DFM4
XL-DDP step-200000 EMA checkpoint show a specific weakness on controlled text
transformation tasks: exact sentence-count summarization, tense rewriting,
child-friendly simplification, numbered fact extraction, and non-copy rewriting.
The DFM4 checkpoint is more responsive than the original Sapient checkpoint on
some simple English prompts, but both still tend to copy input text or ignore
format constraints on longer transformation prompts.

This is not best treated as a generic "more tokens" problem. Current DFM4 data
already contains broad instruction data and summarization data, including
generated DFM4 summarization tasks from arXiv paper-to-abstract, GovReport,
WikiCatSum, and LAION Scientific-Summaries. Upsampling those can strengthen
summarization, but it will not by itself teach tense conversion, simplification,
exact extraction counts, or robust output-shape compliance.

Recommended remediation order:

- Audit current sampled/converted data for explicit transformation instructions
  with patterns such as `summarize`, `rewrite`, `simplify`, `past tense`,
  `extract`, `numbered`, `exactly`, and `one/two sentences`.
- Add curated public editing/transformation datasets if license and provenance
  are acceptable. Initial candidates to review are `grammarly/coedit` for
  grammar and text editing, `facebook/asset` for simplification seed material,
  and selected Super-NaturalInstructions/NIV2-style rewriting, extraction,
  infilling, and composition tasks. These should be capped and audited rather
  than blindly imported.
- Selectively allow safer Sapient FLAN/Tasksource transformation subsets only
  after source-level review. The broad FLAN/Tasksource deny policy remains the
  default.
- Generate synthetic transformation data from already approved sources
  (DynaWord, LexDK, approved DBC text, GovReport/WikiCatSum/arXiv-derived
  summarization sources, and other accepted corpora). Use programmatic checks
  where possible: sentence count, numbered-list count, length ratio, non-copy
  ratio, language ID, and simple format validation.

Synthetic transformation data should start as a controlled auxiliary component,
not a dominant replacement corpus. A practical first target is roughly 0.5-2B
effective tokens per epoch, then evaluate whether the lite smoke/eval metrics
move before scaling further.

## Post-Training Transform Refine Mix

Added on 2026-06-04. Confidence: high for local preparation commands and
sampled metadata; medium for capability effect until fine-tuning/eval.

Decision: create a separate post-training dataset for final-checkpoint
refinement rather than folding the transformation-remediation data into the
main DFM pretraining mix.

Name and paths:

- Dataset name: `posttrain_transform_refine`
- Training config: `config/data/posttrain_transform_refine.yaml`
- Sampling config: `data_io/prefix_config_posttrain_transform_refine.yaml`
- Existing converted rows: `data/converted_sources_posttrain_transform_refine`
- Synthetic request seeds: `data/synthetic_requests_posttrain_transform_refine`
- Accepted synthetic rows after teacher generation:
  `data/converted_sources_posttrain_transform_refine_synthetic`
- Tokenized union: `data/tokenized_posttrain_transform_refine`
- Sampled data: `data/sampled_posttrain_transform_refine`

Included existing data:

- `grammarly/coedit`: included as direct supervised editing/rewrite rows.
- Filtered `Muennighoff/natural-instructions`: only train tasks whose task name
  or definition matches transformation-like keywords such as summarization,
  simplification, rewrite/paraphrase, extraction, conversion, infilling,
  completion, question/answer generation, or grammar/editing. Benchmark-style
  classification/NLI tasks are blocked by the filter.
- Existing relevant DFM4/repo data selected by tokenized-task prefix:
  DFM4 summarization, DBC/LexDK Danish writing, Danish instruction/IF/QA
  sources, Dolci, selected AllenAI IF/persona data, No Robots, and capped
  Nemotron instruction/multilingual.

ASSET policy: `facebook/asset` is used as synthetic seed material, not direct
supervised training data, because the locally exposed splits are
validation/test. This avoids turning a simplification benchmark-style reference
split directly into post-training targets.

Synthetic plan: create five task families in both English and Danish:

- exact two-sentence summarization
- past-tense rewrite
- child-friendly simplification
- exactly five numbered facts
- non-copy paraphrase/rewrite

The scaffold writes `50,000` teacher requests per task/language pair, for
`500,000` total requests. Responses are intended to be generated by a Gemma 4
teacher through an OpenAI-compatible API and accepted only after lightweight
validation checks. The request files are not sampled until responses have been
generated and converted.

Verified existing-only sample on 2026-06-04:

- `data/sampled_posttrain_transform_refine/metadata.json` reports
  `total_length=29,131,369,710` tokens for `EPOCHS=1`.
- New curated rows contribute:
  - `posttrain_coedit`: `70,783` unique rows, sampled with `repeat: 8`.
  - `posttrain_superni_filtered`: `498,918` retained rows after tokenizer
    filtering, sampled with `repeat: 2`.
- Synthetic sources are not yet present in the sampled dataset.

Subdataset sizing clarification, 2026-06-04. Confidence: high for current
analytics/config counts; low for synthetic token estimates until teacher
generations are produced.

- `data_io/prefix_config_posttrain_transform_refine.yaml` has `43` planned
  prefix rules: `33` existing/reused source rules and `10` synthetic task
  rules.
- The current tokenized union links `4,117` task directories: `4,115` selected
  existing DFM4/relevant tasks plus `2` new existing post-training tasks
  (`posttrain_coedit` and `posttrain_superni_filtered`).
- The current sampled analytics collapse those into `28` non-global category
  groups.
- Synthetic plan: `10` subdatasets, one for each combination of five task
  families and two languages, with `50,000` teacher requests each. The sampling
  config repeats each synthetic subdataset `20` times, so each accepted
  synthetic subdataset is planned for up to `1,000,000` sampled rows per epoch.
  Token volume depends on generated response length; a rough planning estimate
  is about `0.35-0.60B` tokens per synthetic subdataset, or about `3.5-6B`
  tokens across all ten.

Synthetic generation runtime note, 2026-06-04. Confidence: high for local
request counts and installed package check; low/medium for throughput estimates
until benchmarked on the target Gemma teacher.

- Local request files contain exactly `500,000` requests.
- A 1,000-row sample across request files has mean instruction length about
  `1,448` characters, roughly `360` input tokens by a simple character/token
  proxy. Generated response length is expected to dominate variance.
- `vllm` is installed locally (`0.20.2`), but the current
  `generate-synthetic` scaffold only calls an already-running
  OpenAI-compatible endpoint and sends requests serially. To use 8 B200 GPUs
  efficiently, run the teacher through vLLM or another batched serving backend
  and add/request concurrency or shard-level parallel clients.
- Planning estimate for 8 B200s with a 26B/31B teacher and batched serving:
  about `2-8` hours if sustained aggregate throughput is `5k-20k` generated
  examples/hour. The current serial client could be many times slower and
  should be treated as a functional scaffold, not the final high-throughput
  generation path.

Posttrain audit/regeneration policy, 2026-06-06. Confidence: high for local
counts and code paths; medium for final quality impact until the first audit
has been reviewed.

- Keep the synthetic generation target at `1,000,000` rows: `450,000`
  already-generated usable rows plus `550,000` pending rows.
- Generate the pending `550,000` rows with the Gemma judge enabled
  (`JUDGE_QUALITY=1`, `JUDGE_RETRIES=2`).
- Do not blindly regenerate the old `450,000`. First rejudge/audit accepted
  rows with `scripts/prepare_posttrain_transform_refine.py audit-generated`.
- Always drop and regenerate any row for which the judge is unhappy. No
  judge-failed row should be included in the converted post-training data.
- Regenerate an entire old slice when that is operationally simpler or when it
  shows a coherent systematic failure like the superseded bad
  `past_tense_rewrite_da` slice.
- The audit writes separate JSONL/summary artifacts and does not mutate the
  generated data; conversion to Parquet should only happen after unhappy judge
  rows have been excluded or regenerated.

Seed pool export, 2026-06-06. Confidence: high from local command output.

```text
data/posttrain_transform_refine_seed_texts/en.jsonl: 1,119,746 rows
data/posttrain_transform_refine_seed_texts/da.jsonl:    99,538 rows
data/posttrain_transform_refine_seed_texts/manifest.json
```

The seed manifest records the English and Danish source roots used by request
generation, making future request/regeneration runs reproducible.

## Mixed English/Danish Filtered 2x-Original Cap

Verified/created locally on 2026-05-24.

The first mixed-only filtered sample used `data_io/prefix_config.yaml` against `data/tokenized_mixed` and produced a very large corpus:

- Output: `data/sampled_mixed_english_danish_filtered`
- Analytics: `data/show_analytics_mixed_english_danish_filtered.md`
- Per-epoch `metadata.total_length`: `70,644,435,216` tokens
- 4-epoch covered tokens: `282,577,740,862`

Cause: `data/tokenized_mixed` task names include source prefixes such as `sapient_cleaned__data_clustered__SYNTH__...`, but the shared `data_io/prefix_config.yaml` uses unprefixed Sapient rules such as `SYNTH__`, `flan__`, and `dmmath__`. Those rules therefore did not match the filtered Sapient tasks in the mixed-only tokenized tree, causing most filtered Sapient files to be sampled uncapped.

A dedicated capped config was added:

```text
data_io/prefix_config_mixed_2x_original.yaml
```

Target ceiling:

- Original Sapient sample: `56,140,714,711` covered tokens over 4 epochs.
- Original per-epoch size: `14,035,178,677.75` tokens.
- 2x ceiling: `28,070,357,355.5` tokens per epoch.

Dry-run estimate after applying the new config with PrefixLM truncation/filtering:

- Estimated per-epoch sampled tokens: `24,630,898,966`
- Ratio to original per-epoch size: `1.755x`
- This is below the `2x` ceiling.

Final completed sample:

- Output: `data/sampled_mixed_english_danish_filtered_2x_original`
- Analytics: `data/show_analytics_mixed_english_danish_filtered_2x_original.md`
- Hydra config: `config/data/mixed_english_danish_filtered_2x_original.yaml`
- `metadata.total_length`: `24,630,436,020` tokens per epoch
- 4-epoch covered tokens: `98,521,744,082`
- Ratio to original per-epoch size: `1.755x`
- Unique sampled tokens: `55,258,504,135 / 78,082,414,846` (`70.77%`)
- Directory size: about `625G`

Note: `sample_tokenized.py` copies the full token bank into output `tokens.npy` before writing capped epoch indices, so the disk footprint remains large even though the epoch index budget is capped.

Estimated largest per-epoch category shares:

| Category | Estimated tokens/epoch | Share |
|---|---:|---:|
| `sapient_cleaned` | `8,129,060,084` | `33.0%` |
| `danish_dynaword` | `3,093,170,660` | `12.6%` |
| `nemotron_multilingual` | `3,001,252,991` | `12.2%` |
| `allenai_big_reasoning_traces` | `1,624,580,477` | `6.6%` |
| `dolci_instruct_sft` | `1,380,220,345` | `5.6%` |
| `dolci_instruct_sft_no_tools` | `962,106,919` | `3.9%` |
| `allenai_tulu_v2_sft_mixture` | `902,702,844` | `3.7%` |
| `allenai_tulu_3_sft_mixture` | `831,587,284` | `3.4%` |

Sampling was launched in tmux:

```bash
cd /work/dfm/HRM-Text/data_io
/home/ucloud/miniforge3/envs/hrm/bin/python sample_tokenized.py \
  tokenized_path=../data/tokenized_mixed \
  output_path=../data/sampled_mixed_english_danish_filtered_2x_original \
  prefix_config_path=prefix_config_mixed_2x_original.yaml \
  epochs=4 \
  concat_workers=4 \
  > ../data/show_analytics_mixed_english_danish_filtered_2x_original.md \
  2> ../logs/sample_mixed_english_danish_filtered_2x_original.err
```

Session:

```bash
tmux attach -t hrm_sample_mixed_2x_original
```

Confidence: high.
