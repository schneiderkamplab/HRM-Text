# TODO5 handoff to Epicurus and Boole

## Authorized 3154500 Pause: Final Frozen Handoff

### Critical spacing correction: supersedes implicit-cursor instructions

The five existing training panels explicitly use `_step`. The final logger
therefore does NOT use one implicit row step per logging call. Instead it fixes
`logging_offset = max(0, run.step - first_optimizer_step)` on its first call,
then logs with `step=max(optimizer_step + logging_offset, run.step)` and
`commit=True`. Optimizer-step gaps (including uneven intervals) remain intact;
same-step diagnostic/validation rows append monotonically. Exact optimizer
coordinates remain in `train/step`. Optimizer, cursor, LR, epoch, and existing
panel axes are unchanged. No training or W&B sync is launched here.

The former helper hash below is superseded; Epicurus MUST refresh the helper
pin from the final `utils/training_wandb.py` before resume. `pretrain.py` is
unchanged from its previously supplied integration hash.49 focused tests pass,
including uneven spacing, repeated same-step rows, initial backfill high-water,
cursor jumps, and uninitialized-run rejection. Expanded-average work is handed
to Harvey; this agent will not modify its logger or definitions further.

Final helper SHA256:
`0803f49bfa4b031ff362276a6b09e8db57c75b4def8d9b1d0e64c7ae4aa72dfe`.
Pretrain SHA256 remains
`6da39b654ba88d69d77e8dbb5a1394d58a4241279a50a5bdd010814355d3bf87`.

Read-only remote confirmation after raw sync: actual `lastHistoryStep=3154562`;
633326 is the history record count, not `_step`. Recent training records were
`_step=3154400..3154495` every5, LR0.0003, with no `train/step` field. Raw rejudge
rows appended at `_step=3154496..3154562`. The old `train/step` series still
ended at1229500. Thus the logging fix is necessary, not an inferred change
based on console file-stream offsets. The stopped launcher uses
`/work/mimir/HRM-Text/pretrain.py` via the handoff segment's `cwd=ROOT`.
All runtime code and final payload are now frozen for parent/Epicurus.

After parent's raw-score sync finishes, use this freshly hash-verified payload:

```bash
python -m scripts.prepare_talemaader_v2_averages \
  --sync-prepared logs/rejudge_talemaader_v2/averages/prepared-pause3154500-final-v2.json \
  --paused-step 3154500
```

The guard explicitly permits3154500 and3200000, rejects live training, and
retains idempotence/uncertain-attempt protection.67 points and all payload pins
verified.44 focused tests passed. No sync or training was launched by this agent.

The authorized logging-only fix supersedes the earlier unresolved high-water
limitation for NEW training processes: `pretrain.py` now routes all four
training/validation/diagnostic/initial metadata calls through
`utils/training_wandb.py`. The helper logs exact `train/step=optimizer_step`
as an ordinary metric, defines training metric axes explicitly, and does NOT
pass `step=` to W&B. Thus W&B appends after its resumed internal cursor even
if134 historical rows advanced it beyond3154500. It never mutates optimizer
step, checkpoint state, cursor, LR, or training configuration. Old history is
not rewritten; training charts should use `train/step`, not internal `_step`.

Parent/Epicurus must explicitly refresh owned resume pins, preserving old pin
evidence, and include the new helper before launching. Frozen hashes:

- `pretrain.py`: `6da39b654ba88d69d77e8dbb5a1394d58a4241279a50a5bdd010814355d3bf87`
- `utils/training_wandb.py`: `64f8e0a76c199a4588c05433a77dac4a38a6defc04180b1caab11747f9f514f3`
- `scripts/prepare_talemaader_v2_averages.py`: `8ffdecb081dab7a2e075221d3460d695cd7da522ac823473afd699bc17dd65f5`

Do not run raw-score and average writers concurrently. No further runtime
edits are planned. Historical paragraphs below remain for audit chronology.

