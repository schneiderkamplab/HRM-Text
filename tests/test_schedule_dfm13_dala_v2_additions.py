from scripts import schedule_dfm13_dala_v2_additions as s
from scripts import schedule_dfm13_wave34_baseline as base
from tests.test_schedule_dfm13_wave34_baseline import fixture


def test_additive_coverage_and_cleanup(tmp_path):
    jobs,r=fixture();r['dfm'][0]['name']='dala_lt'
    jobs=base.build(jobs,r)
    tasks=[dict(name='dala_v2_da',suite='dala_v2_da',config='/new',language='da',max_tokens=32,shards=4)]
    out=s.build(jobs,tasks,tmp_path/'populations.json');by={j.job_id:j for j in out}
    assert len(out)-len(jobs)==18
    for old in jobs:
        assert by[old.job_id].metadata==old.metadata
        if old.action==s.Action.TEARDOWN_EVAL:assert by[old.job_id]==old
    assert by['old-3200000-train']==next(j for j in jobs if j.job_id=='old-3200000-train')
    assert 'dfm13-xl-dala-v2-step_3150000-average' in by['old-3200000-wait'].deps
    assert 'dfm13-xl-dala-v2-step_3200000-average' in by['old-3250000-train'].deps
    barrier=by['dfm13-xl-wave34-step_3200000-barrier']
    assert 'dfm13-xl-dala-v2-step_3200000-dala_v2_da-0' in barrier.deps
    assert barrier.deps_mode=='terminal'
    from eval_scheduler.runtime import dependencies_satisfied
    terminal=[j.with_updates(status=s.JobStatus.FAILED) if j.job_id in barrier.deps else j for j in out]
    assert dependencies_satisfied(barrier,terminal)


def test_successor_replaces_legacy_training_dispatcher(tmp_path,monkeypatch):
    from eval_scheduler import runtime
    jobs,r=fixture();r['dfm'][0]['name']='dala_lt'
    jobs=base.build(jobs,r)
    jobs=[j.with_updates(metadata={**j.metadata,'python_bin':'/resume_training.sh',
        'vllm_python':'/env/bin/python','wandb_run_name':'test'}) for j in jobs]
    tasks=[dict(name='dala_v2_da',suite='dala_v2_da',config='/new',language='da',max_tokens=32,shards=4)]
    out=s.build(jobs,tasks,tmp_path/'populations.json')
    calls=[]
    monkeypatch.setattr(runtime,'run_command',lambda argv,**kwargs:calls.append(argv) or 0)
    for job in out:
        if job.metadata.get(s.FLAG) and job.action==s.Action.AVERAGE:
            runtime.run_average(job)
    assert len(calls)==3
    assert all(argv[:2]==['/env/bin/python','scripts/log_multilingual_headline_averages.py']
               for argv in calls)
