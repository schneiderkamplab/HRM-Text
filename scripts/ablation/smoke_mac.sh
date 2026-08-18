#!/usr/bin/env bash
# Mac (M4 Pro / MPS) smoke test. Validates that every config in the grid resolves,
# builds, and takes finite-loss steps -- before burning B200 time on a typo.
#
# NOT for producing numbers. MPS runs the custom Metal PrefixLM kernels in float32
# only, torch.compile is off, and the batch shape is nothing like the real runs.
#
#   bash scripts/ablation/smoke_mac.sh
set -euo pipefail
cd "$(dirname "$0")/../.."

TINY=data/tiny_smoke
STEPS=20

if [ ! -d "$TINY" ]; then
  echo "== building tiny synthetic dataset =="
  python scripts/create_tiny_sampled_dataset.py "$TINY" \
    --rows 2048 --epochs 1 --vocab-size 4096 --inst-len 64 --resp-len 192
fi

COMMON=(
  "arch/size@arch=XXS"
  "data=tiny_smoke"
  "global_batch_size=2048"
  "gradient_accumulation_steps=1"
  "epochs=1"
  "training_total_steps=${STEPS}"
  "max_steps=${STEPS}"
  "lr_warmup_steps=5"
  "lr_min_ratio=0.1"
  "lr=1e-3"
  "validation_interval=10"
  "validation_batches=2"
  "accelerator_type=mps"        # cpu also works, just slower
  "distributed_strategy=none"   # no torchrun, no process group
  "fwd_bwd_dtype=float32"       # the Metal PrefixLM kernels are fp32-only
  "compile_train_batch=false"
  "checkpoint_format=unsharded"
  "log_interval=1"
)

run () {
  local name="$1"; shift
  echo
  echo "===================== $name ====================="
  WANDB_MODE=disabled PYTORCH_ENABLE_MPS_FALLBACK=1 \
    python pretrain.py "${COMMON[@]}" "$@" "run_name=smoke-${name}" \
      "checkpoint_path=checkpoints/smoke/${name}" \
    && echo "PASS: $name" || { echo "FAIL: $name"; exit 1; }
}

# The three fixed-depth cells, at full BPTT
run h2l3-bp8  arch/net@arch=hrm arch.H_cycles=2 arch.L_cycles=3 arch.bp_max_steps=8 +arch.bp_min_steps=8
run h1l7-bp8  arch/net@arch=hrm arch.H_cycles=1 arch.L_cycles=7 arch.bp_max_steps=8 +arch.bp_min_steps=8
run h4l1-bp8  arch/net@arch=hrm arch.H_cycles=4 arch.L_cycles=1 arch.bp_max_steps=8 +arch.bp_min_steps=8
# Truncation variants
run h2l3-bp2  arch/net@arch=hrm arch.H_cycles=2 arch.L_cycles=3 arch.bp_max_steps=2 +arch.bp_min_steps=2
run h2l3-ramp arch/net@arch=hrm arch.H_cycles=2 arch.L_cycles=3 arch.bp_max_steps=5 +arch.bp_min_steps=2 arch.bp_warmup_ratio=0.2
# Controls
run tfm-L6    arch/net@arch=transformer arch.n_layers=6
run tfm-L24   arch/net@arch=transformer arch.n_layers=24
run hrm1-c8   arch/net@arch=hrm1 arch.cycles=8 arch.bp_max_steps=8 arch.bp_min_steps=8

echo
echo "All smoke configs passed. Logs above; nothing here is a result."
