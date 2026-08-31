---
type: Training Data Plan
title: DFM10 Plan
description: DFM10 integration of Danish H.C. Andersen and Alexandra Institute data plus native English search-agent trajectories.
tags: [dfm10, danish, english, andersen, alexandra-institute, agentic, tool-use, evaluation]
status: stable
last_updated: 2026-08-30
confidence: high
---
# DFM10 Plan

## Danish corpus expansion, 2026-08-29

DFM10 now also includes one-pass, gold-label supervision from the explicitly
licensed DSL Danish Sentiment Lexicon and Danish FrameNet. The strict-open
Tidsskrift.dk article-to-author-abstract source completed its extraction and
independent grounding audit. Its nine accepted gold rows are retained inside
the unified `dfm10-tidsskrift-open-sft` package rather than exposed as a tiny
standalone source. **Superseded 2026-08-30:** the 200,000-row minimum exceeded
the 189,392 candidates; production now audits all and requires 125,000 accepted
rows. A separate
`dfm10-tidsskrift-open-chats` package uses the same chunks for audited 2–10
exchange student inquiry conversations under the 4,096-token contract.
The Kalliope modernization pilot supports later full production behind the
existing audit gate. VoxPopuli normalization is excluded because 67 of its 79
accepted pilot outputs were near-copies and provide too little SFT signal.
Exact commands, rights policy, counts, and paths are maintained in the
[DFM10 Danish Corpus Expansion](/pages/dfm10-danish-corpus-expansion.md)
runbook.

## Repaired inherited sources

DFM10 replaces the inherited raw `nvidia/OpenMathInstruct-2` CoT/direct
prefixes with the verified, PRM-filtered, decontaminated
`openmathinstruct2_repaired__*` source. The repaired source contains 7,490,945
rows and passed both exhaustive structural validation and a 4,000-row
stratified E4B audit. The old prefix has `max_per_file: 0`; the repaired prefix
is capped at 20,000,000 rows per file, so its actual rows remain available
without repetition. Full methodology and results are in the
[DFM10 source-quality audit](/pages/dfm10-source-quality-audit.md).

DFM10 also replaces the inherited `nemotron_swe_windowed__*` conversion with
`nemotron_swe_repaired__*`. The legacy converter emitted every assistant turn
as a target and the generic chat tokenizer emitted every preceding assistant
turn again, creating duplicated targets and contextless partial actions. The
repaired conversion retains complete native `execute_bash` and
`str_replace_editor` call/result cycles, removes obsolete `think` calls,
converts terminal `finish` calls to normal assistant responses, admits only
complete examples fitting 4,096 tokens, and designates exactly one assistant
target per row. Agentless examples use a separate generic software-task system
prompt that defers to each explicit user request, and no tool schema. The old
prefix has `max_per_file: 0`; the
repaired prefix is the only Nemotron SWE source eligible for DFM10 sampling.
Conversion, structural validation, tokenization, and audit details are in the
[DFM10 source-quality audit](/pages/dfm10-source-quality-audit.md).
The authoritative converter-v4 corpus contains 2,472,316 examples and
6,597,089,585 exact Gemma-rendered tokens before sampling. The DFM10 union
contains all 33 repaired tokenized tasks; the new prefix retains up to 500,000
rows per task without repeating these files.

DFM10 also replaces all four inherited `oliverkinch/da-instruct-dynaword*`
tasks with `dynaword_instruct_repaired__*`. A complete E4B audit separates
clean rows, prompt/target mismatches, and damaged or incomplete authentic
targets. Only prompts are regenerated; authentic target text is never rewritten
or heuristically extended. A strict second audit and global target-aware dedupe
yield 65,548 final rows and 39,422,832 Gemma-rendered tokens. The repaired
prefix retains the prior repeat factor of four, while every legacy prefix has
`max_per_file: 0`. See the
[DFM10 source-quality audit](/pages/dfm10-source-quality-audit.md) for exact
admission counts and serving-path requirements.

DFM10 also disables the inherited `oliverkinch_danmarks_statistik_bt__`
prefix. Its authentic Danmarks Statistik targets are retained, but
persona-generated prompts are regenerated to request only information that the
target actually supplies. A separate exhaustive E4B audit filters indirect,
context-dependent, malformed, or still-mismatched pairs before the replacement
`danmarks_statistik_bt_repaired__` prefix becomes available at repeat ten. See
the [Danmarks Statistik repair runbook](/pages/dfm10-danmarks-statistik-repair.md).

The exact original-versus-repaired row and token inventory is maintained in
[DFM10 Production Replacement Inventory](/pages/dfm10-repaired-datasets.md).

## Z.ai Dataset Candidate Review

Review date: 2026-08-26. Confidence: medium-to-high from the current Z.ai Hub
catalog, official dataset cards, and the existing DFM9/long-context records.
This review records candidates; it does not yet add them to the downloader,
converter, tokenized tree, or sampled DFM10 mix.

