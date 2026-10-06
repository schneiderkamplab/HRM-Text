from tests.test_schedule_dfm13_wave34_baseline import fixture
from scripts import schedule_todo5_future_averages as s


def test_future_only_no_backfill_no_training_change(monkeypatch):
    jobs,_=fixture()
    jobs=[j.with_updates(metadata={**j.metadata,'average_prefix':'headline_avg_v3'})
          if j.action==s.Action.AVERAGE else j for j in jobs]
    monkeypatch.setattr(s,'file_hash',lambda p:'sha')
    out=s.build(jobs);by={j.job_id:j for j in out}
    assert len(out)-len(jobs)==2
    assert by['old-3200000-train']==next(j for j in jobs if j.job_id=='old-3200000-train')
    for j in jobs:
        if j.action!=s.Action.TRAIN_UNTIL_STEP:assert by[j.job_id]==j
    assert 'dfm13-xl-todo5-step_3200000-average' in by['old-3250000-train'].deps
    for row in out[len(jobs):]:
        assert row.action==s.Action.AVERAGE
        assert row.metadata['atomic_v3_averages'] is False
        assert row.metadata['average_prefix']=='headline_avg_talemaader_v2'
        assert row.metadata['extra_average_prefixes']==['suite_avg_talemaader_v2']
