#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

EPOCH="${EPOCH:-1}"
CKPT_PATH="${CKPT_PATH:-checkpoints/dfm/L}"
CKPT_TAG="${CKPT_TAG:-epoch_${EPOCH}}"
CKPT_TAG="${CKPT_TAG#fsdp2_}"
CKPT_TAG="${CKPT_TAG#unsharded_}"
CKPT_TAG="${CKPT_TAG%.pt}"
CKPT_TAG="${CKPT_TAG#carry_}"
EVAL_EPOCH="${EVAL_EPOCH:-${EPOCH}}"
GPUS_CSV="${GPUS:-0,1,2,3,4,5,6,7}"
LOG_ROOT="${LOG_ROOT:-logs/eval/dfm_L_epoch${EPOCH}_queued_all}"
DFM_LOG_ROOT="${DFM_LOG_ROOT:-logs/dfm_evals/dfm_L_epoch${EPOCH}_queued_all}"
WANDB_PROJECT="${WANDB_PROJECT:-DFM L}"
WANDB_RUN_ID="${WANDB_RUN_ID:-kgnbdmwf}"
WANDB_RUN_NAME="${WANDB_RUN_NAME:-dfm-L}"
DFM_EVALS_DIR="${DFM_EVALS_DIR:-${REPO_ROOT}/dfm-evals}"
STANDARD_CONFIG="${STANDARD_CONFIG:-evaluation/config/hrm_benchmarking.yaml}"
DFM_SINGLE_TASKS_CONFIG="${DFM_SINGLE_TASKS_CONFIG:-${REPO_ROOT}/config/dfm_evals_hrm_single_tasks.yaml}"
DFM_IFEVAL_SHARDS="${DFM_IFEVAL_SHARDS:-32}"
DFM_IFEVAL_SHARDS_CONFIG="${DFM_IFEVAL_SHARDS_CONFIG:-${REPO_ROOT}/config/dfm_evals_hrm_ifeval_da_32_shards.yaml}"
MODEL_PREFIX="${MODEL_PREFIX:-hrm-dfm-L}"
HOST="${HOST:-127.0.0.1}"
PORT_BASE="${PORT_BASE:-9500}"
JUDGE_PORT="${JUDGE_PORT:-9599}"
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
MAX_RETRIES="${MAX_RETRIES:-3}"
DRY_RUN="${DRY_RUN:-0}"
QUEUE_ORDER="${QUEUE_ORDER:-default}"
RESUME_EXISTING_QUEUE="${RESUME_EXISTING_QUEUE:-0}"

