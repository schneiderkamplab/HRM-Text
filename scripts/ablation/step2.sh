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

echo
echo "############ 2b. MINIMAL TRAINING DEPENDENCIES ############"
python3 -m pip install --user --quiet \
    torch numpy numba einops pydantic hydra-core omegaconf tqdm wandb coolname PyYAML \
  && echo "base deps OK" || echo "WARN: some base deps failed; see errors above"

CAP="$(python3 -c 'import torch;print(torch.cuda.get_device_capability(0)[0] if torch.cuda.is_available() else 0)' 2>/dev/null || echo 0)"
echo "cuda capability major: $CAP"
case "$CAP" in
  10) ACCEL=sm100; REQ=requirements-sm100.txt; FA_MOD=flash_attn.cute ;;
  9)  ACCEL=sm90;  REQ=requirements-sm90.txt;  FA_MOD=flash_attn_interface ;;
  *)  echo "FAIL: no CUDA GPU visible to torch."; exit 1 ;;
esac
echo "-> accelerator_type=$ACCEL, installing $REQ"
python3 -m pip install --user --quiet -r "$REQ" \
  && echo "FlashAttention install OK" || echo "WARN: FlashAttention install reported errors"

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
export WANDB_MODE="${WANDB_MODE:-offline}"
echo "WANDB_MODE=$WANDB_MODE   (offline needs no login; \`wandb sync wandb/offline-run-*\` to upload)"
python3 scripts/ablation/run_paramfixed.py \
    --timing --data dfm9_mini_val --epochs 3 \
    --val-every 50 --val-batches 256 \
    --extra memory_log_interval=50 \
    --gpus 0 2>&1

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
echo "--- last 25 log lines ---"
tail -25 "$LOG" 2>/dev/null || echo "(no log)"

echo
echo "############ END ############"
} 2>&1 | tee "$REPORT"

echo
echo "Report: $REPORT"
