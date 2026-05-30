#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

EPOCH="${EPOCH:-3}"
CKPT_PATH="${CKPT_PATH:-checkpoints/original_plus_mixed_danish_instruction_rich/L}"
GPUS_CSV="${GPUS:-0,1,2,3,4,5,6,7}"
LOG_ROOT="${LOG_ROOT:-logs/eval/original_plus_mixed_danish_instruction_rich_L_epoch${EPOCH}_queued_all}"
DFM_LOG_ROOT="${DFM_LOG_ROOT:-logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch${EPOCH}_queued_all}"
WANDB_PROJECT="${WANDB_PROJECT:-Original Plus Mixed Danish Instruction Rich L}"
WANDB_RUN_ID="${WANDB_RUN_ID:-es1od1in}"
WANDB_RUN_NAME="${WANDB_RUN_NAME:-original-plus-mixed-danish-instruction-rich-L}"
DFM_EVALS_DIR="${DFM_EVALS_DIR:-${REPO_ROOT}/dfm-evals}"
STANDARD_CONFIG="${STANDARD_CONFIG:-evaluation/config/hrm_benchmarking.yaml}"
DFM_SINGLE_TASKS_CONFIG="${DFM_SINGLE_TASKS_CONFIG:-${REPO_ROOT}/config/dfm_evals_hrm_single_tasks.yaml}"
DFM_IFEVAL_SHARDS_CONFIG="${DFM_IFEVAL_SHARDS_CONFIG:-${REPO_ROOT}/config/dfm_evals_hrm_ifeval_da_4_shards.yaml}"
MODEL_PREFIX="${MODEL_PREFIX:-hrm-original-plus-mixed-L}"
HOST="${HOST:-127.0.0.1}"
PORT_BASE="${PORT_BASE:-9300}"
JUDGE_PORT="${JUDGE_PORT:-9399}"
JUDGE_MODEL="${JUDGE_MODEL:-unsloth/gemma-4-E4B-it}"
JUDGE_SERVED_NAME="${JUDGE_SERVED_NAME:-gemma-4-e4b-judge}"
MAX_CONTEXT="${MAX_CONTEXT:-4096}"
STANDARD_BATCH_SIZE="${STANDARD_BATCH_SIZE:-8}"
DFM_BATCH_SIZE="${DFM_BATCH_SIZE:-8}"
DFM_BATCH_TIMEOUT_MS="${DFM_BATCH_TIMEOUT_MS:-25}"
IFEVAL_BATCH_SIZE="${IFEVAL_BATCH_SIZE:-1}"
IFEVAL_BATCH_TIMEOUT_MS="${IFEVAL_BATCH_TIMEOUT_MS:-25}"
CHECKPOINT_WAIT_SECONDS="${CHECKPOINT_WAIT_SECONDS:-300}"
CHECKPOINT_WAIT_MAX="${CHECKPOINT_WAIT_MAX:-0}"
STARTUP_STAGGER_SECONDS="${STARTUP_STAGGER_SECONDS:-10}"

