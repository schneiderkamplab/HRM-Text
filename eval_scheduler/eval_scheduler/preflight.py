"""Offline availability sweep for pending plan rows.

Classifies each row's runtime inputs as required-now (durable plan inputs:
configs, scripts, binaries, repository directories) or anchored (artifacts
produced by earlier rows in the same plan: shard roots, HF export dirs,
per-boundary log roots — only some existing ancestor is required so that
future boundary subdirectories do not produce false failures). Read-only:
never claims, mutates, or queries GPUs. Dataset availability inside training
configs remains out of scope.
"""
from __future__ import annotations

import os
import re
import shlex
from pathlib import Path

from .model import Action, Job

_ENV_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=[^=]*")


def check_artifact_isolation(jobs, root: Path) -> list[str]:
    """Allow shard sharing within a checkpoint, never across checkpoints.

    Check both producers and consumers so a copied consumer path cannot point
    at another experiment's otherwise valid export. Ignore rows without an
    explicit checkpoint identity (external model evaluations).
    """
    owners = {}
    errors = []
    resolved = {}

    def canonical(path):
        path = str(path)
        if path not in resolved:
            resolved[path] = str((root / path).resolve())
        return resolved[path]

    for job in jobs:
        md = job.metadata
        if not md.get("ckpt_path") or not md.get("ckpt_tag"):
            continue
        checkpoint = Path(str(md["ckpt_path"]))
        identity = (canonical(checkpoint), str(md["ckpt_tag"]))
        paths = [("export", md.get(key)) for key in
                 ("hf_export_dir", "hrm_hf_export_dir", "standard_hf_export_dir")]
        if str(job.action).startswith("eval_"):
            paths.append(("inference", job.log_dir))
        for kind, path in paths:
            if not path:
                continue
            key = (kind, canonical(path))
            previous = owners.setdefault(key, (identity, job.job_id))
            if previous[0] != identity:
                errors.append(f"artifact collision {key[1]}: {previous[1]} ({previous[0]}) "
                              f"and {job.job_id} ({identity})")
    return errors

# Metadata keys whose value must exist at preflight time. The multilingual
# manifest is consumed only by the multilingual average variant, so it is
# handled specially in check_job (dead weight on expanded-dala rows).
REQUIRED_PATH_KEYS = {
    "semantic_manifest",
    "ckpt_path", "standard_config", "dfm_single_tasks_config",
    "dfm_ifeval_config", "dfm_evals_dir",
    "export_tokenizer_path", "source_hf_export_dir", "resume_ckpt_path",
    "workdir",
}
# Metadata keys for artifacts produced by earlier rows in the same plan;
# only the path's anchor (nearest existing ancestor) must be on disk.
ANCHORED_PATH_KEYS = {
    "log_root", "dfm_log_root", "euroeval_log_root", "hf_export_dir",
    "standard_hf_export_dir", "hrm_hf_export_dir", "long_context_root",
    "plan_dir",
}
# Repository-relative scripts each action invokes.
ACTION_SCRIPTS: dict[Action, tuple[str, ...]] = {
    Action.EXPORT_HF: ("conversion/convert_to_hf.py",),
    Action.MERGE_STANDARD: ("scripts/merge_standard_eval_shards.py",),
    Action.MERGE_DFM: ("scripts/merge_dfm_eval_shards.py",),
    Action.MERGE_IFEVAL: ("scripts/merge_ifeval_da_shards.py",),
    Action.MERGE_EUROEVAL: ("scripts/log_euroeval_to_wandb.py",),
    Action.AVERAGE: ("scripts/backfill_external_eval_to_wandb.py",),
    Action.AVERAGE_LONG_CONTEXT: ("scripts/log_long_context_headline.py",),
    Action.RELOG_PROJECT_AVERAGES: ("scripts/relog_project_averages_v3.py",),
    Action.REPORT: ("scripts/generate_dfm5_l_eval_comparison_report.py",),
}
AVERAGE_SCRIPT_OVERRIDES = (
    (lambda md: md.get("average_prefix") == "headline_danish_semantic_v1", "scripts/log_danish_semantic_headline.py"),
    # (metadata predicate, script); first match wins, else ACTION_SCRIPTS fallback.
    (lambda md: md.get("expanded_dala_v2_average"), "scripts/log_expanded_dala_v2_averages.py"),
    (lambda md: md.get("multilingual_manifest"), "scripts/log_multilingual_headline_averages.py"),
)


def _missing(path: Path) -> str | None:
    return None if path.exists() else f"missing {path}"


def _unanchored(path: Path) -> str | None:
    if path.exists():
        return None
    for parent in path.parents:
        if parent.parent == parent:  # never anchor on the filesystem root
            break
        if parent.exists():
            return None
    return f"unanchored {path} (no existing ancestor)"


def _executable(path: Path) -> str | None:
    if not path.exists():
        return f"missing {path}"
    if not os.access(path, os.X_OK):
        return f"not executable {path}"
    return None


