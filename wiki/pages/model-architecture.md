# Model Architecture

Last updated: 2026-06-18  
Confidence: high  
Scope: Current recurrent HRM/CRM architecture variants in this checkout.

## Current Two-Level Relation

## vLLM DFM Judge-Backed Eval Memory

2026-06-18 operational note, Confidence: high:

For `generative_talemaader` under `scripts/schedule_checkpoint_evals.sh`, the DFM runner starts a Gemma judge on the same GPU as the target model unless `JUDGE_GPU` is overridden:

```bash
CUDA_VISIBLE_DEVICES="${judge_gpu}" "${PYTHON_BIN}" scripts/transformers_openai_server.py ...
start_target_server "${gpu}" ... "${effective_batch_size}" ...
```

When the DFM5-L `step_550000` vLLM FA4 eval was co-located with active 8-GPU training, `VLLM_GPU_MEMORY_UTILIZATION=0.35` failed for `generative_talemaader` before any requests were served. The judge used about 15.8 GiB per GPU, leaving only about 55-56 GiB free, while vLLM requested about 62.4 GiB at utilization 0.35:

```text
ValueError: Free memory on device cuda:0 (55.04/178.34 GiB) on startup is less than desired GPU memory utilization (0.35, 62.42 GiB).
```

The scheduler then halved the task batch from 16 to 8 on retry, but batch backoff cannot fix this class of failure because it occurs during vLLM startup memory reservation. The working restart used:

```bash
VLLM_GPU_MEMORY_UTILIZATION=0.25
STANDARD_VLLM_GPU_MEMORY_UTILIZATION=0.25
DFM_BATCH_SIZE=16
DFM_BATCH_SIZE_GENERATIVE_TALEMAADER=16
CKPT_PATH=/work/dfm/HRM-Text/checkpoints/dfm5/L
CKPT_TAG=step_550000
```

With utilization 0.25, shard 0 reached `/health`, used FlashAttention 4, and reported about 42 GiB available KV cache. GPU memory remained tight because each judged shard colocates training, the judge server, and target vLLM on one GPU.

2026-06-18 native-vs-vLLM `step_550000` comparison, Confidence: high for
local merged metrics:

The fixed vLLM FA4 path aligns closely with the native/simple HRM eval path on
standard benchmarks. Relevant local roots:

- Native: `logs/eval/dfm5_L_step550000_full_native_followup_20260617`
- vLLM FA4 remaining: `logs/eval/dfm5_L_step550000_vllm_fa4_remaining_6gpu_20260618_144432`
- Fixed FA4 MMLU local run: `logs/eval/dfm5_L_step550000_vllm_fa4_local_mmlu_piqa_20260618_143153`

The earlier `vllm_eval/MMLU/acc ~= 0.334` result is superseded by the fixed FA4
run; it came from the broken/non-FA4 path. The fixed MMLU result is
`macro_acc=0.52782`, matching native `eval/MMLU/acc=0.528775` within about
`0.001`.

Selected standard deltas, vLLM minus native:

| Task | Native | vLLM FA4 | Delta |
|---|---:|---:|---:|
| ARC acc | 0.6928 | 0.6903 | -0.0025 |
| BoolQ acc | 0.8456 | 0.8443 | -0.0013 |
| DROP F1 | 0.7716 | 0.7724 | +0.0008 |
| GSM8k acc | 0.35861 | 0.35861 | ~0 |
| HellaSwag acc | 0.5202 | 0.5199 | -0.0003 |
| MATH acc | 0.4764 | 0.4788 | +0.0024 |
| MMLU macro acc | 0.5288 | 0.5278 | -0.0010 |
| Winogrande acc | 0.6559 | 0.6519 | -0.0040 |

DFM overlap is also close for deterministic/simple tasks:
`danish_citizen_tests` `0.6330` vs `0.6404`, `dala` macro-F1 `0.4314` vs
`0.4310`, `gec_dala` exact match `0.0479` vs `0.0518`, `multi_wiki_qa` F1
`0.8507` vs `0.8491`, and `wmt24pp_en_da` chrF++ `0.5123` vs `0.5135`.
`generative_talemaader` differs more (`0.0` native vs `0.1238` vLLM FA4 with
the current judge-backed run), so treat that one as requiring separate output
inspection rather than as a pure engine-equivalence check.

The active HRM network is `models/baselines/hrm_nocarry_bp_warmup.py`.

It has two recurrent Transformer blocks:

