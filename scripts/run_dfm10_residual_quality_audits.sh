#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CONFIG="${CONFIG:-config/dfm10_residual_quality_audits.yaml}"
RUN_ROOT="${RUN_ROOT:-logs/data_audits/dfm10_residual_quality_20260830}"
MODEL_PATH="${MODEL_PATH:-/work/dfm/.home/.cache/huggingface/hub/models--google--gemma-4-26B-A4B-it/snapshots/4d7ae4984b7db7de8f8457170b3f1a419ee76d52}"
MODEL_NAME="${MODEL_NAME:-openai/gemma-4-26b-a4b-residual-audit}"
VLLM_PYTHON="${VLLM_PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
CLIENT_PYTHON="${CLIENT_PYTHON:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
CUDA_TOOLKIT_ROOT="${CUDA_TOOLKIT_ROOT:-/home/ucloud/miniforge3/envs/audit/targets/x86_64-linux}"
PORT_BASE="${PORT_BASE:-9400}"
CONCURRENCY="${CONCURRENCY:-64}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-64}"
JUDGE_MAX_TOKENS="${JUDGE_MAX_TOKENS:-1024}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"
MIN_FREE_MIB="${MIN_FREE_MIB:-170000}"
PREPARE_RETRY_SECONDS="${PREPARE_RETRY_SECONDS:-30}"
PARTITIONS=8

mkdir -p "$RUN_ROOT"/{servers,pids,cache,stages}
exec 9>"$RUN_ROOT/runner.lock"
if ! flock -n 9; then
  echo "Another residual-audit runner holds $RUN_ROOT/runner.lock" >&2
  exit 2
fi
# The logger must not inherit the queue lock or it can outlive a hard-killed
# runner and prevent a clean resume.
exec > >(exec 9>&-; tee -a "$RUN_ROOT/runner.log") 2>&1

STATE=("$CLIENT_PYTHON" scripts/dfm10_residual_audit_queue_state.py)
"${STATE[@]}" init --config "$CONFIG" --run-root "$RUN_ROOT"

