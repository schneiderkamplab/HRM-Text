---
type: Technical Reference
title: vLLM HRM-Text Serving Status
description: 'Part of Model Architecture: vLLM HRM-Text Serving Status.'
tags:
- architecture
- hrm
- crm
- checkpoints
- inference
status: stable
last_updated: 2026-10-06
confidence: high
part_of: /pages/model-architecture.md
---
# vLLM HRM-Text Serving Status

## Talemaader Judge Truncation (2026-10-06)

Read-only inspection after DFM13 training resumed found the near-zero generative
Talemaader score is not a valid model-quality measurement. Saved Inspect logs in
`logs/dfm_evals/dfm12_XL_epoch11/step_3150000/generative_talemaader/` contain
808 samples: 798 have `Grade not found in model output`, all scored incorrect.
801 judge completions use exactly 64 tokens. The judge launch explicitly sets
`--max-new-tokens 64`; the scorer requests an explanation followed by a final
`GRADE: C/P/I` line. The Transformers server reports `stop` even when truncated,
concealing the limit. At 3100K, 800/808 grades are missing; at 3050K, 794/808.

Example: for `laegge et godt ord ind for nogen`, the model correctly answers
`At tale positivt om nogen eller goere noget for at fremme deres sag.` The judge
begins agreeing but runs out before its grade, producing an incorrect score.
There are also genuine model errors and source-reference issues: the saved
reference for `der er loebet meget vand gennem aaen siden ..` describes something
matching someone's wishes, whereas the model correctly says much has happened.

Recommended next work: give the judge a separate sufficient output budget,
validate a small saved-answer replay, treat missing grades as scoring failures
rather than wrong model answers, and rejudge cached generations without rerunning
the evaluated model. Review suspect source references before claiming benchmark
validity. No scorer, judge, dataset, or historical W&B values were changed during
this investigation.

Part of [Model Architecture](/pages/model-architecture.md).

## Installed implementation versus local adapters (2026-10-05)

### All-task follow-up at3143000 (2026-10-05)

The user requested coverage of every scheduled task, then clarified that
identical translated tasks should share a calibration and that upcoming evals
should use the **best tested throughput**, rather than maximizing KV occupancy.
This supersedes the occupancy-first selection in the3142000 experiment below.

Training was safely stopped after preserving `ephemeral_step_3143000` under
`checkpoints/preserved/xl-eval-calibration-3143000`. The existing3150K scheduler
row is prepared to resume that checkpoint with the same training policy/W&B run.

`scripts/prepare_all_eval_capacity.py` extracted actual3100K request evidence
for all266 pending3150K eval action/task variants. EuroEval uses recorded native
proxy outgoing payloads; DFM uses Inspect model events; standard evals use saved
prompts with their sampling contracts. A maximum64 representative requests per
task are selected across lengths. No benchmark scores are logged or changed.

`scripts/group_eval_capacity_tasks.py` reduces these to162 groups: translated
DaLA/GEC, ScaLA, Multi-IFEval, Multi-WikiQA, Winogrande and HellaSwag variants
share tests only within the same suite/template family and generation contract.
Each language contributes short/median/long requests. Distinct datasets are not
collapsed merely because they belong to the same task category.

`scripts/calibrate_all_eval_tasks.py` measures per-group candidates using server
KV token capacity, prompt lengths and observed output lengths/generation limits.
It records requests/s, tokens/s, steady/peak KV occupancy, failures and preemptions.
Safe selection requires no errors/preemptions and peak KV below90%. The judged
task additionally starts the production judge and replays its recorded requests;
this tests capacity, not the correctness of new answers against old judge inputs.
HTTP keepalive is shorter than the server timeout and transient disconnects get
bounded retries. The first ungrouped partial run is retained as evidence; its
successful nonduplicated task results are reused, its failures are not accepted.

Evidence root: `data/dfm13/xl3143-all-task-calibration/`.
Client log: `logs/xl3143-grouped-calibration.log`.
Detached finisher `scripts/finish_xl_eval_calibration.py` waits for cleanup,
applies tested choices under the plan lock to all pending matching tasks,
updates both client/server settings, and starts the original persistent scheduler.
It writes `applied.json` and `resumed.json`. Unmeasured failures are explicitly
listed and retain their existing settings, never mislabeled as calibrated.
The finisher has a90-minute guard so a stuck experiment cannot hold training
indefinitely; it signals only its verified calibration owner and requires cleanup
before launching training. Finisher log: `logs/finish-xl3143-calibration.log`.

**Completed:** all162 groups succeeded, covering all266 original action/task
variants; no unmeasured tasks remained. The finisher updated6,270 pending eval
rows, including the3150K and DFM13 blocks, and restarted scheduler PID879040 at
22:15 local time. Selected client concurrencies across the266 variants:
32 for21,64 for107,128 for61,256 for38,512 for38,1024 for1.
Examples: MATH/GSM8k256; ARC32; GovReport32; DaLA512; GEC256;
EuroEval ScaLA/Multi-IFEval64; batched English IFEval128/Danish64;
judge-backed Talemaader32. These are best among the tested candidates, not a
claim of a globally optimal batch size. Ten-second request-feeding windows
include completion draining; short-run timing noise remains possible.

Every pending eval has a per-task/group provenance field. Server capacity is
1024 sequences,16384 batched tokens and graph capture up to512; client concurrency
is independently tuned. Fixed `max_connections` overrides were removed so retry
halving affects DFM clients too. Original judge model, memory utilization, sampling,
prompt/tokenizer/scoring and W&B destinations remain unchanged. Best choices can
be below50% KV occupancy: the updated user instruction preferred throughput.

### Full-GPU capacity calibration at training step 3142000

The user requested a checkpointed pause, non-eager batch calibration targeting
greater than50% KV occupancy, then resume to3150000. Training stopped after
`ephemeral_step_3142000` was verified complete and preserved under
`checkpoints/preserved/xl-eval-calibration-3142000`. Scheduler training was reset
to resume that exact checkpoint with unchanged optimizer/EMA/data cursor/LR/run.

`scripts/calibrate_xl_eval_capacity.py` replayed saved3100K eval prompts against
the existing3100K EMA export on all8 GPUs, without W&B. Evidence:
`data/dfm13/xl3100-eval-capacity-20261005-v2` and `...-v3`; an additional short1024
check is in `data/dfm13/xl3100-eval-short1024-20261005-v1`.
These are capacity replays, not scored benchmark reruns or parity guarantees.

| Prompt family | Selected concurrency | Steady KV at0.95 utilization | Scope |
| --- | ---: | ---: | --- |
| DFM acceptability/correction |1024|58%|Applied to DaLA/GEC variants; translated variants extrapolate the measured family.|
| GovReport/Nordjylland summaries |64|56.5%|128 reached94-96% peak, rejected for insufficient margin.|
| DFM and batched EuroEval IFEval |512|63.3%|Measured512-token generation settings; longer production responses can exert more pressure.|
| Mixed standard tasks |1024|45.6%|Peak70%; **sustained50% target not met** at0.95. Applied to ARC/HellaSwag/DROP/GSM8k/MATH, not untested MMLU/BoolQ/Winogrande.|

