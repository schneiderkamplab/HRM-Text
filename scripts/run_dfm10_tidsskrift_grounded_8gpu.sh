#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DATA_ROOT="${DATA_ROOT:-$ROOT/data/dfm10_tidsskrift_grounded_sft}"
MODEL_PATH="${MODEL_PATH:-$ROOT/data/models/google/gemma-4-31B-it-fresh-20260604}"
MODEL_NAME="${MODEL_NAME:-dfm10-tidsskrift-gemma4-31b}"
PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
HRM_PYTHON="${HRM_PYTHON:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
TOKENIZER_PATH="${TOKENIZER_PATH:-/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json}"
SHARDS="${SHARDS:-256}"
CONCURRENCY="${CONCURRENCY:-64}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.70}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-8192}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-64}"
FREE_THRESHOLD_MIB="${FREE_THRESHOLD_MIB:-3000}"
PORT_BASE="${PORT_BASE:-8800}"
LOG_ROOT="${LOG_ROOT:-$ROOT/logs/dfm10_tidsskrift_grounded_$(date +%Y%m%dT%H%M%S)}"

mkdir -p "$DATA_ROOT" "$LOG_ROOT"/{servers,workers,pids,queue/{pending,running,done,failed}}
exec 9>"$DATA_ROOT/campaign.lock"
flock -n 9 || { echo "Another Tidsskrift campaign holds $DATA_ROOT/campaign.lock"; exit 1; }
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

echo "$(date -Is) waiting for the all-article download to finish"
while pgrep -f '[p]repare_dfm10_tidsskrift_expansion.py download' >/dev/null; do sleep 30; done

echo "$(date -Is) retrying strict-open PDFs with a 512 MiB article limit"
"$HRM_PYTHON" scripts/prepare_dfm10_tidsskrift_expansion.py download \
  --min-abstract-chars 0 --max-bytes $((512 * 1024 * 1024)) --delay 1.5

echo "$(date -Is) extracting coherent article chunks"
while pgrep -f '[p]repare_dfm10_tidsskrift_grounded_sft.py .*extract' >/dev/null; do sleep 30; done
"$HRM_PYTHON" scripts/prepare_dfm10_tidsskrift_grounded_sft.py --data-root "$DATA_ROOT" extract --force
"$HRM_PYTHON" scripts/prepare_dfm10_tidsskrift_grounded_sft.py --data-root "$DATA_ROOT" prepare

candidate_rows="$(jq -r '.candidate_rows' "$DATA_ROOT/requests/summary.json")"
if (( candidate_rows < 180000 )); then
  echo "Only $candidate_rows candidate rows; require at least 180000" >&2
  exit 1
fi

echo "$(date -Is) waiting for the current Mimir Gemma 4 31B campaign lock"
exec 8>"$ROOT/data/mimir_grounded_500k_sft/campaign.lock"
flock 8

all_gpus_free() {
  local values value
  mapfile -t values < <(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)
  [[ "${#values[@]}" -eq 8 ]] || return 1
  for value in "${values[@]}"; do (( value <= FREE_THRESHOLD_MIB )) || return 1; done
}
echo "$(date -Is) waiting for all GPUs below ${FREE_THRESHOLD_MIB} MiB used"
until all_gpus_free; do sleep 30; done