usage() {
  cat <<'USAGE'
Queue all CP3 standard HRM evals and dfm-evals onto a single 8-GPU worker pool.

The scheduler waits for fsdp2_epoch_3 and carry_epoch_3.{0..7}.pt before
workers start. It runs at most one eval job per GPU. The generative-talemaader
job starts a Gemma judge on the same GPU as that job. IFEval-DA uses 4 shards
and is merged only after all workers complete.

Important env overrides:
  EPOCH=3
  GPUS=0,1,2,3,4,5,6,7
  LOG_ROOT=logs/eval/original_plus_mixed_danish_instruction_rich_L_epoch3_queued_all
  DFM_LOG_ROOT=logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch3_queued_all
  CHECKPOINT_WAIT_MAX=0   # 0 means wait indefinitely
USAGE
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

IFS=',' read -r -a GPUS_ARR <<< "${GPUS_CSV}"
mkdir -p "${LOG_ROOT}" "${DFM_LOG_ROOT}" "${LOG_ROOT}/workers"

JOB_FILE="${LOG_ROOT}/jobs.tsv"
STATUS_FILE="${LOG_ROOT}/status.tsv"
LOCK_FILE="${LOG_ROOT}/jobs.lock"
: > "${JOB_FILE}"
: > "${STATUS_FILE}"

log_status() {
  printf "%s\t%s\n" "$(date --iso-8601=seconds)" "$*" | tee -a "${STATUS_FILE}"
}

checkpoint_ready() {
  [[ -d "${CKPT_PATH}/fsdp2_epoch_${EPOCH}" ]] || return 1
  [[ -f "${CKPT_PATH}/fsdp2_epoch_${EPOCH}/.metadata" ]] || return 1
  local rank
  for rank in 0 1 2 3 4 5 6 7; do
    [[ -f "${CKPT_PATH}/carry_epoch_${EPOCH}.${rank}.pt" ]] || return 1
  done
}

wait_for_checkpoint() {
  local waited=0
  until checkpoint_ready; do
    log_status "WAIT_CHECKPOINT epoch_${EPOCH} path_${CKPT_PATH}"
    sleep "${CHECKPOINT_WAIT_SECONDS}"
    waited=$((waited + CHECKPOINT_WAIT_SECONDS))
    if [[ "${CHECKPOINT_WAIT_MAX}" != "0" && "${waited}" -ge "${CHECKPOINT_WAIT_MAX}" ]]; then
      log_status "CHECKPOINT_TIMEOUT epoch_${EPOCH} waited_${waited}"
      return 1
    fi
  done
  log_status "CHECKPOINT_READY epoch_${EPOCH} path_${CKPT_PATH}"
}

enqueue_jobs() {
  local task
  for task in GSM8k DROP MMLU ARC HellaSwag Winogrande BoolQ; do
    printf "standard\t%s\n" "${task}" >> "${JOB_FILE}"
  done
  for shard in 0 1 2 3 4 5 6 7; do
    printf "standard_math\t%s\n" "${shard}" >> "${JOB_FILE}"
  done
  for task in danish_citizen_tests dala gec_dala wmt24pp_en_da multi_wiki_qa piqa generative_talemaader; do
    printf "dfm\t%s\n" "${task}" >> "${JOB_FILE}"
  done
  for shard in 0 1 2 3; do
    printf "dfm_ifeval\t%s\n" "${shard}" >> "${JOB_FILE}"
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

dfm_suite_for_task() {
  case "$1" in
    danish_citizen_tests) echo "hrm_danish_danish_citizen_tests" ;;
    dala) echo "hrm_danish_dala" ;;
    gec_dala) echo "hrm_danish_gec_dala" ;;
    wmt24pp_en_da) echo "hrm_danish_wmt24pp_en_da" ;;
    multi_wiki_qa) echo "hrm_danish_multi_wiki_qa" ;;
    piqa) echo "hrm_danish_piqa" ;;
    generative_talemaader) echo "hrm_danish_generative_talemaader" ;;
    humaneval) echo "hrm_code_humaneval" ;;
    *) echo "Unknown dfm task: $1" >&2; return 1 ;;
  esac
}

run_standard() {
  local gpu="$1" task="$2"
  local log="${LOG_ROOT}/standard_${task}.log"
  export CUDA_VISIBLE_DEVICES="${gpu}"
  export PYTHONUNBUFFERED=1
  python -u -m evaluation.main \
    config="${STANDARD_CONFIG}" \
    ckpt_path="${CKPT_PATH}" \
    ckpt_epoch="${EPOCH}" \
    "run_only=[${task}]" \
    generation_config.batch_size="${STANDARD_BATCH_SIZE}" \
    > "${log}" 2>&1
}

run_standard_math() {
  local gpu="$1" shard="$2"
  local dir="${LOG_ROOT}/math_shards"
  mkdir -p "${dir}"
  local log="${dir}/MATH_shard_${shard}_of_8.log"
  export CUDA_VISIBLE_DEVICES="${gpu}"
  export PYTHONUNBUFFERED=1
  python -u -m evaluation.main \
    config="${STANDARD_CONFIG}" \
    ckpt_path="${CKPT_PATH}" \
    ckpt_epoch="${EPOCH}" \
    "benchmarks=[{name: MATH, num_shards: 8, shard_index: ${shard}}]" \
    generation_config.batch_size="${STANDARD_BATCH_SIZE}" \
    > "${log}" 2>&1
}

