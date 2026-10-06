# Expanded Traditional DaLA V2 Averages

Validated against actual3150K roots from installed
`dfm13-xl-dala-v2-step_3150000-average`:57historical inputs resolved, exactly68new
metrics missing, no historical key/root/checkpoint mismatch. Scores correctly
withheld. CPU-only receipt:
`data/dfm13/expanded-dala-v2-averages-20261006/step3150000-dry-run.json`.
Twelve focused tests passed before handoff; no W&B writes performed.

Parent/Epicurus owns plan installation; Boole owns panels. Poincare's training
logger, historical67-point Talemaader-v2 series and existing multilingual
population averages are untouched.

Implementation: `scripts/log_expanded_dala_v2_averages.py` and exact opt-in
`eval_scheduler/eval_scheduler/runtime.py::run_average` dispatch.

Install ONE additional AVG row per intended checkpoint, not historical backfill:

- `average_prefix: headline_avg_dala_v2`
- `extra_average_prefixes: [suite_avg_dala_v2]`

This supersedes the initial two-row handoff: two concurrent W&B writers can lose
history. The exact pair above omits `--metric-prefix` in scheduler dispatch, so
one process emits both namespaces in one committed W&B row with both epoch axes.
Do not install separate headline/suite rows for this expanded population.

Use existing metadata `log_root`, `dfm_log_root`, `euroeval_log_root`, `ckpt_tag`,
`eval_epoch`, checkpoint step and W&B run identity. Additional checkpoint-scoped
roots are accepted as lists `additional_standard_roots`, `additional_dfm_roots`,
`additional_euroeval_roots`; the EuroEval primary root follows existing dispatch
and appends `ckpt_tag`. Additional roots are used verbatim, not appended.

Deps must cover existing standard/DFM/EuroEval merges, Talemaader-v2 merge, all26
new13-language DaLA merges and all42existing21-language v2 merges. Incomplete,
invalid, ambiguous or mismatched inputs produce a coverage report and failure,
with no W&B metrics emitted. There is no fallback to old DaLA or Talemaader.
Even a Danish-only namespace requires the entire expanded input set before emit.

Panel keys:

- `headline_avg_dala_v2/danish`:20tasks (old18 with Talemaader-v2, plus2DaLA-v2).
- `headline_avg_dala_v2/english`:17tasks (old15 plus2DaLA-v2).
- `headline_avg_dala_v2/overall`: equal mean of the same eight traditional section
  means. No multilingual mean or extra language section is added.
- `suite_avg_dala_v2/dfm`:99tasks, original unique31DFM suite with Talemaader-v2 plus68new
  DaLA/GEC metrics. Old strict DaLA remains present; no semantic substitution.

Each prefix has its own `/epoch`, `/train_step`, `/definition_sha256` and counts.
All emitted metrics are explicitly registered with their prefix's epoch axis;
each invocation logs one atomic checkpoint row with W&B `resume=must`.

Standalone dry-run (repeat roots as required):

```bash
python scripts/log_expanded_dala_v2_averages.py \
  --standard-root STANDARD --dfm-root DFM --euroeval-root EURO_CHECKPOINT \
  --additional-dfm-root NEW13 --additional-dfm-root EXISTING21_V2 \
  --epoch EPOCH --step STEP --report REPORT.json --dry-run
```

Omitting `--metric-prefix` in standalone mode emits both new namespaces together.
Scheduler dispatch for the exact pair above also emits both; single-prefix
dispatch remains supported when no extra prefixes are specified. Unknown prefix
combinations fail closed. `log_wandb=false`
performs validation/dry-run rather than silently treating absent results as ready.
No plan changes, network calls or metric backfill are performed by this handoff.
