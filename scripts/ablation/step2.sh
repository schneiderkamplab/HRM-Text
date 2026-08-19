#!/usr/bin/env bash
# ============================================================================
# STEP 2 — GPU environment + the 200-step timing baseline.
#
# Needs a B200 job with the data folder mounted. Run from the repo root.
#
#   bash scripts/ablation/step2.sh              # install + verify + timing run
#   bash scripts/ablation/step2.sh --check-only # install + verify, no training
#
# Installs the MINIMAL training dependency set, not requirements.txt: pretrain.py
# and the modules it loads need only torch, numpy, numba, einops, pydantic,
# hydra-core, omegaconf, tqdm, wandb, coolname, PyYAML. requirements.txt also pulls
# vllm and lm-eval, which are for evaluation and add a long, failure-prone install.
#
# W&B runs OFFLINE by default so no login is needed. `wandb sync` later to upload.
# ============================================================================
set -uo pipefail

CHECK_ONLY=0
[ "${1:-}" = "--check-only" ] && CHECK_ONLY=1

REPORT="logs/step2-report.txt"
[ -f pretrain.py ] || { echo "ERROR: run from the HRM-Text repo root." >&2; exit 1; }
mkdir -p logs

{
echo "STEP 2 report — $(date -u '+%Y-%m-%d %H:%M:%SZ')  host=$(hostname)"

echo
echo "############ 2a. GPU ############"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=index,name,memory.total,compute_cap --format=csv
else
  echo "FAIL: no nvidia-smi -- this job has no GPU. Start a B200 job."
  exit 1
fi
GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)"
case "$GPU_NAME" in
  *MIG*) echo
         echo "NOTE: this is a MIG slice ($GPU_NAME), not a whole card."
         echo "      Fine for a smoke test, but sec/step measured here does NOT extrapolate"
         echo "      to a full GPU. For the real timing baseline, move the UCloud slider from"
         echo "      the MIG section (1/7..4/7) to GPU(s) = 1." ;;
esac

echo
echo "############ 2a2. DATA LINKS ############"
DATA_SRC="${DATA_SRC:-/work/Training_Ablations/data/sampled_dfm9_mini}"
if [ ! -e data/sampled_dfm9_mini ]; then
  if [ -d "$DATA_SRC" ]; then
    mkdir -p data && ln -sfn "$DATA_SRC" data/sampled_dfm9_mini
    echo "linked data/sampled_dfm9_mini -> $DATA_SRC"
  else
    echo "FAIL: data/sampled_dfm9_mini is missing and DATA_SRC=$DATA_SRC does not exist."
    echo "      Re-run with DATA_SRC=/path/to/sampled_dfm9_mini bash scripts/ablation/step2.sh"
    exit 1
  fi
else
  echo "data/sampled_dfm9_mini  OK  -> $(readlink -f data/sampled_dfm9_mini)"
fi
if [ -d data/val_dfm9_mini/epoch_0 ]; then
  echo "data/val_dfm9_mini      OK  (validation holdout built by step1)"
else
  echo "FAIL: data/val_dfm9_mini is missing. Run step1 first:"
  echo "      bash scripts/ablation/step1.sh data/sampled_dfm9_mini"
  exit 1
fi

echo
echo "############ 2b. MINIMAL TRAINING DEPENDENCIES ############"
# Persistent venv on /work if setup_env.sh is present, so a new job costs seconds
# instead of ~2 minutes. Falls back to a --user install if it is missing.
if [ -f scripts/ablation/setup_env.sh ]; then
  # shellcheck disable=SC1091
  . scripts/ablation/setup_env.sh
  [ "${HRM_ENV_OK:-0}" = "1" ] || echo "WARN: setup_env.sh reported a problem; continuing"
fi
PIPU="${HRM_PIP_USER---user}"   # empty inside a venv: pip refuses --user there
python3 -m pip install $PIPU --quiet \
    torch numpy numba einops pydantic hydra-core omegaconf tqdm wandb coolname PyYAML \
  && echo "base deps OK" || echo "WARN: some base deps failed; see errors above"

CAP="$(python3 -c 'import torch;print(torch.cuda.get_device_capability(0)[0] if torch.cuda.is_available() else 0)' 2>/dev/null || echo 0)"
echo "cuda capability major: $CAP"
case "$CAP" in
  10) ACCEL=sm100; REQ=requirements-sm100.txt; FA_MOD=flash_attn.cute ;;
  9)  ACCEL=sm90;  REQ=requirements-sm90.txt;  FA_MOD=flash_attn_interface ;;
  *)  echo "FAIL: no CUDA GPU visible to torch."; exit 1 ;;