| Dataset | DFM10 decision | Required handling |
| --- | --- | --- |
| `zai-org/LongReward-10k` | **Recommended for an 8K DFM10 SFT slice.** | Use the English `sft` split only. Render with the Gemma4 template and retain complete rows fitting 8,192 tokens; never truncate the answer. Keep both DPO splits for a later preference stage. |
| `zai-org/LongCite-45k` | **Recommended as a capped 8K grounded-QA/citation slice.** | Build evidence-preserving windows that retain every cited sentence and fit 8K. Cap its weight so the specialized citation syntax does not dominate general responses. |
| `zai-org/DeepDive` | **Included in DFM10.** | Only the 858 successful `trajectories_sft` rows are used. Search operations/results are converted into Gemma4-native tool calls and tool messages; model-specific wrappers and visible hidden-chain-of-thought are removed. |
| `zai-org/SWE-Dev-train` | **High capability value, but hold pending review.** | The 17,871 repository-agent rows could strengthen coding and long-horizon tool use, but the current card has no declared license and the transcript/action schema must be audited and converted to native tool calls. Check benchmark overlap before admission. |
| `zai-org/LongAlign-10k` | **Do not add to DFM10.** | DFM9 already has LongAlign-derived exposure through inherited material, and the project currently uses standalone LongAlign as a long-context diagnostic. Direct inclusion would add duplication and invalidate that diagnostic. Reserve a reviewed 8K--16K source subset for a future 16K stage only if the evaluation is replaced. |
| `zai-org/LongWriter-6k` | **Do not add to the 8K DFM10 mix.** | It primarily trains 2K--32K-word output generation; most complete examples cannot fit an 8K total sequence. Reconsider only a separately capped fitting subset at 16K or longer. |
| `zai-org/BPO` | **Preference-data candidate, not ordinary DFM10 SFT.** | Preserve `good_res`/`bad_res` pairs for DPO-style work. It overlaps OASST1, HH-RLHF, Alpaca-GPT4, and Chatbot Arena sources and adds little clean SFT breadth. |
| `zai-org/AgentInstruct` | **Do not add as-is.** | The small dataset uses old Llama/ReAct conventions with explicit thought/action text, and its Hub card does not declare a license. DeepDive is the cleaner modern candidate. |
| `zai-org/T1` | **Do not add without a separate audit.** | The repository mixes schemas, exposes only answer-level math supervision in part of the data, has no clear license on the card, and likely overlaps common olympiad/STEM benchmark families. |
| `zai-org/LongBench`, `LongBench-v2`, `terminal-bench-2-verified`, `ComplexFuncBench`, and other `*Bench` datasets | **Evaluation-only.** | Never admit benchmark rows or derivatives to DFM10 training. |

If DFM10 remains a 4K rather than 8K training mix, do not add the raw
LongReward or LongCite rows. Produce separately named 4K evidence-preserving
window variants, or defer both sources to the dedicated 8K post-training mix.

### DeepDive integration

Implemented 2026-08-26. Confidence: high from complete local conversion and
tokenization of the pinned upstream parquet SHA-256
`1e9f6545b460980bc894ce1c1ce60e0ae18fd2b2843d9a728ce3f16ca6dcd551`.

- Downloader name: `zai_deepdive`; only
  `data/trajectories_sft-00000-of-00001.parquet` and the card are downloaded.
- Converter: `scripts/prepare_dfm10_deepdive.py`.
- Converted source: `data/dfm10_deepdive_sources/`.
- Tokenized source: `data/tokenized_dfm10_deepdive/`.
- Sampling prefix: `zai_deepdive_trajectories_sft__`, `repeat: 1`,
  `long_context: drop`. Its 4K tokenizer drops complete older turns, never
  clips targets, and preserves the longer source trajectories.

The upstream `id` field is incorrectly constant (`858`) across all 858 rows.
The converter therefore derives a stable ID from row index and a BLAKE2 hash
of the unique question. Complete validation produced:

| Measure | Count |
| --- | ---: |
| Source trajectories / final gold answers | 858 |
| Structured search/click/open calls and matching responses | 8,212 |
| Visible `<think>` blocks removed | 9,070 |
| Tokenized assistant examples | 9,070 |
| Unfiltered rendered tokens | 98,214,430 |
| Examples fitting 4K by complete prompt/target | 2,731 |
| Examples fitting 8K by complete prompt/target | 4,449 |

The converted output defines only `search`, `click`, and `open` as tools. The
legacy terminal `finish` call is not taught as a tool; it becomes a normal
assistant response containing the upstream gold answer. The current
`data/tokenized_dfm10` union has been incrementally linked to this tokenized
task. A complete scripted rebuild will include it automatically after the
separate Folketing accepted-source tree is ready.

## Alexandra Institute Collection Review

The complete `alexandrainst` Hugging Face dataset collection was rescanned on
2026-08-15 and cross-checked against the inherited DFM8/DFM9 sources. The
following train-only additions are integrated into DFM10:

| Dataset | Training material to use | Current size | Intended conversion |
| --- | --- | ---: | --- |
| `alexandrainst/nordjylland-news-summarization` | grounded subset of original `train` | 75,219 source rows; 73,097 pre-audit candidates | Article to an authentic headline or brief summary. **Superseded 2026-08-28:** the generic-summary conversion is disabled; only the full-corpus grounding-filtered [repair](/pages/dfm10-nordjylland-news-repair.md) is eligible. The separate 63,855-row synthetic-summary file inherited through `oliverkinch/danish-summarization` is not duplicated. |
| `alexandrainst/scandi-qa` | Danish `train` only | 6,810 Danish rows | Context and question to short extractive answer or an explicit unanswerable response. Validation/test remain held out. |
| `alexandrainst/multi-zebra-logic` | Danish and English `train` configs only | 512 Danish + 256 English puzzles | Introduction, clues, question, and format instruction to compact JSON solution. Reserve validation/test as a new bilingual structured-reasoning evaluation. |
| `alexandrainst/dane` | `train` only | 4,383 Danish sentences | Sentence to JSON grouped `PER`/`ORG`/`LOC`/`MISC` surface spans, decoded from BIO annotations. This does not materially overlap the production DANSK NER benchmark; see the overlap audit below. |
| `alexandrainst/dacoref` | `train` only | 2,686 Danish documents | Document to JSON coreference clusters using exact surface mentions. Reserve validation/test. |

All conversions render through the Gemma 4 chat template. Split membership
and stable source IDs must be retained in conversion metadata. `multi-zebra`
solutions must be serialized deterministically; clue types, red-herring indices,
and gold solutions must never appear in the user prompt. Confidence: high for
dataset identity, split sizes, schemas, and tokenization statistics.

## Folketinget / Rigsarkivet Training Tasks