- `L_level`: low/local recurrent block.
- `H_level`: high/global recurrent block.

Both levels operate on token-aligned hidden states with the same sequence positions and hidden width. There is no segment pooling, bottleneck, learned compression, or reduced-length workspace between levels in the current implementation.

The interaction is additive injection:

```python
return self.core(hidden_states + input_injection, **kwargs)
```

During forward:

- `z_H` starts as the token embeddings `x`.
- `z_L` starts from a learned vector buffer `zL_init`, broadcast across token positions by PyTorch broadcasting.
- Each L update receives current `z_H` as additive input.
- Each H update receives current `z_L` as additive input.
- The model returns final `z_H` to the language-model head.
- `initial_carry()` returns `None`; there is no persistent recurrent carry across training batches.

## Schedule

Default HRM config:

```yaml
half_layers: true
H_cycles: 2
L_cycles: 3
bp_warmup_ratio: 0.2
bp_max_steps: 5
```

With `half_layers: true`, the configured layer count is divided in half before constructing the H and L blocks, so a size config with `n_layers: 24` creates 12 Transformer layers in H and 12 in L.

The recurrence schedule is nested:

```text
for each of 2 H cycles:
  run 3 L cycles
  run 1 H cycle
```

So each forward pass runs 6 L block applications and 2 H block applications.

Backpropagation through recurrent applications is truncated by `bp_steps`, which warms from `bp_min_steps=2` to `bp_max_steps=5` over the first `20%` of total training steps. Allocation prioritizes H while leaving at least one L step:

```python
H_bp_steps = min(H_cycles, bp_steps - 1)
L_bp_steps = bp_steps - H_bp_steps
```

For the default `H_cycles=2`, `L_cycles=3`:

| `bp_steps` | H recurrent apps with grad | L recurrent apps with grad |
|---:|---:|---:|
| 2 | 1 | 1 |
| 3 | 2 | 1 |
| 4 | 2 | 2 |
| 5 | 2 | 3 |

All earlier recurrent applications still run, but with gradients disabled.

## Compression

There is no architectural compression between levels. Both levels use full token-sequence tensors and normal attention over the packed PrefixLM sequence. Any "hierarchy" currently comes from iterative cross-injection and truncated backpropagation scheduling, not from a shorter segment-level representation.

## One-Level Recurrent Baseline

Added on 2026-05-27:

- Model: `models/baselines/hrm1_nocarry_bp_warmup.py`
- Config: `config/arch/net/hrm1.yaml`
- Hydra override: `arch/net@arch=hrm1`

This is a separate one-level recurrent architecture, not the existing `ut_nocarry` baseline.

The model keeps one token-aligned recurrent state:

```text
z = x
for each recurrent cycle:
  z = R_level(z)
return z
```

There is no cross-level injection because there is only one level. Unlike `ut_nocarry`, this baseline does not keep injecting the original token embeddings into a learned recurrent state each pass; it initializes from the token embeddings and refines that state directly.

Default config:

```yaml
half_layers: true
cycles: 8
bp_warmup_ratio: 0.2
bp_min_steps: 1
bp_max_steps: 8
```

With `half_layers: true`, the configured layer count is divided by 2 before constructing the single recurrent block. This makes HRM1 compute-match HRM2 by recurrent application count: HRM2 runs 8 half-depth applications (`L,L,L,H,L,L,L,H`), and HRM1 runs 8 applications of one shared half-depth block. It is not parameter-matched to HRM2; it has about half the recurrent-block parameters. Backpropagation is truncated through the last `bp_steps` recurrent applications. Earlier recurrent applications still run with gradients disabled.

Verified locally:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m py_compile models/baselines/hrm1_nocarry_bp_warmup.py
```

CPU cache-path forward smoke also passed in the HRM env with a tiny config:

```text
torch.Size([2, 4, 64]) True
```

Tiny one-GPU compiled diagnostic with real sampled data:

```bash
cd /work/dfm/HRM-Text-3
CUDA_VISIBLE_DEVICES=7 PYTHONPATH=/work/dfm/HRM-Text-3 \
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
/home/ucloud/miniforge3/envs/hrm/bin/torchrun --master_port=29642 --nproc_per_node=1 \
  scripts/debug_nan_training_step.py \
  --steps 1 \
  --compiled-train-batch \
  --check-every-param \
  --override arch/net@arch=hrm1 \
  --override arch.n_layers=4 \
  --override arch.hidden_size=128 \
  --override arch.num_heads=4 \
  --override arch.expansion=2 \
  --override global_batch_size=512 \
  --override data.path=/work/dfm/HRM-Text/data/sampled_original_sapient \
  --override lr=1e-4