esac
echo "-> detected accelerator_type=$ACCEL, installing $REQ"
python3 -m pip install $PIPU --quiet -r "$REQ" \
  && echo "FlashAttention install OK" || echo "WARN: FlashAttention install reported errors"

echo
echo "############ 2b2. accelerator_type IN THE CONFIG ############"
# The launcher only sets H_cycles/L_cycles and the batch plumbing. accelerator_type is
# infrastructure, not recipe -- but if the config disagrees with the hardware, pretrain.py
# dispatches the wrong FlashAttention kernel and dies. Decide it here from the DETECTED
# device rather than hardcoding a value that goes stale on a different job type.
CFG_YAML=config/cfg_pretrain.yaml
CUR_ACCEL="$(sed -n 's/^accelerator_type:[[:space:]]*\([^#[:space:]]*\).*/\1/p' "$CFG_YAML" 2>/dev/null | head -1)"
CUR_ACCEL="${CUR_ACCEL%\"}"; CUR_ACCEL="${CUR_ACCEL#\"}"
CUR_ACCEL="${CUR_ACCEL%\'}"; CUR_ACCEL="${CUR_ACCEL#\'}"
ACCEL_OV=""
KNOWN=" sm90 sm100 cpu mps none auto null "
if [ -z "$CUR_ACCEL" ]; then
  echo "$CFG_YAML has no accelerator_type line."
  echo "-> passing ++accelerator_type=$ACCEL"
  ACCEL_OV="++accelerator_type=$ACCEL"
elif [ "$CUR_ACCEL" = "$ACCEL" ]; then
  echo "$CFG_YAML says accelerator_type: $CUR_ACCEL -- matches the detected device."
  echo "-> no override needed"
elif echo "$KNOWN" | grep -q " $CUR_ACCEL "; then
  echo "$CFG_YAML says accelerator_type: $CUR_ACCEL, but this device is $ACCEL."
  echo "-> passing ++accelerator_type=$ACCEL"
  ACCEL_OV="++accelerator_type=$ACCEL"
else
  echo "$CFG_YAML says accelerator_type: $CUR_ACCEL -- not a token this script recognises."
  echo "-> LEAVING IT ALONE. If training dies on a kernel or FlashAttention import error,"
  echo "   that line is the first suspect."
fi

echo
echo "############ 2c. IMPORT VERIFICATION ############"
python3 - <<PY
import importlib, sys
ok = True
for m in ("torch","numpy","numba","einops","pydantic","hydra","omegaconf","tqdm","wandb","coolname","yaml"):
    try:
        importlib.import_module(m); print(f"  OK   {m}")
    except Exception as e:
        ok = False; print(f"  FAIL {m}: {e}")
import torch
print(f"  torch {torch.__version__} | cuda {torch.cuda.is_available()} | devices {torch.cuda.device_count()}")
try:
    importlib.import_module("$FA_MOD"); print("  OK   $FA_MOD  (required for $ACCEL -- there is NO dense fallback)")
except Exception as e:
    ok = False
    print(f"  FAIL $FA_MOD: {e}")
    print("       $ACCEL cannot train without it. Try docker/Dockerfile, or use")
    print("       accelerator_type=cpu to smoke-test the pipeline without a GPU.")
sys.exit(0 if ok else 1)
PY
IMPORTS=$?

echo
echo "############ 2d. PREFLIGHT (now with GPU) ############"
python3 scripts/ablation/preflight.py --data data/sampled_dfm9_mini --skip-overlap 2>&1

echo
echo "############ 2d2. VALIDATION LOADER PATCH ############"
# V1Dataset advances _epoch on every __iter__, so the SECOND evaluation against a
# one-directory validation set asks for epoch_1 and dies. This is a bug in the training
# source, not in the harness, so it is never applied silently -- you run the patch.
python3 scripts/ablation/patch_val_epoch.py --check
PATCH_RC=$?
if [ "$PATCH_RC" -eq 0 ] && python3 scripts/ablation/patch_val_epoch.py --check 2>/dev/null | grep -q "^  \[to do"; then
  echo
  echo "FAIL: the validation-loader fix is NOT applied. Repeated validation will crash at"
  echo "      the second evaluation with FileNotFoundError .../epoch_1/inst_start.npy."
  echo "      Apply and verify it with:"
  echo "        python3 scripts/ablation/patch_val_epoch.py"
  echo "        python3 scripts/ablation/verify_val_epoch.py"
  exit 1
