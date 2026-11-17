---
type: Experiment
title: Embla DFM11 architecture comparisons
description: Implementation status and agreed experiment policy for three Embla variants.
status: draft
last_updated: 2026-11-16
confidence: medium
---
# Embla DFM11 experiments

**2026-11-16 kernel update:** the queued recipes now use qualified optimized
attention, with measured3.8–5.0x optimizer-step throughput. See
[optimized kernel qualification](embla-optimized-kernels.md). This supersedes
the eager-path activation status and throughput estimates in older entries below.

The kernel follow-up is tracked in [optimized training kernels](embla-optimized-kernels.md).

## Specialized kernel gap (2026-11-16)

The pinned upstream `models/embla/upstream/modeling_embla.py` explicitly says its
released eager implementation substitutes reference operations for training-time
ReLU²/key-selection kernels, FA4 window attention, QuACK grouped GEMMs and fused
AttnRes merging. Our native implementation has bounded memory and uses
`torch._grouped_mm` for experts, but is not equivalent in kernel efficiency.
The prior compiler improvement is only an intermediate optimization.

A bounded shared-GPU probe compared existing gathered local attention with the
installed FA4 `flash_attn_func(window_size=(127,0), causal=True)` at BF16,
1024 tokens, 16 query/2 KV heads, head dimension96. Forward+backward averaged
6.635 ms versus0.422 ms (15.72x); output/Q/K/V relative L2 differences were
0.226%/0.271%/0.288%/0.278%. Peak allocated memory was134 MB. This measures a
single causal document and does not certify PrefixLM, packed boundaries, an
optimizer update or whole-model throughput. Reproducer:
`scripts/benchmark_embla_fa4_window.py`; receipt:
`logs/diagnostics/embla/fa4-window-probe.json`. The installed FA4 call returns a
tuple, handled explicitly in the probe. No queue/configuration change was made.

Kernel integration priorities:

1. FA4 window attention with equivalent packed causal and PrefixLM visibility;
   preserve symmetric local prompt visibility and causal answer visibility.
2. Fused ReLU² attention forward/backward, retaining its denominator and GQA;
   standard softmax FA4 is not a mathematically equivalent replacement.
3. Fused key selection and indexed sparse softmax/backward without materializing
   gathered K/V tiles. The installed FA4 gather interface requires `qv` and has
   different index-layout constraints; it is not a drop-in Embla GQA solution.
4. Fused residual mixing/norm and measured MoE dispatch/grouped-GEMM improvements.

Refresh the full-model profile after each replacement. Keep the reference path
as a numerical oracle, qualify both objectives and decoder loops, then repeat
full eight-rank capacity/optimizer/suspension checks before enabling new kernels.

## Optional attention compilation benchmark (2026-11-16)

Implemented `embla_compile_attention` (default false) for checkpointed local and
sparse gathered attention. It compiles only the gathered kernel with dynamic
shapes; it does not change routing, masks, precision policy, LR or batch recipe.
The queued v5 configurations remain on their qualified eager path.

On spare capacity while Transformer training continued, the full causal model
(6.26B parameters, BF16, 8192-token microbatch, no optimizer/FSDP) measured
5.946 seconds eager versus 4.405 seconds compiled after warmup: 1.35x throughput,
26% less time. Peak allocation stayed approximately 53.60 GB. First compiled
execution took 16.26 seconds including compilation. Loss was 12.752168 versus
12.752355. These are shared-GPU microbatch observations, not an eight-rank
training-step benchmark or a new epoch ETA.

The actual dynamic compiled kernel measured 1.80x faster in isolation; maximum
output/Q/K/V relative L2 difference was 0.000110 (0.011%). An earlier static
kernel probe measured 2.18x; that result does not describe the dynamic integrated
path. Sixteen attention/model/native CPU tests pass. Before activation, validate
full optimizer updates, variable packed shapes, both objectives, looped execution,
capacity and suspension with eight ranks. Further gains likely require fusing
attention selection/gathers and reducing per-document Python/kernel dispatch;
FP32-to-TF32 changes are a separate numerical experiment, not enabled here.

