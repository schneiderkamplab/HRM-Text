#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

LOG_ROOT="${LOG_ROOT:-logs/dfm_evals/summarization_bertscore_all_checkpoints_$(date +%Y%m%dT%H%M%S)}"
GPUS_CSV="${GPUS:-0,1,2,3,4,5,6,7}"
DFM_EVALS_DIR="${DFM_EVALS_DIR:-${REPO_ROOT}/dfm-evals}"
SUITE_FILE="${SUITE_FILE:-${REPO_ROOT}/config/dfm_evals_hrm_single_tasks.yaml}"
TASKS_CSV="${TASKS:-govreport,nordjyllandnews}"
HOST="${HOST:-127.0.0.1}"
PORT_BASE="${PORT_BASE:-9700}"
MAX_CONTEXT="${MAX_CONTEXT:-4096}"
BATCH_SIZE="${BATCH_SIZE:-4}"
BATCH_TIMEOUT_MS="${BATCH_TIMEOUT_MS:-25}"
INSPECT_MAX_CONNECTIONS="${INSPECT_MAX_CONNECTIONS:-${BATCH_SIZE}}"
STARTUP_STAGGER_SECONDS="${STARTUP_STAGGER_SECONDS:-10}"
WANDB_PROJECT="${WANDB_PROJECT:-Original Plus Mixed Danish Instruction Rich L}"
WANDB_PREFIX="${WANDB_PREFIX:-dfm_eval}"

ORIGINAL_CKPT_PATH="${ORIGINAL_CKPT_PATH:-checkpoints/original_sapient/L}"
ORIGINAL_EPOCHS_CSV="${ORIGINAL_EPOCHS:-1,2,3,4}"
ORIGINAL_WANDB_RUN_ID="${ORIGINAL_WANDB_RUN_ID:-origLclean}"
ORIGINAL_WANDB_RUN_NAME="${ORIGINAL_WANDB_RUN_NAME:-original-sapient-L-clean-history}"
SKIP_ORIGINAL="${SKIP_ORIGINAL:-0}"

ORIGINAL_PLUS_MIXED_CKPT_PATH="${ORIGINAL_PLUS_MIXED_CKPT_PATH:-checkpoints/original_plus_mixed_danish_instruction_rich/L}"
ORIGINAL_PLUS_MIXED_EPOCHS_CSV="${ORIGINAL_PLUS_MIXED_EPOCHS:-1,2,3}"
ORIGINAL_PLUS_MIXED_WANDB_RUN_ID="${ORIGINAL_PLUS_MIXED_WANDB_RUN_ID:-es1od1in}"
ORIGINAL_PLUS_MIXED_WANDB_RUN_NAME="${ORIGINAL_PLUS_MIXED_WANDB_RUN_NAME:-original-plus-mixed-danish-instruction-rich-L}"
SKIP_ORIGINAL_PLUS_MIXED="${SKIP_ORIGINAL_PLUS_MIXED:-0}"

usage() {
  cat <<'USAGE'
Run GovReport/NordjyllandNews through dfm-evals for all available checkpoints.

This scheduler uses up to 8 GPUs in parallel, with one independent checkpoint
server and one dfm-evals process per GPU. It does not distribute a single eval
across GPUs. BERTScore uses xlm-roberta-large inside the same CUDA-visible GPU
as the checkpoint server.

Important env overrides:
  GPUS=0,1,2,3,4,5,6,7
  TASKS=govreport,nordjyllandnews
  LOG_ROOT=logs/dfm_evals/summarization_bertscore_all_checkpoints_<timestamp>
  BATCH_SIZE=4
  INSPECT_MAX_CONNECTIONS=4
USAGE
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

IFS=',' read -r -a GPUS_ARR <<< "${GPUS_CSV}"
IFS=',' read -r -a TASKS_ARR <<< "${TASKS_CSV}"
IFS=',' read -r -a ORIGINAL_EPOCHS_ARR <<< "${ORIGINAL_EPOCHS_CSV}"
IFS=',' read -r -a ORIGINAL_PLUS_MIXED_EPOCHS_ARR <<< "${ORIGINAL_PLUS_MIXED_EPOCHS_CSV}"

mkdir -p "${LOG_ROOT}/workers"
JOB_FILE="${LOG_ROOT}/jobs.tsv"
STATUS_FILE="${LOG_ROOT}/status.tsv"
LOCK_FILE="${LOG_ROOT}/jobs.lock"
: > "${JOB_FILE}"
: > "${STATUS_FILE}"

log_status() {
  printf "%s\t%s\n" "$(date --iso-8601=seconds)" "$*" | tee -a "${STATUS_FILE}"
}

suite_for_task() {
  case "$1" in
    govreport) echo "hrm_summarization_govreport" ;;
    nordjyllandnews) echo "hrm_summarization_nordjyllandnews" ;;
    *) echo "Unknown summarization task: $1" >&2; return 1 ;;
  esac
}

