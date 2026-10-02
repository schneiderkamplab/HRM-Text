---
type: Runbook
title: Versioned Multilingual Headline Populations
description: Opt-in complete-coverage averages with explicit metric origins and units, separate from legacy headline scores.
status: draft
confidence: high
last_updated: 2026-10-01
tags: [evaluation, multilingual, metrics, wandb]
---
# Versioned Multilingual Headline Populations

## 2990K Matched Smoke (2026-10-01)

User requested the same 63 manually authored prompts on `step_2990000` EMA.
Dedicated export: `exports/dfm12_XL_step2990000_ema_smoke_transformers`.
Run directory: `logs/eval/dfm12_XL_2990k_multilingual_smoke`.
CPU export mapped 259 tensors with none dropped; training-tokenizer parity
passed, Mistral regex fix disabled. The export loader defaults to CUDA and
allocates optimizer/EMA state, so exporting alongside training initially OOMed
on GPU0. Run export with `CUDA_VISIBLE_DEVICES=''` to perform it on CPU instead.
Training remained running; no checkpoint, scheduler or W&B settings changed.

The smoke uses the same eight-worker, batch-one, BF16/SDPA, greedy, PrefixLM
and token-budget settings as 2930K below. Report scripts now accept checkpoint
labels; new checkpoint findings must be supplied rather than reusing the old
hard-coded qualitative conclusions. Four LaTeX renderer tests pass.

Completed all 63 responses and direct qualitative reviews. Report:
`docs/reports/xl_2990k_multilingual_smoke_review.pdf` (21 pages), with Markdown,
JSON and LaTeX companions. Nineteen corrections clearly succeed; Polish fails
and Finnish remains a context-sensitive probe with an unrequested tense change.
Summary task scores: eight strong, twelve usable with reservations, one major
problem (Polish changes April to February). Stories remain weak: seven hit the
token cap, and none receives a strong task score. These are single-example
diagnostics, not statistically reliable language rankings. No W&B logging.

## Read-only Task-family LaTeX Report (2026-09-30)

### GEC Sentence-pair Companion

A separate manually composed smoke prompt set is stored in
`docs/prompts/multilingual_three_tasks_21_languages.jsonl`: 63 rows, exactly
three tasks per language (`grammatical_error_correction`, `creative_writing`,
`summarization`), with `language`, `task`, and `prompt` fields. Codex authored
these directly, without delegating to another model or generation service.
They use parallel scenarios across languages: a deliberately erroneous
sentence, an astronaut duck story, and a two-sentence summary of a supplied
library-hours paragraph. These are informal smoke probes, not native-speaker
validated benchmarks or scored evaluation additions; no inference was run.

The no-inference status above is superseded for the 2930K smoke: on 2026-09-30
all 63 prompts were run against `step_2930000` EMA from
`checkpoints/dfm12/XL-from-dfm11-epoch10-noidentity`. The dedicated export
`exports/dfm12_XL_step2930000_ema_smoke_transformers` uses `hf_split` weights
(259 tensors, no dropped/missing/unexpected weights), unlike the production
vLLM packed layout. The campaign's `validate_export_tokenizer` verified raw
training tokenizer/template parity and disabled the Mistral regex fix.

`scripts/run_multilingual_prompt_smoke.py` used Transformers BF16/SDPA,
PrefixLM token types of one on the prompt, batch one, greedy decoding, no
system prompt/thinking/repetition penalty, caps of 768 new story tokens and
384 otherwise. Eight workers used roughly 4.5 GiB each alongside training,
with an 8 GiB PyTorch allocator cap (not a total-device reservation).
All workers exited; only training processes remained. No scheduler/W&B changes.

