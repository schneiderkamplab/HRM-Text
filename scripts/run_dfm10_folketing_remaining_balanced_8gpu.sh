#!/usr/bin/env bash
set -euo pipefail

# Claim each GPU only after it becomes fully free, then audit one balanced
# shard of the rows missing from the original Folketing campaign.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

AUDIT_ROOT="${AUDIT_ROOT:-logs/dfm10_folketing_audit_8gpu_vllm}"
RUN_ROOT="$AUDIT_ROOT/balanced_remaining"
MODEL_PATH="${MODEL_PATH:-/work/dfm/jacobwashere/brainsurgery/models/google/gemma-4-E4B-it}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-openai/gemma-4-e4b-judge}"
VLLM_PYTHON="${VLLM_PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
CLIENT_PYTHON="${CLIENT_PYTHON:-/home/ucloud/miniforge3/envs/hrm-cu132/bin/python}"
CHAT_TEMPLATE="${CHAT_TEMPLATE:-$ROOT/evaluation/chat_templates/gemma4_native_chat.jinja}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"
MIN_FREE_MIB="${MIN_FREE_MIB:-170000}"
CONCURRENCY="${CONCURRENCY:-64}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-64}"
PORT_BASE="${PORT_BASE:-8300}"
POLL_SECONDS="${POLL_SECONDS:-30}"
MAX_CAMPAIGN_ATTEMPTS="${MAX_CAMPAIGN_ATTEMPTS:-3}"

mkdir -p "$RUN_ROOT"/{workers,servers,watchers,pids,cache,retryable_errors,locks}
exec > >(tee -a "$RUN_ROOT/launcher.log") 2>&1

if [[ ! -s "$RUN_ROOT/completed_ids.txt" ]]; then
  echo "Missing $RUN_ROOT/completed_ids.txt; run prepare_dfm10_folketing_audit_resume.py prepare first" >&2
  exit 2
fi

gpu_free() {
  local gpu="$1" free
  free="$(nvidia-smi -i "$gpu" --query-gpu=memory.free --format=csv,noheader,nounits 2>/dev/null | tr -d ' ')"
  [[ "$free" =~ ^[0-9]+$ ]] && (( free >= MIN_FREE_MIB )) || return 1
  [[ -z "$(nvidia-smi -i "$gpu" --query-compute-apps=pid --format=csv,noheader,nounits 2>/dev/null | tr -d '[:space:]')" ]]
}

cleanup_shard_errors() {
  local shard="$1" audit_file archive
  audit_file="$RUN_ROOT/workers/shard_${shard}/export_judge.audit.jsonl"
  archive="$RUN_ROOT/retryable_errors/shard_${shard}.jsonl.gz"
  if [[ -s "$audit_file" ]]; then
    "$CLIENT_PYTHON" scripts/prepare_dfm10_folketing_audit_resume.py \
      clean-file "$audit_file" --archive "$archive"
  else
    printf '{"kept": 0, "retryable_removed": 0}\n'
  fi
}

seal_shard_errors() {
  local shard="$1" audit_file archive
  audit_file="$RUN_ROOT/workers/shard_${shard}/export_judge.audit.jsonl"
  archive="$RUN_ROOT/retryable_errors/shard_${shard}.jsonl.gz"
  "$CLIENT_PYTHON" scripts/prepare_dfm10_folketing_audit_resume.py \
    seal-file "$audit_file" --archive "$archive"
}

