#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REQUESTS="${REQUESTS:-data/wiki_cat_sum_recovery/requests.jsonl}"
GEN_ROOT="${GEN_ROOT:-logs/data_audits/wiki_cat_sum_recovery_31b_20260829}"
AUDIT_ROOT="${AUDIT_ROOT:-logs/data_audits/wiki_cat_sum_recovery_e4b_20260829}"
CANDIDATES="${CANDIDATES:-data/converted_sources/wiki_cat_sum_recovery_candidates}"
OUTPUT="${OUTPUT:-data/converted_sources/wiki_cat_sum_repaired_with_recovery}"
GEN_MODEL_PATH="${GEN_MODEL_PATH:-data/models/google/gemma-4-31B-it-fresh-20260604}"
GEN_MODEL_NAME="${GEN_MODEL_NAME:-openai/gemma-4-31b-wikicat-recovery}"
AUDIT_MODEL_PATH="${AUDIT_MODEL_PATH:-data/models/google/gemma-4-E4B-it}"
AUDIT_MODEL_NAME="${AUDIT_MODEL_NAME:-openai/gemma-4-e4b-wikicat-recovery-audit}"
VLLM_PYTHON="${VLLM_PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
CLIENT_PYTHON="${CLIENT_PYTHON:-/home/ucloud/miniforge3/envs/hrm-cu132/bin/python}"
CHAT_TEMPLATE="${CHAT_TEMPLATE:-data_io/chat_templates/gemma4_native_chat.jinja}"
TOKENIZER_PATH="${TOKENIZER_PATH:-/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json}"
CONCURRENCY="${CONCURRENCY:-64}"
PORT_BASE="${PORT_BASE:-8980}"
POLL_SECONDS="${POLL_SECONDS:-10}"
STABLE_SECONDS="${STABLE_SECONDS:-30}"
START_PHASE="${START_PHASE:-generation}"
AUDIT_GPU_UTILIZATION="${AUDIT_GPU_UTILIZATION:-0.90}"

case "$START_PHASE" in
  generation|audit) ;;
  *) echo "START_PHASE must be generation or audit, got: $START_PHASE" >&2; exit 2 ;;
esac

mkdir -p "$GEN_ROOT"/{partitions,servers,pids,cache} "$AUDIT_ROOT"/{results,servers,workers,pids,cache}
exec > >(tee -a "$GEN_ROOT/launcher.log") 2>&1
exec 9>"$GEN_ROOT/launcher.lock"
flock -n 9 || { echo "Another WikiCatSum recovery launcher is active" >&2; exit 2; }

SERVER_PIDS=()
WORKER_PIDS=()
cleanup() {
  local pid
  for pid in "${WORKER_PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  for pid in "${SERVER_PIDS[@]:-}"; do kill -TERM -- "-$pid" 2>/dev/null || true; done
  sleep 2
  for pid in "${SERVER_PIDS[@]:-}"; do kill -KILL -- "-$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; done
  SERVER_PIDS=()
  WORKER_PIDS=()
}
trap cleanup EXIT INT TERM

