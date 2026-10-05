---
type: Research
title: DFM13 Lithuanian and Latvian Sources
description: Baltic text and instruction source shortlist, verification evidence and integration gates excluding DaLA.
status: draft
confidence: medium
last_updated: 2026-10-03
tags: [dfm13, multilingual, lithuanian, latvian, data]
---
# DFM13 Lithuanian and Latvian Sources

## Verified Status Snapshot, 2026-10-04

Read-only inspection of `config/dfm13_sources.json` and the v11 additions
assembly confirms 43 Baltic OPUS pair packages, 25 transformation packages,
and three instruction packages are accepted/uploaded, tokenized, and included
in that assembly. They contain respectively 6,675,232 / 272,045 / 2,708
conversation rows and 675,279,476 / 245,710,270 / 3,367,332 stored tokens.
These are unweighted additions, not a sampled full DFM13 epoch. The three
ready instruction packages are Lithuanian Aya, Baltic EuroBlocks, and the
Lithuanian summarization corpus. Both Wikipedia QA packages and both Latvian
P3 license-specific packages remain on source-fidelity quality hold.

All four transformation families are represented: denoising 81,153 rows,
prefix continuation 112,506, span filling 50,161, paragraph reordering 28,225.
The main ready sources are Wikipedia, ParlaMint, and selected Lithuanian BLKT;
only nine FinePDF examples passed the exact-rights release gate. Wider FinePDF
and standalone Europarl transformation releases are not implicitly admitted.

Synthetic targets remain 70,000 accepted conversations each for LT and LV.
No Baltic synthetic generation client is currently running. The original LV
grounded run produced 7,626 provisional keeps from 12,392 attempts before the
quality stop; other language/family production targets have not been filled.
The later compact re-audit/repair finalizer has completed selection and staged
3,720 LV grounded conversations (2,316,062 rendered tokens), but its receipt
still says admission/publication false. Thus these are not an uploaded or
integrated 70K release. The stale intermediate finalizer counts in earlier
notes are superseded by its terminal receipt, not by unconditional acceptance.

## LV Source-Fidelity Calibration

**Production approval revoked,2026-10-03:** following the failed fidelity
calibration, user sent SIGTERM to owned PID2192702. Drain completed, PID exited,
controller lock released and active jobs reached0. Final12392 attempts produced
7626 provisional automated keeps,3447 valid nonaccepted outcomes,430 invalid
generations,657 invalid reviews,67 generation unknowns and165 review unknowns.
These roughly7K keeps are not final publication acceptance. No records/counters
or targets were removed:140K total,70K/language,20K LV grounded remain unchanged.

Hash-pinned quality receipt and final drain evidence:
`data/dfm13/baltic/synthetic-production-staged-v3/quality-hold-20261003-v1/`.
Original calibration approval was archived; active `calibration-approved.json`
now has empty approved_groups and revoked_quality_hold status. The actual startup
approval loader was verified to reject it. No new process/server signals were
sent by the reviewing worker; other GPU audits remain untouched. The prior
staged-production approval and continue_generation wording in historical holds
are superseded, not deleted. Future start requires a new model/reviewer probe,
fresh blinded source-fidelity/LV assessment and explicit hash-pinned approval;
never automatically restore the old approval.

2026-10-03: `dfm12.baltic_source_fidelity` prepares a separate content-hashed
queue from provisionally accepted LV grounded rows in
`data/dfm13/baltic/synthetic-production-staged-v3`. Initial review and the five
independent holds are preserved. Calibration root:
`data/dfm13/baltic/lv-source-fidelity-calibration100-20261003-v1`.
It includes all5 known holds and95 deterministically sampled other accepted rows.
Full source/spec and conversation are supplied, not prior judgments or hold
labels. All100 fit the actual Gemma tokenizer/template at32768 tokens, with
4096 output reserve, thinking enabled, and no exclusions/truncation. Local
BatchEncoding tokenizer output required an isolated budget adapter;9 tests pass.

Review launched PID2293400, `review.log`, at most8 requests/server on existing
8800-8807 shared26B endpoints. No server lifecycle, production ledger/counter,
upload or acceptance changes. Raw requests/responses and errors remain isolated.
The rubric checks omissions relative to task, scope, modality, unsupported
inference, source facts, instruction following and Latvian fluency. Findings
are model judgments, not native certification or population error estimates.

Separate explicit repair and fresh re-audit phases are bounded to8 repair-labeled
cases. Only assistant contents can change; user turns/tools/source remain fixed.
Each stage records candidate/spec/request and parent-stage hashes. Fresh re-audit
gets source/spec and repaired conversation, not the previous defect rationale.
Known-control recall and qualitative assessment must be recorded before any
proposal to scale; no automatic bulk successor or production admission exists.

