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
EUROEVAL_LOG_ROOT="${EUROEVAL_LOG_ROOT:-logs/euroeval/dfm_L_epoch${EPOCH}_queued_all}"
WANDB_PROJECT="${WANDB_PROJECT:-DFM L}"
WANDB_RUN_ID="${WANDB_RUN_ID:-kgnbdmwf}"
WANDB_RUN_NAME="${WANDB_RUN_NAME:-dfm-L}"
WANDB_SYNC="${WANDB_SYNC:-1}"
DFM_EVALS_DIR="${DFM_EVALS_DIR:-${REPO_ROOT}/dfm-evals}"
PYTHON_BIN="${PYTHON_BIN:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python"
fi
STANDARD_CONFIG="${STANDARD_CONFIG:-evaluation/config/hrm_benchmarking.yaml}"
DFM_SINGLE_TASKS_CONFIG="${DFM_SINGLE_TASKS_CONFIG:-${REPO_ROOT}/config/dfm_evals_hrm_single_tasks.yaml}"
DFM_IFEVAL_SHARDS="${DFM_IFEVAL_SHARDS:-32}"
DFM_IFEVAL_SHARDS_CONFIG="${DFM_IFEVAL_SHARDS_CONFIG:-${REPO_ROOT}/config/dfm_evals_hrm_ifeval_da_32_shards.yaml}"
MODEL_PREFIX="${MODEL_PREFIX:-hrm-dfm-L}"
HOST="${HOST:-127.0.0.1}"
PORT_BASE="${PORT_BASE:-9500}"
JUDGE_PORT="${JUDGE_PORT:-9599}"
JUDGE_GPU="${JUDGE_GPU:-}"
JUDGE_MODEL="${JUDGE_MODEL:-unsloth/gemma-4-E4B-it}"
JUDGE_SERVED_NAME="${JUDGE_SERVED_NAME:-gemma-4-e4b-judge}"
MAX_CONTEXT="${MAX_CONTEXT:-4096}"
STANDARD_BATCH_SIZE="${STANDARD_BATCH_SIZE:-8}"
DFM_BATCH_SIZE="${DFM_BATCH_SIZE:-8}"
DFM_BATCH_TIMEOUT_MS="${DFM_BATCH_TIMEOUT_MS:-25}"
IFEVAL_BATCH_SIZE="${IFEVAL_BATCH_SIZE:-16}"
IFEVAL_BATCH_TIMEOUT_MS="${IFEVAL_BATCH_TIMEOUT_MS:-25}"
RUN_EUROEVAL="${RUN_EUROEVAL:-0}"
EUROEVAL_BATCH_SIZE="${EUROEVAL_BATCH_SIZE:-4}"
EUROEVAL_BATCH_TIMEOUT_MS="${EUROEVAL_BATCH_TIMEOUT_MS:-25}"
EUROEVAL_LANGUAGES="${EUROEVAL_LANGUAGES:-da,en}"
EUROEVAL_DATASETS="${EUROEVAL_DATASETS:-}"
EUROEVAL_DATASET_GROUPS="${EUROEVAL_DATASET_GROUPS:-}"
EUROEVAL_TASKS="${EUROEVAL_TASKS:-}"
EUROEVAL_FEW_SHOT="${EUROEVAL_FEW_SHOT:-}"
EUROEVAL_NUM_ITERATIONS="${EUROEVAL_NUM_ITERATIONS:-}"
EUROEVAL_GENERATIVE_TYPE="${EUROEVAL_GENERATIVE_TYPE:-}"
EUROEVAL_BIN="${EUROEVAL_BIN:-euroeval}"
EUROEVAL_PREFIX="${EUROEVAL_PREFIX:-euroeval}"
NO_EMA="${NO_EMA:-0}"
CHECKPOINT_WAIT_SECONDS="${CHECKPOINT_WAIT_SECONDS:-300}"
CHECKPOINT_WAIT_MAX="${CHECKPOINT_WAIT_MAX:-0}"
STARTUP_STAGGER_SECONDS="${STARTUP_STAGGER_SECONDS:-10}"
MAX_RETRIES="${MAX_RETRIES:-3}"
DRY_RUN="${DRY_RUN:-0}"
QUEUE_ORDER="${QUEUE_ORDER:-default}"
RESUME_EXISTING_QUEUE="${RESUME_EXISTING_QUEUE:-0}"
SKIP_FINAL_MERGE="${SKIP_FINAL_MERGE:-0}"
FINAL_MERGE_ONLY="${FINAL_MERGE_ONLY:-0}"
LITE_EVAL="${LITE_EVAL:-0}"
LITE_SHARD_INDEX="${LITE_SHARD_INDEX:-0}"
if [[ -z "${EVAL_PREFIX+x}" ]]; then
  if [[ "${LITE_EVAL}" == "1" ]]; then
    EVAL_PREFIX="lite_eval"
  else
    EVAL_PREFIX="eval"
  fi
