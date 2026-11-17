---
type: Runbook
title: DFM10 HF-only rebuild recipe
description: HF-only replacement of the invalid local-source DFM10 recipe; historical reconstruction details retained.
status: draft
confidence: high
last_updated: 2026-11-10
---
# DFM10 HF-only rebuild recipe

## Unpacking scope/performance correction, 2026-11-08

The initial 72-package acquisition/unpacking scope was excessive. Twenty-three
packages (117.13 GB compressed) contain inherited families already supplied
by the verified DFM9 union. Reprocessing their exports is unnecessary for
DFM10's 4,351 additions. The earlier progress denominator of 151.15 GB and
12–24-hour ETA were therefore misleading and are superseded.

`scripts/dfm10_export_scope.py` now explicitly excludes those inherited
packages from acquisition, unpacking and task indexing. Forty-nine packages
remain relevant (about 34.02 GB compressed). QReCC-II, SciBench, scientific
summaries, OPUS and native Nemotron additions remain included. Full task
mapping and exact-array verification gates are unchanged; no nonempty
missing task may be silently dropped. Historical already-downloaded/unpacked
artifacts remain preserved but excluded from the active task map.

The serial unpacker also performed filesystem path resolution per row,
including 38.4 million FLAN-T0 rows. It now validates each distinct source
path once while keeping duplicate/order checks on every row and manifest
row-count/hash checks. At inspection it had written 394 GB across all
exports, spent about six CPU hours over twelve elapsed hours, and was still
actively writing. This was avoidable orchestration/metadata overhead, not
a GPU capacity issue or a demonstrated stalled worker.

Stopped only the isolated unpacker and waiting DFM10 continuation, applied
these fixes, and restarted both. Forty-three required packages are already
unpacked; six remain, chiefly scientific summaries. DFM11 and OPUS publication
remain gated as before. Eighteen focused tests passed.

## Policy correction, 2026-11-07

The original recipe below is **superseded and disabled**. Its 4,351 local
component inputs did not meet HF-only policy, despite the earlier title.
The user stopped that run; its artifacts are reference-only and must never
feed the verified chain. The serial DFM10 row remains held.

`scripts/acquire_dfm10_hf.py` now runs fresh acquisition under
`data/rebuild_hf_dfm/dfm10-hf-v2`, pinning 72 published dataset repositories
to immutable HF commits. It downloads remote manifests and checks each
payload's size and SHA-256. The local export manifest selects repository
names only; local export payloads are not consumed. Progress is recorded in
`acquisition-progress.json`; launch log:
`logs/analysis/dfm-hf-provenance-20261107/dfm10-acquire.log`.

Acquisition is running, **not a completed reconstruction**. Source-file/row
mapping, historical transformation equivalence, and missing publication
coverage still need resolution before tokenization can start. No local
public fallback is authorized. Only lexdk/DBC are exceptions. In particular,
the 72-package publication inventory does not directly name historical
DaCoref, original Nordjylland, English model-charter, or the two medical
component tasks; upstream HF reconstruction must be investigated.

### HF-only continuation implemented (2026-11-07)

The five initially uncovered tasks have now been rebuilt from upstream HF:
DaCoref, original Nordjylland, English model charter, ELRC, and NHS. All five
match all historical token/instance/response arrays exactly; receipt:
`data/rebuild_hf_dfm/dfm10-hf-v2/upstream/token-comparison.json`.
Converters are frozen from repository revision `ccbb215`; upstream revisions,
file hashes and converter hashes are recorded in the separate upstream
acquisition/conversion receipts. No original local payload was consumed.

`scripts/unpack_dfm10_hf.py` streams verified exports back into original
source-file groups, rejects duplicate/reordered source rows and retains
original message/tool fields separately from publication provenance.
`scripts/map_dfm10_hf.py` and `scripts/materialize_dfm10_hf.py` map those
sources to historical task identities and restore HRM conditions explicitly.
Expanded Mimir consumes pinned HF export shards directly, as historically.
DOLCI uses its historical compact-JSON 256 MiB split: all seven recovered
shard byte sizes match the historical inventory. This is a boundary check,
not yet token-equivalence certification for DOLCI.

