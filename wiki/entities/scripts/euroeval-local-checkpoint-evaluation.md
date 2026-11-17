---
type: Software Reference
title: EuroEval Local Checkpoint Evaluation
description: 'Part of Script Entities: EuroEval Local Checkpoint Evaluation.'
tags:
- scripts
- software
- catalog
- operations
status: stable
last_updated: 2026-11-16
confidence: high
part_of: /entities/scripts.md
---
# EuroEval Local Checkpoint Evaluation

Part of [Script Entities](/entities/scripts.md).

Added on 2026-06-12. Confidence: high for local syntax checks and dry-runs;
medium until a full EuroEval run completes against a checkpoint.

`scripts/run_euroeval_on_checkpoint.sh` runs EuroEval against a local HRM
checkpoint through `scripts/hrm_openai_server.py`. The requested default scope
is Danish and English only:

```text
EUROEVAL_LANGUAGES=da,en
```

The wrapper intentionally does not override EuroEval's standard evaluation
policy by default. In particular, it leaves few-shot/zero-shot choice,
`num_iterations`, and `generative_type` unset unless the corresponding
environment variables are explicitly provided. EuroEval's upstream CLI default
is few-shot with 10 iterations, with internal zero-shot fallback for tasks that
require zero-shot evaluation. The wrapper still passes the local API endpoint,
API key, cache directory, max context length, `--save-results`, and the
requested language filters.

Outputs per checkpoint:

```text
logs/euroeval/.../<CKPT_TAG>/server.log
logs/euroeval/.../<CKPT_TAG>/euroeval.log
logs/euroeval/.../<CKPT_TAG>/euroeval_benchmark_results.jsonl
logs/euroeval/.../<CKPT_TAG>/merged_metrics.json
logs/euroeval/.../<CKPT_TAG>/merge_and_wandb_sync.log
```

`scripts/log_euroeval_to_wandb.py` flattens EuroEval JSONL results to W&B
metrics under `euroeval/<lang>/<task>/<dataset>/...` and records
`euroeval/epoch` as the step metric. It filters to `da` and `en` in the
checkpoint wrapper.

Operational update on 2026-06-12. Confidence: high. Installing EuroEval into
the `hrm` conda environment was done directly because editable install of the
repo extra failed under setuptools' flat-layout package discovery:

```bash
uv pip install euroeval
```

This installed `euroeval==17.3.0` and downgraded `scikit-learn` from `1.8.0`
to `1.6.1`. EuroEval's import guard refuses any visible top-level
`flash_attn` package on non-ROCm builds. This conflicts with the local FA4
install, which provides top-level `flash_attn` from the `flash-attn-4`
distribution. For API-only EuroEval, use
`scripts/euroeval_api_no_flash_attn_guard.py`; it hides `flash_attn` only from
EuroEval's import guard in the EuroEval process. The HRM server process still
runs normally with FA4 visible.

Concurrency update on 2026-06-12. Confidence: high for local source inspection
and syntax check. EuroEval 17.3.0's LiteLLM backend hard-codes
`max_concurrent_calls = 20`. `scripts/euroeval_api_no_flash_attn_guard.py` now
supports `EUROEVAL_MAX_CONCURRENT_CALLS`; when set, it monkeypatches
`LiteLLMModel.__init__` after construction to override
`self.buffer["max_concurrent_calls"]`.

Verification:

```bash
cd /work/dfm/HRM-Text
PYTHONDONTWRITEBYTECODE=1 python -m py_compile scripts/euroeval_api_no_flash_attn_guard.py
```

Example launch using larger server and EuroEval concurrency:

```bash
cd /work/dfm/HRM-Text
EUROEVAL_BATCH_SIZE=32 EUROEVAL_MAX_CONCURRENT_CALLS=32 \
  scripts/run_original_sapient_l_euroeval_epochs.sh
```

## Mimir v1.5 direct-vLLM smoke finding (2026-10-07)

