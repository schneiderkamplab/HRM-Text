#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/work/dfm/HRM-Text}"
STAMP="${STAMP:-$(date +%Y%m%dT%H%M%S)}"
RUN_ROOT="${RUN_ROOT:-$ROOT/logs/export_prefix_gpus012367_${STAMP}}"

mkdir -p "$RUN_ROOT/audits"
cd "$ROOT/export/common-pile-prefix-continuation"

SKIPS=()
for f in \
  audit_full/audit.jsonl \
  audit_rebalance_*/audit.jsonl; do
  if [[ -f "$f" ]]; then
    SKIPS+=(--skip-audit "$ROOT/export/common-pile-prefix-continuation/$f")
  fi
done

ports=(8903 8900 8902 8901 8916 8917)
gpus=(0 1 2 3 6 7)
pids=()

for i in 0 1 2 3 4 5; do
  shard="$(printf '%02d' "$i")"
  audit_root="$ROOT/export/common-pile-prefix-continuation/audit_manual_prefix_gpus012367_${STAMP}_shard${shard}of06"
  log="$RUN_ROOT/audits/common-pile-prefix-continuation_gpu${gpus[$i]}_shard${shard}.log"
  env PYTHONUNBUFFERED=1 CUDA_VISIBLE_DEVICES="${gpus[$i]}" python recreate_dataset.py audit \
    --base-url "http://127.0.0.1:${ports[$i]}/v1" \
    --model posttrain-gemma-teacher \
    --sample-rate 1.0 \
    --concurrency 8 \
    --audit-root "$audit_root" \
    --num-shards 6 \
    --shard-index "$i" \
    --force \
    "${SKIPS[@]}" > "$log" 2>&1 &
  pids+=("$!")
  echo "GPU ${gpus[$i]} shard $i/6 pid=${pids[-1]} log=$log"
done

echo "RUN_ROOT=$RUN_ROOT"
wait "${pids[@]}"
