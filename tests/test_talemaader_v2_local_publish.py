import json
import pytest
from scripts.talemaader_v2_local_publish import publish,digest,PREFIX


def fixture(root):
    point=dict(id='p',epoch=1.5,train_step=100,expected_n=2,inputs=['source'],merged_metrics=str(root/'merged_metrics.json'))
    row={'dfm_eval/epoch':1.5,'dfm_eval/train_step':100,PREFIX+'/n':2,PREFIX+'/accuracy':.5}
    manifest={'points':[point]};rows=[row]
    documents={'manifest.json':manifest,'rows.json':rows,'p.json':{'point':point,'row':row},
        'completed.json':dict(points=1,manifest_sha256=digest(manifest),rows_sha256=digest(rows))}
    for name,value in documents.items():(root/name).write_text(json.dumps(value))


def test_local_only_idempotent(tmp_path):
    fixture(tmp_path);a=publish(tmp_path)
    assert a==publish(tmp_path) and a['wandb_history_written'] is False
    assert (tmp_path/'merged_metrics_v2.json').exists()
    assert not (tmp_path/'synced.json').exists()


def test_conflict_refused(tmp_path):
    fixture(tmp_path);(tmp_path/'merged_metrics_v2.json').write_text('{}')
    with pytest.raises(ValueError,match='differs'):publish(tmp_path)
