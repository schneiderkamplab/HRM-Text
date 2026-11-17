import json
import sqlite3
from scripts import activate_b_dfm15_epoch3 as switch


def test_trim_only_passed_suspensions():
    d={'action':'train_until_step','metadata_json':json.dumps({'command':'python pretrain.py suspend_after_steps=[650000,700000,1025846]', 'cooperative_training':{'command':['python','pretrain.py','suspend_after_steps=[650000,700000,1025846]']}})}
    m=json.loads(switch.trim_passed(d)['metadata_json'])
    assert 'suspend_after_steps=[700000,1025846]' in m['command']
    assert m['cooperative_training']['command'][-1]=='suspend_after_steps=[700000,1025846]'


def test_reconcile_preserves_live_claims_and_completed_rows(tmp_path,monkeypatch):
    live=tmp_path/'live.sqlite';staged=tmp_path/'staged.sqlite';out=tmp_path/'receipts';out.mkdir()
    monkeypatch.setattr(switch,'LIVE',live);monkeypatch.setattr(switch,'STAGED',staged);monkeypatch.setattr(switch,'HANDOFF',out)
    for path in (live,staged):
        with sqlite3.connect(path) as db:
            db.executescript('CREATE TABLE jobs(job_id TEXT PRIMARY KEY,definition TEXT,deps_mode TEXT,status TEXT,token TEXT,position INTEGER); CREATE TABLE dependencies(job_id TEXT,dependency TEXT); CREATE TABLE administration(locked INTEGER); INSERT INTO administration VALUES (1);')
            for i,jid in enumerate(['b-dfm15-train-650000','current-eval','b-dfm15-train-700000']+(['new'] if path==staged else [])):
                status='pending' if path==staged or i>=2 else ('done' if i==0 else 'running')
                d={'job_id':jid,'action':'average','deps':'b-dfm15-train-650000' if i else '', 'deps_mode':'terminal','metadata_json':json.dumps({'version':'new' if path==staged else 'old'})}
                db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?)',(jid,json.dumps(d),'terminal',status,'live-token' if status=='running' else None,i))
    assert switch.apply_definitions()==(1,1)
    with sqlite3.connect(live) as db:
        assert db.execute("SELECT status,token FROM jobs WHERE job_id='current-eval'").fetchone()==('running','live-token')
        old=json.loads(db.execute("SELECT definition FROM jobs WHERE job_id='b-dfm15-train-650000'").fetchone()[0]);assert json.loads(old['metadata_json'])['version']=='old'
        assert db.execute("SELECT status FROM jobs WHERE job_id='new'").fetchone()[0]=='pending'
    switch.rollback()
    with sqlite3.connect(live) as db:
        assert not db.execute("SELECT 1 FROM jobs WHERE job_id='new'").fetchone()
        d=json.loads(db.execute("SELECT definition FROM jobs WHERE job_id='b-dfm15-train-700000'").fetchone()[0]);assert json.loads(d['metadata_json'])['version']=='old'
