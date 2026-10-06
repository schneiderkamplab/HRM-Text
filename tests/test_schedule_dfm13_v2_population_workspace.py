from scripts import schedule_dfm13_v2_population_workspace as s
from scripts import schedule_dfm13_wave34_baseline as base
from scripts import schedule_dfm13_dala_v2_additions as additions
from tests.test_schedule_dfm13_wave34_baseline import fixture


def test_only_v2_baseline_gates_workspace(tmp_path,monkeypatch):
    jobs,r=fixture();r['dfm'][0]['name']='dala_lt';jobs=base.build(jobs,r)
    tasks=[dict(name='dala_v2_da',suite='dala_v2_da',config='/new',language='da',max_tokens=32,shards=4)]
    jobs=additions.build(jobs,tasks,tmp_path/'p.json')
    monkeypatch.setattr(s,'file_hash',lambda p:'sha')
    out=s.build(jobs);by={j.job_id:j for j in out}
    assert by[s.ID].deps==(s.BASELINE,)
    assert s.ID in by['old-3200000-wait'].deps
    assert by['old-3200000-train']==next(j for j in jobs if j.job_id=='old-3200000-train')
    assert len(out)==len(jobs)+1
    commands=s.commands()
    assert all('--population' in c and str(s.POPULATION) in c for c in commands)
    assert '--verify-remote-sync' in commands[0] and '--apply-prepared' in commands[2]
    assert not any('historical-mapping' in arg for c in commands for arg in c)