Measured stages had no preemptions or request errors. Short-answer256 was faster
than1024 (~6.4K versus5.0K output tokens/s); the selected setting follows the
requested occupancy target, not peak throughput. IFEval256 was also slightly
faster than512. Small shards cannot realize these concurrent request counts.
Judge concurrency16 and other untested client settings remain unchanged.
The0.85 tests reserved judge space but did not run an actual judge concurrently.

All pending nonjudged eval server configurations now consistently use
`--max-num-seqs 1024 --max-num-batched-tokens 16384
--max-cudagraph-capture-size 512` for persistent reuse; eager remains disabled.
Changed client batches permit halving on retry. The persistent EuroEval OpenAI
runner now passes `EUROEVAL_MAX_CONCURRENT_CALLS` to its guard process, capped
by the retry batch; previously this path ignored the metadata setting.
Nine server-pool tests and44 combined capacity/pool/campaign tests pass.

Plan backup: `plan.before-calibrated-batches-3142k.tsv`; change receipt:
`calibration-3142k-applied.json`, both under the active DFM12 scheduler directory.
All calibration-owned servers were shut down before scheduler PID855375 resumed
the3150K training row at21:31 local time. Log:
`logs/scheduler/dfm12_XL_epoch11_noidentity/runner-after-3142k-calibration.log`.

The `hrm` environment now has vLLM `0.23.1rc1.dev102+ga46abb7ae`.
The historical environment observations below are superseded for this environment.
Direct SHA-256 comparison with upstream commit `a46abb7ae` confirmed that both
`model_executor/models/hrm_text.py` and
`model_executor/layers/attention/prefill_prefix_lm_attention.py` are identical
to upstream. HRM recurrence, fused gate/Q/K/V loading, and PrefixLM attention
are therefore not local patches in this installed version. This is a targeted
comparison, not certification that every installed vLLM file is unmodified.

Local serving adaptations are the explicit Gemma 4 chat template under
`evaluation/chat_templates`, `scripts/native_compatible_openai_proxy.py`
(benchmark message flattening, optional BFCL native tool conversion and response
normalization, optional context fitting), the fast-tokenizer instance locking
in `dfm-evals/dfm_evals/vllm_patches.py`, and scheduler launch settings such as
the FLASH_ATTN backend and eager execution. The benchmark proxy is not a
transparent general-purpose multi-turn chat proxy. Gemma 4 formatting does not
change the model architecture from HRM-Text to Gemma 4.

### Launch-mode smoke (2026-10-05)

`scripts/smoke_vllm_launch_modes.py` tested
`exports/dfm8_XL_step1650000_ema_hf` on GPU 7 alongside training, with
FA4, BF16, max context 4096, max sequences 2, GPU utilization 0.07,
greedy decoding, and nine English/Danish arithmetic, summary, JSON, code,
multi-turn and tool prompts repeated twice. No W&B logging or production
configuration changes during the smoke. Evidence (commands, server logs, prompts, token IDs,
responses, timings, process GPU memory samples):
`logs/smoke/vllm_launch_modes_20261005_retry/`.

| Launch | Readiness | Completion tokens / request wall second | Sampled server peak MiB | Exact outputs versus eager explicit |
| --- | ---: | ---: | ---: | ---: |
| Eager, explicit template | 40.0 s | 41.1 | 13,566 | 18/18 |
| Non-eager, explicit template | 86.0 s | 64.0 | 13,166 | 16/18 |
| Eager, checkpoint template | 44.0 s | 42.2 | 13,566 | 18/18 |

Non-eager successfully compiled and captured CUDA graphs (reported graph pool
0.04 GiB). The only differing prompt was the Danish summary, in both repeats:
both outputs were plausible but wording differed. This small, shared-GPU smoke
is not benchmark score parity or a dedicated throughput benchmark. Readiness
excludes a subsequent warmup request; sampled memory is not a CUDA allocator
peak. Production eager defaults were not changed during the smoke.

### Scheduled non-eager evaluations (2026-10-05)

At the user's request, removed `--enforce-eager` from all 7,222 pending/failed
rows carrying that setting in `logs/scheduler/dfm12_XL_epoch11_noidentity/plan.tsv`,
including the 3150K evaluation and installed DFM13 evaluation blocks. The edit
used the scheduler's exclusive `PlanLock` and atomic plan writer. Backup:
`plan.before-non-eager-20261005.tsv` in the same directory. This supersedes
eager execution for this campaign, not historical launch scripts elsewhere.

Only the training row was running; no servers or training processes needed
restarting. Persistent server launches now permit compilation/CUDA graphs;
FA4, templates, tokenization, EMA, batch sizes, utilization limits and judge
settings are unchanged. Full-batch memory and benchmark parity remain to be
observed on these evaluations; the smoke above is not proof of either.

The old 1650K bundled template differs functionally only by missing support
for dictionary-valued tool results: a separate CPU rendering test fails there
with the old template and succeeds with the explicit one. Standard OpenAI
string tool results and the other nine cases render identically. Recent
`dfm11_XL_epoch10_step_2850000_ema_hf`,
`dfm11_XXL_wide_epoch_2_ema_hf`, and
`dfm13_XXL_wide_step_800000_ema_hf` exports contain a template byte-identical
to `evaluation/chat_templates/gemma4_native_chat.jinja`; the explicit override
is redundant for those exports. Native vLLM chat serving needs no benchmark
proxy. Tool parsing can be enabled with `--enable-auto-tool-choice
--tool-call-parser gemma4`.

Initial diagnostic startup failed because the default FlashInfer sampler
could not find nvcc; retained in `logs/smoke/vllm_launch_modes_20261005/`.
Successful tests used the scheduler's `VLLM_USE_FLASHINFER_SAMPLER=0` and
`FLASHINFER_DISABLE_VERSION_CHECK=1`, plus
`CUDA_HOME=/home/ucloud/miniforge3/envs/hrm-cu132` and its bin directory on
PATH. This was an environment issue, not an eager/non-eager incompatibility.
The current vLLM build automatically disables chunked prefill and prefix
caching for this model's non-causal attention.

Added on 2026-06-16.

Upstream vLLM `main` / latest docs include a native HRM-Text implementation:

- Architecture: `HrmTextForCausalLM`
- Module: `vllm.model_executor.models.hrm_text`
- Reference model: `sapientinc/HRM-Text-1B`
- Key implementation detail: each H/L recurrence step gets a distinct vLLM-visible attention/KV-cache slot; PrefixLM prefill is handled via vLLM prefix-LM attention; fused `[gate | q | k | v]` attention weights are loaded through `MergedColumnParallelLinear`.

