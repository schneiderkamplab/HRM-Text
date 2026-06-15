#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

GPUS_CSV="${GPUS:-4,5}"
POLL_SECONDS="${POLL_SECONDS:-15}"
PORT_BASE="${PORT_BASE:-9950}"
MAX_CONTEXT="${MAX_CONTEXT:-4096}"
EUROEVAL_BATCH_SIZE="${EUROEVAL_BATCH_SIZE:-32}"
EUROEVAL_MAX_CONCURRENT_CALLS="${EUROEVAL_MAX_CONCURRENT_CALLS:-32}"
EUROEVAL_BATCH_TIMEOUT_MS="${EUROEVAL_BATCH_TIMEOUT_MS:-25}"
EUROEVAL_BIN="${EUROEVAL_BIN:-${REPO_ROOT}/scripts/euroeval_api_no_flash_attn_guard.py}"
PYTHON_BIN="${PYTHON_BIN:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
HOST="${HOST:-127.0.0.1}"
QUEUE_ROOT="${QUEUE_ROOT:-logs/euroeval/priority_valeu_da_then_dfm4_$(date +%Y%m%dT%H%M%S)}"
STATUS_FILE="${QUEUE_ROOT}/status.tsv"

mkdir -p "${QUEUE_ROOT}/launcher"
: > "${STATUS_FILE}"

IFS=',' read -r -a GPUS_ARR <<< "${GPUS_CSV}"

jobs=(
  "orig_epoch2_valeu_da	2	checkpoints/original_sapient/L	epoch_2	2	hrm-original-sapient-L	logs/euroeval/original_sapient_L/epoch_2_valeu_da_rerun	Original Plus Mixed Danish Instruction Rich L	origLclean	original-sapient-L-clean-history	valeu-da	--verbose	0"
  "dfm4_XL	1	checkpoints/dfm4/XL-ddp	epoch_1	1	hrm-dfm4-XL-ddp	logs/euroeval/dfm4_XL_ddp_epoch_checkpoints	Original Plus Mixed Danish Instruction Rich L	dfm4xlddpcleanfixed2	dfm4-XL-ddp clean corrected history v2	-	-	1"
  "dfm4_XL	2	checkpoints/dfm4/XL-ddp	epoch_2	2	hrm-dfm4-XL-ddp	logs/euroeval/dfm4_XL_ddp_epoch_checkpoints	Original Plus Mixed Danish Instruction Rich L	dfm4xlddpcleanfixed2	dfm4-XL-ddp clean corrected history v2	-	-	1"
)

if [[ "${SKIP_VAL_RERUN:-0}" == "1" ]]; then
  jobs=("${jobs[@]:1}")
fi

log_status() {
  printf "%s\t%s\n" "$(date --iso-8601=seconds)" "$*" | tee -a "${STATUS_FILE}"
}

gpu_has_compute_process() {
  local gpu="$1"
  [[ -n "$(nvidia-smi --id="${gpu}" --query-compute-apps=pid --format=csv,noheader,nounits 2>/dev/null | tr -d '[:space:]')" ]]
}

checkpoint_ready() {
  local ckpt_path="$1" ckpt_tag="$2"
  if [[ ! -d "${ckpt_path}/fsdp2_${ckpt_tag}" && ! -f "${ckpt_path}/unsharded_${ckpt_tag}.pt" ]]; then
    return 1
  fi
  for rank in 0 1 2 3 4 5 6 7; do
    [[ -f "${ckpt_path}/carry_${ckpt_tag}.${rank}.pt" ]] || return 1
  done
}