Calibration completed:52 strict-valid reviews (42 keep,9 repair,1 reject),36
missing-field contract errors and12 length-limited outputs. A separate sidecar
retains parseable raw verdicts without altering strict statuses:78 keep,9 repair,
1 reject,12 unanswered. Known5 holds:1 detected,2 false keeps,2 unanswered;
end-to-end detection recall1/5, answered-control recall1/3. The model misses the
recommendation-to-commitment shift and excuses garbled/inferred crisis content.
This does not support scaling. See `assessment.md` in the calibration root.
Bounded8 repairs produced3 valid corrected candidates and5 length failures;
fresh re-audit PID2312831 covers the3 only. Corrections still have potential
user-turn language/modality issues; whole-conversation quality is not certified.
All production holds/counters and servers remain unchanged by this work.
Final fresh re-audit:2 valid keeps,1 length failure; all111 diagnostic calls are
terminal. Independent inspection still finds user-turn language defects and
residual wording issues despite the2 keeps. `repair-reaudit-links.json` records
candidate/correction/fresh-review hashes. None is admitted; no automatic scale-up.
The completed assessment recommends against bulk use of this reviewer/policy.

Publication-rights refinement, 2026-10-03: see the focused
[Baltic publication-rights review](dfm13-baltic-publication-rights.md) for pinned
P3 constituent terms, BLKT row-license separation and summary privacy evidence.
Its explicit conditional NewGenLTU grants supersede any generic diagnosis of
missing permission below, not the operational publication holds. Inclusion
approval does not waive upstream conditions; no pipeline gates changed.

For the subsequent eleven-language proposal, see [fourth-wave source research](fourth-language-extension-wave.md)
and [wave history](language-extension-waves.md). Update, 2026-10-03: MIZAN's
OPUS page confirms CC-BY-4.0, superseding the earlier unresolved license
assessment; Matina and TLPC are explicitly owner-approved with their original
license metadata retained.

## Active Preparation Decisions, 2026-10-03

Superseding the initial deferrals below: the owner requests Latvian P3
source/split review and ParlaMint preparation, and all Baltic translation pairs.
P3 remains train-only and audit-gated, not a blanket admission of test/validation
or rank-expanded incorrect targets. ParlaMint supplies structured text, not
parallel translations merely because sittings have similar dates.

The owner explicitly superseded the proposed exclusion of DaLA source articles
and sittings: retain all original source documents, including those underlying
heldouts. Do not import DaLA evaluation labels/pairs. Consequently these sources
are not source-disjoint from DaLA evaluation material.

`python -m dfm12.baltic_opus` prepares discovery and direct candidates in
`data/dfm13/baltic/translations`. It covers 43 requested undirected pairs across
23 languages: LT/LV with the existing 21 languages plus LT-LV. Auxiliary English
legs support the requested English-pivot fallback. Existing reviewed corpus
licenses and quality exclusions apply; missing approved direct supply is marked
for pivot preparation, not silently filled from web-mined corpora.

Per-pair future sampled-token caps inherit `dfm12/config.yaml`: English-LT and
English-LV get T/4 each; LT-LV and each other Baltic-language pair get T/16 each.
T is the sampled repaired English-Danish baseline, both directions together.
Direct and pivot routes share one cap. These are token caps, not row counts or
guaranteed supply; do not inflate scarce pairs with repeats. English bridge legs
are preparation inputs, not additional DFM13 copies of inherited pairs.

CPU downloads and text screening/preparation have completed for the selected HF
sources, ParlaMint and the original DaLA text pools. Native-template preflight
and queue sealing have completed for instruction, transformation and translation
candidates. The synthetic
ledger targets 70K accepted conversations per Baltic language; GPU generation
has not started.

User requested support analogous to the DFM12 nineteen-language expansion.
**DaLA acceptability/correction creation is owned by another thread and is out
of scope here.** The original discovery-only state is superseded by the CPU
preparation section below. Preparation does not authorize training admission:
no GPU generation/audit or final training sampling has occurred.
Live HF cards, repository metadata and viewer size/statistics were inspected
2026-10-03. Counts are upstream supply, not audited acceptance or token counts.

## Recommended Text Sources

