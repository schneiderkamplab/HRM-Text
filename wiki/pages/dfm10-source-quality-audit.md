---
type: Runbook
title: DFM10 Source Quality Audit
description: Deterministic Gemma 4 26B-A4B review of up to 100 exact training examples from every logical DFM10 source.
tags: [dfm10, data-quality, audit, gemma4, vllm]
status: draft
last_updated: 2026-08-28
confidence: high
---
# DFM10 Source Quality Audit

## Scope and authority

The source-quality campaign audits the complete logical DFM10 inventory rather
than only the new DFM10 additions. Its `178` source definitions comprise `161`
sources documented in `docs/dfm8-datasets.md`, nine DFM9 additions, and eight
DFM10 additions. The tokenized DFM10 union and
`data_io/prefix_config_dfm10.yaml` determine which examples are training
eligible. This preserves the sampler's default inclusion of unmatched tasks and
its explicit `max_per_file: 0` exclusions.

For the 177 sources already tokenized, sampling decodes the exact prompt and
assistant token spans visible to training. Each source receives a deterministic
uniform sample of 100 eligible examples, or every example when fewer than 100
exist.

**Superseded 2026-08-27:** the original plan required the fully merged
Folketing accepted tree. The acceptance campaign's stable-hash partitions 0--5
were complete while partitions 6--7 and the merged tree were not. The report
therefore adds a deterministic, task-stratified sample of 100 accepted rows
from the six complete partitions: 25 each from denoising, error correction,
prefix continuation, and span filling. This is an unbiased accepted-row subset
of those six partitions, not a claim that the full acceptance campaign was
consolidated.

## Review dimensions

Gemma 4 26B-A4B-it scores each example from 1 to 5 for:

1. language quality and absence of corruption;
2. instruction/answer or tool-call coherence;
3. meaningful ability to contribute to model training.

The rubric is task-aware: short labels, translation, reconstruction, synthetic
reasoning, structured output, and native tool calls are judged against their
declared purpose rather than rejected for their format.

The OpenAI-compatible request uses an explicit JSON Schema response format.
Generic JSON-object constraints reduced malformed responses but still allowed
missing nested scores; the explicit schema is required for reliable resumable
audits. Retry-exhausted rows are regenerated with a larger output allowance
before merge rather than accepted as audit results.

## Race and failure safety

`scripts/dfm10_quality_audit.py` writes deterministic samples once, gives each
sample a stable ID, and assigns IDs to a configured number of disjoint partitions. Each GPU
writes only its own resumable JSONL. Retry-exhausted API records are removed
from completed resume state and retried on the next invocation. The final
merger takes an exclusive file lock, rejects duplicates/missing/unexpected IDs,
and publishes the single result JSONL with `fsync` plus atomic rename.

On 2026-08-26, the original queued eight-GPU E4B plan was superseded by
`scripts/run_dfm10_quality_audit_4gpu_a4b.sh`. Folketing partitions 0 through 3
had completed, so their exact E4B server PIDs were terminated and GPUs 0 through
3 were reassigned to four A4B audit partitions. The launcher owns only the
server/worker PIDs it creates and frees them on completion or interruption.

The A4B vLLM launch uses the complete Hugging Face snapshot rather than the
incomplete weights-only copy, disables all multimodal inputs for this text-only
audit, uses `gpu_memory_utilization=0.90`, `max_num_seqs=64`, and client
concurrency 64. `CUDA_HOME=/usr/local/cuda` is required: pointing at the conda
environment prefix omitted CUDA headers from FlashInfer's host C++ compilation.
Warm `fused_moe_100` once with one server before parallel startup; the first
build compiles 266 CUDA objects, links the extension, and populates the shared
MoE autotune cache. Starting several cold servers against that cache is unsafe.

## Active paths

```text
logs/data_audits/dfm10_source_quality_a4b_20260826/
  inventory.json
  samples.jsonl
  partitions/partition_{0..3}.jsonl
  dfm10_source_quality_audit.jsonl
  dfm10_source_quality_audit.summary.json
```

The base 177-source artifact is
`logs/data_audits/dfm10_source_quality_a4b_20260826/dfm10_source_quality_audit.jsonl`.
The Folketing assessment is
`logs/data_audits/dfm10_folketing_quality_a4b_20260827/folketing_quality_audit.jsonl`.
The report builder combines these two immutable audit results rather than
rewriting the completed base artifact.

The ready-source pass completed on 2026-08-26 with 17,455 judgments across 177
sources, zero judge errors, and 15,044 rows (`86.2%`) marked usable for training.
All A4B servers owned by the pass were torn down after the merge.

The Folketing pass completed on 2026-08-27 with zero judge errors. It marked 87
of 100 accepted examples usable, with mean language, coherence, and training
value scores of 4.38, 4.59, and 4.48. Usable counts by task were 22/25
denoising, 18/25 error correction, 23/25 prefix continuation, and 24/25 span
filling. Error correction is the weakest family because residual OCR damage can
make even an acceptance-audited reconstruction target unreliable.

## Ranked PDF report

The reproducible report builder is
[`scripts/build_dfm10_quality_audit_report.py`](/../scripts/build_dfm10_quality_audit_report.py).
It reads the authoritative merged JSONL and produces both the LaTeX source and
the compiled report at:

- [`docs/reports/dfm10-source-quality-audit.tex`](/../docs/reports/dfm10-source-quality-audit.tex)
- [`docs/reports/dfm10-source-quality-audit.pdf`](/../docs/reports/dfm10-source-quality-audit.pdf)

Rebuild the committed artifacts with:

```bash
python scripts/build_dfm10_quality_audit_report.py
cd docs/reports
pdflatex -interaction=nonstopmode -halt-on-error dfm10-source-quality-audit.tex
pdflatex -interaction=nonstopmode -halt-on-error dfm10-source-quality-audit.tex
```