SERVER_PIDS=()
WORKER_PIDS=()
cleanup() {
  local pid
  for pid in "${WORKER_PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  for pid in "${SERVER_PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM

echo "Waiting for the active Mimir and MedQuAD campaigns to release their servers..."
"${STATE[@]}" set --run-root "$RUN_ROOT" --stage "01_sapient_packages" --status blocked \
  --message "Queued behind the active Mimir campaign and then MedQuAD English/Danish; no processes will be interrupted."
while pgrep -f '[r]un_mimir_benchmark_campaigns_8gpu.sh|[r]un_dfm10_medquad_da_8gpu.sh' >/dev/null; do
  sleep 60
done

echo "Waiting until every GPU has at least ${MIN_FREE_MIB} MiB free..."
while true; do
  ready=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | \
    awk -v minimum="$MIN_FREE_MIB" '$1 >= minimum {count++} END {print count+0}')
  [[ "$ready" == "$PARTITIONS" ]] && break
  sleep 30
done

start_server() {
  local gpu="$1"
  port=$((PORT_BASE + gpu))
  CUDA_VISIBLE_DEVICES="$gpu" \
    CUDA_HOME="$CUDA_TOOLKIT_ROOT" \
    PATH="$CUDA_TOOLKIT_ROOT/bin:/home/ucloud/miniforge3/envs/audit/bin:/home/ucloud/miniforge3/envs/audit/nvvm/bin:$PATH" \
    LD_LIBRARY_PATH="$CUDA_TOOLKIT_ROOT/lib:$CUDA_TOOLKIT_ROOT/lib64:${LD_LIBRARY_PATH:-}" \
    VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_DISABLE_VERSION_CHECK=1 \
    TORCHINDUCTOR_CACHE_DIR="$RUN_ROOT/cache/gpu${gpu}/torchinductor" \
    TRITON_CACHE_DIR="$RUN_ROOT/cache/gpu${gpu}/triton" \
    "$VLLM_PYTHON" -m vllm.entrypoints.openai.api_server \
      --model "$MODEL_PATH" --served-model-name "$MODEL_NAME" \
      --host 127.0.0.1 --port "$port" --max-model-len 8192 \
      --limit-mm-per-prompt '{"image":0,"video":0,"audio":0}' \
      --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
      --max-num-seqs "$MAX_NUM_SEQS" --enforce-eager \
      >"$RUN_ROOT/servers/gpu${gpu}.log" 2>&1 &
  local pid="$!"
  SERVER_PIDS+=("$pid")
  echo "$pid" >"$RUN_ROOT/pids/server_gpu${gpu}.pid"
}

wait_for_server() {
  local gpu="$1"
  local pid="$2"
  deadline=$((SECONDS + 900))
  until curl -fsS "http://127.0.0.1:$((PORT_BASE + gpu))/v1/models" >/dev/null 2>&1; do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "GPU${gpu} server exited during startup; see $RUN_ROOT/servers/gpu${gpu}.log" >&2
      return 1
    fi
    (( SECONDS <= deadline )) || { echo "GPU${gpu} server startup timed out" >&2; exit 1; }
    sleep 2
  done
}

echo "Starting persistent Gemma 4 26B-A4B audit servers."
# Prewarm the shared FlashInfer fused-MoE cache once, avoiding eight concurrent
# first-use compilations against the same cache path.
start_server 0
wait_for_server 0 "${SERVER_PIDS[0]}"
for gpu in {1..7}; do
  start_server "$gpu"
done
for gpu in {1..7}; do
  wait_for_server "$gpu" "${SERVER_PIDS[$gpu]}"
done

mapfile -t STAGES < <("$CLIENT_PYTHON" -c \
  'import sys,yaml; print("\n".join(str(x["id"]) for x in yaml.safe_load(open(sys.argv[1]))["stages"]))' "$CONFIG")

for stage in "${STAGES[@]}"; do
  stage_root="$RUN_ROOT/stages/$stage"
  mkdir -p "$stage_root/partitions"
  if [[ -s "$stage_root/audit.summary.json" ]]; then
    samples=$(jq -r '.rows' "$stage_root/audit.summary.json")
    "${STATE[@]}" set --run-root "$RUN_ROOT" --stage "$stage" --status done \
      --samples "$samples" --message "Existing merged receipt verified."
    continue
  fi

  "${STATE[@]}" set --run-root "$RUN_ROOT" --stage "$stage" --status preparing \
    --message "Preparing exact deterministic samples."
  while true; do
    if [[ "$stage" == "02_native_tool_agent" && \
          -s data/tokenized_dfm10_nemotron_terminal_native/completion.json ]]; then
      "$CLIENT_PYTHON" scripts/build_tokenized_dfm10_tree.py --force \
        >"$stage_root/refresh_union.log" 2>&1
    fi
    if "$CLIENT_PYTHON" scripts/dfm10_quality_audit.py prepare \
      --source-specs "$CONFIG" --stage "$stage" \
      --samples-output "$stage_root/samples.jsonl" \
      --inventory-output "$stage_root/inventory.json" \
      >"$stage_root/prepare.log" 2>&1; then
      break
    fi
    reason=$(tail -1 "$stage_root/prepare.log" | tr '\t' ' ' | cut -c1-240)
    "${STATE[@]}" set --run-root "$RUN_ROOT" --stage "$stage" --status blocked \
      --message "$reason; retrying in ${PREPARE_RETRY_SECONDS}s"
    sleep "$PREPARE_RETRY_SECONDS"
  done
  samples=$(jq -r '.sample_count' "$stage_root/inventory.json")
  "${STATE[@]}" set --run-root "$RUN_ROOT" --stage "$stage" --status running \
    --samples "$samples" --message "Auditing on eight persistent judge servers."

  attempt=1
  while true; do
    WORKER_PIDS=()
    for gpu in {0..7}; do
      "$CLIENT_PYTHON" scripts/dfm10_quality_audit.py audit \
        --samples "$stage_root/samples.jsonl" \
        --output "$stage_root/partitions/partition_${gpu}.jsonl" \
        --base-url "http://127.0.0.1:$((PORT_BASE + gpu))/v1" \
        --model "$MODEL_NAME" --partitions "$PARTITIONS" --partition-index "$gpu" \
        --concurrency "$CONCURRENCY" --max-tokens "$JUDGE_MAX_TOKENS" --retries 3 --resume \
        >"$stage_root/partitions/partition_${gpu}.log" 2>&1 &
      WORKER_PIDS+=("$!")
    done
    status=0
    for pid in "${WORKER_PIDS[@]}"; do
      wait "$pid" || status=1
    done
    WORKER_PIDS=()
    (( status == 0 )) && break
    if (( attempt >= 3 )); then
      "${STATE[@]}" set --run-root "$RUN_ROOT" --stage "$stage" --status failed \
        --samples "$samples" --message "Audit workers failed after three resumable attempts."
      exit 1
    fi
    attempt=$((attempt + 1))
    sleep 30
  done

  "$CLIENT_PYTHON" scripts/dfm10_quality_audit.py merge \
    --samples "$stage_root/samples.jsonl" \
    --partition-root "$stage_root/partitions" --partitions "$PARTITIONS" \
    --output "$stage_root/audit.jsonl"
  judge_errors=$(jq -r '.judge_errors' "$stage_root/audit.summary.json")
  "${STATE[@]}" set --run-root "$RUN_ROOT" --stage "$stage" --status done \
    --samples "$samples" --message "Merged atomically; judge_errors=${judge_errors}."
done

echo "All queued DFM10 residual quality audits completed."