Zero-payload task shapes may be reconstructed only where the corresponding
HF export is complete, no rows were exported for the source, and all five
historical comparison arrays are empty. This does not supply local text.
Missing nonempty sources remain errors. DBC repaired inputs retain their
explicit agreement exception.

The detached sequential continuation `scripts/finish_dfm10_hf.py` waits for
acquisition/unpacking, then runs mapping/materialization, preparation,
tokenization, assembly, per-task verification, ten-epoch sampling and full
sample comparison. It writes resumable stage receipts and stops on errors.
New outputs live at `data/rebuild_hf_dfm/serial-queue/dfm10-hf-v2`; the old
`dfm10` tree/held queue row remain historical and cannot feed this rebuild.
`compare_dfm10_hf.py` issues the final receipt only after all 41 sampled
arrays and metadata match. Production remains untouched. Sampling policy,
code and the existing DST approval gate are local control metadata, not
local public dataset payloads.

Export-restoration smoke verification also matched all five arrays for Andersen,
Bornholmsk and the first Code Meta Reasoning shard (three additional tasks).
Fourteen focused tests pass.

User authorized full verification on 2026-11-07. Confirmed the detached
continuation includes all 4,351 addition-task comparisons, ten-epoch sampling,
and all 41 final token/index array comparisons plus sampled metadata. It
remains CPU-only; no production admission or upload is part of this run.

Current state: acquisition, unpacking and continuation are running; complete
DFM10 verification is still pending. Logs are `dfm10-{acquire,unpack,finish}.log`
under `logs/analysis/dfm-hf-provenance-20261107/`.

### Verified OPUS publication authorized and scheduled (2026-11-07)

User approved publishing rebuild-ready converted OPUS shards after exact
verification. This supersedes the earlier no-upload scope **for OPUS only**.
`scripts/publish_dfm10_opus_rebuild.py --wait` is running detached, targeting
the new public repository `schneiderkamplab/dfm10-opus-da-en-rebuild-ready`.
It waits for the corrected HF-only input lock and completed addition-token
comparison, then independently compares all five arrays for each of the
64 OPUS tasks. It rechecks converted-payload hashes and includes only those
64 Parquet inputs, the pinned tokenizer/template recipe, OPUS lineage and
verification evidence. No agreement-only data or other DFM sources are
included. Publication is pending, not yet completed.

The publisher verifies the uploaded files at the returned immutable HF commit
and records it in `config/data/dfm10_rebuild_ready_packages.json` only after
remote checksum verification. Existing repositories are not overwritten on
first creation. Log: `logs/analysis/dfm-hf-provenance-20261107/dfm10-opus-publication.log`.
Status: `data/rebuild_hf_dfm/serial-queue/dfm10-hf-v2/opus-publication-status.json`.

For future runs, execute `scripts/fetch_dfm10_opus_rebuild.py --work <fresh-work>`
after the publication registry exists. It downloads the pinned manifest and
exact task files and validates all checksums. The unpacker recognizes that
verified receipt and skips OPUS regrouping; the task mapper uses those
Parquet files directly. The current running reconstruction is not changed
or replaced by its own future publication. Tokenization and exact comparison
still remain required. Nine focused acquisition/publication tests passed.


DFM10 is the DFM9 union minus four superseded prefix families plus 42 audited
component trees (repaired inherited sources and new Danish/English
supervision). The recipe lives in `scripts/rebuild_dfm10.py` with the input
lock `config/data/dfm10_hf_rebuild.json`; the queue row gains stages
`prepare, tokenize, assemble, verify, sample, compare` after `enable-dfm10`,
which requires a verified DFM9 rebuild. `recover-lock` runs manually first.

## Union composition (verified 2026-11-02)

From `data/tokenized_dfm10/union_manifest.json`: base `data/tokenized_dfm9`
contributes 11,395 tasks (11,413 task dirs minus the 18 tasks under the
replaced prefixes `nemotron_terminal_corpus__`,
`dolci_instruct_sft_tool_use__`, `dolci_instruct_sft_tool_use_sa__`,
`dolci_native_tool_use__`), the 42 components contribute 4,351 tasks, and the
union adds `tokenizer_info.json` plus `union_manifest.json`: 15,748 entries.
The pre-flight `resolve_sources` reproduces these counts exactly.

