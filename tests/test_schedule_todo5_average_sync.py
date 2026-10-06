import pytest
from scripts import schedule_todo5_average_sync as s
from scripts import schedule_dfm13_wave34_baseline as base
from tests.test_schedule_dfm13_wave34_baseline import fixture


def test_deferred_average_sync_preserves_training_and_cleanup(monkeypatch):
    jobs,registry=fixture();jobs=base.build(jobs,registry)
    monkeypatch.setattr(s,'file_hash',lambda p:'testhash')
    out=s.build(jobs);by={j.job_id:j for j in out}
    assert by[s.ID].deps==(s.SYNC_ID,)
    assert by[s.HIST].deps==(s.ID,)
    assert by[s.POP].deps==('dfm13-xl-wave34-step_3150000-average',s.HIST)
    assert s.POP in by['old-3200000-wait'].deps
    for j in jobs:
        if j.action==s.Action.TRAIN_UNTIL_STEP or j.action in (s.Action.TEARDOWN_EVAL,s.Action.TERMINAL_BARRIER):
            assert by[j.job_id]==j
        if j.metadata.get(s.MARK) and s.boundary(j)==3150000 and s.SYNC_ID in j.deps:
            assert s.ID in by[j.job_id].deps
            assert s.HIST in by[j.job_id].deps
    from eval_scheduler.runtime import dependencies_satisfied
    failed=[j.with_updates(status=s.JobStatus.FAILED) if j.job_id==s.ID else j for j in out]
    baseline=next(j for j in out if j.metadata.get(s.MARK) and s.boundary(j)==3150000 and j.action==s.Action.EVAL_DFM)
    assert not dependencies_satisfied(baseline,failed)


def test_no_reinstallation(monkeypatch):
    jobs,registry=fixture();jobs=base.build(jobs,registry)
    monkeypatch.setattr(s,'file_hash',lambda p:'testhash')
    with pytest.raises(ValueError,match='Already installed'):s.build(s.build(jobs))


def test_future_successor_namespaces_and_gates(monkeypatch):
    jobs,registry=fixture();jobs=base.build(jobs,registry)
    jobs=[j.with_updates(metadata={**j.metadata,'average_prefix':'headline_avg_v3'})
          if j.job_id in ('old-3200000-average','old-3250000-average') else j for j in jobs]
    monkeypatch.setattr(s,'file_hash',lambda p:'testhash')
    out=s.build(jobs);by={j.job_id:j for j in out}
    successor=by['dfm13-xl-todo5-step_3200000-average']
    assert successor.metadata['average_prefix']=='headline_avg_talemaader_v2'
    assert successor.metadata['extra_average_prefixes']==['suite_avg_talemaader_v2']
    assert successor.metadata['atomic_v3_averages'] is False
    assert by['old-3200000-average']==next(j for j in jobs if j.job_id=='old-3200000-average')
    assert successor.job_id in by['old-3250000-train'].deps
    assert successor.job_id in by['dfm13-xl-wave34-step_3200000-average'].deps
    assert by['old-3200000-train']==next(j for j in jobs if j.job_id=='old-3200000-train')


@pytest.mark.parametrize('phase',['historical','populations'])
def test_workspace_three_commands_ordered_and_no_history_writer(monkeypatch,phase):
    jobs,registry=fixture();jobs=base.build(jobs,registry)
    monkeypatch.setattr(s,'file_hash',lambda p:'testhash')
    jobs=[j.with_updates(status=s.JobStatus.DONE) for j in s.build(jobs)]
    monkeypatch.setattr(s,'read_plan',lambda p:jobs)
    class Lock:
        def __init__(self,*args):pass
        def __enter__(self):pass
        def __exit__(self,*args):pass
    monkeypatch.setattr(s,'PlanLock',Lock)
    monkeypatch.setattr(s.runpy,'run_path',lambda p:{'validate':lambda jobs,args:None})
    calls=[]
    monkeypatch.setattr(s.subprocess,'run',lambda command,**kw:calls.append(command))
    s.workspace_dispatch(phase)
    assert len(calls)==3
    assert '--verify-remote-sync' in calls[0]
    assert '--apply-prepared' not in calls[1]
    assert '--apply-prepared' in calls[2]
    assert all('patch_dfm13_workspace.py' in c[1] for c in calls)
    assert ('--prepared-history' in calls[0])==(phase=='historical')