fi
if [[ -z "${DFM_EVAL_PREFIX+x}" ]]; then
  if [[ "${LITE_EVAL}" == "1" ]]; then
    DFM_EVAL_PREFIX="lite_dfm_eval"
  else
    DFM_EVAL_PREFIX="dfm_eval"
  fi
fi

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
  WANDB_SYNC=0 # merge local metrics without logging them to W&B
  MAX_RETRIES=3 # retry failed jobs this many extra times
  QUEUE_ORDER=heavy_first # start longest shard groups first
  QUEUE_ORDER=euroeval_first # start EuroEval one-dataset jobs before other evals
  LITE_EVAL=1 # queue only one deterministic shard per task
  LITE_SHARD_INDEX=0 # shard index to use in lite mode
  EVAL_PREFIX=lite_eval # default in lite mode; eval otherwise
  DFM_EVAL_PREFIX=lite_dfm_eval # default in lite mode; dfm_eval otherwise
  RUN_EUROEVAL=1 # add EuroEval jobs, restricted to da,en by default
  EUROEVAL_BIN='uv run --no-project --with euroeval euroeval' # if not installed
  EUROEVAL_LANGUAGES=da,en
  EUROEVAL_DATASET_GROUPS=... # optional semicolon-separated dataset groups; default is one da/en dataset per job
  EUROEVAL_DATASETS=... # optional; forces one EuroEval job over these datasets
  EUROEVAL_TASKS=... # optional; mutually exclusive with EUROEVAL_DATASETS
  EUROEVAL_FEW_SHOT=0 # optional override; unset uses EuroEval default
  EUROEVAL_NUM_ITERATIONS=1 # optional override; unset uses EuroEval default
  EUROEVAL_GENERATIVE_TYPE=instruction_tuned # optional override; unset uses EuroEval default
  NO_EMA=1 # evaluate raw model weights instead of EMA weights
  RESUME_EXISTING_QUEUE=1 # use existing jobs.tsv/status.tsv instead of rebuilding
  JOB_FILE_OVERRIDE=/tmp/one_job.tsv # optional alternate queue file
  STATUS_FILE_OVERRIDE=/tmp/one_status.tsv # optional alternate status file
  SKIP_FINAL_MERGE=1 # run workers only
  FINAL_MERGE_ONLY=1 # only merge/log existing shard outputs
  DRY_RUN=1   # write and print the queue, then exit before waiting/running
USAGE
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

IFS=',' read -r -a GPUS_ARR <<< "${GPUS_CSV}"
mkdir -p "${LOG_ROOT}" "${DFM_LOG_ROOT}" "${EUROEVAL_LOG_ROOT}" "${LOG_ROOT}/workers"

JOB_FILE="${JOB_FILE_OVERRIDE:-${LOG_ROOT}/jobs.tsv}"
STATUS_FILE="${STATUS_FILE_OVERRIDE:-${LOG_ROOT}/status.tsv}"
LOCK_FILE="${LOCK_FILE_OVERRIDE:-${LOG_ROOT}/jobs.lock}"
WORKER_LOG_DIR="${WORKER_LOG_DIR:-${LOG_ROOT}/workers}"
TELEMETRY_FILE="${TELEMETRY_FILE_OVERRIDE:-${LOG_ROOT}/eval_attempts.tsv}"
TELEMETRY_LOCK_FILE="${TELEMETRY_LOCK_FILE_OVERRIDE:-${LOG_ROOT}/eval_attempts.lock}"
mkdir -p "$(dirname "${JOB_FILE}")" "$(dirname "${STATUS_FILE}")" "$(dirname "${LOCK_FILE}")" "${WORKER_LOG_DIR}"
if [[ "${RESUME_EXISTING_QUEUE}" != "1" ]]; then
  : > "${JOB_FILE}"
  : > "${STATUS_FILE}"
else
  touch "${JOB_FILE}" "${STATUS_FILE}"
fi
TELEMETRY_HEADER="timestamp	ckpt_tag	kind	task	shard	shards	gpu	attempt	batch_size	status	oom	free_before_mib	used_before_mib	total_before_mib	free_after_mib	used_after_mib	total_after_mib	peak_used_mib	log_path"
if [[ ! -s "${TELEMETRY_FILE}" ]]; then
  printf "%s\n" "${TELEMETRY_HEADER}" > "${TELEMETRY_FILE}"
elif ! head -n 1 "${TELEMETRY_FILE}" | grep -q $'\tpeak_used_mib\t'; then
  awk -F'\t' -v OFS='\t' -v header="${TELEMETRY_HEADER}" '
    BEGIN { print header }
    NR == 1 { next }
    NF == 18 {
      log_path = $18
      $18 = "NA"
      $19 = log_path
      print
      next
    }
    { print }
  ' "${TELEMETRY_FILE}" > "${TELEMETRY_FILE}.tmp"
  mv "${TELEMETRY_FILE}.tmp" "${TELEMETRY_FILE}"
