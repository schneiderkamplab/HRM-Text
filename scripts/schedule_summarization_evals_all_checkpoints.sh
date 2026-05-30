#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_ROOT="${LOG_ROOT:-logs/eval/summarization_all_checkpoints_$(date +%Y%m%dT%H%M%S)}"
GPUS_CSV="${GPUS:-0,1,2,3,4,5,6,7}"
CONFIG="${CONFIG:-evaluation/config/hrm_benchmarking.yaml}"
BENCHMARKS_CSV="${BENCHMARKS:-GovReport,NordjyllandNews}"
STARTUP_STAGGER_SECONDS="${STARTUP_STAGGER_SECONDS:-10}"
EXTRA_ARGS=("$@")

ORIGINAL_CKPT_PATH="${ORIGINAL_CKPT_PATH:-checkpoints/original_sapient/L}"
ORIGINAL_EPOCHS_CSV="${ORIGINAL_EPOCHS:-1,2,3,4}"
ORIGINAL_PLUS_MIXED_CKPT_PATH="${ORIGINAL_PLUS_MIXED_CKPT_PATH:-checkpoints/original_plus_mixed_danish_instruction_rich/L}"
ORIGINAL_PLUS_MIXED_EPOCHS_CSV="${ORIGINAL_PLUS_MIXED_EPOCHS:-1,2,3}"

IFS=',' read -r -a GPUS_ARR <<< "${GPUS_CSV}"
IFS=',' read -r -a BENCHMARKS_ARR <<< "${BENCHMARKS_CSV}"
IFS=',' read -r -a ORIGINAL_EPOCHS_ARR <<< "${ORIGINAL_EPOCHS_CSV}"
IFS=',' read -r -a ORIGINAL_PLUS_MIXED_EPOCHS_ARR <<< "${ORIGINAL_PLUS_MIXED_EPOCHS_CSV}"

cd "${REPO_ROOT}"
mkdir -p "${LOG_ROOT}"

job_file="${LOG_ROOT}/jobs.tsv"
status_file="${LOG_ROOT}/status.tsv"
worker_log_dir="${LOG_ROOT}/workers"
mkdir -p "${worker_log_dir}"
: > "${job_file}"
: > "${status_file}"

enqueue_family() {
  local family="$1"
  local ckpt_path="$2"
  shift 2
  local epochs=("$@")
  local epoch benchmark

  for epoch in "${epochs[@]}"; do
    if [[ ! -d "${ckpt_path}/fsdp2_epoch_${epoch}" ]]; then
      echo "Missing checkpoint directory: ${ckpt_path}/fsdp2_epoch_${epoch}" >&2
      exit 1
    fi
    for benchmark in "${BENCHMARKS_ARR[@]}"; do
      printf "%s\t%s\t%s\t%s\n" "${family}" "${ckpt_path}" "${epoch}" "${benchmark}" >> "${job_file}"
    done
  done
}

enqueue_family "original_sapient" "${ORIGINAL_CKPT_PATH}" "${ORIGINAL_EPOCHS_ARR[@]}"
enqueue_family "original_plus_mixed_danish_instruction_rich" "${ORIGINAL_PLUS_MIXED_CKPT_PATH}" "${ORIGINAL_PLUS_MIXED_EPOCHS_ARR[@]}"

total_jobs="$(wc -l < "${job_file}")"
echo "Queued ${total_jobs} summarization eval job(s) in ${job_file}"
echo "Status: ${status_file}"

worker() {
  local gpu="$1"
  local worker_id="$2"
  local line family ckpt_path epoch benchmark run_dir log status

  sleep "$((worker_id * STARTUP_STAGGER_SECONDS))"

  while true; do
    line="$(
      {
        flock -x 9
        if [[ ! -s "${job_file}" ]]; then
          exit 0
        fi
        head -n 1 "${job_file}"
        tail -n +2 "${job_file}" > "${job_file}.tmp"
        mv "${job_file}.tmp" "${job_file}"
      } 9>"${LOG_ROOT}/jobs.lock"
    )" || break

    [[ -n "${line}" ]] || break
    IFS=$'\t' read -r family ckpt_path epoch benchmark <<< "${line}"
    run_dir="${LOG_ROOT}/${family}/epoch_${epoch}"
    mkdir -p "${run_dir}"
    log="${run_dir}/${benchmark}.log"

    printf "%s\tSTART\t%s\tepoch_%s\t%s\tgpu_%s\n" "$(date --iso-8601=seconds)" "${family}" "${epoch}" "${benchmark}" "${gpu}" | tee -a "${status_file}"
    status=0
    set +e
    (
      set -euo pipefail
      export CUDA_VISIBLE_DEVICES="${gpu}"
      export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
      export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
      export PYTHONUNBUFFERED=1
      python -u -m evaluation.main \
        config="${CONFIG}" \
        ckpt_path="${ckpt_path}" \
        ckpt_epoch="${epoch}" \
        "run_only=[${benchmark}]" \
        "${EXTRA_ARGS[@]}"
    ) > "${log}" 2>&1 || status=$?
    set -e
    printf "%s\tEND\t%s\tepoch_%s\t%s\tgpu_%s\tstatus_%s\n" "$(date --iso-8601=seconds)" "${family}" "${epoch}" "${benchmark}" "${gpu}" "${status}" | tee -a "${status_file}"
  done
}

pids=()
for i in "${!GPUS_ARR[@]}"; do
  gpu="${GPUS_ARR[$i]}"
  worker "${gpu}" "${i}" > "${worker_log_dir}/worker_${i}_gpu_${gpu}.log" 2>&1 &
  pids+=("$!")
done

printf "%s\n" "${pids[@]}" > "${LOG_ROOT}/worker_pids.txt"
echo "Launched worker PIDs: ${pids[*]}"

final_status=0
for pid in "${pids[@]}"; do
  if ! wait "${pid}"; then
    final_status=1
  fi
done

exit "${final_status}"