Reproducers: `scripts/benchmark_embla_gather_compile.py --dynamic` and
`scripts/benchmark_embla_full_compile.py` (explicit CUDA device required).
Receipts: `logs/diagnostics/embla/gather-compile-dynamic-benchmark.json`,
`full-compile-benchmark.json`, and `optional-compile-tests.txt` in that directory.
Benchmarks exited; no new persistent GPU workload or scheduler change was made.

## Final232K validation and queue status

All three variants passed full-size eight-rank capacity and real-data training
checks with the v5/GAS4 recipes. They are queued immediately after Ouro, followed
by sampled-recursion BP16. The current Transformer trainer resumed from memory
at232000. See [the complete validation report](validation-232k-20261116.md) for
failures, repairs, throughput limitations, receipts and the pending250K scheduler
reload. This supersedes the pending/unqueued statements in the historical entries
below; prior failures remain part of the record.

Agreed order immediately after Ouro: causal/all-token Embla, PrefixLM/target-only
Embla, then four-loop decoder-only PrefixLM/target-only Embla. Match training
FLOPs within 5% of Transformer48, preserving one DFM11 epoch and batch recipe.
The encoder executes once; decoder parameters execute four times with fixed
bridged KV caches, full backpropagation and final-loop loss.

Retain AdamATan2, base LR 3e-4, 5K warmup and the shared flat schedule.
No inverse-loop LR multiplier for Sandwich, Ouro or Embla. This adopts the
published architectures' loop-scaling approach, not their complete optimizer
recipes. Existing HRM lr_auto remains unchanged.

## Earlier implementation status — superseded by final232K validation

Native Embla training, decoder-only looping, packed causal/PrefixLM attention,
trainable Engram, distributed EQB, checkpoint/export and native HTTP serving are
implemented. The regression run passed 52 tests (including optimizer lifecycle
and existing FSDP topology tests); the native scheduler dispatch tests pass too.
Real small-model CUDA offload/restore preserved model, optimizer/EMA and metrics
exactly. Full-size eight-rank qualification remains outstanding: active training
occupies all eight GPUs. No Embla rows have been inserted into the live queue.

The final prepared recipes are in `logs/diagnostics/embla/candidate-configs-v4`.
The two nonlooped models share width1536/shared FFN704 (6,261,466,624 parameters).
The four-loop decoder model uses width1024/shared FFN320 (2,954,791,936 parameters).
Measured-matrix estimates over256 frozen real batches give relative training
compute1.02633 causal,0.98756 PrefixLM,1.00472 looped PrefixLM. All pass the
specified sensitivity calculation within5%; the1% scalar allowance remains an
engineering estimate, not a measured bound. Config hashes bind the ledger at
`logs/diagnostics/embla/compute-match.json`; the failed v3 ledger is preserved.

The earlier v2 inference sweep passed32K for both models: nonlooped17.74s
prefill/18.81GB peak; looped14.05s/10.19GB peak.64K and128K exceeded40s process
deadlines. At256K nonlooped hit the imposed30% allocator cap, while looped timed
out. These are constrained synthetic-weight probes, not context-quality results
or evidence that a dedicated GPU cannot support longer contexts.

Review also fixed collective failure handling: a nonfinite EQB margin on one
rank now causes all ranks to reject before entering histogram reductions,
preventing peers from hanging. The uneven two-rank regression covers this case.

## Historical initial status — superseded by the implementation above

Only initial eager numerical primitives are implemented in
`models/embla/reference.py`: packed PrefixLM/local masks, squared-ReLU attention,
and a gathered exact-quantile balancing oracle. Three CPU tests pass. These
are initial mathematical tests, not parity against released Embla weights.
Dense score matrices and gathered quantiles are unsuitable for production scale.

Outstanding: verify primitives against pinned official implementation, complete
Engram/MoE/residual/bridge model, looping, distributed balancing, bounded-memory
kernels, native training integration, export and serving, FLOP sizing, full-size
capacity checks, suspension/resume verification, scheduler insertion and HRM
long-context assessment. No Embla runs have been queued or launched.

