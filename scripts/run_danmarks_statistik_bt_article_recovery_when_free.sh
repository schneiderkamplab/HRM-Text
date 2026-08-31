#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GEN_ROOT="${GEN_ROOT:-logs/data_audits/danmarks_statistik_bt_article_generation_31b_20260829}"
AUDIT_ROOT="${AUDIT_ROOT:-logs/data_audits/danmarks_statistik_bt_article_recovery_31b_e4b_20260829}"
REQUESTS="${REQUESTS:-data/danmarks_statistik_bt_article_recovery/article_recovery_requests.jsonl}"
CANDIDATES="${CANDIDATES:-data/converted_sources/danmarks_statistik_bt_article_recovery_31b_candidates}"
BASE="${BASE:-data/converted_sources/danmarks_statistik_bt_repaired}"
UNION="${UNION:-data/converted_sources/danmarks_statistik_bt_repaired_with_article_recovery}"
GENERATOR_MODEL_PATH="${GENERATOR_MODEL_PATH:-$ROOT/data/models/google/gemma-4-31B-it-fresh-20260604}"
GENERATOR_MODEL_NAME="${GENERATOR_MODEL_NAME:-openai/gemma-4-31b-dst-article-recovery}"
AUDIT_MODEL_PATH="${AUDIT_MODEL_PATH:-$ROOT/data/models/google/gemma-4-E4B-it}"
AUDIT_MODEL_NAME="${AUDIT_MODEL_NAME:-openai/gemma-4-e4b-dst-article-audit}"
VLLM_PYTHON="${VLLM_PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
CLIENT_PYTHON="${CLIENT_PYTHON:-/home/ucloud/miniforge3/envs/hrm-cu132/bin/python}"
CHAT_TEMPLATE="${CHAT_TEMPLATE:-data_io/chat_templates/gemma4_native_chat.jinja}"
PORT_BASE="${PORT_BASE:-8960}"
CONCURRENCY="${CONCURRENCY:-64}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"
POLL_SECONDS="${POLL_SECONDS:-30}"
IDLE_SECONDS="${IDLE_SECONDS:-30}"
PARTITIONS=8

mkdir -p "$GEN_ROOT"/{servers,partitions,pids,cache} "$AUDIT_ROOT"/{partitions,results,workers}
exec 9>"$GEN_ROOT/orchestrator.lock"
flock -n 9 || { echo "DST article recovery is already orchestrated" >&2; exit 2; }
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
all_gpus_free || { echo "GPU became busy while locks were acquired" >&2; exit 1; }

