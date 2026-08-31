#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GEN_ROOT="${GEN_ROOT:-logs/data_audits/danmarks_statistik_bt_prompt_repair_20260829}"
AUDIT_ROOT="${AUDIT_ROOT:-logs/data_audits/danmarks_statistik_bt_repaired_20260829}"
REQUESTS="${REQUESTS:-data/danmarks_statistik_bt_repair/prompt_repair_requests.jsonl}"
CANDIDATES="${CANDIDATES:-data/converted_sources/danmarks_statistik_bt_repaired_candidates}"
REPAIRED="${REPAIRED:-data/converted_sources/danmarks_statistik_bt_repaired}"
MODEL_PATH="${MODEL_PATH:-/work/dfm/jacobwashere/brainsurgery/models/google/gemma-4-E4B-it}"
MODEL_NAME="${MODEL_NAME:-openai/gemma-4-e4b-dst-repair}"
VLLM_PYTHON="${VLLM_PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
CLIENT_PYTHON="${CLIENT_PYTHON:-/home/ucloud/miniforge3/envs/hrm-cu132/bin/python}"
PORT_BASE="${PORT_BASE:-8920}"
CONCURRENCY="${CONCURRENCY:-64}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"
POLL_SECONDS="${POLL_SECONDS:-30}"
IDLE_SECONDS="${IDLE_SECONDS:-30}"
PARTITIONS=8

mkdir -p "$GEN_ROOT"/{servers,partitions,pids,cache} "$AUDIT_ROOT"/{partitions,results,workers}
exec 9>"$GEN_ROOT/orchestrator.lock"
flock -n 9 || { echo "Danmarks Statistik repair is already orchestrated" >&2; exit 2; }
exec > >(tee -a "$GEN_ROOT/orchestrator.log") 2>&1

