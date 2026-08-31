#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/work/dfm/HRM-Text"
PLAN_DIR="$REPO_ROOT/logs/scheduler/mimir_v1_mmlu_corrected_20260829"
ROOT="$REPO_ROOT/logs/analysis/mimir_v1_mmlu_failure_ontology"
REQUESTS="$ROOT/quarantined_ontology_requests.jsonl"
PARTITIONS="$ROOT/ontology_partitions"
MODEL_PATH="$REPO_ROOT/data/models/google/gemma-4-31B-it-fresh-20260604"
MODEL_NAME="openai/gemma-4-31b-mimir-ontology"
PYTHON="/home/ucloud/miniforge3/envs/audit/bin/python"
CLIENT_PYTHON="/home/ucloud/miniforge3/envs/hrm-cu132/bin/python"
LOG_ROOT="$ROOT/run_$(date +%Y%m%dT%H%M%S)"
LOCK_FILE="$ROOT/ontology_runner.lock"

mkdir -p "$PARTITIONS" "$LOG_ROOT/servers"
exec 9>"$LOCK_FILE"
flock -n 9 || { echo "Another Mimir ontology runner holds $LOCK_FILE"; exit 1; }

exec > >(tee -a "$LOG_ROOT/runner.log") 2>&1
cd "$REPO_ROOT"

if [[ ! -s "$REQUESTS" ]]; then
  echo "Missing ontology requests: $REQUESTS" >&2
  exit 1
fi

echo "Waiting for WikiCat recovery and corrected MMLU evaluation to finish."
while pgrep -f '[r]un_wiki_cat_sum_recovery_when_free.sh|[g]enerate_wiki_cat_sum_recovery.py generate' >/dev/null; do
  sleep 60
done
while awk -F '\t' 'NR>1 && ($12 == "pending" || $12 == "running") {found=1} END {exit !found}' "$PLAN_DIR/plan.tsv"; do
  sleep 60
done

echo "Waiting for the queued OpenStax Mimir pilot to finish."
while pgrep -f '[r]un_openstax_mimir_sft_after_current_work.sh|[r]un_openstax_mimir_sft_pilot_8gpu.sh|[o]penstax_sft_model.py' >/dev/null; do
  sleep 60
done

echo "Waiting for all eight GPUs to have at least 175000 MiB free."
while true; do
  ready=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | awk '$1 >= 175000 {n++} END {print n+0}')
  [[ "$ready" -eq 8 ]] && break
  sleep 60
done

server_pids=()
client_pids=()
cleanup() {
  for pid in "${client_pids[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  for pid in "${server_pids[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  for pid in "${client_pids[@]:-}" "${server_pids[@]:-}"; do
    [[ -n "$pid" ]] && wait "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

for gpu in $(seq 0 7); do
  port=$((8990 + gpu))
  CUDA_VISIBLE_DEVICES="$gpu" "$PYTHON" -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" \
    --served-model-name "$MODEL_NAME" \
    --hf-overrides '{"architectures":["Gemma4ForCausalLM"]}' \
    --chat-template "$REPO_ROOT/data_io/chat_templates/gemma4_native_chat.jinja" \
    --host 127.0.0.1 \
    --port "$port" \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.70 \
    --max-num-seqs 64 \
    --enforce-eager \
    >"$LOG_ROOT/servers/gpu${gpu}.log" 2>&1 &
  server_pids+=("$!")
done

for gpu in $(seq 0 7); do
  port=$((8990 + gpu))
  until curl -fsS "http://127.0.0.1:${port}/v1/models" >/dev/null; do
    kill -0 "${server_pids[$gpu]}" 2>/dev/null || {
      echo "Ontology vLLM server on GPU $gpu exited during startup" >&2
      exit 1
    }
    sleep 5
  done
done

for gpu in $(seq 0 7); do
  port=$((8990 + gpu))
  "$CLIENT_PYTHON" scripts/classify_mimir_mmlu_failure_ontology.py classify \
    --requests "$REQUESTS" \
    --output "$PARTITIONS/partition_${gpu}.jsonl" \
    --base-url "http://127.0.0.1:${port}/v1" \
    --model "$MODEL_NAME" \
    --partitions 8 \
    --partition-index "$gpu" \
    --concurrency 64 \
    --retries 3 \
    --resume \
    >"$LOG_ROOT/client_gpu${gpu}.log" 2>&1 &
  client_pids+=("$!")
done

failed=0
for pid in "${client_pids[@]}"; do
  wait "$pid" || failed=1
done
client_pids=()
[[ "$failed" -eq 0 ]] || { echo "At least one ontology classifier failed" >&2; exit 1; }

"$CLIENT_PYTHON" scripts/classify_mimir_mmlu_failure_ontology.py aggregate \
  --partitions "$PARTITIONS" \
  --output "$ROOT/ontology_aggregate_k10.json" \
  --min-cell-count 10

echo "Ontology classification complete: $ROOT/ontology_aggregate_k10.json"