The report ranks all 178 audited sources and 17,555 judgments from most to least
severe. Its severity
index gives 50% weight to the unusable-row rate, 20% to coherence deficit, and
15% each to language-quality and training-value deficits. The table also gives
sample counts, usable and issue rates, all three mean scores, and the two most
frequent qualitative issue categories for every source.

**Superseded 2026-08-27:** the first report revision used one `Posttrain`
column whose labels combined task role and observed quality. That conflated two
independent decisions and must not be used.

The corrected report has two columns. `LLM role` depends only on task semantics:
`SFT` is ordinary supervised post-training, `Aux-SFT` is a reconstruction-style
auxiliary objective, and `Midtrain` is continuation data better suited to
continued pretraining or midtraining. `Quality` depends only on the audit:
`Use` requires at least 80% usable rows, mean coherence of at least 4.0, and
mean training value of at least 3.5; `Filter` is the intermediate disposition;
and `Repair` applies below 50% usability or 3.0 mean coherence. Thus a source
can be semantically appropriate for SFT while still requiring repair, or be a
high-quality source whose semantics make it midtraining data.

The combined report yields 169 `SFT`, 6 `Aux-SFT`, 2 `Midtrain`, and 1 `Mixed`
role classifications, independently of 136 `Use`, 32 `Filter`, and 10 `Repair`
quality dispositions. `Mixed` applies to the combined Folketing source because
it contains both reconstruction and continuation families. These are pipeline
triage judgments, not licensing, privacy, provenance, or safety determinations.