fi

log_status() {
  printf "%s\t%s\n" "$(date --iso-8601=seconds)" "$*" | tee -a "${STATUS_FILE}"
}

retry_batch_size() {
  local base="$1" attempt="$2" batch="$1"
  local i
  for ((i = 0; i < attempt; i++)); do
    if (( batch > 1 )); then
      batch=$(((batch + 1) / 2))
    fi
  done
  if (( batch < 1 )); then
    batch=1
  fi
  echo "${batch}"
}

batch_size_for_job() {
  local kind="$1" attempt="$2"
  case "${kind}" in
    standard) retry_batch_size "${STANDARD_BATCH_SIZE}" "${attempt}" ;;
    dfm) retry_batch_size "${DFM_BATCH_SIZE}" "${attempt}" ;;
    dfm_ifeval) retry_batch_size "${IFEVAL_BATCH_SIZE}" "${attempt}" ;;
    euroeval) retry_batch_size "${EUROEVAL_BATCH_SIZE}" "${attempt}" ;;
    *) echo 1 ;;
  esac
}

base_batch_size_for_kind() {
  local kind="$1" name="${2:-}"
  local override_var override_value safe_name
  if [[ -n "${name}" ]]; then
    safe_name="$(printf "%s" "${name}" | tr '[:lower:]-' '[:upper:]_')"
    case "${kind}" in
      standard) override_var="STANDARD_BATCH_SIZE_${safe_name}" ;;
      dfm) override_var="DFM_BATCH_SIZE_${safe_name}" ;;
      dfm_ifeval) override_var="IFEVAL_BATCH_SIZE_${safe_name}" ;;
      euroeval) override_var="EUROEVAL_BATCH_SIZE_${safe_name}" ;;
      *) override_var="" ;;
    esac
    if [[ -n "${override_var}" ]]; then
      override_value="${!override_var:-}"
      if [[ -n "${override_value}" ]]; then
        echo "${override_value}"
        return
      fi
    fi
  fi
  case "${kind}" in
    standard) echo "${STANDARD_BATCH_SIZE}" ;;
    dfm) echo "${DFM_BATCH_SIZE}" ;;
    dfm_ifeval) echo "${IFEVAL_BATCH_SIZE}" ;;
    euroeval) echo "${EUROEVAL_BATCH_SIZE}" ;;
    *) echo 1 ;;
  esac
}

select_batch_size_for_job() {
  local kind="$1" name="$2" attempt="$3" free_before="$4"
  local base
  base="$(base_batch_size_for_kind "${kind}" "${name}")"
  if (( attempt > 0 )); then
    retry_batch_size "${base}" "${attempt}"
    return
  fi
  if [[ ! -s "${TELEMETRY_FILE}" || "${free_before}" == "NA" ]]; then
    echo "${base}"
    return
  fi
  awk -F'\t' -v kind="${kind}" -v task="${name}" -v free="${free_before}" -v base="${base}" '
    NR == 1 { next }
    $3 != kind || $4 != task { next }
    $12 !~ /^[0-9]+$/ || $9 !~ /^[0-9]+$/ { next }
    {
      batch = $9 + 0
      row_free = $12 + 0
      status = $10 + 0
      oom = $11 + 0
      if (oom == 1 && row_free >= free && batch <= base) {
        if (oom_floor == 0 || batch < oom_floor) {
          oom_floor = batch
        }
      }
    }
    END {
      candidate = base
      while (candidate > 1 && oom_floor > 0 && candidate >= oom_floor) {
        candidate = int((candidate + 1) / 2)
      }
      if (candidate < 1) {
        candidate = 1
      }
      print candidate
    }
  ' "${TELEMETRY_FILE}"
}

gpu_mem_snapshot() {
  local gpu="$1"
  local values
  values="$(nvidia-smi -i "${gpu}" --query-gpu=memory.free,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null | head -n 1 | tr -d ' ')" || true
  if [[ -z "${values}" ]]; then
    printf "NA\tNA\tNA"
  else
    printf "%s\n" "${values}" | awk -F, '{printf "%s\t%s\t%s", $1, $2, $3}'
  fi
}

start_gpu_peak_sampler() {
  local gpu="$1" output_file="$2" initial_used="${3:-NA}" poll_seconds="${GPU_MEM_PEAK_POLL_SECONDS:-2}"
  printf "%s\n" "${initial_used}" > "${output_file}"
  (
    local peak="${initial_used}" snapshot used
    while true; do
      snapshot="$(gpu_mem_snapshot "${gpu}")"
      used="$(printf "%s" "${snapshot}" | cut -f2)"
      if [[ "${used}" =~ ^[0-9]+$ ]]; then
        if [[ ! "${peak}" =~ ^[0-9]+$ || "${used}" -gt "${peak}" ]]; then
          peak="${used}"
        fi
      fi
      printf "%s\n" "${peak}" > "${output_file}"
      sleep "${poll_seconds}"
    done
  ) >/dev/null 2>&1 &
  echo "$!"
}