Reference revision: sevren-ai/Embla1-bf16
347209cc1a7414f597be80ff9bab7e454d1d030a.

Reference audit: downloaded the four official source/configuration files at the
pinned revision, with SHA256 receipts in `logs/diagnostics/embla/reference`.
Corrected the initial attention oracle: upstream EPS32 is float32 machine epsilon,
not the number 32. Four CPU tests now pass, including a normalization regression.

Added eager grouped-query sparse selection and gathered softmax attention.
Selection masks forbidden keys before top-k and excludes recent keys from the
ranked pool; fully masked rows return zero. Five CPU tests pass, including
agreement with dense SDPA when every visible key is selected and finite gradients.
These primitives still require upstream parity and bounded-memory implementations.

Vendored the unmodified pinned official modeling/configuration code under
`models/embla/upstream`, including its MIT license and source SHA256 receipt.
It imports in the hrm environment. Seven CPU tests now pass: full attention
matches upstream on packed examples; sparse selected-key sets, outputs and
Q/K/V gradients match upstream. This establishes primitive parity only,
not full-model training or export parity.

Implemented TrainableEngram with a registered device-resident table parameter,
retaining upstream hashing, gate and causal convolution. Nine CPU tests pass;
new checks cover upstream lookup/read parity, nonzero finite table gradients,
state-dict restoration and packed-document hash resets. This enables ordinary
parameter checkpointing; large-table FSDP behavior remains unverified.

Full eager training model is implemented in `models/embla/model.py`, including
MoE, trainable Engram, attention residuals, KV bridges, packed PrefixLM and
four-loop decoder recurrence with fixed projected KV. Small full-model logits
match the pinned causal reference. Tests verify encoder/decoder gradients,
once-only decoder KV projection and future-answer isolation under PrefixLM.

Implemented two-pass BF16 radix histogram quantiles and an explicit per-step
router accumulator in `models/embla/balancing.py`. Local exact-quantile and
multiple-invocation accumulation tests pass. Distributed reductions and trainer
lifecycle integration remain to be verified. Forward hooks must not count
activation-checkpoint recomputation twice; integration must resolve this before
production. Eager model still materializes dense attention and is not launch-ready.

Added tiled squared-ReLU full attention with a custom recomputing backward;
it retains no quadratic score tensor. Four FP32 tests verify output and Q/K/V
backward parity for packed causal/PrefixLM masks and tile boundaries. The full
model now defaults to this path and its three model tests still pass. Local
attention masks and sparse selection remain eager/quadratic; total model memory
is therefore not yet bounded as required. GPU throughput remains unmeasured.

Removed quadratic local masks and sparse selection from the tiled model path.
Local attention uses explicit bounded windows; sparse top-k selection merges
scores over query/key tiles. Gathered attention checkpoints tiles to avoid
retaining all gathered K/V activations for backward. Twenty CPU cases pass,
including tiled/eager sparse-selection equivalence for causal and PrefixLM.
Production GPU performance, mixed precision, distributed execution and native
trainer integration remain unverified; these tests do not authorize launch.

Native adapter `models/baselines/embla.py` and architecture config now exist.
The adapter owns the embedding/output head, uses already-shifted dataset labels,
derives PrefixLM visibility from prefix lengths (not the loss mask), and excludes
trailing padding. A packed-batch loss/backward CPU test passes. An explicit
calibrated configuration is required; empty defaults fail instead of allocating
the published full-sized model. Incremental native caching deliberately raises
until serving integration is implemented. Optimizer/router lifecycle, FSDP and
activation-checkpoint integration still remain.

GPU availability check during this work: all eight devices were 97–100% busy
with approximately 96–99 GiB allocated. No device tests were launched and no
active training was displaced.