| Language | Source | Observed supply | Proposed use and gates |
| --- | --- | --- | --- |
| lt | [wikimedia/wikipedia](https://huggingface.co/datasets/wikimedia/wikipedia), `20231101.lt` | 211,292 articles | Primary reference seed; retain article IDs/paragraphs, remove boilerplate, deduplicate against QA and held-out sources. Card declares CC-BY-SA-3.0/GFDL. |
| lv | Same repository, `20231101.lv` | 123,413 articles | Same; do not mix in `ltg` (Latgalian). |
| lt | [HuggingFaceFW/finepdfs-edu](https://huggingface.co/datasets/HuggingFaceFW/finepdfs-edu), `lit_Latn` | 96,715 documents; 1.818 GB parquet | Educational/scientific breadth after document-language, OCR, duplication and source-rights screening. Database ODC-BY is not a blanket underlying-document licence. |
| lv | Same repository, `lvs_Latn` | 58,471 documents; 0.814 GB parquet | Same; sample broadly across files/domains, not just first shards. |
| lt | [VSSA-SDSA/LT_AI_BLKT](https://huggingface.co/datasets/VSSA-SDSA/LT_AI_BLKT) | 8,438,155 texts; 3,941,476,219 alpha-words; 17.79 GB reported | Strong native-text candidate, with source/type/period/licence fields. Stratify modern prose and domains: news and administrative documents dominate. **Conditional on custom NewGenLTU OpenRAIL-D compatibility**, not an unrestricted CC source. |
| lv | [ParlaMint 5.0](https://www.clarin.si/repository/xmlui/handle/11356/2004), `ParlaMint-LV.tgz` | 50.98 MB compressed archive listed | Structured parliamentary speeches; preserve speech boundaries. Confirm distribution licence at download. Useful for long coherent text, but cap political register. |
| lt | [ParlaMint 2.1](https://live.european-language-grid.eu/catalogue/corpus/8390) | Lithuanian coverage documented; no exact current count established | Candidate for structured speeches. Do not assume latest ParlaMint 5.0 contains LT: its inspected file list contains LV but no LT archive. |
| lv | [RaivisDejus/latvian-text](https://huggingface.co/datasets/RaivisDejus/latvian-text) | Source bundle/scripts; no reliable unified row count | Useful source map to Rainis, Wikisource, Wikipedia, Europarl and Tilde MODEL. Prefer original structured sources; do not run sentence-normalization scripts for paragraph reordering or count this and its components twice. |

Wikipedia and selected educational/native documents should feed the existing
four transformation families: denoising/error correction, prefix continuation,
span filling and paragraph reordering. This transformation correction is not
the separately owned DaLA work. Preserve real paragraph structure; label any
sentence-group fallback honestly. Use train-document splits before deriving
tasks, and stratified source sampling. No raw continuation admission is implied.

Current HF search for `dynaword` found no LT/LV counterpart. This does not prove
none exists privately or under another name; do not invent dataset IDs.

## Instruction Sources

### CPU Preparation Implementation

The 2026-10-03 preparation runs under `data/dfm13/baltic`, using the existing
DFM11 Gemma 4 tokenizer/template, with `enable_thinking=False` and the original
training tokenizer path (no HF tokenizer substitution).

Commands (CPU only; no final training sampling):

```bash
python -m dfm12.baltic_sources_cpu p3
python -m dfm12.baltic_sources_cpu parlamint-lt
python -m dfm12.baltic_sources_cpu parlamint-lv
python -m dfm12.baltic_sources_cpu euroblocks
python -m dfm12.baltic_transforms select --workers 16
python -m dfm12.baltic_transforms make --workers 9
python -m dfm12.baltic_opus
python -m dfm12.baltic_opus_extra
python -m dfm12.baltic_pivots
python -m dfm12.baltic_audit instructions
python -m dfm12.baltic_audit transforms
python -m dfm12.baltic_audit translations --workers 32
python -m dfm12.baltic_audit queue
python -m dfm12.baltic_audit finalize
```

Run from the repository with the `hrm` Python environment and
`TOKENIZERS_PARALLELISM=false`. Start pivots only after both translation
preparations complete; finalize only after all preflight manifests and the queue
exist. Reruns verify candidate hashes. Never rewrite queued inputs behind an
active audit. Dedicated outputs and file locks isolate this work from DaLA,
training and older DFM12 campaigns.

`baltic_audit` builds native-template preflight receipts and a leased SQLite queue
consumable by the existing worker, not a new GPU service:

```bash
python -m dfm12 --root data/dfm13/baltic/audit work audit \
  --endpoint http://HOST:PORT/v1 --concurrency 128
```

That basic compatibility client is capped at 128 requests per endpoint and is
not the recommended full-eight-GPU launch. Use the already proven
`dfm12.european_stage` directly on the same database for production:

```bash
python -m dfm12.european_stage \
  --database data/dfm13/baltic/audit/jobs.sqlite --stage audit \
  --endpoint http://HOST:PORT/v1 \
  --output data/dfm13/baltic/audit/production \
  --concurrency 256 --max-concurrency 1024
```

Supply all eight actual endpoints with repeated `--endpoint` arguments; the
single endpoint above is a command template, not a launched campaign. This
client uses per-endpoint HTTP pools, batched claims/results through one database
thread, and adaptive KV/preemption limits. Payloads are already prepared, so
there is no tokenization/source-conversion feeder in the GPU critical path.
Start at 256/server and allow adaptation up to 1024/server, subject to matching
vLLM sequence capacity and available KV cache. Nominal concurrency is not proof
of saturation: measure actual active requests, queues, KV use, preemptions and
completed decisions after startup.

Planning evidence: [prior audit client measurements](dfm12-audit-client-throughput.md)
record 13,406 completed rows/minute; [DFM12 audit readiness](dfm12-audit-readiness.md)
records 16,120/min over 17 minutes and 23,388.5/min over only 122 seconds. At
5,194,017 jobs those rates imply 6.46, 5.37 and 3.70 hours respectively before
additional retry/tail overhead. Budget roughly 6-9 hours for this audit on eight
otherwise available servers, then replace the estimate with a measured mixed-row
window. This is not a benchmark of the new Baltic client workload; it excludes
the separate 140K accepted synthetic generation campaign and repairs/uploads.

Repeat `--endpoint` for shared servers when subsequently authorized. Requests
specify `google/gemma-4-26B-A4B-it`; use compatible served names. Audits require
32K context (including a 1K output allowance). Preflight checks every supervised
training target against 4K, and the complete audit request against 32K; it rejects,
rather than truncates, overlength examples. The queue deduplicates candidate IDs,
rejects ID/content conflicts and inserts batches transactionally; preparation
does not start inference. Source rights/export holds remain separate from model
quality judgments.

For multi-million-row preparation the writer uses a 512 MiB SQLite page cache
instead of the default 2 MiB; this avoids repeated remote-filesystem reads of
the hash indexes. Transactions retain the existing durability settings. An
interrupted writer resumes from committed candidate IDs. Finalization checks
that preflight manifest hashes still match the queued versions, then creates
claim and expired-lease indexes for the existing audit worker. New worker
connections use these indexes without changing claim ordering or lease semantics.

P3 selection pins `f8d6ecba6fa51521db139c57de9b21870eed9b33`: one canonical
training template each for ARC-Challenge, ARC-Easy, OpenBookQA, QuaRel, QuaRTz,
MRPC paraphrasing, WebQuestions and WikiQA. All other templates/splits are listed
in `p3/selection.json`; no score-evaluation expansion or false rank targets are
admitted. Result: 20,204 candidates after 52 duplicates, not the entire P3 repo.
Original constituent rights still apply; the translated card does not supply a
blanket license. Test and validation files are not downloaded.

ParlaMint supplies 244,835 LT and 162,782 LV speeches; speech/segment boundaries
are preserved. Native transformation sampling scans all source files with bounded
reservoirs, and samples windows throughout Europarl sittings. Flat BLKT records
do not become invented paragraphs; no BLKT reordering candidates were made.
FinePDFs requires matching document language at confidence >=0.9 and mean
education score >=2, then prose/OCR/repetition screening; GPU audit still checks
the original text, not only the mechanically recoverable answer.

The six supplementary named ELRC sources have both parent and v1 license
evidence pinned to OPUS revision `42d4fbe382245487a68e853ca53bea832a41a02a`:
2717/2729 EMEA, 405 President Lithuania, 402 MFA Latvia, 425 Lithuanian
legislation, and 433 Latvian state-related text. No blanket Europarl/DGT/JRC
license approval was inferred. Direct and pivot data share each pair's budget.
English bridge legs are not themselves new DFM13 training components.

English-pivot construction rejects anchors with multiple distinct targets per
language, preserves both original alignments and licenses, and excludes duplicate
direct pairs. It supplements absent or sparse (<1000) direct supply. Exact anchor
matching is **not** a quality verdict; audit must reject mismatched senses and
wrong language variants. It generates no machine translations.

Completed pivot pairs are hash-verified and reused on restart. Native token
counting is deferred to the 32-worker translation preflight rather than repeated
serially inside the English join. All 43 requested pairs have raw candidate
supply after joining: 17,723 direct pairs, 1,702,942 supplementary institutional
pairs and 2,796,599 pivots. These are pre-audit counts, not quality approvals;
Faroese and Nynorsk pair supply remains especially small.

Verified sampled repaired EN-DA baseline: 2,645,005,627 tokens in the inherited
DFM11 epoch-0 selection, from 64 sources in the composition report. Caps are
661,251,406 tokens per English/Baltic pair and 165,312,851 per non-English pair,
both directions and all routes combined. Evidence and report hash are in
`translations/token-budgets.json`. Actual available data can be far below caps.

Synthetic generation remains distinct: 70K accepted per language in six families,
with 120 prepared calibration requests and no fabricated calibration approval.
The generation ledger is sealed; do not mutate pinned production modules while
it is active.

### Completed Native Preflight

All counts below are candidates awaiting model review, not accepted training rows.

| Candidate family | Ready records | Notes |
| --- | ---: | --- |
| LT QA + Aya + summaries | 16,763 | 228 overlength summary records excluded |
| LV Wikipedia QA | 118,505 | 2 overlength records excluded |
| LV P3 | 20,204 | Eight canonical train-only source templates |
| LT/LV EuroBlocks | 179 | 14 LT + 165 LV; inherited expansion did not include these languages |
| Native transformations | 521,106 | All four families in both languages |
| Translation pairs | 4,517,264 | Two directions per record, reviewed jointly; all 43 pairs covered |

Instruction inputs total 155,881; 155,651 remain after the 4K checks. All
transformation and translation candidates pass structural/context preflight.
Maximum complete audit input was 8,665 tokens, below the reserved 32K server
context with a 1K answer allowance. Semantic quality remains for GPU review.

Transformation candidates by language (source shortages are not hidden with
repetition):

| Language | Denoising | Prefix continuation | Span filling | Paragraph reordering |
| --- | ---: | ---: | ---: | ---: |
| Lithuanian | 76,140 | 105,932 | 67,195 | 27,020 |
| Latvian | 68,743 | 78,449 | 63,851 | 33,776 |

The audit-ready receipts live under `data/dfm13/baltic/audit-ready/`; the leased
queue is `data/dfm13/baltic/audit/jobs.sqlite`. `readiness.json` is written only
after queue assembly, source-manifest verification, all-pair coverage checks,
and synthetic-ledger verification. The DFM13 registry records preparation under
`preparations.baltic`, not under accepted `additions`.

Finalized on 2026-10-03: **5,194,017 unique pending audit jobs** across 987
preflight components/chunks (four identical candidate-ID duplicates removed).
All 43 translation pairs have audit-ready records. The readiness receipt and
DFM13 registry now say `cpu_ready_for_audit`. No GPU audits/generation, accepted
data admission, final tokenization, or final sampling were performed.
The optional full SQLite `quick_check` was stopped while I/O-bound after about
five minutes; it did not return a result, so no full-database integrity-pass
claim is made. Counts, source/preflight hashes, synthetic pins and indexed
claim-query behavior were verified separately.

### Original Instruction Discovery

| Language | Source | Supply | Recommendation |
| --- | --- | --- | --- |
| lt | [neurotechnology/lithuanian-qa-v1](https://huggingface.co/datasets/neurotechnology/lithuanian-qa-v1) | 13,848 question/answer pairs | Include after audit. Wikipedia-derived, culturally grounded, CC-BY-4.0 declared in card prose. Narrow factual QA rather than broad chat; verify unsupported claims and context-dependent questions. |
| lv | [martinsu/latvian-wikipedia-qa-gemma3](https://huggingface.co/datasets/martinsu/latvian-wikipedia-qa-gemma3) | 118,507 conversations, about 454K QA pairs | Highest-priority LV SFT candidate. Gemma 3 27B synthetic from October 2024 Wikipedia; CC-BY-SA-3.0 declared. Preserve full multi-turn messages, audit all supervised answers, remove missing-context questions and hallucinations. Card explicitly warns factual inaccuracies; visible preview includes references to absent text. |
| lt | [CohereLabs/aya_dataset](https://huggingface.co/datasets/CohereLabs/aya_dataset), default/train, `language_code=lit` | 916 train rows | Small human-written/edited instruction seed, Apache-2.0. Exclude demographics/test; deduplicate against inherited sources. Current train statistics show no Latvian subset. |
| lt | [VytautoDidziojoUniversitetas/LT_Summarisation_Corpus](https://huggingface.co/datasets/VytautoDidziojoUniversitetas/LT_Summarisation_Corpus) | **2,240 train / 100 test** in viewer | Human-written abstract/extract summaries, four domains. Conditional on NewGenLTU licence review. Default config already combines domains: do not add it and domain configs twice. Card's 2,251 train claim conflicts with viewer; use file counts before admission. Protect test; check medical/privacy material. |
| lv | [matiss/P3-Latvian-translategemma-27b](https://huggingface.co/datasets/matiss/P3-Latvian-translategemma-27b) | Many task/config/split combinations; no unique-row total established | Conditional task-diversity source, not bulk inclusion. Translated using TranslateGemma 27B. Explicit source allowlist, train-only, evaluation-overlap exclusion, source-specific rights, template caps and original-example deduplication required. Keep only correct targets in rank-expanded records. |
| lv | [matiss/P3-Latvian-Full](https://huggingface.co/datasets/matiss/P3-Latvian-Full), [QuickMT](https://huggingface.co/datasets/matiss/P3-Latvian-QuickMT) | Related translation variants | Alternatives for paired quality comparison, **not additive independent corpora**. Full visibly includes test-only configurations and benchmark families. Prefer the version that wins bilingual audit; do not infer quality solely from model name. |
| lt/lv | [utter-project/EuroBlocks-SFT-2512](https://huggingface.co/datasets/utter-project/EuroBlocks-SFT-2512) | Earlier inventory: 14 LT / 165 LV monolingual-labelled rows | Small optional top-up, not an instruction backbone. Counts are the 2026-09-26 snapshot, not remeasured here. Labels/source lineage require checks. |

Do not default to `saillab/alpaca-{lithuanian,latvian}-cleaned`: both cards
explicitly declare **CC BY-NC**, Google-translated Alpaca, and research-only
intended use. `MBZUAI/Bactrian-X` also declares CC-BY-NC-4.0. Their discovery
does not establish compatibility with the planned distribution. New native-
grounded generation is preferable to depending on these older translations.

## Translation And Coverage Gaps

### Existing DaLA Text Preparations (2026-10-03)

Read-only inspection of `/work/mimir/DaLA` found reusable **original text**
already prepared for both languages. Counts below were streamed from the actual
JSONL files, not inferred from the upstream cards:

| Source | Prepared documents | Text characters | Path relative to `/work/mimir/DaLA/la_output/resources/` |
| --- | ---: | ---: | --- |
| Lithuanian Europarl v8 | 403 sittings | 88,972,885 | `lithuanian-extension-v7/lt/europarl-documents.jsonl` |
| Lithuanian Wikipedia | 123,850 articles | 265,831,481 | `lithuanian-extension/production/lt/documents.jsonl` |
| Latvian Europarl v8 | 403 sittings | 89,144,434 | `latvian-extension-v2/production/lv/europarl-documents.jsonl` |
| Latvian Wikipedia | 76,621 articles | 179,380,600 | `latvian-extension/production/lv/documents.jsonl` |

Latest inspected source manifests are `lithuanian-extension-v7/lt/sources.json`
and `latvian-extension-v2/production/lv/sources.json`. Both retain source hashes,
language, provenance and stable document IDs. Wikipedia uses the same pinned
20231101 snapshot shortlisted above; prepared article counts are smaller due
to filtering, not extra independent supply. Lithuanian's recorded length window
is 600--60,000 characters. Source candidates are explicitly not certified clean
gold text.

Europarl preserves paragraphs and groups chapters by sitting date. Prefer these
structured inputs over sentence-normalized mirrors for reordering, span filling,
continuation and grounded generation. Cap parliamentary exposure and split
long sittings into coherent windows; do not treat an entire sitting as one
short-context example. The local receipts retain original Parliament terms and
pending redistribution review, not a blanket CC-BY claim.

**Superseded by the explicit 2026-10-03 owner decision above:** the original
proposal was to coordinate the exact source
document/split assignments with the DaLA owner, including existing frozen
evaluation reservations. Exclude held-out articles and whole held-out sittings,
not just exact corrupted sentences. `dala/pair_pipeline.py:split_for` is one
relevant implementation, but do not assume a default seed reproduces every
existing run's reservations. These four files are source pools, not train-only
exports. No DaLA outputs, profiles, processes or files were modified.

UD treebanks, UniMorph, dictionaries and grammar references also appear in DaLA,
but are linguistic generation resources rather than new broad prose corpora.
Keep that work with the DaLA owner; no duplicate corruption pipeline is needed.

Extend the existing OPUS preparation to `en-lt`, `en-lv`, and direct `lt-lv`
where available. Prioritize institutional/document-aligned Europarl, DGT,
JRC-Acquis, EUbookshop and eligible Tilde/ELRC subsets over web-mined pairs.
These are **candidate families, not verified pair/version admissions**: query
the OPUS inventory and apply existing explicit licence decisions per release.
Do not call all EU material CC-BY by default. Do not add ParaCrawl, CCAligned,
NLLB or subtitles simply to inflate counts. Retain original alignment IDs,
quality/length checks, bidirectional dedup and benchmark exclusions.

Both languages still need broader instruction following, reasoning/math/code,
constraint following and grounded multi-turn/tool interactions. Reuse the
DFM12 six-family synthetic pipeline with native source seeding and independent
review; do not equate LV's 118K topical QA conversations with balanced coverage.
Initial planning target: **70K accepted diverse synthetic conversations per
language**, expandable after quality calibration (a proposal, not a launched
campaign). Target allocation and transformation volumes should follow measured
source/token yield rather than repeating scarce rows to match a nominal size.

All adapters must output structured messages rendered by the existing Gemma 4
tokenizer/template, not translated ChatML or Llama control tokens. Name the
intended language explicitly in task prompts; keep lt/lv distinct. Preserve
tool definitions/results only when actual evidence exists. Do not import
foreign assistant identity. The earlier suggestion to exclude DaLA source
fingerprints is superseded; do not edit the DaLA owner's datasets or pipelines.

## Reproducibility Snapshot

Inspected HF revisions (pin at preparation; no sources admitted by this page):

| Repository | Revision |
| --- | --- |
| wikimedia/wikipedia | `b04c8d1ceb2f5cd4588862100d08de323dccfbaa` |
| HuggingFaceFW/finepdfs-edu | `9cfabe2127faca99b3d5c4dc6d1fcb397399ebde` |
| VSSA-SDSA/LT_AI_BLKT | `4fa6c3894fd9f1f9f8db773ae844e126fa61f61d` |
| neurotechnology/lithuanian-qa-v1 | `a2c5072aa6a01ed44660fafd70b59214563c73f6` |
| martinsu/latvian-wikipedia-qa-gemma3 | `ed202b8334890985f0879eeb48fff84565d890aa` |
| CohereLabs/aya_dataset | `f9ea04583f02a8f86404ff6c58bf75fe637df8a2` |
| VytautoDidziojoUniversitetas/LT_Summarisation_Corpus | `42ff26844cd2b3d26880f631ab498da1568cda15` |
| matiss/P3-Latvian-translategemma-27b | `f8d6ecba6fa51521db139c57de9b21870eed9b33` |
| matiss/P3-Latvian-Full | `5a4b4f8bba21f82b1205178fc13cde4d77a21ae7` |
| RaivisDejus/latvian-text | `4787c0aae32f0ba7b9e0fba8944292f55a27340e` |

## Audit Launch After XL 3,081,500 (2026-10-03)

The requested ephemeral was validated using the sidecar, DCP metadata, and all
shard byte extents, then hardlink-preserved under
`checkpoints/preserved/dfm13-audit-3081500`. The exact XL torchrun was stopped;
the existing `dfm12_XL_epoch11_noidentity` scheduler remains soft-stopped. Its
3,100,000 training row is pending with resume tag `ephemeral_step_3081500` and
unchanged training/W&B settings. Do not clear the stop while audits own the GPUs.

Shared servers: `logs/dfm13/baltic-audit-3081500/servers`, ports 8800-8807,
Gemma 4 26B A4B, memory utilization 0.95, maximum sequences 1,024, context
32,768. Both `dfm13-gemma4` and the canonical model ID are served. The existing
owned-server supervisor is reused; clients do not tear down shared servers.

The Baltic audit uses `dfm12.european_stage`, gated on all eight model endpoints,
with initial/maximum client concurrency 384 per endpoint. Logs and telemetry
are under `logs/dfm13/baltic-audit-3081500/{client.log,client/}`. The pending
jjzha audit also resumes at 384 per endpoint with a separate ledger and
`jjzha.log`; combined caps are 768 requests/server while both are active.
This starts auditing only, not unapproved bulk synthetic generation.

Verified all eight endpoints ready and both audits issuing successful requests.
The initial Baltic window completed 2,875 reviews with zero request errors;
combined server activity was 727-767 requests, KV occupancy 92-96%, and zero
preemptions. The existing adaptive pressure control reduced Baltic concurrency
from 384 to 346 on high-KV endpoints; 384 remains its ceiling. Startup now reuses
equivalent queue indexes regardless of their names, avoiding a redundant full
queue scan. Fresh-queue and equivalent-index initialization were both tested.

Performance follow-up: `serve_dfm13_shared.py` inherits `--enforce-eager` from
`dfm12.diagnostic_server.command_env`, originally a bounded TP2 co-resident
diagnostic launcher. Its full-GPU overrides do not remove that flag. Current
server logs confirm compilation and CUDA graphs are disabled. No requirement
for eager mode in this bulk campaign was found in the reviewed runbooks;
benchmark graph-enabled serving before treating eager mode as necessary.

Superseded by explicit user instruction on 2026-10-03: restart all eight servers
without benchmarking first. The bulk launcher now removes the inherited
`--enforce-eager`, retaining vLLM compilation/CUDA-graph defaults. Old clients
were stopped before owned-server teardown; Baltic flushed and released its
leases, and jjzha resumes only unfinished ledger rows. Replacement server logs
are in `logs/dfm13/baltic-audit-3081500/servers-compiled`; clients are gated on
all eight endpoints and use `client-compiled` / `jjzha-compiled.log`, with the
same databases and 384/server caps. Training remains paused.

Restart verified: all eight endpoints ready, compilation mode `VLLM_COMPILE`,
graph mode `FULL_AND_PIECEWISE`. GPU0 compiled in 72.84 seconds and captured
graphs in 10 seconds using 0.50 GiB. Both clients relaunched successfully;
the Baltic client committed 1,066 additional reviews in its initial startup
window. GPU utilization snapshot was 61-100%, with no new preemptions. This
startup snapshot is not a steady-state throughput benchmark.

Combined-budget update (2026-10-03): the two independent 384/server clients
could together submit 768 and filled KV cache. The authorized replacement uses
one fixed combined ceiling of 384/server: Baltic initial/max 256 plus jjzha 128.
Jjzha now has continuously replenished workers with bounded keyset paging,
not a global request-batch barrier. Baltic retains downward pressure control.
Servers are unchanged. Logs: `client-budgeted.log` and `jjzha-continuous.log` in
the same run root. This is a static allocation; unused jjzha slots are not
automatically borrowed. Completed reviews remain untouched, and the jjzha
manifest records the dispatch transition and new client hash.

User correction, 2026-10-03: the 384 budget was intended for Baltic alone, not
both clients combined. Supersedes the 256/128 allocation above: Baltic initial
and maximum concurrency are restored to 384/server, jjzha remains 128/server,
combined ceiling 512/server. Only Baltic is drained/restarted; servers and jjzha
remain running. Baltic log: `client-384-jjzha128.log` in the same run root.
Existing Baltic adaptive downward pressure control remains enabled.

## Remaining EuroEval Language Coverage

Compared on 2026-10-03 against [EuroEval's language index](https://euroeval.com/llms.txt):
after counting the 21 DFM12 language variants and planned Lithuanian/Latvian
additions, ten EuroEval languages lack a dedicated DFM13 support programme:
Albanian, Belarusian, Bosnian, Bulgarian, Croatian, Hungarian, Luxembourgish,
Serbian, Slovak, and Slovene. Incidental multilingual-source rows do not establish
support. Lithuanian/Latvian remain under audit, not yet training-ready; Norwegian
Bokmal and Nynorsk are counted separately locally but grouped on EuroEval's site.

### OPUS Availability Check (2026-10-03)

Read-only [OPUS API](https://opus.nlpl.eu/opusapi/) query with `source=en`,
`target=<language>`, `preprocessing=moses`, `version=latest` confirms direct
English pairs for all ten missing languages and Persian/Farsi (`fa`). Examples
below are raw alignment counts, not deduplicated/approved training rows:

| Language | Corpus | Alignment pairs |
| --- | --- | ---: |
| Albanian | SETIMES | 227,516 |
| Belarusian | Tatoeba / translatewiki | 7,061 / 24,240 |
| Bosnian | SETIMES | 138,387 |
| Bulgarian | DGT | 4,318,892 |
| Croatian | DGT / SETIMES | 1,416,461 / 205,910 |
| Hungarian | DGT | 5,799,885 |
| Luxembourgish | translatewiki / Tatoeba | 51,762 / 420 |
| Serbian | SETIMES | 225,169 |
| Slovak | DGT | 5,799,714 |
| Slovenian | DGT | 5,801,309 |
| Persian | MIZAN / TEP / GlobalVoices | 1,021,597 / 612,086 / 10,321 |

No new sources are admitted by this inventory. Continue preferring curated,
non-web-mined bitexts; check release-specific licensing. SETIMES OPUS documentation
explicitly labels CC-BY-SA. The API did not return licenses. Persian MIZAN/TEP
need source-rights review; TED, subtitles and religious corpora are not automatically
within our existing license/quality policy. tico-19 has 3,071 en-fa pairs but is
evaluation-oriented and must not be casually folded into training. For Belarusian
and Luxembourgish, avoid filling quotas with generic web-mined pairs by default.

## Independent QA Content Check, 2026-10-03

The read-only follow-up to P3 inspected 20 published QA conversations (44
assistant turns): five accepted originals plus five accepted repairs per LT/LV,
selected at deterministic spread ordinals of sorted original ledger IDs.
Material defects: LT 3/10 (all repaired), LV 6/10 (three originals, three repaired).
Two additional LV repairs have unresolved source/biographical concerns, not proven
hallucinations; three cases have minor/uncertain details and six have no observed
material defect. Deliberate repair oversampling means these are NOT corpus error
rate estimates or factual certification of the remaining rows.

LT failures include swapping the Trakai village near Švenčionys for the
Galvė-lake town, malformed trade terminology, and dropping
the Lithuanian extent of historical Žiemgala. LV includes an invented Sassuolo
career claim, league-tier confusion and broken Latvian explanations; partial
repairs also leave errors in earlier assistant history. Earlier-history errors
are prompt exposure, not necessarily final-target loss. All sampled machine
audits nevertheless gave keep=true and 5/5/5; these labels are not independent
semantic verification. Local upstream rows contain QA/messages, not the original
Wikipedia articles, limiting grounding certainty.

Full exact IDs, source/publication hashes, messages, original-to-repair deltas,
manual case dispositions and bounded external references:
`docs/reports/baltic-qa-independent20-20261003/report.md`.
Machine-readable bindings: `review.json`, `evidence.json`, `receipt.json` in the
same directory. All four source/publication input files were rehashed unchanged.
No registry, eligibility, published artifact, pipeline or worker changes were made;
eligibility decisions remain with the owner. Do not clear holds based on the
old generic keep verdicts or automatically admit another unconstrained rewrite.

Superseded operational state, 2026-10-03: the owner subsequently authorized and
applied [source-wide QA quality holds](dfm13-baltic-qa-quality-holds.md) to both
components. Published data/pins remain unchanged; warning-only Hub cards and
unsubmitted source-aware 31B packets are documented there.

Related: [DFM13 plan](dfm13-plan.md),
[previous source inventory](european-language-expansion-sources.md),
[DFM12 preparation](dfm12-european-cpu-preparation.md).