Raw responses: `logs/eval/dfm12_XL_2930k_multilingual_smoke/responses.jsonl`.
Direct Codex judgments (not a separate judge model):
`docs/reports/xl_2930k_smoke_judgments.json`. The renderer
`scripts/build_multilingual_smoke_review.py` combines them into
`docs/reports/xl_2930k_multilingual_smoke_review.md` and a JSON companion,
with all prompts, verbatim outputs, per-response task/language/fluency scores
and rationales. Eighteen corrections clearly succeed; Icelandic/Faroese leave
the error unchanged and the Finnish numeral-agreement probe is context-sensitive.
All summaries contain two sentences, with 14 strong task-success judgments.
Twelve stories hit the cap with visible degeneration; none earned the strongest
overall task-success judgment. Short-form competence does not imply fluent
long-form generation. These results do not prove a regression: no matched
vLLM or earlier-checkpoint replay was run, and linguistic judgments are not
native-speaker certification. The response cap and greedy decoding are part
of this observation, not hidden scoring assumptions.

`scripts/multilingual_smoke_latex.py` renders the reviewed JSON into a
one-language-per-page LaTeX report. Each page contains all three full prompts,
verbatim responses, separate task/language/fluency scores and written judgments.
No content is truncated; long pages scale down and long repeated strings gain
invisible break opportunities. Use `--paper a3` for more readable large pages.

```bash
python scripts/multilingual_smoke_latex.py \
  --input docs/reports/xl_2930k_multilingual_smoke_review.json \
  --output docs/reports/xl_2930k_multilingual_smoke_review.tex
lualatex -interaction=nonstopmode -halt-on-error -output-directory=docs/reports \
  docs/reports/xl_2930k_multilingual_smoke_review.tex
```

The A4 report compiled to 21 pages on 2026-09-30. Tests check complete task
coverage, LaTeX escaping, page breaks, scores and preservation of looped text.

`scripts/gec_examples_report.py` samples ten distinct corrupted/reference pairs
per language from the Inspect archives referenced by completed GEC merges.
It excludes unchanged controls, uses stable seed-42 SHA256 ranking, and never
uses model answers. Conflicting corrections or missing languages fail closed.
Its JSON sidecar retains sample IDs, archive members and source metadata.
References are dataset labels, not a fresh linguistic audit. No sentence is
truncated; unusually long tables are scaled to fit one language per page.

```bash
python scripts/gec_examples_report.py \
  --root logs/dfm_evals/dfm11_XL_epoch10/epoch_10 \
  --root logs/dfm_evals/dfm12_multilingual/epoch_10 \
  --output docs/reports/gec_examples_21_languages.tex
lualatex -interaction=nonstopmode -halt-on-error -output-directory=docs/reports \
  docs/reports/gec_examples_21_languages.tex
```

Use LuaLaTeX and DejaVu Serif for Greek/Cyrillic as well as Latin scripts.
The initial LuaLaTeX binary lacked `luaotfload-main`; install the system
`texlive-luatex` package to provide the missing font support. CLI options
`--seed`, `--count`, and `--languages` customize selection without changing
evaluation data. Tests cover controls, reference consistency, deterministic
sampling and Unicode LaTeX escaping.

### Score Report

Generate a local report without inference, scheduler changes, or W&B writes:

```bash
python scripts/multilingual_family_report.py \
  --manifest config/multilingual_family_report_epoch10_2900k.json \
  --output docs/reports/multilingual_epoch10_2900k.tex
```

The manifest lists checkpoint label, step, fractional epoch and merged-artifact
roots. Append checkpoints to extend the comparison. Run from the repo root.
The accompanying JSON contains exact task membership, raw scores and artifact
paths. Each family occupies one LaTeX page; cells show mean (minimum--maximum)
on a 0--100 scale, equally weighted by task/suite combination. Ranges are across
tasks, not confidence intervals. Multiple implementations of the same benchmark
count separately, as in the requested across-suite comparisons.

The report also includes a last-minus-first checkpoint change column in
percentage points, and a per-family horizontal bar plot alongside each table.
The plots share one horizontal scale across all families; decreases are red,
increases green, and missing comparisons are explicitly marked n/a. Matplotlib
generates vector PDF plots in a sibling `<report_stem>_plots` directory. All
checkpoint columns remain in the table when further checkpoints are added;
the change and plot always compare the first and last manifest entries.

