from scripts.extend_dfm12_multilingual_evals import extended_jobs
from scripts.schedule_dfm12_xl_epoch11 import SOURCE_PLAN, TEMPLATE_PREFIX, build
from eval_scheduler.model import Action, JobStatus, read_plan


def test_baseline_and_all_future_checkpoints_get_new_tasks(tmp_path):
    template=[j for j in read_plan(SOURCE_PLAN/'plan.tsv') if j.job_id.startswith(TEMPLATE_PREFIX)]
    jobs=build(template,dict(start_step=2877261,end_step=3000079),tmp_path,tmp_path/'run.json')
    jobs=[j.with_updates(status=JobStatus.DONE) if j.action in
          (Action.TERMINAL_BARRIER,Action.TEARDOWN_EVAL) else j for j in jobs]
    registry=dict(headline_manifest='config/populations.json',
        dfm=[dict(name='dala_en',language='en',suite='dala_en',config='config/tasks.yaml',shards=2)],
        euroeval=[dict(dataset='dbrd',language='nl')])
    expanded=extended_jobs(jobs,registry,tmp_path)
    for tag in ('epoch_10','step_2900000','step_2950000','step_3000000','epoch_11'):
        added=[j for j in expanded if j.metadata.get('ckpt_tag')==tag and j.metadata.get('multilingual_extension')]
        assert sum(j.action==Action.EVAL_DFM for j in added)==2
        assert sum(j.action==Action.EVAL_EUROEVAL for j in added)==1
        barrier=next(j for j in expanded if j.metadata.get('ckpt_tag')==tag and j.action==Action.TERMINAL_BARRIER)
        assert barrier.status == JobStatus.PENDING
        teardown=next(j for j in expanded if j.metadata.get('ckpt_tag')==tag and j.action==Action.TEARDOWN_EVAL)
        assert teardown.status == JobStatus.PENDING
        assert all(j.job_id in barrier.deps for j in added if j.action in (Action.EVAL_DFM,Action.EVAL_EUROEVAL))
    wait=next(j for j in expanded if j.metadata.get('ckpt_tag')=='step_2900000' and j.action==Action.WAIT_CHECKPOINT)
    assert 'dfm12-multilingual-epoch_10-teardown' in wait.deps
    baseline=next(j for j in expanded if j.metadata.get('ckpt_tag')=='epoch_10' and j.action==Action.EXPORT_HF)
    assert baseline.metadata['eval_epoch']==10.0
    assert baseline.metadata['eval_step']==2877261
    assert baseline.metadata['no_ema'] is False
    final=next(j for j in expanded if j.metadata.get('ckpt_tag')=='epoch_11' and j.action==Action.AVERAGE)
    assert final.metadata['eval_step']==3000079
    old=[j for j in expanded if j.action==Action.EVAL_STANDARD]
    assert len(old)==sum(j.action==Action.EVAL_STANDARD for j in jobs)