```

Result after adding `half_layers` and changing the default to `cycles=8`: one compiled optimizer step completed. The run reported `metric_tensors_finite=True` with range `[0.0, 3903.812744140625]` and `post_optim_params_finite=True` with range `[-0.26907622814178467, 0.26907891035079956]`. Confidence: high.

## Three-Level No-Compression Experimental Path

Added on 2026-05-24:

- Model: `models/baselines/hrm3_nocarry_bp_warmup.py`
- Config: `config/arch/net/hrm3.yaml`
- Hydra override: `arch/net@arch=hrm3`

This is a separate architecture path; the existing `hrm` model and config are unchanged.

The three levels are:

- `S_level`: token/local recurrent block.
- `M_level`: segment-reasoning-style recurrent block, but still token-aligned.
- `H_level`: global-planning-style recurrent block, but still token-aligned.

No compression is implemented. `S`, `M`, and `H` all use full sequence hidden states, the same hidden width, and additive injection through:

```python
hidden_states + input_injection
```

Injection relation after the 2026-05-27 Option D correction:

```text
S update: z_S = S_level(z_S, z_M + z_H)
M update: z_M = M_level(z_M, z_S + z_H)
H update: z_H = H_level(z_H, z_M)
```

This gives the token/local level immediate top-down global context without adding an extra M priming pass. The effective information graph is:

```text
H -> S
H -> M
M -> S
S -> M
M -> H
```

Earlier HRM3 notes are superseded where they imply that `S` only received `M`, or that `M` only received `S`. The first HRM3 draft updated `H` from `M` but did not feed `H` back down. The first 2026-05-27 correction fed `H` into `M`; Option D additionally feeds `H` into `S`. Confidence: high.

The initial states are:

- `z_H = x`
- `z_M = zM_init`
- `z_S = x + zS_init`

`z_S` starts token-aligned so the first S update has full sequence shape before M has been injected with token information.

Default schedule:

```yaml
third_layers: true
H_cycles: 2
M_cycles: 2
S_cycles: 2
bp_warmup_ratio: 0.2
bp_min_steps: 3
bp_max_steps: 7
```

With `third_layers: true`, the configured layer count is divided by 3 before constructing each level. A size config with `n_layers: 24` creates 8 Transformer layers in S, 8 in M, and 8 in H. The configured layer count must be divisible by 3; current `B`, `L`, and `XXL` sizes satisfy this, while the default `XL` and `XXL_wide` size configs do not.

The recurrence schedule is nested:

```text
for each of 2 H cycles:
  for each of 2 M cycles:
    run 2 S cycles
    run 1 M cycle
  run 1 H cycle
```

So each forward pass runs 8 S block applications, 4 M block applications, and 2 H block applications.

Backpropagation allocation extends the current two-level priority policy: prioritize H, then M, while keeping at least one S application in the graph. For default cycles:

| `bp_steps` | H apps with grad | M apps with grad | S apps with grad |
|---:|---:|---:|---:|
| 3 | 1 | 1 | 1 |
| 4 | 2 | 1 | 1 |
| 5 | 2 | 2 | 1 |
| 6 | 2 | 3 | 1 |
| 7 | 2 | 4 | 1 |

Verified locally:

```bash
python -m py_compile models/baselines/hrm3_nocarry_bp_warmup.py
```

and with the HRM env:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python - <<'PY'
from models.baselines.hrm3_nocarry_bp_warmup import ThreeLevelHierarchicalReasoningModel
cfg = dict(
    max_seq_len=16, n_layers=6, hidden_size=64, num_heads=4,
    expansion=4, norm_type='pre', norm_eps=1e-6,
    rope_theta=10000.0, pos_emb_type='rope', init_type='lecun_normal',
    third_layers=True, H_cycles=2, M_cycles=2, S_cycles=2,
    bp_warmup_ratio=0.2, bp_min_steps=3, bp_max_steps=7,
)
model = ThreeLevelHierarchicalReasoningModel(cfg)
print(len(model.H_level.core.layers), len(model.M_level.core.layers), len(model.S_level.core.layers))
for steps in range(3, 8):
    print(steps, model._allocate_bp_steps(steps))
PY
```

Output confirmed `2 2 2` layers for the tiny test config and BP allocations `(1,1,1)`, `(2,1,1)`, `(2,2,1)`, `(2,3,1)`, `(2,4,1)`.

