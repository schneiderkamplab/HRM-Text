import asyncio
import json
import sqlite3
import sys
from types import SimpleNamespace

import pytest

from dfm12 import baltic_qa31_consumer as b
from dfm12 import fars_summary_consumer as original
from dfm12.io import digest,write_json,file_hash


def sample():
    record=dict(id='candidate',component='baltic_lv_qa',language='lv',tools=[],
        messages=[dict(role='user',content='question1'),dict(role='assistant',content='history'),
                  dict(role='user',content='question2'),dict(role='assistant',content='target')],
        target_message_index=3,provenance={'file':'source','row':0},
        quality_status='accepted_repair',audit={'keep':True,'reason':'HIDDEN_PRIOR_VERDICT'})
    binding=dict(record_sha256=digest(record),candidate_id=record['id'],upstream=record['provenance'],
        component=record['component'],target_message_index=3)
    return b.bind_packet(record,binding,{'messages':record['messages']})


def test_full_history_blind_labels_and_missing_primary_source():
    packet=sample();request=packet['audit_request']
    value=json.loads(request['messages'][1]['content'])
    assert len(value['candidate']['messages'])==4
    assert value['primary_article'] is None and value['upstream_is_not_gold']
    assert value['protected_message_indices']==[0,1,2]
    assert 'HIDDEN_PRIOR_VERDICT' not in str(request) and 'accepted_repair' not in str(request)
    assert packet['candidate']['audit']['keep'] is True


def test_repair_protects_all_history_tools_and_target_scope():
    packet=sample();result=dict(status='corrected',reason='supported correction',target='correct')
    candidate=b.validate_repair(packet,result)
    assert candidate['messages'][:-1]==packet['candidate']['messages'][:-1]
    assert candidate['tools']==packet['candidate']['tools']
    assert candidate['messages'][-1]['content']=='correct'
    assert not candidate['admission_authorized']
    review=dict(reason='specific flaw',verdict='repair',history_quality='pass',factual_support='contradicted')
    assert 'specific flaw' in str(b.repair_request(packet,review))
    assert 'specific flaw' not in str(b.fresh_reaudit_request(dict(packet,candidate=candidate),'correct'))


@pytest.mark.parametrize('verdict,history,support',[
    ('keep','fail','sufficient'),('keep','pass','uncertain'),('repair','fail','contradicted'),
    ('repair','pass','uncertain')])
def test_uncertain_or_bad_history_never_accepted_or_patched(verdict,history,support):
    with pytest.raises(ValueError):
        b.validate_review(dict(reason='evidence',verdict=verdict,history_quality=history,factual_support=support))


def test_private_engine_does_not_modify_fars_globals():
    old=original.p;next_state=original.next_state
    first=b.engine();second=b.engine()
    assert first is not second
    assert first.p is not old and original.p is old and original.next_state is next_state
    assert first.next_state('review',dict(reason='missing evidence',verdict='needs_verification',
        history_quality='uncertain',factual_support='uncertain'))=='needs_review_verification'


def test_binding_mismatch_fails_before_packet():
    packet=sample();binding=dict(packet['binding'],target_message_index=1)
    with pytest.raises(ValueError):b.bind_packet(packet['candidate'],binding,packet['upstream_record'])


def test_bulk_cannot_bypass_calibration(tmp_path):
    manifest=dict(diagnostic_only=False,calibration_diagnostic_ids=['x'])
    with pytest.raises(ValueError):b.check_calibration(manifest,{})
    b.check_calibration(dict(diagnostic_only=True),{})
    report=tmp_path/'report.json';write_json(report,dict(calibration_complete=False,jobs=[]))
    approval=tmp_path/'approval.json';write_json(approval,dict(approved=True,model=b.MODEL,
        report=str(report),report_sha256=file_hash(report),semantic_assessment='not enough'))
    with pytest.raises(ValueError):b.check_calibration(manifest,dict(calibration_approval=str(approval)))


