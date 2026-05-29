#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CKPT_PATH="${CKPT_PATH:-checkpoints/original_plus_mixed_danish_instruction_rich/L}"
LOG_DIR="${LOG_DIR:-logs/eval/original_plus_mixed_danish_instruction_rich_L_standard}"
GPUS_CSV="${GPUS:-0,1,2,3,4,5,6,7}"
CONFIG="${CONFIG:-evaluation/config/hrm_benchmarking.yaml}"
EPOCHS_CSV="${EPOCHS:-1,2}"
BENCHMARKS_CSV="${BENCHMARKS:-GSM8k,MATH,DROP,MMLU,ARC,HellaSwag,Winogrande,BoolQ}"
STARTUP_STAGGER_SECONDS="${STARTUP_STAGGER_SECONDS:-20}"
EXTRA_ARGS=("$@")

IFS=',' read -r -a GPUS_ARR <<< "${GPUS_CSV}"
IFS=',' read -r -a EPOCHS_ARR <<< "${EPOCHS_CSV}"
IFS=',' read -r -a BENCHMARKS_ARR <<< "${BENCHMARKS_CSV}"

cd "${REPO_ROOT}"
mkdir -p "${LOG_DIR}"

job_file="${LOG_DIR}/jobs.tsv"
status_file="${LOG_DIR}/status.tsv"
worker_log_dir="${LOG_DIR}/workers"
mkdir -p "${worker_log_dir}"
: > "${job_file}"
: > "${status_file}"

for epoch in "${EPOCHS_ARR[@]}"; do
  for benchmark in "${BENCHMARKS_ARR[@]}"; do
    printf "%s\t%s\n" "${epoch}" "${benchmark}" >> "${job_file}"
  done
done

total_jobs="$(wc -l < "${job_file}")"
echo "Queued ${total_jobs} standard eval job(s) in ${job_file}"

worker() {
  local gpu="$1"
  local worker_id="$2"
  local line epoch benchmark run_dir log status

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
      } 9>"${LOG_DIR}/jobs.lock"
    )" || break

    [[ -n "${line}" ]] || break
    IFS=$'\t' read -r epoch benchmark <<< "${line}"
    run_dir="${LOG_DIR}/epoch_${epoch}"
    mkdir -p "${run_dir}"
    log="${run_dir}/${benchmark}.log"

    printf "%s\tSTART\tepoch_%s\t%s\tgpu_%s\n" "$(date --iso-8601=seconds)" "${epoch}" "${benchmark}" "${gpu}" | tee -a "${status_file}"
    status=0
    set +e
    (
      set -euo pipefail
      export CUDA_VISIBLE_DEVICES="${gpu}"
      export PYTHONUNBUFFERED=1
      python -u -m evaluation.main \
        config="${CONFIG}" \
        ckpt_path="${CKPT_PATH}" \
        ckpt_epoch="${epoch}" \
        "run_only=[${benchmark}]" \
        "${EXTRA_ARGS[@]}"
    ) > "${log}" 2>&1 || status=$?
    set -e
    printf "%s\tEND\tepoch_%s\t%s\tgpu_%s\tstatus_%s\n" "$(date --iso-8601=seconds)" "${epoch}" "${benchmark}" "${gpu}" "${status}" | tee -a "${status_file}"
  done
}

pids=()
for i in "${!GPUS_ARR[@]}"; do
  gpu="${GPUS_ARR[$i]}"
  worker "${gpu}" "${i}" > "${worker_log_dir}/worker_${i}_gpu_${gpu}.log" 2>&1 &
  pids+=("$!")
done

echo "Launched worker PIDs: ${pids[*]}"

final_status=0
for pid in "${pids[@]}"; do
  if ! wait "${pid}"; then
    final_status=1
  fi
done

exit "${final_status}"