run_shard_on_gpu() {
  local gpu="$1" shard="$2" port server_pid client_status=1 attempt=0
  port="$((PORT_BASE + gpu))"
  exec 9>"$RUN_ROOT/locks/gpu${gpu}.lock"
  flock 9
  while (( client_status != 0 )); do
    echo "GPU${gpu} shard ${shard}: waiting for >=${MIN_FREE_MIB} MiB free"
    until gpu_free "$gpu"; do sleep "$POLL_SECONDS"; done
    sleep 10
    gpu_free "$gpu" || continue
    attempt="$((attempt + 1))"
    echo "GPU${gpu} shard ${shard}: claiming GPU, attempt ${attempt}"
    cleanup_shard_errors "$shard"

    CUDA_VISIBLE_DEVICES="$gpu" \
      CUDA_HOME="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}" \
      PATH="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}/bin:/home/ucloud/miniforge3/envs/audit/bin:$PATH" \
      LD_LIBRARY_PATH="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}/lib:${LD_LIBRARY_PATH:-}" \
      VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_DISABLE_VERSION_CHECK=1 \
      TORCHINDUCTOR_CACHE_DIR="$RUN_ROOT/cache/gpu${gpu}/torchinductor" \
      TRITON_CACHE_DIR="$RUN_ROOT/cache/gpu${gpu}/triton" \
      "$VLLM_PYTHON" -m vllm.entrypoints.openai.api_server \
        --model "$MODEL_PATH" --served-model-name "$SERVED_MODEL_NAME" \
        --host 127.0.0.1 --port "$port" --max-model-len 8192 \
        --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
        --max-num-seqs "$MAX_NUM_SEQS" --enforce-eager \
        --chat-template "$CHAT_TEMPLATE" \
        >"$RUN_ROOT/servers/gpu${gpu}.log" 2>&1 &
    server_pid="$!"
    echo "$server_pid" >"$RUN_ROOT/pids/server_gpu${gpu}.pid"

    ready=0
    for _ in $(seq 1 450); do
      if ! kill -0 "$server_pid" 2>/dev/null; then break; fi
      if curl -fsS "http://127.0.0.1:${port}/v1/models" >/dev/null 2>&1; then
        ready=1
        break
      fi
      sleep 2
    done
    if (( ready == 0 )); then
      echo "GPU${gpu} shard ${shard}: server failed to become ready"
      kill "$server_pid" 2>/dev/null || true
      wait "$server_pid" 2>/dev/null || true
      sleep "$POLL_SECONDS"
      continue
    fi

    set +e
    "$CLIENT_PYTHON" scripts/audit_export_datasets.py audit \
      --dataset-root data/dfm10_folketing_transform_sources/folketingets-dokumenter-denoising \
      --dataset-root data/dfm10_folketing_transform_sources/folketingets-dokumenter-error-correction \
      --dataset-root data/dfm10_folketing_transform_sources/folketingets-dokumenter-prefix-continuation \
      --dataset-root data/dfm10_folketing_transform_sources/folketingets-dokumenter-span-filling \
      --audit-root "$RUN_ROOT/workers/shard_${shard}" \
      --base-url "http://127.0.0.1:${port}/v1" --model "$SERVED_MODEL_NAME" \
      --partitions 1 --partition-index 0 \
      --secondary-partitions 8 --secondary-partition-index "$shard" \
      --skip-id-file "$RUN_ROOT/completed_ids.txt" \
      --concurrency "$CONCURRENCY" --retries 5 --max-tokens 512 \
      --json-response-format --progress-interval 100 --resume \
      >"$RUN_ROOT/workers/shard_${shard}.log" 2>&1
    client_status="$?"
    set -e
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
    rm -f "$RUN_ROOT/pids/server_gpu${gpu}.pid"
    if (( client_status == 0 )); then
      if (( attempt >= MAX_CAMPAIGN_ATTEMPTS )); then
        seal_result="$(seal_shard_errors "$shard")"
        echo "GPU${gpu} shard ${shard}: exhausted retries; ${seal_result}"
      else
        cleanup_result="$(cleanup_shard_errors "$shard")"
        echo "GPU${gpu} shard ${shard}: post-run cleanup ${cleanup_result}"
        retryable_removed="$(printf '%s\n' "$cleanup_result" | "$CLIENT_PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["retryable_removed"])')"
        if (( retryable_removed > 0 )); then
          client_status=1
        fi
      fi
    fi
    if (( client_status != 0 )); then
      echo "GPU${gpu} shard ${shard}: client failed (${client_status}); retaining valid rows and retrying later"
      sleep "$POLL_SECONDS"
    fi
  done
  echo "GPU${gpu} shard ${shard}: complete"
}

WATCHER_PIDS=()
for gpu in 0 1 2 3 4 5 6 7; do
  run_shard_on_gpu "$gpu" "$gpu" >"$RUN_ROOT/watchers/gpu${gpu}.log" 2>&1 &
  WATCHER_PIDS+=("$!")
  echo "$!" >"$RUN_ROOT/pids/watcher_gpu${gpu}.pid"
done

status=0
for index in "${!WATCHER_PIDS[@]}"; do
  if ! wait "${WATCHER_PIDS[$index]}"; then
    echo "watcher ${index} failed" >&2
    status=1
  fi
done
(( status == 0 )) || exit "$status"

"$CLIENT_PYTHON" scripts/prepare_dfm10_folketing_audit_resume.py \
  --audit-root "$AUDIT_ROOT" finalize
echo "Balanced Folketing audit complete and validated."