Local environment check:

```bash
python - <<'PY'
import vllm
print(vllm.__version__, vllm.__file__)
try:
    import vllm.model_executor.models.hrm_text as h
    print("has hrm_text", h.__file__)
except Exception as e:
    print("no hrm_text import:", type(e).__name__, e)
PY
```

Result in the current HRM env: `vllm 0.20.2` is installed, but `vllm.model_executor.models.hrm_text` is not present. Current `transformers 5.8.1` also does not recognize `model_type="hrm_text"` for `sapientinc/HRM-Text-1B`, so the local stack is behind the upstream HRM-Text support.

Practical implication: implementing HRM-Text math in vLLM from scratch is probably unnecessary if we can use a vLLM checkout/release containing `hrm_text.py`. The remaining local work is checkpoint export/conversion: map this repo's PyTorch/FSDP or unsharded `.pt` checkpoints into the HF/vLLM layout expected by `HrmTextForCausalLM` (`config.json`, tokenizer files, safetensors weights, correct H/L stack names, `z_L_init`, fused attention and MLP weights). Confidence: high for local checks; medium for upstream support until tested with a concrete exported checkpoint.

## Existing HF Conversion Script
Added on 2026-06-16.

The repo already contains one checkpoint-to-HF conversion script:

```bash
PYTHONPATH=. python conversion/convert_to_hf.py --help
```

Running without `PYTHONPATH=.` from repo root fails with `ModuleNotFoundError: No module named 'dataset_new'`, because Python puts `conversion/` rather than the repo root on `sys.path` when the file is executed directly.

Script behavior from inspection:

- Loads repo checkpoints via `simple_inference_engine.inference_load_checkpoint`, supporting both `fsdp2_<tag>` and `unsharded_<tag>.pt`.
- Can use EMA weights through the local optimizer/EMA path.
- Saves `config.json`, `model.safetensors`, and tokenizer files.
- Remaps local keys:
  - `model.H_level.core.layers.*` -> `model.H_module.layers.*`
  - `model.L_level.core.layers.*` -> `model.L_module.layers.*`
  - `model.zL_init` -> `model.z_L_init`
  - `embed_tokens.embedding_weight` -> `model.embed_tokens.weight`
- Leaves local `attn.gqkv_proj` names intact; upstream vLLM's `HrmTextForCausalLM.hf_to_vllm_mapper` maps `.attn.` to `.self_attn.`, so this is intentionally compatible with vLLM's current loader.

Superseded on 2026-06-17: `build_hf_config()` used to write `num_hidden_layers: cfg["n_layers"]`, which was wrong for `half_layers: true` HRM configs. `conversion/convert_to_hf.py` now exports `num_hidden_layers=n_layers//2` when `half_layers` is set, adds upstream HRM config fields (`L_bp_cycles`, `hidden_act`, `rope_parameters`, bias/dropout/cache fields), and can be run directly from repo root without manually setting `PYTHONPATH`.

Verified smoke export:

```bash
cd /work/dfm/HRM-Text
CUDA_VISIBLE_DEVICES=3 python conversion/convert_to_hf.py \
  --ckpt_path checkpoints/dfm5/XXS-fsdp-bf16 \
  --ckpt_tag step_10000 \
  --ckpt_use_ema true \
  --out_dir exports/_smoke_dfm5_XXS_fsdp_bf16_step10000_hf
```

Result: exported `config.json`, tokenizer files, and a 78 MB `model.safetensors`; mapped 27 tensors and dropped 0. For this XXS config (`n_layers=6`, `half_layers=true`), `config.json` correctly contains `num_hidden_layers=3`; safetensors keys include `model.{H,L}_module.layers.*.attn.gqkv_proj.weight`, `model.{H,L}_module.layers.*.mlp.gate_up_proj.weight`, `model.embed_tokens.weight`, `lm_head.weight`, and `model.z_L_init`. Confidence: high from local command output and safetensors inspection.

Remaining export validation before using this for production eval serving:

- Install or isolate a vLLM/Transformers build that actually includes `HrmTextForCausalLM`.
- Load the smoke export through HF or vLLM and verify no missing/unexpected weight keys.
- Compare greedy generations/logits for a fixed short prompt against `simple_inference_engine` on the same checkpoint and EMA setting.
- Then export DFM5-L checkpoints with the same converter.

Update on 2026-06-17: the HRM env was upgraded from PyPI `vllm 0.20.2` to a vLLM commit wheel that includes native HRM-Text:

```bash
cd /work/dfm/HRM-Text
uv pip install --upgrade vllm \
  --extra-index-url https://wheels.vllm.ai/a46abb7ae68acc13a4fc5870db98619b3f97c6e0
```

Installed version:

```text
vllm 0.23.1rc1.dev102+ga46abb7ae
transformers 5.12.1
torch 2.11.0+cu130
```

Validation:

- `import vllm.model_executor.models.hrm_text` succeeds.
- `ModelRegistry.get_supported_archs()` includes `HrmTextForCausalLM`.
- `evaluation.engines` still imports successfully.
- A tiny native-vLLM generation smoke using `exports/_smoke_dfm5_XXS_fsdp_bf16_step10000_hf` resolved architecture `HrmTextForCausalLM`, loaded the fused safetensors export, allocated KV cache, and generated a short string.

PyPI `vllm==0.23.0` was tested first and did not include `vllm.model_executor.models.hrm_text`. Its generic `model_impl="transformers"` path found Transformers HRM but failed to load our fused native-vLLM export because the generic Transformers backend expects split HF weights (`self_attn.q_proj/k_proj/v_proj/gate_proj`, `mlp.gate_proj/up_proj`) rather than fused `attn.gqkv_proj` and `mlp.gate_up_proj`. Confidence: high from local install/import/load tests.

Original Sapient L epoch-4 EMA export on 2026-06-17:

```bash
cd /work/dfm/HRM-Text
CUDA_VISIBLE_DEVICES=6 python conversion/convert_to_hf.py \
  --ckpt_path checkpoints/original_sapient/L \
  --ckpt_epoch 4 \
  --ckpt_use_ema true \
  --out_dir exports/original_sapient_L_epoch4_ema_hf
```

Result: mapped 99 tensors, dropped 0, wrote `exports/original_sapient_L_epoch4_ema_hf`. The export is 1.3 GB and contains `config.json`, `model.safetensors`, `tokenizer.json`, and `tokenizer_config.json`. Config sanity: `hidden_size=1280`, `intermediate_size=3584`, `num_hidden_layers=12` per H/L stack, `num_attention_heads=10`, `H_cycles=2`, `L_cycles=3`, `L_bp_cycles=[0,3]`, `max_position_embeddings=4096`, `pad_token_id=5`, `bos_token_id=6`, `eos_token_id=11`. Safetensors sanity: bf16 weights, expected fused `attn.gqkv_proj` and `mlp.gate_up_proj` keys, `model.embed_tokens.weight`, `lm_head.weight`, and `model.z_L_init`. Confidence: high from local export and safetensors inspection.

