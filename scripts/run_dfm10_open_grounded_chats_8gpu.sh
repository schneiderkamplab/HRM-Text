#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DATA_ROOT="${DATA_ROOT:-$ROOT/data/dfm10_open_grounded_chats}"
MODEL_PATH="${MODEL_PATH:-$ROOT/data/models/google/gemma-4-31B-it-fresh-20260604}"
MODEL_NAME="${MODEL_NAME:-dfm10-open-chats-gemma4-31b}"
PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
HRM_PYTHON="${HRM_PYTHON:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
TOKENIZER_PATH="${TOKENIZER_PATH:-/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json}"
CONCURRENCY="${CONCURRENCY:-64}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.70}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-8192}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-64}"
FREE_THRESHOLD_MIB="${FREE_THRESHOLD_MIB:-3000}"
PORT_BASE="${PORT_BASE:-8800}"
LOG_ROOT="${LOG_ROOT:-$ROOT/logs/dfm10_open_grounded_chats_$(date +%Y%m%dT%H%M%S)}"

mkdir -p "$DATA_ROOT" "$LOG_ROOT"/{servers,workers,pids,queue/{pending,running,done,failed}}
exec 9>"$DATA_ROOT/campaign.lock"
flock -n 9 || { echo "Another open grounded-chat campaign holds $DATA_ROOT/campaign.lock"; exit 1; }
exec > >(tee -a "$LOG_ROOT/runner.log") 2>&1
printf '%s\n' "$LOG_ROOT" > "$DATA_ROOT/current_run_log_root.txt"

