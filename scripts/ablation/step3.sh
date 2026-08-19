#!/usr/bin/env bash
# ============================================================================
# STEP 3 — how does step time scale with recurrent depth D?
#
# Four short runs, ~10 minutes total, then a linear fit that costs the full
# 17-config sweep. Run from the repo root on a full B200, after step2 has passed.
#
#   bash scripts/ablation/step3.sh          # probe + fit
#   bash scripts/ablation/step3.sh --fit    # re-fit existing bench json, run nothing
#
# The cells are chosen deliberately:
#   1x1  D=2   low anchor
#   1x4  D=5   mid point -- tests that t(D) really is linear, not just two dots
#   1x7  D=8   |
#   2x3  D=8   |  same D, three different splits: the control
#   4x1  D=8   |
#   1x9  D=10  high anchor
#
# 2x3 is re-measured HERE even though step2 already timed it, because step2 runs with
# validation on over 200 steps. Mixing that number into a comparison against 100-step
# validation-off probes made the split spread look like 9.6% when the like-for-like
# figure is 2.3%. Only compare runs measured the same way.
#
# The two D=8 cells are the control. Block invocations per forward pass are
# H*L + H = H*(L+1) = D regardless of the split, so all three D=8 configs should
# take the SAME time. If they do not, step time is not a function of D alone and
# the sweep estimate from two anchors is not valid.
#
# Validation is OFF here on purpose -- an evaluation costs ~7s and would pollute
# the median.
# ============================================================================
set -uo pipefail

FIT_ONLY=0
[ "${1:-}" = "--fit" ] && FIT_ONLY=1

REPORT="logs/step3-report.txt"
[ -f pretrain.py ] || { echo "ERROR: run from the HRM-Text repo root." >&2; exit 1; }
mkdir -p logs

PROBE_CELLS="${PROBE_CELLS:-1x1,1x4,1x7,2x3,4x1,1x9}"
PROBE_STEPS="${PROBE_STEPS:-100}"

{
echo "STEP 3 report — $(date -u '+%Y-%m-%d %H:%M:%SZ')  host=$(hostname)"

if [ "$FIT_ONLY" -eq 0 ]; then
  echo
  echo "############ 3z. ENVIRONMENT ############"
  # UCloud job homes are PER JOB: ~/.local does not survive into a new job, so a fresh
  # job has neither torch nor the torchrun console script even though step2 passed
  # yesterday. Re-run step2's installer rather than assuming.
  if [ -f scripts/ablation/setup_env.sh ]; then
    # shellcheck disable=SC1091
    . scripts/ablation/setup_env.sh
  fi
  if ! python3 -c "import torch, flash_attn.cute" 2>/dev/null; then
    echo "environment incomplete -- running step2 --check-only to build it."
    bash scripts/ablation/step2.sh --check-only 2>&1 | sed 's/^/  | /'
    if ! python3 -c "import torch, flash_attn.cute" 2>/dev/null; then
      echo "FAIL: environment still incomplete after step2 --check-only. Stopping."
      exit 1
    fi
  fi
echo "environment OK: $(python3 -c 'import sys,torch;print(sys.prefix, torch.__version__)')"

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

  echo
  echo "############ 3a. D-SCALING PROBE ############"
  echo "cells=$PROBE_CELLS  steps=$PROBE_STEPS  validation OFF"
  python3 scripts/ablation/run_paramfixed.py \
      --cells "$PROBE_CELLS" --tag probe \
      --data dfm9_mini_val --epochs 3 \
      --max-steps "$PROBE_STEPS" --val-every 0 \
      --gpus 0 2>&1
else
  echo
  echo "############ 3a. SKIPPED (--fit) ############"
fi

echo
echo "############ 3b. PER-RUN MEDIANS ############"
for f in logs/paramfixed/*.bench.json; do
  [ -e "$f" ] || { echo "(no bench json yet)"; break; }
  python3 -c "
import json,sys
d=json.load(open('$f'))
print(f\"  {'$f'.split('/')[-1]:<34} median={d['median_step_seconds']:.4f}s  \"
      f\"steps={d.get('measured_steps','?')}\")"
done

echo
echo "############ 3b2. FAILURES ############"
FAILED=0
for log in logs/paramfixed/*probe*.log; do
  [ -e "$log" ] || { echo "(no probe logs)"; break; }
  base="${log%.log}"
  if [ -f "$base.bench.json" ]; then
    echo "  ok   $(basename "$log")"
    continue
  fi
  FAILED=1
  echo "  FAIL $(basename "$log") -- child error:"
  if grep -q "Error executing job with overrides" "$log" 2>/dev/null; then
    sed -n '/Error executing job with overrides/,/torch.distributed.elastic/p' "$log" \
      | grep -v "^torch.distributed.elastic" | tail -30 | sed 's/^/      /'
  else
    grep -nE "Traceback|Error|Exception|No module|not found" "$log" 2>/dev/null \
      | tail -15 | sed 's/^/      /' || true
    echo "      --- last 15 lines ---"
    tail -15 "$log" | sed 's/^/      /'
  fi
done
[ "$FAILED" = "1" ] && echo && echo "One or more probes failed; the fit below will be short of points."

echo
echo "############ 3c. FIT + SWEEP BUDGET ############"
python3 scripts/ablation/fit_scaling.py --val-every 500 \
    --pattern '*probe*.bench.json' 2>&1

echo
echo "############ END ############"
} 2>&1 | tee "$REPORT"

echo
echo "Report: $REPORT"