Equivalence comparison script added on 2026-06-17:

```bash
cd /work/dfm/HRM-Text
CUDA_VISIBLE_DEVICES=6 python scripts/compare_hrm_vllm_export.py \
  --ckpt-path checkpoints/original_sapient/L \
  --ckpt-epoch 4 \
  --ckpt-use-ema true \
  --export-dir exports/original_sapient_L_epoch4_ema_hf \
  --condition direct \
  --prompt 'Write one short sentence about Denmark.' \
  --max-context 256 \
  --max-new-tokens 16 \
  --gpu-memory-utilization 0.08 \
  --enforce-eager true
```

The script uses `InferenceCheckpoint.tokenize_prompt()` to generate exact prompt token IDs and feeds the same IDs to vLLM via `TokensPrompt`. Result for the prompt above:

```text
prompt_tokens: [6, 8, 6805, 674, 2120, 1088, 556, 13626, 44, 7]
simple_ids:   [341, 857, 399, 5339, 44, 11]                  # "The people are happy."
vllm_ids:     [341, 620, 322, 7857, 236, 95, 9861, 44, 11]   # "The man is wearing a hat."
same_prefix_tokens: 1/6
```

A one-token run with `--max-new-tokens 1` matched exactly (`[341]`, `"The"`). This strongly suggests that export weights, prompt tokenization, and prefill first-token logits are aligned, but the cached decode path diverges from the local `simple_inference_engine` after the first generated token. The native vLLM HRM implementation resolves `HrmTextForCausalLM`, loads the fused export, and uses distinct cache slots per H/L recurrence step; `TokensPrompt` supports `token_type_ids`, but `vllm.model_executor.models.hrm_text` does not currently reference token type IDs. Confidence: high for observed behavior; root cause still unresolved.

vLLM eval server opt-in added on 2026-06-17:

- New wrapper: `scripts/hrm_vllm_openai_server.sh`
- EuroEval wrapper `scripts/run_euroeval_on_checkpoint.sh` supports:

```bash
HRM_SERVER_BACKEND=vllm
HRM_HF_EXPORT_DIR=exports/original_sapient_L_epoch4_ema_hf
VLLM_DTYPE=bfloat16
VLLM_GPU_MEMORY_UTILIZATION=0.85
VLLM_EXTRA_ARGS='...'
```

- Main queue script `scripts/schedule_checkpoint_evals.sh` passes the same settings through for server-backed DFM, IFEval, and EuroEval jobs.
- Default remains `HRM_SERVER_BACKEND=simple`, using `scripts/hrm_openai_server.py` and raw repo checkpoints.
- Superseded on 2026-06-18: Standard `evaluation.main` shards used to remain on their configured engine even when server-backed evals opted into vLLM. `scripts/schedule_checkpoint_evals.sh` now has a separate standard-eval opt-in, documented below.

Validation performed:

```bash
bash -n scripts/hrm_vllm_openai_server.sh scripts/run_euroeval_on_checkpoint.sh scripts/schedule_checkpoint_evals.sh
DRY_RUN=1 HRM_SERVER_BACKEND=vllm \
  HRM_HF_EXPORT_DIR=exports/original_sapient_L_epoch4_ema_hf \
  CKPT_PATH=checkpoints/original_sapient/L CKPT_TAG=epoch_4 \
  EUROEVAL_LOG_ROOT=logs/tmp_dry_vllm_euroeval GPU=0 PORT=19999 \
  scripts/run_euroeval_on_checkpoint.sh
```

The dry-run printed the vLLM wrapper launch and EuroEval client command without starting a server. Confidence: high for syntax/dry-run wiring; runtime eval execution remains intentionally untested.

Standard eval vLLM opt-in added on 2026-06-18:

- `evaluation/engines.py` `VLLMEngine` now supports `prompt_mode=hrm`, which wraps prompts with the same HRM special-token format as `simple_inference_engine.InferenceCheckpoint.tokenize_prompt()`.
- HRM condition mapping in `VLLMEngine`:
  - `direct` -> `<|object_ref_start|>`
  - `cot` -> `<|object_ref_end|>`
  - `noisy` -> `<|quad_start|>`
  - `synth` -> `<|quad_end|>`
- In HRM prompt mode, vLLM generation stops on token id `11`, the local `<|box_end|>` response terminator.
- `VLLMEngine.generate()` accepts the HRM standard generation kwargs (`batch_size`, `max_context`, `condition`) and chunks prompts by `batch_size` so the scheduler's retry/batch-size controls still bound per-call load.
- New config: `evaluation/config/hrm_vllm_benchmarking.yaml`. It mirrors `evaluation/config/hrm_benchmarking.yaml` for the standard benchmark set (`GSM8k`, `MATH`, `DROP`, `GovReport`, `NordjyllandNews`, `MMLU`, `ARC`, `HellaSwag`, `Winogrande`, `BoolQ`) but uses `engine: VLLMEngine`, `prompt_mode: hrm`, and `max_model_len: 4096`.
- `scripts/schedule_checkpoint_evals.sh` now supports:

```bash
STANDARD_ENGINE_BACKEND=vllm
STANDARD_HF_EXPORT_DIR=exports/original_sapient_L_epoch4_ema_hf
STANDARD_VLLM_CONFIG=evaluation/config/hrm_vllm_benchmarking.yaml
STANDARD_VLLM_DTYPE=bfloat16
STANDARD_VLLM_GPU_MEMORY_UTILIZATION=0.85
STANDARD_VLLM_MAX_MODEL_LEN=4096
```

Default remains `STANDARD_ENGINE_BACKEND=simple`, so existing standard eval runs still use raw repo checkpoints and `SimpleEngine`. `HRM_SERVER_BACKEND=vllm` remains separate and controls only the OpenAI-compatible server path for DFM, IFEval, and EuroEval jobs.

Validation performed:

```bash
cd /work/dfm/HRM-Text
python -m py_compile evaluation/engines.py evaluation/main.py
bash -n scripts/schedule_checkpoint_evals.sh
python - <<'PY'
from omegaconf import OmegaConf
from evaluation.main import EvaluationConfig
for path in ['evaluation/config/hrm_benchmarking.yaml', 'evaluation/config/hrm_vllm_benchmarking.yaml']:
    cfg = EvaluationConfig(**OmegaConf.to_container(OmegaConf.load(path), resolve=True))
    print(path, cfg.engine, len(cfg.benchmarks), cfg.generation_config)
PY
DRY_RUN=1 LITE_EVAL=1 RUN_EUROEVAL=0 \
  STANDARD_ENGINE_BACKEND=vllm \
  STANDARD_HF_EXPORT_DIR=exports/original_sapient_L_epoch4_ema_hf \
  CKPT_PATH=checkpoints/original_sapient/L \
  CKPT_TAG=epoch_4 \
  LOG_ROOT=logs/tmp_dry_standard_vllm \
  scripts/schedule_checkpoint_evals.sh
```