## Frozen revisions

- Standard adapter `cd88c93`: every DFM10 tokenization ran before the
  2026-08-31 11:30 adapter rewrite (the last component,
  `synthetic_values_model_charter_da`, finished 11:28). The rewrite in
  `ccbb215` restructured existing code paths, so it must not be used for the
  standard tasks.
- Native adapter `ccbb215`: the 29 `nemotron_terminal_native` tasks were
  tokenized with the uncommitted native-tool-use mode that `ccbb215` recorded
  (`max_seq_len` 4096, `preserve_first_user` true; their metadata carries
  those keys). The rebuilt run reproduces them with the staged `ccbb215`
  adapter invoked directly.
- Union builder `ccbb215` (`scripts/build_tokenized_dfm10_tree.py`): the
  rebuilt union is assembled by the committed builder over the rebuilt DFM9
  union as base. The historical manifest predates that commit and omits the
  `dfm10_synthetic_values_model_charter_da` component path (recorded in
  `FALLBACK_TREES`), so the rebuilt manifest gains that key; verification
  compares task inventories, not manifest bytes.
- Sampling policy `data_io/prefix_config_dfm10.yaml` @ data_io `1f52b10`
  (2026-08-31 11:43 "Expand DFM10 sampling policy"); the working-tree file
  matches byte-for-byte. Sampling: 10 epochs, seed 0, concat_workers 4;
  compare target `data/sampled_dfm10` (total_length 92,658,813,451).
- Tokenizer chain inherited from the DFM9 lock (gemma4_31b tokenizer with the
  frozen post-processor and semantic digest). Standing instruction
  (2026-11-03): never run the old tokenizers or a non-Gemma-4 tokenizer
  template — the Gemma-4 native chat template at the DFM10 data_io pin
  (`1f52b10`, with mapping/sequence tool-body handling) is the pinned
  template; 0483afe predates it and cannot tokenize the DFM10 sources.

## Sources are frozen local inputs

All 4,351 component tasks' tokenization inputs survive locally. 4,335
resolve by exact `(source_mtime, source_size)` against
`data/converted_sources`, the `data/dfm10_*source*` trees (with symlink
following for the audited Folketing gz files in
`dfm10_folketing_transform_sources_audited`),
`data/mimir_benchmark_campaigns/accepted`, and
`data/mimir_answer_contract_calibration/final`. One task
(`sapient_scibench_repaired__train.parquet`) lost its mtime because the
source was re-saved after tokenization; it resolves by name and size
(`FALLBACK_SOURCES`) and the verify stage proves content. Ambiguous
mtime/size matches (hardlinked duplicates) are resolved by sha256 equality
with a `converted_sources` preference. The lock digests every source, so
`prepare` re-verifies content before linking the sources into the work tree.

No HF acquisitions are needed for the additions: the repaired sources are
model-audited local artifacts, and re-running those repair pipelines is out
of scope for the rebuild. The lock therefore has an empty `acquisitions`
map, and source provenance is the digest pin plus the wiki repair runbooks.

## Verification scope

`verify` compares all 4,351 addition tasks' five arrays against
`data/tokenized_dfm10/<task>`; the base tasks are covered by the DFM9
matched receipt (minus the 18 replaced tasks, which the builder excludes).
The union inventory must equal the historical 15,748-entry tree.

Status 2026-11-03: recover-lock ran after DFM9 reached `matched` (config
written: base 11,395 + additions 4,351 = 15,748; template_revision 0483afe).
Three first-run fixes were needed in `scripts/rebuild_dfm10.py`:
(1) `prepare` called `check_config` before `inputs-verified.json` existed —
it now loads the lock directly on first run and keeps the digest check on
re-runs; (2) `prepare` staged the chat template from the data_io pin
(`1f52b10`, which already carries the DFM11-era mapping-valued template
`e9584e0` lineage) and asserted equality with `TEMPLATE_REVISION` 0483afe —
the template is now staged from `TEMPLATE_REVISION` 0483afe directly (DFM10's
tool bodies are string-valued; mapping-valued responses are DFM11); (3)
source staging used `allowed()` which resolves symlinks, and the reservoir
trees contain symlinks to files outside the repo (e.g.
`/work/dfm/andersen/...`) — containment is now checked on the in-repo path
(`source_path_ok`, same roots `source_index` enumerates) with content
guaranteed by the lock's sha256+size pins. Prepare verified and staged all
4,351 sources on 2026-11-03; the guarded runner advanced to tokenize.