SERVER_PIDS=()
WORKER_PIDS=()
cleanup() {
  local pid
  for pid in "${WORKER_PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  for pid in "${SERVER_PIDS[@]:-}"; do kill -TERM -- "-$pid" 2>/dev/null || true; done
  for pid in "${SERVER_PIDS[@]:-}"; do wait "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

start_servers() {
  local model_path="$1"
  local model_name="$2"
  local phase="$3"
  SERVER_PIDS=()
  for gpu in 0 1 2 3 4 5 6 7; do
    CUDA_VISIBLE_DEVICES="$gpu" VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_DISABLE_VERSION_CHECK=1 \
      VLLM_DEEP_GEMM_WARMUP=skip \
      TORCHINDUCTOR_CACHE_DIR="$GEN_ROOT/cache/${phase}_gpu${gpu}/torchinductor" \
      TRITON_CACHE_DIR="$GEN_ROOT/cache/${phase}_gpu${gpu}/triton" \
      setsid "$VLLM_PYTHON" -m vllm.entrypoints.openai.api_server \
        --model "$model_path" --served-model-name "$model_name" \
        --hf-overrides '{"architectures":["Gemma4ForCausalLM"]}' \
        --chat-template "$CHAT_TEMPLATE" \
        --host 127.0.0.1 --port "$((PORT_BASE + gpu))" --max-model-len 16384 \
        --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" --max-num-seqs 64 --enforce-eager \
        >"$GEN_ROOT/servers/${phase}_gpu${gpu}.log" 2>&1 &
    SERVER_PIDS+=("$!")
    echo "$!" >"$GEN_ROOT/pids/${phase}_server_gpu${gpu}.pid"
  done
  for gpu in 0 1 2 3 4 5 6 7; do
    deadline=$((SECONDS + 900))
    until curl -fsS "http://127.0.0.1:$((PORT_BASE + gpu))/v1/models" >/dev/null 2>&1; do
      kill -0 "${SERVER_PIDS[$gpu]}" 2>/dev/null || { echo "GPU${gpu} ${phase} server exited" >&2; exit 1; }
      (( SECONDS <= deadline )) || { echo "GPU${gpu} ${phase} server startup timed out" >&2; exit 1; }
      sleep 2
    done
  done
}

stop_servers() {
  local pid
  for pid in "${SERVER_PIDS[@]:-}"; do kill -TERM -- "-$pid" 2>/dev/null || true; done
  for pid in "${SERVER_PIDS[@]:-}"; do wait "$pid" 2>/dev/null || true; done
  SERVER_PIDS=()
  while [[ -n "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader,nounits 2>/dev/null | sed '/^[[:space:]]*$/d')" ]]; do
    sleep 2
  done
}

echo "Starting Gemma 4 31B IT generators."
start_servers "$GENERATOR_MODEL_PATH" "$GENERATOR_MODEL_NAME" generation

echo "Generating article-grounded recovery pairs."
for pass in 1 2 3 4; do
  echo "31B generation pass ${pass}/4."
  for gpu in 0 1 2 3 4 5 6 7; do
    "$CLIENT_PYTHON" scripts/generate_danmarks_statistik_bt_article_recovery.py generate \
      --requests "$REQUESTS" --output "$GEN_ROOT/partitions/partition_${gpu}.jsonl" \
      --base-url "http://127.0.0.1:$((PORT_BASE + gpu))/v1" --model "$GENERATOR_MODEL_NAME" \
      --partitions "$PARTITIONS" --partition-index "$gpu" --concurrency "$CONCURRENCY" \
      --max-tokens 2048 --resume \
      >"$GEN_ROOT/partitions/partition_${gpu}.log" 2>&1 &
    WORKER_PIDS+=("$!")
  done
  status=0
  for pid in "${WORKER_PIDS[@]}"; do wait "$pid" || status=1; done
  WORKER_PIDS=()
  (( status == 0 )) && break
  (( pass < 4 )) || break
  sleep $((pass * 2))
done
"$CLIENT_PYTHON" scripts/generate_danmarks_statistik_bt_article_recovery.py fail-close-errors \
  --partition-root "$GEN_ROOT/partitions" --partitions "$PARTITIONS" \
  --expected-model "$GENERATOR_MODEL_NAME"
"$CLIENT_PYTHON" scripts/generate_danmarks_statistik_bt_article_recovery.py merge \
  --requests "$REQUESTS" --partition-root "$GEN_ROOT/partitions" \
  --partitions "$PARTITIONS" --output "$GEN_ROOT/article_recoveries.jsonl" \
  --expected-model "$GENERATOR_MODEL_NAME"

"$CLIENT_PYTHON" scripts/recover_danmarks_statistik_bt_from_articles.py build \
  --generated "$GEN_ROOT/article_recoveries.jsonl" --output-dir "$CANDIDATES" --force
"$CLIENT_PYTHON" scripts/audit_danmarks_statistik_bt_article_recovery.py prepare \
  --input-dir "$CANDIDATES" --audit-dir "$AUDIT_ROOT" --partitions "$PARTITIONS"

stop_servers
echo "Starting independent Gemma 4 E4B auditors."
start_servers "$AUDIT_MODEL_PATH" "$AUDIT_MODEL_NAME" audit

echo "Independently auditing prompt, answer, and source evidence."
for pass in 1 2 3 4; do
  echo "E4B audit pass ${pass}/4."
  for gpu in 0 1 2 3 4 5 6 7; do
    "$CLIENT_PYTHON" scripts/audit_danmarks_statistik_bt_article_recovery.py audit \
      --audit-dir "$AUDIT_ROOT" --partition-index "$gpu" \
      --base-url "http://127.0.0.1:$((PORT_BASE + gpu))/v1" --model "$AUDIT_MODEL_NAME" \
      --concurrency "$CONCURRENCY" >"$AUDIT_ROOT/workers/partition_${gpu}.log" 2>&1 &
    WORKER_PIDS+=("$!")
  done
  status=0
  for pid in "${WORKER_PIDS[@]}"; do wait "$pid" || status=1; done
  WORKER_PIDS=()
  (( status == 0 )) && break
  (( pass < 4 )) || exit "$status"
  sleep $((pass * 2))
done
"$CLIENT_PYTHON" scripts/audit_danmarks_statistik_bt_article_recovery.py merge \
  --audit-dir "$AUDIT_ROOT" --partitions "$PARTITIONS" --model "$AUDIT_MODEL_NAME"
"$CLIENT_PYTHON" scripts/audit_danmarks_statistik_bt_article_recovery.py finalize \
  --input-dir "$CANDIDATES" --audit-dir "$AUDIT_ROOT" --base-dir "$BASE" \
  --output-dir "$UNION" --force

echo "Tokenizing the verified union without changing the source-only baseline."
STAGE="data/dfm10_danmarks_statistik_bt_repaired_sources"
TOKENIZED="data/tokenized_dfm10_danmarks_statistik_bt_repaired"
mkdir -p "$STAGE"
find "$STAGE" -mindepth 1 -maxdepth 1 -delete
ln -s "$(realpath "$UNION")" "$STAGE/danmarks_statistik_bt_repaired"
"$CLIENT_PYTHON" scripts/tokenize_chat_template.py "$STAGE" \
  --tokenizer-path /work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json \
  --chat-template data_io/chat_templates/gemma4_native_chat.jinja \
  --output-dir "$TOKENIZED" --workers 16 --force
echo "DST full-article recovery, audit, union, and tokenization complete."