Result: syntax checks passed, both standard configs parse as 10-benchmark `EvaluationConfig`s, and the scheduler dry-run queued standard/DFM/IFEval jobs without starting workers. Runtime full standard eval execution through vLLM remains intentionally untested. Confidence: high for wiring and config validation; medium for score equivalence because multi-token native-vLLM decode still diverges from `simple_inference_engine` after the first generated token.

Published config comparison on 2026-06-17:

Compared generated DFM5-L config-only export against `sapientinc/HRM-Text-1B` from Hugging Face. Matching semantic fields include `model_type`, `architectures`, `vocab_size`, `head_dim`, `H_cycles`, `L_cycles`, `L_bp_cycles`, `max_position_embeddings`, `rms_norm_eps`, `rope_theta`, `tie_word_embeddings`, `prefix_lm`, `bos_token_id`, `eos_token_id`, and, after a converter fix, `pad_token_id`.

Expected differences are model-size/init-derived: DFM5-L uses `hidden_size=1280`, `intermediate_size=3584`, `num_hidden_layers=12` per stack, `num_attention_heads=10`, and `initializer_range=1/sqrt(1280)`, while published HRM-Text-1B uses `hidden_size=1536`, `intermediate_size=4096`, `num_hidden_layers=16` per stack, `num_attention_heads=12`, and `initializer_range=1/sqrt(1536)`. The converter also emits explicit defaults (`hidden_act=silu`, `attention_bias=false`, `attention_dropout=0.0`, `mlp_bias=false`, `use_cache=true`, and `rope_parameters`) that are absent from the older published config but match current upstream HF/vLLM config expectations.

Fix applied: local tokenizer metadata did not define a pad token, so the converter originally emitted `pad_token_id=0` (`<|PAD|>`). Published HRM-Text uses `<|endoftext|>` id `5` as padding. `conversion/convert_to_hf.py` now sets `tokenizer.pad_token="<|endoftext|>"` when present before writing config/tokenizer files. Confidence: high from local config-only export and HF Hub `config.json`/tokenizer inspection.

## vLLM and Current DFM5-L Eval Throughput
Added on 2026-06-17.

Superseded in part on 2026-06-18: current DFM5-L evaluation scripts originally did not serve the HRM checkpoint through vLLM:

- Standard evals use `evaluation.main` with `evaluation/config/hrm_benchmarking*.yaml`, whose engine is `SimpleEngine`, unless `STANDARD_ENGINE_BACKEND=vllm` is set and an HF export path is supplied.
- `SimpleEngine` calls `simple_inference_engine.inference_generate`.
- DFM evals and EuroEval launch `scripts/hrm_openai_server.py`, which also uses the local simple inference engine path.
- `evaluation/engines.py` imports vLLM at module import time because it also defines `VLLMEngine`, but the HRM benchmarking configs do not instantiate `VLLMEngine`.

Updated implication: updating vLLM alone still does not speed up default `SimpleEngine` runs. It becomes relevant only for runs that explicitly use an exported HF/vLLM checkpoint through `STANDARD_ENGINE_BACKEND=vllm` or `HRM_SERVER_BACKEND=vllm`. Confidence: high from local script/config inspection and dry-run validation.

DFM5-L step-550000 vLLM probe on 2026-06-18:

Checkpoint export:

```text
checkpoints/dfm5/L fsdp2_step_550000
exports/dfm5_L_step550000_ema_hf
```

The export mapped 99 tensors and dropped 0. The evals were logged to the temporary W&B run `dfm5-l-step550k-vllm-probe-20260618` in project `DFM5`, not to the main DFM5-L run.

Measured comparison against the existing simple-engine 550K eval artifacts:

| Task | Engine | Score | Runtime |
|---|---:|---:|---:|
| MMLU | SimpleEngine | `acc=0.528775` | `8m46s` wall on 4 GPUs; shard generation about `5m57s-6m07s` |
| MMLU | vLLM | `acc=0.3342` | `7m18s` wall because it was run sequentially on 1 GPU; shard generation about `1m20s-1m21s` |
| PIQA-DA | SimpleEngine | `accuracy=0.574074` | `35s` wall including merge; task log `11s` |
| PIQA-DA | vLLM server with custom chat template | `accuracy=0.870370` | `47s` wall on 4 GPUs including four server startups and merge; task logs about `1s` per shard |

The one-GPU MMLU launch was a conservative but suboptimal choice while DFM5-L training was active on all GPUs. It slowed the training for longer than necessary. PIQA was then rerun as four shards on GPUs 4-7. The MMLU vLLM per-shard speed was about `43 prompts/s` versus about `9.6 prompts/s` for the simple engine, so a fair 4-GPU vLLM MMLU run would likely be around `1.5-2m` plus merge, but that parallel wall time was not directly measured. Confidence: high for measured logs; low for the 4-GPU MMLU estimate.

The PIQA vLLM server path initially failed because the vLLM OpenAI chat endpoint requires an explicit chat template with modern Transformers. Added `evaluation/chat_templates/hrm_direct_chat.jinja`, which wraps user messages in the HRM direct prompt tokens and assistant messages with `<|box_end|>`. Confidence: high from the successful PIQA rerun.

Operational conclusion: vLLM is not yet score-equivalent to the simple engine for HRM-Text eval reporting. The MMLU and PIQA score divergences are too large to treat as noise. Until prompt/decode equivalence is fixed, use vLLM only for debugging and throughput experiments, not as a replacement for the main reported evals. Next debugging steps are exact prompt/token comparisons for DFM tasks, generated-choice mismatch inspection for MMLU, and avoiding the chat endpoint where possible by feeding exact HRM tokenized prompts through a completions/direct-engine path. Confidence: high.

EMA handling equivalence note on 2026-06-18:

- `conversion/convert_to_hf.py --ckpt_use_ema true` calls the same `simple_inference_engine.inference_load_checkpoint(..., ckpt_use_ema=True, ...)` loader used by `SimpleEngine`.
- For sharded checkpoints, `inference_load_checkpoint` constructs `AdamATan2`, loads optimizer EMA state together with the model, then calls `optim.swap_ema()` before returning the model.
- For unsharded checkpoints, `load_unsharded_checkpoint(..., use_ema=True)` replaces each model tensor with the optimizer state's same-name `param_ema` tensor before loading the model.
- `SimpleEngine` defaults to `ckpt_use_ema=True`; `scripts/hrm_openai_server.py` also defaults to EMA unless `--no-ema` is passed. `scripts/schedule_checkpoint_evals.sh` passes `ckpt_use_ema=false`/`--no-ema` only when `NO_EMA=1`.
- vLLM does not apply EMA at runtime. It uses whatever weights were written into the HF export directory, so EMA/no-EMA selection is encoded by the export path.

