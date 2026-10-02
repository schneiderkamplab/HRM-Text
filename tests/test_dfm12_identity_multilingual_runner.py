import json
from types import SimpleNamespace

import pytest

from dfm12 import identity_multilingual_runner as r
from dfm12.io import file_hash, write_json


def test_complete_response_only():
    assert r.complete_response({'choices':[{'finish_reason':'stop','message':{'content':'{"keep":true}'}}]})=={'keep':True}


@pytest.mark.parametrize('reason',['length','abort','tool_calls',None])
def test_incomplete_responses_never_submitted(reason):
    with pytest.raises(ValueError,match='Incomplete'):
        r.complete_response({'choices':[{'finish_reason':reason,'message':{'content':'{"keep":true}'}}]})


@pytest.mark.parametrize('content',['[]','{"keep":','not json'])
def test_bad_json_rejected(content):
    with pytest.raises(ValueError):r.complete_response({'choices':[{'finish_reason':'stop','message':{'content':content}}]})


def test_endpoint_identity_and_context():
    r.validate_health({'data':[{'id':r.queue_module.MODEL,'max_model_len':16384}]})
    with pytest.raises(ValueError):r.validate_health({'data':[{'id':'other','max_model_len':16384}]})
    with pytest.raises(ValueError):r.validate_health({'data':[{'id':r.queue_module.MODEL,'max_model_len':4096}]})


def test_draining_cannot_claim_new_generation():
    calls=[]
    db=SimpleNamespace(execute=lambda *_:SimpleNamespace(fetchone=lambda:None))
    broker=r.Broker.__new__(r.Broker)
    broker.queue=SimpleNamespace(db=db,claim=lambda owner:calls.append(owner))
    assert broker.claim('owned',True) is None
    assert calls==[]
    broker.claim('owned',False)
    assert calls==['owned']


def test_draining_preserves_audit_progress():
    db=SimpleNamespace(execute=lambda *_:SimpleNamespace(fetchone=lambda:('audit_pending',)))
    broker=r.Broker.__new__(r.Broker)
    broker.queue=SimpleNamespace(db=db,claim=lambda owner:{'stage':'audit','owner':owner})
    assert broker.claim('owned',True)=={'stage':'audit','owner':'owned'}


def test_explicit_512_activation_preserves_sealed_module(tmp_path,monkeypatch):
    import sqlite3
    write_json(tmp_path/'recipe.json',{})
    write_json(tmp_path/'manifest.json',{'test':'fixture'})
    db=sqlite3.connect(tmp_path/'queue.sqlite')
    db.execute('CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT)')
    db.execute("INSERT INTO metadata VALUES('activated','false')")
    db.commit();db.close()
    monkeypatch.setattr(r.queue_module,'verify',lambda _:None)
    q=r.queue_module.Queue(tmp_path)
    authorization=dict(manifest_sha256=file_hash(tmp_path/'manifest.json'),
        scope='identity_extension_generation_and_audit',coordination_complete=True,
        authorized_by='test fixture',endpoints=list(r.ENDPOINTS),concurrency_per_endpoint=512,
        runner_sha256=file_hash(r.__file__),explicit_512_override=True)
    before=file_hash(r.queue_module.__file__)
    for changed in ({'concurrency_per_endpoint':513},{'explicit_512_override':False},
                    {'runner_sha256':'wrong'},{'concurrency_per_endpoint':True}):
        with pytest.raises(ValueError,match='authorization'):
            r.activate_authorized(q,tmp_path,dict(authorization,**changed))
    r.activate_authorized(q,tmp_path,authorization)
    r.activate_authorized(q,tmp_path,authorization)
    assert q.db.execute("SELECT value FROM metadata WHERE key='activated'").fetchone()[0]=='true'
    assert file_hash(r.queue_module.__file__)==before
    with pytest.raises(ValueError,match='drift'):
        r.activate_authorized(q,tmp_path,dict(authorization,concurrency_per_endpoint=32))
    q.close()
