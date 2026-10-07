from scripts import schedule_historical_available_sync as s
from scripts import schedule_dfm13_wave34_baseline as base
from tests.test_schedule_dfm13_wave34_baseline import fixture
import ast
import subprocess
import sys


def test_exclusive_window_no_cycle(tmp_path,monkeypatch):
    jobs,r=fixture();jobs=base.build(jobs,r)
    jobs=[j.with_updates(job_id='dfm13-xl-step_3250000-train' if j.job_id=='old-3250000-train' else j.job_id,
          deps=tuple('dfm13-xl-step_3250000-train' if d=='old-3250000-train' else d for d in j.deps)) for j in jobs]
    monkeypatch.setattr(s,'file_hash',lambda p:'sha')
    report=next(j for j in jobs if j.job_id=='old-3200000-average').with_updates(
        job_id='after-average-report',action=s.Action.REPORT,deps=('old-3200000-average',))
    jobs.append(report)
    out=s.build(jobs,tmp_path/'payload',{'payload_sha256':'payload'});by={j.job_id:j for j in out}
    assert s.ID in by['dfm13-xl-step_3250000-train'].deps
    row=by[s.ID]
    assert 'old-3200000-euro' in row.deps
    assert 'old-3200000-average' not in row.deps
    assert 'dfm13-xl-wave34-step_3200000-average' not in row.deps
    assert s.ID in by['old-3200000-average'].deps
    assert s.ID in by['dfm13-xl-wave34-step_3200000-average'].deps
    assert 'dfm13-xl-wave34-step_3200000-teardown' in row.deps
    assert row.max_retries==0
    assert 'after-average-report' not in row.deps
    assert by['after-average-report'].deps==('old-3200000-average',)
    assert all(j==by[j.job_id] for j in jobs if j.status==s.JobStatus.RUNNING)


def test_summary_only_payload_keys():
    payload={'points':[{'row':{'avg_population/new/score':.2,'headline_avg_dala_v2/overall':.3}}]}
    summary={'avg_population/new/score':.8,'train/loss':1,'legacy/score':2}
    assert s.summary_subset(summary,payload)=={'avg_population/new/score':.8}


def test_actual_subprocess_prefix_imports_and_cli():
    tree=ast.parse(open(s.__file__).read())
    calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call)
           and isinstance(n.func,ast.Attribute) and n.func.attr=='run'
           and isinstance(n.func.value,ast.Name) and n.func.value.id=='subprocess']
    assert len(calls)==2
    for call in calls:
        prefix=[ast.literal_eval(x) for x in call.args[0].elts[:3]]
        assert prefix[1:]==['-m','scripts.backfill_available_eval_averages']
        for command in ('prepare','sync'):
            result=subprocess.run([*prefix,command,'--help'],cwd=s.ROOT,
                                  capture_output=True,text=True)
            assert result.returncode==0,result.stderr
    result=subprocess.run([sys.executable,s.__file__,'--help'],cwd=s.ROOT,
                          capture_output=True,text=True)
    assert result.returncode==0,result.stderr
