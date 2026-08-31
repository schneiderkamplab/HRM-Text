#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
EPOCHS="${DFM10_EPOCHS:-10}"
WORKERS="${DFM10_CONCAT_WORKERS:-4}"
STAGING="${STAGING:-$ROOT/data/sampled_dfm10_rebuild_20260830}"
CURRENT="${CURRENT:-$ROOT/data/sampled_dfm10}"
BACKUP="${BACKUP:-$ROOT/data/sampled_dfm10_pre_20260830}"
ANALYTICS="${ANALYTICS:-$ROOT/data/show_analytics_dfm10_rebuild_20260830.md}"

[[ ! -e "$STAGING" ]] || { echo "Staging path already exists: $STAGING" >&2; exit 1; }
[[ ! -e "$BACKUP" ]] || { echo "Backup path already exists: $BACKUP" >&2; exit 1; }

echo "Sampling $EPOCHS DFM10 epochs into $STAGING"
(
  cd "$ROOT/data_io"
  nice -n 10 ionice -c 2 -n 7 "$PYTHON" sample_tokenized.py \
    tokenized_path=../data/tokenized_dfm10 \
    output_path="$STAGING" \
    epochs="$EPOCHS" \
    concat_workers="$WORKERS" \
    default_long_context=drop \
    prefix_config_path=prefix_config_dfm10.yaml \
    > "$ANALYTICS"
)

echo "Validating sampled arrays"
"$PYTHON" - "$STAGING" "$EPOCHS" <<'PY'
import json
import sys
from pathlib import Path

import numpy as np

root = Path(sys.argv[1])
epochs = int(sys.argv[2])
metadata = json.loads((root / "metadata.json").read_text())
tokens = np.load(root / "tokens.npy", mmap_mode="r")
if tokens.ndim != 1 or tokens.size == 0:
    raise SystemExit("invalid tokens.npy")
for epoch in range(epochs):
    directory = root / f"epoch_{epoch}"
    arrays = {
        name: np.load(directory / f"{name}.npy", mmap_mode="r")
        for name in ("inst_start", "inst_len", "resp_start", "resp_len")
    }
    sizes = {array.size for array in arrays.values()}
    if len(sizes) != 1 or not sizes or next(iter(sizes)) == 0:
        raise SystemExit(f"epoch_{epoch}: inconsistent or empty arrays")
    size = next(iter(sizes))
    for start_name, length_name in (("inst_start", "inst_len"), ("resp_start", "resp_len")):
        start, length = arrays[start_name], arrays[length_name]
        for offset in range(0, size, 5_000_000):
            end = min(size, offset + 5_000_000)
            if np.any(start[offset:end].astype(np.uint64) + length[offset:end] > tokens.size):
                raise SystemExit(f"epoch_{epoch}: {start_name} span exceeds tokens.npy")
if int(metadata["total_length"]) <= 0:
    raise SystemExit("invalid metadata total_length")
print(json.dumps({"epochs": epochs, "backing_tokens": int(tokens.size), "metadata": metadata}))
PY

echo "Promoting staged sample and preserving the prior snapshot"
mv "$CURRENT" "$BACKUP"
mv "$STAGING" "$CURRENT"
mv "$ANALYTICS" "$ROOT/data/show_analytics_dfm10.md"
echo "DFM10 sampling complete: $CURRENT"