A separate EuroEval 18.1.0 / LiteLLM 1.104.0 smoke against eight vLLM 0.31.0
servers reproduced the structured-output issue documented in the
[native-compatible proxy probe](/pages/current-state/dfm5-xxs-step-50k-full-eval/chronology-native-compatible-vllm-proxy-probe-2026-06-18.md).
ScaLA validation completed in eight languages, but six language runs emitted
frequent missing-label warnings. Direct probes with the classification JSON
schema repeated whitespace until the output limit; the same Faroese prompt
through `scripts/native_compatible_openai_proxy.py` returned `Nei.` with a
normal stop within the original 10-token budget. This verifies the proxy path
for that probe, not a completed eight-language proxy rerun.

All eight servers rendered the supplied Mimir v1.5 chat template correctly,
with thinking disabled. A separate tokenizer discrepancy remains: with
Transformers 5.17.0, standard Hub loading and `local_files_only=True` loading
of revision `521b40b36a79918014544b970d4c2669ff1530eb` produced different token
IDs for identical rendered text. The servers matched standard Hub loading;
local loading applied the regex compatibility patch. Pin the model/tokenizer
revision and explicitly verify the intended token IDs before comparing with
historical local-export results. The proxy does not resolve this tokenizer
policy difference.

Evidence: `/work/dfm/euroeval-runs/mimir-v1.5-20261007/`, including
`chat-template-verification.json`, `proxy-verification.json`, per-language
structured-output probes, and the smoke manifest. These are diagnostic smoke
results, not final leaderboard measurements.

### Root-cause investigation and corrected protocol

Follow-up on 2026-10-07, confidence high for the reproduced probes. All eight
investigation vLLM servers were stopped before training resumed. Subsequent
inference ran on CPU (BF16, SDPA, bidirectional prompt token types), with
XGrammar 0.2.7; no training GPU was used.

The documented final export `exports/dfm11_XL_epoch10_epoch_10_ema_hf`
(step 2,877,261) was absent locally. The available
`exports/dfm11_XL_epoch10_step_2850000_ema_hf` has different weights. Tests
instead used a local directory reconstructed from the pinned uploaded snapshot
`521b40b36a79918014544b970d4c2669ff1530eb`. Its weights SHA-256 is
`226257d0d6c5dc04d920e48bb7079c3361dcf0866a950f4667bfcc9ae7bb6e48`,
matching the release metadata. The earlier checkpoint has identical config,
tokenizer JSON, tokenizer config, and chat-template bytes, but is not the
released weight checkpoint.

The JSON failure is a protocol mismatch in installed EuroEval 18.1.0:

- The prompt requests a bare localized yes/no label, while the out-of-band
  schema requires an object whose `label` is an unbounded array of strings.
- Grammar masking forces the object prefix. After `"label":`, the model
  prefers a string; the schema disallows that and permits whitespace before
  the required array. Whitespace wins over the array opening and repeats.
- These outputs are unfinished legal JSON prefixes truncated at the token
  limit, not completed schema-violating outputs. Raising the budget to 64
  did not eliminate the loop in the vLLM probe.
- Disallowing arbitrary whitespace alone can produce repeated labels in the
  unbounded array. Explicit JSON instructions or a single-label bounded
  schema resolved the corresponding CPU probes.