CPU cache-path forward smoke also passed in the HRM env with a tiny config:

```text
torch.Size([2, 4, 64]) True
```

CUDA/FA4/FSDP diagnostics on 2026-05-25:

The `HRM-Text-3` checkout does not currently have local sampled data, so diagnostics used the original Sapient sample from the sibling checkout:

```text
/work/dfm/HRM-Text/data/sampled_original_sapient
```

Because the environment had another checkout on `PYTHONPATH`, diagnostics must force this checkout first:

```bash
PYTHONPATH=/work/dfm/HRM-Text-3
```

Also, default `torchrun` port `29500` was already in use, so diagnostics used explicit `--master_port` values.

Tiny one-GPU compiled check, using one Transformer layer per level and real sampled data:

```bash
cd /work/dfm/HRM-Text-3
CUDA_VISIBLE_DEVICES=7 PYTHONPATH=/work/dfm/HRM-Text-3 \
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
/home/ucloud/miniforge3/envs/hrm/bin/torchrun --master_port=29632 --nproc_per_node=1 \
  scripts/debug_nan_training_step.py \
  --steps 2 \
  --compiled-train-batch \
  --check-every-param \
  --override arch/net@arch=hrm3 \
  --override arch.n_layers=3 \
  --override arch.hidden_size=128 \
  --override arch.num_heads=4 \
  --override arch.expansion=2 \
  --override global_batch_size=512 \
  --override data.path=/work/dfm/HRM-Text/data/sampled_original_sapient \
  --override lr=1e-4
```

Result: two compiled optimizer steps completed. Step 1 and step 2 both reported `metric_tensors_finite=True` and `post_optim_params_finite=True`. Confidence: high.

Tiny one-GPU non-compiled check, same overrides:

```bash
cd /work/dfm/HRM-Text-3
CUDA_VISIBLE_DEVICES=7 PYTHONPATH=/work/dfm/HRM-Text-3 \
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
/home/ucloud/miniforge3/envs/hrm/bin/torchrun --master_port=29633 --nproc_per_node=1 \
  scripts/debug_nan_training_step.py \
  --steps 2 \
  --check-every-param \
  --override arch/net@arch=hrm3 \
  --override arch.n_layers=3 \
  --override arch.hidden_size=128 \
  --override arch.num_heads=4 \
  --override arch.expansion=2 \
  --override global_batch_size=512 \
  --override data.path=/work/dfm/HRM-Text/data/sampled_original_sapient \
  --override lr=1e-4
```

Result: two non-compiled optimizer steps completed with finite loss, finite metric tensors, finite parameters, finite gradients, and finite post-optimizer parameters. Observed losses were about `11.356` and `10.544`. Confidence: high.

Full L-size one-GPU non-compiled check, using `arch/size@arch=L` and a tiny `global_batch_size=512`:

```bash
cd /work/dfm/HRM-Text-3
CUDA_VISIBLE_DEVICES=7 PYTHONPATH=/work/dfm/HRM-Text-3 \
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
/home/ucloud/miniforge3/envs/hrm/bin/torchrun --master_port=29634 --nproc_per_node=1 \
  scripts/debug_nan_training_step.py \
  --steps 1 \
  --check-every-param \
  --override arch/net@arch=hrm3 \
  --override arch/size@arch=L \
  --override global_batch_size=512 \
  --override data.path=/work/dfm/HRM-Text/data/sampled_original_sapient \
  --override lr=1e-4
```

Result: one full L-size HRM3 step completed. The run reported finite loss (`11.638178825378418`), `metric_tensors_finite=True`, `params_finite=True`, `grads_finite=True`, and `post_optim_params_finite=True`. Confidence: high.

Superseded on 2026-05-27: these diagnostics were run before the corrected `M` injection included `z_H`. They still validate the original HRM3 scaffolding, but the corrected injection rule needs fresh CUDA finite-step diagnostics before training.

Fresh tiny compiled diagnostic after the first 2026-05-27 injection correction, before Option D:

```bash
cd /work/dfm/HRM-Text-3
CUDA_VISIBLE_DEVICES=7 PYTHONPATH=/work/dfm/HRM-Text-3 \
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
/home/ucloud/miniforge3/envs/hrm/bin/torchrun --master_port=29635 --nproc_per_node=1 \
  scripts/debug_nan_training_step.py \
  --steps 1 \
  --compiled-train-batch \
  --check-every-param \
  --override arch/net@arch=hrm3 \
  --override arch.n_layers=3 \
  --override arch.hidden_size=128 \
  --override arch.num_heads=4 \
  --override arch.expansion=2 \
  --override global_batch_size=512 \
  --override data.path=/work/dfm/HRM-Text/data/sampled_original_sapient \
  --override lr=1e-4
```