### Existing repaired OPUS publication confirmed (2026-11-08)

Live HF inspection confirmed `schneiderkamplab/dfm10-opus-da-en-repaired`
at `76989fcedaed661bc0b9f44719198bf67396a545`: 165 compressed JSONL
shards, 41,155,546 rows originating from 64 converted source files. Its
card identifies the accepted repaired source tree used by final DFM10.
The current HF-only reconstruction already consumes this publication; it
does not redo the language/alignment repair. The proposed rebuild-ready
publication is an optional format/task-boundary cache (64 Parquet inputs),
not recovery of previously unpublished repaired data. Earlier wording that
suggested the repaired versions were absent from HF was misleading.

### Optional publication cancelled (2026-11-08)

User explicitly cancelled the superfluous rebuild-ready uploads. Stopped
the waiting OPUS publisher before any repository creation/upload receipt
was produced, and wrote `opus-publication-cancelled.json`; the publisher
refuses restart while this marker exists. This supersedes the earlier
OPUS publication authorization/schedule. Use the existing repaired HF
publication. DFM10 verification and the gated DFM11 runner remain active.

### Tidsskrift mapping repaired; materialization resumed (2026-11-08)

After the scoped unpack completed, mapping stopped on one nine-row task,
`tidsskrift_open_article_summaries.jsonl`. The pinned Tidsskrift SFT HF export
already contains these rows, marked `row_origin=gold_author_abstract`. The
historical builder appends them in original order, adding only origin and
training-token metadata. Recovery now selects those nine unique source IDs
in export order, removes those added metadata fields, and records HF lineage.
No local text supplies the reconstruction. All five token/index arrays for
the recovered task match the historical reference exactly; receipt:
`data/rebuild_hf_dfm/dfm10-hf-v2/tidsskrift-smoke/comparison.json`.

Task mapping is now complete: 4,351 mapped, zero missing/ambiguous. Added
per-task materialization receipts and atomic writes so interruptions do not
repeat completed conversions. Restarted the detached DFM10 continuation,
resuming at materialization. Sixteen focused tests passed. OPUS publication
remains cancelled; DFM11 remains gated on full exact DFM10 verification.

### Native Parquet materialization fixed (2026-11-08)

Materialization stopped after 162 tasks at the first native Nemotron terminal
Parquet input: the materializer previously required an HRM condition column
for all Parquet files. Added explicit native schema matching the frozen
converter: a list of role/content message structs, source_file, and
upstream_metadata. Unexpected message fields are rejected rather than lost.
All 214 rows/columns of a reconstructed native shard match its historical
reference; all five token/index arrays also match exactly (4,819,977 tokens).
Receipts: `data/rebuild_hf_dfm/dfm10-hf-v2/native-smoke/{row-comparison,comparison}.json`.

Preflight checked first-row schema compatibility for 4,182 distinct non-native
Parquet inputs, finding no additional incompatible schemas. Nine focused tests
passed. Resumed materialization using the 162 completed per-task receipts;
the continuation now clears stale errors on resume. Full DFM10 verification
is still pending; DFM11 remains gated and optional OPUS publication cancelled.

### Native tail parallelized (2026-11-08)

User requested applying the previously used split/tokenize/join strategy to
the remaining native math task. Stopped only the isolated DFM10 continuation
and tokenizer process tree (67 processes); retained 4,322 standard outputs
and 28 complete native outputs. The math task had no completed output.

`scripts/tokenize_dfm10_native_sharded.py` now handles native tasks. Completed
outputs are retained only with complete arrays and matching source size/mtime,
4096-token setting and preserve-first-user flag. Missing tasks are split by
original Parquet row groups using `shard_dfm7_large_parquets.py`, tokenized
with the frozen native adapter across up to 64 workers, then joined in lexical
row-group order using `join_tokenized_shards.py`. The helper verifies all five
joined arrays against the historical reference before linking the task into
the native output tree. Shard source hashes and completed outputs support resume.