wait_for_idle() {
  local stable_since=0
  echo "Waiting for all GPUs to remain process-free for ${STABLE_SECONDS}s."
  while true; do
    if [[ -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader,nounits 2>/dev/null | sed '/^[[:space:]]*$/d')" ]]; then
      (( stable_since > 0 )) || stable_since="$(date +%s)"
      (( $(date +%s) - stable_since >= STABLE_SECONDS )) && return
    else
      stable_since=0
    fi
    sleep "$POLL_SECONDS"
  done
}

start_servers() {
  local model_path="$1" model_name="$2" max_len="$3" utilization="$4" phase="$5"
  local gpu port pid
  SERVER_PIDS=()
  for gpu in {0..7}; do
    port=$((PORT_BASE + gpu))
    CUDA_VISIBLE_DEVICES="$gpu" \
      CUDA_HOME="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}" \
      PATH="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}/bin:/home/ucloud/miniforge3/envs/audit/bin:$PATH" \
      LD_LIBRARY_PATH="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}/lib:${LD_LIBRARY_PATH:-}" \
      VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_DISABLE_VERSION_CHECK=1 \
      TORCHINDUCTOR_CACHE_DIR="$GEN_ROOT/cache/${phase}_gpu${gpu}/torchinductor" \
      TRITON_CACHE_DIR="$GEN_ROOT/cache/${phase}_gpu${gpu}/triton" \
      setsid "$VLLM_PYTHON" -m vllm.entrypoints.openai.api_server \
        --model "$model_path" --served-model-name "$model_name" \
        --hf-overrides '{"architectures":["Gemma4ForCausalLM"]}' \
        --chat-template "$CHAT_TEMPLATE" --host 127.0.0.1 --port "$port" \
        --max-model-len "$max_len" --gpu-memory-utilization "$utilization" \
        --max-num-seqs 64 --enforce-eager \
        >"$GEN_ROOT/servers/${phase}_gpu${gpu}.log" 2>&1 &
    pid=$!
    SERVER_PIDS+=("$pid")
    echo "$pid" >"$GEN_ROOT/pids/${phase}_gpu${gpu}.pid"
  done
  for gpu in {0..7}; do
    port=$((PORT_BASE + gpu))
    local deadline=$((SECONDS + 1200))
    until curl -fsS "http://127.0.0.1:${port}/v1/models" >/dev/null 2>&1; do
      kill -0 "${SERVER_PIDS[$gpu]}" 2>/dev/null || { echo "${phase} GPU${gpu} server exited" >&2; return 1; }
      (( SECONDS <= deadline )) || { echo "${phase} GPU${gpu} startup timed out" >&2; return 1; }
      sleep 2
    done
  done
}

run_generation() {
  local pass gpu status pid
  for pass in 1 2 3 4; do
    echo "31B generation pass ${pass}/4."
    WORKER_PIDS=()
    for gpu in {0..7}; do
      "$CLIENT_PYTHON" scripts/generate_wiki_cat_sum_recovery.py generate \
        --requests "$REQUESTS" --output "$GEN_ROOT/partitions/partition_${gpu}.jsonl" \
        --base-url "http://127.0.0.1:$((PORT_BASE + gpu))/v1" --model "$GEN_MODEL_NAME" \
        --partitions 8 --partition-index "$gpu" --concurrency "$CONCURRENCY" --resume \
        >"$GEN_ROOT/partitions/partition_${gpu}.log" 2>&1 &
      WORKER_PIDS+=("$!")
    done
    status=0
    for pid in "${WORKER_PIDS[@]}"; do wait "$pid" || status=1; done
    WORKER_PIDS=()
    (( status == 0 )) && return
  done
  "$CLIENT_PYTHON" scripts/generate_wiki_cat_sum_recovery.py fail-close-errors \
    --partition-root "$GEN_ROOT/partitions" --partitions 8 --expected-model "$GEN_MODEL_NAME"
}

run_audit() {
  local pass gpu status pid
  for pass in 1 2 3 4; do
    echo "E4B audit pass ${pass}/4."
    WORKER_PIDS=()
    for gpu in {0..7}; do
      "$CLIENT_PYTHON" scripts/audit_wiki_cat_sum_recovery.py audit \
        --audit-dir "$AUDIT_ROOT" --partition-index "$gpu" \
        --base-url "http://127.0.0.1:$((PORT_BASE + gpu))/v1" --model "$AUDIT_MODEL_NAME" \
        --concurrency "$CONCURRENCY" >"$AUDIT_ROOT/workers/partition_${gpu}.log" 2>&1 &
      WORKER_PIDS+=("$!")
    done
    status=0
    for pid in "${WORKER_PIDS[@]}"; do wait "$pid" || status=1; done
    WORKER_PIDS=()
    (( status == 0 )) && return
  done
  echo "Fail-closing judge-format failures remaining after four audit passes."
  "$CLIENT_PYTHON" scripts/audit_wiki_cat_sum_recovery.py fail-close \
    --audit-dir "$AUDIT_ROOT" --partitions 8 --model "$AUDIT_MODEL_NAME"
}

[[ -s "$REQUESTS" ]] || { echo "Missing prepared requests: $REQUESTS" >&2; exit 1; }
if [[ "$START_PHASE" == generation ]]; then
  wait_for_idle
  echo "Starting 31B WikiCatSum source-grounded generation."
  start_servers "$GEN_MODEL_PATH" "$GEN_MODEL_NAME" 16384 0.70 generation
  run_generation
  "$CLIENT_PYTHON" scripts/generate_wiki_cat_sum_recovery.py merge \
    --requests "$REQUESTS" --partition-root "$GEN_ROOT/partitions" --partitions 8 \
    --output "$GEN_ROOT/generations.jsonl" --expected-model "$GEN_MODEL_NAME"
  "$CLIENT_PYTHON" scripts/prepare_wiki_cat_sum_recovery.py build \
    --requests "$REQUESTS" --generations "$GEN_ROOT/generations.jsonl" \
    --output-dir "$CANDIDATES" --force
  cleanup
fi

"$CLIENT_PYTHON" scripts/audit_wiki_cat_sum_recovery.py prepare \
  --input-dir "$CANDIDATES" --audit-dir "$AUDIT_ROOT" --partitions 8
wait_for_idle
echo "Starting independent E4B WikiCatSum recovery audit."
start_servers "$AUDIT_MODEL_PATH" "$AUDIT_MODEL_NAME" 8192 "$AUDIT_GPU_UTILIZATION" audit
run_audit
"$CLIENT_PYTHON" scripts/audit_wiki_cat_sum_recovery.py merge \
  --audit-dir "$AUDIT_ROOT" --partitions 8 --model "$AUDIT_MODEL_NAME"
cleanup

"$CLIENT_PYTHON" scripts/prepare_wiki_cat_sum_recovery.py finalize \
  --candidate-dir "$CANDIDATES" --audit-dir "$AUDIT_ROOT" --output-dir "$OUTPUT" --force
STAGE="data/dfm10_wiki_cat_sum_repaired_sources"
rm -rf "$STAGE"
mkdir -p "$STAGE"
ln -s "$(realpath "$OUTPUT")" "$STAGE/wiki_cat_sum_repaired"
TOKENIZED_OUTPUT="data/tokenized_dfm10_wiki_cat_sum_repaired"
TOKENIZED_TMP="${TOKENIZED_OUTPUT}.tmp"
TOKENIZED_PREVIOUS="${TOKENIZED_OUTPUT}.previous"
rm -rf "$TOKENIZED_TMP" "$TOKENIZED_PREVIOUS"
"$CLIENT_PYTHON" scripts/tokenize_chat_template.py "$STAGE" \
  --tokenizer-path "$TOKENIZER_PATH" --chat-template "$CHAT_TEMPLATE" \
  --output-dir "$TOKENIZED_TMP" --workers 16 --force
printf 'complete\n' > "$TOKENIZED_TMP/.recovery_complete"
[[ ! -e "$TOKENIZED_OUTPUT" ]] || mv "$TOKENIZED_OUTPUT" "$TOKENIZED_PREVIOUS"
mv "$TOKENIZED_TMP" "$TOKENIZED_OUTPUT"
rm -rf "$TOKENIZED_PREVIOUS"
echo "WikiCatSum generated recovery, strict audit, union, and tokenization complete."
