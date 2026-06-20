#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  cat >&2 <<'USAGE'
Usage:
  scripts/create_dfm5_l_vllm_eval_plan.sh CKPT_TAG EVAL_EPOCH [RUN_SUFFIX]

Example:
  scripts/create_dfm5_l_vllm_eval_plan.sh step_750000 4.141326927327961 20260619

Environment overrides:
  PLAN_DIR, CKPT_PATH, EXPORT_DIR, LOG_ROOT, DFM_LOG_ROOT, EUROEVAL_LOG_ROOT,
  WANDB_PROJECT, WANDB_RUN_ID, WANDB_RUN_NAME, MODEL_PREFIX, PORT_BASE, FORCE,
  SKIP_VALEU_DA
USAGE
  exit 2
fi

CKPT_TAG="$1"
EVAL_EPOCH="$2"
RUN_SUFFIX="${3:-$(date +%Y%m%d_%H%M%S)}"
if [[ "${CKPT_TAG}" =~ ^step_([0-9]+)$ ]]; then
  PATH_TAG="step${BASH_REMATCH[1]}"
else
  PATH_TAG="${CKPT_TAG}"
fi

PLAN_DIR="${PLAN_DIR:-logs/scheduler/dfm5_L_${PATH_TAG}_vllm_main_${RUN_SUFFIX}}"
CKPT_PATH="${CKPT_PATH:-checkpoints/dfm5/L}"
EXPORT_DIR="${EXPORT_DIR:-/work/dfm/HRM-Text/exports/dfm5_L_${PATH_TAG}_ema_hf}"
LOG_ROOT="${LOG_ROOT:-logs/eval/dfm5_L_${PATH_TAG}_vllm_main_${RUN_SUFFIX}}"
DFM_LOG_ROOT="${DFM_LOG_ROOT:-logs/dfm_evals/dfm5_L_${PATH_TAG}_vllm_main_${RUN_SUFFIX}}"
EUROEVAL_LOG_ROOT="${EUROEVAL_LOG_ROOT:-logs/euroeval/dfm5_L_${PATH_TAG}_vllm_main_${RUN_SUFFIX}}"
WANDB_PROJECT="${WANDB_PROJECT:-DFM5}"
WANDB_RUN_ID="${WANDB_RUN_ID:-oti1lisg}"
WANDB_RUN_NAME="${WANDB_RUN_NAME:-dfm5-L}"
MODEL_PREFIX="${MODEL_PREFIX:-hrm-dfm5-L-vllm-native-proxy}"
PORT_BASE="${PORT_BASE:-28000}"
FORCE="${FORCE:-0}"
SKIP_VALEU_DA="${SKIP_VALEU_DA:-1}"
CHECKPOINT_WAIT_SECONDS="${CHECKPOINT_WAIT_SECONDS:-60}"

force_arg=()
if [[ "${FORCE}" == "1" ]]; then
  force_arg=(--force)
fi

cd /work/dfm/HRM-Text

python -m eval_scheduler plan create \
  --plan-dir "${PLAN_DIR}" \
  --ckpt-path "${CKPT_PATH}" \
  --ckpt-tag "${CKPT_TAG}" \
  --eval-epoch "${EVAL_EPOCH}" \
  --log-root "${LOG_ROOT}" \
  --dfm-log-root "${DFM_LOG_ROOT}" \
  --euroeval-log-root "${EUROEVAL_LOG_ROOT}" \
  --wandb-project "${WANDB_PROJECT}" \
  --wandb-run-id "${WANDB_RUN_ID}" \
  --wandb-run-name "${WANDB_RUN_NAME}" \
  --model-prefix "${MODEL_PREFIX}" \
  --run-euroeval \
  --queue-order euroeval-first \
  --max-retries 5 \
  --checkpoint-wait-seconds "${CHECKPOINT_WAIT_SECONDS}" \
  --standard-config evaluation/config/hrm_vllm_benchmarking.yaml \
  --standard-engine-backend vllm \
  --standard-hf-export-dir "${EXPORT_DIR}" \
  --standard-batch 64 \
  --dfm-batch 32 \
  --ifeval-batch 32 \
  --dfm-ifeval-shards 32 \
  --euroeval-batch 32 \
  --euroeval-max-concurrent-calls 32 \
  --hrm-server-backend vllm \
  --hrm-hf-export-dir "${EXPORT_DIR}" \
  --hrm-vllm-native-proxy \
  --vllm-dtype bfloat16 \
  --vllm-max-model-len 4096 \
  --vllm-gpu-memory-utilization 0.35 \
  --vllm-attention-backend FLASH_ATTN \
  --vllm-extra-args "--enforce-eager --attention-backend FLASH_ATTN --chat-template /work/dfm/HRM-Text/evaluation/chat_templates/hrm_direct_chat.jinja" \
  --judge-model openai/gemma-4-e4b-judge \
  --judge-server-model unsloth/gemma-4-E4B-it \
  --judge-server-dtype bfloat16 \
  --judge-server-attn-implementation sdpa \
  --judge-server-max-new-tokens 64 \
  --judged-batch 16 \
  --judged-max-connections 16 \
  --judged-vllm-gpu-memory-utilization 0.25 \
  --govreport-max-report-chars 9000 \
  "${force_arg[@]}"

if [[ "${SKIP_VALEU_DA}" == "1" ]]; then
  python - <<'PY' "${PLAN_DIR}"
from pathlib import Path
import sys

from eval_scheduler.eval_scheduler.locking import PlanLock
from eval_scheduler.eval_scheduler.model import JobStatus, read_plan, write_plan

plan_dir = Path(sys.argv[1])
plan_file = plan_dir / "plan.tsv"
with PlanLock(plan_dir, exclusive=True):
    jobs = read_plan(plan_file)
    updated = []
    skipped = 0
    for job in jobs:
        if job.action.value == "eval_euroeval" and job.name == "valeu-da":
            updated.append(
                job.with_updates(
                    status=JobStatus.SKIPPED,
                    metadata={
                        **job.metadata,
                        "skip_reason": "EuroEval ValEU-da aborts the whole task on invalid labels; skipped for failure-free DFM5-L checkpoint sweeps.",
                    },
                )
            )
            skipped += 1
        else:
            updated.append(job)
    write_plan(plan_file, updated)
print(f"skipped_valeu_da_rows={skipped}")
PY
fi

cat <<EOF

Created DFM5-L vLLM eval plan:
  PLAN_DIR=${PLAN_DIR}
  EXPORT_DIR=${EXPORT_DIR}

Run:
  python -m eval_scheduler run --plan-dir ${PLAN_DIR} --gpus 0,1,2,3,4,5,6,7

Monitor:
  python -m eval_scheduler monitor --plan-dir ${PLAN_DIR} --gpus 0,1,2,3,4,5,6,7 --interval 10
EOF
