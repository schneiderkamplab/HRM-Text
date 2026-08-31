#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

WORK="${WORK:-$ROOT/data/dfm10_medquad_da_work}"
MODEL="${MODEL:-$ROOT/data/models/google/gemma-4-31B-it-fresh-20260604}"
SERVED_MODEL="${SERVED_MODEL:-google/gemma-4-31B-it-fresh-20260604}"
VLLM_PYTHON="${VLLM_PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
HRM_PYTHON="${HRM_PYTHON:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
TOKENIZER_PATH="${TOKENIZER_PATH:-/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json}"
CHAT_TEMPLATE="${CHAT_TEMPLATE:-$ROOT/data_io/chat_templates/gemma4_native_chat.jinja}"
PORT_BASE="${PORT_BASE:-9400}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.70}"
CONCURRENCY="${CONCURRENCY:-64}"
FREE_MEMORY_THRESHOLD_MIB="${FREE_MEMORY_THRESHOLD_MIB:-175000}"
LOG_ROOT="${LOG_ROOT:-$ROOT/logs/dfm10_medquad_da_$(date +%Y%m%dT%H%M%S)}"

mkdir -p "$WORK" "$LOG_ROOT/servers" "$LOG_ROOT/workers"
exec 9>"$WORK/campaign.lock"
flock -n 9 || { echo "Another MedQuAD campaign holds $WORK/campaign.lock"; exit 1; }

echo "$(date -Is) preparing official pinned MedQuAD source and request shards"
"$HRM_PYTHON" scripts/prepare_dfm10_medquad_da.py --work "$WORK" prepare --shards 8

echo "$(date -Is) waiting for all eight GPUs to become free; existing jobs will not be disturbed"
while true; do
  mapfile -t free_mib < <(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
  if [[ "${#free_mib[@]}" -eq 8 ]]; then
    ready=1
    for value in "${free_mib[@]}"; do
      (( value >= FREE_MEMORY_THRESHOLD_MIB )) || ready=0
    done
    (( ready == 1 )) && break
  fi
  sleep 60
done

server_pgids=()
cleanup() {
  status=$?
  trap - EXIT INT TERM
  for pgid in "${server_pgids[@]}"; do
    kill -TERM -- "-$pgid" 2>/dev/null || true
  done
  sleep 3
  for pgid in "${server_pgids[@]}"; do
    kill -KILL -- "-$pgid" 2>/dev/null || true
  done
  exit "$status"
}
trap cleanup EXIT INT TERM

for gpu in $(seq 0 7); do
  port=$((PORT_BASE + gpu))
  CUDA_VISIBLE_DEVICES="$gpu" setsid "$VLLM_PYTHON" -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" \
    --served-model-name "$SERVED_MODEL" \
    --hf-overrides '{"architectures":["Gemma4ForCausalLM"]}' \
    --chat-template "$CHAT_TEMPLATE" \
    --host 127.0.0.1 --port "$port" \
    --tensor-parallel-size 1 --max-model-len 8192 \
    --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
    --max-num-seqs 128 --enforce-eager \
    >"$LOG_ROOT/servers/gpu${gpu}.log" 2>&1 &
  server_pgids+=("$!")
done

for gpu in $(seq 0 7); do
  port=$((PORT_BASE + gpu))
  for _ in $(seq 1 180); do
    if curl -fsS "http://127.0.0.1:${port}/v1/models" >/dev/null; then break; fi
    sleep 5
  done
  curl -fsS "http://127.0.0.1:${port}/v1/models" >/dev/null || {
    echo "GPU $gpu MedQuAD vLLM server failed to become ready" >&2
    exit 1
  }
done

worker() {
  gpu="$1"
  name="part-$(printf '%02d' "$gpu")-of-08.jsonl"
  base_url="http://127.0.0.1:$((PORT_BASE + gpu))/v1"
  # Each pass skips successful stable IDs. Later passes recover malformed JSON
  # and transient request failures without regenerating accepted records.
  for recovery_pass in $(seq 1 4); do
    echo "$(date -Is) gpu=$gpu recovery_pass=$recovery_pass translate"
    "$HRM_PYTHON" scripts/prepare_dfm10_medquad_da.py --work "$WORK" translate \
      --input "$WORK/requests/$name" --output "$WORK/translations/$name" \
      --base-url "$base_url" --model "$SERVED_MODEL" --concurrency "$CONCURRENCY" \
      --max-tokens 4096 --timeout 900 --retries 3
    echo "$(date -Is) gpu=$gpu recovery_pass=$recovery_pass audit"
    "$HRM_PYTHON" scripts/prepare_dfm10_medquad_da.py --work "$WORK" audit \
      --requests "$WORK/requests/$name" --input "$WORK/translations/$name" \
      --output "$WORK/audits/$name" --base-url "$base_url" --model "$SERVED_MODEL" \
      --concurrency "$CONCURRENCY" --max-tokens 768 --timeout 600 --retries 3 --min-score 4
  done
}

worker_pids=()
for gpu in $(seq 0 7); do
  worker "$gpu" >"$LOG_ROOT/workers/gpu${gpu}.log" 2>&1 &
  worker_pids+=("$!")
done
for pid in "${worker_pids[@]}"; do wait "$pid"; done

"$HRM_PYTHON" scripts/prepare_dfm10_medquad_da.py --work "$WORK" build --allow-incomplete
"$HRM_PYTHON" scripts/tokenize_chat_template.py \
  data/dfm10_medquad_sources --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template data_io/chat_templates/gemma4_native_chat.jinja \
  --output-dir data/tokenized_dfm10_medquad --workers 16 --force
flock data/.dfm10-union.lock "$HRM_PYTHON" scripts/build_tokenized_dfm10_tree.py --force
echo "$(date -Is) MedQuAD English/Danish campaign built, tokenized, and integrated"
