#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

WORK_ROOT="${WORK_ROOT:-$ROOT/data/dfm10_danish_lexical_natural_work}"
SOURCE_ROOT="${SOURCE_ROOT:-$ROOT/data/dfm10_danish_lexical_sources}"
MODEL_PATH="${MODEL_PATH:-$ROOT/data/models/google/gemma-4-31B-it-fresh-20260604}"
MODEL_NAME="${MODEL_NAME:-dfm10-danish-lexical-natural-gemma4-31b}"
PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
HRM_PYTHON="${HRM_PYTHON:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
TOKENIZER_PATH="${TOKENIZER_PATH:-/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json}"
CHAT_TEMPLATE="${CHAT_TEMPLATE:-$ROOT/data_io/chat_templates/gemma4_native_chat.jinja}"
CONCURRENCY="${CONCURRENCY:-64}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.70}"
PORT_BASE="${PORT_BASE:-8920}"
FREE_THRESHOLD_MIB="${FREE_THRESHOLD_MIB:-3000}"
MIMIR_LOCK="$ROOT/data/mimir_grounded_500k_sft/campaign.lock"
LOG_ROOT="${LOG_ROOT:-$ROOT/logs/dfm10_danish_lexical_natural_$(date +%Y%m%dT%H%M%S)}"

mkdir -p "$WORK_ROOT" "$LOG_ROOT"/{servers,workers,pids,cache}
exec 9>"$WORK_ROOT/campaign.lock"
flock -n 9 || { echo "Another lexical-natural runner is active"; exit 1; }
exec > >(tee -a "$LOG_ROOT/runner.log") 2>&1
printf '%s\n' "$LOG_ROOT" > "$WORK_ROOT/current_run_log_root.txt"

