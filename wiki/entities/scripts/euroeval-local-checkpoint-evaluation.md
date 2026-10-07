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
last_updated: 2026-10-07
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
