#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

: "${HF_TOKEN:?Set HF_TOKEN to a Hugging Face write token}"
PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
ORG="${ORG:-schneiderkamplab}"
RUN_DIR="${RUN_DIR:-$ROOT/logs/dfm10_ready_upload}"
UPLOAD_WORKERS="${UPLOAD_WORKERS:-8}"
PACKAGE_NAMES="${PACKAGE_NAMES:-}"
mkdir -p "$RUN_DIR"
VERIFIED="$RUN_DIR/verified.jsonl"
UPLOAD_LOG="$RUN_DIR/upload.log"

mapfile -t packages < <(
  "$PYTHON" - <<'PY'
import json
import os
from pathlib import Path

manifest = json.loads(Path("exports_dfm10/manifest.json").read_text())
selected = set(os.environ.get("PACKAGE_NAMES", "").split())
for package in manifest["packages"]:
    if package["status"] == "ready_for_upload" and (
        not selected or package["name"] in selected
    ):
        print(package["name"])
PY
)

if [[ -n "$PACKAGE_NAMES" ]]; then
  expected_count="$(wc -w <<<"$PACKAGE_NAMES")"
  if [[ "${#packages[@]}" -ne "$expected_count" ]]; then
    echo "Requested $expected_count packages but found ${#packages[@]} ready: ${packages[*]}" >&2
    exit 1
  fi
fi

is_verified() {
  local package="$1"
  [[ -s "$VERIFIED" ]] && "$PYTHON" - "$VERIFIED" "$package" <<'PY'
import json
import sys

path, package = sys.argv[1:]
found = False
with open(path, encoding="utf-8") as handle:
    for line in handle:
        if line.strip() and json.loads(line).get("package") == package:
            found = True
raise SystemExit(0 if found else 1)
PY
}

verify_remote() {
  local package="$1"
  "$PYTHON" - "$ORG" "$package" "$VERIFIED" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from huggingface_hub import HfApi

org, package, receipt_path = sys.argv[1:]
root = Path("exports_dfm10") / package
expected = {
    path.relative_to(root).as_posix()
    for path in root.rglob("*")
    if path.is_file()
    and ".cache" not in path.parts
    and "__pycache__" not in path.parts
    and path.suffix != ".pyc"
}
api = HfApi(token=os.environ["HF_TOKEN"])
repo_id = f"{org}/{package}"
info = api.dataset_info(repo_id=repo_id)
remote = set(api.list_repo_files(repo_id=repo_id, repo_type="dataset"))
missing = sorted(expected - remote)
if missing:
    raise SystemExit(f"{repo_id}: {len(missing)} local files missing remotely: {missing[:10]}")
receipt = {
    "package": package,
    "repo_id": repo_id,
    "verified_at": datetime.now(timezone.utc).isoformat(),
    "commit_sha": info.sha,
    "expected_files": len(expected),
    "remote_files": len(remote),
}
with open(receipt_path, "a", encoding="utf-8") as handle:
    handle.write(json.dumps(receipt, sort_keys=True) + "\n")
print(json.dumps(receipt, sort_keys=True), flush=True)
PY
}

echo "Uploading ${#packages[@]} manifest-ready DFM10 packages to $ORG"
for package in "${packages[@]}"; do
  if is_verified "$package"; then
    echo "SKIP verified $package"
    continue
  fi
  echo "START $package"
  "$PYTHON" scripts/upload_export_upload_to_hf.py \
    --org "$ORG" \
    --root exports_dfm10 \
    --include-glob "$package" \
    --large-folder \
    --workers "$UPLOAD_WORKERS" \
    --log "$UPLOAD_LOG"
  verify_remote "$package"
  echo "VERIFIED $package"
done
echo "All manifest-ready DFM10 packages uploaded and remotely verified."