def _split_command(value: str | list[str]) -> list[str]:
    if isinstance(value, str):
        try:
            return shlex.split(value)
        except ValueError as exc:
            return [f"unparseable command: {exc}"]
    return [str(part) for part in value]


def _check_command(argv: list[str], resolve: Path, issues: list[str]) -> None:
    if argv and argv[0].startswith(("unparseable",)):
        issues.append(argv[0])
        return
    # The runner's split_command_environment consumes leading KEY=VALUE tokens.
    body = list(argv)
    while body and _ENV_ASSIGNMENT.fullmatch(body[0]):
        body.pop(0)
    if body:
        path = Path(body[0])
        problem = _executable(path if path.is_absolute() else resolve / path)
        if problem:
            issues.append(f"command: {problem}")
    for token in body[1:]:
        value = token
        if "=" in token and not token.startswith("/"):
            value = token.split("=", 1)[1].lstrip("+~^@")
        if value.startswith("/") and not value.startswith("/dev"):
            path = Path(value)
            if path.suffix in {".py", ".yaml", ".json", ".so", ".jinja"}:
                problem = _missing(path)
            else:
                problem = _unanchored(path)
            if problem:
                issues.append(f"command: {problem}")


def repo_root() -> Path:
    """Locate the repository root the runner would use as its cwd.

    Prefers the current directory when it is the repo (contains pretrain.py
    and scripts/), then the vendored package location, then parent walks.
    """
    package_root = Path(__file__).resolve().parents[2]
    for candidate in (Path.cwd(), package_root, *Path.cwd().parents, *package_root.parents):
        if (candidate / 'pretrain.py').is_file() and (candidate / 'scripts').is_dir():
            return candidate
    return Path.cwd()


def check_job(job: Job, resolve: Path | None = None) -> list[str]:
    """Return human-readable availability issues for one job definition."""
    issues: list[str] = []
    resolve = resolve or repo_root()
    md = job.metadata
    if job.action == Action.AVERAGE and not md.get("expanded_dala_v2_average") \
            and md.get("multilingual_manifest"):
        path = Path(str(md["multilingual_manifest"]))
        problem = _missing(path if path.is_absolute() else resolve / path)
        if problem:
            issues.append(f"multilingual_manifest: {problem}")
    for key in sorted(REQUIRED_PATH_KEYS & md.keys()):
        path = Path(str(md[key]))
        problem = _missing(path if path.is_absolute() else resolve / path)
        if problem:
            issues.append(f"{key}: {problem}")
    for key in sorted(ANCHORED_PATH_KEYS & md.keys()):
        path = Path(str(md[key]))
        problem = _unanchored(path if path.is_absolute() else resolve / path)
        if problem:
            issues.append(f"{key}: {problem}")
    for key in ("python_bin", "vllm_python"):
        if md.get(key):
            path = Path(str(md[key]))
            problem = _executable(path if path.is_absolute() else resolve / path)
            if problem:
                issues.append(f"{key}: {problem}")
    if md.get("euroeval_bin"):
        _check_command(_split_command(str(md["euroeval_bin"])), resolve, issues)
    if md.get("judge_server_model") and str(md["judge_server_model"]).startswith("/"):
        problem = _missing(Path(str(md["judge_server_model"])))
        if problem:
            issues.append(f"judge_server_model: {problem}")
    if job.action == Action.TRAIN_UNTIL_STEP:
        raw = md.get("command")
        if isinstance(raw, (str, list)) and raw:
            argv = _split_command(raw)
            workdir = Path(str(md.get("workdir") or resolve))
            _check_command(argv, workdir, issues)
        coop = md.get("cooperative_training")
        if isinstance(coop, dict):
            control = coop.get("control_root")
            if control:
                problem = _unanchored(Path(str(control)))
                if problem:
                    issues.append(f"cooperative_training.control_root: {problem}")
            for key in ("launcher_settings",):
                if coop.get(key):
                    problem = _missing(Path(str(coop[key])))
                    if problem:
                        issues.append(f"cooperative_training.{key}: {problem}")
            if coop.get("python"):
                path = Path(str(coop["python"]))
                problem = _executable(path if path.is_absolute() else resolve / path)
                if problem:
                    issues.append(f"cooperative_training.python: {problem}")
            cuda = coop.get("cuda_checkpoint")
            if isinstance(cuda, dict):
                for key in ("shim_library", "nccl_library", "cuda_checkpoint_binary"):
                    if cuda.get(key):
                        problem = _missing(Path(str(cuda[key])))
                        if problem:
                            issues.append(f"cooperative_training.cuda_checkpoint.{key}: {problem}")
    if job.action == Action.AVERAGE:
        scripts = None
        for predicate, script in AVERAGE_SCRIPT_OVERRIDES:
            if predicate(md):
                scripts = (script,)
                break
        if scripts is None:
            scripts = ACTION_SCRIPTS.get(job.action, ())
    else:
        scripts = ACTION_SCRIPTS.get(job.action, ())
    for script in scripts:
        problem = _missing(resolve / script)
        if problem:
            issues.append(f"script: {problem}")
    return issues