Conclusion: EMA source-weight selection is equivalent between HF export and the simple engine when the same checkpoint tag and `ckpt_use_ema=True` are used. Remaining vLLM-vs-simple differences are therefore not explained by EMA application; they are more likely from vLLM decode/cache/prompt-serving behavior, remapped HF/vLLM execution, or endpoint formatting. Confidence: high from local code inspection.

Direct-token vLLM diagnostic on 2026-06-18:

Added an exact-token prompt mode to `evaluation.engines.VLLMEngine`:

```yaml
prompt_mode: hrm_tokens
```

In this mode, the engine formats the HRM prompt exactly as `SimpleEngine` does, tokenizes with `add_special_tokens=False`, and passes `TokensPrompt(prompt_token_ids=...)` to vLLM. This bypasses both OpenAI chat templates and vLLM's string-prompt tokenization surface. Added config `evaluation/config/hrm_vllm_tokens_benchmarking.yaml` for standard evals with this mode.

Added local diagnostic scripts:

- `scripts/eval_piqa_direct_engine.py`: runs PIQA-da directly through `SimpleEngine` or `VLLMEngine`, reusing the same prompt and scoring logic from `dfm-evals/dfm_evals/tasks/piqa.py`, without inspect/OpenAI chat serving.
- `scripts/eval_mmlu_direct_engine.py`: runs a direct MMLU prefix probe through `SimpleEngine` or `VLLMEngine` and saves generations. A 200-sample simple/vLLM comparison could not complete while DFM5-L training had only a few GiB free on the selected GPU; keep this script for a quieter window.

PIQA-da direct results for DFM5-L step 550000 EMA:

| Path | Accuracy | Prediction distribution | Timing |
|---|---:|---|---:|
| Simple direct | `0.574074` | `A=61`, `B=46`, invalid `1` | `14.41s` total; `9.67s` generation |
| vLLM direct string HRM prompt | `0.870370` | `A=107`, `B=1` | `13.02s` total; `0.78s` generation |
| vLLM direct `TokensPrompt` HRM prompt | `0.870370` | `A=107`, `B=1` | `11.04s` total; `0.73s` generation |

Conclusion for PIQA: the vLLM/simple divergence is not caused by inspect, OpenAI chat serving, the custom chat template, or vLLM string prompt tokenization. The exact-token vLLM path reproduces the same result as the chat-server vLLM path.

MMLU direct-token vLLM rerun for DFM5-L step 550000 EMA:

- Original vLLM string-prompt MMLU full result: `acc=0.3342`.
- vLLM `prompt_mode=hrm_tokens` full MMLU shard rerun: shard aggregate accuracies `0.3301`, `0.3412`, `0.3273`, `0.3382`; combined result remains `acc=0.3342`.
- SimpleEngine full MMLU result for the same checkpoint: `acc=0.528775`.

Operational notes from the rerun:

- First attempt to run four tokenized-vLLM MMLU shards on GPUs 4-7 failed on three shards because the active DFM5-L training run had already filled most memory on GPUs 4, 5, and 7.
- Rerunning the failed shards sequentially on GPU6 with `STANDARD_VLLM_GPU_MEMORY_UTILIZATION=0.05` succeeded.
- The standard shard merge helper did not produce `merged_metrics.json` for this diagnostic because its parser did not recognize the MMLU summary in these logs; the aggregate above was computed directly from the four shard summaries.

Interpretation: MMLU is a one-token generation task, so the unchanged `0.3342` result under `TokensPrompt` means the mismatch is already in vLLM's prefill/first-token logits for realistic long MMLU prompts. This rules out multi-token decode as the MMLU cause, and largely rules out prompt string tokenization. The remaining likely causes are in vLLM's native HRM execution for longer PrefixLM prompts: attention metadata/prefix handling, RoPE position handling, recurrence-step cache slot behavior during prefill, or a subtle weight-layout/runtime mismatch that is not exposed by the short one-token smoke test. Confidence: high for measured results; medium for root-cause narrowing.

Short first-token backend diagnostics on 2026-06-18:

The active DFM5-L training run occupied all GPUs, and EuroEval/simple-server jobs were on GPUs 5 and 6. The short vLLM diagnostics below were run on GPU0, which had training load but no eval server, with `gpu_memory_utilization=0.05`, exact prompt token IDs, `max_new_tokens=1`, and `enforce_eager=true`.

The initial prompt matrix using vLLM's default attention backend showed that exact-token vLLM still diverged from `SimpleEngine` on realistic MCQ prompts:

| Prompt | Prompt tokens | Simple first token | Default vLLM first token | Match |
|---|---:|---|---|---|
| `short` | `10` | `341` / `The` | `341` / `The` | yes |
| `piqa_0` | `168` | `64` / `B` | `63` / `A` | no |
| `mmlu_0_tail_block` | `57` | `66` / `D` | `65` / `C` | no |
| `mmlu_0_first_512chars` | `195` | `63` / `A` | `65` / `C` | no |
| `mmlu_0_full` | `352` | `66` / `D` | `64` / `B` | no |
| `filler_64` | `98` | `63` / `A` | `63` / `A` | yes |
| `filler_256` | `290` | `63` / `A` | `63` / `A` | yes |
| `filler_1024` | `1058` | `65` / `C` | `63` / `A` | no |
| `filler_2048` | `2082` | `65` / `C` | `63` / `A` | no |

This ruled out the OpenAI endpoint, chat templates, and string tokenization for these failures. It also showed that length can trigger divergence, but task-like MCQ prompts can diverge much earlier.

Forced-backend reruns on the two known-mismatching short prompts:

| Prompt | Backend | vLLM log backend | Simple first token | vLLM first token | Match |
|---|---|---|---|---|---|
| `mmlu_0_tail_block` | `FLASH_ATTN` | `AttentionBackendEnum.FLASH_ATTN`, FlashAttention 4 | `66` / `D` | `66` / `D` | yes |
| `mmlu_0_tail_block` | `TRITON_ATTN` | `AttentionBackendEnum.TRITON_ATTN` | `66` / `D` | `66` / `D` | yes |
| `piqa_0` | `FLASH_ATTN` | `AttentionBackendEnum.FLASH_ATTN`, FlashAttention 4 | `64` / `B` | `64` / `B` | yes |
| `piqa_0` | `TRITON_ATTN` | `AttentionBackendEnum.TRITON_ATTN` | `64` / `B` | `64` / `B` | yes |

Operational change: `evaluation/config/hrm_vllm_tokens_benchmarking.yaml` now sets `attention_backend: FLASH_ATTN`, which is passed through `VLLMEngine(**kwargs)` to vLLM. The default backend in the local B200 vLLM install had been selecting FlashInfer/TRTLLM prefill paths for HRM PrefixLM attention, and that default is now the prime suspect for the MMLU/PIQA score divergence. The next validation step is to rerun a small real MMLU/PIQA shard with `prompt_mode=hrm_tokens` and `attention_backend=FLASH_ATTN`; if scores move back toward SimpleEngine, use FA4 for HRM vLLM evals and keep FlashInfer disabled for this model until upstream fixes PrefixLM/non-causal HRM behavior. Confidence: high from local command output and successful one-token backend smoke tests.