usage() {
  cat <<'USAGE'
Queue standard HRM evals and dfm-evals onto a single 8-GPU worker pool.

The scheduler waits for fsdp2_${CKPT_TAG} or unsharded_${CKPT_TAG}.pt, plus
carry_${CKPT_TAG}.{0..7}.pt.
It runs at most one eval job per GPU. The generative-talemaader job starts a
Gemma judge on the same GPU. MATH and IFEval-DA are sharded and merged after all
workers finish.

Important env overrides:
  EPOCH=1
  EVAL_EPOCH=1.25 # W&B eval/epoch and dfm_eval/epoch x-axis value
  CKPT_TAG=epoch_${EPOCH} # or step_10000
  CKPT_PATH=checkpoints/dfm/L
  GPUS=0,1,2,3,4,5,6,7
  WANDB_PROJECT="DFM L"
  WANDB_RUN_ID=kgnbdmwf
  MAX_RETRIES=3 # retry failed jobs this many extra times
  QUEUE_ORDER=heavy_first # start longest shard groups first
  RESUME_EXISTING_QUEUE=1 # use existing jobs.tsv/status.tsv instead of rebuilding
  DRY_RUN=1   # write and print the queue, then exit before waiting/running
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
if [[ "${RESUME_EXISTING_QUEUE}" != "1" ]]; then
  : > "${JOB_FILE}"
  : > "${STATUS_FILE}"
else
  touch "${JOB_FILE}" "${STATUS_FILE}"
fi

log_status() {
  printf "%s\t%s\n" "$(date --iso-8601=seconds)" "$*" | tee -a "${STATUS_FILE}"
}

checkpoint_ready() {
  if [[ -d "${CKPT_PATH}/fsdp2_${CKPT_TAG}" ]]; then
    [[ -f "${CKPT_PATH}/fsdp2_${CKPT_TAG}/.metadata" ]] || return 1
  elif [[ -f "${CKPT_PATH}/unsharded_${CKPT_TAG}.pt" ]]; then
    true
  else
    return 1
  fi
  local rank
  for rank in 0 1 2 3 4 5 6 7; do
    [[ -f "${CKPT_PATH}/carry_${CKPT_TAG}.${rank}.pt" ]] || return 1
  done
}

wait_for_checkpoint() {
  local waited=0
  until checkpoint_ready; do
    log_status "WAIT_CHECKPOINT ${CKPT_TAG} path_${CKPT_PATH}"
    sleep "${CHECKPOINT_WAIT_SECONDS}"
    waited=$((waited + CHECKPOINT_WAIT_SECONDS))
    if [[ "${CHECKPOINT_WAIT_MAX}" != "0" && "${waited}" -ge "${CHECKPOINT_WAIT_MAX}" ]]; then
      log_status "CHECKPOINT_TIMEOUT ${CKPT_TAG} waited_${waited}"
      return 1
    fi
  done
  log_status "CHECKPOINT_READY ${CKPT_TAG} path_${CKPT_PATH}"
}

enqueue_jobs() {
  local task shard
  local standard_tasks dfm_tasks enqueue_ifeval_first
  if [[ "${QUEUE_ORDER}" == "heavy_first" ]]; then
    standard_tasks=(MATH GSM8k DROP MMLU HellaSwag ARC Winogrande BoolQ)
    dfm_tasks=(govreport wmt24pp_en_da generative_talemaader nordjyllandnews humaneval gec_dala multi_wiki_qa danish_citizen_tests dala piqa)
    enqueue_ifeval_first=1
  elif [[ "${QUEUE_ORDER}" == "default" ]]; then
    standard_tasks=(GSM8k DROP MMLU ARC HellaSwag Winogrande BoolQ MATH)
    dfm_tasks=(danish_citizen_tests dala gec_dala wmt24pp_en_da multi_wiki_qa piqa generative_talemaader govreport nordjyllandnews humaneval)
    enqueue_ifeval_first=0
  else
    echo "Unsupported QUEUE_ORDER=${QUEUE_ORDER}" >&2
    return 1
  fi

  if [[ "${enqueue_ifeval_first}" == "1" ]]; then
    for ((shard = 0; shard < DFM_IFEVAL_SHARDS; shard++)); do
      printf "dfm_ifeval\t%s\n" "${shard}" >> "${JOB_FILE}"
    done
  fi

  for task in "${standard_tasks[@]}"; do
    local shards
    shards="$(standard_shards_for_task "${task}")"
    for ((shard = 0; shard < shards; shard++)); do
      printf "standard\t%s\t%s\t%s\n" "${task}" "${shard}" "${shards}" >> "${JOB_FILE}"
    done
  done
  for task in "${dfm_tasks[@]}"; do
    local shards
    shards="$(dfm_shards_for_task "${task}")"
    for ((shard = 0; shard < shards; shard++)); do
      printf "dfm\t%s\t%s\t%s\n" "${task}" "${shard}" "${shards}" >> "${JOB_FILE}"
    done
  done

  if [[ "${enqueue_ifeval_first}" == "0" ]]; then
    for ((shard = 0; shard < DFM_IFEVAL_SHARDS; shard++)); do
      printf "dfm_ifeval\t%s\n" "${shard}" >> "${JOB_FILE}"
    done
  fi
}

standard_shards_for_task() {
  case "$1" in
    ARC|Winogrande|BoolQ) echo 1 ;;
    HellaSwag) echo 2 ;;
    DROP|MMLU) echo 4 ;;
    GSM8k) echo 8 ;;
    MATH) echo 64 ;;
    *) echo 1 ;;
  esac
}

