---
type: Report
title: DFM12 Multilingual EuroEval Registry
description: Official task coverage, cached-runtime support, access preflight and contamination caveats for nineteen added languages.
tags: [dfm12, euroeval, multilingual, evaluation]
status: draft
last_updated: 2026-10-05
confidence: high
---
# DFM12 Multilingual EuroEval Registry

## 3100K Comparison Snapshot

The [epoch-10/3050K/3100K comparison](../../docs/reports/dfm12-xl-epoch10-3050k-3100k.md)
records fixed-population EMA scores from merged local artifacts. Multilingual-v2
improves from45.62 to65.97 to67.08; standard-suite scores are80.72,78.80,78.85.
English EuroEval HellaSwag and BFCL show unusually large rebounds at3100K;
do not interpret these as uniform capability gains without inspecting outputs.
At the snapshot, Multi-IFEval ET/CA/EL remained active, separate from the
completed fixed headline populations. This is a read-only comparison, not a
new metric definition or W&B backfill.

## Scope And Artifacts

`config/euroeval_dfm12_multilingual.yaml` is an opt-in registry, not an active
scheduler change. It mirrors the ten task categories represented by the existing
20 Danish/English EuroEval groups across NL, NB, NN, SV, IS, FO, PL, DE, FR, ES,
IT, CS, PT_PT, FI, EL, RO, UK, ET and CA. There are **190 coverage entries**,
**163 dataset-backed entries**, **157 unique dataset jobs**, and **27 gaps**.
Each runnable group contains exactly one dataset. Deduplicate execution by
`deduplication_key`; shared Norwegian records do not require repeated evaluations.

The existing English suite already covers all ten categories. Existing DA/EN
groups are retained explicitly; this registry does not silently replace ScaLA-da
with the current official DaLA choice or HellaSwag-da with Winogrande-da.
Task-category parity does not imply identical cultural content or difficulty.

### Danish/English Coverage Check (2026-09-30)

Further instruction-following audit: the installed 18.1 runtime registers
MultiIFEval for all 21 target languages (Portuguese uses `pt`). The remaining
unscheduled counterparts are `multi-ifeval-fr`, `multi-ifeval-es`,
`multi-ifeval-et`, `multi-ifeval-ca`, and `multi-ifeval-el`. Their original
selection favored each language's official/default IFEval task; MultiIFEval
is marked `unofficial=True` there, but is supported. This is a selection
choice, not missing dataset availability. Plain IFEval does not have equivalent
registered variants for all 21 languages. Registration alone is not an access
preflight or proof of matched example difficulty. No tasks added in that check.

**Follow-up implemented on 2026-09-30:** all five passed runtime-auth access
preflight and were added to epoch_10 and every current/future campaign
checkpoint (55 more rows). Each of the 11 checkpoints now schedules all 21
MultiIFEval variants. Existing IFEval tasks are retained. The five panels and
the 21-language table were updated; average definitions remain unchanged.
Receipt: `logs/scheduler/dfm12_XL_epoch11_noidentity/multi-ifeval-complete-access.json`.

Cross-language family inventory of the pinned 18.1 runtime, excluding values:
ScaLA and MultiIFEval have distinct registered variants for all 21 languages.
MultiWikiQA has 20, missing Czech. RAGTruth has 19 distinct target-language
variants and a generic `ragtruth-no`, not distinct NB/NN tests. Zebra Puzzles
(easy and hard) each cover DA, EN, NB, NN, SV, IS, FO, NL, DE (9/21).
Different benchmark families cover sentiment, NER, reading and knowledge in
all languages, but this is task-category coverage, not a matched test.
These catalog checks establish registration, not dataset access or equal
difficulty. No extra families were scheduled by this inventory.

**Superseding the omissions below:** the user requested five DA/EN additions
(`multi-ifeval-da`, `multi-ifeval-en`, `winogrande-da`, `winogrande`,
`multi-wiki-qa-en`) and all available ScaLA variants. Four additional ScaLA
datasets were missing: `scala-nl`, `scala-cs`, `scala-et`, `scala-is`.
All nine passed metadata/revision/data-file access preflight using the pinned
EuroEval runtime credential. Receipt:
`logs/scheduler/dfm12_XL_epoch11_noidentity/euro-additions-access.json`.

