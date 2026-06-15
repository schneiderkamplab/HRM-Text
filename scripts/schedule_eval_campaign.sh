#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

CAMPAIGN_PLAN="${CAMPAIGN_PLAN:?Set CAMPAIGN_PLAN to a TSV file with eval variants.}"
CAMPAIGN_ROOT="${CAMPAIGN_ROOT:-logs/eval/campaign_$(date +%Y%m%dT%H%M%S)}"
CKPT_PATH="${CKPT_PATH:-checkpoints/dfm4/XL-ddp}"
GPUS_CSV="${GPUS:-0,1,2,3,4,5,6,7}"
QUEUE_ORDER="${QUEUE_ORDER:-heavy_first}"
LITE_SHARD_INDEX="${LITE_SHARD_INDEX:-0}"
MAX_RETRIES="${MAX_RETRIES:-5}"
WANDB_SYNC="${WANDB_SYNC:-1}"
DRY_RUN="${DRY_RUN:-0}"
PYTHON_BIN="${PYTHON_BIN:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python"
fi

IFS=',' read -r -a GPUS_ARR <<< "${GPUS_CSV}"
mkdir -p "${CAMPAIGN_ROOT}/workers" "${CAMPAIGN_ROOT}/jobfiles"
JOB_FILE="${CAMPAIGN_ROOT}/jobs.tsv"
STATUS_FILE="${CAMPAIGN_ROOT}/status.tsv"
LOCK_FILE="${CAMPAIGN_ROOT}/jobs.lock"
VARIANTS_FILE="${CAMPAIGN_ROOT}/variants.tsv"
TELEMETRY_FILE="${CAMPAIGN_ROOT}/eval_attempts.tsv"
TELEMETRY_LOCK_FILE="${CAMPAIGN_ROOT}/eval_attempts.lock"
: > "${JOB_FILE}"
: > "${STATUS_FILE}"
: > "${VARIANTS_FILE}"

log_status() {
  printf "%s\t%s\n" "$(date --iso-8601=seconds)" "$*" | tee -a "${STATUS_FILE}"
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
  local variant_id="$1" ckpt_tag="$2" eval_epoch="$3" lite_eval="$4" no_ema="$5"
  local eval_prefix="$6" dfm_eval_prefix="$7" log_root="$8" dfm_log_root="$9"
  local kind="${10}" task="${11}" shards="${12}" shard
  mkdir -p "${log_root}" "${dfm_log_root}"
  if [[ "${lite_eval}" == "1" ]]; then
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
      "${variant_id}" "${ckpt_tag}" "${eval_epoch}" "${lite_eval}" "${no_ema}" \
      "${eval_prefix}" "${dfm_eval_prefix}" "${log_root}" "${dfm_log_root}" \
      "${kind}" "${task}" "${LITE_SHARD_INDEX}" "${shards}" >> "${JOB_FILE}"
    return 0
  fi
  for ((shard = 0; shard < shards; shard++)); do
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
      "${variant_id}" "${ckpt_tag}" "${eval_epoch}" "${lite_eval}" "${no_ema}" \
      "${eval_prefix}" "${dfm_eval_prefix}" "${log_root}" "${dfm_log_root}" \
      "${kind}" "${task}" "${shard}" "${shards}" >> "${JOB_FILE}"
  done
}

enqueue_ifeval_jobs() {
  local variant_id="$1" ckpt_tag="$2" eval_epoch="$3" lite_eval="$4" no_ema="$5"
  local eval_prefix="$6" dfm_eval_prefix="$7" log_root="$8" dfm_log_root="$9"
  local shards="${DFM_IFEVAL_SHARDS:-32}" shard
  mkdir -p "${log_root}" "${dfm_log_root}"
  if [[ "${lite_eval}" == "1" ]]; then
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\tdfm_ifeval\t%s\t%s\t%s\n" \
      "${variant_id}" "${ckpt_tag}" "${eval_epoch}" "${lite_eval}" "${no_ema}" \
      "${eval_prefix}" "${dfm_eval_prefix}" "${log_root}" "${dfm_log_root}" \
      "${LITE_SHARD_INDEX}" "${LITE_SHARD_INDEX}" "${shards}" >> "${JOB_FILE}"
    return 0
  fi
  for ((shard = 0; shard < shards; shard++)); do
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\tdfm_ifeval\t%s\t%s\t%s\n" \
      "${variant_id}" "${ckpt_tag}" "${eval_epoch}" "${lite_eval}" "${no_ema}" \
      "${eval_prefix}" "${dfm_eval_prefix}" "${log_root}" "${dfm_log_root}" \
      "${shard}" "${shard}" "${shards}" >> "${JOB_FILE}"
  done
}