Result: one compiled optimizer step completed with the corrected `M` injection. The run reported `metric_tensors_finite=True` and `post_optim_params_finite=True`. Superseded for exact current architecture by the Option D diagnostic below. Confidence: high.

Fresh tiny compiled diagnostic after the 2026-05-27 Option D correction:

```bash
cd /work/dfm/HRM-Text-3
CUDA_VISIBLE_DEVICES=7 PYTHONPATH=/work/dfm/HRM-Text-3 \
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
/home/ucloud/miniforge3/envs/hrm/bin/torchrun --master_port=29636 --nproc_per_node=1 \
  scripts/debug_nan_training_step.py \
  --steps 1 \
  --compiled-train-batch \
  --check-every-param \
  --override arch/net@arch=hrm3 \
  --override arch.n_layers=3 \
  --override arch.hidden_size=128 \
  --override arch.num_heads=4 \
  --override arch.expansion=2 \
  --override global_batch_size=512 \
  --override data.path=/work/dfm/HRM-Text/data/sampled_original_sapient \
  --override lr=1e-4
```

Result: one compiled optimizer step completed with Option D. The run reported `metric_tensors_finite=True` with range `[0.0, 3894.86572265625]` and `post_optim_params_finite=True` with range `[-0.269079327583313, 0.26907840371131897]`. Confidence: high.

Residual risk: full production-shape HRM3 training remains untested. The checks above validate model construction, real sampled data loading, FA4 PrefixLM forward/backward, FSDP wrapping, optimizer update, and torch.compile on a tiny corrected HRM3 shape, but not multi-GPU scaling or production batch memory.

## CRM2 Latent-Compressed Experimental Path

Added on 2026-05-27:

- Model: `models/baselines/crm2_latent_nocarry_bp_warmup.py`
- Config: `config/arch/net/crm2.yaml`
- Hydra override: `arch/net@arch=crm2`

CRM2 is a separate compressed two-level model. It does not mutate the existing token-aligned HRM2 path.

State shapes:

```text
z_L: token-level packed sequence state, [T, d]
z_H: learned latent slots per sequence, [B * K, d]
```

Default config:

```yaml
half_layers: true
H_cycles: 2
L_cycles: 3
num_latents: 256
latent_cross_attn_heads: 8
bp_warmup_ratio: 0.2
bp_min_steps: 2
bp_max_steps: 5
```

Forward structure:

```text
z_L = token embeddings
z_H = learned latent slots repeated per packed sequence

for each H cycle:
  expanded_H = token queries attend to z_H
  repeat L_cycles:
    z_L = L_level(z_L + expanded_H)
  compressed_L = latent queries attend to z_L
  z_H = H_level(z_H + compressed_L)

return z_L
```

Compression and expansion use learned cross-attention:

- `compress`: latent queries attend over the token states of their own packed sequence.
- `expand`: token queries attend over the latent slots for their own packed sequence.

The latent H Transformer gets its own PrefixLM-style sequence metadata where every latent slot is treated as prefix/bidirectional within each sequence. This keeps H attention on `K` latent slots per example rather than all token positions.

Implementation note: the packed latent helper uses scalar `.item()` calls to build dense per-sequence token grids, but those calls are isolated inside `@torch.compiler.disable` helpers. The cleaned tiny compiled diagnostic no longer reported Dynamo scalar graph-break warnings from CRM2; FA4/CUTLASS still emits its usual deprecation warnings. Confidence: high.

Verified locally:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m py_compile models/baselines/crm2_latent_nocarry_bp_warmup.py
```

Tiny one-GPU compiled diagnostic with real sampled data:

```bash
cd /work/dfm/HRM-Text-3
CUDA_VISIBLE_DEVICES=7 PYTHONPATH=/work/dfm/HRM-Text-3 \
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
/home/ucloud/miniforge3/envs/hrm/bin/torchrun --master_port=29640 --nproc_per_node=1 \
  scripts/debug_nan_training_step.py \
  --steps 1 \
  --compiled-train-batch \
  --check-every-param \
  --override arch/net@arch=crm2 \
  --override arch.n_layers=4 \
  --override arch.hidden_size=128 \
  --override arch.num_heads=4 \
  --override arch.expansion=2 \
  --override arch.num_latents=8 \
  --override arch.latent_cross_attn_heads=4 \
  --override global_batch_size=512 \
  --override data.path=/work/dfm/HRM-Text/data/sampled_original_sapient \
  --override lr=1e-4