Primary metrics are explicitly bound in the generator: EuroEval macro-F1 for
acceptability/sentiment, micro-F1 for NER, accuracy for knowledge/commonsense,
answer F1 for QA, instruction accuracy and chrF3++ for summarization. DFM uses
semantic acceptability macro-F1, correction exact match, strict instruction
accuracy, QA F1 and chrF3++. GovReport chrF3++ is already 0--100; it must not
be multiplied by 100. No strict-acceptability fallback or VaLEU inclusion.

Membership is the union across requested checkpoints; incomplete cells are
withheld, not averaged over fewer tasks. The default threshold requires 18 of
21 individual languages to have complete cells at every checkpoint. Joint
Norwegian benchmarks are displayed separately and do not inflate coverage.
Conflicting duplicates, wrong checkpoint stamps and invalid scores fail closed.
Identical duplicate artifacts count once. Unstamped artifacts rely on the
explicit checkpoint-root assignment; baseline EuroEval uses the canonicalized
roots documented below. New metric naming schemes require an explicit binding.

The epoch-10/2900K report includes nine families: acceptability, correction,
instruction following, QA, summarization, NER, sentiment, knowledge and
commonsense. The earlier conversational QA table omitted DFM SQuAD and CoQA;
the generated report includes these, so its English QA mean supersedes that
table. Five focused tests cover units, ranges, membership, coverage, provenance
checks, conflicting scores and LaTeX escaping. The initial compiler-unavailable
status is superseded: on 2026-09-30, `/usr/bin/pdflatex` successfully compiled
the report into nine pages, one table per page. Recompile with:

```bash
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=docs/reports \
  docs/reports/multilingual_epoch10_2900k.tex
```

## Semantic Acceptability Migration (2026-09-30)

The earlier read-only diagnosis below is historical. On user request, the
completed epoch-10 acceptability logs for all 21 languages and the completed
2900K Danish task were rescored without inference. New merges automatically
emit the same semantic metrics for subsequent checkpoints.

`scripts/dala_semantic.py` accepts whole-label English and task-native yes/no,
correct/incorrect/wrong variants, after Unicode normalization, case folding,
and surrounding whitespace/quote/punctuation removal. Internal punctuation
and explanatory prose are not stripped into an answer; contradictory labels,
unknown outputs, and truncated generations remain invalid. Invalid answers
remain in the F1/accuracy denominator. The original strict scores and Inspect
logs are retained. New task keys are `dfm_eval/dala[_LANG]/semantic_v1/{macro_f1,
mcc,accuracy,invalid_rate,n}` with `dfm_eval/epoch` as the x-axis.

All acceptability-dependent populations get new versions, with the same task
memberships, units, and weighting (only the acceptability binding changes):

| Old population | Semantic population |
| --- | --- |
| `multilingual_v1` | `multilingual_v2` |
| `english_dfm_v1` | `english_dfm_v2` |
| `english_v2` | `english_v3` |
| `cross_language_v1` | `cross_language_v2` |

These retain `avg_population/<id>/score`, language scores below
`languages/<lang>/score`, and `avg_population/epoch`. Comparable Czech still
uses four tasks; the other languages use five. Multilingual still equally
weights its 19 language means. Neither change adds multilingual to the legacy
overall average. No fallback to strict acceptability is allowed.

`python -m scripts.prepare_semantic_acceptability_averages --include-legacy --apply` adds
CPU-only average rows under the live plan lock, preserving all old rows.
Semantic multilingual/English rows cover epoch 10 and every scheduled DFM12
checkpoint; comparable rows cover epoch 10 and 2900K. Their dependencies are
copied from the corresponding original average rows. Missing tasks withhold
the corresponding score rather than changing the denominator.

The optional legacy counterparts use `headline_avg_semantic_v1/*` and
`suite_avg_semantic_v1/*`, each with its own `/epoch` axis. They retain legacy
memberships (including the existing overall definition) and replace only the
Danish acceptability key. Missing semantic evidence suppresses the affected
Danish/overall/DFM means; it never falls back to strict scoring. The standalone
scheduler rows log only new average keys, not old raw metrics or v3 averages.
All 11 checkpoint groups have these additive rows, in addition to the 13
population rows. Existing averages and logs remain intact.

