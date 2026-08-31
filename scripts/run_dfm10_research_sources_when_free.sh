#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
HRM_PYTHON="${HRM_PYTHON:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
TEACHER_PATH="${TEACHER_PATH:-$ROOT/data/models/google/gemma-4-31B-it-fresh-20260604}"
TEACHER_NAME="${TEACHER_NAME:-dfm10-diem-gemma4-31b}"
JUDGE_PATH="${JUDGE_PATH:-/work/dfm/jacobwashere/brainsurgery/models/google/gemma-4-E4B-it}"
JUDGE_NAME="${JUDGE_NAME:-openai/gemma-4-e4b-research-judge}"
TOKENIZER_PATH="${TOKENIZER_PATH:-/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json}"
CHAT_TEMPLATE="${CHAT_TEMPLATE:-$ROOT/data_io/chat_templates/gemma4_native_chat.jinja}"
WORK_ROOT="${WORK_ROOT:-$ROOT/data/dfm10_research_sources_campaign}"
LOG_ROOT="${LOG_ROOT:-$ROOT/logs/dfm10_research_sources_$(date +%Y%m%dT%H%M%S)}"
PORT_BASE="${PORT_BASE:-8980}"
CONCURRENCY="${CONCURRENCY:-64}"
FREE_THRESHOLD_MIB="${FREE_THRESHOLD_MIB:-3000}"

mkdir -p "$WORK_ROOT" "$LOG_ROOT"/{servers,workers,pids,cache}
exec 9>"$WORK_ROOT/campaign.lock"
flock -n 9 || { echo "Another research-source campaign is active"; exit 1; }
exec > >(tee -a "$LOG_ROOT/runner.log") 2>&1
printf '%s\n' "$LOG_ROOT" > "$WORK_ROOT/current_run_log_root.txt"

# Serialize with the current Tidsskrift/Mimir fleets. Holding this descriptor
# across the campaign prevents another shared-fleet watcher from racing us.
exec 8>"$ROOT/data/mimir_grounded_500k_sft/campaign.lock"
echo "$(date -Is) queued behind the active shared GPU campaign"
flock 8

all_gpus_free() {
  local values value
  mapfile -t values < <(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)
  [[ "${#values[@]}" -eq 8 ]] || return 1
  for value in "${values[@]}"; do (( value <= FREE_THRESHOLD_MIB )) || return 1; done
}
echo "$(date -Is) waiting for all GPUs below ${FREE_THRESHOLD_MIB} MiB used"
until all_gpus_free; do sleep 30; done

server_pids=()
worker_pids=()
cleanup_fleet() {
  local pid
  for pid in "${worker_pids[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  for pid in "${server_pids[@]:-}"; do kill -TERM -- "-$pid" 2>/dev/null || true; done
  sleep 3
  for pid in "${server_pids[@]:-}"; do kill -KILL -- "-$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; done
  worker_pids=(); server_pids=()
}
trap cleanup_fleet EXIT INT TERM

wait_server() {
  local port="$1" pid="$2" deadline=$((SECONDS + 1200))
  until curl -fsS "http://127.0.0.1:${port}/v1/models" >/dev/null 2>&1; do
    kill -0 "$pid" 2>/dev/null || return 1
    (( SECONDS < deadline )) || return 1
    sleep 2
  done
}

start_fleet() {
  local model_path="$1" model_name="$2" utilization="$3" max_len="$4" gpu port cache pid
  server_pids=()
  for gpu in $(seq 0 7); do
    port=$((PORT_BASE + gpu)); cache="$LOG_ROOT/cache/${model_name//\//_}_gpu${gpu}"
    mkdir -p "$cache"
    CUDA_VISIBLE_DEVICES="$gpu" CUDA_HOME="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}" \
      PATH="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}/bin:/home/ucloud/miniforge3/envs/audit/bin:$PATH" \
      LD_LIBRARY_PATH="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}/lib:${LD_LIBRARY_PATH:-}" \
      VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_DISABLE_VERSION_CHECK=1 \
      TORCHINDUCTOR_CACHE_DIR="$cache/torchinductor" TRITON_CACHE_DIR="$cache/triton" \
      setsid "$PYTHON" -m vllm.entrypoints.openai.api_server \
        --model "$model_path" --served-model-name "$model_name" \
        --hf-overrides '{"architectures":["Gemma4ForCausalLM"]}' \
        --chat-template "$CHAT_TEMPLATE" --host 127.0.0.1 --port "$port" \
        --max-model-len "$max_len" --gpu-memory-utilization "$utilization" \
        --max-num-seqs 64 --enforce-eager \
        >"$LOG_ROOT/servers/${model_name//\//_}_gpu${gpu}.log" 2>&1 &
    pid=$!; server_pids+=("$pid"); echo "$pid" >"$LOG_ROOT/pids/server_gpu${gpu}.pid"
  done
  for gpu in $(seq 0 7); do wait_server "$((PORT_BASE + gpu))" "${server_pids[$gpu]}"; done
}

