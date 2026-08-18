#!/usr/bin/env bash
# ============================================================================
# STEP 1 — verify Peter's rebuilt DFM9-mini and set up the validation view.
#
# CPU only. No GPU-hours, no training, no heavy installs. Needs numpy.
#
#   bash step1.sh                                  # uses ./data/sampled_dfm9_mini
#   bash step1.sh /work/HRM-Text/data/sampled_dfm9_mini
#
# Run from the repo root. Writes logs/step1-report.txt.
# ============================================================================
set -uo pipefail

DATA="${1:-data/sampled_dfm9_mini}"
VAL="data/val_dfm9_mini"
HOLDOUT_EPOCH="${2:-9}"     # reserved for validation; training must never reach it
TRAIN_EPOCHS="${3:-3}"      # canonical DFM9-mini recipe: ~5B/epoch x 3 = ~15B
VAL_ROWS="${4:-2000}"       # small on purpose -- see make_val_from_epoch.py --rows
VAL_BATCHES=256             # > batches in the val set, so every eval sees the same data
REPORT="logs/step1-report.txt"

[ -f pretrain.py ] || { echo "ERROR: run from the HRM-Text repo root." >&2; exit 1; }
mkdir -p logs

# UCloud job homes are ephemeral -- ~/.local does not survive a new job, so numpy has to
# be (re)installed each session. Tiny wheel, no torch, no vllm.
if ! python3 -c "import numpy" 2>/dev/null; then
  echo "numpy missing -- installing (small wheel, seconds) ..."
  pip install --quiet --user numpy || pip install --quiet numpy || {
    echo "ERROR: could not install numpy. Install it and re-run." >&2; exit 1; }
fi
python3 -c "import numpy; print('numpy', numpy.__version__)"

{
echo "STEP 1 report — $(date -u '+%Y-%m-%d %H:%M:%SZ')  host=$(hostname)"
echo "data = $DATA   holdout epoch = $HOLDOUT_EPOCH   train epochs = $TRAIN_EPOCHS"

echo
echo "############ 1a. tokens.npy INTEGRITY ############"
python3 scripts/ablation/check_npy.py "$DATA/tokens.npy" 2>&1
INTEGRITY=$?

echo
echo "############ 1b. DATASET STRUCTURE ############"
python3 scripts/ablation/preflight.py --data "$DATA" --cpu-session --skip-overlap 2>&1

echo
echo "############ 1c. VALIDATION VIEW (dry run) ############"
python3 scripts/ablation/make_val_from_epoch.py \
    --src "$DATA" --out "$VAL" --epoch "$HOLDOUT_EPOCH" --rows "$VAL_ROWS" --dry-run 2>&1

echo
echo "############ 1d. BUILD + VERIFY VALIDATION VIEW ############"
if [ "$INTEGRITY" -eq 0 ]; then
  python3 scripts/ablation/make_val_from_epoch.py \
      --src "$DATA" --out "$VAL" --epoch "$HOLDOUT_EPOCH" --rows "$VAL_ROWS" --verify 2>&1
else
  echo "SKIPPED: tokens.npy did not pass 1a. Fix that before building the split."
fi

echo
echo "############ 1e. DATA CONFIG ############"
CFG=config/data/dfm9_mini_val.yaml
cat > "$CFG" <<YAML
# Peter's dfm9_mini, plus epoch_$HOLDOUT_EPOCH held out for validation.
# Training reads $DATA/epoch_0..$((HOLDOUT_EPOCH-1)); canonical recipe is epochs=$TRAIN_EPOCHS.
# epoch_$HOLDOUT_EPOCH is the validation holdout -- never train on it.
# The validation dir is symlinks only -- no token data is duplicated.
path: $DATA
validation_path: $VAL
target_only: true
YAML
echo "wrote $CFG"
cat "$CFG"
echo "--- Peter's original, left untouched ---"
cat config/data/dfm9_mini.yaml 2>&1

echo
echo "############ 1f. LAUNCH COMMAND FOR STEP 2 (nothing runs) ############"
python3 scripts/ablation/run_paramfixed.py \
    --timing --data dfm9_mini_val --epochs "$TRAIN_EPOCHS" \
    --val-every 50 --val-batches "$VAL_BATCHES" --dry-run 2>&1

echo
echo "############ END ############"
} 2>&1 | tee "$REPORT"

echo
echo "Report: $REPORT"
