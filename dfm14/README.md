# DFM14 Preparation and Auditing

CPU preparation is isolated from live DFM13 training. Explicit audit/calibration
commands use supplied shared vLLM endpoints; they do not start servers, publish
datasets, change training samples or touch `/work/dfm/DaLA`.

Current additions, exact counts and remaining gates are documented in
[the OKF operational page](../wiki/pages/dfm14-additions-audit-expansion.md).
`python -m dfm14.additions_campaign` chains prepared Asian and English additions
through CPU validation, teacher-tokenizer readiness and separate resumable audits.
Original source-audit contracts remain pinned; extended evidence uses the module
named in `readiness.json`. Do not interpret automated calibration accepts as
production approval: v6 still failed six exposed negative controls.

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  /home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm14.prepare \
  --root data/dfm14/cpu-preparation-expanded \
  --workers 320 --download-workers 8 --rows-per-file 20000 \
  --download-root data/dfm14/cpu-preparation-v1/downloads

python -m dfm14.status --root data/dfm14/cpu-preparation-expanded \
  --output data/dfm14/cpu-preparation-expanded/coverage.json
```

The current root is `data/dfm14/cpu-preparation-expanded`. The 2K/file v2
calibration pass completed; expanded preparation supersedes its selected rows,
so never concatenate both. The first exploratory v1 pass is retained separately
for diagnostics, **not** a training/admission source.
Reusing its download directory avoids fetching unchanged pinned payloads again.

## Bounds and Safety

- 320 is the CPU process ceiling, not a target for network concurrency.
- Eight download threads; one internal Arrow/tokenizer/BLAS thread per worker.
- At most eight hash-selected payload files and 2 GiB downloaded per component.
- Deterministic bottom-k row samples over entire selected files, now 20,000
  rows per file after explicit language and heldout filtering. These are
  source/adapter/quality candidates, not final accepted production quotas.
- Keep full source provenance, hashes and language-filter outcomes. Context
  never substitutes for an answer; no assistant response truncation.
- Unknown formats, tools, explicit foreign reasoning tags and embedded
  templates are held for adapters, not silently flattened or admitted.
- One output directory/lock per source file and one parent manifest writer.
  Atomic outputs are trusted only with a matching final receipt.
- Resume repeats failed/incomplete files and verifies completed candidate
  hashes. Changed settings require a new root; do not mutate live receipts.

## Outputs

- `configuration.json`: worker/selection bounds, tokenizer/template hashes,
  source registry and implementation hashes.
- `sources/*/source-lock.json`: HF revision pins, selected files and source card.
- `file-plan.json`: bounded file work plan.
- `candidates/*/*/candidates.jsonl`: instruction conversations or document seeds.
- `candidates/*/*/transforms.jsonl`: denoising, prefix continuation, span filling,
  paragraph reordering; original evidence and exact reconstruction metadata.
- `needs_adapter.jsonl`: up to three diagnostic rows per structural hold reason.
- `receipt.json`: input/output hashes, schema counts and candidate/hold counts.
- `progress.json`: parent-owned stage, counters and explicit blocked sources.

The native training tokenizer/template are taken from the current DFM13
metadata. A prefix-compatible chat smoke must pass before launch. Do not use
the raw Gemma serving Jinja as a drop-in training renderer.

## Grounding and Transformations

For all sixteen languages the registry uses native Wikipedia. Broad web crawls,
including web-PDF corpora, were removed by owner decision on 2026-10-06.
Selected educational/institutional corpora are preferred supplements. Source
cards are retained for review before admission/publication. Historical campaign
configuration/progress files describe the original pass; after cleanup use
completed surviving receipts via `dfm14.status` for current coverage.

Windows retain source paragraphs and exact sentence spans; CJK sentence
boundaries and grapheme-safe corruption avoid whitespace-only or case-swap
assumptions. Reordering requires at least three real source paragraphs: no
fabricated paragraph breaks. Native prompt wording still needs calibration.
All records explicitly carry `training_ready=false` and
`admission_authorized=false` until language/semantic audit, benchmark exclusion,
inherited/cross-source deduplication and rights review are complete.

## Not Yet Production-Complete

Language coverage in a registry is not measured unique accepted coverage.
Use `dfm14.status` to distinguish actual candidate counts, source diversity and
gaps. Gated repos, unsupported formats and absent language partitions remain
explicit holds. Parallel translation pairs, synthesis calibration/quotas,
full-source expansion, audits/repairs and final sampling are separate stages.

## Curated Supplements and GPU Handoff

The completed supplemental sources are Wikisource for fourteen languages,
EUR-Lex-Sum **training documents only** for Irish/Maltese, and Irish/Maltese
EUbookshop publications via OPUS. These are specifically identified reference
and institutional collections, not broad web crawls. EUbookshop preserves XML
document/paragraph provenance and records Moses detokenization; review OCR and
spacing quality rather than assuming source cleanliness. Invalid XML is held.

Run CPU preparation in `hrm`; it additionally needs `defusedxml` (installed
with `uv pip`), `sacremoses`, and the existing tokenizer/Arrow/HF dependencies.

```bash
python -m dfm14.prepare --curated-supplements \
  --root data/dfm14/curated-supplements --workers 320 --rows-per-file 20000