```

Result: one compiled optimizer step completed. The run reported `metric_tensors_finite=True` with range `[0.0, 3866.23974609375]` and `post_optim_params_finite=True` with range `[-0.2690795361995697, 0.26907792687416077]`. Confidence: high.

Residual risk: full production-shape CRM2 training remains untested. Inference/export handling for the latent H cache is also only scaffolded, not validated end to end.

## CRM3 Latent-Compressed Experimental Path

Implemented on 2026-05-27. Confidence: high for implementation and tiny CUDA diagnostic; medium for production training behavior.

CRM3 is a separate model, not a config variant of HRM3 or CRM2:

```text
models/baselines/crm3_latent_nocarry_bp_warmup.py
config/arch/net/crm3.yaml
```

State shapes:

```text
z_S: token-level packed sequence state, [T, d]
z_M: per-sequence mid latent slots, [B * K_M, d]
z_H: per-sequence high latent slots, [B * K_H, d]
```

Default config:

```yaml
H_cycles: 2
M_cycles: 2
S_cycles: 2
num_m_latents: 256
num_h_latents: 64
latent_cross_attn_heads: 8
bp_warmup_ratio: 0.2
bp_min_steps: 3
bp_max_steps: 7
```

No-extra-pass Option-D-style flow:

```text
z_S = token embeddings
z_M = learned M latent slots per sequence
z_H = learned H latent slots per sequence

for each H cycle:
  for each M cycle:
    expanded_M = S-token queries attend to z_M
    expanded_H_to_S = S-token queries attend to z_H
    repeat S_cycles:
      z_S = S_level(z_S + expanded_M + expanded_H_to_S)

    compressed_S = M-latent queries attend to z_S
    expanded_H_to_M = M-latent queries attend to z_H
    z_M = M_level(z_M + compressed_S + expanded_H_to_M)

  compressed_M = H-latent queries attend to z_M
  z_H = H_level(z_H + compressed_M)

return z_S
```

This preserves the current HRM3 Option D information graph while compressing the upper two levels:

```text
H -> S
H -> M
M -> S
S -> M
M -> H
```

but with:

```text
S token states
M latent slots
H fewer latent slots
```

The main design risk is expansion cost. Since `z_H` expands directly to all S tokens each M cycle, CRM3 adds a `T * K_H` cross-attention path. That may still be acceptable if `K_H` is small, but a cheaper future variant is:

```text
H expands only to M
M expands to S
```

This cheaper variant removes direct `H -> S` and relies on `H -> M -> S`, so it is less faithful to HRM3 Option D but cleaner computationally.

Verified locally:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m py_compile models/baselines/crm3_latent_nocarry_bp_warmup.py
```

Tiny one-GPU compiled diagnostic with real sampled data:

```bash
cd /work/dfm/HRM-Text-3
CUDA_VISIBLE_DEVICES=7 PYTHONPATH=/work/dfm/HRM-Text-3 \
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
/home/ucloud/miniforge3/envs/hrm/bin/torchrun --master_port=29641 --nproc_per_node=1 \
  scripts/debug_nan_training_step.py \
  --steps 1 \
  --compiled-train-batch \
  --check-every-param \
  --override arch/net@arch=crm3 \
  --override arch.n_layers=3 \
  --override arch.hidden_size=128 \
  --override arch.num_heads=4 \
  --override arch.expansion=2 \
  --override arch.num_m_latents=8 \
  --override arch.num_h_latents=4 \
  --override arch.latent_cross_attn_heads=4 \
  --override global_batch_size=512 \
  --override data.path=/work/dfm/HRM-Text/data/sampled_original_sapient \
  --override lr=1e-4
```

Result: one compiled optimizer step completed. The run reported `metric_tensors_finite=True` with range `[0.0, 3894.79248046875]` and `post_optim_params_finite=True` with range `[-0.26907771825790405, 0.2690773606300354]`. Confidence: high.

Residual risk: full production-shape CRM3 training remains untested. Inference/export handling for two compressed latent levels is scaffolded but not validated end to end.

## vLLM HRM-Text Serving Status

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

### Existing HF Conversion Script

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

### vLLM and Current DFM5-L Eval Throughput

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
