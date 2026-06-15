#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

env \
  VLLM_PYTHON=/home/ucloud/miniforge3/envs/hrm/bin/python \
  CLIENT_PYTHON=/home/ucloud/miniforge3/envs/hrm/bin/python \
  GEMMA_MODEL_PATH=/work/dfm/HRM-Text/data/models/google/gemma-4-31B-it-fresh-20260604 \
  SERVED_MODEL_NAME=posttrain-gemma-teacher \
  GPU_LIST="${GPU_LIST:-0,1,2,3,4,5,6,7}" \
  REQUESTS_PER_SHARD="${REQUESTS_PER_SHARD:-1000}" \
  CLIENT_CONCURRENCY="${CLIENT_CONCURRENCY:-32}" \
  GENERATION_ENDPOINT=chat \
  JUDGE_QUALITY="${JUDGE_QUALITY:-1}" \
  JUDGE_RETRIES="${JUDGE_RETRIES:-2}" \
  SHARD_ROOT=data/synthetic_request_shards_posttrain_transform_refine_v3_missing \
  GENERATED_ROOT=data/generated_posttrain_transform_refine \
  LOG_ROOT=logs/posttrain_transform_refine_generation_v3_missing \
  STOP_SERVERS_ON_EXIT=1 \
  scripts/run_posttrain_synthetic_generation_vllm.sh