python -m dfm14.institutional --root data/dfm14/institutional-supplements-v2
python -m dfm14.prepare_gpu \
  --root data/dfm14/cpu-preparation-expanded \
  --root data/dfm14/curated-supplements --output data/dfm14/gpu-ready-v1
python -m dfm14.prepare_gpu --root data/dfm14/institutional-supplements-v2 \
  --output data/dfm14/gpu-ready-institutional
python -m dfm14.merge_audit --root data/dfm14/gpu-ready-v1 \
  --root data/dfm14/gpu-ready-institutional --output data/dfm14/gpu-ready
python -m dfm14.generation_prepare --audit-root data/dfm14/gpu-ready
python -m dfm14.readiness
python -m dfm14.report
```

Final audit inputs: `data/dfm14/gpu-ready/{manifest.json,jobs.tsv}`. The
intermediate roots are not the final selection. The merger rechecks checksums,
removes cross-campaign duplicates and holds unresolved Wikimedia markup.
Generation calibration has 100 attempts per language/family, **not** a production
quota. The six families reuse native v4 contracts with an isolated language map;
OpenHermes seeds come only from `schneiderkamplab/dfm8-openhermes-en`.

The audit CLI never starts servers or claims GPUs. After an explicit GPU
handoff, supply healthy Gemma4 26B-A4B endpoints advertising at least 32K:

```bash
python -m dfm14.audit --root data/dfm14/gpu-ready \
  --endpoint http://127.0.0.1:8800/v1 --concurrency 64
```

Repeat `--endpoint` for each available replica. Only one audit controller may
own the output root; per-chunk locks allow dynamic work sharing. Results use
durable per-chunk journals with partial-tail recovery and content hashes.
Three failed attempts become explicit infrastructure/invalid-review results,
never semantic rejection or acceptance. Repairs and generated conversations
need a new audit before admission. Do not run an independent generation client
against the same endpoint without a combined concurrency budget.

`ready_for_gpu_audit` does not mean training-ready: inherited/benchmark
decontamination, semantic decisions/repairs and accepted-only export remain
required. Separate DaLA, parallel pairs and full-scale synthetic production are
not silently declared complete by this bounded preparation campaign.

## Synthetic Quality Recalibration

The accepted-v2 spot inspection found material false accepts. Bulk six-family
generation stays held. `synthetic_quality.py` wraps, rather than changes, the
historical v4 native assembler; `synthetic_review.py` checks every assistant
message (including calls), preceding user intent and sources without seeing
prior verdicts or the generator's authorization claim. Fail/uncertain never keep.

Fixed-count summaries use separate answer parts, assembled without commentary.
Math prompts retain literal boxed notation; reference code/answers remain CPU
owned. Action examples require an exact user authorization quote as metadata;
semantic review must independently establish actual permission. The quote alone
is not authorization. Source filtering holds category-only/non-prose windows,
obvious markup and damaged encoding; it is conservative, not a factual verifier.
No existing accepted text is silently trimmed or retrospectively approved.

```bash
python -m unittest discover -s tests -p 'test_dfm14*py'
python -m dfm14.quality_calibration_prepare \
  data/dfm14/generation-quality-calibration-v4 --per-group 2
python -m dfm14.calibrate \
  --root data/dfm14/generation-quality-calibration-v4 \
  --output data/dfm14/quality-calibration-v5 --concurrency 16 \
  --endpoint http://127.0.0.1:8800/v1
python -m dfm14.review_regression data/dfm14/review-regression-v5 \
  --endpoint http://127.0.0.1:8800/v1
```

Repeat endpoints for all eight replicas; account for the active source audit's
256 slots/server. The diagnostic adds 16 calibration slots plus two regression
slots/server, not another full production workload. Preparation refuses overwrite;
code-pinned calibration outputs refuse changed settings. Use a fresh output root
after changing contracts. These are diagnostic revisions, not dataset versions.

The first bounded-EBNF v4 experiment yielded punctuation-only fields and was
stopped. Its evidence is preserved. v5 uses JSON-object transport (as the existing
source audit does), explicit output layouts and full CPU schema validation.
Four live generation smoke cases assembled successfully before the 192-case
calibration and 18-case exposed review regression launched. Neither launch is
evidence of calibration success. Results and raw requests live under the roots
above; logs are under `logs/dfm14/shared-gemma-20261007/`.

No blanket production approval, native-speaker certification, automatic repairs
or Gemma 31B comparison has been performed. Review fresh accepted examples before
issuing any hash-bound language/family admission. In particular, the prose gate
does not resolve internal source contradictions; the semantic review must do so.