enqueue_family() {
  local family="$1" ckpt_path="$2" run_id="$3" run_name="$4"
  shift 4
  local epochs=("$@")
  local epoch task
  for epoch in "${epochs[@]}"; do
    if [[ ! -d "${ckpt_path}/fsdp2_epoch_${epoch}" ]]; then
      echo "Missing checkpoint directory: ${ckpt_path}/fsdp2_epoch_${epoch}" >&2
      exit 1
    fi
    for task in "${TASKS_ARR[@]}"; do
      printf "%s\t%s\t%s\t%s\t%s\t%s\n" \
        "${family}" "${ckpt_path}" "${epoch}" "${task}" "${run_id}" "${run_name}" \
        >> "${JOB_FILE}"
    done
  done
}

wait_for_server() {
  local url="$1"
  for _ in $(seq 1 240); do
    if python - "$url" <<'PY'
import sys
import urllib.request

try:
    with urllib.request.urlopen(sys.argv[1], timeout=2) as response:
        raise SystemExit(0 if response.status == 200 else 1)
except Exception:
    raise SystemExit(1)
PY
    then
      return 0
    fi
    sleep 2
  done
  return 1
}

run_job() {
  local gpu="$1" worker_id="$2" family="$3" ckpt_path="$4" epoch="$5" task="$6" run_id="$7" run_name="$8"
  local suite port base_url model_name run_dir inspect_dir eee_dir server_log server_pid status
  suite="$(suite_for_task "${task}")"
  port=$((PORT_BASE + worker_id * 100 + RANDOM % 80 + 1))
  base_url="http://${HOST}:${port}/v1"
  model_name="hrm-${family}-${task}-epoch-${epoch}"
  run_dir="${LOG_ROOT}/${family}/${task}/epoch_${epoch}"
  inspect_dir="${run_dir}/inspect"
  eee_dir="${run_dir}/eee"
  server_log="${run_dir}/server.log"
  mkdir -p "${inspect_dir}" "${eee_dir}"

  server_pid=""
  cleanup_server() {
    if [[ -n "${server_pid:-}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
      kill "${server_pid}" 2>/dev/null || true
      wait "${server_pid}" 2>/dev/null || true
    fi
  }
  trap cleanup_server RETURN

  CUDA_VISIBLE_DEVICES="${gpu}" python scripts/hrm_openai_server.py \
    --ckpt-path "${ckpt_path}" \
    --ckpt-epoch "${epoch}" \
    --host "${HOST}" \
    --port "${port}" \
    --model-name "${model_name}" \
    --max-context "${MAX_CONTEXT}" \
    --batch-size "${BATCH_SIZE}" \
    --batch-timeout-ms "${BATCH_TIMEOUT_MS}" \
    --condition direct \
    > "${server_log}" 2>&1 &
  server_pid="$!"
  wait_for_server "http://${HOST}:${port}/health"

  CUDA_VISIBLE_DEVICES="${gpu}" \
  OPENAI_API_KEY="${OPENAI_API_KEY:-inspectai}" \
  OPENAI_BASE_URL="${base_url}" \
  DFM_EVALS_MODEL_INFO_OVERRIDES="{\"openai/${model_name}\":{\"context_length\":${MAX_CONTEXT},\"output_tokens\":512,\"display_name\":\"${model_name}\",\"organization\":\"local\"}}" \
  uv run --project "${DFM_EVALS_DIR}" evals suite "${suite}" \
    --file "${SUITE_FILE}" \
    --target-model "openai/${model_name}" \
    --target-base-url "${base_url}" \
    --mode set \
    -- \
    --log-dir "${inspect_dir}" \
    --log-dir-allow-dirty \
    --max-connections "${INSPECT_MAX_CONNECTIONS}" \
    > "${run_dir}/dfm-evals.log" 2>&1

  uv run --project "${DFM_EVALS_DIR}" evals eee inspect \
    --log-path "${inspect_dir}" \
    --output-dir "${eee_dir}" \
    --source-organization-name "schneiderkamplab" \
    --evaluator-relationship "first_party" \
    --inference-base-url "${base_url}" \
    --inference-provider-name "hrm-openai-shim" \
    > "${run_dir}/eee-export.log" 2>&1

  python scripts/log_dfm_evals_to_wandb.py \
    --eee-dir "${eee_dir}" \
    --epoch "${epoch}" \
    --project "${WANDB_PROJECT}" \
    --run-id "${run_id}" \
    --run-name "${run_name}" \
    --prefix "${WANDB_PREFIX}" \
    > "${run_dir}/wandb.log" 2>&1
}

worker() {
  local gpu="$1" worker_id="$2" line family ckpt_path epoch task run_id run_name status
  sleep "$((worker_id * STARTUP_STAGGER_SECONDS))"
  while true; do
    line="$(
      {
        flock -x 9
        if [[ ! -s "${JOB_FILE}" ]]; then
          exit 0
        fi
        head -n 1 "${JOB_FILE}"
        tail -n +2 "${JOB_FILE}" > "${JOB_FILE}.tmp"
        mv "${JOB_FILE}.tmp" "${JOB_FILE}"
      } 9>"${LOCK_FILE}"
    )" || break
    [[ -n "${line}" ]] || break
    IFS=$'\t' read -r family ckpt_path epoch task run_id run_name <<< "${line}"
    log_status "START ${family} epoch_${epoch} ${task} gpu_${gpu}"
    status=0
    set +e
    run_job "${gpu}" "${worker_id}" "${family}" "${ckpt_path}" "${epoch}" "${task}" "${run_id}" "${run_name}" || status=$?
    set -e
    log_status "END ${family} epoch_${epoch} ${task} gpu_${gpu} status_${status}"
  done
}

if [[ "${SKIP_ORIGINAL}" != "1" ]]; then
  enqueue_family \
    "original_sapient" \
    "${ORIGINAL_CKPT_PATH}" \
    "${ORIGINAL_WANDB_RUN_ID}" \
    "${ORIGINAL_WANDB_RUN_NAME}" \
    "${ORIGINAL_EPOCHS_ARR[@]}"
fi
if [[ "${SKIP_ORIGINAL_PLUS_MIXED}" != "1" ]]; then
  enqueue_family \
    "original_plus_mixed_danish_instruction_rich" \
    "${ORIGINAL_PLUS_MIXED_CKPT_PATH}" \
    "${ORIGINAL_PLUS_MIXED_WANDB_RUN_ID}" \
    "${ORIGINAL_PLUS_MIXED_WANDB_RUN_NAME}" \
    "${ORIGINAL_PLUS_MIXED_EPOCHS_ARR[@]}"
fi

total_jobs="$(wc -l < "${JOB_FILE}")"
log_status "QUEUED ${total_jobs} summarization dfm-evals job(s)"

pids=()
for i in "${!GPUS_ARR[@]}"; do
  gpu="${GPUS_ARR[$i]}"
  worker "${gpu}" "${i}" > "${LOG_ROOT}/workers/worker_${i}_gpu_${gpu}.log" 2>&1 &
  pids+=("$!")
done
printf "%s\n" "${pids[@]}" > "${LOG_ROOT}/worker_pids.txt"
log_status "LAUNCHED worker_pids ${pids[*]}"

final_status=0
for pid in "${pids[@]}"; do
  if ! wait "${pid}"; then
    final_status=1
  fi
done
log_status "DONE status_${final_status}"
exit "${final_status}"