`config/euroeval_additions_20260930.json` records these additions;
`scripts/append_euroeval_language_additions.py --apply` idempotently adds them
to the existing campaign under the plan lock. On 2026-09-30 it added 99 jobs:
nine each for epoch_10, steps 2900K through 3300K at 50K intervals, and epoch_11.
Epoch-10 additions use its own EMA export and exact epoch/step metadata. Because
its original teardown had completed, these additions participate in the current
2900K phase's terminal barrier before training resumes. Future additions join
their own checkpoint barriers. All inherit persistent vLLM, batch 32, native
context fitting, and direct W&B sync to the same XL run. Existing scores are
not rerun and frozen average definitions are unchanged.

The nine panels were added to the corresponding existing language sections in
workspace `3fvncok3gjh`, preserving averages first and other panels/selections.
Saved remote spec verified in `logs/wandb_workspace_specs/euro-additions-20260930-084516/`.
The full 21-column table is [EuroEval coverage](../../docs/euroeval-21-languages.md),
regenerated with `python -m scripts.publish_euroeval_coverage`.

Checked the actual step_2900000 plan against the multilingual registry, ignoring
values diagnostics. Danish has nine datasets over eight categories; English
has nine over nine categories (including BFCL-v2 tool calling, displayed under
Math & Code). Neither is missing a category exercised by the other 19 languages.
The new-language registry has no native tool-calling task; Faroese also lacks
summarization and commonsense reasoning.

Benchmark families are not identical: DA/EN use `ifeval-da`/`ifeval`, not the
available `multi-ifeval-da`/`multi-ifeval-en`; they use HellaSwag rather than
the Winogrande variants used for many new languages. The installed 18.1 catalog
also offers `winogrande-da`/`winogrande`, and English `multi-wiki-qa-en` (the
scheduled English reading task is SQuAD). Danish retains EuroEval ScaLA-da
rather than EuroEval DaLA; separately scheduled DFM DaLA is not the same
evaluation wrapper. These are dataset-family differences, not uncovered task
categories. No additional tasks were scheduled by this review.

The newer installed catalog also lists logic and hallucination tasks such as
Zebra Puzzles and RAGTruth. These are outside both the existing DA/EN campaign
and the selected 19-language campaign, not unilateral DA/EN omissions.