elif [ "$PATCH_RC" -ne 0 ]; then
  echo "FAIL: patch_val_epoch.py could not match the source (see above)."
  exit 1
fi

if [ "$CHECK_ONLY" -eq 1 ]; then
  echo; echo "--check-only: stopping before the timing run."; echo "############ END ############"
  exit 0
fi
if [ "$IMPORTS" -ne 0 ]; then
  echo; echo "SKIPPING the timing run: imports failed above."; echo "############ END ############"
  exit 1
fi

echo
echo "############ 2e. TIMING RUN — 200 steps, H=2 L=3, recipe otherwise untouched ############"
# W&B: a key must actually exist. Claiming online without one makes wandb.init()
# abort the run minutes in; offline is always recoverable with `wandb sync`.
if [ -z "${HRM_WANDB_OK:-}" ]; then
  if [ -n "${WANDB_API_KEY:-}" ] || grep -qs "api\.wandb\.ai" "$HOME/.netrc"; then
    HRM_WANDB_OK=1
  else
    HRM_WANDB_OK=0
  fi
fi
if [ "$HRM_WANDB_OK" = "0" ]; then
  case "${WANDB_MODE:-}" in
    offline|disabled|dryrun) ;;
    *) [ -n "${WANDB_MODE:-}" ] && echo "W&B: WARNING -- WANDB_MODE=$WANDB_MODE but no API key; forcing offline."
       export WANDB_MODE=offline ;;
  esac
  echo "W&B: no key -> WANDB_MODE=offline  (persist a key: see scripts/ablation/setup_env.sh)"
else
  [ -z "${WANDB_MODE:-}" ] && export WANDB_MODE=online
  echo "W&B: key present -> WANDB_MODE=$WANDB_MODE"
fi

LAUNCH=(python3 scripts/ablation/run_paramfixed.py
        --timing --data dfm9_mini_val --epochs 3
        --val-every 50 --val-batches 256
        --extra memory_log_interval=50)
[ -n "$ACCEL_OV" ] && LAUNCH+=(--extra "$ACCEL_OV")
LAUNCH+=(--gpus 0)
printf '%s ' "${LAUNCH[@]}"; echo
"${LAUNCH[@]}" 2>&1

echo
echo "############ 2f. RESULTS ############"
BENCH=logs/paramfixed/XXS-timing-h2l3.bench.json
LOG=logs/paramfixed/XXS-timing-h2l3.log
if [ -f "$BENCH" ]; then
  echo "--- bench summary ---"; cat "$BENCH"
else
  echo "no bench json at $BENCH; grepping the log"
  grep -F "[bench]" "$LOG" 2>/dev/null || echo "no [bench] line found"
fi
echo
echo "--- val/loss seen? ---"
grep -iE "val/loss|validation" "$LOG" 2>/dev/null | tail -5 || echo "(none in log; check W&B)"
echo
echo "--- peak memory ---"
grep -iE "memory|GiB|GB allocated" "$LOG" 2>/dev/null | tail -5 || echo "(none)"
echo
echo "--- step timing ---"
grep -oE "[0-9]+/[0-9]+ \[[0-9:]+<[0-9:]+, +[0-9.]+it/s\]" "$LOG" 2>/dev/null | tail -3 \
  || echo "(no progress bar found)"
echo
echo "--- THE ACTUAL ERROR (child traceback, not torchrun's wrapper) ---"
# Hydra prints 'Error executing job with overrides:' then the real traceback. torchrun's
# ChildFailedError block after it is noise, so cut the log at that boundary.
if grep -q "Error executing job with overrides" "$LOG" 2>/dev/null; then
  sed -n '/Error executing job with overrides/,/torch.distributed.elastic/p' "$LOG" \
    | grep -v "^torch.distributed.elastic" | tail -60
elif grep -qE "^(Traceback|.*Error:)" "$LOG" 2>/dev/null; then
  grep -nE "Traceback|Error|Exception|OutOfMemory|StopIteration|assert" "$LOG" | tail -30
else
  echo "(no error region found -- run probably succeeded)"
fi
echo
echo "--- last 25 log lines ---"
tail -25 "$LOG" 2>/dev/null || echo "(no log)"

echo
echo "############ END ############"
} 2>&1 | tee "$REPORT"

echo
echo "Report: $REPORT"