stop_gpu_peak_sampler() {
  local sampler_pid="$1" output_file="$2"
  kill "${sampler_pid}" 2>/dev/null || true
  wait "${sampler_pid}" 2>/dev/null || true
  if [[ -s "${output_file}" ]]; then
    tr -d '\n' < "${output_file}"
  else
    printf "NA"
  fi
}

primary_log_for_job() {
  local kind="$1" name="$2" shard="${3:-0}" shards="${4:-1}"
  case "${kind}" in
    standard)
      printf "%s" "${LOG_ROOT}/standard_shards/${name}/${name}_shard_${shard}_of_${shards}.log"
      ;;
    dfm)
      printf "%s" "${DFM_LOG_ROOT}/${name}/shard_${shard}_of_${shards}/${CKPT_TAG}/dfm-evals.log"
      ;;
    dfm_ifeval)
      printf "%s" "${DFM_LOG_ROOT}/ifeval_shard_${name}/${CKPT_TAG}/dfm-evals.log"
      ;;
    euroeval)
      if [[ "${shards}" != "1" || "${name}" != "euroeval" ]]; then
        printf "%s" "${EUROEVAL_LOG_ROOT}/${CKPT_TAG}/${name}/euroeval.log"
      else
        printf "%s" "${EUROEVAL_LOG_ROOT}/${CKPT_TAG}/euroeval.log"
      fi
      ;;
    *)
      printf ""
      ;;
  esac
}

oom_for_job() {
  local kind="$1" name="$2" shard="${3:-0}" shards="${4:-1}"
  local paths=()
  case "${kind}" in
    standard)
      paths+=("${LOG_ROOT}/standard_shards/${name}/${name}_shard_${shard}_of_${shards}.log")
      ;;
    dfm)
      paths+=("${DFM_LOG_ROOT}/${name}/shard_${shard}_of_${shards}/${CKPT_TAG}/dfm-evals.log")
      paths+=("${DFM_LOG_ROOT}/${name}/shard_${shard}_of_${shards}/${CKPT_TAG}/server.log")
      ;;
    dfm_ifeval)
      paths+=("${DFM_LOG_ROOT}/ifeval_shard_${name}/${CKPT_TAG}/dfm-evals.log")
      paths+=("${DFM_LOG_ROOT}/ifeval_shard_${name}/${CKPT_TAG}/server.log")
      ;;
    euroeval)
      if [[ "${shards}" != "1" || "${name}" != "euroeval" ]]; then
        paths+=("${EUROEVAL_LOG_ROOT}/${CKPT_TAG}/${name}/euroeval.log")
        paths+=("${EUROEVAL_LOG_ROOT}/${CKPT_TAG}/${name}/server.log")
      else
        paths+=("${EUROEVAL_LOG_ROOT}/${CKPT_TAG}/euroeval.log")
        paths+=("${EUROEVAL_LOG_ROOT}/${CKPT_TAG}/server.log")
      fi
      ;;
  esac
  local path
  for path in "${paths[@]}"; do
    if [[ -f "${path}" ]] && grep -Eiq "OutOfMemoryError|CUDA out of memory|out of memory" "${path}"; then
      echo 1
      return 0
    fi
  done
  echo 0
}

log_eval_attempt() {
  local kind="$1" name="$2" shard="$3" shards="$4" gpu="$5" attempt="$6" batch_size="$7" status="$8" oom="$9" before="${10}" after="${11}" peak_used="${12}" log_path="${13}"
  {
    flock -x 9
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
      "$(date --iso-8601=seconds)" "${CKPT_TAG}" "${kind}" "${name}" "${shard:-0}" "${shards:-1}" "${gpu}" "${attempt}" "${batch_size}" "${status}" "${oom}" "${before}" "${after}" "${peak_used}" "${log_path}" \
      >> "${TELEMETRY_FILE}"
  } 9>"${TELEMETRY_LOCK_FILE}"
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
  elif [[ "${QUEUE_ORDER}" == "euroeval_first" ]]; then
    standard_tasks=(MATH GSM8k DROP MMLU HellaSwag ARC Winogrande BoolQ)
    dfm_tasks=(govreport wmt24pp_en_da generative_talemaader nordjyllandnews humaneval gec_dala multi_wiki_qa danish_citizen_tests dala piqa)
    enqueue_ifeval_first=2
  elif [[ "${QUEUE_ORDER}" == "default" ]]; then
    standard_tasks=(GSM8k DROP MMLU ARC HellaSwag Winogrande BoolQ MATH)
    dfm_tasks=(danish_citizen_tests dala gec_dala wmt24pp_en_da multi_wiki_qa piqa generative_talemaader govreport nordjyllandnews humaneval)
    enqueue_ifeval_first=0
  else
    echo "Unsupported QUEUE_ORDER=${QUEUE_ORDER}" >&2
    return 1
  fi

  if [[ "${enqueue_ifeval_first}" == "2" ]]; then
    enqueue_euroeval_job
    enqueue_ifeval_jobs
  elif [[ "${enqueue_ifeval_first}" == "1" ]]; then
    enqueue_ifeval_jobs
    enqueue_euroeval_job
  fi

  for task in "${standard_tasks[@]}"; do
    local shards
    shards="$(standard_shards_for_task "${task}")"
    enqueue_sharded_job standard "${task}" "${shards}"
  done
  for task in "${dfm_tasks[@]}"; do
    local shards
    shards="$(dfm_shards_for_task "${task}")"
    enqueue_sharded_job dfm "${task}" "${shards}"
  done

  if [[ "${enqueue_ifeval_first}" == "0" ]]; then
    enqueue_ifeval_jobs
    enqueue_euroeval_job
  fi
}