Integrated optional accumulated-step model lifecycle in pretrain.py. Embla router
statistics begin once per optimizer step, combine microbatches/loops, apply after
successful updates, and discard on skipped updates or exceptions. Compile warmup
without optimizer steps does not collect statistics. Four lifecycle tests pass.
Native metadata now slices cu_seqlens to numseqs, avoiding padded trailing zeros.
Two-process Gloo verification confirms exact global BF16 quantiles with uneven
3/34-token partitions. GPU/FSDP router integration is still unverified.

Two BF16-autocast optimizer updates and a model/optimizer checkpoint round trip
pass on CPU; restored BF16 logits are bit-identical. Explicitly disabled autocast
inside tiled attention, backward, key ranking and gathered softmax so their stated
FP32 arithmetic is preserved. Added a BF16-vs-FP32 attention regression. These
are not CUDA or distributed checkpoint/suspension verification.

Added self-contained Hugging Face export with MIT-licensed reference dependencies
and explicit loop/objective metadata. AutoModelForCausalLM remote-code reload
matches native logits within FP32 rounding tolerance for causal, PrefixLM and four-loop PrefixLM small
models. HF initialization required post_init for tied-weight metadata in the
installed Transformers version. This is a correctness serving adapter that
recomputes sequences; incremental caching and scheduler/vLLM integration remain.

Added metadata-only calibration freezing script. It replays the exact eight-rank
multipack boundaries and uses fixed-seed reservoir sampling to select 256 actual
global batches uniformly over the epoch. It reads prompt/answer length arrays,
not the token payload, records sampled rows/lengths and source metadata, and
refuses to overwrite a frozen output. Calibration replay has been started;
completion and derived FLOP dimensions remain to be checked.

Calibration freeze completed: exact epoch replay yielded 393997 global batches;
256 uniform reservoir samples are stored in
`logs/diagnostics/embla/calibration-batches.json`. No token payload was read.
Added a preliminary matrix-FLOP estimator with explicit implementation overhead,
balanced-rank approximation and gathered-slot upper bounds. Its output is marked
unqualified and must not freeze launch dimensions: scalar work, profiler checks
and exact per-rank accounting remain outstanding.

Supersedes the previous packed-row score cost estimate (2026-11-16): full
attention and key selection now execute per packed document, eliminating masked
cross-document GEMMs. A regression verifies outputs, all Q/K/V gradients and
selected key sets against whole-row execution. Full-model and export parity
still pass. Updated preliminary compute ledger is in
`logs/diagnostics/embla/preliminary-compute-packed.json`; profiler qualification
remains outstanding. Boundary discovery currently causes a host synchronization
once per forward; a compiled/device-native schedule remains an optimization task.

Checkpoint conversion now dispatches Embla to its portable export before generic
HRM weight mapping. Config-only export explicitly remains unsupported. Added
[HRM efficiency assessment](embla-hrm-efficiency.md), distinguishing exact cache
accounting from unmeasured throughput and algorithm-changing KV reuse.

Small CUDA BF16 smoke passed on physical GPU7 using existing memory headroom,
with a 2.5% per-process allocator cap; no existing jobs were stopped/suspended.
The full32-layer topology with four decoder loops completed three optimizer and
router-balancing updates. Losses5.5630→5.3196→5.0831; peak tensor allocation
98,736,640 bytes; measured update loop14.81s. Receipt:
`logs/diagnostics/embla/cuda-small-smoke.json`. This establishes small-device
execution only, not full-size capacity, distributed training or throughput.

Two-rank CUDA FSDP2 smoke passed with native packed loss, full32-layer/four-loop
small model, BF16 compute, FP32 master/reduction, AdamATan2 and EMA. Both ranks
completed two updates; globally balanced router biases were bit-identical.
Peak tensor allocation84,561,408 bytes per rank. Receipts:
`logs/diagnostics/embla/fsdp-small-rank{0,1}.json`. Used limited headroom on
physical GPUs6/7 without stopping jobs. Full-size eight-rank capacity and actual
CUDA checkpoint offload/restore remain outstanding.

HF PrefixLM generation now has a regression proving the initial prompt length
stays fixed as answer tokens are appended; two greedy tokens match explicit
full-sequence forwards. Incremental serving is still pending.