def test_complete_binding_join_and_pinned_population(tmp_path,monkeypatch):
    hold=tmp_path/'hold';hold.mkdir();root=tmp_path/'prepared'
    inputs={};bindings=[];controls=[]
    counts={'baltic_lt_qa':2,'baltic_lv_qa':18}
    for component,count in counts.items():
        upstream=tmp_path/(component+'.json')
        write_json(upstream,[{'messages':sample()['candidate']['messages']}])
        inputs[str(upstream)]=file_hash(upstream)
        published=tmp_path/(component+'.jsonl');records=[]
        for index in range(count):
            record=json.loads(json.dumps(sample()['candidate']))
            record.update(id=component+str(index),component=component)
            record['provenance']=dict(file=str(upstream),row=0,file_sha256=file_hash(upstream))
            records.append(record);controls.append({'candidate_id':record['id']})
        published.write_text(''.join(json.dumps(r)+'\n' for r in records))
        inputs[str(published)]=file_hash(published)
        for index,record in enumerate(records):
            bindings.append(dict(component=component,candidate_id=record['id'],record_sha256=digest(record),
                upstream=record['provenance'],target_message_index=3,published_path=str(published),
                published_file_sha256=file_hash(published),published_row=index))
    (hold/'all-candidate-bindings.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in bindings))
    (hold/'calibration-requests.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in controls))
    write_json(hold/'reason.json',dict(published_rows=20,inputs=inputs,
        files={name:file_hash(hold/name) for name in ('all-candidate-bindings.jsonl','calibration-requests.jsonl')}))
    monkeypatch.setattr(b,'COUNTS',counts);monkeypatch.setattr(b,'HOLD_SHA',file_hash(hold/'reason.json'))
    assert b.prepare(root,hold)['prepared']==20
    manifest=json.loads((root/'manifest.json').read_text())
    assert manifest['counts']==counts and manifest['primary_articles_available'] is False
    assert (root/'seal.json').exists()


def test_private_engine_full_multiturn_repair_reaudit_resume(tmp_path,monkeypatch):
    module=b.engine();packet=sample();requests=[]
    with sqlite3.connect(tmp_path/'catalog.sqlite') as db:
        db.execute('CREATE TABLE catalog(id PRIMARY KEY,packet,prior_evidence,origin)')
        db.execute('INSERT INTO catalog VALUES(?,?,?,?)',('one',json.dumps(packet),'{"keep":true}','published'))
    write_json(tmp_path/'manifest.json',{})
    auth=tmp_path/'approval.json';write_json(auth,dict(run_authorized=True,model=b.MODEL,
        manifest_sha256=file_hash(tmp_path/'manifest.json')))
    snapshot=tmp_path/'snapshot'
    class Response:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        def raise_for_status(self):pass
        async def json(self):return {'data':[dict(id=b.MODEL,root=str(snapshot),max_model_len=32768)]}
    class Session:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        def get(self,*args,**kwargs):return Response()
    class ClientError(Exception):pass
    monkeypatch.setitem(sys.modules,'aiohttp',SimpleNamespace(ClientSession=Session,ClientError=ClientError,
        ClientTimeout=lambda **kw:None,TCPConnector=lambda **kw:None))
    monkeypatch.setattr(module,'verify',lambda _:dict(snapshot=str(snapshot),context_limit=32768,endpoints=['fake']))
    monkeypatch.setattr(module.h,'tokenizer_init',lambda _:None)
    monkeypatch.setattr(module.h,'TOKENIZER',None,raising=False)
    monkeypatch.setattr(module.h,'measure_request',lambda *args:dict(fits=True))
    outputs=[dict(reason='target flaw',verdict='repair',history_quality='pass',factual_support='contradicted'),
        dict(reason='supported repair',status='corrected',target='new target'),
        dict(reason='all turns checked',verdict='keep',history_quality='pass',factual_support='sufficient')]
    async def query(session,endpoint,payload,writer,metadata):
        requests.append(payload)
        return dict(content=json.dumps(outputs.pop(0)),finish_reason='stop',raw_request_id='mock')
    monkeypatch.setattr(module,'raw_query',query)
    assert asyncio.run(module.run(tmp_path,auth,1))['jobs']=={'provisional_repaired_keep':1}
    assert len(requests)==3 and 'HIDDEN_PRIOR_VERDICT' not in str(requests)
    fresh=json.loads(requests[2]['messages'][1]['content'])
    assert fresh['candidate']['messages'][:-1]==packet['candidate']['messages'][:-1]
    assert fresh['candidate']['messages'][-1]['content']=='new target'
    assert 'target flaw' not in str(fresh)
    asyncio.run(module.run(tmp_path,auth,1))
    assert len(requests)==3