dfm_shards_for_task() {
  case "$1" in
    danish_citizen_tests|dala|piqa) echo 1 ;;
    gec_dala|multi_wiki_qa) echo 2 ;;
    humaneval) echo 4 ;;
    wmt24pp_en_da|generative_talemaader|nordjyllandnews) echo 8 ;;
    govreport) echo 16 ;;
    *) echo 1 ;;
  esac
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
    govreport) echo "hrm_summarization_govreport" ;;
    nordjyllandnews) echo "hrm_summarization_nordjyllandnews" ;;
    humaneval) echo "hrm_code_humaneval_local" ;;
    *) echo "Unknown dfm task: $1" >&2; return 1 ;;
  esac
}

ifeval_suite_for_shard() {
  local shard="$1"
  if [[ "${DFM_IFEVAL_SHARDS}" == "4" ]]; then
    echo "hrm_danish_ifeval_da_shard_${shard}_of_4"
  elif [[ "${DFM_IFEVAL_SHARDS}" == "8" ]]; then
    echo "hrm_danish_ifeval_da_shard_${shard}"
  elif [[ "${DFM_IFEVAL_SHARDS}" == "16" ]]; then
    echo "hrm_danish_ifeval_da_shard_${shard}_of_16"
  elif [[ "${DFM_IFEVAL_SHARDS}" == "32" ]]; then
    echo "hrm_danish_ifeval_da_shard_${shard}_of_32"
  else
    echo "Unsupported DFM_IFEVAL_SHARDS=${DFM_IFEVAL_SHARDS}" >&2
    return 1
  fi
}

run_standard() {
  local gpu="$1" task="$2" shard="${3:-0}" shards="${4:-1}"
  local dir="${LOG_ROOT}/standard_shards/${task}"
  mkdir -p "${dir}"
  local log="${dir}/${task}_shard_${shard}_of_${shards}.log"
  export CUDA_VISIBLE_DEVICES="${gpu}"
  export PYTHONUNBUFFERED=1
  python -u -m evaluation.main \
    config="${STANDARD_CONFIG}" \
    ckpt_path="${CKPT_PATH}" \
    ckpt_tag="${CKPT_TAG}" \
    "benchmarks=[{name: ${task}, num_shards: ${shards}, shard_index: ${shard}}]" \
    generation_config.batch_size="${STANDARD_BATCH_SIZE}" \
    > "${log}" 2>&1
}

