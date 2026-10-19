"""Exclusive native-inference subplan for architectures without HF/vLLM export.

Reuse the legacy per-GPU executor and scorers, under one SQLite GPU lease.
Never disguise a v2 checkpoint as a v1 HF export.
"""
from pathlib import Path

from .model import Action, JobStatus, read_plan, plan_database


ALLOWED = frozenset((Action.EVAL_STANDARD, Action.EVAL_DFM, Action.EVAL_DFM_IFEVAL,
                     Action.MERGE_STANDARD, Action.MERGE_DFM, Action.MERGE_IFEVAL,
                     Action.EXPORT_DFM_RESULTS, Action.TERMINAL_BARRIER))


def validate_native_plan(job, parent_dir=None):
    child = Path(job.metadata['native_plan_dir']).resolve()
    if job.gpu_policy != 'all':
        raise ValueError('Native subplans require an exclusive all-GPU allocation')
    if parent_dir is not None and child == Path(parent_dir).resolve():
        raise ValueError('Native subplan cannot be its parent')
    if plan_database(child / 'plan.tsv') is not None:
        raise ValueError('Native subplan must use the per-GPU TSV executor')
    jobs = read_plan(child / 'plan.tsv')
    if not jobs or any(j.action not in ALLOWED for j in jobs):
        raise ValueError('Native subplan contains unsupported or recursive actions')
    for row in jobs:
        if row.requires_gpu and (row.metadata.get('standard_engine_backend', 'simple') != 'simple'
                                or row.metadata.get('hrm_server_backend', 'simple') != 'simple'
                                or row.metadata.get('external_model')):
            raise ValueError('Native subplan must not launch vLLM/external models')
        if row.status == JobStatus.RUNNING:
            raise ValueError('Reconcile interrupted native claims before resuming')
    return child


def run_native_plan(job, gpus):
    from . import runtime
    if not gpus:
        raise ValueError('Native subplan has no allocated GPUs')
    child = validate_native_plan(job)
    status = runtime.run_command(
        [runtime.python_bin(job), '-m', 'eval_scheduler', 'run', '--backend', 'tsv',
         '--plan-dir', str(child), '--gpus', ','.join(map(str, gpus))],
        log_path=Path(job.log_dir) / 'native-plan.log')
    if status:
        return status
    jobs = read_plan(child / 'plan.tsv')
    # Legacy runners can exit zero with failed/blocked rows. Do not report success.
    if any(j.status != JobStatus.DONE for j in jobs):
        return 1
    return 0
