#!/bin/bash
#SBATCH --job-name=hrm-original-sapient-L-mn
#SBATCH --account=project_465002606
#SBATCH --partition=standard-g
#SBATCH --nodes=4
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=56
#SBATCH --mem=480G
#SBATCH --time=2-00:00:00
#SBATCH --output=logs/lumi/%x-%j.out
#SBATCH --error=logs/lumi/%x-%j.err

# Larger-scale HRM-Text "L" run on LUMI-G (AMD MI250X / ROCm), FULL dataset.
#
# Differences vs scripts/lumi_train_original_sapient_l.sbatch (single node):
#   - Multi-node (default 4 nodes = 32 GCDs) via per-node torchrun rendezvous.
#   - Higher dataloader prefetch to hide Lustre read latency on the full dataset.
#   - Global batch scales with node count to keep per-GCD work efficient
#     (the scaling benchmark showed a fixed batch saturates by 8 nodes).
#
# Context length: the dataset is tokenized/sampled at max_seq_len=4097 (=> 4096
# usable). The model uses RoPE, so context is bounded by the data, NOT the model.
# Increasing context requires rebuilding the dataset (see
# scripts/lumi_context_bump_plan.md); it is NOT a flag here.
#
# Container: lumi-pytorch-rocm-6.2.4-python-3.12-pytorch-v2.7.1.sif
# Backend: accelerator_type=rocm (FA2 CK varlen, FSDP2/RCCL, bf16).

set -euo pipefail

REPO=/project/project_465002606/HRM-Text
SIF=/appl/local/containers/sif-images/lumi-pytorch-rocm-6.2.4-python-3.12-pytorch-v2.7.1.sif
VENV=${REPO}/.venv-lumi
DATA=/scratch/project_465002606/data/sampled_original_sapient
CKPT=/scratch/project_465002606/checkpoints/original_sapient/L_multinode

MIOPEN_CACHE=/scratch/project_465002606/cache/miopen
TRITON_CACHE=/scratch/project_465002606/cache/triton

mkdir -p "${REPO}/logs/lumi" "${CKPT}" "${MIOPEN_CACHE}" "${TRITON_CACHE}"

GPUS_PER_NODE=8
NNODES=${SLURM_JOB_NUM_NODES:-4}
WORLD_SIZE=$(( NNODES * GPUS_PER_NODE ))

# --- Batch sizing -----------------------------------------------------------
# Per-GCD token budget = GLOBAL_BATCH_SIZE / WORLD_SIZE / GRAD_ACCUM and MUST be
# >= the context length (4096) or long sequences cannot be packed; pretrain.py
# also requires GLOBAL_BATCH_SIZE divisible by WORLD_SIZE * GRAD_ACCUM.
#
# Scale the global batch with world size so each GCD keeps ~10752 tokens/step
# (the efficient point from the scaling benchmark). At 4 nodes (32 GCDs) this is
# 32 * 10752 = 344064. GRAD_ACCUM=1.
PER_GCD_TOKENS=10752
GRAD_ACCUM=1
GLOBAL_BATCH_SIZE=$(( WORLD_SIZE * PER_GCD_TOKENS * GRAD_ACCUM ))

# Learning rate: keep the reference 2.5e-4. NOTE: the reference L recipe used
# global_batch_size=172032; this script doubles it at 4 nodes, so consider LR
# scaling / a longer warmup if you observe instability. lr_warmup_steps default
# is 2000 (config/cfg_pretrain.yaml).
LR=2.5e-4

CKPT_STEP_INTERVAL=2000
PREFETCH=16

# --- Auto-resume from newest step_* checkpoint ------------------------------
RESUME_ARGS=""
LATEST_TAG=""
if [ -d "${CKPT}" ]; then
  LATEST_TAG=$(ls -1d "${CKPT}"/fsdp2_step_* 2>/dev/null \
    | sed 's#.*/fsdp2_##' \
    | sort -t_ -k2 -n \
    | tail -n1 || true)
fi
if [ -n "${LATEST_TAG}" ]; then
  echo "Resuming from checkpoint tag ${LATEST_TAG}"
  RESUME_ARGS="resume_checkpoint_path=${CKPT} resume_checkpoint_tag=${LATEST_TAG}"
else
  echo "No existing step checkpoint found; starting a fresh run."
fi

MASTER_ADDR=$(scontrol show hostnames "${SLURM_JOB_NODELIST}" | head -n1)
export MASTER_ADDR
export MASTER_PORT=29500

echo "nnodes=${NNODES} world_size=${WORLD_SIZE} global_batch_size=${GLOBAL_BATCH_SIZE} per_gcd_tokens=${PER_GCD_TOKENS} grad_accum=${GRAD_ACCUM} master=${MASTER_ADDR}"

BIND="-B /project/project_465002606 -B /scratch/project_465002606 -B /flash/project_465002606"

# One srun task per node; each runs torchrun with its SLURM_NODEID as node_rank.
srun bash -c "
  MASTER_ADDR=\$(scontrol show hostnames \"\${SLURM_JOB_NODELIST}\" | head -n1)
  singularity exec ${BIND} ${SIF} bash -c \"
    cd ${REPO}
    source ${VENV}/bin/activate
    export PYTHONPATH=.
    export MIOPEN_USER_DB_PATH=${MIOPEN_CACHE}
    export MIOPEN_CUSTOM_CACHE_DIR=${MIOPEN_CACHE}
    export TRITON_CACHE_DIR=${TRITON_CACHE}
    export WANDB_MODE=\\\${WANDB_MODE:-offline}
    export OMP_NUM_THREADS=7
    export NCCL_SOCKET_IFNAME=hsn
    export NCCL_NET_GDR_LEVEL=PHB
    export MPICH_GPU_SUPPORT_ENABLED=1
    python -m torch.distributed.run \
      --nnodes=${NNODES} \
      --nproc_per_node=${GPUS_PER_NODE} \
      --node_rank=\\\${SLURM_NODEID} \
      --master_addr=\${MASTER_ADDR} \
      --master_port=${MASTER_PORT} \
      pretrain.py \
        data=original_sapient \
        data.path=${DATA} \
        arch/size@arch=L \
        accelerator_type=rocm \
        distributed_strategy=fsdp \
        fwd_bwd_dtype=bfloat16 \
        lr=${LR} \
        global_batch_size=${GLOBAL_BATCH_SIZE} \
        gradient_accumulation_steps=${GRAD_ACCUM} \
        dataloader_prefetch_factor=${PREFETCH} \
        checkpoint_step_interval=${CKPT_STEP_INTERVAL} \
        +project_name='Original Sapient L HLM-torch (LUMI ROCm multinode)' \
        +run_name=original-sapient-L-lumi-mn \
        +checkpoint_path=${CKPT} \
        ${RESUME_ARGS}
  \"
"