all_gpus_free() {
  [[ -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader,nounits 2>/dev/null | sed '/^[[:space:]]*$/d')" ]]
}

echo "Waiting for all eight GPUs to be free for ${IDLE_SECONDS}s; running jobs will not be disturbed."
idle_since=0
while true; do
  if all_gpus_free; then
    (( idle_since == 0 )) && idle_since=$SECONDS
    (( SECONDS - idle_since >= IDLE_SECONDS )) && break
  else
    idle_since=0
  fi
  sleep "$POLL_SECONDS"
done

for gpu in 0 1 2 3 4 5 6 7; do
  exec {fd}>"/tmp/hrm-gpu-${gpu}.lock"
  flock "$fd"
  eval "GPU_LOCK_${gpu}=$fd"
done
all_gpus_free || { echo "GPU became busy while acquiring locks" >&2; exit 1; }

SERVER_PIDS=()
WORKER_PIDS=()
cleanup() {
  local pid
  for pid in "${WORKER_PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  for pid in "${SERVER_PIDS[@]:-}"; do kill -TERM -- "-$pid" 2>/dev/null || true; done
  for pid in "${SERVER_PIDS[@]:-}"; do wait "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

for gpu in 0 1 2 3 4 5 6 7; do
  CUDA_VISIBLE_DEVICES="$gpu" VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_DISABLE_VERSION_CHECK=1 \
    VLLM_DEEP_GEMM_WARMUP=skip \
    TORCHINDUCTOR_CACHE_DIR="$GEN_ROOT/cache/gpu${gpu}/torchinductor" \
    TRITON_CACHE_DIR="$GEN_ROOT/cache/gpu${gpu}/triton" \
    setsid "$VLLM_PYTHON" -m vllm.entrypoints.openai.api_server \
      --model "$MODEL_PATH" --served-model-name "$MODEL_NAME" \
      --host 127.0.0.1 --port "$((PORT_BASE + gpu))" --max-model-len 8192 \
      --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" --max-num-seqs 64 --enforce-eager \
      >"$GEN_ROOT/servers/gpu${gpu}.log" 2>&1 &
  SERVER_PIDS+=("$!")
  echo "$!" >"$GEN_ROOT/pids/server_gpu${gpu}.pid"
done

for gpu in 0 1 2 3 4 5 6 7; do
  deadline=$((SECONDS + 900))
  until curl -fsS "http://127.0.0.1:$((PORT_BASE + gpu))/v1/models" >/dev/null 2>&1; do
    kill -0 "${SERVER_PIDS[$gpu]}" 2>/dev/null || { echo "GPU${gpu} server exited" >&2; exit 1; }
    (( SECONDS <= deadline )) || { echo "GPU${gpu} server startup timed out" >&2; exit 1; }
    sleep 2
  done
done

echo "Generating answer-matched prompts for all 7,154 rows."
WORKER_PIDS=()
for gpu in 0 1 2 3 4 5 6 7; do
  "$CLIENT_PYTHON" scripts/generate_danmarks_statistik_bt_prompts.py generate \
    --requests "$REQUESTS" --output "$GEN_ROOT/partitions/partition_${gpu}.jsonl" \
    --base-url "http://127.0.0.1:$((PORT_BASE + gpu))/v1" --model "$MODEL_NAME" \
    --partitions "$PARTITIONS" --partition-index "$gpu" --concurrency "$CONCURRENCY" --resume \
    >"$GEN_ROOT/partitions/partition_${gpu}.log" 2>&1 &
  WORKER_PIDS+=("$!")
done
status=0
for pid in "${WORKER_PIDS[@]}"; do wait "$pid" || status=1; done
WORKER_PIDS=()
(( status == 0 )) || exit "$status"
"$CLIENT_PYTHON" scripts/generate_danmarks_statistik_bt_prompts.py merge \
  --requests "$REQUESTS" --partition-root "$GEN_ROOT/partitions" \
  --partitions "$PARTITIONS" --output "$GEN_ROOT/prompt_repairs.jsonl"

echo "Building bounded Gemma-native repair candidates."
"$CLIENT_PYTHON" scripts/repair_danmarks_statistik_bt.py build \
  --generated "$GEN_ROOT/prompt_repairs.jsonl" --output-dir "$CANDIDATES" --force
"$CLIENT_PYTHON" scripts/audit_repaired_danmarks_statistik_bt.py prepare \
  --input-dir "$CANDIDATES" --audit-dir "$AUDIT_ROOT" --samples 0 --partitions "$PARTITIONS"

echo "Auditing every generated prompt/target pair."
WORKER_PIDS=()
for gpu in 0 1 2 3 4 5 6 7; do
  "$CLIENT_PYTHON" scripts/audit_repaired_danmarks_statistik_bt.py audit \
    --audit-dir "$AUDIT_ROOT" --partition-index "$gpu" \
    --base-url "http://127.0.0.1:$((PORT_BASE + gpu))/v1" --model "$MODEL_NAME" \
    --concurrency "$CONCURRENCY" >"$AUDIT_ROOT/workers/partition_${gpu}.log" 2>&1 &
  WORKER_PIDS+=("$!")
done
status=0
for pid in "${WORKER_PIDS[@]}"; do wait "$pid" || status=1; done
WORKER_PIDS=()
(( status == 0 )) || exit "$status"
"$CLIENT_PYTHON" scripts/audit_repaired_danmarks_statistik_bt.py merge \
  --audit-dir "$AUDIT_ROOT" --partitions "$PARTITIONS" --model "$MODEL_NAME"
"$CLIENT_PYTHON" scripts/audit_repaired_danmarks_statistik_bt.py filter \
  --input-dir "$CANDIDATES" --audit-dir "$AUDIT_ROOT" --output-dir "$REPAIRED" --force

echo "Tokenizing strict accepted rows."
STAGE="data/dfm10_danmarks_statistik_bt_repaired_sources"
TOKENIZED="data/tokenized_dfm10_danmarks_statistik_bt_repaired"
mkdir -p "$STAGE"
find "$STAGE" -mindepth 1 -maxdepth 1 -delete
ln -s "$(realpath "$REPAIRED")" "$STAGE/danmarks_statistik_bt_repaired"
"$CLIENT_PYTHON" scripts/tokenize_chat_template.py "$STAGE" \
  --tokenizer-path /work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json \
  --chat-template data_io/chat_templates/gemma4_native_chat.jinja \
  --output-dir "$TOKENIZED" --workers 16 --force
echo "Danmarks Statistik BT repair, audit, filtering, and tokenization complete."