Extended the existing suspension smoke harness with an isolated --embla profile:
32-layer small model, four decoder loops, native trainer, GAS2, FSDP/AdamATan2,
matched uninterrupted/suspended six-step runs with offloads at steps2 and4.
The live smoke was launched on GPU7 in existing headroom under
`logs/diagnostics/embla/cuda-suspend`; outcome remains pending. It uses the
existing controller and only the smoke-owned process identities.

CUDA suspension smoke completed successfully: two real offload/restore cycles,
zero owned GPU memory while offloaded, and exact final model, optimizer/EMA and
per-step metric parity against uninterrupted training. Receipt:
`logs/diagnostics/embla/cuda-suspend/result.json`. This is single-rank small-model
qualification; full-size eight-rank execution remains outstanding.

Broader FSDP topology test initially failed because its SimpleNamespace fixture
omitted total_steps (and its constructed config omitted arch), now required by
the previously added cycle-contract checkpoint metadata. Updated only the fixture
and asserted cycle sampling remains off; all16 topology tests pass. No relaxation
of production checkpoint validation was introduced.

Superseded the full-sequence-only HF generation limitation: native model and HF
adapter now support unpadded incremental caches. Sliding KV retains window-1
positions; full KV is appended once per physical full layer, reused across decoder
loops; sparse selections recompute each loop. Engram keeps causal ID/convolution
history. Cached prefill and three subsequent decode steps match full recomputation
for causal, PrefixLM and four-loop PrefixLM within FP32 tolerance. HF greedy
PrefixLM generation regression also passes. Last-token-only decoder prefill,
vLLM integration and large-device serving tests remain outstanding.

Implemented last-token-only decoder prefill after encoder-derived KV is available.
The encoder still processes the complete bidirectional PrefixLM prompt. Tests
verify every decoder loop receives one query, all full KV caches match full
prefill, and the subsequent decoded token matches for all three variants. Ten
model/export CPU tests pass. HF generation requests this optimized prefill when
logits_to_keep=1. Training continues to compute all prediction positions.

Native SimpleEngine generation dispatch now supports Embla with independent
incremental caches per request, optimized prefill, stopping/context limits and
the checkpoint's existing tokenizer/template. A multi-request test proves outputs
match isolated generation. This connects the existing HRM OpenAI server to Embla;
it currently interleaves requests but executes their attention serially, so no
batched-throughput claim is made. Persistent scheduler dispatch and HTTP/device
parity still need verification before scheduling production evaluations.

Persistent evaluation pool now accepts an explicit `persistent_server_backend:
embla_native` metadata value and dispatches to the existing HRM OpenAI server.
Pool identity includes backend, native batch size, actual checkpoint path/tag
and EMA choice, preventing native/vLLM cross-reuse. Ordinary vLLM dispatch is
unchanged. Thirteen server-pool/dispatch tests pass. This reuses scheduler queues
and server lifetimes rather than creating another scheduler. Live runner has not
been restarted; new backend code must be loaded before Embla jobs are enabled.
HTTP/device integration remains to be tested.

Full CPU Embla/lifecycle suite passes36 cases. First real native HTTP smoke
failed after generation because decode_generation requires a NumPy array and
the adapter passed a list. Corrected the adapter boundary; failed evidence is
preserved under `logs/diagnostics/embla/http-smoke`. A new HTTP/native parity run
is active under `http-smoke-v2`; its outcome remains pending.

End-to-end native CUDA HTTP parity now passes. The existing HRM OpenAI server
loaded the trained small checkpoint, rendered prompts, generated three greedy
tokens for two requests and exactly matched native engine text. Receipt:
`logs/diagnostics/embla/http-smoke-v2/result.json`; prior failed run is preserved.

Added candidate-config preparation (never queue-mutating): provisional widths1536
(nonlooped pair) and1024 (four-loop), original expert/head/layout ratios, Engram
pages scaled quadratically, shared DFM11/batch/LR recipe. Configs explicitly use
eager training because current per-document scheduling is not compile-qualified.
These remain unqualified pending profiler-backed FLOP matching and full-size
capacity/throughput checks. A small executed-operation FLOP counter succeeds,
providing a basis for checking the analytical matrix ledger.