enqueue_variant() {
  local variant_id="$1" ckpt_tag="$2" eval_epoch="$3" lite_eval="$4" no_ema="$5"
  local eval_prefix="$6" dfm_eval_prefix="$7" log_root="$8" dfm_log_root="$9"
  local standard_tasks dfm_tasks enqueue_ifeval_first task shards
  if [[ "${QUEUE_ORDER}" == "heavy_first" ]]; then
    standard_tasks=(MATH GSM8k DROP MMLU HellaSwag ARC Winogrande BoolQ)
    dfm_tasks=(govreport wmt24pp_en_da generative_talemaader nordjyllandnews humaneval gec_dala multi_wiki_qa danish_citizen_tests dala piqa)
    enqueue_ifeval_first=1
  else
    standard_tasks=(GSM8k DROP MMLU ARC HellaSwag Winogrande BoolQ MATH)
    dfm_tasks=(danish_citizen_tests dala gec_dala wmt24pp_en_da multi_wiki_qa piqa generative_talemaader govreport nordjyllandnews humaneval)
    enqueue_ifeval_first=0
  fi
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
    "${variant_id}" "${ckpt_tag}" "${eval_epoch}" "${lite_eval}" "${no_ema}" \
    "${eval_prefix}" "${dfm_eval_prefix}" "${log_root}" "${dfm_log_root}" >> "${VARIANTS_FILE}"
  [[ "${enqueue_ifeval_first}" == "1" ]] && enqueue_ifeval_jobs "$@"
  for task in "${standard_tasks[@]}"; do
    shards="$(standard_shards_for_task "${task}")"
    enqueue_sharded_jobs "$@" standard "${task}" "${shards}"
  done
  for task in "${dfm_tasks[@]}"; do
    shards="$(dfm_shards_for_task "${task}")"
    enqueue_sharded_jobs "$@" dfm "${task}" "${shards}"
  done
  [[ "${enqueue_ifeval_first}" == "0" ]] && enqueue_ifeval_jobs "$@"
  return 0
}