enqueue_sharded_job() {
  local kind="$1" task="$2" shards="$3" shard
  if [[ "${LITE_EVAL}" == "1" ]]; then
    if (( LITE_SHARD_INDEX >= shards )); then
      echo "LITE_SHARD_INDEX=${LITE_SHARD_INDEX} is out of range for ${task} (${shards} shards)." >&2
      return 1
    fi
    printf "%s\t%s\t%s\t%s\n" "${kind}" "${task}" "${LITE_SHARD_INDEX}" "${shards}" >> "${JOB_FILE}"
    return 0
  fi
  for ((shard = 0; shard < shards; shard++)); do
    printf "%s\t%s\t%s\t%s\n" "${kind}" "${task}" "${shard}" "${shards}" >> "${JOB_FILE}"
  done
}

enqueue_ifeval_jobs() {
  local shard
  if [[ "${LITE_EVAL}" == "1" ]]; then
    if (( LITE_SHARD_INDEX >= DFM_IFEVAL_SHARDS )); then
      echo "LITE_SHARD_INDEX=${LITE_SHARD_INDEX} is out of range for IFEval-DA (${DFM_IFEVAL_SHARDS} shards)." >&2
      return 1
    fi
    printf "dfm_ifeval\t%s\n" "${LITE_SHARD_INDEX}" >> "${JOB_FILE}"
    return 0
  fi
  for ((shard = 0; shard < DFM_IFEVAL_SHARDS; shard++)); do
    printf "dfm_ifeval\t%s\n" "${shard}" >> "${JOB_FILE}"
  done
}

