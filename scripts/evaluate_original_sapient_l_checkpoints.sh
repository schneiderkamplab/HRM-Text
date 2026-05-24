#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CKPT_PATH="${CKPT_PATH:-checkpoints/original_sapient/L}"
LOG_DIR="${LOG_DIR:-logs/eval/original_sapient_L}"
GPUS_CSV="${GPUS:-0,1,2,3}"
CONFIG="${CONFIG:-evaluation/config/hrm_benchmarking.yaml}"
EXTRA_ARGS=("$@")

IFS=',' read -r -a GPUS_ARR <<< "${GPUS_CSV}"
EPOCHS=(1 2 3 4)

if [[ "${#GPUS_ARR[@]}" -lt "${#EPOCHS[@]}" ]]; then
  echo "Need at least ${#EPOCHS[@]} GPUs in GPUS, got: ${GPUS_CSV}" >&2
  exit 2
fi

cd "${REPO_ROOT}"
mkdir -p "${LOG_DIR}"

pids=()
for i in "${!EPOCHS[@]}"; do
  epoch="${EPOCHS[$i]}"
  gpu="${GPUS_ARR[$i]}"
  log="${LOG_DIR}/epoch_${epoch}.log"

  echo "Launching epoch ${epoch} on GPU ${gpu}; log: ${log}"
  (
    set -euo pipefail
    CUDA_VISIBLE_DEVICES="${gpu}" python -m evaluation.main \
      config="${CONFIG}" \
      ckpt_path="${CKPT_PATH}" \
      ckpt_epoch="${epoch}" \
      "${EXTRA_ARGS[@]}"
  ) > "${log}" 2>&1 &
  pids+=("$!")
done

echo "Launched PIDs: ${pids[*]}"

status=0
for pid in "${pids[@]}"; do
  if ! wait "${pid}"; then
    status=1
  fi
done

exit "${status}"
