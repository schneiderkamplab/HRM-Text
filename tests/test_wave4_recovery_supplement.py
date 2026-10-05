import base64
import json
from pathlib import Path

import pytest
from dfm12 import wave4_recovery_supplement as supplement
from dfm12.io import digest,write_json,load
from dfm12.multilingual_calibration_v6 import strict_json


def raw_fixture(root, finish='stop', content='{"verdict":"keep","issues":[],"reason":""}'):
    payload={'messages':[{'role':'user','content':'unaltered'}]}
    rawid='request-1';key='job'
    write_json(root/'requests/job-review.json',dict(request=payload))
    write_json(root/'stages/job-review.json',dict(request_sha256=digest(payload),
        raw=dict(raw_request_id=rawid,content=content,finish_reason=finish)))
    write_json(root/'raw/request-1.request.json',dict(request_id=rawid,
        request=dict(payload,stream=True,stream_options={'include_usage':True})))
    body='data: '+json.dumps({'choices':[{'index':0,'delta':{'content':content},'finish_reason':finish}]})+'\n\ndata: [DONE]\n'
    write_json(root/'raw/request-1.response.json',dict(request_id=rawid,status=200,
        transport_error=None,content=content,raw_body_base64=base64.b64encode(body.encode()).decode()))
    return key


def test_full_raw_stage_proof(tmp_path):
    key=raw_fixture(tmp_path)
    assert len(supplement.raw_proof(tmp_path,key,'review',strict_json))==4


@pytest.mark.parametrize('change',['length','body','request','transport','status','hash'])
def test_raw_proof_fails_closed(tmp_path,change):
    key=raw_fixture(tmp_path,finish='length' if change=='length' else 'stop')
    response=tmp_path/'raw/request-1.response.json'
    value=load(response)
    if change=='body':value['raw_body_base64']=base64.b64encode(b'data: [DONE]\n').decode()
    if change=='transport':value['transport_error']='TimeoutError'
    if change=='status':value['status']=500
    write_json(response,value)
    if change=='request':
        path=tmp_path/'raw/request-1.request.json';value=load(path)
        value['request']['messages'][0]['content']='changed';write_json(path,value)
    if change=='hash':
        path=tmp_path/'stages/job-review.json';value=load(path)
        value['request_sha256']='changed';write_json(path,value)
    with pytest.raises(ValueError):supplement.raw_proof(tmp_path,key,'review',strict_json)


def test_readonly_connection_cannot_mutate(tmp_path):
    import sqlite3
    path=tmp_path/'db'
    with sqlite3.connect(path) as db:db.execute('CREATE TABLE x(n)')
    with supplement.ro(path) as db:
        with pytest.raises(sqlite3.OperationalError):db.execute('INSERT INTO x VALUES(1)')


def test_finalize_live_does_not_create_release(tmp_path):
    # Independent of other checks, missing terminal evidence never promotes rows.
    root=tmp_path/'bundle';root.mkdir();out=tmp_path/'prepared';out.mkdir()
    write_json(out/'initial.json',dict(bundle=str(root),pins={}))
    write_json(out/'prepared.json',dict(initial_sha256=supplement.file_hash(out/'initial.json'),result_pins={}))
    for i in range(8):(root/f'shard-{i}').mkdir()
    with pytest.raises(FileNotFoundError):supplement.finalize(root,out,tmp_path/'release')
    assert not (tmp_path/'release').exists()