Historical epoch-10 EuroEval suite inputs with step zero were copied unchanged
to `data/eval/dfm11-xl-epoch10-semantic-headlines/epoch_10` using
`scripts/canonicalize_epoch10_english_euroeval.build` with `SUITE_KEYS['euroeval']`.
Its provenance pins the completed export/eval jobs and checkpoint state; only
the checkpoint stamps change in the copies. Never bypass the mismatch check.

`scripts/publish_semantic_population_panels.py` switches existing population
and non-Danish acceptability panels in workspace `3fvncok3gjh` to the new keys.
Section ordering, run selections, and axes are unchanged. Legacy Danish,
English, overall, and suite panels are retained: replacing their keys globally
would hide older runs whose stored generations have not been rescored. The new
semantic counterpart metrics are available separately. Workspace verification
is an API-spec re-read, not a claim to have checked browser rendering.

The completed epoch-10 multilingual mean changes from 43.9582% to 45.6233%;
the expanded 17-metric English mean changes from 74.9794% to 76.3680%.
The latter is not the legacy 15-metric English headline. The comparable
21-language mean is still waiting for outstanding task results.

Scorer: `scripts/dala_semantic.py`; additive merged metrics:
`scripts/merge_dfm_eval_shards.py`; rescore receipt:
`logs/diagnostics/epoch10_dala_label_formats/semantic_v1_rows.json`.
Versioned manifests: `config/multilingual_headline_populations_semantic_v1.json`
and `config/cross_language_average_v2.json`. Old definitions are not rewritten.

### Mandatory Finalization Before Training

On 2026-09-30 the user required all epoch-10 and 2900K merges, syncs, and
averages to finish before training resumes. The existing terminal GPU barrier
alone did not enforce that. `scripts/gate_dfm12_training_on_final_averages.py`
adds 11 sequential final average/sync rows after all non-skipped, non-VaLEU
evaluation/merge/average/report producers for both checkpoints and GPU-phase
teardown. The next training segment (`step_2950000`, resuming 2928000) now
requires successful finalization, not merely terminal completion. Failed
finalization blocks training; intentionally excluded VaLEU failures do not.

This final sequential pass also repairs the observed concurrent-write loss:
the first two semantic legacy-average writers started in the same second;
remote history initially retained only epoch 10, not 2900K. A successful
process exit is not by itself proof every concurrent W&B point survived.
Do not run those two checkpoint writers concurrently again. The final pass
preserves old metric definitions, registers keys explicitly, and re-logs each
checkpoint's averages with its own fractional-epoch axes. No training or
evaluation process was stopped to install the gate.

## Cross-Language Comparison V1

### Epoch-10 Acceptability Scoring Diagnosis (2026-09-30)

Read-only inspection of all 20 new languages' 2,000 stored DaLA generations
reproduced the logged macro F1 exactly. The heldout scorer accepts only the
entire stripped/casefolded `yes` or `no`; punctuation and native labels are
invalid. This is materially stricter than the existing Danish DaLA scorer,
which recognizes Danish label words within surrounding text. Native prompts
explicitly requested English labels, so native-label normalization is a
counterfactual semantic diagnostic, not compliance with the original format.

For Spanish/Greek/Portuguese, invalid counts were 1998/1969/1950 of 2000.
Punctuation-only normalization changed macro F1 from 0.20/1.26/2.76 percent to
35.02/35.57/19.24. Exact, language-specific yes/no aliases additionally yielded
72.48/35.57/34.76. Spanish answers were almost entirely `Si` with an accent and
`No` with punctuation. Portuguese remained genuinely biased: 1,987 yes versus
13 no, identifying only 13/1000 corrupted examples. Greek identified 30/1000
corruptions and still had 96 unrecognized outputs. English punctuation-only
F1 rose from 65.32 to 88.92; German from 58.88 to 61.16. Output truncation
was not the dominant issue (0/2000 for ES/PT/EN/DE, 2/2000 for EL).