launch_job() {
  local gpu="$1" port="$2" job_index="$3" job_line="$4"
  local family epoch ckpt_path ckpt_tag eval_epoch model_prefix log_base wandb_project wandb_run_id wandb_run_name datasets extra_args wandb_sync
  IFS=$'\t' read -r family epoch ckpt_path ckpt_tag eval_epoch model_prefix log_base wandb_project wandb_run_id wandb_run_name datasets extra_args wandb_sync <<< "${job_line}"
  [[ "${datasets}" == "-" ]] && datasets=""
  [[ "${extra_args}" == "-" ]] && extra_args=""
  local run_dir="${log_base}"
  if [[ "${family}" != "orig_epoch2_valeu_da" ]]; then
    run_dir="${log_base}/${ckpt_tag}"
  fi
  local launcher_log="${QUEUE_ROOT}/launcher/${family}_${ckpt_tag}_gpu_${gpu}.log"
  mkdir -p "${run_dir}" "$(dirname "${launcher_log}")"

  if ! checkpoint_ready "${ckpt_path}" "${ckpt_tag}"; then
    log_status "SKIP job_${job_index} ${family}/${ckpt_tag} checkpoint_not_ready path=${ckpt_path}"
    return 2
  fi

  log_status "START job_${job_index} ${family}/${ckpt_tag} gpu_${gpu} port_${port} log_${run_dir}"
  (
    CKPT_PATH="${ckpt_path}" \
    CKPT_TAG="${ckpt_tag}" \
    EVAL_EPOCH="${eval_epoch}" \
    GPU="${gpu}" \
    HOST="${HOST}" \
    PORT="${port}" \
    MODEL_PREFIX="${model_prefix}" \
    MAX_CONTEXT="${MAX_CONTEXT}" \
    EUROEVAL_LOG_ROOT="${run_dir}" \
    EUROEVAL_BIN="${EUROEVAL_BIN}" \
    EUROEVAL_BATCH_SIZE="${EUROEVAL_BATCH_SIZE}" \
    EUROEVAL_MAX_CONCURRENT_CALLS="${EUROEVAL_MAX_CONCURRENT_CALLS}" \
    EUROEVAL_BATCH_TIMEOUT_MS="${EUROEVAL_BATCH_TIMEOUT_MS}" \
    EUROEVAL_LANGUAGES="da,en" \
    EUROEVAL_DATASETS="${datasets}" \
    EUROEVAL_EXTRA_ARGS="${extra_args}" \
    WANDB_SYNC="${wandb_sync}" \
    WANDB_PROJECT="${wandb_project}" \
    WANDB_RUN_ID="${wandb_run_id}" \
    WANDB_RUN_NAME="${wandb_run_name}" \
    PYTHON_BIN="${PYTHON_BIN}" \
    scripts/run_euroeval_on_checkpoint.sh
  ) > "${launcher_log}" 2>&1 &
  echo "$!"
}

declare -A running_pid_by_gpu=()
declare -A running_desc_by_gpu=()
declare -A running_job_by_gpu=()
next_job=0
next_port=$((PORT_BASE + 1))
overall_status=0

log_status "QUEUE_START jobs_${#jobs[@]} gpus_${GPUS_CSV} batch_${EUROEVAL_BATCH_SIZE} concurrent_${EUROEVAL_MAX_CONCURRENT_CALLS}"

while (( next_job < ${#jobs[@]} || ${#running_pid_by_gpu[@]} > 0 )); do
  for gpu in "${GPUS_ARR[@]}"; do
    pid="${running_pid_by_gpu[$gpu]:-}"
    if [[ -n "${pid}" ]] && ! kill -0 "${pid}" 2>/dev/null; then
      if wait "${pid}"; then
        log_status "END ${running_job_by_gpu[$gpu]} ${running_desc_by_gpu[$gpu]} gpu_${gpu} status_0"
      else
        status="$?"
        log_status "END ${running_job_by_gpu[$gpu]} ${running_desc_by_gpu[$gpu]} gpu_${gpu} status_${status}"
        overall_status=1
      fi
      unset "running_pid_by_gpu[$gpu]" "running_desc_by_gpu[$gpu]" "running_job_by_gpu[$gpu]"
    fi
  done

  for gpu in "${GPUS_ARR[@]}"; do
    if (( next_job >= ${#jobs[@]} )); then
      break
    fi
    if [[ -n "${running_pid_by_gpu[$gpu]:-}" ]]; then
      continue
    fi
    if gpu_has_compute_process "${gpu}"; then
      continue
    fi
    job_line="${jobs[$next_job]}"
    IFS=$'\t' read -r family _ ckpt_path ckpt_tag _ <<< "${job_line}"
    launch_output="$(launch_job "${gpu}" "${next_port}" "${next_job}" "${job_line}")" || {
      status="$?"
      if [[ "${status}" == "2" ]]; then
        next_job=$((next_job + 1))
        next_port=$((next_port + 1))
        continue
      fi
      exit "${status}"
    }
    pid="$(printf "%s\n" "${launch_output}" | tail -n 1)"
    running_pid_by_gpu["$gpu"]="${pid}"
    running_desc_by_gpu["$gpu"]="${family}/${ckpt_tag}"
    running_job_by_gpu["$gpu"]="job_${next_job}"
    next_job=$((next_job + 1))
    next_port=$((next_port + 1))
  done

  sleep "${POLL_SECONDS}"
done

log_status "QUEUE_END status_${overall_status}"
exit "${overall_status}"
