#!/usr/bin/env bash
set -euo pipefail

cd /work/dfm/HRM-Text

PLAN_DIR="${PLAN_DIR:-logs/scheduler/gemma4_e2b_clean_external_$(date +%Y%m%d_%H%M%S)}"
RUN_ID="${RUN_ID:-gemma4-e2b-it-clean-candidate}"
RUN_NAME="${RUN_NAME:-Gemma 4 E2B IT clean candidate}"
MODEL_PATH="${MODEL_PATH:-/work/dfm/brainsurgery/models/google/gemma-4-E2B-it}"
SERVED_NAME="${SERVED_NAME:-gemma4-e2b-it-clean}"
JUDGE_MODEL="${JUDGE_MODEL:-openai/gemma-4-e4b-judge}"
JUDGE_BASE_URL="${JUDGE_BASE_URL:-http://127.0.0.1:8099/v1}"

python -m eval_scheduler plan create-external \
  --plan-dir "${PLAN_DIR}" \
  --model "${MODEL_PATH}" \
  --served-model-name "${SERVED_NAME}" \
  --eval-epoch 0.0 \
  --ckpt-tag external_clean \
  --log-root logs/eval/gemma4_e2b_clean_external \
  --dfm-log-root logs/dfm_evals/gemma4_e2b_clean_external \
  --euroeval-log-root logs/euroeval/gemma4_e2b_clean_external \
  --wandb-project DFM5 \
  --wandb-run-id "${RUN_ID}" \
  --wandb-run-name "${RUN_NAME}" \
  --standard-config evaluation/config/external_chat_benchmarking.yaml \
  --run-euroeval \
  --queue-order euroeval-first \
  --dfm-ifeval-shards 32 \
  --max-retries 5 \
  --standard-batch 64 \
  --dfm-batch 32 \
  --ifeval-batch 32 \
  --euroeval-batch 16 \
  --vllm-dtype bfloat16 \
  --vllm-max-model-len 4096 \
  --vllm-gpu-memory-utilization 0.9 \
  --vllm-extra-args '--enforce-eager --hf-overrides {"architectures":["Gemma4ForCausalLM"]} --chat-template /work/dfm/HRM-Text/evaluation/chat_templates/gemma4_native_chat.jinja' \
  --judge-model "${JUDGE_MODEL}" \
  --judge-base-url "${JUDGE_BASE_URL}" \
  --judged-max-connections 4 \
  --no-include-average \
  --no-log-wandb \
  --force

python - "${PLAN_DIR}" <<'PY'
from pathlib import Path
import sys

from eval_scheduler.eval_scheduler.model import read_plan, write_plan

plan_dir = Path(sys.argv[1])
plan_path = plan_dir / "plan.tsv"
jobs = []
for job in read_plan(plan_path):
    metadata = dict(job.metadata)
    if metadata.get("external_model"):
        metadata["fixed_retry_batch"] = True
        metadata["euroeval_generative_type"] = "instruction_tuned"
    if job.family == "dfm" and job.name == "govreport":
        metadata["dfm_context_length"] = 3968
        metadata["dfm_max_gen_toks"] = 128
        metadata["dfm_task_args"] = ["max_report_chars=10000"]
    jobs.append(job.with_updates(metadata=metadata))
write_plan(plan_path, jobs)
PY

cat <<EOF
Prepared clean Gemma external diagnostic plan:
  ${PLAN_DIR}

After the current 500K eval is finished, run:
  cd /work/dfm/HRM-Text
  python -m eval_scheduler run --plan-dir ${PLAN_DIR} --gpus 0,1,2,3,4,5,6,7

Monitor with:
  python -m eval_scheduler monitor --plan-dir ${PLAN_DIR} --interval 30

This plan writes local metrics and generation JSONL files, but does not sync to W&B.
EOF