All inspected datasets had 1000 clean and 1000 corrupted targets. A sampled
English clean target was itself grammatically questionable; the amount of
source-label noise is not established. Do not interpret strict-parser rankings
as language ability without separating format compliance and semantic scoring.
Recommend a versioned, common scorer across languages accepting standalone
labels plus harmless punctuation, with explicit native aliases and a separate
invalid/format-compliance metric. Rescore stored generations; no GPU rerun is
needed for such a diagnostic. Broader prose/contradictory answers must not be
accepted by first-label extraction without an explicit scoring policy.

Reproducer: `python -m scripts.inspect_dala_label_formats`.
Detailed counts, confusion matrices, examples, and human-readable report:
`logs/diagnostics/epoch10_dala_label_formats/report.{json,md}`.
No production scorer, evaluation plan, stored metrics, or W&B data were changed.

On 2026-09-30 the user requested a separate comparison across all 21 languages:
ScaLA macro F1, MultiIFEval instruction accuracy, MultiWikiQA F1, DFM
acceptability macro F1, and DFM correction exact match. Czech omits MultiWikiQA
by definition and averages the other four, not a zero placeholder. Every other
language requires all five. EuroEval percentages are divided by 100; DFM scores
are already fractions. Languages have equal weight in the aggregate. Existing
headline, suite, overall, and multilingual_v1 definitions remain unchanged.

Manifest: `config/cross_language_average_v1.json` (104 metric bindings).
New keys:
- `avg_population/cross_language_v1/languages/<language>/score`
- `avg_population/cross_language_v1/score`
- Shared x-axis: `avg_population/epoch`; also records the exact train step.

`scripts/prepare_cross_language_average.py --apply` installed average rows
`cross-language-epoch_10-average` and `cross-language-step_2900000-average`
in the existing plan, plus 11 missing MultiWikiQA jobs for each checkpoint.
These new MultiWikiQA jobs are deliberately scoped to the two requested
checkpoints, unlike the earlier ScaLA/MultiIFEval additions across the campaign.
All 20 language variants passed access checks; Czech is unavailable.
The epoch-10 additions participate in the current 2900K phase's terminal
barrier. Averaging waits for the appropriate eval/merge successes and uses
historical Danish/English artifacts only where already completed. The
cross-language logger refuses to log incomplete populations, so missing data
cannot silently change the denominator or mark a partial average successful.

Historical Danish EuroEval scores are copied unchanged into
`data/eval/dfm11-xl-epoch10-danish-comparison-20260930`, with hashes and
provenance binding their formerly zero step stamp to the completed epoch-10
export/evaluation rows and checkpoint state (step 2877261). Original artifacts
are unchanged. Existing English canonical copies are reused. Portuguese
MultiIFEval uses generic `pt`, while ScaLA/MultiWikiQA use `pt_pt-pt`; the
population language label remains `pt_pt`. This variant limitation and varying
source difficulty mean common task families do not imply equal test difficulty.

Dry-run evidence is in each average row's `cross_language/<tag>/preflight.json`:
epoch 10 initially had 81 valid and 23 missing metrics, 2900K had 3 valid and
101 missing, with no ambiguous or checkpoint-mismatched metrics. Focused tests
cover equal language weights, the Czech denominator, unit conversion, missing
metric suppression, and unchanged legacy populations (41 tests passed).

## Existing Workspace Extension

### Language Sections (2026-09-30)

Superseding the single multilingual section described below, workspace
`3fvncok3gjh` now has 19 language-specific sections, each with its existing
language average first, followed by that language's DFM and EuroEval panels.
Shared Norwegian diagnostic metrics appear in both applicable language sections.
The multilingual headline remains in Headline Averages. Its computation is
unchanged: equal task weighting within each declared language population, then
equal weighting of all 19 complete language means. The legacy overall average
is deliberately unchanged. Diagnostic exclusions still apply; not every visible
panel contributes to its language average.

`scripts/split_multilingual_workspace.py` preserves all unrelated sections and
run selections exactly and verifies the saved remote spec. Snapshot directory:
`logs/wandb_workspace_specs/3fvncok3gjh-languages-20260930-083603/`.
This verifies API persistence, not browser rendering of metrics not yet logged.