Executed actual-dimension CPU BF16 forward/backward matrix-FLOP probes at16 tokens
for both candidate widths. Looped1024:86,698,360,832 FLOPs; nonlooped1536:
93,838,540,800 FLOPs. Receipts `profile-loop16.json` and `profile-prefix16.json`
include per-module/operator counts. Constant weights make these accounting probes,
not loss-quality tests. Sequence-length extrapolation and reconciliation to the
256 frozen batches remain outstanding; no compute qualification is claimed yet.

Actual-dimension16/32-token operation counts predict128-token execution exactly
for both candidates, including attention/checkpoint recomputation. Isolated
operator measurement found18 GEMM FLOPs per full-attention head-dimension/pair
and14 for gathered attention; the preliminary full-attention16 coefficient was
an underestimate. Reconciled matrix ledger is recorded separately in
`profile-reconciled-ledger.json`. Candidate widths/FFNs remain unfrozen until the
complete256-batch comparison and refinement are settled.

Full-size qualification command is prepared in `scripts/smoke_embla_fsdp.py`:
`torchrun --standalone --nproc-per-node=8 scripts/smoke_embla_fsdp.py --config
<resolved-candidate.yaml> --output <fresh-receipt-directory>`. With --config it
requires exactly8 ranks and at least178000 MiB free per GPU, uses32768 tokens/rank
(global262144), packed4K documents, the candidate objective, BF16/FSDP2,
AdamATan2+EMA and three optimizer/EQB updates. Receipts include config hash,
per-step times, peak allocation and synchronized router checks. This is synthetic
capacity testing, distinct from frozen real-batch FLOP accounting.

Latest availability check: all eight GPUs97–100% busy and only83929–86233 MiB
free, below the full-size qualification requirement. The full-size command was
not launched; current training is untouched. CPU preparation can continue.

Full-dimension6.27B PrefixLM synthetic-weight inference passed4K context on GPU7
within existing headroom: prefill1.871s, decode0.0674s/token, peak allocated
13,342,964,224 bytes. Receipt `context-prefix4096.json`. No quality claim; training
capacity and longer-context probes remain outstanding.

Candidate Pydantic validation exposed a missing suspend_control_dir inherited
from the template. Preparation now supplies each run's own control root; new
candidate-configs-v2 files preserve the old artifacts. All three revised configs
validate, retain LR3e-4/lr_auto=false/global batch262144, and point to existing
DFM11 data. Receipt `config-validation.json`.

Prepared scheduler insertion script `scripts/schedule_dfm11_embla.py`: clones the
existing complete50K/final evaluation blocks for all three variants, orders their
full epochs after Ouro, and changes only the pending successor dependency.
Execution requires a positive qualification receipt whose config hashes match
and whose full-size8GPU/compute/serving/suspension checks pass. Dry run is active;
no database mutation has been requested.

Started serial context sweep for nonlooped/looped PrefixLM at4K,16K,32K,64K,128K,
256K using bounded30%-allocator headroom on GPU7. Each isolated child has a40s
wall deadline, with explicit timeout/OOM receipts. The sweep reports capacity
and latency only; it does not establish context quality.

Scheduler dry run passed:52896 additions, one pending successor dependency change
(`btarget-dfm11-step_150000-train`), zero preflight errors or artifact collisions.
Receipt: scheduler plan's `embla-preparation-20261116/dry-run.json`. Executed=false;
no live rows added. This dry run covers v2 candidates and must be repeated after
configuration refinement.

Context sweep so far: full-width nonlooped PrefixLM passes16K (6.78s prefill,
15.68GB peak) and32K (17.74s,18.81GB).64K and128K exceeded the40s process deadline;
these are timeouts, not OOM or evidence of incorrect outputs. Sweep continues.

Prepared v3 candidates refining looped shared-expert FFN width512→320 (routed
experts and topology unchanged) to reduce the measured compute deviation. An
actual-dimension32-token probe is running to verify the predicted matrix-cost
change. Prior configs/receipts remain preserved and are not final qualification.