run_dfm_task() {
  local gpu="$1" task="$2" worker_id="$3"
  local suite model_name run_dir inspect_dir eee_dir server_log port base_url
  suite="$(dfm_suite_for_task "${task}")"
  port=$((PORT_BASE + worker_id * 100 + RANDOM % 80 + 1))
  base_url="http://${HOST}:${port}/v1"
  model_name="${MODEL_PREFIX}-${task}-epoch-${EPOCH}"
  run_dir="${DFM_LOG_ROOT}/${task}/epoch_${EPOCH}"
  inspect_dir="${run_dir}/inspect"
  eee_dir="${run_dir}/eee"
  server_log="${run_dir}/server.log"
  mkdir -p "${inspect_dir}" "${eee_dir}"

  local judge_pid="" judge_args=()
  if [[ "${task}" == "generative_talemaader" ]]; then
    local judge_dir="${DFM_LOG_ROOT}/judge_gemma4_e4b_gpu${gpu}"
    mkdir -p "${judge_dir}"
    CUDA_VISIBLE_DEVICES="${gpu}" python scripts/transformers_openai_server.py \
      "${JUDGE_MODEL}" \
      --served-model-name "${JUDGE_SERVED_NAME}" \
      --host "${HOST}" \
      --port "${JUDGE_PORT}" \
      > "${judge_dir}/server.log" 2>&1 &
    judge_pid="$!"
    wait_for_server "http://${HOST}:${JUDGE_PORT}/health"
    judge_args=(--judge-model "openai/${JUDGE_SERVED_NAME}" --judge-base-url "http://${HOST}:${JUDGE_PORT}/v1")
  fi

  local server_pid=""
  cleanup_dfm() {
    if [[ -n "${server_pid}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
      kill "${server_pid}" 2>/dev/null || true
      wait "${server_pid}" 2>/dev/null || true
    fi
    if [[ -n "${judge_pid}" ]] && kill -0 "${judge_pid}" 2>/dev/null; then
      kill "${judge_pid}" 2>/dev/null || true
      wait "${judge_pid}" 2>/dev/null || true
    fi
  }
  trap cleanup_dfm RETURN

  CUDA_VISIBLE_DEVICES="${gpu}" python scripts/hrm_openai_server.py \
    --ckpt-path "${CKPT_PATH}" \
    --ckpt-epoch "${EPOCH}" \
    --host "${HOST}" \
    --port "${port}" \
    --model-name "${model_name}" \
    --max-context "${MAX_CONTEXT}" \
    --batch-size "${DFM_BATCH_SIZE}" \
    --batch-timeout-ms "${DFM_BATCH_TIMEOUT_MS}" \
    --condition direct \
    > "${server_log}" 2>&1 &
  server_pid="$!"
  wait_for_server "http://${HOST}:${port}/health"

  OPENAI_API_KEY="${OPENAI_API_KEY:-inspectai}" \
  OPENAI_BASE_URL="${base_url}" \
  DFM_EVALS_MODEL_INFO_OVERRIDES="{\"openai/${model_name}\":{\"context_length\":${MAX_CONTEXT},\"output_tokens\":512,\"display_name\":\"${model_name}\",\"organization\":\"local\"}}" \
  uv run --project "${DFM_EVALS_DIR}" evals suite "${suite}" \
    --file "${DFM_SINGLE_TASKS_CONFIG}" \
    --target-model "openai/${model_name}" \
    --target-base-url "${base_url}" \
    "${judge_args[@]}" \
    --mode set \
    -- \
    --log-dir "${inspect_dir}" \
    --log-dir-allow-dirty \
    --max-connections "${DFM_BATCH_SIZE}" \
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
    --epoch "${EPOCH}" \
    --project "${WANDB_PROJECT}" \
    --run-id "${WANDB_RUN_ID}" \
    --run-name "${WANDB_RUN_NAME}" \
    --prefix dfm_eval \
    > "${run_dir}/wandb.log" 2>&1
}

run_dfm_ifeval() {
  local gpu="$1" shard="$2" worker_id="$3"
  local port=$((PORT_BASE + 1000 + worker_id * 100 + shard))
  local base_url="http://${HOST}:${port}/v1"
  local suite="hrm_danish_ifeval_da_shard_${shard}_of_4"
  local model_name="${MODEL_PREFIX}-ifeval-da-shard-${shard}-epoch-${EPOCH}"
  local run_dir="${DFM_LOG_ROOT}/ifeval_shard_${shard}/epoch_${EPOCH}"
  local inspect_dir="${run_dir}/inspect"
  local eee_dir="${run_dir}/eee"
  mkdir -p "${inspect_dir}" "${eee_dir}"

  local server_pid=""
  cleanup_ifeval() {
    if [[ -n "${server_pid}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
      kill "${server_pid}" 2>/dev/null || true
      wait "${server_pid}" 2>/dev/null || true
    fi
  }
  trap cleanup_ifeval RETURN

  CUDA_VISIBLE_DEVICES="${gpu}" python scripts/hrm_openai_server.py \
    --ckpt-path "${CKPT_PATH}" \
    --ckpt-epoch "${EPOCH}" \
    --host "${HOST}" \
    --port "${port}" \
    --model-name "${model_name}" \
    --max-context "${MAX_CONTEXT}" \
    --batch-size "${IFEVAL_BATCH_SIZE}" \
    --batch-timeout-ms "${IFEVAL_BATCH_TIMEOUT_MS}" \
    --condition direct \
    > "${run_dir}/server.log" 2>&1 &
  server_pid="$!"
  wait_for_server "http://${HOST}:${port}/health"

  OPENAI_API_KEY="${OPENAI_API_KEY:-inspectai}" \
  OPENAI_BASE_URL="${base_url}" \
  DFM_EVALS_MODEL_INFO_OVERRIDES="{\"openai/${model_name}\":{\"context_length\":${MAX_CONTEXT},\"output_tokens\":512,\"display_name\":\"${model_name}\",\"organization\":\"local\"}}" \
  uv run --project "${DFM_EVALS_DIR}" evals suite "${suite}" \
    --file "${DFM_IFEVAL_SHARDS_CONFIG}" \
    --target-model "openai/${model_name}" \
    --target-base-url "${base_url}" \
    --mode set \
    -- \
    --log-dir "${inspect_dir}" \
    --log-dir-allow-dirty \
    --max-connections "${IFEVAL_BATCH_SIZE}" \
    > "${run_dir}/dfm-evals.log" 2>&1

  uv run --project "${DFM_EVALS_DIR}" evals eee inspect \
    --log-path "${inspect_dir}" \
    --output-dir "${eee_dir}" \
    --source-organization-name "schneiderkamplab" \
    --evaluator-relationship "first_party" \
    --inference-base-url "${base_url}" \
    --inference-provider-name "hrm-openai-shim" \
    > "${run_dir}/eee-export.log" 2>&1
}

worker() {
  local gpu="$1" worker_id="$2" line kind name status
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
    IFS=$'\t' read -r kind name <<< "${line}"
    log_status "START ${kind} ${name} gpu_${gpu}"
    status=0
    set +e
    case "${kind}" in
      standard) run_standard "${gpu}" "${name}" ;;
      standard_math) run_standard_math "${gpu}" "${name}" ;;
      dfm) run_dfm_task "${gpu}" "${name}" "${worker_id}" ;;
      dfm_ifeval) run_dfm_ifeval "${gpu}" "${name}" "${worker_id}" ;;
      *) echo "Unknown job kind: ${kind}" >&2; status=2 ;;
    esac
    status=$?
    set -e
    log_status "END ${kind} ${name} gpu_${gpu} status_${status}"
  done
}

