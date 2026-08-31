#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
GPU="${GPU:-2}"
PORT="${PORT:-8922}"
GEN_ROOT="logs/data_audits/danmarks_statistik_bt_prompt_repair_20260829"
AUDIT_ROOT="logs/data_audits/danmarks_statistik_bt_repaired_20260829"
REQUESTS="data/danmarks_statistik_bt_repair/prompt_repair_requests.jsonl"
MODEL_PATH="${MODEL_PATH:-/work/dfm/jacobwashere/brainsurgery/models/google/gemma-4-E4B-it}"
MODEL_NAME="openai/gemma-4-e4b-dst-repair"
VLLM_PYTHON="${VLLM_PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
CLIENT_PYTHON="${CLIENT_PYTHON:-/home/ucloud/miniforge3/envs/hrm-cu132/bin/python}"
mkdir -p "$GEN_ROOT"/{servers,pids,cache} "$AUDIT_ROOT"/{partitions,results,workers}
exec 9>"$GEN_ROOT/gpu${GPU}-continuation.lock"; flock -n 9 || exit 2
exec {gpu_lock}>"/tmp/hrm-gpu-${GPU}.lock"; flock "$gpu_lock"
[[ -z "$(nvidia-smi -i "$GPU" --query-compute-apps=pid --format=csv,noheader,nounits | sed '/^[[:space:]]*$/d')" ]] || {
  echo "GPU${GPU} became busy before continuation startup" >&2; exit 1;
}
exec > >(tee -a "$GEN_ROOT/gpu${GPU}-continuation.log") 2>&1

CUDA_VISIBLE_DEVICES="$GPU" VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_DISABLE_VERSION_CHECK=1 \
  VLLM_DEEP_GEMM_WARMUP=skip \
  TORCHINDUCTOR_CACHE_DIR="$GEN_ROOT/cache/gpu${GPU}/torchinductor" \
  TRITON_CACHE_DIR="$GEN_ROOT/cache/gpu${GPU}/triton" \
  setsid "$VLLM_PYTHON" -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" --served-model-name "$MODEL_NAME" \
    --host 127.0.0.1 --port "$PORT" --max-model-len 8192 \
    --gpu-memory-utilization 0.90 --max-num-seqs 64 --enforce-eager \
    >"$GEN_ROOT/servers/gpu${GPU}-continuation.log" 2>&1 &
server_pid=$!
cleanup() { kill -TERM -- "-$server_pid" 2>/dev/null || true; wait "$server_pid" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

deadline=$((SECONDS + 900))
until curl -fsS "http://127.0.0.1:${PORT}/v1/models" >/dev/null 2>&1; do
  kill -0 "$server_pid" 2>/dev/null || exit 1
  (( SECONDS <= deadline )) || exit 1
  sleep 2
done

echo "Retrying incomplete prompt-generation partitions on GPU${GPU}."
for partition in 0 1 2 3 4 5 6 7; do
  if ! "$CLIENT_PYTHON" scripts/generate_danmarks_statistik_bt_prompts.py generate \
      --requests "$REQUESTS" --output "$GEN_ROOT/partitions/partition_${partition}.jsonl" \
      --base-url "http://127.0.0.1:${PORT}/v1" --model "$MODEL_NAME" \
      --partitions 8 --partition-index "$partition" --concurrency 64 --resume \
      >>"$GEN_ROOT/partitions/partition_${partition}.log" 2>&1; then
    echo "Partition ${partition} retains a persistent generation failure; sealing it as rejected."
  fi
done

# Rows that still fail after the original campaign and two retry campaigns are
# fail-closed as generator rejections. They cannot enter the training corpus.
"$CLIENT_PYTHON" - "$GEN_ROOT/partitions" <<'PY'
import json
import os
import sys
from pathlib import Path

root = Path(sys.argv[1])
sealed = 0
for path in sorted(root.glob("partition_*.jsonl")):
    rows = []
    for line in path.open(encoding="utf-8"):
        row = json.loads(line)
        if "generation_error" in row:
            row = {
                "sample_id": row["sample_id"],
                "source_row": row["source_row"],
                "usable": False,
                "generated_prompt": "",
                "reason": "terminal rejection after exhausted prompt-generation retries",
                "audit_resolution": "terminal_generator_rejection",
            }
            sealed += 1
        rows.append(row)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(temporary, path)
print(f"sealed persistent generation failures: {sealed}")
PY

"$CLIENT_PYTHON" scripts/generate_danmarks_statistik_bt_prompts.py merge \
  --requests "$REQUESTS" --partition-root "$GEN_ROOT/partitions" --partitions 8 \
  --output "$GEN_ROOT/prompt_repairs.jsonl"
"$CLIENT_PYTHON" scripts/repair_danmarks_statistik_bt.py build \
  --generated "$GEN_ROOT/prompt_repairs.jsonl" \
  --output-dir data/converted_sources/danmarks_statistik_bt_repaired_candidates --force
"$CLIENT_PYTHON" scripts/audit_repaired_danmarks_statistik_bt.py prepare \
  --input-dir data/converted_sources/danmarks_statistik_bt_repaired_candidates \
  --audit-dir "$AUDIT_ROOT" --samples 0 --partitions 8

echo "Auditing all candidate rows with eight clients sharing GPU${GPU}."
worker_pids=()
for partition in 0 1 2 3 4 5 6 7; do
  "$CLIENT_PYTHON" scripts/audit_repaired_danmarks_statistik_bt.py audit \
    --audit-dir "$AUDIT_ROOT" --partition-index "$partition" \
    --base-url "http://127.0.0.1:${PORT}/v1" --model "$MODEL_NAME" \
    --concurrency 8 >"$AUDIT_ROOT/workers/partition_${partition}.log" 2>&1 &
  worker_pids+=("$!")
done
status=0
for pid in "${worker_pids[@]}"; do wait "$pid" || status=1; done
(( status == 0 )) || exit "$status"
"$CLIENT_PYTHON" scripts/audit_repaired_danmarks_statistik_bt.py merge \
  --audit-dir "$AUDIT_ROOT" --partitions 8 --model "$MODEL_NAME"
"$CLIENT_PYTHON" scripts/audit_repaired_danmarks_statistik_bt.py filter \
  --input-dir data/converted_sources/danmarks_statistik_bt_repaired_candidates \
  --audit-dir "$AUDIT_ROOT" --output-dir data/converted_sources/danmarks_statistik_bt_repaired --force

stage=data/dfm10_danmarks_statistik_bt_repaired_sources
mkdir -p "$stage"; find "$stage" -mindepth 1 -maxdepth 1 -delete
ln -s "$(realpath data/converted_sources/danmarks_statistik_bt_repaired)" \
  "$stage/danmarks_statistik_bt_repaired"
"$CLIENT_PYTHON" scripts/tokenize_chat_template.py "$stage" \
  --tokenizer-path /work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json \
  --chat-template data_io/chat_templates/gemma4_native_chat.jinja \
  --output-dir data/tokenized_dfm10_danmarks_statistik_bt_repaired --workers 16 --force
echo "Danmarks Statistik BT repair complete."
