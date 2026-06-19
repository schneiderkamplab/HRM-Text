#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

PYTHON_BIN="${PYTHON_BIN:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python"
fi

MODEL=""
SERVED_MODEL_NAME=""
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-9700}"
DTYPE="${VLLM_DTYPE:-bfloat16}"
MAX_MODEL_LEN="${MAX_CONTEXT:-${VLLM_MAX_MODEL_LEN:-4096}}"
GPU_MEMORY_UTILIZATION="${VLLM_GPU_MEMORY_UTILIZATION:-0.85}"
EXTRA_ARGS="${VLLM_EXTRA_ARGS:-}"

usage() {
  cat <<'USAGE'
Start a vLLM OpenAI-compatible server for an exported HRM-Text checkpoint.

Required:
  --model EXPORT_DIR
  --served-model-name NAME

Common options:
  --host 127.0.0.1
  --port 9700
  --max-model-len 4096
  --dtype bfloat16
  --gpu-memory-utilization 0.85

Extra vLLM flags can be passed through VLLM_EXTRA_ARGS.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model)
      MODEL="$2"
      shift 2
      ;;
    --served-model-name|--model-name)
      SERVED_MODEL_NAME="$2"
      shift 2
      ;;
    --host)
      HOST="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --max-model-len|--max-context)
      MAX_MODEL_LEN="$2"
      shift 2
      ;;
    --dtype)
      DTYPE="$2"
      shift 2
      ;;
    --gpu-memory-utilization)
      GPU_MEMORY_UTILIZATION="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "${MODEL}" || -z "${SERVED_MODEL_NAME}" ]]; then
  usage >&2
  exit 2
fi
if [[ ! -d "${MODEL}" ]]; then
  echo "Exported HF/vLLM model directory not found: ${MODEL}" >&2
  exit 2
fi

argv=(
  "${PYTHON_BIN}" -m vllm.entrypoints.openai.api_server
  --model "${MODEL}"
  --served-model-name "${SERVED_MODEL_NAME}"
  --host "${HOST}"
  --port "${PORT}"
  --dtype "${DTYPE}"
  --max-model-len "${MAX_MODEL_LEN}"
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION}"
)

if [[ -n "${EXTRA_ARGS}" ]]; then
  # shellcheck disable=SC2206
  extra=( ${EXTRA_ARGS} )
  argv+=("${extra[@]}")
fi

exec "${argv[@]}"