final_merge() {
  log_status "FINAL_MERGE_START"
  python scripts/merge_standard_math_shards.py \
    "${LOG_ROOT}"/math_shards/MATH_shard_*_of_8.log \
    --epoch "${EPOCH}" \
    --output "${LOG_ROOT}/math_shards/merged_math_metrics.json" \
    --log-wandb \
    --project "${WANDB_PROJECT}" \
    --run-id "${WANDB_RUN_ID}" \
    --run-name "${WANDB_RUN_NAME}" \
    > "${LOG_ROOT}/math_shards/merge_and_wandb_sync.log" 2>&1 || log_status "FINAL_MERGE_STANDARD_MATH_FAILED"

  python scripts/merge_ifeval_da_shards.py \
    "${DFM_LOG_ROOT}"/ifeval_shard_{0,1,2,3}/epoch_"${EPOCH}"/inspect/*.eval \
    --epoch "${EPOCH}" \
    --output "${DFM_LOG_ROOT}/merged_ifeval_da_metrics.json" \
    --log-wandb \
    --project "${WANDB_PROJECT}" \
    --run-id "${WANDB_RUN_ID}" \
    --run-name "${WANDB_RUN_NAME}" \
    > "${DFM_LOG_ROOT}/merge_ifeval_da_wandb.log" 2>&1 || log_status "FINAL_MERGE_IFEVAL_FAILED"
  log_status "FINAL_MERGE_END"
}

enqueue_jobs
log_status "QUEUED $(wc -l < "${JOB_FILE}") jobs"
wait_for_checkpoint

pids=()
for i in "${!GPUS_ARR[@]}"; do
  gpu="${GPUS_ARR[$i]}"
  worker "${gpu}" "${i}" > "${LOG_ROOT}/workers/worker_${i}_gpu_${gpu}.log" 2>&1 &
  pids+=("$!")
done
log_status "WORKERS ${pids[*]}"

final_status=0
for pid in "${pids[@]}"; do
  if ! wait "${pid}"; then
    final_status=1
  fi
done

final_merge
exit "${final_status}"