All `valeu-*` tasks remain outside averages and their success dependencies.
By user request, exhausted failures should also be excluded from future evals.
The current failures `valeu-fr`, `valeu-fi`, and `valeu-is` are recorded in
`config/euroeval_optional_exclusions.json`; the multilingual plan builder skips
these entries. Under the live plan lock, 3 failed rows and 30 future pending
rows were marked skipped with original status and reason retained in metadata.
Logs and completed results were preserved. Other values diagnostics were not
cancelled. For further exhausted values failures, add the dataset to this
exclusion list and skip its failed/pending rows under the plan lock.
No model, training, evaluation scoring, or average definitions were changed.

On 2026-09-30, explicit user authorization extended existing DFM5 workspace
`3fvncok3gjh` in place: one Multilingual headline average panel appended to
Headline Averages, and a new Multilingual Headline Metrics section appended
with 215 panels from `scripts/multilingual_workspace_panels.py`. These cover
the multilingual average, language averages, DaLA/GEC, and EuroEval metrics
(including explicitly labeled diagnostics outside the average).
All seven previous sections, existing panels, ordering, settings, and run
selections were preserved. In particular, the subtractive selection tree was
not modified. A raw-spec minimal API update avoided SDK model normalization.
Remote re-read matched the intended spec exactly; removing the additions
recovers the entire previous spec. Before/after specs and verification receipt:
`logs/wandb_workspace_specs/3fvncok3gjh-multilingual-20260930/`.
Operation script: `scripts/extend_existing_multilingual_workspace.py`.
No metric history, evaluation, or scheduler plan changes were made.

## Epoch-10 Artifact Compatibility

On 2026-09-30 the actual epoch-10 average preflight found only 7/15 existing
English metrics because its EuroEval root repeated the suffix
`epoch_10/epoch_10`; artifacts were under `epoch_10/epoch_2` instead.
The collector now recovers only a nonexistent duplicated checkpoint suffix,
never a missing checkpoint via campaign-wide search. The initial zero-step
compatibility exception and its `population_metrics_discovery_fix.json` report
were superseded the same day: all explicit step mismatches, including zero,
are now rejected. Use canonical copies instead of relaxing checkpoint checks.

Canonical English EuroEval root:
`data/eval/dfm11-xl-epoch10-english-euroeval-20260930`.
Its eight scores are unchanged copies; only checkpoint metadata is normalized
to epoch 10 / step 2877261. `provenance.json` binds the original files, completed
export job `dfm11-xl-e10-epoch_10-export-600290`, its dependent completed eval
jobs, EMA export metadata, checkpoint state, and available execution logs by
hash. Seven originals had step zero; IFEval omitted the step stamp.
The CPU builder is `scripts/canonicalize_epoch10_english_euroeval.py` and refuses
an existing output root. Replace the incorrect additional EuroEval root with
this canonical root, rather than including both originals and copies.

Canonical-baseline dry-run found 15/15 existing English metrics and withheld
the full English score at 15/17 pending new LA/GEC results. Evidence:
`logs/scheduler/dfm12_XL_epoch11_noidentity/preflight_multilingual_average/population_metrics_canonical_baseline.json`.
No plan, source artifact, GPU, or W&B changes were made.

`scripts/log_multilingual_headline_averages.py` is a separate, opt-in collector.
The existing `scripts/log_dfm5_headline_averages.py` populations, normalization,
prefixes, and historical English averages are unchanged. Scheduler/workspace
integration and actual metric logging are separate operator actions.

## Manifest Interface

JSON requires `schema_version: 1` and a `populations` list. Every population has
exactly `id`, `kind`, `languages`, `required_tasks`, and `metrics`.
`required_tasks` may be a language-to-task-list mapping (or a shared list for
backward compatibility). Every language must explicitly name its expected set.
`metrics[language][task]` is a binding with `suite`, `key`, and `scale`, plus an
optional `artifact` path relative to that suite's root. A null binding means
explicitly unavailable; it does not remove a task from the denominator.

- `kind: multilingual`, `id: multilingual_v1`: exactly 19 distinct non-DA/EN
  languages, each with the same explicit required task slots.