pop_ready_job() {
  local line="" rest="" candidate ckpt_tag
  {
    flock -x 9
    while IFS= read -r candidate; do
      IFS=$'\t' read -r _ ckpt_tag _ <<< "${candidate}"
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
  local variant_id ckpt_tag eval_epoch lite_eval no_ema eval_prefix dfm_eval_prefix log_root dfm_log_root kind task shard shards
  IFS=$'\t' read -r variant_id ckpt_tag eval_epoch lite_eval no_ema eval_prefix dfm_eval_prefix log_root dfm_log_root kind task shard shards <<< "${line}"
  local job_id="${worker_id}_$(date +%s%N)"
  local job_dir="${CAMPAIGN_ROOT}/jobfiles/${job_id}"
  local child_job_file="${job_dir}/jobs.tsv"
  local child_status_file="${job_dir}/status.tsv"
  local child_lock_file="${job_dir}/jobs.lock"
  local worker_log_dir="${CAMPAIGN_ROOT}/workers/${job_id}"
  mkdir -p "${job_dir}" "${worker_log_dir}" "${log_root}" "${dfm_log_root}"
  if [[ "${kind}" == "dfm_ifeval" ]]; then
    printf "dfm_ifeval\t%s\n" "${shard}" > "${child_job_file}"
  else
    printf "%s\t%s\t%s\t%s\n" "${kind}" "${task}" "${shard}" "${shards}" > "${child_job_file}"
  fi
  log_status "START ${variant_id} ${ckpt_tag} lite_${lite_eval} noema_${no_ema} ${kind} ${task} shard_${shard}_of_${shards} gpu_${gpu}"
  set +e
  CKPT_TAG="${ckpt_tag}" \
  EVAL_EPOCH="${eval_epoch}" \
  CKPT_PATH="${CKPT_PATH}" \
  GPUS="${gpu}" \
  LOG_ROOT="${log_root}" \
  DFM_LOG_ROOT="${dfm_log_root}" \
  RESUME_EXISTING_QUEUE=1 \
  JOB_FILE_OVERRIDE="${child_job_file}" \
  STATUS_FILE_OVERRIDE="${child_status_file}" \
  LOCK_FILE_OVERRIDE="${child_lock_file}" \
  WORKER_LOG_DIR="${worker_log_dir}" \
  TELEMETRY_FILE_OVERRIDE="${TELEMETRY_FILE}" \
  TELEMETRY_LOCK_FILE_OVERRIDE="${TELEMETRY_LOCK_FILE}" \
  SKIP_FINAL_MERGE=1 \
  STARTUP_STAGGER_SECONDS=0 \
  MAX_RETRIES="${MAX_RETRIES}" \
  NO_EMA="${no_ema}" \
  WANDB_SYNC=0 \
  LITE_EVAL="${lite_eval}" \
  LITE_SHARD_INDEX="${LITE_SHARD_INDEX}" \
  EVAL_PREFIX="${eval_prefix}" \
  DFM_EVAL_PREFIX="${dfm_eval_prefix}" \
  PYTHON_BIN="${PYTHON_BIN}" \
  scripts/schedule_checkpoint_evals.sh > "${worker_log_dir}/scheduler.log" 2>&1
  local status="$?"
  set -e
  log_status "END ${variant_id} ${ckpt_tag} lite_${lite_eval} noema_${no_ema} ${kind} ${task} shard_${shard}_of_${shards} gpu_${gpu} status_${status}"
  return "${status}"
}

worker() {
  local gpu="$1" worker_id="$2" line status
  while true; do
    line="$(pop_ready_job)"
    if [[ -z "${line}" ]]; then
      [[ ! -s "${JOB_FILE}" ]] && return 0
      sleep 30
      continue
    fi
    status=0
    run_one_job "${gpu}" "${worker_id}" "${line}" || status="$?"
    [[ "${status}" != "0" ]] && return "${status}"
  done
}

final_merge_variant() {
  local variant_id="$1" ckpt_tag="$2" eval_epoch="$3" lite_eval="$4" no_ema="$5"
  local eval_prefix="$6" dfm_eval_prefix="$7" log_root="$8" dfm_log_root="$9"
  log_status "FINAL_MERGE_START ${variant_id} ${ckpt_tag}"
  CKPT_TAG="${ckpt_tag}" \
  EVAL_EPOCH="${eval_epoch}" \
  CKPT_PATH="${CKPT_PATH}" \
  PYTHON_BIN="${PYTHON_BIN}" \
  LOG_ROOT="${log_root}" \
  DFM_LOG_ROOT="${dfm_log_root}" \
  FINAL_MERGE_ONLY=1 \
  NO_EMA="${no_ema}" \
  WANDB_SYNC="${WANDB_SYNC}" \
  LITE_EVAL="${lite_eval}" \
  LITE_SHARD_INDEX="${LITE_SHARD_INDEX}" \
  EVAL_PREFIX="${eval_prefix}" \
  DFM_EVAL_PREFIX="${dfm_eval_prefix}" \
  scripts/schedule_checkpoint_evals.sh > "${log_root}/final_merge.log" 2>&1
  log_status "FINAL_MERGE_END ${variant_id} ${ckpt_tag}"
}

while IFS=$'\t' read -r variant_id ckpt_tag eval_epoch lite_eval no_ema eval_prefix dfm_eval_prefix log_root dfm_log_root; do
  [[ -z "${variant_id}" || "${variant_id}" == \#* ]] && continue
  enqueue_variant "${variant_id}" "${ckpt_tag}" "${eval_epoch}" "${lite_eval}" "${no_ema}" "${eval_prefix}" "${dfm_eval_prefix}" "${log_root}" "${dfm_log_root}"
done < "${CAMPAIGN_PLAN}"

log_status "QUEUED $(wc -l < "${JOB_FILE}") jobs for $(wc -l < "${VARIANTS_FILE}") variants"

if [[ "${DRY_RUN}" == "1" ]]; then
  cat "${JOB_FILE}"
  exit 0
fi

pids=()
for i in "${!GPUS_ARR[@]}"; do
  gpu="${GPUS_ARR[$i]}"
  worker "${gpu}" "${i}" > "${CAMPAIGN_ROOT}/workers/worker_${i}_gpu_${gpu}.log" 2>&1 &
  pids+=("$!")
done
log_status "WORKERS ${pids[*]}"

final_status=0
for pid in "${pids[@]}"; do
  if ! wait "${pid}"; then
    final_status=1
  fi
done

if [[ "${final_status}" == "0" ]]; then
  while IFS=$'\t' read -r variant_id ckpt_tag eval_epoch lite_eval no_ema eval_prefix dfm_eval_prefix log_root dfm_log_root; do
    [[ -z "${variant_id}" || "${variant_id}" == \#* ]] && continue
    final_merge_variant "${variant_id}" "${ckpt_tag}" "${eval_epoch}" "${lite_eval}" "${no_ema}" "${eval_prefix}" "${dfm_eval_prefix}" "${log_root}" "${dfm_log_root}" || final_status=1
  done < "${VARIANTS_FILE}"
fi

log_status "DONE status_${final_status}"
exit "${final_status}"