Full local FA4 vLLM MMLU/PIQA validation on 2026-06-18:

Run directory:

```text
logs/eval/dfm5_L_step550000_vllm_fa4_local_mmlu_piqa_20260618_143153
```

Setup:

- Checkpoint export: `exports/dfm5_L_step550000_ema_hf`
- GPUs: MMLU shards on GPUs 0, 1, 2, 3; PIQA on GPU0 after MMLU completion.
- W&B disabled via `WANDB_DISABLED=true` and `WANDB_MODE=disabled`; logs show no W&B sync lines.
- All five vLLM logs confirm `AttentionBackendEnum.FLASH_ATTN`.
- Added single-task config `evaluation/config/hrm_vllm_tokens_mmlu_fa4.yaml` to avoid fragile OmegaConf list/index CLI overrides.
- Added `--attention-backend` support to `scripts/eval_piqa_direct_engine.py`.

Local MMLU aggregate from the four generation JSONL shards:

```json
{
  "n": 14042,
  "acc": 0.518106395100413,
  "stderr": 0.004216679315608595,
  "invalid": 0.00007121492664862555,
  "macro_acc": 0.5278198563753062,
  "macro_invalid": 0.00006497725795971411,
  "pred_counts": {"<invalid>": 1, "A": 3501, "B": 4233, "C": 3779, "D": 2528}
}
```

Local PIQA direct-script result:

```json
{
  "n": 108,
  "accuracy": 0.5462962962962963,
  "stderr": 0.04790583480943956,
  "invalid_rate": 0.009259259259259259,
  "pred_counts": {"<invalid>": 1, "A": 62, "B": 45},
  "target_counts": {"A": 95, "B": 13},
  "timing": {
    "load_seconds": 17.2759726960212,
    "generation_seconds": 8.476359352003783,
    "total_seconds": 25.752332048024982
  }
}
```

Interpretation: FA4-backed exact-token vLLM recovers MMLU from the bad default-vLLM result (`acc=0.3342`) to essentially the SimpleEngine range; SimpleEngine MMLU was `acc=0.528775` in the earlier 550K eval. PIQA also drops back near SimpleEngine/direct behavior (`0.5463` here versus earlier SimpleEngine direct `0.5741`) instead of the pathological default-vLLM `0.8704` / mostly-`A` result. This strongly supports keeping `attention_backend=FLASH_ATTN` for HRM vLLM evals on B200. Confidence: high from local completed runs and saved JSON metrics.

DFM5-L `step_550000` vLLM FA4 continuation on 2026-06-18:

- Active run directory: `logs/eval/dfm5_L_step550000_vllm_fa4_remaining_6gpu_20260618_144432`
- HF export: `exports/dfm5_L_step550000_ema_hf`
- GPUs: `0,1,2,3,4,7`; GPUs 5 and 6 were intentionally avoided because they were reserved for other eval servers.
- Required vLLM flags: `--enforce-eager --attention-backend FLASH_ATTN --chat-template /work/dfm/HRM-Text/evaluation/chat_templates/hrm_direct_chat.jinja`
- Scheduler environment uses `STANDARD_ENGINE_BACKEND=vllm`, `HRM_SERVER_BACKEND=vllm`, `STANDARD_VLLM_CONFIG=evaluation/config/hrm_vllm_tokens_benchmarking.yaml`, and `STANDARD_VLLM_GPU_MEMORY_UTILIZATION=0.05`.
- The earlier launch quoting bug was fixed by quoting `VLLM_EXTRA_ARGS` in `run.env`; a separate silent first attempt was not fully root-caused, so this run was kept in a foreground tool session for observability.

Completed standard-task comparisons against the non-vLLM 550K follow-up run:

| Task | Native/SimpleEngine run | vLLM FA4 run | Delta |
|---|---:|---:|---:|
| HellaSwag | `0.5202` | `0.5199` | `-0.0003` |
| BoolQ | `0.8456` | `0.8443` | `-0.0013` |

Both tasks had `invalid=0.0` in both eval paths, so these two tasks show close numerical agreement after forcing FA4. Confidence: high from local merged metrics JSON files.

Operational correction on 2026-06-18: the DFM5-L `step_550000` vLLM FA4 eval scheduler was restarted as a single detached scheduler using all GPUs `0,1,2,3,4,5,6,7` and `STANDARD_VLLM_GPU_MEMORY_UTILIZATION=0.25` / `VLLM_GPU_MEMORY_UTILIZATION=0.25`. The visible tmux pane is `hrm-0:9.1`, which runs `scripts/watch_eval_progress.py` in the foreground; the scheduler itself writes to `logs/eval/dfm5_L_step550000_vllm_fa4_remaining_6gpu_20260618_144432/scheduler_monitor_restart_all_gpus_025.log` and worker logs under `workers_monitor_restart_all_gpus_025`. During the restart, incomplete in-flight MATH shards were requeued by prepending missing non-completed shards back into `jobs.tsv`; queue backups were written as `jobs.tsv.before_restart_550k_vllm` and `jobs.tsv.before_monitor_restart_550k_vllm`. Confidence: high from local process and tmux inspection.

Superseding operational correction on 2026-06-18: the pane-9 monitor was changed to `scripts/watch_legacy_eval_progress_detailed.py`, because this run uses the legacy `scripts/schedule_checkpoint_evals.sh` queue while the richer plan monitor expects an `eval_scheduler` plan directory. After MATH remained slow with `STANDARD_BATCH_SIZE=4`, the remaining queue was restarted with `STANDARD_BATCH_SIZE_MATH=32` and `STANDARD_BATCH_SIZE=16` while keeping vLLM FA4 and `gpu_memory_utilization=0.25`. The current detached scheduler PID at restart was `2139453`, writing to `scheduler_batch32_math_standard16.log` with worker logs under `workers_batch32_math_standard16`. In-flight incomplete MATH shards were requeued before restart; `jobs.tsv.before_batch32_16_setsid_restart` is the queue backup from the successful setsid restart. Confidence: high from local status file, process args showing `generation_config.batch_size=32`, and pane-9 monitor output.

