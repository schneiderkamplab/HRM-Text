#!/usr/bin/env python3
"""Append DFM11 epoch two to the XXL-wide campaign; finalize segment metadata."""
import argparse
import copy
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'eval_scheduler'))
from eval_scheduler.locking import PlanLock
from eval_scheduler.model import Action, JobStatus, read_plan, write_plan
from eval_scheduler.runtime import checkpoint_ready

PREFIX = 'xxlw-dfm11-'
CKPT = 'checkpoints/dfm11/XXL-wide-from-dfm10-epoch1'
OLD = 'checkpoints/dfm10/XXL-wide'
WAIT = 'wait-2484101'
TEARDOWN = 'xxlw-teardown-353465'


def finalize(plan, target):
    import numpy as np
    with PlanLock(plan):
        jobs = read_plan(plan / 'plan.tsv')
        train = next(j for j in jobs if j.job_id == f'{PREFIX}train-{target}')
        ready, _ = checkpoint_ready(train)
        finished, _ = checkpoint_ready(train.with_updates(
            metadata={**train.metadata, 'ckpt_tag': 'epoch_2'}))
        if not ready and not finished:
            raise RuntimeError('Neither target checkpoint nor epoch_2 is complete')
        epoch = None
        if ready:
            state = json.loads((ROOT / CKPT / f'checkpoint_state_step_{target}.json').read_text())
            count = len(np.load(ROOT / 'data/sampled_dfm11/epoch_1/inst_start.npy', mmap_mode='r'))
            epoch = 1 + state['global_row_cursor_in_epoch'] / count
        out = []
        for job in jobs:
            if job.job_id.startswith(PREFIX) and job.status == JobStatus.PENDING:
                meta = dict(job.metadata)
                boundary = meta.get('dfm11_boundary')
                if boundary == target and epoch is not None:
                    meta['eval_epoch'] = epoch
                if finished and boundary is not None and (boundary > target or (boundary == target and not ready)):
                    job = job.with_updates(status=JobStatus.SKIPPED)
                    meta['skip_reason'] = 'DFM11 epoch_2 completed before this boundary'
                job = job.with_updates(metadata=meta)
            out.append(job)
        if finished:
            dependency = f'{PREFIX}{target}-{TEARDOWN}' if ready else train.job_id
            out = [j.with_updates(deps=(dependency,))
                   if j.job_id == f'{PREFIX}epoch_2-{WAIT}' else j for j in out]
        write_plan(plan / 'plan.tsv', out)


def add_eval(out, template, tag, label, dependency, boundary):
    mapping = {j.job_id: f'{PREFIX}{label}-{j.job_id}' for j in template}
    def convert(value):
        if isinstance(value, str):
            return (value.replace('dfm10_XXL_wide_step353465', f'dfm11_XXL_wide_{tag}')
                    .replace('dfm10_XXL_wide', 'dfm11_XXL_wide')
                    .replace('step_353465', tag))
        if isinstance(value, dict):
            return {k: convert(v) for k, v in value.items()}
        if isinstance(value, list):
            return [convert(v) for v in value]
        return value
    for original in template:
        meta = convert(copy.deepcopy(original.metadata))
        meta.update(ckpt_path=CKPT, ckpt_tag=tag, eval_epoch=2.0 if boundary is None else 1.0,
                    dfm11_boundary=boundary)
        deps = (dependency,) if original.job_id == WAIT else tuple(mapping[d] for d in original.deps)
        out.append(original.with_updates(job_id=mapping[original.job_id], deps=deps,
            status=JobStatus.PENDING, attempt=0, name=convert(original.name),
            log_dir=convert(original.log_dir), metadata=meta))
    return mapping[TEARDOWN]