The brief category column uses the eight functional categories from the
[DFM-Mimir technical report](https://arxiv.org/html/2608.13517): Danish
instruction and knowledge, English instruction, Sapient mixed, math and
reasoning, Mimir synthetic, agentic and tool use, machine translation, and
science and summarization. Compact labels in the PDF assign each source its
dominant intended category.

The report also contains a remediation table for every `Filter` or `Repair`
source. It gives full eligible row counts, source-specific filtering or repair
steps, and coarse B200-equivalent GPU-hour estimates. Planning ranges are
10,000--40,000 A4B audit decisions per GPU-hour and 2,000--4,000 LLM
repair/regeneration rows per GPU-hour, reflecting substantial prompt-length
variance. Full-row re-audit of the 147,266,048 eligible rows in all 42 affected
sources is estimated at about 3.7k--14.7k B200 GPU-hours. Processing all
35,263,154 rows in the 14 sources marked for LLM repair would add about
8.8k--17.6k B200 GPU-hours. Deterministic converter/filter work is marked
`repair CPU`; the table still estimates the full re-audit cost. Startup,
engineering, human review, and repeat passes after further failures are
excluded.

## Initial source-level finding

The `dfm-agreement/dbc` sample had 73 of 100 rows marked unusable and 97 of 100
rows carrying at least one complaint. Inspection found a systematic conversion
policy mismatch in `dbc-abstracts_0011.parquet`: the prompt always requests a
Danish abstract (`Skriv et kort abstract eller resume ...`) while many source
abstracts and assistant targets are English. Treat this primarily as a converter
language-selection defect. Before retaining these rows, either preserve the
source language in the instruction or restrict the Danish instruction variant
to Danish targets; do not infer that the underlying English abstracts are
intrinsically unusable.

The `ccdv/govreport-summarization` sample had 73 of 100 rows marked unusable.
This is also a conversion defect, but one that breaks grounding rather than
only language selection. `scripts/generate_dfm4_tasks.py` keeps the complete
GovReport reference summary while trimming the report from its beginning to
`3000 - 300 - len(summary)` characters. In the audited sample, prompts averaged
only `1113` characters while targets averaged `1590` characters. The references
therefore routinely summarize facts absent from the model input, and some
targets are longer than the purported concise source summary. Do not retain the
current converted rows unchanged. Regenerate using token-aware admission of
only complete reports that fit the training context, move complete long reports
to an adequate long-context regime, or create genuinely chunk-grounded summary
targets. Merely increasing the prefix truncation limit does not establish that
the target is supported by the retained chunk.

**Resolved 2026-08-28:** the
[GovReport repair](/pages/dfm10-govreport-repair.md) admits only complete
report/summary pairs that fit the exact 4,096-token Gemma rendering, audits
every candidate, and applies a strict grounding filter. It retained 891 rows
and passed an independent published-corpus audit at 199/200 usable with zero
judge errors. DFM10 disables the inherited conversion and samples the repaired
prefix twice.

The `laion/Scientific-Summaries` defect is likewise primarily in the DFM4
converter, not evidence that all source rows are intrinsically unusable. The
converter first concatenates many detailed summary fields; when that does not
fit its 3,000-character proxy budget, it concatenates the executive summary,
key results, and takeaways and hard-cuts the result at 1,400 characters. The
cut is only moved to a word boundary, so it commonly ends mid-sentence. The
current tokenized source has 2,288,807 rows and 1,271,200,636 token IDs. A naive
filter retaining the audit-observed 20% usable fraction would leave about
457,761 rows and 254M tokens; a stricter 8% retention would still leave about
183,105 rows and 102M tokens. That is enough for a useful supporting science
summarization source, but not enough to preserve its current 1.27B-token scale.
Prefer rebuilding targets from individually complete source fields and
admitting only source text that supports them before considering expensive LLM
regeneration.

### Scientific Summaries repaired rebuild and audit

On 2026-08-28, the truncating DFM4 conversion was superseded by the isolated
rebuild in `scripts/repair_scientific_summaries.py`. It writes
`data/converted_sources/scientific_summaries_repaired` without modifying the
old converted source. The converter supports resumable multi-process execution,
applies the Gemma 4 native chat template with the real Gemma 4 tokenizer, and enforces the
4,096-token contract exactly. It uses the complete executive summary as the
assistant target and admits only complete, whole supporting fields from the
structured paper notes; it never character-cuts a target or support field.
Each output Parquet and sidecar metadata file is published atomically, making
the conversion resumable by source file.

The production rebuild began with 16 workers and was safely resumed from its
completed per-file outputs with 64 workers after machine load was checked. The
64-worker phase used about 44 GiB RSS at peak observed steady state and kept all
workers CPU-active; this is the preferred setting on the 384-core, 3 TiB host
when no heavier CPU workload is present.

A 32-file pilot processed 113,793 source rows and retained 112,915 (99.23%). A
stratified Gemma 4 E4B audit then judged ten rows from every pilot file, 320 in
total. It marked 294 rows usable (91.88%), with mean language quality 4.37,
instruction/answer coherence 4.68, grounding 4.23, and training value 4.33.
The pilot artifacts are under
`logs/data_audits/scientific_summaries_repaired_pilot_20260828`.

The production audit is prepared by
`scripts/audit_repaired_scientific_summaries.py` and launched by
`scripts/run_scientific_summaries_repaired_audit_when_ready.sh`. It samples ten
deterministic rows from each of the 4,006 rebuilt files (about 40,060 judgments),
partitions them over eight independently owned E4B vLLM servers, resumes by
stable sample ID, and requires an exact locked merge. A Gemma/vLLM constrained
decoding edge case can emit all four scores and both substantive booleans and
then generate whitespace until the output limit instead of emitting the final
diagnostic enum. The auditor recovers only those fully substantive judgments,
derives the non-authoritative issue label deterministically, marks every
recovered row, and fails closed when any score or decision is absent. The
pilot required this recovery for 6/320 rows. The full audit launcher waits for
both a fully published rebuild summary and genuinely free GPUs and tears down
only servers it owns.

The full rebuild completed the same day with 4,006 Parquet outputs and
3,312,314 retained rows from 3,324,592 inputs (99.631%). Its 8.6 GB output tree
contains no partial files, and the summed Parquet metadata row count exactly
matches `repair_summary.json`. Deterministic exclusions comprised 10,802
non-English rows, 625 incomplete targets, 814 rows with insufficient complete
support, 24 retracted papers, 10 context-overflow rows, and 3 overlong targets;
these mutually exclusive rejection counts sum to 12,278. Another 1,668 rows
had at least one incomplete optional support field; that diagnostic does not
imply rejection when enough other complete support remained.

The production E4B audit completed 40,044 unique judgments with zero missing
or duplicate sample IDs. It marked 36,456 usable (91.04%). Mean language,
coherence, grounding, and training-value scores were 4.39, 4.70, 4.25, and
4.36. Family usability was 2,841/3,180 (`new`, 89.34%), 1,831/2,010 (`old`,
91.09%), and 31,784/34,854 (`titled`, 91.19%). Among 3,588 unusable judgments,
2,290 were primarily incomplete, 1,239 contained unsupported claims, 58 had a
language issue, and one had no issue enum despite the negative decision. The
whitespace-stall recovery was needed for 1,248 rows, including 849 negative
decisions; it preserves Gemma's substantive boolean rather than converting a
failed decode into an acceptance. The merged immutable result is
`logs/data_audits/scientific_summaries_repaired_20260828/scientific_summaries_repaired_quality_audit.jsonl`
(SHA-256 `46600ca3e311bf3c76c3bd818e154be9a1046e5314cf9aacab4d53132477661e`).

This passes the source-level 90% gate narrowly. The residual failures concern
semantic coverage and grounding rather than a high-precision mechanical text
pattern, so another deterministic filter is not justified by the audit. Keep
the repaired source as a supporting science/summarization source; improving it
further requires full-row judging or grounded regeneration, not reinstating
the old character truncation.

### Oliver Kinch DynaWord-instruction repair

The four inherited sources now use a 65,548-row audited replacement that keeps
clean targets, repairs only prompts, and drops damaged targets. Details are in
the
[DFM10 DynaWord instruction repair](/pages/dfm10-dynaword-instruct-repair.md).

## Strategic repair priority

Severity alone is not the repair order. The highest-value DFM10 repair queue is:

**Superseded ownership note (2026-08-28):** GovReport repair was assigned to a
separate workstream and is now complete. The earlier instruction not to modify
`oliverkinch/da-instruct-dynaword*` was superseded later the same day when this
workstream took ownership and completed the repair described below.

1. `dfm-agreement/dbc`: core Danish knowledge/instruction data and a large,
   deterministic converter-language defect; fix prompts to follow target
   language or retain Danish targets only.
2. `nvidia/OpenMathInstruct-2`: central math supervision; retain only
   task-verified answers and normalize the expected final-answer contract.
3. `nvidia/Nemotron-SFT-SWE-v2`: high-profile code/agentic supervision; create
   complete context-aware trajectory windows and validate patch/tool structure.
4. `allenai/Dolci-Instruct-SFT-Tool-Use`: directly relevant to the known
   tool-calling weakness; normalize native schemas, calls, and results and
   reject structurally invalid trajectories. **Resolved 2026-08-28:** the
   [DOLCI tool-use repair](/pages/dfm10-dolci-tool-use-repair.md) retained
   190,736 validated trajectories and passed its E4B gate at 674/700 usable;
   DFM10 now replaces the inherited native conversion with this repaired path.
5. `laion/Scientific-Summaries` and `ccdv/govreport-summarization`: rebuild
   complete, source-grounded summarization examples. **Resolved 2026-08-28:**
   both repaired paths are complete; GovReport contributes 891 strictly
   grounded rows and Scientific Summaries supplies the larger supporting
   corpus.
6. Danish instruction/summarization families (`oliverkinch/da-instruct-dynaword*`
   and `alexandrainst/nordjylland-news-summarization`): enforce complete target
   boundaries and grounding before restoring full weight. **Resolved in design
   2026-08-28:** the four DynaWord-instruction sources use the audited
   prompt-repair replacement. The separate
   [NordjyllandNews repair](/pages/dfm10-nordjylland-news-repair.md) now has a
   headline-aware 73,097-row candidate conversion and a full-corpus 31B
   grounding gate; its old prefix is disabled while the production audit runs.
7. `schneiderkamplab/opus-da-en-permissive`: **In progress 2026-08-28:** the
   [OPUS repair](/pages/dfm10-opus-da-en-repair.md) applies scalable language,
   direction, alignment, rebuild, and post-filter audit gates.

The `da-ar` and `da-uk` translation sources remain excluded unless those
language pairs become DFM objectives. **Superseded 2026-08-31:** Folketing's
90.67% acceptance result did not establish target quality; an independent
5,000-row audit found only 62.5% of error-correction targets usable. Tighten
that family only; see [Residual Quality-Audit Queue](dfm10-residual-quality-audit-queue.md).

### DBC repair design

DBC has no source language field, and the abstract shards are not reliably
language-homogeneous: sampled rows in `0001`--`0010` are mixed Danish/English,
while `0011`--`0019` are effectively English. Detect language per response and
retain only high-confidence Danish and English rows. Use a matching monolingual
prompt and metadata labels for each row. Recast abstract rows as closed-book
bibliographic questions (for example, what a named work is about) rather than
claiming that the model has been given material to summarize when only title,
creator, and subjects are present. Include creator metadata for disambiguation.

Before conversion, normalize and hash targets across all shards. Drop empty or
uninformative metadata, exact/high-frequency boilerplate targets, uncertain or
mixed-language rows, and rows whose response is inconsistent with the title or
subjects. Handle reviews separately, and leave Faktalink/Forfatterweb section
conversion unchanged until separately audited. Publish repaired outputs under
a new prefix, explicitly exclude the old `dbc__*` tokenized outputs, and require
a stratified post-conversion audit with prompt/target language mismatch below
1% and at least 90% usable rows before sampling.

Prompt replacement is performed while rebuilding converted Parquet from raw
DBC JSONL, never by editing tokenized records. `scripts/repair_dbc_sources.py`
detects each response language and selects a natural, semantically matched
question by stable row-ID hash. Examples include `Hvad handler "{title}" af
{creator} om?` and `What is "{title}" by {creator} about?`; the question's own
language establishes the answer language without a robotic language directive.
Missing creators are omitted cleanly. For reviews, the converter first collects
only the referenced work IDs and resolves those IDs while streaming the abstract
shards, then prompts with title/creator; unresolved joins are dropped rather
than exposing an opaque material ID as the only input. Gemma chat tokens are
applied later by the tokenizer and must not be embedded in these instructions.

The repair is isolated under `data/converted_sources/dbc_repaired`. It performs
global normalized exact-target counting over all 21 abstract shards, removes
all targets repeated more than five times as likely boilerplate, retains one
canonical occurrence of lower-frequency duplicates, and keeps only Danish or
English targets with Lingua confidence at least 0.25 and top-language margin at
least 0.03. Outputs are atomically renamed and carry source signatures, filter
settings, and per-reason rejection counts for safe resume. The reproducible
launch command is:

```bash
PATH="/home/ucloud/miniforge3/envs/hrm/bin:$PATH" \
  ionice -c2 -n7 nice -n 10 python scripts/repair_dbc_sources.py --workers 16
```

The converter depends on `lingua-language-detector`, which is declared in
`pyproject.toml` and installed in the `hrm` environment. As of 2026-08-28,
`uv.lock` cannot be regenerated: resolving the project-wide `eval` and `sm100`
extras exposes an existing conflict between vLLM's CUTLASS DSL 4.5.2 pin and
FA4's CUTLASS DSL >=4.6.2 requirement. Do not hand-edit the lockfile; resolve
the optional-extra constraint before refreshing it.

**Superseded 2026-08-28:** do not replace the legacy DBC sampling entries until
a stratified judge audit of the repaired files meets the acceptance criteria
above. The calibrated audit described below subsequently passed that gate, so
the repaired prefixes now replace the legacy abstract and review prefixes.

**Completed 2026-08-28:** the repair converted all 21 abstract shards and the
review file into 22 atomically completed Parquet files. The output contains
9,517,244 rows from 11,878,023 candidates (80.12%) and occupies approximately
1.7 GB at `data/converted_sources/dbc_repaired`. Rejections comprise 1,223,476
high-frequency boilerplate targets, 380,015 targets shorter than 24 characters,
320,436 lower-frequency duplicate occurrences, 301,185 non-Danish/non-English
targets, 78,161 uncertain language classifications, 57,505 reviews without a
resolved titled work, and one empty target. All 137,713 distinct review work
references found in the abstract collection were resolved; the unresolved-row
count covers reviews whose referenced work was absent or lacked a title. The
Parquet metadata row total exactly matches the repair summary.

The repaired-source validation uses an immutable deterministic sample of 100
rows from each of the 22 output files (2,200 judgments total). The prepared
inventory and eight whole-file partitions are under
`logs/data_audits/dbc_repaired_100_per_file_20260828`. Launch with
`scripts/run_repaired_dbc_validation_when_free.sh`: each watcher polls one
physical GPU, takes the cooperative `/tmp/hrm-gpu-N.lock`, rechecks that no
compute PID is present, and only then starts its own E4B vLLM and audit
partition. It never signals a pre-existing GPU process and tears down only its
recorded server PID. The merge validates the exact 2,200 sample IDs under an
exclusive file lock and atomically publishes the merged JSONL and summary.

On 2026-08-28 the first launch exposed and immediately corrected a free-GPU
predicate bug: deleting all whitespace concatenated UUID output lines and made
busy GPUs look free. The false-started validator PIDs alone were terminated;
the eight pre-existing OpenMathInstruct PRM scorers remained alive. The fixed
predicate preserves newlines with `sed`, was verified against all eight busy
GPUs, and detached launcher PID `1000631` is waiting for them to become free.
Do not restore the newline-deleting form.

**Completed 2026-08-28:** all eight validation partitions eventually completed,
the exact 2,200 IDs merged without duplicates or omissions, and all validator
servers were released. Four partitions initially stopped one to three rows from
completion because detailed free-text judge issue strings produced malformed
JSON. A bounded compact fallback schema containing only score integers,
booleans, and enums recovered five affected rows; future launchers retry a
resumable partition up to four times and clean up servers by PID-file lookup
rather than a function-local shell variable.

The first-pass E4B result is 1,908/2,200 usable (86.73%), below the 90% gate.
Per-file usable rates range from 72% (`0008`) and 77% (`0017`) to 95% for
reviews. Mean scores are 4.748 language quality, 4.093 instruction/answer
coherence, and 3.373 training value. Inspection shows material judge
miscalibration as well as genuine defects: DBC works include photographs,
articles, recordings, catalog records, and reviews, but the generic judge often
calls an accurate description of such an object irrelevant because it assumes
the titled work is a book. Other rejected examples are genuinely mismatched or
fragmentary.

**Superseded 2026-08-28:** do not integrate on the raw 86.73% result; first
recalibrate the rubric explicitly for heterogeneous bibliographic works and
rejudge the 292 first-pass failures, retaining the original result as immutable
evidence. That recalibration is now complete.

The calibrated rubric treats a DBC work as a heterogeneous bibliographic object
rather than assuming every title identifies a book. It accepts concise and
telegraphic catalog descriptions, photographs, articles, recordings, reviews,
and labels such as `Summary` or `Subject`, while continuing to reject
wrong-language, unrelated, boilerplate, corrupt, and meaningless targets.
`scripts/rejudge_repaired_dbc_failures.py` rejudged exactly the 292 first-pass
failures using a compact enum/integer JSON schema. It changed 224 rows to usable
and left 68 unusable, yielding 2,132/2,200 usable rows (96.91%). Per-file usable
rates are 93--100%, and reviews reach 99%. This passes the 90% integration gate.

The immutable first-pass and calibrated artifacts are:

```text
logs/data_audits/dbc_repaired_100_per_file_20260828/
  dbc_repaired_quality_audit.jsonl
  summary.json
  dbc_repaired_quality_audit_recalibrated.jsonl
  recalibrated_summary.json
```

The 22 repaired files were tokenized with the Gemma 4 native chat template and
the DFM9 tokenizer into `data/tokenized_dfm10_dbc_repaired`. Tokenization
completed all 9,517,244 rows with zero skips and produced 984,542,417 token IDs.
`data/tokenized_dfm10` now links all 22 tasks under the
`dbc_repaired__dbc-*` prefix. In `data_io/prefix_config_dfm10.yaml`, the legacy
`dbc__dbc-abstracts_*` and `dbc__dbc-reviews` caps are zero; repaired abstract
shards retain the prior cap of 100,000 rows per file and repaired reviews retain
the prior cap of 150,000. Faktalink and Forfatterweb sampling is unchanged.
The union builder records a missing optional addition with count zero, which
allows the repaired DBC source to be integrated while the separately audited
Folketing tokenized tree is not yet present.

### Nemotron SWE repair design

**Superseded 2026-08-28:** the inherited `nemotron_swe_windowed__*`
conversion is not suitable for continued DFM10 sampling. It discarded the
upstream system/tool contract, truncated the issue, and emitted a cumulative
conversation once for every assistant target. The generic tokenizer then
treated every assistant message in each cumulative row as a fresh target. This
multiplied earlier actions, allowed contextless partial actions, and produced
approximately 4.14M sampled rows and 10.4B tokens per epoch from only 46,278
interactive source conversations.

The replacement is `scripts/repair_nemotron_swe_sources.py`. It converts the
32 deterministic source shards with up to 16 CPU workers and writes each shard
through an atomic partial-file rename. The converter:

1. reduces the upstream eight-phase issue boilerplate to repository identity,
   the complete issue description, and a concise implementation request;
2. declares Gemma-native `execute_bash` and `str_replace_editor` schemas;
3. removes obsolete hidden-reasoning `think` calls and their synthetic tool
   acknowledgements;
4. retains only structurally matched executable call/result cycles and turns
   `finish` into an ordinary assistant answer;
5. selects the latest complete cycle suffix that fits the exact Gemma-native
   4,096-token rendering, without clipping prompts, calls, results, or targets;
6. writes one explicit `target_message_index` per row, which the backward-
   compatible tokenizer honors instead of relabeling all assistant history.

Agentless rows comprise several explicitly requested task families, including
file identification, test generation, issue analysis, and patch guidance.
They therefore receive a generic software-task system prompt that defers to the
user's requested artifact and an empty tool list. A first full pass exposed
that the cleanup regex
also matched legitimate headings such as `### 1.1 Code Analysis`; the pass was
superseded before tokenization. The corrected expression removes only explicit
`Phase N` trajectory scaffolding, preserving ordinary numbered prose and code
comments.

**Superseded 2026-08-28:** a second pre-tokenization draft incorrectly
specialized every agentless system prompt to file identification. Manual review
of the first stable audit sample found test-generation rows whose user request
and target agreed with each other but conflicted with that system prompt. The
judge nevertheless marked them usable, so its 1,000/1,000 result is retained
only as evidence that automated scoring cannot replace contract inspection.
The authoritative conversion uses the generic task-following prompt above and
requires a fresh validation and audit. It also deliberately drops source
`reasoning_content` from agentless outputs. The current template does not
render that field for non-tool targets, but removing it prevents audit leakage
and future-template regressions.

The exhaustive validator checks all output rows for role order, one final
target index, native tool schemas, call/result ID pairing, complete history
cycles, and target-kind contracts. The quality gate uses a stable 1,000-row
sample stratified as 400 shell actions, 400 editor actions, 100 final answers,
and 100 agentless answers. Its task-aware rubric treats a complete next native
tool call as valid next-action supervision rather than requiring every target
to solve the full issue. `scripts/run_nemotron_swe_quality_audit_8gpu.sh`
supports an explicit `GPUS` subset and processes the eight logical audit
partitions in deterministic waves, avoiding unrelated GPU services.
**Superseded 2026-08-28:** before hidden agentless reasoning metadata was
removed, the audit payload reached 11,732 tokens and appeared to require a 16K
judge. The authoritative request distribution is 1,050 tokens minimum, 4,037
median, 4,673 at p95, 4,776 at p99, and 4,933 maximum. No request exceeds
8,192 tokens, so the final audit uses an 8,192-token server limit without
truncating or removing any sampled example.

**Superseded 2026-08-28:** converter version 3 admitted 2,466,262 examples from
the two upstream files. The 46,278 interactive conversations produced
2,293,982 native tool-call targets and 44,335 final text responses; 124,167
obsolete `think` actions were removed, 199,554 actions were omitted because no
complete valid context fit 4,096 tokens, and 224 targets were structurally
invalid. Agentless conversion admitted 127,945/209,976 rows and rejected 82,031
only because the complete prompt/target did not fit. The exact rendered corpus
contains 6,105,798,581 prompt tokens and 509,348,483 response tokens before
sampling.

Exhaustive validation passed all 2,466,262 rows in 33 files with no failures.
The final E4B audit completed all 1,000 stable sample IDs with zero judge
errors and marked all 1,000 usable. Mean language/coherence/training-value
scores were 4.99/5.00/5.00 for shell, 4.97/4.98/4.99 for editor, 4.99/5.00/5.00
for finish, and 4.98/4.95/5.00 for agentless. Four agentless rows were labeled
`format_error` but retained as usable; manual inspection found correct file
lists with extra explanation rather than broken contracts. At utilization
0.90 each B200 server exposed a 2,676,677-token KV cache and nominal 326.74-way
8K concurrency, making client concurrency 64 conservative. All audit-owned
servers were released after the atomic merge.

Although structurally valid, version 3 used the interactive tool schemas during
agentless exact-fit admission and then emitted `tools: []`. Its final token
arrays therefore contained 41,838,015 fewer agentless prompt tokens than the
admission accounting, proving that the fit check was unnecessarily
conservative. Version 4 passes the actual per-task tool list into exact-fit
rendering and supersedes the counts and audit result above.

Converter version 4 is authoritative. It admits 2,472,316 examples:
2,293,982 native tool-call targets, 44,335 final text responses, and
133,999/209,976 agentless targets. The interactive exclusions are unchanged:
124,167 obsolete `think` actions were removed, 199,554 targets lacked a
complete fitting context, and 224 targets were structurally invalid. The
correct no-tools agentless fit check recovers 6,054 rows relative to v3 and
rejects 75,977 rows solely because the complete prompt and target exceed 4,096
tokens.

Exhaustive v4 validation passed all 2,472,316 rows across 33 files with zero
failures. Independent mmap summation of the final token arrays exactly matches
conversion accounting: 6,085,072,100 prompt tokens, 512,017,485 response
tokens, and 6,597,089,585 total tokens. A second incremental tokenization pass
rebuilt zero rows. The final audit request distribution is 985 tokens minimum,
4,050 median, 4,687 at p95, 4,793 at p99, and 5,076 maximum; no request exceeds
the 8,192-token judge limit.

The fresh v4 E4B audit completed 1,000/1,000 rows with zero judge errors and
1,000 usable decisions. Overall means were 4.979 language quality, 4.980
instruction/answer coherence, and 4.992 training value. Fifteen judgments used
a non-`none` problem label while still marking the row usable. Manual review
found four real but mild agentless format deviations (correct requested file
lists plus extra explanation), several weak or premature exploratory editor
actions, and several internally contradictory judge labels on otherwise
5/5/5 final responses. This low residual issue rate does not justify rejecting
the repaired source, but it is retained as an audit limitation rather than
reported as perfect data.

Authoritative artifacts are:

```text
data/converted_sources/nemotron_swe_repaired/
data/nemotron_swe_repair/validation_summary.json
data/nemotron_swe_repair/audit_request_lengths.json
data/nemotron_swe_repair/quality_audit_summary.json
logs/data_audits/nemotron_swe_repaired_20260828_v4/samples.jsonl
logs/data_audits/nemotron_swe_repaired_20260828_v4/nemotron_swe_repaired_quality_audit.jsonl
```

The first mismatched-prompt audit is retained with
`superseded_file_identification_prompt` in its artifact names and must not be
used as the acceptance result.

### OpenMathInstruct-2 repair design

DFM10 currently inherits `13,972,791` CoT rows and `11,050,232` direct rows
(`25,023,023` rows in the local Parquet metadata; the audit inventory reports
`25,023,006` eligible rows). They occupy approximately 5.59B and 1.01B
tokenized tokens respectively. These are two condition-specific views of the
same underlying problems, not 25M independent questions. Rebuild from only the
canonical 32-shard HF `train-*` split; `train_1M`, `train_2M`, and `train_5M`
are overlapping fair-downsampled subsets and must not be concatenated.

The source-quality judge's low direct-row acceptance rate is partly a contract
error: a bare target is intentional for `condition=direct` and must not be
rejected merely for lacking a derivation. Accept a direct target only when its
corresponding canonical problem/solution passes answer verification and quality
filtering. Keep CoT and direct outputs distinct and normalize their contracts:
CoT contains a coherent derivation ending in exactly one canonical final answer;
direct contains only the verified expected answer.

Use a staged rejection-sampling pipeline:

1. On CPU, validate schema and lengths, remove exact duplicate pairs and
   conflicting answers for the same normalized problem, apply test-set
   decontamination, extract the generated final answer, and symbolically compare
   it with `expected_answer` using the NVIDIA NeMo-Skills/math-verification
   semantics. The first canonical shard pilot found normalized boxed-answer
   agreement for 432,098/436,650 rows (98.96%); agreement alone therefore does
   not establish reasoning correctness.
2. Score every surviving CoT trace with a math process reward model. Calibrate
   its minimum-step and aggregate thresholds against a stratified human/Gemma
   review before filtering; cap repeated solution variants per normalized
   problem only after scoring so useful solution augmentation is preserved.
3. Use Gemma 4 as a structured judge for calibration, a stratified final audit,
   and optionally the PRM-borderline band. Do not regenerate millions of failed
   traces by default: the source is sufficiently large to discard bad rows.
4. Write paired repaired outputs under a new prefix, tokenize them, and disable
   the inherited `openmathinstruct2__{cot,direct}` prefixes only after the new
   audit passes.

**Superseded 2026-08-28:** the initial budget was 1--4 CPU wall-hours plus
40--160 GPU-hours for PRM scoring. The implemented pipeline is materially
faster on this B200 node. `scripts/prepare_openmathinstruct2_repair.py` verified
all 13,972,791 canonical rows in 54 seconds with 32 CPU workers: 13,959,613
passed, 10,192 failed answer verification, 2,902 lacked required fields, and 84
were duplicate pairs within a shard.

Qwen2.5-Math-PRM-7B is served through vLLM's native
`Qwen2ForProcessRewardModel` pooling/token-classification runner. At GPU memory
utilization 0.90, a one-GPU smoke measured a 2,590,064-token KV cache and 632x
nominal 4,096-token concurrency. Four 20K-row benchmarks established:

| max sequences | max batched tokens | rows/s/GPU |
| ---: | ---: | ---: |
| 128 | 65,536 | 211.7 |
| 256 | 131,072 | 210.2 |
| 512 | 262,144 | **214.2** |
| 768 | 393,216 | 205.4 |

Production therefore uses 512 sequences and 262,144 batched tokens per GPU.
This remains below the measured cache ceiling, sustains about 207--215 rows/s
on each of eight B200s, and leaves approximately 14--15 GiB GPU headroom. The
full pass is expected to cost about 18--20 GPU-hours (roughly 2.3--2.5 wall
hours), not the superseded 40--160 GPU-hour estimate. The commands are:

```bash
python scripts/prepare_openmathinstruct2_repair.py --workers 32
python scripts/score_openmathinstruct2_prm.py \
  --gpus 0,1,2,3,4,5,6,7 \
  --gpu-memory-utilization 0.90 \
  --max-num-seqs 512 \
  --max-num-batched-tokens 262144 \
  --request-batch-size 2048
```

**Superseded 2026-08-28:** the implementation plan above described the final
PRM calibration and build prospectively and treated a full stratified Gemma
audit as optional. The completed pipeline and audit below are authoritative.

The full eight-GPU PRM pass scored all `13,959,613` verified candidates across
32 shards with no failed or partial shards. Aggregate throughput was about
1,681 rows/s and wall time about 2.3 hours. The 55 exactly mapped existing
Gemma judgments selected minimum/mean/final PRM thresholds of
`0.01`/`0.60`/`0.20`, with calibration precision 0.9149, recall 0.9348, and F1
0.9247. At those thresholds, 12,499,203 candidates (89.54%) pass before global
problem-level selection.

`scripts/build_openmathinstruct2_contamination_denylist.py` hashes the exact
production GSM8K test split (1,319 questions) and all seven Hendrycks MATH test
subsets (5,000 questions), yielding 6,319 unique normalized test-question
hashes. The repaired builder removed 13 matching traces. It also performs
global pair deduplication, drops 771 problems with conflicting expected
answers, retains at most the eight highest-scoring traces per problem, and
preserves the original converter's policy of omitting direct variants for
`problem_source=math` and `problem_source=gsm8k` while retaining eligible CoT
traces.

The completed repaired corpus at
`data/converted_sources/openmathinstruct2_repaired` contains 3,803,822 CoT rows
and 3,687,123 direct rows (7,490,945 total) over 581,346 selected problems.
Every CoT target ends in exactly one `Final answer: \\boxed{...}.`; every direct
target is the bare expected answer. `scripts/validate_openmathinstruct2_repaired.py`
scanned all 64 Parquet shards and found no blank prompts/targets, condition
mismatches, box-contract violations, or exact denylist matches. Its durable
result is `data/openmathinstruct2_repair/validation_summary.json`.

The final E4B quality audit is a deterministic stratified sample of 100 CoT and
25 direct rows from each canonical source shard. All 4,000 rows were judged and
merged with zero errors. CoT acceptance is 3,072/3,200 (96.00%), with mean
language/coherence/training-value scores of 4.941/4.638/4.792. Direct acceptance
is 691/800 (86.38%), with corresponding means of 4.994/4.286/3.868. The direct
acceptance rate is a conservative lower bound: inspection found the judge
calling correct intentional bare answers such as `1` and `5` insufficient even
though the audit input declared the direct contract. The audit therefore
passes the repaired source; it is not used as a second row-level filter.

Audit artifacts live under
`logs/data_audits/openmathinstruct2_repaired_20260828`. Detailed judge JSON was
used where possible; 20 rows required the bounded compact-schema fallback, and
the final artifact contains no judge errors. The generic merger now sorts by
`sample_id` when a specialized sample set does not define the optional
`sample_ordinal` field.

The repaired source was tokenized with 16 workers, the DFM9 Gemma 4 tokenizer,
and `data_io/chat_templates/gemma4_native_chat.jinja`. Tokenization completed
all 64 files and 7,490,945 rows with zero skips in 151.1 seconds. It produced
2,140,161,586 rendered token IDs: 1,782,684,161 in CoT rows and 357,477,425 in
direct rows. Response spans account for 1,463,692,290 tokens. The summary is
`data/openmathinstruct2_repair/tokenization_summary.json`, and the tokenized
tree is `data/tokenized_dfm10_openmathinstruct2_repaired`.

`scripts/build_tokenized_dfm10_tree.py --force` linked all 64 repaired tasks
into `data/tokenized_dfm10`. The union currently contains 11,511 task
directories. The separately audited Folketing accepted tree remains absent and
is recorded as zero tasks, so do not treat this union rebuild alone as approval
to sample final DFM10. Sampling disables `openmathinstruct2__*` and enables
`openmathinstruct2_repaired__*` through
`data_io/prefix_config_dfm10.yaml`.

## Code Meta-Reasoning structured repair

On 2026-08-28, inspection showed that the inherited
`allenai_code_meta_reasoning` conversion was not an SFT conversion. It read the
flattened `text` field from
`allenai/code-meta-reasoning-cleaned-final-string-id`, emitted an empty user
instruction, and treated the concatenated problem plus generated target as one
assistant response. This explains much of the source audit's 60% usable rate:
planning documents, difficulty analyses, debugging traces, and unit-test
walkthroughs were judged as though they had failed an invisible code-generation
request.

The authoritative `allenai/code-meta-reasoning-filtered` release contains the
original question, generation prompt, prompt family, reasoning target, and
message boundaries for the same 911,517 examples. The downloader now selects
this structured release. The previously downloaded flattened source is retained
locally at
`data/downloads/datasets/allenai_code_meta_reasoning_flattened_legacy` only for
traceability; it is not an input to the repair.

`scripts/repair_code_meta_reasoning.py` rebuilds the structured source under
`data/converted_sources/code_meta_reasoning_repaired`. It restores an explicit,
family-specific visible task contract and applies the exact Gemma 4 native
template and 4,096-token admission check. Unit-test walkthroughs retain the
provided reference implementation and tests because those are task inputs.
Other families receive a concise contract plus the original coding problem,
without exposing hidden generation annotations.

The deterministic filter excludes two unsafe upstream families:
`code_quality_evaluation_low.txt` deliberately requests bad-style code, while
`code_quality_evaluation_high.txt` hard-codes the unrelated function name
`max_accordion_length`. The same function-name contamination occurs in 96,729
other rows and is removed whenever the question does not request that name.
Missing `<image>` problems, incomplete required structures, and over-4K rows
are also rejected. A second inspection found 125,133 recursive
`code_recovery.txt` examples whose alleged coding problem is actually an earlier
preference-review, planning, difficulty, implementation, or quality-evaluation
meta-task; these are excluded as `nested_meta_task` rather than teaching a
mismatched debugging contract.

The final deterministic rebuild retained 429,301 rows from 911,517 in 72
seconds with 36 workers. Retained family counts are 113,005 difficulty analyses,
3,395 uncontaminated implementations, 92,519 single-recovery traces, 89,095
multi-recovery traces, 53,722 unit-test walkthroughs, and 77,565 planning
documents. It rejected 210,704 unsafe-family rows, 125,133 nested meta-tasks,
96,729 contaminated function names, 26,449 missing-image problems, 22,942
over-context rows, and 259 rows with incomplete required structures. Parquet
metadata sums exactly to the rebuild summary, and no partial outputs remain.

The quality gate is a deterministic sample of 100 rows from each retained
family, 600 total, prepared by
`scripts/audit_repaired_code_meta_reasoning.py` under
`logs/data_audits/code_meta_reasoning_repaired_20260828`. The task-aware rubric
does not require planning or difficulty targets to contain code and permits
explicitly marked buggy intermediate attempts only when the debugging target
ends in a correct complete solution. The eight-GPU E4B launcher
`scripts/run_repaired_code_meta_reasoning_audit_when_free.sh` uses process-owned
servers, GPU availability checks, and `/tmp/hrm-gpu-*.lock`.

**Superseded 2026-08-28:** the audit was initially waiting behind unrelated GPU
processes, and the repaired prefix was intentionally inactive pending its
result. The completed audit and integration below are authoritative.

All 600 judgments merged exactly. The raw usable result is 577/600 (96.17%).
The source-level gate uses the stricter
criterion `usable_for_training && complete && min(all four scores) >= 3`, which
passes 575/600 rows (95.83%). Strict family acceptance is 100% for difficulty,
91% for implementation, 91% for single recovery, 96% for multi-recovery, 99%
for unit-test walkthroughs, and 98% for planning. Mean language, coherence,
grounding/correctness, and training-value scores are 4.935, 4.952, 4.852, and
4.868. Ten responses required the bounded whitespace-stall recovery path.

The judge's `primary_problem` enum is diagnostic: 188 rows combine a non-`none`
enum with a positive usable decision and strong scores. The strict gate uses
the substantive Boolean, completeness, and score fields instead.

The accepted rebuild was tokenized with 16 workers into
`data/tokenized_dfm10_code_meta_reasoning_repaired`. All 36 files and 429,301
rows completed with zero skips in 73.6 seconds. The result contains 667,312,660
tokens: 222,031,799 instruction tokens and 445,280,861 response tokens. DFM10
now disables `allenai_code_meta_reasoning__*` and enables
`code_meta_reasoning_repaired__*`. The per-file cap of 12,412 selects exactly
249,999 rows from the 36-shard retained distribution, preserving the intended
approximately 250K-row contribution rather than 250K rows per shard.

The rebuilt `data/tokenized_dfm10` union contains 11,599 task directories,
including all 36 repaired Code Meta-Reasoning tasks. The Folketing addition is
still recorded as zero tasks in that manifest, so this union state alone is
not authorization to produce the final DFM10 sample.