run_dfm_task() {
  local gpu="$1" task="$2" worker_id="$3" shard="${4:-0}" shards="${5:-1}"
  local suite model_name run_dir inspect_dir eee_dir server_log port base_url
  suite="$(dfm_suite_for_task "${task}")"
  port=$((PORT_BASE + worker_id * 100 + RANDOM % 80 + 1))
  base_url="http://${HOST}:${port}/v1"
  model_name="${MODEL_PREFIX}-${task}-shard-${shard}-${CKPT_TAG}"
  run_dir="${DFM_LOG_ROOT}/${task}/shard_${shard}_of_${shards}/${CKPT_TAG}"
  inspect_dir="${run_dir}/inspect"
  eee_dir="${run_dir}/eee"
  server_log="${run_dir}/server.log"
  rm -rf "${inspect_dir}" "${eee_dir}"
  mkdir -p "${inspect_dir}" "${eee_dir}"

  local judge_pid="" judge_args=()
  if [[ "${task}" == "generative_talemaader" ]]; then
    local judge_port=$((JUDGE_PORT + worker_id))
    local judge_dir="${DFM_LOG_ROOT}/judge_gemma4_e4b_gpu${gpu}"
    mkdir -p "${judge_dir}"
    CUDA_VISIBLE_DEVICES="${gpu}" python scripts/transformers_openai_server.py \
      "${JUDGE_MODEL}" \
      --served-model-name "${JUDGE_SERVED_NAME}" \
      --host "${HOST}" \
      --port "${judge_port}" \
      > "${judge_dir}/server.log" 2>&1 &
    judge_pid="$!"
    wait_for_server "http://${HOST}:${judge_port}/health"
    judge_args=(--judge-model "openai/${JUDGE_SERVED_NAME}" --judge-base-url "http://${HOST}:${judge_port}/v1")
  fi

  local server_pid=""
  cleanup_dfm() {
    local current_server_pid="${server_pid:-}"
    local current_judge_pid="${judge_pid:-}"
    if [[ -n "${current_server_pid}" ]] && kill -0 "${current_server_pid}" 2>/dev/null; then
      kill "${current_server_pid}" 2>/dev/null || true
      wait "${current_server_pid}" 2>/dev/null || true
    fi
    if [[ -n "${current_judge_pid}" ]] && kill -0 "${current_judge_pid}" 2>/dev/null; then
      kill "${current_judge_pid}" 2>/dev/null || true
      wait "${current_judge_pid}" 2>/dev/null || true
    fi
  }
  trap cleanup_dfm RETURN

  CUDA_VISIBLE_DEVICES="${gpu}" python scripts/hrm_openai_server.py \
    --ckpt-path "${CKPT_PATH}" \
    --ckpt-tag "${CKPT_TAG}" \
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
    -T "num_shards=${shards}" \
    -T "shard_index=${shard}" \
    --log-dir "${inspect_dir}" \
    --log-dir-allow-dirty \
    --max-connections "${DFM_BATCH_SIZE}" \
    > "${run_dir}/dfm-evals.log" 2>&1

  if grep -Eq "param '(num_shards|shard_index)' not used by task" "${run_dir}/dfm-evals.log"; then
    echo "Sharding parameters were ignored by ${task}; refusing to treat this as shard output." >&2
    return 3
  fi

  uv run --project "${DFM_EVALS_DIR}" evals eee inspect \
    --log-path "${inspect_dir}" \
    --output-dir "${eee_dir}" \
    --source-organization-name "schneiderkamplab" \
    --evaluator-relationship "first_party" \
    --inference-base-url "${base_url}" \
    --inference-provider-name "hrm-openai-shim" \
    > "${run_dir}/eee-export.log" 2>&1

  # Sharded dfm-evals are merged and logged once in final_merge().
}

run_dfm_ifeval() {
  local gpu="$1" shard="$2" worker_id="$3"
  local port=$((PORT_BASE + 1000 + worker_id * 100 + shard))
  local base_url="http://${HOST}:${port}/v1"
  local suite
  suite="$(ifeval_suite_for_shard "${shard}")"
  local model_name="${MODEL_PREFIX}-ifeval-da-shard-${shard}-${CKPT_TAG}"
  local run_dir="${DFM_LOG_ROOT}/ifeval_shard_${shard}/${CKPT_TAG}"
  local inspect_dir="${run_dir}/inspect"
  local eee_dir="${run_dir}/eee"
  rm -rf "${inspect_dir}" "${eee_dir}"
  mkdir -p "${inspect_dir}" "${eee_dir}"

  local server_pid=""
  cleanup_ifeval() {
    local current_server_pid="${server_pid:-}"
    if [[ -n "${current_server_pid}" ]] && kill -0 "${current_server_pid}" 2>/dev/null; then
      kill "${current_server_pid}" 2>/dev/null || true
      wait "${current_server_pid}" 2>/dev/null || true
    fi
  }
  trap cleanup_ifeval RETURN

  CUDA_VISIBLE_DEVICES="${gpu}" python scripts/hrm_openai_server.py \
    --ckpt-path "${CKPT_PATH}" \
    --ckpt-tag "${CKPT_TAG}" \
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
  local gpu="$1" worker_id="$2" line kind name shard shards status
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
    IFS=$'\t' read -r kind name shard shards <<< "${line}"
    local attempt=0
    status=1
    while (( attempt <= MAX_RETRIES )); do
      log_status "START ${kind} ${name} shard_${shard:-0}_of_${shards:-1} gpu_${gpu} attempt_$((attempt + 1))_of_$((MAX_RETRIES + 1))"
      set +e
      case "${kind}" in
        standard) run_standard "${gpu}" "${name}" "${shard:-0}" "${shards:-1}" ;;
        dfm) run_dfm_task "${gpu}" "${name}" "${worker_id}" "${shard:-0}" "${shards:-1}" ;;
        dfm_ifeval) run_dfm_ifeval "${gpu}" "${name}" "${worker_id}" ;;
        *) echo "Unknown job kind: ${kind}" >&2; status=2 ;;
      esac
      status=$?
      set -e
      if [[ "${status}" == "0" ]]; then
        break
      fi
      if (( attempt >= MAX_RETRIES )); then
        break
      fi
      log_status "RETRY ${kind} ${name} shard_${shard:-0}_of_${shards:-1} gpu_${gpu} status_${status} next_attempt_$((attempt + 2))"
      sleep "$((10 * (attempt + 1)))"
      attempt=$((attempt + 1))
    done
    log_status "END ${kind} ${name} shard_${shard:-0}_of_${shards:-1} gpu_${gpu} status_${status}"
  done
}

