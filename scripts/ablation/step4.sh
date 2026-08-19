#!/usr/bin/env bash
# ============================================================================
# STEP 4 — run a tranche of Peter's parameter-fixed sweep for real.
#
#   bash scripts/ablation/step4.sh                 # D=2..4  (4 configs), GPU 0
#   bash scripts/ablation/step4.sh 2 4 0,1,2,3     # D=2..4 across 4 GPUs
#   bash scripts/ablation/step4.sh 5 10 0,1,2,3    # the rest, later
#   bash scripts/ablation/step4.sh 2 4 0 --dry-run # print commands only
#
# Full recipe, nothing changed but H_cycles/L_cycles:
#   XXS, 3 epochs x 5.69B tokens = 86,801 optimizer steps
#   global_batch 196,608, microbatch 16,384, grad_accum 12
#   bp ramp 2->5 as shipped, epoch_9 held out, validation every 500 steps
#
# BEFORE YOU START: these are MULTI-HOUR runs. A D=4 config is ~12.7 h. Make sure
# the UCloud job's "Hours" field is long enough -- the job is killed when it expires
# and an unfinished run is wasted. Ask for at least 1.5x the estimate below.
# ============================================================================
set -uo pipefail

MIN_D="${1:-2}"
MAX_D="${2:-4}"
GPUS="${3:-0}"
DRY=""
[ "${4:-}" = "--dry-run" ] && DRY="--dry-run"

REPORT="logs/step4-d${MIN_D}-${MAX_D}-report.txt"
[ -f pretrain.py ] || { echo "ERROR: run from the HRM-Text repo root." >&2; exit 1; }
mkdir -p logs

{
echo "STEP 4 report — $(date -u '+%Y-%m-%d %H:%M:%SZ')  host=$(hostname)"
echo "tranche D=$MIN_D..$MAX_D on GPU(s) $GPUS"

echo
echo "############ 4a. ENVIRONMENT ############"
if [ -f scripts/ablation/setup_env.sh ]; then
  # shellcheck disable=SC1091
  . scripts/ablation/setup_env.sh
fi
if ! python3 -c "import torch, flash_attn.cute" 2>/dev/null; then
  echo "environment incomplete -- building it with step2 --check-only."
  bash scripts/ablation/step2.sh --check-only 2>&1 | sed 's/^/  | /'
  python3 -c "import torch, flash_attn.cute" 2>/dev/null || {
    echo "FAIL: environment still incomplete. Stopping."; exit 1; }
fi
echo "python : $(python3 -c 'import sys;print(sys.prefix)')"
echo "torch  : $(python3 -c 'import torch;print(torch.__version__)')"
echo "GPUs   : $(nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader 2>/dev/null | tr '\n' ';')"

NGPU="$(echo "$GPUS" | tr ',' '\n' | grep -c .)"
VISIBLE="$(nvidia-smi --list-gpus 2>/dev/null | wc -l)"
if [ "$NGPU" -gt "$VISIBLE" ]; then
  echo "FAIL: asked for $NGPU GPU(s) ($GPUS) but this job only has $VISIBLE."
  echo "      Either request more GPUs on UCloud or pass a smaller list."
  exit 1
fi

echo
echo "############ 4b. VALIDATION LOADER PATCH ############"
python3 scripts/ablation/patch_val_epoch.py --check || { echo "FAIL: patch check errored."; exit 1; }
if python3 scripts/ablation/patch_val_epoch.py --check 2>/dev/null | grep -q "^  \[to do"; then
  echo "FAIL: validation fix not applied -- every run would die at the 2nd evaluation."
  echo "      python3 scripts/ablation/patch_val_epoch.py && python3 scripts/ablation/verify_val_epoch.py"
  exit 1
fi

echo
echo "############ 4c. W&B ############"
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
  echo "W&B: no key -> offline. These are multi-hour runs; you probably want them live."
  echo "     echo 'KEY' > /work/Training_Ablations/.wandb_key && chmod 600 \$_"
else
  [ -z "${WANDB_MODE:-}" ] && export WANDB_MODE=online
  echo "W&B: key present -> WANDB_MODE=$WANDB_MODE"
fi

echo
echo "############ 4d. EXPECTED COST ############"
python3 scripts/ablation/fit_scaling.py --pattern '*probe*.bench.json' \
    --min-d "$MIN_D" --max-d "$MAX_D" --val-every 500 2>&1 | tail -18 \
  || echo "(no probe data yet -- run step3.sh first for an estimate)"
echo
echo ">>> Make sure the UCloud job has more hours left than the wall-clock above."

echo
echo "############ 4e. LAUNCH ############"
date -u '+start %Y-%m-%d %H:%M:%SZ'
python3 scripts/ablation/run_paramfixed.py \
    --min-d "$MIN_D" --max-d "$MAX_D" \
    --data dfm9_mini_val --epochs 3 \
    --val-every 500 --val-batches 256 \
    --gpus "$GPUS" $DRY 2>&1
date -u '+end   %Y-%m-%d %H:%M:%SZ'

if [ -n "$DRY" ]; then echo; echo "############ END (dry run) ############"; exit 0; fi

echo
echo "############ 4f. RESULTS ############"
python3 scripts/ablation/collect.py 2>/dev/null || {
  echo "(collect.py unavailable; raw summary below)"
  for b in logs/paramfixed/*pf-d*.bench.json; do
    [ -e "$b" ] || { echo "  no bench json"; break; }
    python3 -c "
import json;d=json.load(open('$b'))
print(f\"  {'$b'.split('/')[-1]:<32} median={d['median_step_seconds']:.4f}s steps={d.get('measured_steps','?')}\")"
  done
}
echo
echo "--- per-run status ---"
for log in logs/paramfixed/*pf-d*.log; do
  [ -e "$log" ] || break
  if [ -f "${log%.log}.bench.json" ]; then
    printf '  ok   %s   final val/loss: %s\n' "$(basename "$log")" \
      "$(grep -oE 'val/loss[^0-9]*[0-9]+\.[0-9]+' "$log" | tail -1 | grep -oE '[0-9]+\.[0-9]+' || echo '?')"
  else
    echo "  FAIL $(basename "$log")"
    sed -n '/Error executing job with overrides/,/torch.distributed.elastic/p' "$log" 2>/dev/null \
      | grep -v "^torch.distributed.elastic" | tail -20 | sed 's/^/      /'
  fi
done

echo
echo "############ END ############"
} 2>&1 | tee "$REPORT"

echo
echo "Report: $REPORT"
