import shlex

from scripts.schedule_xl_identity_interlude import (
    Action, Job, JobStatus, XXL_JOB, XL_JOB, BARRIER, END, START,
    STOP_TAG, insert_interlude, overrides,
)
from eval_scheduler.runtime import dependencies_satisfied


def test_interlude_preserves_xxl_except_resume_and_dependency():
    previous = Job('previous',Action.TERMINAL_BARRIER,'control','previous',status=JobStatus.DONE)
    xxl = Job(XXL_JOB,Action.TRAIN_UNTIL_STEP,'training','XXL',deps=('previous',),
              status=JobStatus.RUNNING,metadata={'command':'torchrun pretrain.py lr=3e-4 resume_checkpoint_tag=step_660000',
                  'stop_after_step':700000,'wandb_run_id':'xxl-original','extra':'untouched'})
    tail = Job('tail',Action.WAIT_CHECKPOINT,'wait','700K',deps=(XXL_JOB,))
    jobs = insert_interlude([previous,xxl,tail])
    by_id = {j.job_id:j for j in jobs}
    assert jobs[-1] is tail
    assert by_id[XXL_JOB].metadata['wandb_run_id'] == 'xxl-original'
    assert by_id[XXL_JOB].metadata['extra'] == 'untouched'
    assert by_id[XXL_JOB].metadata['stop_after_step'] == 700000
    assert f'resume_checkpoint_tag={STOP_TAG}' in shlex.split(by_id[XXL_JOB].metadata['command'])
    assert 'lr=3e-4' in shlex.split(by_id[XXL_JOB].metadata['command'])
    assert by_id[XXL_JOB].status == JobStatus.PENDING
    assert not dependencies_satisfied(by_id[XXL_JOB],jobs)
    failed = [j.with_updates(status=JobStatus.FAILED) if j.job_id==XL_JOB else j for j in jobs]
    assert dependencies_satisfied(by_id[BARRIER],failed)
    released = [j.with_updates(status=JobStatus.DONE) if j.job_id==BARRIER else j for j in failed]
    assert dependencies_satisfied(by_id[XXL_JOB],released)


def test_xl_constant_lr_and_exact_duration():
    args = dict(s.lstrip('+').split('=',1) for s in overrides())
    assert END - START == 1000
    assert args['lr'] == '1e-5'
    assert args['lr_auto'] == 'true'
    assert args['lr_warmup_steps'] == '0'
    assert args['lr_min_ratio'] == '1'
    assert args['lr_piecewise_points'] == args['lr_cooldown_checkpoint'] == 'null'
    assert args['arch.bp_min_steps'] == args['arch.bp_max_steps'] == '8'
    assert args['gradient_accumulation_steps'] == '2'
    assert args['global_batch_size'] == '262144'
    assert args['resume_checkpoint_tag'] == 'epoch_10'
    assert args['epochs'] == '11'
    assert args['wandb_run_id'] != 'xxl-restart520k-20260910'
