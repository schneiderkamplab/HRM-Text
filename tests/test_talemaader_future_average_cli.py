import json
import os
from pathlib import Path
import subprocess
import sys
import runpy
from types import SimpleNamespace

import pytest

from scripts import log_dfm5_headline_averages as logger
from scripts.prepare_talemaader_v2_averages import NEW, THP, TSP


def fixture(tmp_path):
    task = tmp_path/'generative_talemaader'
    task.mkdir()
    doc=dict(epoch=11.,step=3200000,num_samples=808,metrics={NEW:.5,NEW.rsplit('/',1)[0]+'/n':808})
    (task/'merged_metrics_v2.json').write_text(json.dumps(doc))
    (task/'merged_metrics.json').write_text(json.dumps({'metrics':{'dfm_eval/generative-talemaader/model_graded_fact/accuracy':0.}}))
    return logger.EvalItem(3200000,11.,tmp_path,tmp_path,tmp_path),task,doc


@pytest.mark.parametrize('scope',['danish','overall'])
def test_future_scopes(tmp_path,scope):
    item,_,_=fixture(tmp_path)
    kw=dict(sections={'danish'},include_overall=False) if scope=='danish' else dict(overall_only=True,include_sections=False)
    row=logger.build_row(item,metric_prefix=THP,**kw)
    assert row[THP+'/'+scope]==.5
    assert THP+'/english' not in row


def test_suite_and_legacy_unchanged(tmp_path):
    item,_,_=fixture(tmp_path)
    assert logger.build_row(item,metric_prefix=TSP,include_sections=False)[TSP+'/dfm']==.5
    assert logger.build_row(item,metric_prefix='headline_avg_v3')['headline_avg_v3/danish']==0.


@pytest.mark.parametrize('mutation',['step','epoch','count','duplicate','absent'])
def test_bad_sidecars_fail_closed(tmp_path,mutation):
    item,task,doc=fixture(tmp_path)
    path=task/'merged_metrics_v2.json'
    if mutation=='step':doc['step']=3150000
    if mutation=='epoch':doc['epoch']=10.
    if mutation=='count':doc['num_samples']=807
    path.write_text(json.dumps(doc))
    if mutation=='duplicate':
        other=tmp_path/'other';other.mkdir();doc['metrics'][NEW]=.75;(other/path.name).write_text(json.dumps(doc))
    if mutation=='absent':path.unlink()
    with pytest.raises(ValueError):logger.build_row(item,metric_prefix=THP)


def test_actual_existing_cli_dry_run(tmp_path):
    item,_,_=fixture(tmp_path)
    env=dict(os.environ);env.pop('PYTHONPATH',None)
    result=subprocess.run([sys.executable,'scripts/log_dfm5_headline_averages.py','--metric-prefix',THP,
        '--average-scope','danish','--item',f'3200000:11:{tmp_path}:{tmp_path}','--dry-run'],
        capture_output=True,text=True,env=env)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)[0][THP+'/danish']==.5


def test_native_future_merge_without_sidecar(tmp_path):
    item,task,doc=fixture(tmp_path)
    (task/'merged_metrics_v2.json').unlink()
    doc.pop('step')
    doc['inputs']=[f'/logs/task/shard_{i}_of_8/step_3200000/inspect/a.eval' for i in range(8)]
    (task/'merged_metrics.json').write_text(json.dumps(doc))
    assert logger.build_row(item,metric_prefix=THP)[THP+'/danish']==.5


def test_identical_native_and_historical_merge_is_unambiguous(tmp_path):
    item,task,doc=fixture(tmp_path)
    (task/'merged_metrics.json').write_text(json.dumps(doc))
    assert logger.build_row(item,metric_prefix=THP)[THP+'/danish']==.5


def test_actual_scheduler_dispatch_cli_with_fake_wandb(tmp_path,monkeypatch):
    item,task,doc=fixture(tmp_path)
    (task/'merged_metrics_v2.json').unlink()
    (task/'merged_metrics.json').write_text(json.dumps(doc))
    logged=[]
    fake=SimpleNamespace(init=lambda **kw:SimpleNamespace(summary={}),
        define_metric=lambda *a,**kw:None,log=lambda row,**kw:logged.append(row),finish=lambda:None)
    monkeypatch.setitem(sys.modules,'wandb',fake)
    monkeypatch.syspath_prepend(str(Path('scripts').resolve()))
    monkeypatch.setattr(sys,'argv',['scripts/backfill_external_eval_to_wandb.py',
        '--project','DFM5','--run-id','test','--run-name','test',
        '--standard-root',str(tmp_path),'--dfm-root',str(tmp_path),'--euroeval-root',str(tmp_path),
        '--epoch','11','--step','3200000','--average-prefix',THP,
        '--extra-average-prefix',TSP,'--log-averages','--average-scope','all','--averages-only'])
    runpy.run_path('scripts/backfill_external_eval_to_wandb.py',run_name='__main__')
    assert len(logged)==1
    assert logged[0][THP+'/danish']==.5 and logged[0][TSP+'/dfm']==.5
    assert all(k.startswith((THP+'/',TSP+'/')) for k in logged[0])