server_pids=()
worker_pids=()
cleanup() {
  for pid in "${worker_pids[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  for pid in "${server_pids[@]:-}"; do kill -TERM -- "-$pid" 2>/dev/null || true; done
  sleep 3
  for pid in "${server_pids[@]:-}"; do kill -KILL -- "-$pid" 2>/dev/null || true; done
  for pid in "${worker_pids[@]:-}" "${server_pids[@]:-}"; do
    [[ -n "$pid" ]] && wait "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

if "$HRM_PYTHON" - <<'PY'
import json
from pathlib import Path

names = ("dfm10-danish-lexical-sentiment-sft", "dfm10-danish-framenet-sft")
for name in names:
    path = Path("exports_dfm10") / name / "metadata" / "validation.json"
    if not path.is_file() or not json.loads(path.read_text()).get("valid"):
        raise SystemExit(1)
if not Path("data/tokenized_dfm10_danish_lexical/completion.json").is_file():
    raise SystemExit(1)
PY
then
  echo "Danish lexical generation, audit, tokenization, and packages are already complete."
  exit 0
fi

echo "Preparing 47,854 additive lexical items in eight request shards..."
"$HRM_PYTHON" scripts/dfm10_danish_lexical_natural.py \
  --source-dir "$SOURCE_ROOT" --work-dir "$WORK_ROOT" prepare --shards 8 --batch-size 8

if [[ -e "$MIMIR_LOCK" ]]; then
  echo "Waiting for the current Mimir campaign lock..."
  flock "$MIMIR_LOCK" -c true
fi

all_gpus_free() {
  local values
  mapfile -t values < <(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)
  [[ "${#values[@]}" -eq 8 ]] || return 1
  for value in "${values[@]}"; do (( value <= FREE_THRESHOLD_MIB )) || return 1; done
}
echo "Waiting for all eight GPUs below ${FREE_THRESHOLD_MIB} MiB used..."
until all_gpus_free; do sleep 30; done

wait_server() {
  local port="$1" pid="$2" deadline=$((SECONDS + 1200))
  until curl -fsS "http://127.0.0.1:${port}/v1/models" >/dev/null 2>&1; do
    kill -0 "$pid" 2>/dev/null || return 1
    (( SECONDS < deadline )) || return 1
    sleep 2
  done
}

for gpu in $(seq 0 7); do
  port=$((PORT_BASE + gpu))
  cache="$LOG_ROOT/cache/gpu${gpu}"
  mkdir -p "$cache"
  CUDA_VISIBLE_DEVICES="$gpu" \
  CUDA_HOME="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}" \
  PATH="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}/bin:/home/ucloud/miniforge3/envs/audit/bin:${PATH}" \
  LD_LIBRARY_PATH="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}/lib:${LD_LIBRARY_PATH:-}" \
  VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_DISABLE_VERSION_CHECK=1 \
  TORCHINDUCTOR_CACHE_DIR="$cache/torchinductor" TRITON_CACHE_DIR="$cache/triton" \
  setsid "$PYTHON" -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" --served-model-name "$MODEL_NAME" \
    --hf-overrides '{"architectures":["Gemma4ForCausalLM"]}' \
    --chat-template "$CHAT_TEMPLATE" --host 127.0.0.1 --port "$port" \
    --tensor-parallel-size 1 --max-model-len 4096 \
    --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" --max-num-seqs 64 --enforce-eager \
    >"$LOG_ROOT/servers/gpu${gpu}.log" 2>&1 &
  server_pids+=("$!")
  echo "$!" > "$LOG_ROOT/pids/server_gpu${gpu}.pid"
done
for gpu in $(seq 0 7); do
  wait_server "$((PORT_BASE + gpu))" "${server_pids[$gpu]}" || {
    echo "GPU $gpu server failed to become ready" >&2
    exit 1
  }
done

worker() {
  local gpu="$1" name input generated audit pass
  name="part-$(printf '%02d' "$gpu")-of-08.jsonl"
  input="$WORK_ROOT/requests/$name"
  generated="$WORK_ROOT/generated/$name"
  audit="$WORK_ROOT/audits/$name"
  mkdir -p "$(dirname "$generated")" "$(dirname "$audit")"
  for pass in 1 2 3; do
    "$PYTHON" scripts/dfm10_danish_lexical_natural.py \
      --source-dir "$SOURCE_ROOT" --work-dir "$WORK_ROOT" generate \
      --input "$input" --output "$generated" \
      --base-url "http://127.0.0.1:$((PORT_BASE + gpu))/v1" --model "$MODEL_NAME" \
      --concurrency "$CONCURRENCY" --max-tokens 2048
  done
  for pass in 1 2 3; do
    "$PYTHON" scripts/dfm10_danish_lexical_natural.py \
      --source-dir "$SOURCE_ROOT" --work-dir "$WORK_ROOT" audit \
      --requests "$input" --input "$generated" --output "$audit" \
      --base-url "http://127.0.0.1:$((PORT_BASE + gpu))/v1" --model "$MODEL_NAME" \
      --concurrency "$CONCURRENCY" --max-tokens 2048
  done
}

for gpu in $(seq 0 7); do
  worker "$gpu" >"$LOG_ROOT/workers/gpu${gpu}.log" 2>&1 &
  worker_pids+=("$!")
done
failed=0
for pid in "${worker_pids[@]}"; do wait "$pid" || failed=1; done
worker_pids=()
(( failed == 0 )) || { echo "At least one lexical worker failed" >&2; exit 1; }

"$HRM_PYTHON" scripts/dfm10_danish_lexical_natural.py \
  --source-dir "$SOURCE_ROOT" --work-dir "$WORK_ROOT" build

"$HRM_PYTHON" scripts/tokenize_chat_template.py "$SOURCE_ROOT" \
  --tokenizer-path "$TOKENIZER_PATH" --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_danish_lexical --workers 16 --force
flock data/.dfm10-union.lock "$HRM_PYTHON" scripts/build_tokenized_dfm10_tree.py \
  --danish-lexical data/tokenized_dfm10_danish_lexical --force
"$HRM_PYTHON" scripts/prepare_dfm10_hf_exports.py \
  --dataset dfm10-danish-lexical-sentiment-sft \
  --dataset dfm10-danish-framenet-sft --workers 2 --force

echo "Natural lexical generation, audit, source build, union rebuild, and local export refresh complete."
echo "Final DFM10 sampling and Hugging Face upload remain explicit follow-up operations."
