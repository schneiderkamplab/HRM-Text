#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

WORK_ROOT="${WORK_ROOT:-$ROOT/data/dfm10_persona_doms_chats}"
MODEL_PATH="${MODEL_PATH:-$ROOT/data/models/google/gemma-4-31B-it-fresh-20260604}"
MODEL_NAME="${MODEL_NAME:-dfm10-persona-doms-gemma4-31b}"
PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
HRM_PYTHON="${HRM_PYTHON:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
TOKENIZER_PATH="${TOKENIZER_PATH:-/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json}"
CHAT_TEMPLATE="${CHAT_TEMPLATE:-$ROOT/data_io/chat_templates/gemma4_native_chat.jinja}"
CONCURRENCY="${CONCURRENCY:-64}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.70}"
PORT_BASE="${PORT_BASE:-8940}"
FREE_THRESHOLD_MIB="${FREE_THRESHOLD_MIB:-3000}"
MAX_JOB_ATTEMPTS="${MAX_JOB_ATTEMPTS:-4}"
LEXICAL_LOCK="$ROOT/data/dfm10_danish_lexical_natural_work/campaign.lock"
LOG_ROOT="${LOG_ROOT:-$ROOT/logs/dfm10_persona_doms_chats_$(date +%Y%m%dT%H%M%S)}"

mkdir -p "$WORK_ROOT" "$LOG_ROOT"/{servers,workers,pids,cache}
exec 9>"$WORK_ROOT/campaign.lock"
flock -n 9 || { echo "Another persona/Doms runner is active"; exit 1; }
exec > >(tee -a "$LOG_ROOT/runner.log") 2>&1
printf '%s\n' "$LOG_ROOT" > "$WORK_ROOT/current_run_log_root.txt"

"$PYTHON" -c 'import pyarrow' || {
  echo "The audit environment requires pyarrow for persona/Doms clients" >&2
  exit 1
}

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

echo "Preparing deterministic persona and Domsdatabasen request shards..."
"$HRM_PYTHON" scripts/dfm10_persona_doms_chats.py prepare --work "$WORK_ROOT"

if [[ -e "$LEXICAL_LOCK" ]]; then
  echo "Waiting for the active Danish lexical campaign to release its lock..."
  flock "$LEXICAL_LOCK" -c true
fi

all_gpus_free() {
  local values value
  mapfile -t values < <(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)
  [[ "${#values[@]}" -eq 8 ]] || return 1
  for value in "${values[@]}"; do (( value <= FREE_THRESHOLD_MIB )) || return 1; done
}
echo "Waiting for all GPUs below ${FREE_THRESHOLD_MIB} MiB used..."
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
    --tensor-parallel-size 1 --max-model-len 8192 \
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

