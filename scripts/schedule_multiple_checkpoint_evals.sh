#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

CKPT_TAGS_CSV="${CKPT_TAGS:-}"
EVAL_EPOCHS_CSV="${EVAL_EPOCHS:-}"
CKPT_PATH="${CKPT_PATH:-checkpoints/dfm/L}"
LOG_ROOT_BASE="${LOG_ROOT_BASE:-logs/eval/multi_checkpoint_$(date +%Y%m%dT%H%M%S)}"
DFM_LOG_ROOT_BASE="${DFM_LOG_ROOT_BASE:-logs/dfm_evals/multi_checkpoint_$(date +%Y%m%dT%H%M%S)}"
EUROEVAL_LOG_ROOT_BASE="${EUROEVAL_LOG_ROOT_BASE:-logs/euroeval/multi_checkpoint_$(date +%Y%m%dT%H%M%S)}"
GPUS_CSV="${GPUS:-0,1,2,3,4,5,6,7}"
QUEUE_ORDER="${QUEUE_ORDER:-heavy_first}"
LITE_EVAL="${LITE_EVAL:-1}"
LITE_SHARD_INDEX="${LITE_SHARD_INDEX:-0}"
MODEL_PREFIX="${MODEL_PREFIX:-hrm-multi-checkpoint}"
STANDARD_BATCH_SIZE="${STANDARD_BATCH_SIZE:-8}"
DFM_BATCH_SIZE="${DFM_BATCH_SIZE:-8}"
IFEVAL_BATCH_SIZE="${IFEVAL_BATCH_SIZE:-16}"
DFM_BATCH_TIMEOUT_MS="${DFM_BATCH_TIMEOUT_MS:-25}"
IFEVAL_BATCH_TIMEOUT_MS="${IFEVAL_BATCH_TIMEOUT_MS:-25}"
DRY_RUN="${DRY_RUN:-0}"
CHECKPOINT_POLL_SECONDS="${CHECKPOINT_POLL_SECONDS:-60}"
MAX_RETRIES="${MAX_RETRIES:-3}"
RESUME_EXISTING_QUEUE="${RESUME_EXISTING_QUEUE:-0}"
SKIP_FINAL_MERGE="${SKIP_FINAL_MERGE:-0}"
NO_EMA="${NO_EMA:-0}"
WANDB_SYNC="${WANDB_SYNC:-1}"
WANDB_PROJECT="${WANDB_PROJECT:-}"
WANDB_RUN_ID="${WANDB_RUN_ID:-}"
WANDB_RUN_NAME="${WANDB_RUN_NAME:-}"
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
PYTHON_BIN="${PYTHON_BIN:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python"
fi
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
Run checkpoint evals for multiple checkpoints through one shared GPU queue.

Unlike launching one checkpoint scheduler after another, this keeps a single
job queue. When the last few jobs for checkpoint N are still running, idle GPUs
can immediately take ready jobs for checkpoint N+1.

Required:
  CKPT_TAGS=step_500000,step_550000
  EVAL_EPOCHS=1.1945518877503482,1.314007076525383

Common overrides:
  CKPT_PATH=checkpoints/dfm/L
  GPUS=0,1,2,3,4,5,6,7
  LITE_EVAL=1
  LITE_SHARD_INDEX=0
  MODEL_PREFIX=hrm-dfm5-XXS
  QUEUE_ORDER=heavy_first
  WANDB_PROJECT="Original Plus Mixed Danish Instruction Rich L"
  WANDB_RUN_ID=dfm-l-resume-epoch3
  WANDB_RUN_NAME=dfm-L-resume-epoch3
  EVAL_PREFIX=lite_eval
  DFM_EVAL_PREFIX=lite_dfm_eval
  NO_EMA=1
  WANDB_SYNC=0 # merge local metrics without logging them to W&B
  RESUME_EXISTING_QUEUE=1 # consume an existing shared queue instead of rebuilding it
  SKIP_FINAL_MERGE=1 # run workers only; let the original scheduler do final merge
  LOG_ROOT_BASE=logs/eval/dfm_L_lite_probe
  DFM_LOG_ROOT_BASE=logs/dfm_evals/dfm_L_lite_probe
  RUN_EUROEVAL=1 # enqueue one da,en EuroEval job per checkpoint
  EUROEVAL_DATASET_GROUPS='a,b;c,d' # optional; enqueue one EuroEval job per group
  EUROEVAL_FEW_SHOT=0 # optional override; unset uses EuroEval default
  EUROEVAL_NUM_ITERATIONS=1 # optional override; unset uses EuroEval default
  EUROEVAL_GENERATIVE_TYPE=instruction_tuned # optional override; unset uses EuroEval default
  EUROEVAL_LOG_ROOT_BASE=logs/euroeval/dfm_L_lite_probe

