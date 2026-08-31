#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
DATA_ROOT="${DATA_ROOT:-$ROOT/data/mimir_benchmark_campaigns}"
EXPECTED_SHARDS="${EXPECTED_SHARDS:-1024}"
TOKENIZER_PATH="${TOKENIZER_PATH:-/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json}"
CHAT_TEMPLATE="${CHAT_TEMPLATE:-$ROOT/data_io/chat_templates/gemma4_native_chat.jinja}"
TOKENIZED_ROOT="${TOKENIZED_ROOT:-$ROOT/data/tokenized_dfm10_mimir_benchmark_campaigns}"
LOG="${LOG:-$ROOT/logs/mimir_benchmark_campaigns_finalize_$(date +%Y%m%dT%H%M%S).log}"
PACKAGES=(
  dfm10-mimir-ifeval-verifier-sft
  dfm10-mimir-event-coreference-sft
  dfm10-mimir-drop-reasoning-sft
  dfm10-mimir-boolq-entailment-sft
)

mkdir -p "$DATA_ROOT" "$(dirname "$LOG")"
exec 9>"$DATA_ROOT/finalize.lock"
flock -n 9 || { echo "Another benchmark campaign finalizer holds $DATA_ROOT/finalize.lock"; exit 1; }
exec > >(tee -a "$LOG") 2>&1

retry() {
  local attempts="$1" delay="$2"
  shift 2
  local attempt
  for attempt in $(seq 1 "$attempts"); do
    if "$@"; then return 0; fi
    echo "$(date -Is) attempt=$attempt/$attempts failed: $*" >&2
    (( attempt < attempts )) && sleep "$delay"
  done
  return 1
}

echo "$(date -Is) waiting for all $EXPECTED_SHARDS generation/audit shards"
while true; do
  completed="$(find "$DATA_ROOT/state/done" -maxdepth 1 -name '*.done' 2>/dev/null | wc -l)"
  if (( completed == EXPECTED_SHARDS )); then break; fi
  if ! pgrep -f '[r]un_mimir_benchmark_campaigns_8gpu.sh' >/dev/null; then
    echo "Campaign runner exited before completion: completed=$completed/$EXPECTED_SHARDS" >&2
    exit 1
  fi
  echo "$(date -Is) completed=$completed/$EXPECTED_SHARDS"
  sleep 60
done

echo "$(date -Is) validating complete shard coverage"
"$PYTHON" - "$DATA_ROOT" "$EXPECTED_SHARDS" <<'PY'
import sys
from pathlib import Path

root, expected = Path(sys.argv[1]), int(sys.argv[2])
requests = sorted((root / "requests/shards").glob("part-*.jsonl"))
if len(requests) != expected:
    raise SystemExit(f"request shard count {len(requests)} != {expected}")
missing = []
for request in requests:
    if not (root / "state/done" / f"{request.name}.done").is_file():
        missing.append(f"marker:{request.name}")
    for directory in ("generated", "audits"):
        path = root / directory / request.name
        if not path.is_file() or path.stat().st_size == 0:
            missing.append(f"{directory}:{request.name}")
if missing:
    raise SystemExit(f"incomplete campaign artifacts ({len(missing)}): {missing[:20]}")
print(f"validated {len(requests)} complete request/generated/audit shard triplets")
PY

echo "$(date -Is) running normalized-exact benchmark decontamination"
retry 3 60 "$PYTHON" scripts/decontaminate_mimir_grounded_500k_exact.py \
  --data-root "$DATA_ROOT" \
  --output "$DATA_ROOT/decontamination/report.json"

echo "$(date -Is) building all validated rows; campaign quotas are informational"
"$PYTHON" scripts/mimir_benchmark_campaigns.py --data-root "$DATA_ROOT" build \
  --allow-under-target

echo "$(date -Is) validating accepted campaign artifacts"
"$PYTHON" - "$DATA_ROOT/accepted" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
summary = json.loads((root / "summary.json").read_text())
if summary.get("status") != "complete":
    raise SystemExit(f"accepted summary is not complete: {summary}")
expected = {"ifeval_verifier", "event_coreference", "drop_reasoning", "boolq_entailment"}
if set(summary.get("rows", {})) != expected:
    raise SystemExit(f"unexpected accepted campaigns: {summary.get('rows')}")
for campaign in expected:
    count = int(summary["rows"][campaign])
    path = root / f"{campaign}.jsonl"
    if count <= 0 or not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"{campaign}: invalid accepted artifact rows={count} path={path}")
print(json.dumps(summary, indent=2, sort_keys=True))
PY

echo "$(date -Is) materializing and validating four Hugging Face packages"
prepare_args=()
for package in "${PACKAGES[@]}"; do prepare_args+=(--dataset "$package"); done
"$PYTHON" scripts/prepare_dfm10_hf_exports.py "${prepare_args[@]}" --workers 4 --force
for package in "${PACKAGES[@]}"; do
  "$PYTHON" "exports_dfm10/$package/recreate_dataset.py"
done

if [[ -z "${HF_TOKEN:-}" ]]; then
  HF_TOKEN="$("$PYTHON" - <<'PY'
from huggingface_hub import get_token
print(get_token() or "")
PY
)"
  export HF_TOKEN
fi
: "${HF_TOKEN:?No Hugging Face token is configured; authenticate with hf auth login}"

echo "$(date -Is) uploading and remotely verifying the four packages"
export PACKAGE_NAMES="${PACKAGES[*]}"
retry 3 120 env PACKAGE_NAMES="$PACKAGE_NAMES" HF_TOKEN="$HF_TOKEN" \
  bash scripts/upload_ready_dfm10_packages.sh
"$PYTHON" scripts/prepare_dfm10_hf_exports.py --refresh-inventory

echo "$(date -Is) tokenizing accepted campaigns with the Gemma 4 native template"
"$PYTHON" scripts/tokenize_chat_template.py \
  "$DATA_ROOT/accepted" \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir "$TOKENIZED_ROOT" \
  --workers 16 --force

echo "$(date -Is) rebuilding the DFM10 tokenized union under its global lock"
flock data/.dfm10-union.lock "$PYTHON" scripts/build_tokenized_dfm10_tree.py --force

touch "$DATA_ROOT/finalization_complete"
echo "$(date -Is) Mimir benchmark campaigns uploaded, tokenized, and integrated"