For math: 162,692 input rows, 318 row-group shards. No conversation is split
between shards. A six-row Unicode/multi-turn native fixture produced identical
five arrays with whole-file tokenization and a three-shard join; evidence at
`data/rebuild_hf_dfm/dfm10-hf-v2/shard-validation/passed.txt`. Eighteen focused
tests passed. The continuous DFM10 pipeline was restarted and confirmed to
reuse standard outputs, enter the sharded helper, and preserve completed native
tasks. Full historical verification remains required; DFM11 stays gated.

### Historical token limits restored (2026-11-08)

After sharded math matched and assembly completed, exact verification detected
DeepDive token counts 98,214,430 versus historical 19,735,601. The standard
bounded driver had omitted the historical 4,096-token cap. Auditing all
4,351 reference metadata records identified 14 affected non-native tasks:
DeepDive plus 13 repaired DOLCI tasks, all with max_seq_len=4096 and
preserve_first_user=false. The 29 native terminal tasks retain their separate
preserve-first-user=true path. Uncapped tasks are unchanged.

`scripts/restore_dfm10_token_limits.py` stages only these 14 HF-reconstructed
inputs and runs the frozen native-capable ccbb215 adapter with the correct
settings. It compares all five arrays for every task before publishing any
replacement. Uncapped outputs are archived, not deleted. A policy/hash receipt
records the correction; existing union links continue to resolve the corrected
outputs. The regular recipe now excludes capped families from the unlimited
driver, so fresh runs do not repeat this omission.

Inserted a resumable restore-limits stage before full verification and
restarted the continuation. Remaining stages are full verification, ten-epoch
sampling and exact final comparison. DFM11 remains gated; optional OPUS uploads
remain cancelled. Metadata coverage test confirms exactly the 14 affected tasks.

### DOLCI ordering recovery (2026-11-08)

The capped correction above completed, but six DOLCI tasks still differed in
sparse token values (all shapes and index arrays matched). Investigation found
that the published HF export recursively sorted JSON keys. The frozen Jinja
`dictsort` is case-insensitive and stable: keys such as `hello`, `HELLO`, and
`Hello` retain insertion order on ties. Thus semantic JSON equality did not
imply identical rendered training text.

A raw replay also exposed historical nondeterminism: `json_safe` converts
Python sets into lists, whose ordering varies across processes. Raw replay
alone is therefore insufficient. `scripts/recover_dfm10_dolci_order.py` uses
the seven checksum-pinned, isolated HF raw DOLCI Parquets from the DFM7 lock
and frozen ccbb215 repair/staging code to recover mapping insertion order.
It preserves all values and list order from the published HF reconstruction.
Schema/row-count mismatches fail closed. All 13 resulting files matched the
historical source SHA-256 and byte counts exactly. Local historical files
were inspected only to diagnose differences; they are not reconstruction inputs.

Evidence is in `dfm10-hf-v2/dolci_order_recovery/verified.json`, with raw HF
pins, converter code hashes and recovered source hashes alongside it.
The limit-restoration helper now uses these verified inputs, journals their
receipt hash, and writes a separate `capped_tokenization_order_restored` stage.
The earlier mismatching capped outputs remain preserved. Twenty focused tests
passed, including case-tie rendering and preservation of published list order.
The continuous pipeline resumed at restore-limits; full token and final sampled
array verification remain required. DFM11 remains gated and OPUS uploads remain
cancelled. This supersedes any implication above that restoring token limits
alone resolved every DOLCI difference.

### Nemotron SWE designated-target correction (2026-11-09)

DOLCI/DeepDive correction completed: all 14 tasks matched all five arrays.
Full verification then stopped at SWE shard 00000: 549,877,466 rebuilt tokens
versus 197,239,862 historical tokens. The cd88c93 adapter ignores
`target_message_index`, yielding an example for every preceding assistant
turn as well as the designated target. All 33 SWE JSONL tasks carry this
marker. The frozen ccbb215 adapter supports target selection without dropping
preceding context; SWE uses no token cap.

