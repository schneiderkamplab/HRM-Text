from tests.test_schedule_dfm13_wave34_baseline import fixture
from scripts import schedule_dfm13_wave34_baseline as base
from scripts import schedule_dfm13_dala_v2_additions as v2
from scripts import schedule_expanded_dala_v2_averages as s


def test_full_roots_dependencies_and_atomic_both_namespaces(tmp_path,monkeypatch):
    jobs,r=fixture();r['dfm'][0]['name']='dala_lt'
    jobs=[j.with_updates(metadata={**j.metadata,'wandb_run_name':'test'}) for j in jobs]
    jobs=base.build(jobs,r)
    jobs=v2.build(jobs,[dict(name='dala_v2_da',suite='dala_v2_da',config='/config',language='da',max_tokens=32,shards=4)],tmp_path/'p')
    monkeypatch.setattr(s,'file_hash',lambda p:'hash')
    out=s.build(jobs);by={j.job_id:j for j in out}
    assert len(out)-len(jobs)==3
    row=by['dfm13-xl-expanded-dala-v2-step_3150000']
    assert row.action==s.Action.AVERAGE
    assert row.metadata['average_prefix']=='headline_avg_dala_v2'
    assert row.metadata['extra_average_prefixes']==['suite_avg_dala_v2']
    assert row.metadata['python_bin']=='/home/ucloud/miniforge3/envs/hrm/bin/python'
    assert 'dfm13-xl-dala-v2-step_3150000-dala_v2_da-merge' in row.deps
    assert 'old-3150000-merge' in row.deps
    assert 'old-3150000-euro' in row.deps
    assert 'old-3150000-average' in row.deps
    assert 'dfm13-xl-dala-v2-step_3150000-average' in row.deps
    assert '/dfm/step_3150000' in row.metadata['expanded_roots']['dfm']
    assert any('/wave34/' in p for p in row.metadata['expanded_roots']['dfm'])
    argv=s.command(row)
    assert '--metric-prefix' not in argv
    assert '--standard-root' in argv and '--dfm-root' in argv and '--euroeval-root' in argv
    assert row.job_id in by['old-3200000-wait'].deps
    assert 'dfm13-xl-expanded-dala-v2-step_3200000' in by['old-3250000-train'].deps
    assert by['old-3200000-train']==next(j for j in jobs if j.job_id=='old-3200000-train')
    from eval_scheduler import runtime
    captured=[]
    monkeypatch.setattr(runtime,'run_command',lambda args,**kw:captured.append(args) or 0)
    runtime.run_average(row)
    assert captured[0][:2]==['/home/ucloud/miniforge3/envs/hrm/bin/python','scripts/log_expanded_dala_v2_averages.py']
    assert '--metric-prefix' not in captured[0]
    assert '--additional-dfm-root' in captured[0]