DFM10 also includes the pseudonymized Folketinget document collection from
[Sprogteknologi.dk](https://sprogteknologi.dk/dataset/folketingets-dokumenter-traeningsdata)
and Rigsarkivet handover
[14004](https://digidata.rigsarkivet.dk/aflevering/14004). The official archive
is downloaded from
[`digidata.rigsarkivet.dk/download/14004`](https://digidata.rigsarkivet.dk/download/14004)
to `data/downloads/datasets/folketingets_dokumenter_14004/14004.zip`.

The catalog describes approximately 125,000 Danish documents from 1849--2026
and nearly 1.2 billion words. It is CC BY 4.0, pseudonymized, and excludes
documents with personal information that could not be pseudonymized. Older
material is OCR-derived and has variable quality; the source publisher states
that it has not been generally OCR-cleaned. The converter rejects empty,
too-short, and control-character-dominated documents, while the Gemma judge
performs the semantic/OCR quality decision.

`scripts/prepare_dfm10_folketing_tasks.py` converts bounded text windows into
four auditable Danish task families under
`data/dfm10_folketing_transform_sources/<task>/data/`:

| Task | User input | Target |
| --- | --- | --- |
| `folketingets-dokumenter-prefix-continuation` | A substantial document prefix | Its natural suffix |
| `folketingets-dokumenter-denoising` | Word-level deletion/replacement/swap noise | The clean window |
| `folketingets-dokumenter-error-correction` | Sparse OCR/character corruption | The clean window |
| `folketingets-dokumenter-span-filling` | One masked span with surrounding context | The complete clean window |

Rows retain document identifier, title, period, document type, and OCR method
as provenance fields, but these fields are not inserted into the user prompt.
All rows use the same two-turn Gemma 4 chat structure as the other DFM10
sources. They must be audited before tokenization is used for training:

```bash
python scripts/prepare_dfm10_folketing_tasks.py --force
AUDIT_BASE_URL=http://127.0.0.1:8000/v1 AUDIT_MODEL=<served-judge> \
  bash scripts/audit_dfm10_folketing_tasks.sh
bash scripts/filter_dfm10_folketing_tasks.sh
```

The audit uses the existing retrying export-dataset judge and records decisions
and failure categories before any rows are admitted to training.

### Folketing transformation audit execution

On 2026-08-24 the four Folketing task families were launched as an eight-GPU
audit using the complete local `google/gemma-4-E4B-it` checkpoint at
`/work/dfm/jacobwashere/brainsurgery/models/google/gemma-4-E4B-it`. Each GPU
runs one Transformers OpenAI-compatible judge server and audits a deterministic
disjoint 1/8 partition of every source file. The launcher is
`scripts/run_dfm10_folketing_audit_8gpu.sh`; the active log root is
`logs/dfm10_folketing_audit_8gpu_transformers/`.

**Superseded attempt (2026-08-24):** the Transformers server was initially
used because the old vLLM environment selected an incompatible explicit
`FLASH_ATTN` kernel for E4B's 512-wide global attention head, and had a
`flashinfer`/`flashinfer-cubin` mismatch. That path was correct but too slow.

**Current execution (2026-08-24):** a dedicated conda `audit` environment now
contains conda CUDA 13.2, PyTorch/vLLM, and the matching Transformers pin.
vLLM is run with its default FlashInfer backend, `FLASHINFER_DISABLE_VERSION_CHECK=1`,
`VLLM_USE_FLASHINFER_SAMPLER=0`, `--enforce-eager`, maximum model length 8192,
and GPU utilization 0.90. The one-GPU E4B smoke test succeeded, including a
valid chat completion. The launcher supports a comma-separated `GPUS` subset
so it can coexist with unrelated vLLM services. Each selected GPU runs one
persistent server.

**Superseded 2026-08-26:** earlier subset runs mapped physical GPU IDs directly
to partition IDs and required a later wave for unselected partitions. The
launcher now assigns logical partitions independently of GPU IDs and processes
all `PARTITIONS` in deterministic waves over the selected GPUs. Cleanup tracks
only server and worker PIDs created by the current invocation; stale PID files
are never used to terminate processes. The merged audit is published only when
every logical partition produced an output file.
Confidence: high from the successful startup and live request logs.

**Resumed 2026-08-26:** the authoritative resumable state is
`logs/dfm10_folketing_audit_8gpu_vllm/workers/partition_{0..7}`. Legacy
`workers/gpu{0..7}` directories were renamed in place to the current logical
partition convention; no decision files were copied, regenerated, or dropped.
At resume time the eight partitions contained 8,715,947 decisions in total,
with 393,513--1,638,249 decisions per partition. The audit was restarted on all
eight GPUs with the `audit` conda environment, E4B vLLM judge, 0.90 GPU-memory
utilization, 64 server sequences, 64 client requests per partition, and
row-level `--resume`. The launcher PID is recorded in
`logs/dfm10_folketing_audit_8gpu_vllm/resume_all.pid`, and startup/output logs
are under the same audit root. A resumed worker first reads its existing IDs
and scans all four compressed candidate files before GPU inference starts; zero
GPU utilization during this bounded scan is expected and is not a stall.
Confidence: high from process inspection, source file offsets, server health
checks, and preserved JSONL line counts.

**Superseded readiness snapshot (2026-08-27):** the Folketing audit was not complete
or safe to filter. The four candidate files contain `14,586,873` rows. The
eight authoritative partition files contain `13,327,490` decisions, leaving
`1,259,383` unaudited rows concentrated in partitions 6 and 7. In addition,
partitions 1 and 2 contain approximately `798,000` `judge_error` records caused
by connection-refused failures; these are currently serialized as drops and
must be cleared and retried rather than treated as quality rejections. No audit
workers are active. After all eight partitions cover the complete candidate
set with no retryable judge errors, merge and de-duplicate them by `row_id`,
build `data/dfm10_folketing_transform_sources_audited`, tokenize it into
`data/tokenized_dfm10_folketing`, rebuild the `data/tokenized_dfm10` union, and
only then sample `data/sampled_dfm10`. The Andersen, Alexandra, DeepDive, and
inherited DFM9 tokenized components are already present and have byte-identical
tokenizer/template metadata. Confidence: high from local manifests, complete
partition line counts, audit summaries, and direct inspection of failed rows.

**Current balanced resume (2026-08-27):**
`scripts/prepare_dfm10_folketing_audit_resume.py prepare` atomically removed
and compressed-archived all `810,286` retryable judge-error rows while
retaining `12,517,204` valid decisions. The resulting missing set contains
`2,069,669` rows. A shared completed-ID index under
`logs/dfm10_folketing_audit_8gpu_vllm/balanced_remaining/` lets the audit
client scan the complete candidate corpus with primary partitioning disabled
and independently hash the missing rows into eight approximately equal
secondary partitions. This avoids reproducing the highly uneven ownership of
the interrupted original campaign. The detached launcher
`scripts/run_dfm10_folketing_remaining_balanced_8gpu.sh` (initial PID
`2607312`) has one watcher per GPU. Each watcher waits for no compute PID and
at least 170,000 MiB free before starting its E4B vLLM server and 64-concurrent
client. It never terminates unrelated processes. Retryable errors from a
nominally successful client are removed and retried. After all eight shards
finish, the launcher validates exactly `14,586,873` unique, non-error row IDs
before atomically publishing the merged audit. Confidence: high from the
completed cleanup manifest and live watcher/process inspection.

**Balanced-resume update (2026-08-28):** inference covered
`2,069,526 / 2,069,669` missing rows (`99.993%`). The remaining 143 rows
repeatedly produced malformed judge JSON even after 15--16 campaign attempts;
the old unbounded watcher loop consequently had no finite ETA. The audit client
now optionally requests an OpenAI-compatible constrained JSON object, and the
Folketing launcher enables it. Campaign retries are capped at three; any row
still lacking a parseable judgment is conservatively recorded as a terminal
drop with `audit_resolution=terminal_drop_after_exhausted_judge_retries`, not
accepted as training data. The audit was paused when the XXL training scheduler
claimed all GPUs; relaunch the balanced runner after they are free. One final
source scan plus atomic merge remains. Confidence: high from per-shard counts,
archived error inspection, process ownership, and repeated identical failures.

**Completed audit (2026-08-28):** this supersedes the paused state above. A
constrained-JSON retry resolved 55 of the final 143 malformed judgments. The
remaining 88 had already failed repeatedly and were conservatively sealed as
terminal drops from their archived judge records; none can enter training.
Finalization validated exactly `14,586,873` unique, non-error decisions and
atomically published
`logs/dfm10_folketing_audit_8gpu_vllm/export_judge.audit.jsonl`: `13,225,678`
keep, `1,361,195` drop, keep rate `90.668356%`. All audit vLLM servers were
released after the campaign. Confidence: high from exact-count validation,
duplicate detection, terminal-error checks, and the final summary manifest.

**Accepted-source materialization (2026-08-29):** the exact final audit was
joined back to the four candidate files and atomically materialized at
`data/dfm10_folketing_transform_sources_audited`. It retained 13,225,678 rows:
3,636,825 denoising, 3,105,440 error-correction, 3,573,233 prefix-continuation,
and 2,910,180 span-filling examples. `scripts/finalize_dfm10_folketing.sh`
verifies the exact source/accepted counts and the four-family inventory before
Gemma-native tokenization; it refuses partial or differently shaped input.
Production tokenization completed with zero skipped rows and 17,498,229,889
tokens: 5,391,304,669 denoising, 4,866,431,131 error-correction,
2,851,683,248 prefix-continuation, and 4,388,810,841 span-filling tokens. All
four prefixes use repeat one.

The DFM10 tokenized union was rebuilt after Folketing and the grounded
Nordjylland replacement completed. Its manifest records 11,719 task
directories, including all four Folketing families and one grounded
Nordjylland task.

The raw generated candidates are not an approved training corpus by
themselves; a filtered `keep=true` tree must be built before sampling.

Good held-out evaluation candidates, but weak SFT additions, are Danish
`ScaLA` grammatical acceptability (`2,048` test rows) and `DDisco` discourse
coherence (`201` test rows). Their training targets are short class labels and
would add little generative supervision. MultiZebraLogic validation/test is a
stronger new DFM evaluation because it measures bilingual reasoning and strict
JSON-format following.

**Superseded 2026-08-15:** the initial recommendation was not to use
`alexandrainst/scandi-qa` for DFM10 training because EuroEval directly registers
`EuroEval/scandiqa-da-mini` as the unofficial `scandiqa-da` reading-
comprehension evaluation. The current production campaign does not run that
unofficial task, and strict use of the upstream train split would not expose its
scored validation/test rows. Nevertheless, retaining the whole source family as
evaluation-only gives cleaner future benchmark provenance, while DFM already
has substantial Danish grounded-QA supervision.

**Current decision 2026-08-15:** include all 6,810 upstream Danish `train`
rows, while continuing to exclude validation and test. This accepts source-
family exposure for the currently unused unofficial EuroEval task but does not
expose its scored rows. If `scandiqa-da` is enabled later, report this training
relationship explicitly.

### DaNE versus DANSK overlap audit

The production EuroEval task named `dansk` is `EuroEval/dansk-mini`, derived
from `chcaa/dansk-ner`; it is not `alexandrainst/dane`. The current campaign
evaluates its validation split. `alexandrainst/dane` instead annotates the
Danish Dependency Treebank and uses the narrower `PER`/`ORG`/`LOC` scheme.

An exact local comparison on 2026-08-15 matched all 4,383 proposed DaNE train
sentences and token sequences against the cached DANSK mini train, validation,
and test splits. There was no overlap with DANSK train or validation. The only
test text matches were the trivial strings `-`, `3.`, and `4.`, and only `-`
also matched as a token sequence. This is not meaningful benchmark
contamination. EuroEval separately defines an unofficial `dane` task from the
same DaNE family; enabling that task later would require reporting that DFM10
used DaNE's train split. Confidence: high from installed EuroEval configuration,
production logs, cached DANSK parquet data, and the complete DaNE source split.

Do not add the remaining collection entries to DFM10 without a new policy
decision:

- `ragtruth-translated-hallucinations` has a competitive-model training
  restriction inherited from its GPT-4o-mini translations; raw bad responses
  would also be unsafe assistant targets.
- `multi-wiki-qa` and its synthetic-hallucination derivative overlap the
  existing MultiWikiQA evaluation and the inherited Oliver Kinch high-quality
  subset.
- `m_arc`, `m_hellaswag`, `m_mmlu`, `m_truthfulqa`, and
  `danish-citizen-tests` are benchmark material and must remain evaluation-only.
- `sentiment`, `ScaLA`, and `DDisco` mostly teach class labels; the large
  sentiment compilation also has weaker review/social-media provenance.
- `scandi-reddit`, `scandi-reddit-filtered`, `scandi-wiki`, and `wiki40b-da`
  are raw continuation data, conflicting with the current continuation policy;
  Reddit also raises privacy/provenance concerns.
- **Superseded 2026-08-30:** `domsdatabasen` is admitted only through the
  [audited chat path](/pages/dfm10-persona-doms-chats.md). Speech/audio and
  image-caption data remain out of scope.

## Scope

DFM10 inherits the complete DFM9 tokenized mix and adds the local Danish H.C.
Andersen orthography/language-modernization task plus the five approved
Alexandra Institute source families above. The supplied Andersen paragraph-
aligned files are under `/work/dfm/andersen/`:

| File | Purpose | Rows | Training exposure |
| --- | --- | ---: | ---: |
| `pairs_chunked.jsonl` | Partition audit only | 1,187 | 0 |
| `pairs_chunked_train.jsonl` | DFM10 training | 1,068 | repeat 20 |
| `pairs_chunked_val.jsonl` | Zero-shot DFM eval | 119 | 0 |

Every inspected row has exactly `system`, `user`, and `assistant` messages. The
system prompt asks for modernization of old Danish while preserving meaning,
style, and tone; the user message is the historical passage and the assistant
message is its modernized target.

## Split Integrity

Verified on 2026-08-13 by `scripts/prepare_dfm10_andersen.py`. Confidence:
high from complete local JSONL inspection.

- All 1,187 `(id, chunk_idx)` keys are unique.
- Train and validation have zero key or exact-row overlap.
- Their union exactly equals `pairs_chunked.jsonl`.
- The tokenization source tree contains only the training symlink; no validation
  row is exposed to the tokenizer.
- The validation set covers 71 stories, all of which also have different chunks
  in training. The eval therefore measures held-out paragraph chunks, not
  held-out works. Treat it as in-domain generalization, not document-level
  generalization.

Authoritative SHA-256 values:

```text
pairs_chunked.jsonl       91b914082f389b79a3389379108a6c033f09126056b905393574dcef43b512e3
pairs_chunked_train.jsonl 5dd4f2b67e3e1e358266a8e5e834531abf2630f7eda313588216430f7a683408
pairs_chunked_val.jsonl   7d635eb87ecab1fd88be0e290fe029d4af183fbafc0097f516fce0e7c60e91bf
```

## Training Integration

### Audited OpenStax grounded SFT

The independently audited derivative SFT from 61 immutable historical OpenStax
CC BY artifacts is active in DFM10 at repeat one. All 64 shards succeeded and
the final corpus contains 50,000 rows and 8,592,140 rendered tokens. See the
[DFM10 OpenStax Grounded SFT](/pages/dfm10-openstax-sft.md) record for the
licensing boundary, quality gate, exact artifacts, and integration procedure.

The planned XXL continuation after its first DFM8 epoch is documented in the
[DFM8 XXL to DFM10 multi-node transition plan](model-architecture/dfm8-xxl-to-dfm10-multinode-transition.md).

`scripts/prepare_dfm10_data.sh` validates Andersen, downloads only the selected
Hugging Face train artifacts, converts each source to deterministic chat JSONL,
tokenizes all additions with the Gemma 4 native chat template using 16 workers
by default, and builds `data/tokenized_dfm10`. The completed local tree has
11,413 inherited DFM9 tasks, one Andersen task, and ten Alexandra source tasks.
All 89,866 Alexandra rows tokenized successfully with zero skipped rows.

Tokenization retained all 1,068 training rows and produced 1,205,157 tokens:

| Quantity | Tokens |
| --- | ---: |
| Prompt/system/user | 652,915 |
| Assistant target | 552,242 |
| Unique total | 1,205,157 |
| Raw repeated total before context truncation | 24,103,140 |
| Effective DFM10 contribution under the superseded truncation policy | 24,097,380 |

One row is 4,385 rendered tokens, above the sampler's 4,097-token context
budget. **Superseded 2026-08-30:** truncation retained it with a clipped target;
DFM10 drops it intact for later long-context use. All other rows fit.

Verified Alexandra token counts before sampling/context packing. **Superseded
2026-08-28 for Nordjylland only:** its old count below remains the historical
baseline; the repaired count will replace it after full-corpus filtering and
tokenization.

| Source | Rows | Unique tokens | Repeat | Raw repeated tokens/epoch |
| --- | ---: | ---: | ---: | ---: |
| Original Nordjylland summaries | 75,219 | 37,188,521 | 1 | 37,188,521 |
| Grounded Nordjylland repair (authoritative replacement) | 47,120 | 26,590,391 | 1 | 26,590,391 |
| Danish ScandiQA | 6,810 | 3,988,956 | 4 | 15,955,824 |
| Danish/English MultiZebra | 768 | 521,134 | 1 | 521,134 |
| DaNE | 4,383 | 614,709 | 4 | 2,458,836 |
| DaCoref | 2,686 | 323,960 | disabled | 0 |
| **Alexandra total** | **89,866** | **42,637,280** | | **56,124,315** |

The DaNE upstream archive contains all official splits because that is how the
dataset is distributed, but the converter extracts and exposes only
`ddt.train.conllu`. No validation/test artifact from the other four source
families is downloaded, and no held-out filename exists in
`data/dfm10_alexandra_sources` or `data/tokenized_dfm10_alexandra`.

`data_io/prefix_config_dfm10.yaml` inherits DFM9 and adds:

```yaml
- prefix: andersen_modernization__
  repeat: 20
- prefix: alexandra_nordjylland_original__
  max_per_file: 0
- prefix: nordjylland_news_repaired__
  repeat: 1
- prefix: alexandra_scandi_qa_da__
  repeat: 4
- prefix: alexandra_multi_zebra__
  repeat: 1
- prefix: alexandra_dane__
  repeat: 4
- prefix: alexandra_dacoref__
  max_per_file: 0
```

`config/data/dfm10.yaml` points training to `data/sampled_dfm10`. Full DFM10
sampling completed on 2026-08-29. The following command is retained as the
reproducible rebuild command, not as pending work:

```bash
cd /work/dfm/HRM-Text
DFM10_SAMPLE=1 DFM10_EPOCHS=10 bash scripts/prepare_dfm10_data.sh
```

**Superseded 2026-08-29:** the pre-audit plan used MultiZebra at 8x and DaCoref
at 4x and described sampling as pending. Final source reconciliation reduced
MultiZebra to one pass, disabled DaCoref, and produced ten epochs of
101,731,426,509 tokens each. See the
[final source reconciliation](/pages/dfm10-final-source-reconciliation.md).

## Zero-Shot Evaluation

`dfm-evals/dfm_evals/tasks/andersen_modernization.py` registers
`dfm_evals/andersen-modernization`. It loads only
`pairs_chunked_val.jsonl`, preserves the source system and user messages, uses
no demonstrations or few-shot solver, and generates deterministically with
temperature 0 and at most 1,536 output tokens.

The task reports case-sensitive sentence GLEU and normalized chrF3++. Exact
match is deliberately not the primary metric because legitimate modernization
can differ lexically from a single reference. The production scheduler includes
the task as one DFM shard under the suite
`hrm_danish_andersen_modernization`; its merged W&B keys are:

```text
dfm_eval/andersen_modernization/gleu/mean
dfm_eval/andersen_modernization/chrf3pp/mean
```

The supplied targets contain some sizable source/target length differences,
including omitted or added paragraphs. These are retained as provided. Scores
must therefore be interpreted as agreement with this particular modernization
reference, not as a complete semantic-faithfulness judgment.

## LMSYS Chat Data Decision

For **DFM10**, do not integrate the raw multilingual `lmsys/lmsys-chat-1m`.
Language-filtered local subsets are a reasonable optional DFM10 addition if
they remain internal and pass the filters below. The dataset contains one
million real-world conversations collected from 210,479 IP addresses across
154 languages, with retained unsafe content, best-effort PII redaction, no
benchmark decontamination, and possible redaction errors. Its access agreement
is non-transferable and permits LMSYS to require deletion of all copies. That
does not satisfy the project's current GDPR/privacy and reproducibility bar.

The **Danish subset is worth considering** because it is small and directly
supports DFM10's Danish multi-turn/chat objective. A third-party Danish
filtering note reports approximately 3,741 local LMSYS Danish conversations;
that figure must be verified from the gated source before sampling. Use it as
an additive, capped Danish chat source rather than repeating it heavily.

The **English subset is optional and lower priority**. It is much larger, but
mostly short, two-turn, 2023-era general chat and overlaps substantially with
our existing English chat, WildChat, DOLCI, Nemotron Agentic, and OpenHermes
sources. If used, cap it rather than adding all English rows.

The same DFM10 decision applies to raw `lmsys/chatbot_arena_conversations`.
`lmsys/toxic-chat` should remain evaluation/safety data, and
`lmsys/mt_bench_human_judgments` is evaluation/preference metadata rather than
assistant-response supervision. If used, the DFM10 adapter must retain only
high-confidence English/Danish rows, remove moderation-positive or unsafe
rows, remove residual names, emails, phone numbers, identifier-bearing URLs,
and identifying location/biographical combinations, deduplicate against
evaluation prompts, and keep only coherent assistant turns. The resulting
data must stay local and must not be uploaded or redistributed unless LMSYS
explicitly confirms that the agreement permits derivative transfer.

## LMSYS English/Danish Audit Plan

This is a plan for a **local-only DFM10 experiment**, not approval to publish
or upload an LMSYS-derived dataset. Access must be accepted under the LMSYS
agreement before any files are downloaded. Preserve the original archive,
source revision, access date, and deletion status so the entire derivative can
be removed if requested.

### Inputs and scope

1. Download the gated `lmsys/lmsys-chat-1m` Parquet files into a private local
   directory. Do not mirror them into a public export tree.
2. Keep only rows whose declared language is high-confidence `English` or
   `Danish`. Recheck the first user turn and every retained assistant turn with
   an independent language detector; reject mixed-language or uncertain rows.
3. Preserve conversation boundaries and all preceding turns needed to
   interpret a retained assistant response. Do not create isolated assistant
   answers from a conversation whose context was removed.
4. Start with all Danish candidates and a capped English candidate sample. The
   English subset is a control/comparison source, not an automatic addition to
   the main DFM10 token budget.

### Gemma 4 31B audit

Run a deterministic Gemma 4 31B judge with temperature 0, structured JSON
output, and retries for invalid JSON. One audit record is written per
conversation and includes the dataset row ID, source hash, model/revision,
prompt version, and timestamp. The judge must return separate decisions for:

| Dimension | Retain only when | Mandatory rejection examples |
| --- | --- | --- |
| Usefulness | The user request is meaningful and the assistant response is coherent, relevant, and materially useful | Empty/garbled turns, pure greetings, spam, duplicated boilerplate, broken model output, irrelevant response |
| Instruction following | The response follows explicit constraints and preserves conversation state | Ignores the request, invents a different task, loses previous-turn references, malformed structured output |
| Safety | The exchange is suitable as ordinary capability training | Sexual content, sexual-minor content, graphic violence, hateful/harassing content, self-harm assistance, credential/illegal-action assistance, or jailbreak content |
| Privacy | No residual personal or sensitive information remains | Email, phone, address, account/credential data, unique personal identifiers, or combinations that identify a private person |
| Retention | The complete conversation is safe and useful as a Gemma-native multi-turn example | Any unsafe or privacy-sensitive turn, unresolved moderation flag, severe language mismatch, or context required for interpretation being absent |

The judge also assigns a capability label (`general_instruction`, `multi_turn`,
`reasoning`, `math`, `code`, `translation`, `summarization`, `creative`,
`knowledge`, `refusal`, or `other`) and a quality score from 0--3. The score is
for analysis; retention is conjunctive and cannot override a safety/privacy
failure.

### Deterministic hard filters before/after judging

Before calling Gemma, reject malformed JSON, missing roles, unsupported role
sequences, empty turns, moderation-positive rows, obvious benchmark prompts,
and rows with control characters. After judging, apply local checks for email,
phone, URL query identifiers, API keys, credit-card-like strings, addresses,
and residual PII markers. Hash prompts and assistant outputs for deduplication;
do not retain raw text in audit summaries.

Retain a conversation only when:

```text
language_ok
and usefulness_ok
and instruction_following_ok
and safety_ok
and privacy_ok
and no_hard_filter_match
and judge_confidence >= threshold
```

Run a second independent judge pass on a stratified sample of retained and
rejected rows. Manually inspect every disagreement category and at least 200
retained rows per language. A run is not accepted if safety/privacy false
negatives appear in the manual sample or if the judge's invalid-output rate is
above the configured retry threshold.

### Retention and DFM10 integration

Write accepted rows to two private outputs:

```text
data/dfm10_lmsys_english_audited/
data/dfm10_lmsys_danish_audited/
```

Render accepted conversations through the Gemma 4 native template, retain
source IDs only as local provenance, and run a final template/schema check.
Start with `repeat: 1`; do not compensate for the small Danish subset through
aggressive repetition. Add the Danish source to DFM10 only after the audit
summary and manual review pass. Add English only behind an explicit token cap
after comparing its retained capability distribution with existing DFM10 chat
sources. Never upload either derivative without written confirmation that the
LMSYS agreement permits transfer.

## Long-context evaluation plan (2026-08-24)

The scheduler now has an opt-in `--include-ruler-smoke` row. It runs the
packaged RULER NIAH and variable-tracking tasks at 4K with four examples each,
logs under `long_context/*`, and is intentionally excluded from headline DFM
averages. This is the only RULER level currently valid for HRM checkpoints:
the model/export and normal vLLM path are configured for a 4,096-token context.

After a checkpoint and serving path support longer contexts, add RULER at 8K,
16K, and 32K (and later 64K/128K only if the model is trained for them). Keep
these synthetic capability probes separate from ordinary `eval/*` and
`dfm_eval/*` metrics. RULER is useful for controlled retrieval/aggregation
stress tests, but it is not a substitute for realistic document tasks.

GovReport is suitable for a realistic English long-context summarization task:
17,517 reports were inspected locally; report character lengths had p50 42,538,
p90 91,716, p95 114,440, p99 188,105, and max 1,323,870. There were 11,546
reports at least 32,000 characters and 4,475 at least 64,000 characters. Build
a fixed, held-out source-ID sample at each supported context length, preserve
the original summary target, remove the current 9,000-character cap, and log
it under a distinct long-context summarization prefix.

Individual NordjyllandNews articles are not generally long enough: the local
75,219-row source had p50 1,180 characters, p90 2,552, p95 3,125, p99 4,653,
and max 35,164, with only one row at least 32,000 characters. Do not present
single-article NordjyllandNews as a long-context benchmark. Instead, create a
deterministic Danish multi-document retrieval-plus-summarization task: combine
several articles as context, ask for the summary of a named target article,
and score retrieval of the target plus summary quality. Keep it separate from
the existing single-article NordjyllandNews score and use held-out source IDs.

Recommended 50K cadence:

| Task | Current model support | Cadence | Included in headline averages |
| --- | --- | --- | --- |
| RULER 4K smoke | Yes | Every 50K | No |
| GovReport long summarization | After 8K/16K support | Every 50K or selected checkpoints | No |
| Nordjylland multi-document DA | After 8K support | Every 50K or selected checkpoints | No |
| RULER 8K/16K/32K | After matching model/export support | Epoch boundaries or selected checkpoints | No |

The standardized RULER reference is the [NVIDIA RULER repository](https://github.com/NVIDIA/RULER);
the local packaged task and suite are in `dfm-evals/dfm_evals/eval-sets.yaml`
and `config/dfm_evals_hrm_single_tasks.yaml`.

### Current 8K extension run audit

The run from `/work/dfm/HRM-Text-long-context` is consuming
`data/sampled_dfm9_8k/metadata.json`, whose `max_seq_len` is 8,193. Its model
configuration gives L layers a 4,096-token sliding window and leaves H layers
global, so H can attend across the full 8K sequence. This explains why GPU
memory is not approximately double the 4K baseline: only half the layers are
global and the L layers remain windowed.

There is a configuration caveat for future restarts. The model implementation
reads `H_rope_scaling_type` and `H_rope_scaling_factor`, but the current YAML
puts `rope_scaling_type` and `rope_scaling_factor` inside `H_override`. The
current process therefore has 8K inputs/global H attention, but should not be
assumed to have active H-layer YaRN scaling until the resolved configuration is
corrected and a fresh process is launched.

The scheduler now also provides an opt-in `--include-govreport-long` task. It
uses a stable eight-shard, 512-example subset of 24,000--30,000-character
GovReport documents, an 8K serving context, and the separate `long_context`
metric prefix. It is excluded from headline averages.

The standard long-context headline is logged under
`long_context_headline/*`, separately from the ordinary Danish, English, and
Math & Code averages. The scheduler merges each task independently and then
computes this headline. Current tasks are:

| Group | Task | Dataset/config | Limit and scoring |
| --- | --- | --- | --- |
| Diagnostic | RULER smoke | `NVIDIA/RULER` | Small 4K smoke; exact task score; not a capability claim |
| English | GovReport long | `ccdv/govreport-summarization` | 24K--30K source chars, max 512 rows; ROUGE-L/BERTScore |
| English | LongBench | `zai-org/LongBench` English/LongBench-E files | max 5,000 rows; aggregate diagnostic scorer |
| English | LongAlign | `zai-org/LongAlign-10k` English subset | max 5,000 rows; aggregate diagnostic scorer |
| Danish | LongAlign | `zai-org/LongAlign-10k` Danish subset | max 5,000 rows; currently only a few detected rows |
| English | Marathon | `Hambaobao/Marathon` | max 5,000 rows; format-only because the public conversion has no answer key |
| English | QMSum | `pszemraj/qmsum-cleaned`, validation split | max 5,000 rows; ROUGE-L |
| Danish | Nordjylland | `oliverkinch/danish-summarization`, `nordjylland` | max 5,000 rows; ROUGE-L |
| Danish | EUR-Lex | `oliverkinch/danish-summarization`, `eur_lex` | max 5,000 rows; ROUGE-L |

Marathon is intentionally labeled format-only and must not be interpreted as
correctness. LongBench and LongAlign use generic diagnostics rather than the
official benchmark-specific scoring implementations.

HF candidates worth considering for future standardized long-context evals:

| Dataset | Language | Use |
| --- | --- | --- |
| `zai-org/LongBench` / `LongBench-E` | English and Chinese | Broad long-context QA, retrieval, summarization, few-shot, and code; most task averages are 5K--15K words and LongBench-E explicitly balances 0--4K, 4--8K, and 8K+ examples. |
| `zai-org/LongAlign-10k` | Multilingual, with English examples | 8K--64K long instruction examples; useful as a long-instruction stress set, but not as clean as a task-specific benchmark. |
| `Hambaobao/Marathon` | English | Multiple-choice long-context benchmark reaching 200K+; useful later, but too expensive for every 50K checkpoint. |
| `pszemraj/qmsum-cleaned` | English | Meeting summarization; suitable after checking actual length bins and overlap. |
| `oliverkinch/danish-summarization` (`eur_lex`) | Danish | 831 legal-document summaries with document lengths reported up to roughly 744K characters; promising Danish long summarization, but must be held out and deduplicated against training. |

The Folketing source can provide a held-out Danish document-summary task once
reference summaries are available or independently audited; it is not yet a
scored task in this suite.

An isolated three-step XL measurement at 8K with YaRN factor 2.0 completed
after fixing the YaRN ramp tensor to use the same device as the frequency
tensor. With the same batch and BP settings, peak allocated memory was
`107.5--109.0 GiB/GPU` and peak allocator-reserved memory was
`111.4--129.9 GiB/GPU`, effectively unchanged from the no-YaRN 8K test.

### 100-step attention benchmark (2026-08-24)

To separate attention-window effects from batch and optimizer effects, three
100-optimizer-step runs were measured on eight GPUs with the same sharded XL
checkpoint, `global_batch_size=262144`, `gradient_accumulation_steps=2`,
BF16 compute, FP32 FSDP parameters, BP=5, and YaRN factor 2.0 where needed.
The first two steps were excluded from the timing summary as compiler/warm-up
steps. Peak memory is the maximum CUDA allocator value observed across ranks;
reserved memory is allocator reservation and is therefore not equivalent to
live model memory.

| Configuration | Median step | Mean step | Peak allocated | Peak reserved | Status |
| --- | ---: | ---: | ---: | ---: | --- |
| 4K L window / H global | 1.102 s | 1.102 s | 105.7--106.2 GiB | 119.8--124.7 GiB | complete |
| 8K L window / H global | 1.235 s | 1.549 s | 106.7--107.1 GiB | 120.2--126.9 GiB | complete |
| 8K L global / H global | 1.253 s | 1.399 s | 106.7--107.1 GiB | 120.2--126.9 GiB | complete |

The H-only mean contains one 16.35-second outlier; its median is the more
representative throughput measure. The full 8K run completed without OOM and
was only about 14% slower by median than the fair 4K run in this short sample.
The matching memory ceilings indicate that FA4's memory behavior at this
fixed-token batch is not scaling like a materialized quadratic attention
matrix. This is a performance diagnostic, not evidence that full 8K attention
has the same quality or long-context capability as the windowed design.

An earlier 4K 100-step run used the default 196,608-token batch and was not
used in this comparison. Logs for the comparable runs are
`logs/training/memory_bench_4k_100_gb262k.log`,
`logs/training/memory_bench_8k_H_100.log`, and
`logs/training/memory_bench_8k_LH_100.log` in the long-context worktree.

### 16K and 32K extension benchmark (2026-08-24)

The same protocol was applied to the 16K and 32K configs from the verified 8K
boundary checkpoint. The 16K runs completed with the same 262,144-token global
batch and accumulation 2:

| Configuration | Median step | Mean step | Peak allocated | Peak reserved | Status |
| --- | ---: | ---: | ---: | ---: | --- |
| 16K L window / H global | 1.435 s | 1.815 s | 104.1--107.3 GiB | 109.1--129.5 GiB | complete |
| 16K L global / H global | 1.643 s | 1.845 s | 104.1--107.3 GiB | 109.1--129.5 GiB | complete |

At 32K, the same fixed batch requires care. With accumulation 2, the local
packing capacity is only 16,384 tokens, below the 32,769-token sequence limit.
The sampler consumes the short rows and then stops when it cannot form a full
8-rank batch for longer rows. Those runs exit cleanly with return code 0 and
must not be interpreted as successful 100-step benchmarks.

The valid fixed-batch configuration uses accumulation 1, giving each rank a
32,768-token packing budget. Both H-only and full L+H then OOM on the first
step: PyTorch reports roughly 172--176 GiB allocated on 178.34 GiB GPUs, with
only tens of MiB free. Consequently there is no trustworthy 100-step 32K
throughput result at this batch. The one-step probes establish a hard memory
limit, not a performance comparison.

The 16K logs are
`logs/training/memory_bench_16k_H_100.log` and
`logs/training/memory_bench_16k_LH_100.log`. The 32K diagnostic logs are
`logs/training/memory_bench_32k_H_100_nocompile.log`,
`logs/training/memory_bench_32k_LH_1_nocompile.log`,
`logs/training/memory_bench_32k_H_1_gas1.log`, and
`logs/training/memory_bench_32k_LH_1_gas1.log`.
