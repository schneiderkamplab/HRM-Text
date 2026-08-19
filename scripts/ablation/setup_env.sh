# ============================================================================
# Persistent Python environment for the HRM ablations.  SOURCE THIS, don't run it.
#
#     source scripts/ablation/setup_env.sh
#
# WHY
#   UCloud job homes are per-job: ~/.local is empty in every new job, so
#   `pip install --user` has to redo ~2 minutes of work each time you restart.
#   /work is the mounted drive and DOES persist, so the environment lives there:
#
#       /work/Training_Ablations/venv
#
#   First call creates it and installs everything (~2 min). Every later call in
#   every later job just activates it (~2 s).
#
# Override the location with HRM_VENV=/some/path before sourcing.
# Force a rebuild with HRM_VENV_REBUILD=1.
#
# Sets HRM_ENV_OK=1 on success, 0 on failure. Never calls exit -- it is sourced,
# and exiting would kill the caller's shell.
# ============================================================================

HRM_VENV="${HRM_VENV:-/work/Training_Ablations/venv}"
HRM_ENV_OK=0

_hrm_env_main() {
    local venv="$HRM_VENV"
    local pyver base_py accel req marker

    if ! command -v python3 >/dev/null 2>&1; then
        echo "setup_env: no python3 on PATH" >&2; return 1
    fi
    pyver="$(python3 -c 'import sys;print("%d.%d" % sys.version_info[:2])')"

    if [ "${HRM_VENV_REBUILD:-0}" = "1" ] && [ -d "$venv" ]; then
        echo "setup_env: HRM_VENV_REBUILD=1 -- removing $venv"
        rm -rf "$venv"
    fi

    # A venv hardcodes the absolute path of the interpreter that built it. If the job
    # image ever ships a different Python, the venv silently breaks -- detect and rebuild
    # rather than fail with something obscure two steps later.
    if [ -x "$venv/bin/python" ]; then
        base_py="$("$venv/bin/python" -c 'import sys;print("%d.%d" % sys.version_info[:2])' 2>/dev/null)"
        if [ "$base_py" != "$pyver" ]; then
            echo "setup_env: venv is Python ${base_py:-<broken>} but this job has $pyver -- rebuilding"
            rm -rf "$venv"
        fi
    fi

    if [ ! -x "$venv/bin/python" ]; then
        echo "setup_env: creating $venv (Python $pyver) -- first time only, ~2 min"
        mkdir -p "$(dirname "$venv")" || { echo "setup_env: cannot create $(dirname "$venv")" >&2; return 1; }
        python3 -m venv "$venv" || { echo "setup_env: python3 -m venv failed" >&2; return 1; }
    fi

    # shellcheck disable=SC1091
    . "$venv/bin/activate" || { echo "setup_env: could not activate $venv" >&2; return 1; }
    echo "setup_env: active -> $venv"

    # Which FlashAttention build? Needs torch, so base deps go in first.
    marker="$venv/.hrm-ready-$pyver"
    if [ -f "$marker" ]; then
        accel="$(cat "$marker")"
        if HRM_ACCEL="$accel" python3 - <<'PY' 2>/dev/null
import importlib, os, sys
importlib.import_module("torch")
mod = {"sm100": "flash_attn.cute", "sm90": "flash_attn_interface"}.get(os.environ["HRM_ACCEL"])
if mod:
    importlib.import_module(mod)
sys.exit(0)
PY
        then
            echo "setup_env: dependencies already installed ($accel) -- nothing to do"
            return 0
        fi
        echo "setup_env: marker says $accel but the imports fail -- reinstalling"
    fi

    echo "setup_env: installing base dependencies into the venv"
    python3 -m pip install --quiet --upgrade pip >/dev/null 2>&1
    python3 -m pip install --quiet \
        torch numpy numba einops pydantic hydra-core omegaconf tqdm wandb coolname PyYAML \
        || { echo "setup_env: base dependency install failed" >&2; return 1; }

    case "$(python3 -c 'import torch;print(torch.cuda.get_device_capability(0)[0] if torch.cuda.is_available() else 0)' 2>/dev/null || echo 0)" in
        10) accel=sm100; req=requirements-sm100.txt ;;
        9)  accel=sm90;  req=requirements-sm90.txt  ;;
        *)  echo "setup_env: no CUDA GPU visible -- base deps installed, FlashAttention skipped"
            printf 'cpu' > "$marker"; return 0 ;;
    esac

    if [ -f "$req" ]; then
        echo "setup_env: installing $req ($accel)"
        python3 -m pip install --quiet -r "$req" \
            || { echo "setup_env: $req install failed" >&2; return 1; }
    else
        echo "setup_env: $req not found (are you in the repo root?) -- skipping" >&2
        return 1
    fi

    printf '%s' "$accel" > "$marker"
    echo "setup_env: ready ($accel)"
    return 0
}