Each checkpoint writes to:
  ${LOG_ROOT_BASE}/${CKPT_TAG}
  ${DFM_LOG_ROOT_BASE}/${CKPT_TAG}
  ${EUROEVAL_LOG_ROOT_BASE}/${CKPT_TAG}
USAGE
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ -z "${CKPT_TAGS_CSV}" || -z "${EVAL_EPOCHS_CSV}" ]]; then
  usage >&2
  exit 2
fi

IFS=',' read -r -a CKPT_TAGS_ARR <<< "${CKPT_TAGS_CSV}"
IFS=',' read -r -a EVAL_EPOCHS_ARR <<< "${EVAL_EPOCHS_CSV}"
IFS=',' read -r -a GPUS_ARR <<< "${GPUS_CSV}"

if [[ "${#CKPT_TAGS_ARR[@]}" -ne "${#EVAL_EPOCHS_ARR[@]}" ]]; then
  echo "CKPT_TAGS and EVAL_EPOCHS must have the same number of entries." >&2
  exit 2
fi

mkdir -p "${LOG_ROOT_BASE}/workers" "${LOG_ROOT_BASE}/jobfiles" "${DFM_LOG_ROOT_BASE}" "${EUROEVAL_LOG_ROOT_BASE}"
JOB_FILE="${LOG_ROOT_BASE}/jobs.tsv"
STATUS_FILE="${LOG_ROOT_BASE}/status.tsv"
LOCK_FILE="${LOG_ROOT_BASE}/jobs.lock"
if [[ "${RESUME_EXISTING_QUEUE}" != "1" ]]; then
  : > "${JOB_FILE}"
  : > "${STATUS_FILE}"
else
  touch "${JOB_FILE}" "${STATUS_FILE}"
fi

log_status() {
  printf "%s\t%s\n" "$(date --iso-8601=seconds)" "$*" | tee -a "${STATUS_FILE}"
}

epoch_label() {
  local value="$1"
  if [[ "${value}" =~ ^[0-9]+([.]0+)?$ ]]; then
    printf "%s" "${value%%.*}"
  else
    printf "%s" "${value//./p}"
  fi
}