Primary evidence is the [official dataset catalog](https://euroeval.com/datasets),
its [crawler index](https://euroeval.com/llms.txt), and
[official source commit 1b801b5](https://github.com/EuroEval/EuroEval/tree/1b801b5f2fa123302a1429030612cb57a41a7e86).
That commit declares version 18.2.0. Its registered selections also exist in
the cached 18.1.0 installation. The `hrm` base environment is **17.3.0** and
lacks sixteen selected dataset names. Do not conflate these environments.

## Runtime Contract

Use the already installed cached interpreter and absolute guard path:

```text
/work/mimir/.home/.cache/uv/archive-v0/xPmpbGur3kEaUYAJ/bin/python /work/mimir/HRM-Text/scripts/euroeval_api_no_flash_attn_guard.py
```

A CPU-only CLI help check succeeded. No package was installed or upgraded.
Explicit dataset jobs use `--dataset NAME`, not a combination with `--language`
or `--task`. Registry `metric_key` is the exact existing logger path. EuroEval
records all configured language labels, so Norwegian keys include `nb_no`,
`nn_no` or `nb_nn_no`, and Portuguese keys can include `pt_pt-pt`. The DFM12
language label remains `pt_pt`; generic Portuguese instruction following uses
`pt` and is explicitly variant-unverified.

The user requested epoch-10 baseline, step-2900000 and future comparisons.
Scheduling and GPU/training handoff remain separately owned. Comparisons need
matched tokenizer/template, EMA choice, scorer version, data revisions and
bootstrap settings. A dataset CLI name alone does **not** enforce the captured
HF revision; the scheduler/preflight must enforce or recheck those pins.

## Access Preflight

`config/euroeval_dfm12_multilingual_access.json` records **157/157 accessible**
sources using the installed framework's normal primary credential path.
Each was resolved with `dataset_info`, rechecked at its commit SHA, and probed
with a data-file HEAD request. No dataset payload or model was downloaded.
No credential is printed or retained in the receipt or registry.

The initial probe used only the user's cached HF token and returned 404 for all
157 sources. This is **superseded as a runtime-access conclusion**, not hidden:
the original receipt is retained as
`config/euroeval_dfm12_multilingual_access_user_token.json` and the diagnostics
are in `config/euroeval_dfm12_multilingual_access_diagnosis.json`.
The installed `data_loading.load_raw_data` first uses the library-provided
read credential and only then falls back to the user token. Both the user and
anonymous organization listings showed only the public `EuroEval/test_dataset`.
The standard HF cache contained twenty historical DA/EN datasets and none of
the new selected sources. No substitute dataset or alias was introduced.

Remote readiness is separate from benchmark membership: `catalog_status`,
`status` and `include_in_average` preserve the declared evaluation population;
`remote_probe` records infrastructure/access results. An infrastructure failure
must not silently shrink the suite or produce an empty benchmark average.

`scripts/preflight_euroeval_dfm12.py --framework-auth` reproduces the metadata
check when run with the pinned interpreter. The two source-inspection/build
scripts are `scripts/inspect_euroeval_dfm12.py` and
`scripts/build_euroeval_dfm12_registry.py`; run the access preflight after rebuilding.

## Gaps And Caveats

- No native tool-calling dataset is registered for any of the nineteen added
  languages. BFCL-v2 remains English; do not relabel it as multilingual evidence.
- Faroese additionally lacks official summarization, commonsense and values
  groups in the selected catalog. CA/CS/EL/RO/UK additionally lack values groups.
- Shared Norwegian datasets are not variant-isolated. Their results are kept
  as diagnostics rather than counted as two independent NB/NN capability scores.
- NorQuAD remains visible but excluded from clean averages. DFM12 authorized
  retaining all 1,886 Wikipedia-training candidates, including 1,071 with
  upstream validation/test passage overlap. The prior review found no exact
  question matches; this neither proves EuroEval-mini answer leakage nor clears
  it. See [Norwegian source history](dfm12-norwegian-dynainstruct.md).
- FLEURS inclusion creates a FLORES-lineage risk. Translation is outside this
  baseline-parity registry; no translation-benchmark clearance is claimed.
- Portuguese MultiIFEval is tagged generic `pt`, not `pt-pt`, in the official
  config. It is retained as a variant-unverified diagnostic, outside clean averages.
- VaLEU is retained but excluded from capability headline averages. Its values
  alignment score is not accuracy. Broad training overlap for the remaining
  benchmarks has not been audited, including Wikipedia-derived tasks.

## Dependencies And Verification

`config/euroeval_dfm12_multilingual_dependencies.json` records available metric
dependencies, including lingua, langdetect, nltk, sacrebleu, seqeval, evaluate,
cloudpickle and scikit-learn 1.6.1. No additional pip dependency was identified
for selected task categories. This is not a full execution test of each scorer.
IFEval initializes NLTK resources in its benchmark cache; punkt_tab is visible
globally, while wordnet/omw-1.4 were absent from default search paths. VaLEU
loads its dataset-side pipeline artifact at runtime. These runtime resource
loads are distinct from package installation and were not performed here.

Offline tests in `tests/test_euroeval_dfm12_multilingual.py` verify the complete
coverage matrix, actual cached dataset/task definitions, metric keys, unchanged
baseline groups, variant/contamination exclusions, metadata-access receipts and
absence of persisted HF credentials. No active plan, GPU or training process
was changed by this preparation.
