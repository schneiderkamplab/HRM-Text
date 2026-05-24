#!/usr/bin/env bash
# Clean local artifacts from a failed HRM-Text training run.
#
# Dry-run by default. Pass --execute to actually remove files.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/work/dfm/HRM-Text}"
WANDB_RUN="${WANDB_RUN:-}"
CHECKPOINT_PATH="${CHECKPOINT_PATH:-}"
EXECUTE=0

usage() {
  cat <<'EOF'
Usage:
  scripts/cleanup_failed_training_run.sh [options]

Options:
  --wandb-run PATH       Local W&B run directory to remove.
  --checkpoint PATH      Checkpoint directory to remove.
  --original-l-latest    Target the latest failed original Sapient L paths from the 2026-05-22 runs.
  --execute              Actually remove files. Without this, only prints a dry run.
  -h, --help             Show this help.

Environment overrides:
  REPO_ROOT              Default: /work/dfm/HRM-Text
  WANDB_RUN              Alternative to --wandb-run
  CHECKPOINT_PATH        Alternative to --checkpoint

Safety:
  - Refuses paths outside REPO_ROOT.
  - Refuses to remove data directories.
  - Removes W&B convenience symlinks only when they point at the selected run.
EOF
}

clean_abs() {
  local path="$1"
  if [[ "${path}" = /* ]]; then
    realpath -m "${path}"
  else
    realpath -m "${REPO_ROOT}/${path}"
  fi
}

require_inside_repo() {
  local path="$1"
  case "${path}" in
    "${REPO_ROOT}"/*) ;;
    *)
      echo "Refusing path outside REPO_ROOT: ${path}" >&2
      exit 1
      ;;
  esac
}

require_not_data_path() {
  local path="$1"
  case "${path}" in
    "${REPO_ROOT}/data"|\
    "${REPO_ROOT}/data/"*|\
    "${REPO_ROOT}/data_io"|\
    "${REPO_ROOT}/data_io/"*)
      echo "Refusing to remove data/data_io path: ${path}" >&2
      exit 1
      ;;
  esac
}

remove_path() {
  local path="$1"
  if [[ ! -e "${path}" && ! -L "${path}" ]]; then
    echo "missing: ${path}"
    return
  fi

  if [[ "${EXECUTE}" -eq 1 ]]; then
    rm -rf -- "${path}"
    echo "removed: ${path}"
  else
    echo "would remove: ${path}"
  fi
}

target_original_l_latest() {
  WANDB_RUN="${REPO_ROOT}/wandb/run-20260522_071714-5l4tsw6k"
  CHECKPOINT_PATH="${REPO_ROOT}/checkpoints/original_sapient/L"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --wandb-run)
      WANDB_RUN="${2:?missing value for --wandb-run}"
      shift 2
      ;;
    --checkpoint)
      CHECKPOINT_PATH="${2:?missing value for --checkpoint}"
      shift 2
      ;;
    --original-l-latest)
      target_original_l_latest
      shift
      ;;
    --execute)
      EXECUTE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

REPO_ROOT="$(realpath -m "${REPO_ROOT}")"

if [[ -z "${WANDB_RUN}" && -z "${CHECKPOINT_PATH}" ]]; then
  usage >&2
  echo "No cleanup targets specified." >&2
  exit 2
fi

echo "Mode: $([[ "${EXECUTE}" -eq 1 ]] && echo execute || echo dry-run)"
echo "Repo: ${REPO_ROOT}"

if [[ -n "${WANDB_RUN}" ]]; then
  WANDB_RUN="$(clean_abs "${WANDB_RUN}")"
  require_inside_repo "${WANDB_RUN}"
  require_not_data_path "${WANDB_RUN}"
  echo "W&B run: ${WANDB_RUN}"
  remove_path "${WANDB_RUN}"

  for link in "${REPO_ROOT}/wandb/latest-run" "${REPO_ROOT}/wandb/debug.log" "${REPO_ROOT}/wandb/debug-internal.log"; do
    if [[ -L "${link}" ]]; then
      target="$(readlink "${link}")"
      target_abs="$(clean_abs "$(dirname "${link}")/${target}")"
      if [[ "${target_abs}" == "${WANDB_RUN}" || "${target_abs}" == "${WANDB_RUN}/logs/debug.log" || "${target_abs}" == "${WANDB_RUN}/logs/debug-internal.log" ]]; then
        remove_path "${link}"
      else
        echo "keeping symlink with different target: ${link} -> ${target}"
      fi
    fi
  done
fi

if [[ -n "${CHECKPOINT_PATH}" ]]; then
  CHECKPOINT_PATH="$(clean_abs "${CHECKPOINT_PATH}")"
  require_inside_repo "${CHECKPOINT_PATH}"
  require_not_data_path "${CHECKPOINT_PATH}"
  echo "Checkpoint: ${CHECKPOINT_PATH}"
  remove_path "${CHECKPOINT_PATH}"
fi