checkpoint_ready() {
  local ckpt_tag="$1" rank
  if [[ -d "${CKPT_PATH}/fsdp2_${ckpt_tag}" ]]; then
    [[ -f "${CKPT_PATH}/fsdp2_${ckpt_tag}/.metadata" ]] || return 1
  elif [[ -f "${CKPT_PATH}/unsharded_${ckpt_tag}.pt" ]]; then
    true
  else
    return 1
  fi
  for rank in 0 1 2 3 4 5 6 7; do
    [[ -f "${CKPT_PATH}/carry_${ckpt_tag}.${rank}.pt" ]] || return 1
  done
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

enqueue_sharded_jobs() {
  local ckpt_tag="$1" eval_epoch="$2" kind="$3" task="$4" shards="$5" shard
  local log_root="${LOG_ROOT_BASE}/${ckpt_tag}"
  local dfm_log_root="${DFM_LOG_ROOT_BASE}/${ckpt_tag}"
  mkdir -p "${log_root}" "${dfm_log_root}"
  if [[ "${LITE_EVAL}" == "1" ]]; then
    if (( LITE_SHARD_INDEX >= shards )); then
      echo "LITE_SHARD_INDEX=${LITE_SHARD_INDEX} is out of range for ${task} (${shards} shards)." >&2
      return 1
    fi
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
      "${ckpt_tag}" "${eval_epoch}" "${kind}" "${task}" "${LITE_SHARD_INDEX}" "${shards}" "${log_root}" "${dfm_log_root}" \
      >> "${JOB_FILE}"
    return 0
  fi
  for ((shard = 0; shard < shards; shard++)); do
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
      "${ckpt_tag}" "${eval_epoch}" "${kind}" "${task}" "${shard}" "${shards}" "${log_root}" "${dfm_log_root}" \
      >> "${JOB_FILE}"
  done
}

enqueue_ifeval_jobs() {
  local ckpt_tag="$1" eval_epoch="$2" shard
  local log_root="${LOG_ROOT_BASE}/${ckpt_tag}"
  local dfm_log_root="${DFM_LOG_ROOT_BASE}/${ckpt_tag}"
  mkdir -p "${log_root}" "${dfm_log_root}"
  if [[ "${LITE_EVAL}" == "1" ]]; then
    printf "%s\t%s\tdfm_ifeval\t%s\t0\t%s\t%s\t%s\n" \
      "${ckpt_tag}" "${eval_epoch}" "${LITE_SHARD_INDEX}" "${DFM_IFEVAL_SHARDS:-32}" "${log_root}" "${dfm_log_root}" \
      >> "${JOB_FILE}"
    return 0
  fi
  for ((shard = 0; shard < ${DFM_IFEVAL_SHARDS:-32}; shard++)); do
    printf "%s\t%s\tdfm_ifeval\t%s\t0\t%s\t%s\t%s\n" \
      "${ckpt_tag}" "${eval_epoch}" "${shard}" "${DFM_IFEVAL_SHARDS:-32}" "${log_root}" "${dfm_log_root}" \
      >> "${JOB_FILE}"
  done
}

enqueue_euroeval_job() {
  local ckpt_tag="$1" eval_epoch="$2"
  local log_root="${LOG_ROOT_BASE}/${ckpt_tag}"
  local dfm_log_root="${DFM_LOG_ROOT_BASE}/${ckpt_tag}"
  local euroeval_log_root="${EUROEVAL_LOG_ROOT_BASE}/${ckpt_tag}"
  local group_index group_count group groups_csv
  if [[ "${RUN_EUROEVAL}" == "1" ]]; then
    mkdir -p "${log_root}" "${dfm_log_root}" "${euroeval_log_root}"
    groups_csv="${EUROEVAL_DATASET_GROUPS}"
    if [[ -z "${groups_csv}" && -z "${EUROEVAL_DATASETS}" && -z "${EUROEVAL_TASKS}" && "${EUROEVAL_LANGUAGES}" == "da,en" ]]; then
      groups_csv="angry-tweets;scala-da;dansk;multi-wiki-qa-da;nordjylland-news;danske-talemaader;danish-citizen-tests;hellaswag-da;ifeval-da;valeu-da;sst5;scala-en;conll-en;squad;cnn-dailymail;life-in-the-uk;hellaswag;ifeval;bfcl-v2;valeu-en"
    fi
    if [[ -n "${groups_csv}" ]]; then
      IFS=';' read -r -a groups <<< "${groups_csv}"
      group_count="${#groups[@]}"
      for group_index in "${!groups[@]}"; do
        group="${groups[$group_index]}"
        [[ -z "${group//[[:space:]]/}" ]] && continue
        printf "%s\t%s\teuroeval\teuroeval_g%s\t%s\t%s\t%s\t%s\t%s\n" \
          "${ckpt_tag}" "${eval_epoch}" "${group_index}" "${group_index}" "${group_count}" "${log_root}" "${dfm_log_root}" "${group}" \
          >> "${JOB_FILE}"
      done
    else
      printf "%s\t%s\teuroeval\teuroeval\t0\t1\t%s\t%s\t%s\n" \
        "${ckpt_tag}" "${eval_epoch}" "${log_root}" "${dfm_log_root}" "${EUROEVAL_DATASETS}" \
        >> "${JOB_FILE}"
    fi
  fi
}

enqueue_checkpoint() {
  local ckpt_tag="$1" eval_epoch="$2" task shards
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
    enqueue_ifeval_jobs "${ckpt_tag}" "${eval_epoch}"
    enqueue_euroeval_job "${ckpt_tag}" "${eval_epoch}"
  fi
  for task in "${standard_tasks[@]}"; do
    shards="$(standard_shards_for_task "${task}")"
    enqueue_sharded_jobs "${ckpt_tag}" "${eval_epoch}" standard "${task}" "${shards}"
  done
  for task in "${dfm_tasks[@]}"; do
    shards="$(dfm_shards_for_task "${task}")"
    enqueue_sharded_jobs "${ckpt_tag}" "${eval_epoch}" dfm "${task}" "${shards}"
  done
  if [[ "${enqueue_ifeval_first}" == "0" ]]; then
    enqueue_ifeval_jobs "${ckpt_tag}" "${eval_epoch}"
    enqueue_euroeval_job "${ckpt_tag}" "${eval_epoch}"
  fi
}

pop_ready_job() {
  local line rest candidate ckpt_tag
  line=""
  rest=""
  {
    flock -x 9
    while IFS= read -r candidate; do
      IFS=$'\t' read -r ckpt_tag _ <<< "${candidate}"
      if [[ -z "${line}" ]] && checkpoint_ready "${ckpt_tag}"; then
        line="${candidate}"
      else
        rest+="${candidate}"$'\n'
      fi
    done < "${JOB_FILE}"
    printf "%s" "${rest}" > "${JOB_FILE}.tmp"
    mv "${JOB_FILE}.tmp" "${JOB_FILE}"
    printf "%s" "${line}"
  } 9>"${LOCK_FILE}"
}

run_one_job() {
  local gpu="$1" worker_id="$2" line="$3"
  local ckpt_tag eval_epoch kind task shard shards log_root dfm_log_root euroeval_datasets
  IFS=$'\t' read -r ckpt_tag eval_epoch kind task shard shards log_root dfm_log_root euroeval_datasets <<< "${line}"
  local job_id="${worker_id}_$(date +%s%N)"
  local job_dir="${LOG_ROOT_BASE}/jobfiles/${job_id}"
  local child_job_file="${job_dir}/jobs.tsv"
  local child_status_file="${job_dir}/status.tsv"
  local child_lock_file="${job_dir}/jobs.lock"
  local child_worker_log_dir="${log_root}/workers_multi/${job_id}"
  mkdir -p "${job_dir}" "${child_worker_log_dir}"
  if [[ "${kind}" == "dfm_ifeval" ]]; then
    printf "dfm_ifeval\t%s\n" "${task}" > "${child_job_file}"
  else
    printf "%s\t%s\t%s\t%s\n" "${kind}" "${task}" "${shard}" "${shards}" > "${child_job_file}"
  fi

  log_status "START ${ckpt_tag} ${kind} ${task} shard_${shard}_of_${shards} gpu_${gpu}"
  set +e
  CKPT_TAG="${ckpt_tag}" \
  EVAL_EPOCH="${eval_epoch}" \
  CKPT_PATH="${CKPT_PATH}" \
  GPUS="${gpu}" \
  LOG_ROOT="${log_root}" \
  DFM_LOG_ROOT="${dfm_log_root}" \
  EUROEVAL_LOG_ROOT="${EUROEVAL_LOG_ROOT_BASE}/${ckpt_tag}/${task}" \
  RUN_EUROEVAL="${RUN_EUROEVAL}" \
  EUROEVAL_BATCH_SIZE="${EUROEVAL_BATCH_SIZE}" \
  EUROEVAL_BATCH_TIMEOUT_MS="${EUROEVAL_BATCH_TIMEOUT_MS}" \
  EUROEVAL_LANGUAGES="${EUROEVAL_LANGUAGES}" \
  EUROEVAL_DATASETS="${euroeval_datasets:-${EUROEVAL_DATASETS}}" \
  EUROEVAL_TASKS="${EUROEVAL_TASKS}" \
  EUROEVAL_FEW_SHOT="${EUROEVAL_FEW_SHOT}" \
  EUROEVAL_NUM_ITERATIONS="${EUROEVAL_NUM_ITERATIONS}" \
  EUROEVAL_GENERATIVE_TYPE="${EUROEVAL_GENERATIVE_TYPE}" \
  EUROEVAL_BIN="${EUROEVAL_BIN}" \
  EUROEVAL_PREFIX="${EUROEVAL_PREFIX}" \
  MODEL_PREFIX="${MODEL_PREFIX}" \
  STANDARD_BATCH_SIZE="${STANDARD_BATCH_SIZE}" \
  STANDARD_BATCH_SIZE_GSM8K="${STANDARD_BATCH_SIZE_GSM8K:-}" \
  STANDARD_BATCH_SIZE_MATH="${STANDARD_BATCH_SIZE_MATH:-}" \
  STANDARD_BATCH_SIZE_DROP="${STANDARD_BATCH_SIZE_DROP:-}" \
  DFM_BATCH_SIZE="${DFM_BATCH_SIZE}" \
  DFM_BATCH_SIZE_GOVREPORT="${DFM_BATCH_SIZE_GOVREPORT:-}" \
  DFM_BATCH_SIZE_NORDJYLLANDNEWS="${DFM_BATCH_SIZE_NORDJYLLANDNEWS:-}" \
  DFM_BATCH_SIZE_WMT24PP_EN_DA="${DFM_BATCH_SIZE_WMT24PP_EN_DA:-}" \
  DFM_BATCH_SIZE_HUMANEVAL="${DFM_BATCH_SIZE_HUMANEVAL:-}" \
  DFM_BATCH_SIZE_GENERATIVE_TALEMAADER="${DFM_BATCH_SIZE_GENERATIVE_TALEMAADER:-}" \
  IFEVAL_BATCH_SIZE="${IFEVAL_BATCH_SIZE}" \
  DFM_BATCH_TIMEOUT_MS="${DFM_BATCH_TIMEOUT_MS}" \
  IFEVAL_BATCH_TIMEOUT_MS="${IFEVAL_BATCH_TIMEOUT_MS}" \
  RESUME_EXISTING_QUEUE=1 \
  JOB_FILE_OVERRIDE="${child_job_file}" \
  STATUS_FILE_OVERRIDE="${child_status_file}" \
  LOCK_FILE_OVERRIDE="${child_lock_file}" \
  WORKER_LOG_DIR="${child_worker_log_dir}" \
  SKIP_FINAL_MERGE=1 \
  STARTUP_STAGGER_SECONDS=0 \
  MAX_RETRIES="${MAX_RETRIES}" \
  NO_EMA="${NO_EMA}" \
  WANDB_SYNC="${WANDB_SYNC}" \
  WANDB_PROJECT="${WANDB_PROJECT}" \
  WANDB_RUN_ID="${WANDB_RUN_ID}" \
  WANDB_RUN_NAME="${WANDB_RUN_NAME}" \
  LITE_EVAL="${LITE_EVAL}" \
  LITE_SHARD_INDEX="${LITE_SHARD_INDEX}" \
  EVAL_PREFIX="${EVAL_PREFIX}" \
  DFM_EVAL_PREFIX="${DFM_EVAL_PREFIX}" \
  PYTHON_BIN="${PYTHON_BIN}" \
  scripts/schedule_checkpoint_evals.sh > "${child_worker_log_dir}/scheduler.log" 2>&1
  local status="$?"
  set -e
  log_status "END ${ckpt_tag} ${kind} ${task} shard_${shard}_of_${shards} gpu_${gpu} status_${status}"
  if [[ "${status}" == "0" ]]; then
    maybe_merge_task "${ckpt_tag}" "${eval_epoch}" "${kind}" "${task}" "${shard}" "${shards}" "${log_root}" "${dfm_log_root}" || true
  fi
  return "${status}"
}

standard_shard_ready() {
  local log="$1" task="$2"
  [[ -f "${log}" ]] || return 1
  grep -q "EVALUATION SUMMARY" "${log}" || return 1
  grep -q -- "--- ${task} ---" "${log}" || return 1
}

dfm_shard_ready() {
  local dir="$1"
  compgen -G "${dir}/inspect/*.eval" >/dev/null || return 1
}

maybe_merge_task() {
  local ckpt_tag="$1" eval_epoch="$2" kind="$3" task="$4" shard="$5" shards="$6" log_root="$7" dfm_log_root="$8"
  local merge_key marker lock label
  local wandb_args=()
  if [[ "${WANDB_SYNC}" == "1" ]]; then
    wandb_args=(
      --log-wandb
      --project "${WANDB_PROJECT}"
      --run-id "${WANDB_RUN_ID}"
      --run-name "${WANDB_RUN_NAME}"
    )
  fi
  if [[ "${kind}" == "dfm_ifeval" ]]; then
    merge_key="dfm_ifeval"
  else
    merge_key="${kind}_${task}"
  fi
  label="$(epoch_label "${eval_epoch}")"
  marker="${log_root}/incremental_merge_${merge_key}_epoch_${label}.done"
  lock="${log_root}/incremental_merge_${merge_key}.lock"
  {
    flock -x 9
    [[ -f "${marker}" ]] && return 0

    local expected_shards=()
    local expected_shard
    if [[ "${LITE_EVAL}" == "1" ]]; then
      expected_shards=("${LITE_SHARD_INDEX}")
    else
      for ((expected_shard = 0; expected_shard < shards; expected_shard++)); do
        expected_shards+=("${expected_shard}")
      done
    fi

    local paths=()
    if [[ "${kind}" == "standard" ]]; then
      for expected_shard in "${expected_shards[@]}"; do
        local standard_log="${log_root}/standard_shards/${task}/${task}_shard_${expected_shard}_of_${shards}.log"
        standard_shard_ready "${standard_log}" "${task}" || return 0
        paths+=("${standard_log}")
      done
      log_status "INCREMENTAL_MERGE_START ${ckpt_tag} ${kind} ${task}"
      "${PYTHON_BIN}" scripts/merge_standard_eval_shards.py \
        "${paths[@]}" \
        --benchmark "${task}" \
        --epoch "${eval_epoch}" \
        --output "${log_root}/standard_shards/${task}/merged_metrics.json" \
        --prefix "${EVAL_PREFIX}" \
        "${wandb_args[@]}" \
        > "${log_root}/standard_shards/${task}/incremental_merge_and_wandb_sync.log" 2>&1 || {
          log_status "INCREMENTAL_MERGE_FAILED ${ckpt_tag} ${kind} ${task}"
          return 0
        }
    elif [[ "${kind}" == "dfm_ifeval" ]]; then
      for expected_shard in "${expected_shards[@]}"; do
        local ifeval_dir="${dfm_log_root}/ifeval_shard_${expected_shard}/${ckpt_tag}"
        dfm_shard_ready "${ifeval_dir}" || return 0
        paths+=("${ifeval_dir}/inspect"/*.eval)
      done
      log_status "INCREMENTAL_MERGE_START ${ckpt_tag} ${kind} ifeval-da"
      "${PYTHON_BIN}" scripts/merge_ifeval_da_shards.py \
        "${paths[@]}" \
        --epoch "${eval_epoch}" \
        --output "${dfm_log_root}/merged_ifeval_da_metrics.json" \
        --prefix "${DFM_EVAL_PREFIX}" \
        "${wandb_args[@]}" \
        > "${dfm_log_root}/merge_ifeval_da_wandb.log" 2>&1 || {
          log_status "INCREMENTAL_MERGE_FAILED ${ckpt_tag} ${kind} ifeval-da"
          return 0
        }
    elif [[ "${kind}" == "dfm" ]]; then
      for expected_shard in "${expected_shards[@]}"; do
        local dfm_dir="${dfm_log_root}/${task}/shard_${expected_shard}_of_${shards}/${ckpt_tag}"
        dfm_shard_ready "${dfm_dir}" || return 0
        paths+=("${dfm_dir}/inspect"/*.eval)
      done
      log_status "INCREMENTAL_MERGE_START ${ckpt_tag} ${kind} ${task}"
      "${PYTHON_BIN}" scripts/merge_dfm_eval_shards.py \
        "${paths[@]}" \
        --task "${task}" \
        --epoch "${eval_epoch}" \
        --output "${dfm_log_root}/${task}/merged_metrics.json" \
        --prefix "${DFM_EVAL_PREFIX}" \
        "${wandb_args[@]}" \
        > "${dfm_log_root}/${task}/incremental_merge_and_wandb_sync.log" 2>&1 || {
          log_status "INCREMENTAL_MERGE_FAILED ${ckpt_tag} ${kind} ${task}"
          return 0
        }
    else
      return 0
    fi
    date --iso-8601=seconds > "${marker}"
    log_status "INCREMENTAL_MERGE_END ${ckpt_tag} ${kind} ${task}"
  } 9>"${lock}"
}

worker() {
  local gpu="$1" worker_id="$2" line status
  while true; do
    line="$(pop_ready_job)"
    if [[ -z "${line}" ]]; then
      if [[ ! -s "${JOB_FILE}" ]]; then
        return 0
      fi
      sleep "${CHECKPOINT_POLL_SECONDS}"
      continue
    fi
    status=0
    run_one_job "${gpu}" "${worker_id}" "${line}" || status="$?"
    if [[ "${status}" != "0" ]]; then
      return "${status}"
    fi
  done
}

if [[ "${RESUME_EXISTING_QUEUE}" != "1" ]]; then
  for index in "${!CKPT_TAGS_ARR[@]}"; do
    enqueue_checkpoint "${CKPT_TAGS_ARR[$index]}" "${EVAL_EPOCHS_ARR[$index]}"
  done
  log_status "QUEUED $(wc -l < "${JOB_FILE}") jobs for ${#CKPT_TAGS_ARR[@]} checkpoints"
else
  log_status "RESUME_QUEUED $(wc -l < "${JOB_FILE}") jobs"
fi

if [[ "${DRY_RUN}" == "1" ]]; then
  cat "${JOB_FILE}"
  exit 0
fi

pids=()
for i in "${!GPUS_ARR[@]}"; do
  gpu="${GPUS_ARR[$i]}"
  worker "${gpu}" "${i}" > "${LOG_ROOT_BASE}/workers/worker_${i}_gpu_${gpu}.log" 2>&1 &
  pids+=("$!")
done
log_status "WORKERS ${pids[*]}"

final_status=0
for pid in "${pids[@]}"; do
  if ! wait "${pid}"; then
    final_status=1
  fi
done

if [[ "${final_status}" == "0" && "${SKIP_FINAL_MERGE}" != "1" ]]; then
  for index in "${!CKPT_TAGS_ARR[@]}"; do
    ckpt_tag="${CKPT_TAGS_ARR[$index]}"
    eval_epoch="${EVAL_EPOCHS_ARR[$index]}"
    log_status "FINAL_MERGE_START ${ckpt_tag}"
    CKPT_TAG="${ckpt_tag}" \
    EVAL_EPOCH="${eval_epoch}" \
    CKPT_PATH="${CKPT_PATH}" \
    PYTHON_BIN="${PYTHON_BIN}" \
    LOG_ROOT="${LOG_ROOT_BASE}/${ckpt_tag}" \
    DFM_LOG_ROOT="${DFM_LOG_ROOT_BASE}/${ckpt_tag}" \
    FINAL_MERGE_ONLY=1 \
    NO_EMA="${NO_EMA}" \
    WANDB_SYNC="${WANDB_SYNC}" \
    LITE_EVAL="${LITE_EVAL}" \
    LITE_SHARD_INDEX="${LITE_SHARD_INDEX}" \
    scripts/schedule_checkpoint_evals.sh \
      > "${LOG_ROOT_BASE}/${ckpt_tag}/final_merge.log" 2>&1 || final_status=1
    log_status "FINAL_MERGE_END ${ckpt_tag} status_${final_status}"
  done
fi

log_status "DONE status_${final_status}"
exit "${final_status}"
