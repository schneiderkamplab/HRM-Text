import json
import sqlite3

import pytest

from dfm12 import fars_summary_handoff as h
from dfm12.io import digest,file_hash,write_json


class Tokenizer:
    def apply_chat_template(self,messages,**kwargs):
        assert kwargs==dict(tokenize=True,add_generation_prompt=True,enable_thinking=True)
        assert messages[0]['content']=='whole source'
        return list(range(25000))


def test_budget_includes_output_and_never_truncates():
    request=dict(model=h.packets.MODEL,chat_template_kwargs={'enable_thinking':True},
        messages=[dict(role='user',content='whole source')],max_tokens=8192)
    result=h.measure_request(request,Tokenizer(),32768)
    assert result['total_tokens']==33192 and not result['fits'] and not result['truncated']
    request['model']='wrong'
    with pytest.raises(ValueError): h.measure_request(request,Tokenizer(),32768)


def test_delta_includes_authorized_deferred_and_completed_not_running(tmp_path,monkeypatch):
    base=tmp_path/'base';base.mkdir();downloads=tmp_path/'downloads';downloads.mkdir()
    source=downloads/'x.parquet';source.write_bytes(b'pin')
    write_json(base/'manifest.json',{})
    with sqlite3.connect(base/'snapshot.sqlite') as db:
        db.execute('CREATE TABLE candidates(content_key TEXT)')
        db.execute('CREATE TABLE queue_snapshot(id TEXT PRIMARY KEY,status TEXT,result TEXT)')
    queue=tmp_path/'jobs.sqlite'
    records=[]
    with sqlite3.connect(queue) as db:
        db.execute('CREATE TABLE jobs(id PRIMARY KEY,stage,payload,status,attempts,owner,lease,result,error)')
        db.execute('CREATE TABLE events(timestamp,job_id,attempt,status,detail)')
        for index,status in enumerate(('pending','done','running')):
            record=dict(id=str(index),component=h.packets.COMPONENTS[0],
                messages=[dict(role='user',content='source'),dict(role='assistant',content='bad')],
                provenance=dict(repo='ParsiAI/FarsInstruct',revision='r',file='x.parquet',row=0))
            payload=dict(record=record);key=digest(['generate',payload]);records.append(key)
            result=dict(status='corrected',messages=[record['messages'][0],dict(role='assistant',content='new')])
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)',(key,'generate',json.dumps(payload),status,
                0 if status=='pending' else 1,None if status=='pending' else 'worker',None,
                json.dumps(result) if status=='done' else None,None))
    authorization=tmp_path/'auth';h.deferral.propose(queue,authorization);h.deferral.apply(authorization)
    monkeypatch.setattr(h.packets,'verify',lambda _:dict(downloads=str(downloads),
        snapshot_sha256=file_hash(base/'snapshot.sqlite'),pins={str(source):file_hash(source)}))
    monkeypatch.setattr(h.packets.SourceRows,'get',lambda *args:dict(inputs='source',outputs='old',template='summarize_the_article'))
    root=tmp_path/'delta';result=h.delta(base,authorization,root)
    assert result['prepared']==2 and result['blocked']==0
    assert result['handoff_states']['unfinished31B_authorized']==1
    assert result['handoff_states']['blocked_nonterminal_not_authorized']==1
    assert not result['migration_ready'] and not result['quality_review_complete']
    with sqlite3.connect(root/'packets.sqlite') as db:
        packets=[json.loads(r[0]) for r in db.execute('SELECT packet FROM packets')]
    assert all(p['unfinished31B'] and not p['admission_authorized'] for p in packets)
    with sqlite3.connect(queue) as db:
        assert db.execute('SELECT status FROM jobs WHERE id=?',(records[2],)).fetchone()[0]=='running'