`scripts/restore_dfm10_swe_targets.py` now validates HF source hashes,
retokenizes these 33 tasks with ccbb215, and requires all five arrays per task
to match before replacing canonical rebuilt outputs. Earlier outputs are
archived. The recipe excludes SWE from the old unlimited-adapter stage,
including removal of stale staging symlinks, and the continuation inserts
`restore-swe-targets` before verification. This supersedes the original claim
that cd88c93 was appropriate for every standard historical DFM10 task.

All five arrays for a 100-row SWE prefix match the historical prefix exactly
(receipt: `dfm10-hf-v2/swe-prefix-check/verified.json`). Twenty-one focused
tests passed, including frozen-adapter target selection with prior assistant
context retained. Full 33-task retokenization is running with 16 CPU workers;
full verification, sampling and final comparison remain pending. DFM11 remains
gated. No production data or uploads were changed.

SWE completion update (2026-11-09): all 33 tasks / 2,472,316 designated
examples were retokenized in 1,013.9 seconds. All 165 arrays matched history
exactly; `swe_target_tokenization/published.json` records successful replacement.
Full verification is running, last reported 750/4,351 additions with no new
mismatch. Sampling and final comparison remain pending; DFM11 is still waiting.

User pause (2026-11-09): explicitly stopped DFM10 continuation/verifier and
DFM11 waiting scheduler. All three processes exited after SIGTERM. Progress
receipts are marked paused; completed outputs are preserved. Full verification
last logged 750/4,351; no final verification receipt exists. Resume only on
user instruction. Training/evaluation processes were not touched.

User resume (2026-11-09 14:49 UTC): supersedes the pause above. Restarted the
DFM10 continuation (PID 733670; verifier 733676) and DFM11 waiting scheduler
(PID 733671); confirmed running/waiting receipts and live processes. Completed
reconstruction/correction stages are reused. The verification loop has no
per-task resume receipts, so its comparison pass restarts from the first task.
DFM11 remains gated on complete exact verification; training/evals untouched.

Verification milestone (2026-11-09): `all-token-comparison.json` now confirms
all 4,351 fresh tasks match historical arrays. Ten-epoch sampling completed.
Final sampled comparison is running on `tokens.npy` (about 2h37 elapsed at
inspection, blocked on filesystem page reads); no mismatch reported and no
final `verified.json` yet. DFM11 remains waiting on that final exact receipt.

Final comparison update (2026-11-10): supersedes running status above. The
comparison passed `tokens.npy`, then failed on `epoch_0/inst_start.npy`: rebuilt
224,618,876 entries versus historical 224,091,694 (both int64). Continuation
is blocked and exited; no final verification receipt exists. The cause of
the sampling-index mismatch is not yet established. All fresh task arrays
remain verified; DFM11 scheduler is alive but waiting.

### Historical sampling mode restored (2026-11-10)

Investigation of the epoch-index mismatch found the HF continuation omitted
`default_long_context=drop`. All three historical DFM10 sampling entrypoints
(`prepare_dfm10_data.sh`, `finalize_dfm10_when_ready.sh`, and
`resample_dfm10_current.sh`) explicitly pass this setting. The sampler default
is truncate, which admits extra overlength examples and changes sampling RNG
consumption. The prefix file matches history; current sampler changes since
1f52b10 only add optional row selection, unused here.

`finish_dfm10_hf.py` now constructs an explicit drop-mode sampling command,
records it in `sample-command.json`, and uses `reuse_tokens=true` when a token
store already exists (sampler validates shape/dtype). Preserved the mismatching
epoch arrays, metadata and old continuation receipt in
`sampled-truncate-history`; retained the HF-rebuilt token store that passed
exact comparison. Reset only sample/compare completion and restarted the
continuation (PID 2222997) with ten epochs and seed 0. Sampling is confirmed
running; final exact comparison will run automatically. DFM11 remains gated.

Twenty-two focused tests pass, including a regression check for the historical
sampling option and conditional token reuse. Corrected full index equality is
still pending; this update supersedes the unexplained-mismatch status above.

Completion (2026-11-10): corrected drop-mode sampling passed the entire final
comparison: all 41 arrays (combined tokens plus four index arrays for each of
ten epochs) and metadata match history exactly. `verified.json` records matched
HF-only plus lexdk/DBC status; continuation is complete. This supersedes the
pending sampling/index-verification status above. DFM11 automatically passed
its predecessor gate and began reconstruction.