echo "$(date -Is) preparing audit samples and DiEm shards"
"$HRM_PYTHON" scripts/prepare_dfm10_research_source_audit.py prepare \
  --output "$WORK_ROOT/samples.jsonl" --inventory "$WORK_ROOT/sample_inventory.json" --samples-per-source 100
"$HRM_PYTHON" scripts/prepare_dfm10_research_source_audit.py shard-diem \
  --input data/dfm10_diem_modernization/requests.jsonl --output-dir "$WORK_ROOT/diem_requests" --partitions 8

echo "$(date -Is) starting Gemma 4 31B DiEm generation"
start_fleet "$TEACHER_PATH" "$TEACHER_NAME" 0.70 8192
for gpu in $(seq 0 7); do
  "$PYTHON" scripts/run_dfm10_dynaword_sft.py generate \
    --input "$WORK_ROOT/diem_requests/partition_${gpu}.jsonl" \
    --output "$WORK_ROOT/diem_generated_${gpu}.jsonl" \
    --base-url "http://127.0.0.1:$((PORT_BASE + gpu))/v1" --model "$TEACHER_NAME" \
    --concurrency "$CONCURRENCY" >"$LOG_ROOT/workers/diem_generate_gpu${gpu}.log" 2>&1 &
  worker_pids+=("$!")
done
for pid in "${worker_pids[@]}"; do wait "$pid"; done
worker_pids=(); cleanup_fleet

echo "$(date -Is) starting independent E4B audits"
start_fleet "$JUDGE_PATH" "$JUDGE_NAME" 0.90 8192
for gpu in $(seq 0 7); do
  "$PYTHON" scripts/run_dfm10_dynaword_sft.py audit \
    --requests "$WORK_ROOT/diem_requests/partition_${gpu}.jsonl" \
    --generated "$WORK_ROOT/diem_generated_${gpu}.jsonl" \
    --output "$WORK_ROOT/diem_audited_${gpu}.jsonl" \
    --base-url "http://127.0.0.1:$((PORT_BASE + gpu))/v1" --model "$JUDGE_NAME" \
    --concurrency "$CONCURRENCY" >"$LOG_ROOT/workers/diem_audit_gpu${gpu}.log" 2>&1 &
  worker_pids+=("$!")
  "$PYTHON" scripts/dfm10_quality_audit.py audit \
    --samples "$WORK_ROOT/samples.jsonl" --output "$WORK_ROOT/research_audit_partition_${gpu}.jsonl" \
    --base-url "http://127.0.0.1:$((PORT_BASE + gpu))/v1" --model "$JUDGE_NAME" \
    --partitions 8 --partition-index "$gpu" --concurrency "$CONCURRENCY" --resume \
    >"$LOG_ROOT/workers/research_audit_gpu${gpu}.log" 2>&1 &
  worker_pids+=("$!")
done
for pid in "${worker_pids[@]}"; do wait "$pid"; done
worker_pids=(); cleanup_fleet

mkdir -p "$WORK_ROOT/research_partitions"
for gpu in $(seq 0 7); do
  mv "$WORK_ROOT/research_audit_partition_${gpu}.jsonl" "$WORK_ROOT/research_partitions/partition_${gpu}.jsonl"
done
"$HRM_PYTHON" scripts/dfm10_quality_audit.py merge \
  --samples "$WORK_ROOT/samples.jsonl" --partition-root "$WORK_ROOT/research_partitions" \
  --partitions 8 --output "$WORK_ROOT/research_audit.jsonl"
"$HRM_PYTHON" scripts/prepare_dfm10_research_source_audit.py check \
  --input "$WORK_ROOT/research_audit.jsonl" --output "$WORK_ROOT/research_audit_gate.json"

cat "$WORK_ROOT"/diem_generated_*.jsonl >"$WORK_ROOT/generated.jsonl.tmp"
mv "$WORK_ROOT/generated.jsonl.tmp" data/dfm10_diem_modernization/generated.jsonl
cat "$WORK_ROOT"/diem_audited_*.jsonl >"$WORK_ROOT/audited.jsonl.tmp"
mv "$WORK_ROOT/audited.jsonl.tmp" data/dfm10_diem_modernization/audited.jsonl
"$HRM_PYTHON" scripts/run_dfm10_dynaword_sft.py build \
  --requests data/dfm10_diem_modernization/requests.jsonl \
  --generated data/dfm10_diem_modernization/generated.jsonl \
  --audited data/dfm10_diem_modernization/audited.jsonl \
  --output data/converted_sources/diem_modernization/diem_modernization__accepted.jsonl
"$HRM_PYTHON" scripts/validate_dfm10_diem_modernization.py
"$HRM_PYTHON" scripts/tokenize_chat_template.py data/converted_sources/diem_modernization \
  --tokenizer-path "$TOKENIZER_PATH" --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_diem_modernization --workers 16 --force
"$HRM_PYTHON" scripts/prepare_dfm10_hf_exports.py --dataset dfm10-diem-historical-modernization --force
"$HRM_PYTHON" scripts/build_tokenized_dfm10_tree.py --force
"$HRM_PYTHON" scripts/prepare_dfm10_hf_exports.py --refresh-inventory
echo "$(date -Is) research-source generation, audits, tokenization, packaging, and union integration complete"