## Final Verification / Epicurus Ownership

Implementation is complete and frozen for handoff. Final rerun:36 tests passed.
All input SHA256 pins and the rows digest of
`logs/rejudge_talemaader_v2/averages/prepared-future-compatible-v2.json`
were reverified; all67 points contain each of the three Talemaader-only
successor scores. No W&B writes or scheduler-plan changes were performed.

Epicurus can wire the existing AVG dispatch using the exact metadata below.
Ensure the future native Talemaader v2 merge completes before its AVG row.
No new CLI/runtime dispatch is required. Preserve old averages and unrelated
English/math rows. Boole can map panels to the new keys without redefining
their source metrics. The documented existing W&B high-water collision risk
remains parent-owned; this task does not authorize or implement training fixes.
No further worker, training, or GPU actions are pending from this implementation.

## Superseding Final Handoff

### Future dispatch implemented

The existing `scripts/log_dfm5_headline_averages.py` now recognizes the two
Talemaader-only prefixes explicitly. The scheduler's existing
`backfill_external_eval_to_wandb.py` dispatch works without runtime changes:

```json
{"average_prefix":"headline_avg_talemaader_v2","extra_average_prefixes":["suite_avg_talemaader_v2"],"average_scope":"all","atomic_v3_averages":false}
```

Keep the usual checkpoint roots, step, epoch and run metadata. Ordinary native
future `merged_metrics.json` containing the v2 scorer is supported; historical
`merged_metrics_v2.json` is optional. Epoch, step/input checkpoint tags and
sample counts are validated. Conflicting scores/counts fail; identical native
and historical copies are unambiguous. Missing v2 never falls back to v1.
Legacy prefixes still follow their original unchanged code path.

36 focused tests pass, including actual scheduler-dispatch CLI execution with
a fake W&B sink and a standalone dry-run with PYTHONPATH removed. No remote
writes. Because the legacy logger is pinned by preparation, the fresh compatible
payload is now `logs/rejudge_talemaader_v2/averages/prepared-future-compatible-v2.json`;
older prepared payloads intentionally fail changed-input checks.

### W&B high-water limitation

Installed SDK0.27.0 `Run._log` increments `_step` on every committed row.
An independent eval x-axis changes plot coordinates, NOT this internal counter.
67 historical rows therefore cannot be appended to this same paused run with
a guarantee of zero dropped explicit-step training logs at the old resume
step. `commit=False` is not a solution: repeated same-key historical points
would merge/overwrite until committed, and finishing flushes pending data.
Do not retrofit shared mode onto the live ordinary writer.

Without a production training change, defer same-run historical curve appends
until training completes (or accept explicitly documented skipped logging,
which is not recommended). Summary/table-only publication avoids adding67
history rows but does not create the requested historical curves. The durable
fix is a separately authorized training logger change: log `train/step` as the
axis and stop passing optimizer step as W&B's internal `step=`; serialize
writers at existing pauses. No such production change was made here. Merely
resuming after a planned pause does not solve existing post-eval collisions.

The sync CLI exists but MUST remain deferred until the parent resolves this
logging policy; changing optimizers/global training step to catch W&B is not
an acceptable workaround.

Use `logs/rejudge_talemaader_v2/averages/prepared-talemaader-only-v2.json`,
not the earlier semantic-only proposal. All67 points have new
`headline_avg_talemaader_v2/danish`, `headline_avg_talemaader_v2/overall`,
and `suite_avg_talemaader_v2/dfm` scores. This uniform definition uses strict
DaLA and current task membership, replacing ONLY the idiom scorer. Explicit
task/section completeness counts preserve missing-input visibility. No
multilingual term enters overall; English/math panels remain untouched.

The earlier36 overall mismatch points include33 explained by historical
three-section vs current eight-section membership.150K/800K/1650K retain
raw-input/recipe warnings. Such comparisons are diagnostic, not a reason to
drop points from this explicitly NEW fixed-recipe series. Semantic-v2 remains
separate, with seven supported points; do not replace historical panels with it.