- `kind: english_dfm`, `id: english_dfm_v1`: only EN, tasks exactly `la` and
  `gec`, both from DFM. This is a pair summary, not a revised English headline.
- `kind: english`, `id: english_v2` or later: an explicitly declared full
  replacement population, never written into the old English namespace.

Suites are `standard`, `dfm`, and `euroeval`, with matching `eval/`, `dfm_eval/`,
and `euroeval/` key prefixes. Scales are explicitly `fraction` or `percent`.
For example, percent value 0.5 becomes 0.005, never 0.5. Boolean, nonnumeric,
nonfinite, negative, and out-of-range values are invalid rather than clamped.
Metric bindings cannot count the same suite/key twice within a population.
An optional `metric_language` binds an explicitly registered EuroEval namespace
such as `pt_pt-pt` while preserving the headline language `pt_pt`.

The concrete registry is `config/multilingual_headline_populations_20260930.json`,
derived from `config/dfm_dala_heldout_20260930.json` and the catalog-reviewed
`config/euroeval_dfm12_multilingual.yaml`. Superseding the initial 228-slot/null
proposal, it declares 177 expected multilingual results: 38 DFM bindings plus
139 selected EuroEval bindings, with explicit per-language denominators.
Unavailable categories and ambiguous shared Norwegian metrics are excluded
from that declared population, not counted as missing runs. Every selected task
must finish before a headline score appears; language means remain equally
weighted despite different task counts. A subsequent concurrent remote-access
preflight marked EuroEval entries blocked. This does not silently shrink the
frozen population: missing selected results still withhold its score. Flagged
panels remain separate diagnostics and do not enter averages. English has
both the two-task pair summary and a distinct complete-only 17-metric population
(the original 15 English keys plus the two new heldout keys).

## Computation And Coverage

Outputs use `avg_population/<population-id>/score`, language scores under
`languages/<language>/score`, expected/valid metric counts, complete/expected
language counts, `coverage`, `complete`, and `definition_sha256`.
Average tasks equally within each language, then average languages equally.
A language score requires every declared task. A population score requires
every task for every language: missing or invalid inputs never create a
partial mean. Change the population version when changing its definition.

The collector recursively discovers `merged_metrics.json` files. Multiple
origins for the same metric are ambiguous, even when values agree. An explicit
relative `artifact` can disambiguate a binding. Suite roots remain separate;
one source cannot silently overwrite another. Available train-step stamps
must match the requested checkpoint. Null bindings and absent artifacts are
reported as coverage gaps, not numerical zeros.

## CLI And Safety

```bash
python scripts/log_multilingual_headline_averages.py \
  --manifest REGISTRY.json --dfm-root DFM_ROOT --euroeval-root EURO_ROOT \
  --epoch 10 --step STEP --dry-run --report COVERAGE.json
```

Root flags are repeatable, including optional `--standard-root`. Aliases
`--additional-standard-root`, `--additional-dfm-root`, and
`--additional-euroeval-root` support matching-checkpoint historical English
artifacts. Outside dry-run, `--project`, `--run-id`, and `--run-name` are
required; optional `--entity` selects the account. The logger resumes an
existing run, defines every emitted metric explicitly against
`avg_population/epoch`, and commits one atomic checkpoint row.
`--include-raw-metrics` additionally emits valid, unambiguous source metrics
in their original units. Dry-run never imports W&B.

Local verification: 40 focused population/legacy-root tests passed on
2026-09-30. Tests cover complete coverage, source ambiguity, explicit scales,
invalid values, checkpoint mismatch, unchanged legacy behavior, and mocked
atomic W&B registration. No W&B, GPU, scheduler, or training actions were
performed as part of implementation.

Integration update (2026-09-30): the paused DFM12 XL plan now contains these
average rows for epoch_10, step_2900000, and all later scheduled checkpoints.
Superseding the temporary access warning above, all 157 distinct EuroEval
datasets passed preflight through EuroEval's normal authentication path.
The new opt-in workspace is
[DFM5 Multilingual Headlines](https://wandb.ai/peter-sk-sdu/DFM5?nw=mkrhf1q0gcj).
