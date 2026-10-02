from scripts.append_euroeval_language_additions import extend
from eval_scheduler.model import Action, Job, JobStatus


def test_additions_include_baseline_and_block_training_release():
    jobs = []
    for tag in ('epoch_10', 'step_2900000', 'step_2950000'):
        meta = {'ckpt_tag': tag, 'multilingual_extension': True,
                'euroeval_log_root': '/tmp/euro', 'euroeval_bin': 'pinned-python',
                'eval_epoch': 10, 'log_wandb': True}
        jobs += [
            Job(job_id=tag+'-export', action=Action.EXPORT_HF, family='export', name=tag, metadata=meta),
            Job(job_id=tag+'-eval', action=Action.EVAL_EUROEVAL, family='euroeval',
                name='scala-da', deps=(tag+'-export',), metadata=meta),
            Job(job_id=tag+'-barrier', action=Action.TERMINAL_BARRIER, family='campaign', name=tag,
                status=JobStatus.DONE if tag=='epoch_10' else JobStatus.PENDING,
                deps=(tag+'-eval',), metadata=meta)]
    tasks = [{'dataset':'multi-ifeval-en','language':'en','category':'instruction-following'}]
    result, ids = extend(jobs, tasks)
    assert len(result) == len(jobs) + 3
    barrier = next(j for j in result if j.job_id == 'step_2900000-barrier')
    assert set(ids['epoch_10'] + ids['step_2900000']) <= set(barrier.deps)
    new = next(j for j in result if j.job_id == ids['epoch_10'][0])
    assert new.metadata['log_wandb'] and new.shard is None
    assert new.metadata['euroeval_bin'] == 'pinned-python'
    again, ids = extend(result, tasks)
    assert again == result and not ids