final_merge() {
  log_status "FINAL_MERGE_START"
  local task shards
  for task in GSM8k DROP MMLU ARC HellaSwag Winogrande BoolQ MATH; do
    shards="$(standard_shards_for_task "${task}")"
    python scripts/merge_standard_eval_shards.py \
      "${LOG_ROOT}"/standard_shards/"${task}"/"${task}"_shard_*_of_"${shards}".log \
      --benchmark "${task}" \
      --epoch "${EVAL_EPOCH}" \
      --output "${LOG_ROOT}/standard_shards/${task}/merged_metrics.json" \
      --log-wandb \
      --project "${WANDB_PROJECT}" \
      --run-id "${WANDB_RUN_ID}" \
      --run-name "${WANDB_RUN_NAME}" \
      > "${LOG_ROOT}/standard_shards/${task}/merge_and_wandb_sync.log" 2>&1 || log_status "FINAL_MERGE_STANDARD_${task}_FAILED"
  done

  local ifeval_paths=()
  local shard
  for ((shard = 0; shard < DFM_IFEVAL_SHARDS; shard++)); do
    ifeval_paths+=("${DFM_LOG_ROOT}/ifeval_shard_${shard}/${CKPT_TAG}/inspect"/*.eval)
  done
  python scripts/merge_ifeval_da_shards.py \
    "${ifeval_paths[@]}" \
    --epoch "${EVAL_EPOCH}" \
    --output "${DFM_LOG_ROOT}/merged_ifeval_da_metrics.json" \
    --log-wandb \
    --project "${WANDB_PROJECT}" \
    --run-id "${WANDB_RUN_ID}" \
    --run-name "${WANDB_RUN_NAME}" \
    > "${DFM_LOG_ROOT}/merge_ifeval_da_wandb.log" 2>&1 || log_status "FINAL_MERGE_IFEVAL_FAILED"

  for task in danish_citizen_tests dala gec_dala wmt24pp_en_da multi_wiki_qa piqa generative_talemaader govreport nordjyllandnews humaneval; do
    local shards
    shards="$(dfm_shards_for_task "${task}")"
    local paths=()
    for ((shard = 0; shard < shards; shard++)); do
      paths+=("${DFM_LOG_ROOT}/${task}/shard_${shard}_of_${shards}/${CKPT_TAG}/inspect"/*.eval)
    done
    python scripts/merge_dfm_eval_shards.py \
      "${paths[@]}" \
      --task "${task}" \
      --epoch "${EVAL_EPOCH}" \
      --output "${DFM_LOG_ROOT}/${task}/merged_metrics.json" \
      --log-wandb \
      --project "${WANDB_PROJECT}" \
      --run-id "${WANDB_RUN_ID}" \
      --run-name "${WANDB_RUN_NAME}" \
      > "${DFM_LOG_ROOT}/${task}/merge_and_wandb_sync.log" 2>&1 || log_status "FINAL_MERGE_DFM_${task}_FAILED"
  done
  log_status "FINAL_MERGE_END"
}

if [[ "${RESUME_EXISTING_QUEUE}" == "1" ]]; then
  log_status "RESUME_QUEUED $(wc -l < "${JOB_FILE}") jobs"
else
  enqueue_jobs
  log_status "QUEUED $(wc -l < "${JOB_FILE}") jobs"
fi

if [[ "${DRY_RUN}" == "1" ]]; then
  cat "${JOB_FILE}"
  exit 0
fi

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
