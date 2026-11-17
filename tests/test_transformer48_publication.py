import json
import sqlite3
import pytest
from scripts.publish_transformer48_checkpoint import collect


def fixture_db(tmp_path, *, status='done', recorded=50000):
    p=tmp_path/'results';p.mkdir()
    (p/'merged_metrics.json').write_text(json.dumps({'euroeval/train_step':recorded,'euroeval/test/score':0.5}))
    db=tmp_path/'jobs.sqlite';c=sqlite3.connect(db)
    c.execute('create table jobs(job_id,definition,log_dir,status)')
    d={'job_id':'transformer48-step_50000-eval-test','action':'merge_euroeval','metadata_json':json.dumps({'eval_step':50000,'eval_epoch':0.12})}
    c.execute('insert into jobs values(?,?,?,?)',(d['job_id'],json.dumps(d),str(p),status));c.commit();c.close()
    return db


def test_collect_complete_checkpoint(tmp_path):
    metrics,files,_=collect(fixture_db(tmp_path),'step_50000')
    assert metrics['euroeval/test/score']==0.5
    assert metrics['euroeval/train_step']==50000
    assert len(files)==1


def test_reject_unfinished_merge(tmp_path):
    with pytest.raises(ValueError,match='Incomplete publication'):
        collect(fixture_db(tmp_path,status='failed'),'step_50000')


def test_reject_mixed_checkpoint(tmp_path):
    with pytest.raises(ValueError,match='Wrong checkpoint'):
        collect(fixture_db(tmp_path,recorded=100000),'step_50000')