enqueue_euroeval_job() {
  if [[ "${RUN_EUROEVAL}" == "1" ]]; then
    local groups_csv="${EUROEVAL_DATASET_GROUPS}" group_index group_count group
    if [[ -z "${groups_csv}" && -z "${EUROEVAL_DATASETS}" && -z "${EUROEVAL_TASKS}" && "${EUROEVAL_LANGUAGES}" == "da,en" ]]; then
      groups_csv="angry-tweets;scala-da;dansk;multi-wiki-qa-da;nordjylland-news;danske-talemaader;danish-citizen-tests;hellaswag-da;ifeval-da;valeu-da;sst5;scala-en;conll-en;squad;cnn-dailymail;life-in-the-uk;hellaswag;ifeval;bfcl-v2;valeu-en"
    fi
    if [[ -n "${groups_csv}" ]]; then
      IFS=';' read -r -a groups <<< "${groups_csv}"
      group_count="${#groups[@]}"
      for group_index in "${!groups[@]}"; do
        group="${groups[$group_index]}"
        group="${group#"${group%%[![:space:]]*}"}"
        group="${group%"${group##*[![:space:]]}"}"
        [[ -z "${group}" ]] && continue
        printf "euroeval\t%s\t%s\t%s\n" "${group}" "${group_index}" "${group_count}" >> "${JOB_FILE}"
      done
    else
      printf "euroeval\teuroeval\t0\t1\n" >> "${JOB_FILE}"
    fi
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
  local expected_model="${2:-}"
  for _ in $(seq 1 240); do
    if "${PYTHON_BIN}" - "$url" "${expected_model}" <<'PY'
import json
import sys
import urllib.request

try:
    with urllib.request.urlopen(sys.argv[1], timeout=2) as response:
        if response.status != 200:
            raise SystemExit(1)
        expected_model = sys.argv[2]
        if expected_model:
            data = json.loads(response.read())
            if data.get("model") != expected_model:
                raise SystemExit(1)
        raise SystemExit(0)
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
  local gpu="$1" task="$2" shard="${3:-0}" shards="${4:-1}" effective_batch_size="${5:-${STANDARD_BATCH_SIZE}}"
  local dir="${LOG_ROOT}/standard_shards/${task}"
  mkdir -p "${dir}"
  local log="${dir}/${task}_shard_${shard}_of_${shards}.log"
  local ema_args=()
  if [[ "${NO_EMA}" == "1" ]]; then
    ema_args=(ckpt_use_ema=false)
  fi
  export CUDA_VISIBLE_DEVICES="${gpu}"
  export PYTHONUNBUFFERED=1
  local status
  set +e
  "${PYTHON_BIN}" -u -m evaluation.main \
    config="${STANDARD_CONFIG}" \
    ckpt_path="${CKPT_PATH}" \
    ckpt_tag="${CKPT_TAG}" \
    "run_only=[${task}]" \
    "shard_overrides.${task}.num_shards=${shards}" \
    "shard_overrides.${task}.shard_index=${shard}" \
    generation_config.batch_size="${effective_batch_size}" \
    "${ema_args[@]}" \
    > "${log}" 2>&1
  status=$?
  if [[ "${status}" != "0" ]]; then
    return "${status}"
  fi
  if ! grep -q -- "--- ${task} ---" "${log}"; then
    echo "Missing ${task} summary in ${log}" >&2
    return 4
  fi
}

run_dfm_task() {
  local gpu="$1" task="$2" worker_id="$3" shard="${4:-0}" shards="${5:-1}" effective_batch_size="${6:-${DFM_BATCH_SIZE}}"
  local suite model_name run_dir inspect_dir eee_dir server_log port base_url
  suite="$(dfm_suite_for_task "${task}")"
  port=$((PORT_BASE + gpu * 100 + RANDOM % 80 + 1))
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
    local judge_gpu="${JUDGE_GPU:-${gpu}}"
    local judge_port=$((JUDGE_PORT + judge_gpu))
    local judge_dir="${DFM_LOG_ROOT}/judge_gemma4_e4b_gpu${judge_gpu}"
    mkdir -p "${judge_dir}"
    CUDA_VISIBLE_DEVICES="${judge_gpu}" "${PYTHON_BIN}" scripts/transformers_openai_server.py \
      "${JUDGE_MODEL}" \
      --served-model-name "${JUDGE_SERVED_NAME}" \
      --host "${HOST}" \
      --port "${judge_port}" \
      > "${judge_dir}/server.log" 2>&1 &
    judge_pid="$!"
    wait_for_server "http://${HOST}:${judge_port}/health" || return 1
    judge_args=(--judge-model "openai/${JUDGE_SERVED_NAME}" --judge-base-url "http://${HOST}:${judge_port}/v1")
  fi

  local server_pid=""
  local server_ema_args=()
  if [[ "${NO_EMA}" == "1" ]]; then
    server_ema_args=(--no-ema)
  fi
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

  CUDA_VISIBLE_DEVICES="${gpu}" "${PYTHON_BIN}" scripts/hrm_openai_server.py \
    --ckpt-path "${CKPT_PATH}" \
    --ckpt-tag "${CKPT_TAG}" \
    --host "${HOST}" \
    --port "${port}" \
    --model-name "${model_name}" \
    --max-context "${MAX_CONTEXT}" \
    --batch-size "${effective_batch_size}" \
    --batch-timeout-ms "${DFM_BATCH_TIMEOUT_MS}" \
    --condition direct \
    "${server_ema_args[@]}" \
    > "${server_log}" 2>&1 &
  server_pid="$!"
  wait_for_server "http://${HOST}:${port}/health" "${model_name}" || return 1

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
    --max-connections "${effective_batch_size}" \
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
  local gpu="$1" shard="$2" worker_id="$3" effective_batch_size="${4:-${IFEVAL_BATCH_SIZE}}"
  local port=$((PORT_BASE + 1000 + gpu * 100 + shard))
  local base_url="http://${HOST}:${port}/v1"
  local suite
  suite="$(ifeval_suite_for_shard "${shard}")"
  local model_name="${MODEL_PREFIX}-ifeval-da-shard-${shard}-${CKPT_TAG}"
  local run_dir="${DFM_LOG_ROOT}/ifeval_shard_${shard}/${CKPT_TAG}"
  local inspect_dir="${run_dir}/inspect"
  local eee_dir="${run_dir}/eee"
  local server_ema_args=()
  if [[ "${NO_EMA}" == "1" ]]; then
    server_ema_args=(--no-ema)
  fi
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

  CUDA_VISIBLE_DEVICES="${gpu}" "${PYTHON_BIN}" scripts/hrm_openai_server.py \
    --ckpt-path "${CKPT_PATH}" \
    --ckpt-tag "${CKPT_TAG}" \
    --host "${HOST}" \
    --port "${port}" \
    --model-name "${model_name}" \
    --max-context "${MAX_CONTEXT}" \
    --batch-size "${effective_batch_size}" \
    --batch-timeout-ms "${IFEVAL_BATCH_TIMEOUT_MS}" \
    --condition direct \
    "${server_ema_args[@]}" \
    > "${run_dir}/server.log" 2>&1 &
  server_pid="$!"
  wait_for_server "http://${HOST}:${port}/health" "${model_name}" || return 1

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
    --max-connections "${effective_batch_size}" \
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

run_euroeval_task() {
  local gpu="$1" effective_batch_size="${2:-${EUROEVAL_BATCH_SIZE}}" dataset_group="${3:-euroeval}" group_count="${4:-1}"
  local port=$((PORT_BASE + 2000 + gpu * 100 + RANDOM % 80 + 1))
  local run_root="${EUROEVAL_LOG_ROOT}/${CKPT_TAG}"
  local datasets="${EUROEVAL_DATASETS}"
  if [[ "${group_count}" != "1" || "${dataset_group}" != "euroeval" ]]; then
    run_root="${run_root}/${dataset_group}"
    datasets="${dataset_group}"
  fi

  GPU="${gpu}" \
  PORT="${port}" \
  CKPT_PATH="${CKPT_PATH}" \
  CKPT_TAG="${CKPT_TAG}" \
  EVAL_EPOCH="${EVAL_EPOCH}" \
  EUROEVAL_LOG_ROOT="${run_root}" \
  MODEL_PREFIX="${MODEL_PREFIX}" \
  MAX_CONTEXT="${MAX_CONTEXT}" \
  EUROEVAL_BATCH_SIZE="${effective_batch_size}" \
  EUROEVAL_BATCH_TIMEOUT_MS="${EUROEVAL_BATCH_TIMEOUT_MS}" \
  EUROEVAL_LANGUAGES="${EUROEVAL_LANGUAGES}" \
  EUROEVAL_DATASETS="${datasets}" \
  EUROEVAL_TASKS="${EUROEVAL_TASKS}" \
  EUROEVAL_FEW_SHOT="${EUROEVAL_FEW_SHOT}" \
  EUROEVAL_NUM_ITERATIONS="${EUROEVAL_NUM_ITERATIONS}" \
  EUROEVAL_GENERATIVE_TYPE="${EUROEVAL_GENERATIVE_TYPE}" \
  EUROEVAL_BIN="${EUROEVAL_BIN}" \
  EUROEVAL_PREFIX="${EUROEVAL_PREFIX}" \
  HOST="${HOST}" \
  NO_EMA="${NO_EMA}" \
  WANDB_SYNC="${WANDB_SYNC}" \
  WANDB_PROJECT="${WANDB_PROJECT}" \
  WANDB_RUN_ID="${WANDB_RUN_ID}" \
  WANDB_RUN_NAME="${WANDB_RUN_NAME}" \
  PYTHON_BIN="${PYTHON_BIN}" \
  scripts/run_euroeval_on_checkpoint.sh
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
      local effective_batch_size mem_before mem_after oom log_path peak_file peak_pid peak_used
      mem_before="$(gpu_mem_snapshot "${gpu}")"
      effective_batch_size="$(select_batch_size_for_job "${kind}" "${name}" "${attempt}" "$(printf "%s" "${mem_before}" | cut -f1)")"
      log_path="$(primary_log_for_job "${kind}" "${name}" "${shard:-0}" "${shards:-1}")"
      peak_file="${WORKER_LOG_DIR}/gpu_${gpu}_${kind}_${name}_shard_${shard:-0}_attempt_$((attempt + 1)).peak_mib"
      peak_pid="$(start_gpu_peak_sampler "${gpu}" "${peak_file}" "$(printf "%s" "${mem_before}" | cut -f2)")"
      log_status "START ${kind} ${name} shard_${shard:-0}_of_${shards:-1} gpu_${gpu} attempt_$((attempt + 1))_of_$((MAX_RETRIES + 1)) batch_${effective_batch_size} mem_free_before_$(printf "%s" "${mem_before}" | cut -f1)"
      set +e
      case "${kind}" in
        standard) run_standard "${gpu}" "${name}" "${shard:-0}" "${shards:-1}" "${effective_batch_size}" ;;
        dfm) run_dfm_task "${gpu}" "${name}" "${worker_id}" "${shard:-0}" "${shards:-1}" "${effective_batch_size}" ;;
        dfm_ifeval) run_dfm_ifeval "${gpu}" "${name}" "${worker_id}" "${effective_batch_size}" ;;
        euroeval) run_euroeval_task "${gpu}" "${effective_batch_size}" "${name}" "${shards:-1}" ;;
        *) echo "Unknown job kind: ${kind}" >&2; status=2 ;;
      esac
      status=$?
      set -e
      peak_used="$(stop_gpu_peak_sampler "${peak_pid}" "${peak_file}")"
      mem_after="$(gpu_mem_snapshot "${gpu}")"
      oom="$(oom_for_job "${kind}" "${name}" "${shard:-0}" "${shards:-1}")"
      log_eval_attempt "${kind}" "${name}" "${shard:-0}" "${shards:-1}" "${gpu}" "$((attempt + 1))" "${effective_batch_size}" "${status}" "${oom}" "${mem_before}" "${mem_after}" "${peak_used}" "${log_path}"
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
  local wandb_args=()
  if [[ "${WANDB_SYNC}" == "1" ]]; then
    wandb_args=(
      --log-wandb
      --project "${WANDB_PROJECT}"
      --run-id "${WANDB_RUN_ID}"
      --run-name "${WANDB_RUN_NAME}"
    )
  fi
  local task shards
  for task in GSM8k DROP MMLU ARC HellaSwag Winogrande BoolQ MATH; do
    shards="$(standard_shards_for_task "${task}")"
    local standard_paths=()
    if [[ "${LITE_EVAL}" == "1" ]]; then
      standard_paths=("${LOG_ROOT}/standard_shards/${task}/${task}_shard_${LITE_SHARD_INDEX}_of_${shards}.log")
    else
      standard_paths=("${LOG_ROOT}"/standard_shards/"${task}"/"${task}"_shard_*_of_"${shards}".log)
    fi
    "${PYTHON_BIN}" scripts/merge_standard_eval_shards.py \
      "${standard_paths[@]}" \
      --benchmark "${task}" \
      --epoch "${EVAL_EPOCH}" \
      --output "${LOG_ROOT}/standard_shards/${task}/merged_metrics.json" \
      --prefix "${EVAL_PREFIX}" \
      "${wandb_args[@]}" \
      > "${LOG_ROOT}/standard_shards/${task}/merge_and_wandb_sync.log" 2>&1 || log_status "FINAL_MERGE_STANDARD_${task}_FAILED"
  done

  local ifeval_paths=()
  local shard
  if [[ "${LITE_EVAL}" == "1" ]]; then
    ifeval_paths=("${DFM_LOG_ROOT}/ifeval_shard_${LITE_SHARD_INDEX}/${CKPT_TAG}/inspect"/*.eval)
  else
    for ((shard = 0; shard < DFM_IFEVAL_SHARDS; shard++)); do
      ifeval_paths+=("${DFM_LOG_ROOT}/ifeval_shard_${shard}/${CKPT_TAG}/inspect"/*.eval)
    done
  fi
  "${PYTHON_BIN}" scripts/merge_ifeval_da_shards.py \
    "${ifeval_paths[@]}" \
    --epoch "${EVAL_EPOCH}" \
    --output "${DFM_LOG_ROOT}/merged_ifeval_da_metrics.json" \
    --prefix "${DFM_EVAL_PREFIX}" \
    "${wandb_args[@]}" \
    > "${DFM_LOG_ROOT}/merge_ifeval_da_wandb.log" 2>&1 || log_status "FINAL_MERGE_IFEVAL_FAILED"

  for task in danish_citizen_tests dala gec_dala wmt24pp_en_da multi_wiki_qa piqa generative_talemaader govreport nordjyllandnews humaneval; do
    local shards
    shards="$(dfm_shards_for_task "${task}")"
    local paths=()
    if [[ "${LITE_EVAL}" == "1" ]]; then
      paths=("${DFM_LOG_ROOT}/${task}/shard_${LITE_SHARD_INDEX}_of_${shards}/${CKPT_TAG}/inspect"/*.eval)
    else
      for ((shard = 0; shard < shards; shard++)); do
        paths+=("${DFM_LOG_ROOT}/${task}/shard_${shard}_of_${shards}/${CKPT_TAG}/inspect"/*.eval)
      done
    fi
    "${PYTHON_BIN}" scripts/merge_dfm_eval_shards.py \
      "${paths[@]}" \
      --task "${task}" \
      --epoch "${EVAL_EPOCH}" \
      --output "${DFM_LOG_ROOT}/${task}/merged_metrics.json" \
      --prefix "${DFM_EVAL_PREFIX}" \
      "${wandb_args[@]}" \
      > "${DFM_LOG_ROOT}/${task}/merge_and_wandb_sync.log" 2>&1 || log_status "FINAL_MERGE_DFM_${task}_FAILED"
  done
  log_status "FINAL_MERGE_END"
}

if [[ "${FINAL_MERGE_ONLY}" == "1" ]]; then
  final_merge
  exit 0
elif [[ "${RESUME_EXISTING_QUEUE}" == "1" ]]; then
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
  worker "${gpu}" "${i}" > "${WORKER_LOG_DIR}/worker_${i}_gpu_${gpu}.log" 2>&1 &
  pids+=("$!")
done
log_status "WORKERS ${pids[*]}"

final_status=0
for pid in "${pids[@]}"; do
  if ! wait "${pid}"; then
    final_status=1
  fi
done

if [[ "${SKIP_FINAL_MERGE}" != "1" ]]; then
  final_merge
fi
exit "${final_status}"