QUEUE="$WORK_ROOT/queue"
rm -rf "$QUEUE"
mkdir -p "$QUEUE"/{pending,running,done,failed,attempts}
for campaign in doms persona; do
  for input in "$WORK_ROOT/$campaign/requests/shards"/*.jsonl; do
    printf '%s\t%s\n' "$campaign" "$input" > "$QUEUE/pending/${campaign}__$(basename "$input")"
  done
done

claim_job() {
  local gpu="$1" candidate target
  while IFS= read -r candidate; do
    [[ -n "$candidate" ]] || continue
    target="$QUEUE/running/gpu${gpu}__$(basename "$candidate")"
    if mv "$candidate" "$target" 2>/dev/null; then
      printf '%s\n' "$target"
      return 0
    fi
  done < <(find "$QUEUE/pending" -maxdepth 1 -type f -print | sort)
  return 1
}

process_job() {
  local gpu="$1" claim="$2" campaign input name generated audit attempt
  IFS=$'\t' read -r campaign input < "$claim"
  name="$(basename "$input")"
  generated="$WORK_ROOT/$campaign/generated/$name"
  audit="$WORK_ROOT/$campaign/audits/$name"
  mkdir -p "$(dirname "$generated")" "$(dirname "$audit")"
  attempt_file="$QUEUE/attempts/${campaign}__${name}"
  attempt=0
  [[ ! -s "$attempt_file" ]] || attempt="$(<"$attempt_file")"
  attempt=$((attempt + 1))
  printf '%s\n' "$attempt" > "$attempt_file"
  echo "GPU${gpu}: ${campaign}/${name}, attempt ${attempt}/${MAX_JOB_ATTEMPTS}"

  "$PYTHON" scripts/dfm10_persona_doms_chats.py generate \
    --input "$input" --output "$generated" \
    --base-url "http://127.0.0.1:$((PORT_BASE + gpu))/v1" --model "$MODEL_NAME" \
    --concurrency "$CONCURRENCY" --max-tokens 4096
  "$PYTHON" scripts/dfm10_persona_doms_chats.py audit \
    --requests "$input" --input "$generated" --output "$audit" \
    --base-url "http://127.0.0.1:$((PORT_BASE + gpu))/v1" --model "$MODEL_NAME" \
    --concurrency "$CONCURRENCY" --max-tokens 1024
  "$HRM_PYTHON" scripts/dfm10_persona_doms_chats.py verify-shard \
    --requests "$input" --generated "$generated" --audited "$audit" \
    --minimum-completion-fraction 0.98
}

worker() {
  local gpu="$1" claim base attempt
  while claim="$(claim_job "$gpu")"; do
    base="$(basename "$claim" | sed "s/^gpu${gpu}__//")"
    if process_job "$gpu" "$claim"; then
      mv "$claim" "$QUEUE/done/$base"
    else
      attempt="$(<"$QUEUE/attempts/$base")"
      if (( attempt < MAX_JOB_ATTEMPTS )); then
        mv "$claim" "$QUEUE/pending/$base"
      else
        mv "$claim" "$QUEUE/failed/$base"
        echo "GPU${gpu}: permanently failed $base" >&2
      fi
    fi
  done
}

for gpu in $(seq 0 7); do
  worker "$gpu" >"$LOG_ROOT/workers/gpu${gpu}.log" 2>&1 &
  worker_pids+=("$!")
done
failed=0
for pid in "${worker_pids[@]}"; do wait "$pid" || failed=1; done
worker_pids=()
(( failed == 0 )) || { echo "At least one queue worker crashed" >&2; exit 1; }
if find "$QUEUE/failed" -maxdepth 1 -type f | grep -q .; then
  echo "One or more shards exhausted retries" >&2
  exit 1
fi

echo "Building all accepted rows (no post-audit cap)..."
"$HRM_PYTHON" scripts/dfm10_persona_doms_chats.py build \
  --work "$WORK_ROOT" --campaign persona --shards 64
"$HRM_PYTHON" scripts/dfm10_persona_doms_chats.py build \
  --work "$WORK_ROOT" --campaign doms --shards 32

echo "Tokenizing accepted chats with 16 CPU workers..."
"$HRM_PYTHON" scripts/tokenize_chat_template.py \
  data/dfm10_danish_persona_chats_source \
  --tokenizer-path "$TOKENIZER_PATH" --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_danish_persona_chats --workers 16 --force
"$HRM_PYTHON" scripts/tokenize_chat_template.py \
  data/dfm10_domsdatabasen_grounded_chats_source \
  --tokenizer-path "$TOKENIZER_PATH" --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_domsdatabasen_grounded_chats --workers 16 --force

echo "Materializing local Hugging Face packages..."
"$HRM_PYTHON" scripts/prepare_dfm10_hf_exports.py \
  --dataset dfm10-danish-persona-chats \
  --dataset dfm10-domsdatabasen-grounded-chats --workers 2 --force

echo "Persona and Domsdatabasen generation, audit, tokenization, and local packaging complete."
echo "DFM10 union rebuilding, sampling, and upload remain explicit follow-up operations."
