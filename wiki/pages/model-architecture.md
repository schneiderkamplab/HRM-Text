# Model Architecture

Last updated: 2026-05-27  
Confidence: high  
Scope: Current recurrent HRM/CRM architecture variants in this checkout.

## Current Two-Level Relation

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
