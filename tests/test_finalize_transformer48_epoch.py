import json
import sqlite3
import pytest
from scripts.finalize_transformer48_epoch import finalize


def setup_case(tmp_path, status='pending', bound=False):
    ckpt = tmp_path / 'ckpt'
    ckpt.mkdir()
    (ckpt / 'checkpoint_state_epoch_1.json').write_text(json.dumps({'step': 393997}))
    db = tmp_path / 'jobs.sqlite'
    with sqlite3.connect(db) as c:
        c.execute('create table jobs(job_id text, definition text, status text)')
        for jid, action, state in [('control', 'teardown_eval', 'done'), ('eval', 'eval_dfm', status)]:
            md = dict(transformer_final_epoch=True, ckpt_path=str(ckpt), eval_step=393997 if bound else 393732, eval_epoch=1.0, xl_boundary=393997 if bound else 393732)
            c.execute('insert into jobs values(?,?,?)', (jid, json.dumps(dict(action=action, metadata_json=json.dumps(md))), state))
    return db, ckpt


def test_terminal_control_does_not_block_and_repeat_is_safe(tmp_path):
    db, ckpt = setup_case(tmp_path)
    finalize(db, ckpt)
    with sqlite3.connect(db) as c:
        rows = dict(c.execute('select job_id,definition from jobs'))
        assert json.loads(json.loads(rows['eval'])['metadata_json'])['eval_step'] == 393997
        assert json.loads(json.loads(rows['control'])['metadata_json'])['eval_step'] == 393732
        c.execute("update jobs set status='running' where job_id='eval'")
    finalize(db, ckpt)


@pytest.mark.parametrize('status', ['running', 'done', 'failed'])
def test_dispatched_unbound_evaluation_refused(tmp_path, status):
    db, ckpt = setup_case(tmp_path, status)
    with pytest.raises(RuntimeError, match='already dispatched'):
        finalize(db, ckpt)
    with sqlite3.connect(db) as c:
        definition = c.execute("select definition from jobs where job_id='eval'").fetchone()[0]
    assert json.loads(json.loads(definition)['metadata_json'])['eval_step'] == 393732
