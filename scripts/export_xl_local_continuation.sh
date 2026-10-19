#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PATH="/home/ucloud/miniforge3/envs/hrm/bin:$PATH"
python scripts/schedule_xl_3850k_3900k.py --finalize "$@"
exec python "$@"