Deferred executable command, after training is paused at3200K:

```bash
python -m scripts.prepare_talemaader_v2_averages \
  --sync-prepared logs/rejudge_talemaader_v2/averages/prepared-talemaader-only-v2.json \
  --paused-step 3200000
```

Future pure API: `talemaader_only(metrics, point) -> (row, report)` for the
three new historical-successor keys; `compute(metrics, point, registry)` for
separate semantic and32/34-language populations. Epicurus owns scheduler rows;
Boole owns workspace mapping.24 focused tests passed. No W&B sync executed.

The following earlier semantic-only handoff is retained as superseded context.

Scope: current run `peter-sk-sdu/DFM5/dfm8-xl-from-dfm6-dfm7-epoch5-clean-full`
only. No plan, workspace, training, rejudge runner, or live W&B changes.

Implementation: `scripts/prepare_talemaader_v2_averages.py`.
Tests: `tests/test_prepare_talemaader_v2_averages.py` plus existing
`tests/test_semantic_headline_averages.py`:21 passed.

Prepared payload: `logs/rejudge_talemaader_v2/averages/prepared-v2.json`.
Immutable read-only source snapshot: `source-history-v1.jsonl` in the same
directory, plus `.receipt.json` containing per-key original history values,
latest-per-key selection evidence, exclusions, and all67 point metric counts.
247 relevant available keys were requested.18 inconsistent-axis records were
excluded; none of the selected records required absent-train-step recovery.

All67 completed rejudge sidecars are incorporated. Publishable semantic-v2
scores:7 points (2877261 and 2900000..3150000 every50000).60 older points lack
semantic DaLA.36 points additionally have original-average reconstruction
mismatches. No strict-DaLA fallback, no fabricated population completion.

Future exact mapping:

| Existing | New opt-in |
| --- | --- |
| `headline_avg_v3/danish` or semantic-v1 Danish | `headline_avg_semantic_v2/danish` |
| `headline_avg_v3/overall` or semantic-v1 overall | `headline_avg_semantic_v2/overall` |
| `suite_avg_v3/dfm` or semantic-v1 DFM | `suite_avg_semantic_v2/dfm` |
| 19-language multilingual | `avg_population/dfm13_multilingual_v1/score` (32 languages, complete only) |
| expanded all-language view | `avg_population/dfm13_all_languages_v1/score` (34 languages, complete only) |

Do not rename/overwrite old keys. English/math panels retain their existing
keys and recipe. Overall remains the mean of the existing available section
means; neither multilingual population contributes to it. Axes for each new
namespace are `<namespace>/epoch` and `<namespace>/train_step`. Pure future
API: `compute(metrics, point, load_registry(population_path)) -> (row, report)`.
Parent must gather checkpoint-bound metrics, including the v2 idiom sidecar.
Population config remains `config/multilingual_headline_populations_dfm13_20261006.json`.

At3200K only, after training stops and with exclusive scheduler ownership:

```bash
python -m scripts.prepare_talemaader_v2_averages \
  --sync-prepared logs/rejudge_talemaader_v2/averages/prepared-v2.json \
  --paused-step 3200000
```

No sync has been executed. The writer refuses active training, partial rejudge,
changed pins, old/raw metric keys, and uncertain previous attempts. It writes
one row per inventory checkpoint (coverage-only where scores are blocked),
without passing historical `step=` to W&B. Completed receipt includes the
next internal W&B step: Epicurus must coordinate resumed explicit training
steps against this high-water mark. Do not assume a paused append cannot
advance it. Do not run this alongside other eval W&B writers.

To refresh the prepared file after additional original metrics become available,
use a NEW read-only history snapshot filename; no existing snapshot overwrite.
Reprepare after code/config changes, because implementation and input hashes
are checked at sync. No historic points or original metric values were deleted.
