#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PATH="/home/ucloud/miniforge3/envs/hrm/bin:/usr/local/cuda/bin:$PATH"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
if [[ "${1:-}" == "conversion/convert_to_hf.py" ]]; then
  exec /home/ucloud/miniforge3/envs/hrm/bin/python scripts/schedule_dfm12_xl_epoch11.py export -- "$@"
fi
exec /home/ucloud/miniforge3/envs/hrm/bin/python scripts/schedule_dfm12_xl_epoch11.py train "$@"