mkdir -p "$DATA_ROOT"/{generated,audits,chat_generated,chat_audits,state/sft_done,state/chat_done}
mkdir -p "$DATA_ROOT/state/premature_done_archive"
for mode in sft chat; do
  if [[ "$mode" == "sft" ]]; then
    generated_dir=generated; audit_dir=audits
    verify_script=scripts/dfm10_tidsskrift_grounded_model.py
  else
    generated_dir=chat_generated; audit_dir=chat_audits
    verify_script=scripts/dfm10_tidsskrift_chats_model.py
  fi
  for marker in "$DATA_ROOT/state/${mode}_done"/*.done; do
    [[ -e "$marker" ]] || continue
    base="$(basename "$marker" .done)"
    if ! "$PYTHON" "$verify_script" verify-shard \
        --requests "$DATA_ROOT/requests/shards/$base" \
        --generated "$DATA_ROOT/$generated_dir/$base" \
        --audited "$DATA_ROOT/$audit_dir/$base" \
        --minimum-completion-fraction 1.0 >/dev/null; then
      mv "$marker" "$DATA_ROOT/state/premature_done_archive/${mode}__$(basename "$marker")"
    fi
  done
done
for shard in "$DATA_ROOT"/requests/shards/part-*.jsonl; do
  base="$(basename "$shard")"
  if [[ ! -f "$DATA_ROOT/state/sft_done/${base}.done" ]]; then
    printf 'MODE=sft\nSHARD=%q\n' "$shard" > "$LOG_ROOT/queue/pending/sft__${base}.job"
  fi
  if [[ ! -f "$DATA_ROOT/state/chat_done/${base}.done" ]]; then
    printf 'MODE=chat\nSHARD=%q\n' "$shard" > "$LOG_ROOT/queue/pending/chat__${base}.job"
  fi
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
  wait_server "$((PORT_BASE + gpu))" "${server_pids[$gpu]}" || {
    echo "GPU $gpu Gemma 4 31B server failed to become ready" >&2
    exit 1
  }
done

claim() {
  local gpu="$1" pattern job destination
  for pattern in 'chat__*.job' 'sft__*.job'; do
    while IFS= read -r -d '' job; do
      destination="$LOG_ROOT/queue/running/gpu${gpu}__$(basename "$job")"
      if mv "$job" "$destination" 2>/dev/null; then printf '%s\n' "$destination"; return 0; fi
    done < <(find "$LOG_ROOT/queue/pending" -maxdepth 1 -name "$pattern" -print0 | sort -z)
  done
  return 1
}

worker() {
  local gpu="$1" port=$((PORT_BASE + gpu)) claimed shard base generated audit log pass verified mode minimum_completion_fraction
  log=""
  while claimed="$(claim "$gpu")"; do
    # shellcheck disable=SC1090
    source "$claimed"
    shard="$SHARD"; mode="$MODE"; base="$(basename "$shard")"
    if [[ "$mode" == "sft" ]]; then
      generated="$DATA_ROOT/generated/$base"; audit="$DATA_ROOT/audits/$base"
    else
      generated="$DATA_ROOT/chat_generated/$base"; audit="$DATA_ROOT/chat_audits/$base"
    fi
    log="$LOG_ROOT/workers/${mode}__${base}_gpu${gpu}.log"
    verified=0
    for pass in 1 2 3 4; do
      if [[ "$mode" == "sft" ]]; then
        "$PYTHON" scripts/dfm10_tidsskrift_grounded_model.py --data-root "$DATA_ROOT" generate \
          --input "$shard" --output "$generated" --base-url "http://127.0.0.1:${port}/v1" \
          --model "$MODEL_NAME" --concurrency "$CONCURRENCY" --max-tokens 4096 >>"$log" 2>&1
        "$PYTHON" scripts/dfm10_tidsskrift_grounded_model.py --data-root "$DATA_ROOT" audit \
          --input "$generated" --requests "$shard" --output "$audit" \
          --base-url "http://127.0.0.1:${port}/v1" --model "$MODEL_NAME" \
          --concurrency "$CONCURRENCY" --max-tokens 4096 >>"$log" 2>&1
        verify_script="scripts/dfm10_tidsskrift_grounded_model.py"
      else
        "$PYTHON" scripts/dfm10_tidsskrift_chats_model.py --data-root "$DATA_ROOT" generate \
          --input "$shard" --output "$generated" --base-url "http://127.0.0.1:${port}/v1" \
          --model "$MODEL_NAME" --concurrency "$CONCURRENCY" --max-tokens 4096 >>"$log" 2>&1
        "$PYTHON" scripts/dfm10_tidsskrift_chats_model.py --data-root "$DATA_ROOT" audit \
          --input "$generated" --requests "$shard" --output "$audit" \
          --base-url "http://127.0.0.1:${port}/v1" --model "$MODEL_NAME" \
          --concurrency "$CONCURRENCY" --max-tokens 4096 >>"$log" 2>&1
        verify_script="scripts/dfm10_tidsskrift_chats_model.py"
      fi
      minimum_completion_fraction=1.0
      if "$PYTHON" "$verify_script" verify-shard \
          --requests "$shard" --generated "$generated" --audited "$audit" \
          --minimum-completion-fraction "$minimum_completion_fraction" >>"$log" 2>&1; then
        verified=1
        break
      fi
    done
    if (( verified )); then
      date -Is > "$DATA_ROOT/state/${mode}_done/${base}.done"
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
sft_done="$(find "$DATA_ROOT/state/sft_done" -maxdepth 1 -name '*.done' | wc -l)"
chat_done="$(find "$DATA_ROOT/state/chat_done" -maxdepth 1 -name '*.done' | wc -l)"
echo "$(date -Is) generation/audit sft=$sft_done/$SHARDS chats=$chat_done/$SHARDS failed=$failed"
(( failed == 0 && sft_done == SHARDS && chat_done == SHARDS )) || exit 1

"$HRM_PYTHON" scripts/dfm10_tidsskrift_grounded_model.py --data-root "$DATA_ROOT" build
"$HRM_PYTHON" scripts/dfm10_tidsskrift_chats_model.py --data-root "$DATA_ROOT" build \
  --minimum-chats 18000 --minimum-assistant-turns 100000
"$HRM_PYTHON" scripts/prepare_dfm10_hf_exports.py --dataset dfm10-tidsskrift-open-sft --force
"$HRM_PYTHON" scripts/prepare_dfm10_hf_exports.py --dataset dfm10-tidsskrift-open-chats --force
"$HRM_PYTHON" scripts/tokenize_chat_template.py \
  data/dfm10_tidsskrift_open_sft_source --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template data_io/chat_templates/gemma4_native_chat.jinja \
  --output-dir data/tokenized_dfm10_tidsskrift_open --workers 16 --force
"$HRM_PYTHON" scripts/tokenize_chat_template.py \
  data/dfm10_tidsskrift_open_chats_source --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template data_io/chat_templates/gemma4_native_chat.jinja \
  --output-dir data/tokenized_dfm10_tidsskrift_open_chats --workers 16 --force
"$HRM_PYTHON" scripts/build_tokenized_dfm10_tree.py --force
echo "$(date -Is) Tidsskrift open SFT and chats built, packaged, and tokenized"