Reconciled all three objectives over256 frozen batches in `compute-match.json`.
The first conservative sensitivity check did not pass causal: central ratio1.0323
but upper1.0546 when varying baseline attention recomputation12–16 and adding an
explicit1% estimated scalar allowance. This allowance is an engineering estimate,
not a proven bound. Prefix and refined loop passed that check. Preparing v4 with
shared FFN704 for both nonlooped models (previous768), preserving identical pair
dimensions; loop remains320. Fresh probes and scheduler dry run are required.

Final v4 scheduler dry run completed successfully at
`logs/scheduler/dfm11_architecture_comparison_20261110/embla-preparation-v4-20261116/dry-run.json`:
52896 additions, one pending successor change, no errors or artifact collisions.
No database writes were made. The execution path now verifies definitions and
dependency edges after committing. The native serving backend must be loaded by
the scheduler before Embla dispatch; the current running runner has not been
restarted. Full-size qualification remains blocked by occupied GPUs.

Verification after final review:52 baseline Embla/lifecycle/FSDP tests passed;
then9 affected model/distributed-balancing tests and2 scheduler dispatch tests
passed. Scheduler tests require `PYTHONPATH=$PWD/eval_scheduler:$PWD`; attempting
them with only the repository root causes collection failure (package layout).
OKF validation retains the pre-existing oversized scheduler page and14 unresolved
links; no new documentation validation failures were introduced.

Qualification receipts are now assembled by
`scripts/collect_embla_qualification.py`, rather than manually setting launch
flags. It requires all24 rank receipts (eight per candidate), exact config
hashes, full batch262144, three measured updates, the compute ledger, native HTTP
parity and suspension parity. The insertion script recomputes the evidence and
rejects a stale qualification file. Its missing-rank/config-change regression
passes. Current `qualification.json` explicitly fails only full-size capacity;
all24 full-size receipts remain absent. This is not a queued or scheduled GPU
test: it must be run when GPUs become available.

Full-size command for each of the three candidate names (with the HRM environment
on PATH): `torchrun --standalone --nproc-per-node=8 scripts/smoke_embla_fsdp.py
--config logs/diagnostics/embla/candidate-configs-v4/<candidate>.yaml --output
logs/diagnostics/embla/full-size/<candidate>`. Do not run concurrently with the
current trainer. After successful capacity tests, collect receipts, load the
native backend into the scheduler safely, and run the insertion script with
`--execute`; its transaction backs up the DB and verifies inserted definitions
and edges. The preceding historical dry runs remain valid preparation evidence,
not proof of live queue insertion.

## Full-size232K validation: failed initial recipe, revised memory path

Dedicated GPUs became available after the user-authorized232000 suspension.
All three v4/GAS1 full-size configurations failed with OOM; these failures are
preserved under `logs/diagnostics/embla/full-size` and the real-data native checks
under `logs/diagnostics/queued-validation-232k-20261116`. The earlier small passes
and compute estimates did not establish production memory fit.

Residual mixing now uses nonreentrant recomputation with source-list snapshots,
avoiding retained stacks of every previous residual source at every layer.
Looped parameter gradients match the unrecomputed reference. The output head
uses chunked softcapped CE, retaining raw BF16 logits but bounding FP32 softmax
workspace; it does not recompute vocabulary matrix projections. FP32/BF16 loss,
ignored-label and gradient comparisons pass. The matrix ledger was remeasured:
central ratios1.02652/0.98774/1.00511, still within the declared sensitivity band.

The v4/GAS1 fit claim is superseded by pending v5 validation. v5 keeps the same
model dimensions, global batch262144 and full BP, but uses GAS4 (8192 tokens per
rank per microbatch). This changes packing/microbatch layout, not the epoch's
source population or objective; runtime throughput and full-size fit must be
remeasured. No live Embla rows were admitted. New receipts will go under
`logs/diagnostics/embla/full-size-v5` and separate `*-native-v5` directories;
failed evidence is not overwritten.