Further MATH throughput tuning on 2026-06-18: batch 32 substantially improved MATH throughput over batch 4. Measured completed MATH shard means at the time of inspection were batch 4: `8.75m` over 11 shards, batch 32: `3.24m` over 13 shards. The scheduler was then restarted with `STANDARD_BATCH_SIZE_MATH=64`, `STANDARD_BATCH_SIZE=64`, and `STANDARD_VLLM_GPU_MEMORY_UTILIZATION=0.35` / `VLLM_GPU_MEMORY_UTILIZATION=0.35`. Queue backup: `jobs.tsv.before_batch64_util035_restart`; worker logs: `workers_batch64_util035`; scheduler log: `scheduler_batch64_util035.log`; scheduler PID at launch: `2211096`. Process args confirmed `generation_config.batch_size=64` and `gpu_memory_utilization=0.35`. GPU7 failed quickly at batch 64 and again at automatic batch 32 retry for shard 36, while the other initial batch-64 MATH shards were active. Confidence: high from local status, process args, and telemetry.

DFM GovReport vLLM FA4 correction on 2026-06-18: the first `step_550000`
GovReport pass used the default `MAX_CONTEXT=4096` while the task requests up
to `512` generated tokens. Shards failed with OpenAI-compatible HTTP 400 errors
of the form "maximum context length 4096; requested 512 output tokens and
prompt contains at least 3585 input tokens".

Superseded: an attempted larger-context vLLM rerun used:

```bash
MAX_CONTEXT=8192
VLLM_GPU_MEMORY_UTILIZATION=0.25
DFM_BATCH_SIZE=16
DFM_BATCH_SIZE_GOVREPORT=16
HRM_SERVER_BACKEND=vllm
HRM_HF_EXPORT_DIR=/work/dfm/HRM-Text/exports/dfm5_L_step550000_ema_hf
VLLM_EXTRA_ARGS='--enforce-eager --attention-backend FLASH_ATTN --chat-template /work/dfm/HRM-Text/evaluation/chat_templates/hrm_direct_chat.jinja'
```

That required `VLLM_ALLOW_LONG_MAX_MODEL_LEN=1` because the HF export declares
`max_position_embeddings=4096`. Even then, some GovReport requests exceeded the
8192 budget by one token (`7681` input + `512` output = `8193`), so the
larger-context path was stopped by project decision and replaced with a 4096
context run that truncates the report input.

The superseded batch-16 8192 restart wrote scheduler logs to
`logs/eval/dfm5_L_step550000_vllm_fa4_remaining_6gpu_20260618_144432/scheduler_dfm_govreport_maxcontext8192_batch16.log`
and worker logs under
`logs/eval/dfm5_L_step550000_vllm_fa4_remaining_6gpu_20260618_144432/workers_dfm_govreport_maxcontext8192_batch16`.
All 16 GovReport shards were prepended back into `jobs.tsv` before restart;
the queue backup is
`jobs.tsv.before_govreport_maxcontext8192_batch16_20260618_164132`. A preceding
restart attempt with `DFM_BATCH_SIZE_GOVREPORT=8` was superseded because the
cleaner fix is to keep batch 16 and raise vLLM max length. A launch attempt that
used `HF_EXPORT_DIR` instead of the scheduler's required `HRM_HF_EXPORT_DIR`
failed before workers started. Confidence: high from local process args, worker
logs, and queue backups.

Current GovReport correction, 2026-06-18: `scripts/schedule_checkpoint_evals.sh`
now supports GovReport-specific overrides `GOVREPORT_MAX_REPORT_CHARS` and
`GOVREPORT_MAX_GEN_TOKS`, passed to `dfm-evals` as `-T max_report_chars=...`
and `-T max_gen_toks=...`. The active GovReport rerun returned to:

```bash
MAX_CONTEXT=4096
GOVREPORT_MAX_REPORT_CHARS=9000
DFM_BATCH_SIZE_GOVREPORT=16
VLLM_GPU_MEMORY_UTILIZATION=0.25
HRM_SERVER_BACKEND=vllm
HRM_HF_EXPORT_DIR=/work/dfm/HRM-Text/exports/dfm5_L_step550000_ema_hf
VLLM_EXTRA_ARGS='--enforce-eager --attention-backend FLASH_ATTN --chat-template /work/dfm/HRM-Text/evaluation/chat_templates/hrm_direct_chat.jinja'
```

The corrected 4096 run writes to
`logs/eval/dfm5_L_step550000_vllm_fa4_remaining_6gpu_20260618_144432/scheduler_dfm_govreport_4096_chars9000_batch16.log`
and worker logs under
`logs/eval/dfm5_L_step550000_vllm_fa4_remaining_6gpu_20260618_144432/workers_dfm_govreport_4096_chars9000_batch16`.
Queue backup:
`jobs.tsv.before_govreport_4096_chars9000_20260618_164947`. Shard 0 completed
successfully under this setting in about `1m47s`, and the first wave of shards
showed no fresh context-length errors. Confidence: high from local worker logs,
monitor output, and the successful shard-0 END record.

DFM5-L `step_550000` vLLM FA4 campaign completion status on 2026-06-18:
`logs/eval/dfm5_L_step550000_vllm_fa4_remaining_6gpu_20260618_144432/jobs.tsv`
is empty and the final monitor showed `running=0 queued=0`. All final queued DFM
tasks completed with `status_0`: `danish_citizen_tests`, `dala`, `gec_dala`,
`wmt24pp_en_da`, `multi_wiki_qa`, `generative_talemaader`, `govreport`,
`nordjyllandnews`, and `humaneval`; each has a `merged_metrics.json` under the
matching `logs/dfm_evals/...` task directory. Standard tasks completed with
merged metrics for `ARC`, `BoolQ`, `DROP`, `GSM8k`, `HellaSwag`, `MATH`,
`Winogrande`, and `NordjyllandNews`. Caveats: `standard GovReport` failed
before the DFM GovReport-specific 4096/truncation rerun, and the full vLLM FA4
`MMLU` metrics live in the separate local validation directory
`logs/eval/dfm5_L_step550000_vllm_fa4_local_mmlu_piqa_20260618_143153/mmlu/merged_metrics.json`
rather than the final remaining-queue directory. No EuroEval artifacts exist
under the `dfm5_L_step550000_vllm_fa4_remaining_6gpu_20260618_144432` EuroEval
log root. Confidence: high from local `status.tsv`, empty queue, merged metrics
files, and monitor output.

Follow-up clarification, 2026-06-18: EuroEval did not run in the `step_550000`
vLLM remaining queue because `scripts/schedule_checkpoint_evals.sh` only enqueues
EuroEval when `RUN_EUROEVAL=1`; the vLLM remaining-queue launches/resumes used
the default `RUN_EUROEVAL=0`. The failed `standard GovReport` artifact was not
part of the scheduler's normal final standard-task merge loop (`GSM8k`, `DROP`,
`MMLU`, `ARC`, `HellaSwag`, `Winogrande`, `BoolQ`, `MATH`). It was an earlier
stray standard summarization job, and its log shows offline vLLM rejected a
`13154`-token prompt under `max_model_len=4096`. The completed DFM GovReport
with `GOVREPORT_MAX_REPORT_CHARS=9000` is the usable GovReport metric from this
campaign. Confidence: high from scheduler source inspection, failed standard
GovReport log, and completed DFM GovReport shard/merge status.