if _hrm_env_main; then HRM_ENV_OK=1; else HRM_ENV_OK=0; fi
unset -f _hrm_env_main

# ---------------------------------------------------------------------------
# W&B credentials, same problem as the venv: `wandb login` writes ~/.netrc, and ~ is
# per-job. A key that worked yesterday is gone today, and wandb.init() then kills the
# run several minutes in. Keep the key on /work, next to the venv and OUTSIDE the git
# repo, and export it here.
#
# One-time setup:
#     echo 'YOUR_KEY' > /work/Training_Ablations/.wandb_key && chmod 600 /work/Training_Ablations/.wandb_key
# Key from https://wandb.ai/authorize
# ---------------------------------------------------------------------------
HRM_WANDB_KEY_FILE="${HRM_WANDB_KEY_FILE:-$(dirname "$HRM_VENV")/.wandb_key}"
HRM_WANDB_OK=0

if [ -n "${WANDB_API_KEY:-}" ]; then
    HRM_WANDB_OK=1
    echo "setup_env: W&B key from WANDB_API_KEY"
elif [ -f "$HRM_WANDB_KEY_FILE" ]; then
    WANDB_API_KEY="$(tr -d ' \t\n\r' < "$HRM_WANDB_KEY_FILE")"
    if [ -n "$WANDB_API_KEY" ]; then
        export WANDB_API_KEY
        HRM_WANDB_OK=1
        echo "setup_env: W&B key loaded from $HRM_WANDB_KEY_FILE"
    else
        unset WANDB_API_KEY
        echo "setup_env: $HRM_WANDB_KEY_FILE is empty"
    fi
elif grep -qs "api\.wandb\.ai" "$HOME/.netrc"; then
    HRM_WANDB_OK=1
    echo "setup_env: W&B key found in ~/.netrc (this job only -- see $HRM_WANDB_KEY_FILE to persist)"
fi

# Never let WANDB_MODE claim online without a key: wandb.init() would abort the run
# minutes in. Offline is always recoverable with `wandb sync`.
if [ "$HRM_WANDB_OK" = "0" ]; then
    case "${WANDB_MODE:-}" in
        offline|disabled|dryrun) ;;
        *)
            [ -n "${WANDB_MODE:-}" ] && \
                echo "setup_env: WARNING -- WANDB_MODE=$WANDB_MODE but NO API key is available."
            export WANDB_MODE=offline
            echo "setup_env: W&B -> offline. Runs will still complete; \`wandb sync wandb/offline-run-*\` later."
            echo "           To go online in every future job, once:"
            echo "             echo 'YOUR_KEY' > $HRM_WANDB_KEY_FILE && chmod 600 $HRM_WANDB_KEY_FILE"
            ;;
    esac
else
    [ -z "${WANDB_MODE:-}" ] && export WANDB_MODE=online
    echo "setup_env: W&B -> ${WANDB_MODE}"
fi
export HRM_WANDB_KEY_FILE HRM_WANDB_OK

# pip inside an active venv must NOT get --user; outside one it should. Callers that
# still shell out to pip can use $HRM_PIP_USER.
if python3 -c 'import sys;sys.exit(0 if sys.prefix!=sys.base_prefix else 1)' 2>/dev/null; then
    HRM_PIP_USER=""
else
    HRM_PIP_USER="--user"
fi
export HRM_VENV HRM_ENV_OK HRM_PIP_USER
