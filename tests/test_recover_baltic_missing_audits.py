import json
import sqlite3

import pytest

from dfm12.io import digest, file_hash, write_json
from dfm12.jobs import Queue, audit_payload
from scripts import recover_baltic_missing_audits as m


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    component='institutional-en-lt-part00098';identifier='example'
    monkeypatch.setattr(m,'MISSING',{component:identifier})
    record=dict(id=identifier,component=component,task='translation',messages=[{'role':'user','content':'Q'},{'role':'assistant','content':'A'}])
    path=tmp_path/'audit-ready'/component/'candidates.jsonl';path.parent.mkdir(parents=True)
    path.write_text(json.dumps(record)+'\n')
    seal=dict(component=component,path=str(path),sha256=file_hash(path))
    write_json(path.parent/'receipt.json',seal)
    write_json(tmp_path/'audit/manifest.json',dict(components=[seal]))
    q=Queue(tmp_path/'audit/jobs.sqlite')
    q.db.execute('CREATE TABLE candidate_ids(id TEXT PRIMARY KEY,content_sha256 TEXT)')
    q.db.execute('INSERT INTO candidate_ids VALUES (?,?)',(identifier,digest([record['messages'],None])))
    other=q.add('audit',{'unrelated':'exhausted model error'})
    q.db.execute("UPDATE jobs SET status='failed',attempts=4,error='JSONDecodeError: invalid' WHERE id=?",(other,))
    q.close()
    return tmp_path,record,other


def test_missing_only_preserves_failed_and_is_idempotent(fixture):
    root,record,other=fixture
    assert m.restore(root,root/'dry.json')['newly_added']==0
    assert m.restore(root,root/'apply.json',True)['newly_added']==1
    assert m.restore(root,root/'again.json',True)['newly_added']==0
    with sqlite3.connect(root/'audit/jobs.sqlite') as db:
        assert db.execute('SELECT status,attempts,error FROM jobs WHERE id=?',(other,)).fetchone()==('failed',4,'JSONDecodeError: invalid')
        assert db.execute('SELECT count(*) FROM jobs').fetchone()[0]==2


def test_failed_exact_job_never_reset(fixture):
    root,record,_=fixture
    q=Queue(root/'audit/jobs.sqlite');key=q.add('audit',audit_payload(record,m.MODEL))
    q.db.execute("UPDATE jobs SET status='failed',attempts=4 WHERE id=?",(key,));q.close()
    with pytest.raises(ValueError,match='failed job'):m.restore(root,root/'out.json',True)


def test_changed_seal_refused(fixture):
    root,_,_=fixture
    p=next((root/'audit-ready').glob('*/candidates.jsonl'));p.write_text('{}\n')
    with pytest.raises(ValueError,match='sealed'):m.restore(root,root/'out.json',True)
