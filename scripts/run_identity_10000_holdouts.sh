#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PATH="/home/ucloud/miniforge3/envs/hrm/bin:$PATH"
export CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
export WANDB_MODE=disabled WANDB_DISABLED=true
root=data/dfm12/identity-evaluation-10000-20260927
common=(--latest-only --heldout-only
  --checkpoint checkpoints/dfm12/XL-identity-expanded-from-step2881261
  --tag step_2887261
  --heldout-root data/dfm12/identity-corrected-da-en-20260926-v4
  --heldout-manifest-sha256 b750f605d951fc22740d483fe4e913265427b3b711af44fbfc35490c2d3d476b
  --heldout-spec metadata/identity_correction.yaml
  --gpus 0,1,2,3,4,5,6,7 --max-seconds 1800)
for mode in ema nonema; do
  if [[ -e "$root/$mode" ]]; then
    echo "Refusing to overwrite $root/$mode" >&2
    exit 1
  fi
done
mkdir -p "$root"
echo "Starting EMA identity holdouts: $(date -Is)"
python -u scripts/evaluate_dfm12_identity_continuation_v4.py \
  "${common[@]}" --ema --output "$root/ema"
echo "Starting non-EMA identity holdouts: $(date -Is)"
python -u scripts/evaluate_dfm12_identity_continuation_v4.py \
  "${common[@]}" --output "$root/nonema"
echo "Both identity holdout evaluations completed: $(date -Is)"