The EuroEval checkout identifies as 18.2.0 and already contains commit
`e32e2bc4e6b17849ac55420fd52ac255718dc155` (2026-10-05, fix #2201): JSON
answer examples in the classification prompt, a scalar `label` constrained to
allowed labels, and a 50-token classification budget instead of 10. Using
its actual public prompt formatter and corresponding schema, one validation
example per language under each tokenizer setting produced valid, normally
terminated JSON in **16/16** cases. The old 18.1 contract succeeded in only
**2/16**. This is a CPU protocol reproduction, not a complete vLLM benchmark
or evidence about aggregate task accuracy. The installed environment was not
upgraded during this investigation.

The regex discrepancy is independent. Transformers 5.17.0's
`tokenization_utils_tokenizers.py::_patch_mistral_regex` treats local paths
(including Hub loads with `local_files_only=True`) differently from online
Hub IDs. The online branch requires Mistral base-model metadata, absent here,
so it skips the patch even with explicit `fix_mistral_regex=True`. The local
branch encounters an HRM config with no `transformers_version` and falls
through its model-type/version checks, applying the exported true flag.
The patch prepends a Mistral regex Split to the Gemma tokenizer graph.

For example, raw tokenization merges `▁Dette`; patched tokenization splits it
into `▁`, `D`, `ette`. Both decode to the same text. Across the eight ScaLA
validation splits, 1,169/2,048 raw sentences had different token IDs. This
measures tokenization differences, not changes in correctness. Training's
`scripts/tokenize_chat_template.py` loads `Tokenizer.from_file` directly,
without this Transformers patch. Consequently, local explicit false matches
the raw training graph and the tested online Hub load, while local true
reproduces the patched historical local-evaluation policy. This agrees with
the September correction in
[the epoch-10 resume record](/pages/dfm11-xl-epoch10-resume.md).

For future evaluation, use the corrected EuroEval classification protocol;
retain the proxy only when deliberately reproducing the historical bare-label
protocol. Pin the checkpoint and effective tokenizer policy, assert token-ID
parity on fixed probes, and distinguish raw-training-tokenizer results from
historical patched-tokenizer results. Do not silently change published assets
or compare the diagnostic 18.1 smoke as final model-quality measurements.

Detailed evidence lives in
`/work/dfm/euroeval-runs/mimir-v1.5-20261007/investigation/`:
`version-comparison.json`, `tokenizer-matrix.json`,
`regex-validation-extent.json`, `cpu-loading-info.json`, and per-probe
`cpu-*.json` (including grammar-masked versus unmasked token preferences).

### Checkout installation and headroom smoke

At the owner's request, the `euroeval` conda environment was upgraded by
editable installation of `/work/dfm/EuroEval` (18.2.0, commit
`6089965d79d0112dcb3c97b1169f398d6ced4434`). `pip check` passed. Eight
vLLM servers on ports 8200–8207 used the exact released weights, an isolated
local tokenizer config with `fix_mistral_regex=false`, FLASH_ATTN, eager
execution, memory utilization 0.065, a 4096-token context/batched-token limit,
and 64 maximum sequences. Eight clients each completed one zero-shot ScaLA
validation iteration without missing-label warnings or reported failed
instances. An additional explicit JSON-schema probe per language returned
valid JSON with a normal stop in all eight cases. Observed per-server peaks
were 12,472–12,476 MiB (about 13.1 decimal GB), below the owner's 15 GB limit.
Training processes were left running. Servers were retained for reuse.

Evidence: `/work/dfm/euroeval-runs/mimir-v1.5-18.2-smoke/` contains the
manifest, per-language results and JSON probes, logs, and sampled memory peaks.

Historical interpretation remains important: raw training-tokenizer parity is
not a claim that disabling the patch improves scores. The controlled 2750K
comparison recorded substantial decreases on UK, HellaSwag, and AngryTweets,
a small ScaLA decrease, and an improvement on DFM Winogrande, with answer
formatting/truncation contributing to differences. See the
[regression review](/pages/dfm12-identity-euroeval-regression-review.md).
This new raw-tokenizer smoke verifies the corrected JSON protocol; it does not
reproduce the release's patched-tokenizer evaluation scores.

The owner subsequently requested the full eight-language run. Eight detached
clients started on 2026-10-07 using the same server pool, tokenizer policy,
and memory guard, with test splits, zero-shot, and ten iterations. EuroEval
selected 116 language-dataset jobs in total (da 17, en 13, nb 12, nn 12, sv 16,
is 15, fo 13, nl 18). This entry records launch, not completion. Results,
per-language logs/status, the manifest, and a periodically updated
`progress.json` live under
`/work/dfm/euroeval-runs/mimir-v1.5-18.2-full/`.

The owner expanded the run to remaining official EuroEval languages. A detached
scheduler (`/tmp/mimir-full-182/scheduler.py`) queues 25 additional full language
suites and one generic Norwegian job restricted to four tasks not selected by
Bokmål/Nynorsk (WMT24++, FLORES, RAGTruth, Multi-BFCL). European Portuguese is
omitted as a separate job because its nine tasks are included in Portuguese.
Each server takes a queued job only after its current client exits, its health
check passes, and its running/waiting request counts are zero. Failed clients
are recorded rather than silently treated as successful. No server restart or
memory-budget increase is required. `scheduler-state.json` and `scheduler.log`
in the full-run directory track assignments; telemetry now follows dynamic
language-to-port assignments and remains active through the entire queue.

The owner subsequently requested stopping evaluation on 2026-10-07. The
scheduler, active clients, telemetry/watchers, memory guard, and all eight
run-owned vLLM servers were terminated. Training processes were left running.
Completed results, partial-run caches, logs, and telemetry were preserved;
active and queued jobs are marked stopped in `scheduler-state.json`.

The owner then authorized automatic full-memory resumption once training
releases the GPUs. No vLLM servers remained at setup. The detached
`/tmp/mimir-full-182/resume_when_free.py` watcher requires three consecutive
30-second checks with no GPU compute processes and at least 96% free memory
on all eight GPUs. It then starts eight servers with utilization 0.95 and the
same model, tokenizer, FLASH_ATTN, eager execution, and concurrency 64. It
waits for all health checks before resuming interrupted languages ahead of the
remaining queue. Existing result files and caches are retained. The former
15 GB memory guard is not restarted. `resume-status.json` records whether the
watcher is waiting, starting, resumed, or failed; server logs/commands are
stored in `full-memory-servers/`. This documents scheduling, not a completed
restart. Training processes are never terminated by the watcher.

After full-memory resumption, six language clients reached RAGTruth and spent
extended periods on CPU while their servers had no requests. The API clients
hide CUDA, and the hallucination metric invokes a separate transformer detector
per prediction. The user reported idle GPUs. The scheduler was changed to admit
one additional queued language after a server has had zero running/waiting
requests for 30 seconds, bounded at two live language clients per server.
Existing clients keep scoring and may subsequently share inference capacity.
This replaces the earlier strict one-client-per-server policy, without changing
model outputs, scoring configuration, or server memory settings. Telemetry labels
show both assigned languages where applicable.

On 2026-10-08, completed local v1.5 records were compared with live
euroeval.com CSV assets for `danish-foundation-models/DFM-Mimir`, selecting
its zero-shot validation rows. There are 224 matched datasets (447 metric
pairs), plus 38 supplementary values/hallucination metric pairs. Primary
scores are higher on 126, lower on 97, equal on one. Knowledge and common-sense
scores mostly increase; reading comprehension mostly decreases. SQuAD F1
85.75 to 27.89 and Icelandic sentiment MCC 18.20 to 0.07 are notable flags,
with zero locally reported failed instances. This is descriptive only: v1 uses
validation and mostly EuroEval 18.0.0; v1.5 uses test, 18.2.0, corrected JSON,
and explicit raw training tokenization. Six shared Norwegian datasets were
counted once, using Bokmål records. No causal model-quality or leaderboard-rank
claim follows. Sources, complete comparison CSV/JSON, duplicate records, and
caveats are retained in the full-run directory's `comparison-with-mimir-v1/`.

On 2026-10-08 the owner requested all validation splits after XXL-wide reaches
874K and releases the GPUs. A separate campaign is staged under
`/work/dfm/euroeval-runs/mimir-v1.5-18.2-validation/`. Its detached watcher
`/tmp/mimir-validation-182/resume_when_free.py` polls every ten seconds and
requires three consecutive checks with no GPU compute processes and 96% free
memory on all eight GPUs before launching the previous 0.95-utilization,
FLASH_ATTN, eager, 4096-context, 64-sequence server configuration. This is a
GPU-release gate, not independent verification of the training checkpoint.

All 34 language selections explicitly use `--evaluate-val-split`, zero-shot,
and ten iterations. Generic Norwegian covers its four additional tasks;
European Portuguese is covered by Portuguese. CPU-scoring clients no longer
reserve the server: the scheduler admits another queued language after ten
seconds without running or waiting requests, with no two-client cap. There
are only 34 language jobs total. A wrapper records RAGTruth CPU metric phases
without changing metric inputs or computation. Metrics and per-process GPU
utilization are logged as in the test campaign. Context-window failures receive
at most two retries with client prompt budgets 4032 and 3968; the initial
budget and server limit remain 4096, and each adjustment is recorded. Completed
datasets remain saved and are skipped on retry. Test results stay separate.

Before GPU takeover, the owner expanded validation to both zero-shot and
few-shot. The queue now contains 68 language/mode jobs (34 per mode), using
explicit `--zero-shot` or `--few-shot` with `--evaluate-val-split` and ten
iterations. Result directories are `zero-shot/<language>/` and
`few-shot/<language>/` under the validation campaign root, with independent
caches and status files. EuroEval's task-specific zero-shot requirements still
apply within a few-shot suite. The same idle-server dispatch and GPU-release
gate remain active; training was not interrupted.

The validation campaign also has a detached submission exporter. Native
`euroeval_benchmark_results.jsonl` files are preserved for restart behavior.
The canonical model name/ID stays `danish-foundation-models/DFM-Mimir-v1.5`;
shot mode and validation split come from the actual record fields. Under
`submission/`, the exporter refreshes `DFM-Mimir-v1.5__validation__zero-shot.jsonl`,
`DFM-Mimir-v1.5__validation__few-shot.jsonl`, and an `all-modes` bundle every
30 seconds. It deduplicates dataset/mode identities, prefers the corresponding
explicit-mode source, records duplicate provenance and validation errors, and
marks unfinished bundles partial in `submission-index.json`. It does not
rename model IDs, relabel forced-zero-shot tasks, modify native records, or
upload/approve results. The manifest retains the exact checkpoint, tokenizer,
server settings, and prompt-budget retry policy for submission review.

The owner explicitly authorized 8192-token context after Faroese few-shot
ZebraPuzzlesEasy exceeded the 4096 server window. On 2026-10-08 the validation
pool was restarted with `--max-model-len 8192`,
`--max-num-batched-tokens 8192`, and `VLLM_ALLOW_LONG_MAX_MODEL_LEN=1`.
Weights, tokenizer, FLASH_ATTN, eager execution, memory utilization 0.95, and
concurrency 64 remain unchanged; no RoPE scaling was introduced. Client
budgets are now 8192, and the ineffective smaller-budget retries are disabled.
Interrupted and context-failed jobs were requeued while saved dataset results
were retained. This leaves completed 4096-context records alongside new
8192-context records; the transition is recorded in the manifest and snapshot
`state-before-8192.json` for submission provenance. All eight servers became
healthy. A real completion request with 4100 prompt tokens and one output token
succeeded (`context-8192-probe.json`).

### Correction: 8K request limit did not extend the HRM RoPE cache

On 2026-10-08, the remaining Faroese few-shot non-Zebra tasks completed on
GPU0: grammatical correctness exact match 3.98, semantic relations MCC 35.67 /
accuracy 48.51, metaphorical explanations MCC 41.39 / accuracy 58.29.
The subsequent Zebra investigation reproduced a different failure from the
original context rejection: a 4229-token few-shot prompt caused NaN log
probabilities without JSON constraints, and XGrammar rejected generated token
0 with HTTP 500 when JSON constraints were enabled. A 436-token control worked.

Installed `vllm/model_executor/models/hrm_text.py` builds `get_rope` using
`config.max_position_embeddings`, still 4096. The earlier
`VLLM_ALLOW_LONG_MAX_MODEL_LEN=1` plus server limit 8192 only permitted longer
requests; it did not extend that cache. The prior 4100-token smoke checked
HTTP success without checking finite logits and was insufficient verification.

GPU0 was restarted with `--hf-overrides '{"max_position_embeddings":8192}'`.
Replaying the exact long prompt then succeeded both with and without JSON,
with finite log probabilities. The full constrained response was valid JSON,
stopped normally, and used 4229 input + 53 output tokens. RoPE frequencies,
weights, and tokenizer are unchanged. This establishes a serving configuration
error, not a demonstrated model inability to handle 8K or a JSON-schema error.
Only GPU0 was corrected in this investigation. The remaining Zebra evaluation
was restarted there. Earlier requests whose positions exceeded 4096 require
an audit before leaderboard submission; the manifest records this limitation.
Evidence: validation campaign `zebra-investigation/`.

The corrected Faroese few-shot Zebra rerun completed all ten iterations with
zero failed instances: cell-wise accuracy 60.08 and puzzle-level accuracy
22.50. The short-prompt before/after control had identical generated text and
identical token log probabilities. All 68 language/mode jobs now have saved
results; refreshed bundles contain 442 records per mode and 739 deduplicated
records combined. This completion does not clear the documented audit of earlier
requests above 4096 positions. Submission index metadata includes that audit.


## 2026-10-08: SQuAD zero-shot regression diagnosed

Confidence: high for the reproduced output failure; training origin unverified.
A fresh one-iteration validation reproduction on the uploaded v1.5 weights,
raw tokenizer, FLASH_ATTN, and corrected 8192-position RoPE cache scored
25.33 F1 / 20.00 EM zero-shot versus 88.57 F1 / 75.29 EM few-shot.
Of 170 unique zero-shot evaluation requests, 125 hit the 32-token output
limit and 124 emitted literal `<think>` text. All 170 few-shot responses
stopped normally and none emitted `<think>`. Maximum input lengths were
549 and 1039 tokens respectively, ruling out the earlier 4096-position issue.

The Gemma chat template's `enable_thinking=false` omits the special thinking
marker; it does not enforce suppression of literal `<think>` generation.
EuroEval's reading-comprehension extractor lowercases the entire generated
answer and does not remove these reasoning strings. Thus the metric sees
truncated preambles instead of short answer spans. The model was explicitly
asked to answer in at most three words, but often did not comply zero-shot.

Diagnostic interventions on 160 context-matched unique questions raised F1
from 26.11 to 73.95 by appending an explicit answer-only/no-reasoning instruction
with the same 32-token budget. Eighteen responses still entered thinking mode
and hit the limit. On 16 selected baseline length failures, raising only the
output allowance to 512 tokens left 10 length failures; raw F1 was 3.73
versus 4.06 at baseline. Removing completed think spans post hoc yielded
22.81 F1 on those 16, still not a sufficient fix. These probes use subsets
rather than the benchmark's bootstrapped scoring and are diagnostic only.
Do not substitute modified-prompt probe scores into the official bundles.

Artifacts and scripts: `/work/dfm/euroeval-runs/mimir-v1.5-18.2-validation/squad-investigation/`.
One temporary GPU7 server used about 12.1 GB alongside training and was
stopped after the probes. Official submission records were unchanged.


## Mimir v1.8 all-language validation queue (2026-10-19)

The user named the original XL step 3,800,000 EMA checkpoint **Mimir v1.8**.
This is distinct from the gated Mimir2 3.82M pilot and its controls. Source:
`incoming/mimir-xl-20261015/checkpoints/dfm15/XL-from-dfm14-epoch1`,
tag `step_3800000`. CPU export completed with 131 tensors and 1,786,775,040
parameter elements. The campaign's isolated export is under
`/work/dfm/euroeval-runs/mimir-v1.8-3800000-validation/model`.

The detached launch watcher is
`/tmp/mimir-v18-euroeval/launch_when_free.py`; scripts are backed up under
`launch-scripts/` in the campaign directory. Its initial PID was 186567.
`launch-status.json` is authoritative for current state. At launch all eight
GPUs were occupied by the existing 3.82M evaluation; no process was interrupted.
The gate requires three consecutive checks, ten seconds apart, with no GPU
compute processes and at least 96% free memory on all eight GPUs. It does not
modify the main scheduler or its training handoffs. The watcher survives shell
exit but must be restored after a node reboot; `/tmp` is not durable storage.

Plan: all 35 language codes with official EuroEval datasets, validation splits,
ten iterations, zero-shot plus applicable few-shot; 444 unique zero-shot/shared
datasets and 297 additional few-shot evaluations (741 expected records).
Shared datasets run once. Forced-zero-shot records retain their native metadata
and appear in both separate mode bundles, once in the combined bundle.
The model/server/result identity is `danish-foundation-models/DFM-Mimir-v1.8`,
a local submission label, not a claim that a Hub release already exists.

Eight persistent vLLM servers use ports 8200-8207, FLASH_ATTN, 0.95 utilization,
64 sequences/client requests, eager execution, and 8192 context with the actual
`max_position_embeddings=8192` override. Prefix caching and chunked prefill are
disabled. CPU RAGTruth scoring does not reserve server scheduling capacity;
at most two preparing/generating language clients share a server. Telemetry
records KV occupancy, request queueing, throughput, utilization, and GPU memory.
Owned servers are stopped when the campaign finishes.

The exact training-data chat template was copied from the transferred
`data/sampled_dfm15/chat_template.jinja`. The isolated tokenizer sets
`fix_mistral_regex=false`; token IDs match the raw training tokenizer on text
and rendered chat probes. Weight and tokenizer SHA256s are recorded in
`model-verification.json`. The EuroEval source commit is frozen in
`euroeval-source.tar` and used via an isolated PYTHONPATH snapshot. Before
benchmarking, the watcher requires successful structured JSON and finite
logprobs on every server, server token-ID parity, and finite generation after a
5,000-token prefill. These GPU checks are pending while GPUs remain occupied.
The protocol keeps standard EuroEval scoring and does not apply the previous
SQuAD diagnostic answer-only modification.

Results: `submission/DFM-Mimir-v1.8__validation__zero-shot.jsonl`,
`DFM-Mimir-v1.8__validation__few-shot.jsonl`, and
`DFM-Mimir-v1.8__validation__all-modes.jsonl`. The submission index marks missing
records and errors as partial. Queue preparation and CPU checks are verified;
no new evaluation score was available at the time this entry was written.


Shutdown monitoring update (2026-10-19): after 68/69 language/mode jobs
completed, the user explicitly requested monitoring through GPU release.
An independent detached verifier, `/tmp/mimir-v18-euroeval/verify_release.py`
(initial PID 404690), records `gpu-release.json` in the campaign directory.
It waits for scheduler completion, allows the launcher 180 seconds to release
its allocations, and verifies GPU-process ownership by recorded session IDs
and process start times before signalling any surviving evaluation processes.
It never signals unrelated workloads. At installation, only Croatian zero-shot
remained and 737/741 result records were saved. GPU release is not confirmed
until `gpu-release.json` reports `released`.


Completion verified (2026-10-19): all 69 language/mode jobs completed, with
741/741 unique records, no missing records, and no submission validation errors.
Zero-shot and few-shot bundles each contain 444 records including shared tasks;
the combined bundle contains 741. The launcher reports `complete` and the
independent release verifier reports `released`, with no surviving evaluation
GPU processes and no fallback cleanup signals required.

## Mimir v1.8 export transfer preparation (2026-11-15)

Located and checked the original step-3,800,000 EMA export at
`/work/dfm/euroeval-runs/mimir-v1.8-3800000-validation/model`. The export log
confirms 131 mapped tensors and zero dropped tensors; the safetensors header
and payload extent were checked. Its five files total 3,605,754,331 bytes.
SHA256 checksums and the file inventory are recorded under
`logs/analysis/mimir-v18-transfer-20261115/`.

The user requested transfer to `ssh.cloud.sdu.dk`, port `6519`, destination
`/work/arbiter/mimir/DFM-Mimir-v1.8`. Two bounded SSH attempts (including explicit
IPv4) timed out before authentication. No remote files were transferred or
modified. Transfer remains pending endpoint reachability; the requested
destination and checksums are retained for resumption.

Transfer completion (2026-11-15): the user supplied the working endpoint
`130.225.164.228:8888`. Created `/work/arbiter/mimir/DFM-Mimir-v1.8` and transferred
all five export files as `ucloud` using rsync over SSH. Remote `sha256sum -c`
matched every file, including `model.safetensors`. This supersedes the pending
transfer status above; the original port-6519 timeout remains historical.
The completed receipt is
`logs/analysis/mimir-v18-transfer-20261115/transfer-receipt.json`.

## Mini release comparison: corrected full coverage (2026-11-16)

The previous 37/50-language DFM14 aggregate is superseded for checkpoint
selection: its roots omitted wave34 results and the DFM13 multilingual DFM
root. Combining all checkpoint-specific average roots yields 396/396 valid
metrics and 50/50 complete languages for both step 1500000 and step 1538766.
No GPU reevaluation was necessary. The registry and weighting are unchanged.

Equal-language scores are 65.740693 and 66.007505 respectively; epoch 3 wins
33 languages versus 17. Excluding English/Danish, scores are 66.042648 and
66.323617. This modest descriptive advantage supports retaining final epoch 3
for DFM-Mimir-v1.8-Mini; it is not a statistical significance claim.

Reproducible aggregation, source paths, full metric evidence and language
comparison are saved under
`logs/analysis/mini-release-checkpoint-comparison-20261116/`. Historical
scheduler reports remain unchanged.

### Public v1.8 releases (2026-11-16)

- [danish-foundation-models/DFM-Mimir-v1.8-Mini](https://huggingface.co/danish-foundation-models/DFM-Mimir-v1.8-Mini), revision `bb9e93c076a2db1e14f63c3c93447dbb8abf4119`; 14 file hashes verified against Hub, anonymous public access confirmed.
- [danish-foundation-models/DFM-Mimir-v1.8](https://huggingface.co/danish-foundation-models/DFM-Mimir-v1.8), revision `30485dbad6f3ce50d09eaa963b8a8fce53a4290c`; 12 file hashes verified against Hub, anonymous public access confirmed.

Both staged tokenizers passed raw-tokenizer parity for Danish, English and Unicode probes, native chat rendering and HRM configuration loading. Existing GPU smoke evidence was packaged; no new Hub-based GPU smoke was run. Runtime requires HRM-specific PrefixLM support; version numbers alone are insufficient. Publication receipts and scripts are under `logs/releases/mimir-v1.8-20261116/`. OKF validation retains the pre-existing oversized scheduler page error and 14 link warnings.

### Exact-release comparison limitation (2026-11-16)

The transferred scheduler snapshot for XL step 3800000 contains 46 done,
2093 pending and 64 running evaluation rows; all eight average rows are pending.
No complete checkpoint-matched integrated 50-language/headline result was
located locally for that XL checkpoint. The later standalone EuroEval
comparison is complete on its common 32-language population and must not be
represented as the integrated 50-language comparison. Mini final epoch-3
integrated results are available; nearby XL step 3850000 is not the released
checkpoint and must not silently substitute for it.
