# Checkpoint/Compile Numerical Investigation

Date: 2026-09-15. Production: XXL, GAS8, BP8, FP32 parameters,
BF16 compute, outer compilation, no activation checkpointing.
Production was not changed during the side experiments. No probe used W&B.

## Findings

The evidence supports different finite-precision computations, amplified by
recurrence, rather than an incorrect checkpointed derivative. Eager BF16 is
not a numerical gold standard. This does **not** establish equal downstream
quality or exact training-trajectory parity.

Generated Inductor kernels load BF16 inputs into FP32, fuse operations such
as sigmoid and multiplication, and round when storing the result. Eager
execution rounds intermediate tensors separately. Both the forward values
and backward accumulation can therefore change. Explicit precision-cast
emulation reduced some small-case differences but was not a universal fix.

## Higher-Precision References

All entries below are gradient relative L2 errors, in percent.

| Test | Eager BF16 | Compiled BF16 |
| --- | ---: | ---: |
| SwiGLU product, two seeds, FP64 reference | 0.233-0.243 | 0.166-0.168 |
| Sigmoid gating, two seeds, FP64 reference | 0.249 | 0.163-0.165 |
| Small complete MLP, FP64 reference | 0.376-0.390 | 0.340-0.352 |
| Actual XXS HRM recurrence, BP8, FP64 reference | 1.636 | 1.537 outer / 1.529 block |
| Three trained XXL H blocks, eight repetitions, FP32 reference | 7.278 | 5.492 outer / 5.523 block |
| Three trained XXL L blocks, eight repetitions, FP32 reference | 3.410 | 3.164 outer / 3.115 block |

FP32 small-HRM error against FP64 was about 0.000085%, strongly implicating
BF16 rounding rather than an architectural discrepancy. The trained-block
tests use synthetic inputs, the actual first three blocks of each level,
and simplified repeated application, not the complete production graph.
FP64 trained-block probes exceeded their 6 GiB allocator cap; FP32 references
were used without increasing that cap. Production did not OOM.

## Controlled Differences

| Comparison | Gradient relative L2 difference |
| --- | ---: |
| Small eager versus eager checkpointing | 0% |
| Actual small HRM outer versus block checkpointing, BP8 | 0.320% |
| Small compiled model, GAS8 versus GAS2 | 0.163% |
| Two-rank FSDP, GAS8 versus GAS2, fixed outer compiler | 0.379% |
| Two-rank FSDP, outer versus block checkpointing, fixed GAS8 | 0.141% |
| Two-rank FSDP, outer GAS8 versus checkpointed block GAS2 | 0.394% |
| Full production-size matched-input comparison | 10.938% |

The full-size comparison hashes tokens, labels, positions and sequence
lengths on every rank. The candidate merges four GAS8 microbatches to create
effective GAS2. No examples or attention boundaries change. Its 50-update
candidate run was interrupted by request to resume production, so it must
not be presented as a completed 50-update validation.

Outer compilation combined with activation checkpointing separately failed
saved/recomputed tensor metadata checks in a small probe. The successful
candidate uses block compilation, not that failing combination.

## Do The Differences Matter?

Read-only CPU replay used actual 619K optimizer moments and all saved gradient
shards. The LR and AdamATan2 update formula match production. Common weight
decay is omitted because it cancels from the update difference.

| Adaptive-update comparison | Relative L2 difference |
| --- | ---: |
| Repeated production baseline | 0.400% |
| Production GAS8 versus checkpointed block GAS2 | 4.507% |
| H module | 4.556% |
| L module | 16.058% |
| Embeddings | 7.926% |
| Head | 0.597% |

The combined update cosine is 0.998984: directions are close, but the
difference is about eleven times the repeat baseline and is not negligible
for individual modules. This is numerical significance, not evidence of a
statistically significant quality regression. No validation-set or sustained
training A/B result was collected in this side campaign.

Recommendation: retain GAS8 production for now. A later candidate trial
should start both arms from the same checkpoint, use identical packed data,
compare optimizer updates and held-out loss, and include a repeat baseline.
Do not reject a candidate solely because it fails an arbitrary eager-gradient
percentage threshold, or approve it solely because aggregate cosine is high.

## Artifacts

These are historical, checkpoint-specific investigation tools, not a generic
production launcher. Several depend on existing files under `logs/` and
hard-coded 603500/619000 checkpoints and environment paths. In particular,
`watch_checkpoint_compile_xxl_619000.py` can stop its recorded production
process. Do not rerun it against an active campaign without reviewing its
checkpoint, PID identity, plan, and stop behavior. Nothing imports these
launchers into the normal training path.

- `logs/experiments/small_compile_matrix_619k/`: operator, HRM, accumulation,
  two-rank FSDP, and trained-block JSON results, tensor snapshots, and logs.
- `logs/experiments/checkpoint_compile_xxl_619000/matched_adam_update_difference.json`
- `logs/experiments/checkpoint_compile_xxl_619000/repeat_adam_update_difference.json`
- Scripts: `probe_small_compile_matrix.py`,
  `probe_compile_precision_reference.py`, `probe_saved_update_difference.py`.

All GPU probe processes exited. Most allocated less than 0.5 GiB; successful
trained-block probes allocated under 3.5 GiB. CUDA context overhead is extra.