server_pids=()
worker_pids=()
cleanup() {
  for pid in "${worker_pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  done
  for pid in "${server_pids[@]:-}"; do kill -TERM -- "-$pid" 2>/dev/null || true; done
  sleep 3
  for pid in "${server_pids[@]:-}"; do
    kill -KILL -- "-$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

echo "$(date -Is) waiting for complete Wikipedia/OpenStax request manifests"
until [[ -s "$DATA_ROOT/requests.summary.json" ]]; do sleep 30; done
wiki_rows="$(jq -r '.wikipedia_da.rows' "$DATA_ROOT/requests.summary.json")"
openstax_rows="$(jq -r '.openstax_en.rows' "$DATA_ROOT/requests.summary.json")"
[[ "$wiki_rows" -eq 50000 && "$openstax_rows" -eq 160376 ]] || {
  echo "Unexpected request counts: wikipedia=$wiki_rows openstax=$openstax_rows" >&2
  exit 1
}

echo "$(date -Is) waiting for the Tidsskrift Gemma 4 31B campaign lock"
exec 8>"$ROOT/data/dfm10_tidsskrift_grounded_sft/campaign.lock"
flock 8

all_gpus_free() {
  local values value
  mapfile -t values < <(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)
  [[ "${#values[@]}" -eq 8 ]] || return 1
  for value in "${values[@]}"; do (( value <= FREE_THRESHOLD_MIB )) || return 1; done
}
echo "$(date -Is) waiting for all GPUs below ${FREE_THRESHOLD_MIB} MiB used"
until all_gpus_free; do sleep 30; done

for dataset in wikipedia_da openstax_en; do
  mkdir -p "$DATA_ROOT/$dataset"/{chat_generated,chat_audits,state/done}
  for shard in "$DATA_ROOT/$dataset"/requests/shards/part-*.jsonl; do
    base="$(basename "$shard")"
    [[ -f "$DATA_ROOT/$dataset/state/done/${base}.done" ]] && continue
    printf 'DATASET=%q\nSHARD=%q\n' "$dataset" "$shard" \
      > "$LOG_ROOT/queue/pending/${base}__${dataset}.job"
  done
done

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
    --chat-template "$ROOT/data_io/chat_templates/gemma4_native_chat.jinja" \
    --host 127.0.0.1 --port "$port" --tensor-parallel-size 1 \
    --max-model-len "$MAX_MODEL_LEN" --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
    --max-num-seqs "$MAX_NUM_SEQS" --enforce-eager \
    >"$LOG_ROOT/servers/gpu${gpu}.log" 2>&1 &
  server_pids+=("$!")
  echo "$!" > "$LOG_ROOT/pids/server_gpu${gpu}.pid"
done
for gpu in $(seq 0 7); do
  wait_server "$((PORT_BASE + gpu))" "${server_pids[$gpu]}" || exit 1
done

claim() {
  local gpu="$1" job destination
  while IFS= read -r -d '' job; do
    destination="$LOG_ROOT/queue/running/gpu${gpu}__$(basename "$job")"
    if mv "$job" "$destination" 2>/dev/null; then printf '%s\n' "$destination"; return 0; fi
  done < <(find "$LOG_ROOT/queue/pending" -maxdepth 1 -name '*.job' -print0 | sort -z)
  return 1
}

worker() {
  local gpu="$1" port=$((PORT_BASE + gpu)) claimed shard base dataset generated audit log pass verified
  while claimed="$(claim "$gpu")"; do
    # shellcheck disable=SC1090
    source "$claimed"
    shard="$SHARD"; dataset="$DATASET"; base="$(basename "$shard")"
    generated="$DATA_ROOT/$dataset/chat_generated/$base"
    audit="$DATA_ROOT/$dataset/chat_audits/$base"
    log="$LOG_ROOT/workers/${dataset}__${base}_gpu${gpu}.log"
    verified=0
    for pass in 1 2 3 4; do
      "$PYTHON" scripts/dfm10_tidsskrift_chats_model.py --data-root "$DATA_ROOT/$dataset" generate \
        --input "$shard" --output "$generated" --base-url "http://127.0.0.1:${port}/v1" \
        --model "$MODEL_NAME" --concurrency "$CONCURRENCY" --max-tokens 4096 >>"$log" 2>&1
      "$PYTHON" scripts/dfm10_tidsskrift_chats_model.py --data-root "$DATA_ROOT/$dataset" audit \
        --input "$generated" --requests "$shard" --output "$audit" \
        --base-url "http://127.0.0.1:${port}/v1" --model "$MODEL_NAME" \
        --concurrency "$CONCURRENCY" --max-tokens 4096 >>"$log" 2>&1
      if "$PYTHON" scripts/dfm10_tidsskrift_chats_model.py verify-shard \
          --requests "$shard" --generated "$generated" --audited "$audit" \
          --minimum-completion-fraction 0.98 >>"$log" 2>&1; then
        verified=1
        break
      fi
    done
    if (( verified )); then
      date -Is > "$DATA_ROOT/$dataset/state/done/${base}.done"
      mv "$claimed" "$LOG_ROOT/queue/done/$(basename "$claimed")"
    else
      mv "$claimed" "$LOG_ROOT/queue/failed/$(basename "$claimed")"
    fi
  done
}

for gpu in $(seq 0 7); do
  worker "$gpu" >"$LOG_ROOT/workers/worker_gpu${gpu}.log" 2>&1 &
  worker_pids+=("$!")
done
for pid in "${worker_pids[@]}"; do wait "$pid"; done
worker_pids=()

failed="$(find "$LOG_ROOT/queue/failed" -maxdepth 1 -name '*.job' | wc -l)"
wiki_done="$(find "$DATA_ROOT/wikipedia_da/state/done" -name '*.done' | wc -l)"
openstax_done="$(find "$DATA_ROOT/openstax_en/state/done" -name '*.done' | wc -l)"
echo "$(date -Is) chats done wikipedia=$wiki_done/128 openstax=$openstax_done/256 failed=$failed"
(( failed == 0 && wiki_done == 128 && openstax_done == 256 )) || exit 1

if [[ ! -s data/dfm10_danish_wikipedia_open_chats_source/danish_wikipedia_open_chats.jsonl ]]; then
  "$HRM_PYTHON" scripts/dfm10_tidsskrift_chats_model.py --data-root "$DATA_ROOT/wikipedia_da" build \
    --config config/dfm10_open_grounded_chats.json \
    --request-shards 128 \
    --output data/dfm10_danish_wikipedia_open_chats_source/danish_wikipedia_open_chats.jsonl \
    --minimum-chats 25000 --minimum-assistant-turns 150000
else
  echo "$(date -Is) reusing finalized Danish Wikipedia chats"
fi
"$HRM_PYTHON" scripts/dfm10_tidsskrift_chats_model.py --data-root "$DATA_ROOT/openstax_en" build \
  --config config/dfm10_open_grounded_chats.json \
  --request-shards 256 \
  --output data/dfm10_openstax_open_chats_source/openstax_open_chats.jsonl \
  --minimum-chats 80000 --minimum-assistant-turns 500000

if ! jq -e '.valid == true and .rows == 49787' \
    exports_dfm10/dfm10-danish-wikipedia-open-chats/metadata/validation.json >/dev/null 2>&1; then
  "$HRM_PYTHON" scripts/prepare_dfm10_hf_exports.py --dataset dfm10-danish-wikipedia-open-chats --force
  "$HRM_PYTHON" exports_dfm10/dfm10-danish-wikipedia-open-chats/recreate_dataset.py \
    > exports_dfm10/dfm10-danish-wikipedia-open-chats/metadata/validation.json
else
  echo "$(date -Is) reusing validated Danish Wikipedia export package"
fi
"$HRM_PYTHON" scripts/prepare_dfm10_hf_exports.py --dataset dfm10-openstax-open-chats --force
if [[ ! -s data/tokenized_dfm10_danish_wikipedia_open_chats/danish_wikipedia_open_chats.jsonl/metadata.json ]]; then
  "$HRM_PYTHON" scripts/tokenize_chat_template.py \
    data/dfm10_danish_wikipedia_open_chats_source \
    --tokenizer-path "$TOKENIZER_PATH" \
    --chat-template data_io/chat_templates/gemma4_native_chat.jinja \
    --output-dir data/tokenized_dfm10_danish_wikipedia_open_chats --workers 16 --force
else
  echo "$(date -Is) reusing tokenized Danish Wikipedia chats"
fi
"$HRM_PYTHON" scripts/tokenize_chat_template.py \
  data/dfm10_openstax_open_chats_source \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template data_io/chat_templates/gemma4_native_chat.jinja \
  --output-dir data/tokenized_dfm10_openstax_open_chats --workers 16 --force
"$HRM_PYTHON" scripts/build_tokenized_dfm10_tree.py --force
echo "$(date -Is) Wikipedia and OpenStax grounded chats built, packaged, tokenized, and activated"