def build(jobs, plan):
    assert not any(j.job_id.startswith(PREFIX) for j in jobs), 'Already scheduled'
    train = next(j for j in jobs if j.job_id == 'xxlw-train-353465')
    a = next(i for i, j in enumerate(jobs) if j.job_id == WAIT)
    b = next(i for i, j in enumerate(jobs) if j.job_id == TEARDOWN)
    template = jobs[a:b+1]
    replacements = dict(data='dfm11', epochs='2', lr='3.75e-5', lr_auto='true', lr_min_ratio='1',
                        lr_rewarm_steps='0', lr_rewarm_start_step='null',
                        lr_decay_start_step='null', lr_decay_end_step='null', lr_cooldown_checkpoint='null',
                        **{'arch.bp_min_steps': '8', 'arch.bp_max_steps': '8'},
                        checkpoint_path=CKPT, training_total_steps='747198')
    args = [p for p in shlex.split(train.metadata['command'])
            if p.split('=', 1)[0].lstrip('+') not in replacements]
    args += [('+' if k == 'arch.bp_min_steps' else '') + f'{k}={v}' for k, v in replacements.items()]
    executable = next(i for i, p in enumerate(args) if '=' not in p)
    args[executable:executable] = [sys.executable, str(Path(__file__).resolve()),
                                 'segment', '--plan-dir', str(plan), '--']
    # An explicit stop at the estimated epoch length does not save epoch_1.
    # Finish the original data iterator before switching datasets.
    finish_id = f'{PREFIX}finish-dfm10-epoch1'
    finish_args = [p for p in shlex.split(train.metadata['command'])
                   if not p.startswith('training_total_steps=')]
    finish_args.append('training_total_steps=400000')
    finish = train.with_updates(job_id=finish_id, name='finish_dfm10_epoch1',
        deps=(TEARDOWN,), status=JobStatus.PENDING, attempt=0,
        log_dir='logs/training/dfm10_XXL_wide/finish_epoch1',
        metadata={**train.metadata, 'command': shlex.join(finish_args),
                  'ckpt_tag': 'step_400000', 'stop_after_step': 400000,
                  'resume_from_tag': 'step_353465', 'completion_checkpoint_tag': 'epoch_1'})
    out = [finish]
    previous = finish_id
    previous_train, resume = finish_id, 'epoch_1'
    for target in range(400000, 850001, 50000):
        meta = {**train.metadata, 'command': shlex.join(args), 'ckpt_path': CKPT,
                'ckpt_tag': f'step_{target}', 'stop_after_step': target,
                'completion_checkpoint_tag': 'epoch_2', 'resume_from_tag': resume,
                'resume_ckpt_path': OLD if resume == 'epoch_1' else CKPT, 'dfm11_boundary': target}
        job_id = f'{PREFIX}train-{target}'
        out.append(train.with_updates(job_id=job_id, name=f'step_{target}', deps=tuple(dict.fromkeys((previous, previous_train))),
                   status=JobStatus.PENDING, attempt=0,
                   log_dir=f'logs/training/dfm11_XXL_wide/to_{target}', metadata=meta))
        previous = add_eval(out, template, f'step_{target}', str(target), job_id, target)
        previous_train = job_id
        resume = f'step_{target}'
    add_eval(out, template, 'epoch_2', 'epoch_2', previous, None)
    out[-len(template)] = out[-len(template)].with_updates(deps=(previous, previous_train))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['append', 'segment'])
    parser.add_argument('--plan-dir', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    options, command = parser.parse_known_args()
    plan = options.plan_dir.resolve()
    if options.mode == 'segment':
        if command and command[0] == '--':
            command.pop(0)
        result = subprocess.run(command)
        if result.returncode:
            sys.exit(result.returncode)
        target = int(next(p.split('=', 1)[1] for p in command if p.startswith('stop_after_step=')))
        finalize(plan, target)
        return
    with PlanLock(plan):
        jobs = read_plan(plan / 'plan.tsv')
        additions = build(jobs, plan)
        known = {j.job_id for j in jobs + additions}
        assert len(known) == len(jobs + additions)
        assert all(set(j.deps) <= known for j in additions)
        if options.apply:
            backup = plan / 'plan.before-dfm11-xxl-wide.tsv'
            assert not backup.exists(), 'Backup already exists'
            shutil.copy2(plan / 'plan.tsv', backup)
            write_plan(plan / 'plan.tsv', jobs + additions)
    print(f'{"Appended" if options.apply else "Preview"}: {len(additions)} rows; existing rows unchanged')


if __name__ == '__main__':
    main()
