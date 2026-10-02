import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

P=Path(__file__).resolve().parents[1]/'scripts/dfm13_arena_frozen_review_recovery.py'
spec=importlib.util.spec_from_file_location('frozen_review_test',P)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def source_db(root):
    db=sqlite3.connect(root/'ledger.sqlite')
    for table in ('accepted','rejected','needs_review'):db.execute(f'CREATE TABLE {table}(seq INTEGER PRIMARY KEY,record TEXT)')
    db.execute('CREATE TABLE attempts(seq INTEGER,stage TEXT,n INTEGER,status TEXT,hash TEXT,record TEXT,PRIMARY KEY(seq,stage,n))')
    return db


def attempt(db,seq,stage='retry_audit',n=1,status='invalid_response',content='x'+' '*200):
    raw=dict(finish_reason='length',content=content)
    db.execute('INSERT INTO attempts VALUES(?,?,?,?,?,?)',(seq,stage,n,status,'hash',json.dumps(raw)))


def test_snapshot_only_finalized_no_inflight_conflicts_or_live_writes(tmp_path):
    source=tmp_path/'source';source.mkdir()
    with source_db(source) as db:
        for seq in range(1,9):db.execute('INSERT INTO needs_review VALUES(?,?)',(seq,json.dumps(dict(seq=seq))))
        attempt(db,1)
        attempt(db,2);attempt(db,2,n=2,status='inflight')
        attempt(db,3,stage='correction')
        attempt(db,4,stage='fresh_reaudit');attempt(db,4,stage='correction',status='complete')
        attempt(db,5);attempt(db,5,n=2,status='complete')
        attempt(db,6);attempt(db,6,n=2,content='substantive long answer')
        attempt(db,7);db.execute('INSERT INTO accepted VALUES(7,?)',('{}',))
        attempt(db,8,status='abort_status_unknown',content='')
    snapshot=tmp_path/'snapshot.sqlite'
    before=m.base.file_hash(source/'ledger.sqlite')
    assert m.freeze(source,snapshot)==6
    assert before==m.base.file_hash(source/'ledger.sqlite')
    with m.repair.readonly(snapshot) as db:
        assert [r[0] for r in m.selected_failures(db)]==[1,4]
        assert db.execute("SELECT count(*) FROM attempts WHERE status='inflight'").fetchone()[0]==0
    with sqlite3.connect(source/'ledger.sqlite') as db:
        db.execute('UPDATE needs_review SET record=? WHERE seq=1',('{"later":true}',))
    with m.repair.readonly(snapshot) as db:
        assert json.loads(db.execute('SELECT record FROM needs_review WHERE seq=1').fetchone()[0])=={'seq':1}
    with pytest.raises(ValueError,match='Fresh snapshot'):m.freeze(source,snapshot)


@pytest.mark.parametrize('stage,content,finish,expected',[
    ('retry_audit','x'+' '*200,'length',True),
    ('fresh_reaudit','x'+' '*200,'length',True),
    ('correction','x'+' '*200,'length',False),
    ('retry_audit','long meaningful text','length',False),
    ('retry_audit',None,'length',False),
    ('retry_audit','x'+' '*200,'stop',False)])
def test_only_review_whitespace(stage,content,finish,expected):
    assert m.recovery.eligible(stage,dict(content=content,finish_reason=finish),False)==expected


def test_exact_content_and_explicit_contract_without_control_labels():
    row=dict(id='private-model-votes',target_message_index=1,metadata={'model':'secret'},
        messages=[dict(role='user',content='2+2?'),dict(role='assistant',content='5')])
    original=m.repair.strong.request(row)
    before=json.dumps(original)
    payload,schema=m.payload_for(original)
    assert json.dumps(original)==before
    assert payload['messages'][-1]==original['messages'][-1]
    assert 'WHOLE target' in payload['messages'][0]['content']
    assert 'Exact output contract' in payload['messages'][0]['content']
    assert payload['response_format']=={'type':'json_object'}
    assert payload['chat_template_kwargs']=={'enable_thinking':True}
    assert payload['max_tokens']==8192
    assert schema['properties']['reason']['maxLength']==2400
    assert 'private-model-votes' not in json.dumps(payload)
    assert 'secret' not in json.dumps(payload)


def test_controls_fail_closed_on_false_keep_metadata_error_or_missing_case():
    jobs=[dict(id=f'c{i}',kind='control',allowed=['repair','reject'] if i<3 else ['keep']) for i in range(6)]
    outcomes={j['id']:dict(status='complete',result=dict(verdict=j['allowed'][0])) for j in jobs}
    assert m.controls_pass(jobs,outcomes)
    outcomes['c0']['result']['verdict']='keep';assert not m.controls_pass(jobs,outcomes)
    outcomes['c0']['result']['verdict']='repair';outcomes['c1']['status']='invalid_response'
    assert not m.controls_pass(jobs,outcomes)
    outcomes.pop('c1');assert not m.controls_pass(jobs,outcomes)
    assert not m.controls_pass(jobs[:5],outcomes)


def test_controls_are_three_decisive_negatives_three_positives():
    assert len(m.CONTROL_ALLOWED)==6
    assert sum(v==['keep'] for v in m.CONTROL_ALLOWED.values())==3
    assert sum(v==['repair','reject'] for v in m.CONTROL_ALLOWED.values())==3


def test_bound_cannot_expand_to_bulk(tmp_path):
    with pytest.raises(ValueError,match='bound'):m.prepare(tmp_path,tmp_path,101)


def test_gate_limits_and_missing_metrics_fail_closed():
    fn=m.pilot.next_audit.admission_credits
    assert fn({},0)==0
    values={'vllm:num_requests_running':128,'vllm:num_requests_waiting':0,'vllm:kv_cache_usage_perc':.4}
    assert fn(values,0)==128
    assert fn(values,0,recent=8)==120
    assert fn(dict(values,**{'vllm:kv_cache_usage_perc':.9}),0)==0
