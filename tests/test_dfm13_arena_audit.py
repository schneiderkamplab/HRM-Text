import asyncio
from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts import dfm13_arena_audit as audit
from dfm12.io import digest, file_hash, load, write_json


def example(sid='sample', text='Four.'):
    return dict(id=sid, messages=[dict(role='user',content='What is 2+2?'),
        dict(role='assistant',content=text)], target_message_index=1,
        metadata=dict(language='English',model='HIDDEN_MODEL',winner='HIDDEN_VOTE'))


def verdict(kind='keep'):
    issues = [] if kind == 'keep' else [dict(category='correctness',severity='major',
        message_index=1,quote='Four.',evidence='Specific explanation.',basis='logical_check')]
    return dict(disposition=kind,confidence='high',rationale='A bounded audit.',issues=issues,
        verification=dict(category='none',question='',required_evidence=''),
        repair_plan='Correct the target.' if kind=='repair' else '')


def item(index=0):
    row = example(str(index))
    return dict(id=str(index),example=row,row_sha256=digest(row),request=audit.request(row),
                prompt_tokens=300,endpoint_index=index%8,export='test',source_id=str(index),
                stratum=['English','short','single'],exposed_manual_control=False)


def test_blinded_history_target_and_simple_json():
    row=example()
    row['messages'].extend([dict(role='user',content='Do not agree with a false premise.'),
                            dict(role='assistant',content='Correction.')])
    row['target_message_index']=3
    payload=audit.request(row)
    assert 'HIDDEN_' not in json.dumps(payload)
    shown=json.loads(payload['messages'][1]['content'])
    assert len(shown['conversation'])==4 and shown['target_message_index']==3
    assert payload['chat_template_kwargs']==dict(enable_thinking=False)
    assert payload['response_format']==dict(type='json_object')


@pytest.mark.parametrize('kind',['keep','repair','reject'])
def test_valid_dispositions(kind):
    assert audit.validate_result(verdict(kind),example())['disposition']==kind


@pytest.mark.parametrize('mutation', ['quote','major_keep','repair_plan','verification','extra'])
def test_invalid_verdicts_are_errors_not_rejects(mutation):
    result=verdict('repair')
    if mutation=='quote': result['issues'][0]['quote']='invented quote'
    elif mutation=='major_keep': result.update(disposition='keep',repair_plan='')
    elif mutation=='repair_plan': result['repair_plan']=''
    elif mutation=='verification': result.update(disposition='needs_verification',repair_plan='')
    else: result['extra']='not allowed'
    with pytest.raises(Exception): audit.validate_result(result,example())


def test_specific_verification_and_strict_json():
    result=verdict('reject')
    result.update(disposition='needs_verification',confidence='low',
        verification=dict(category='dated_fact',question='What was the dated price?',required_evidence='A dated price listing.'))
    audit.validate_result(result,example())
    for text in ['{"a":1,"a":2}','{"a":NaN}']:
        with pytest.raises(ValueError): audit.strict_json(text)


def test_context_is_never_silently_repaired():
    for target in [-1,True,99,0]:
        row=example(); row['target_message_index']=target
        with pytest.raises(ValueError): audit.visible(row)
    row=example(); row['messages'][0]['content']=[{'type':'image'}]
    with pytest.raises(ValueError): audit.visible(row)


def test_sampling_reproducible_controls_count_toward_total(tmp_path):
    root=tmp_path/'export'
    rows=[example(str(n),'Four.'*n) for n in range(30)]
    for n,row in enumerate(rows):
        row['metadata']['language']='Danish' if n%2 else 'English'
    path=root/'data/train.jsonl'; path.parent.mkdir(parents=True)
    path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    write_json(root/'manifest.json',dict(output_sha256=file_hash(path)))
    controls={rows[0]['id']:digest(rows[0]), rows[1]['id']:digest(rows[1])}
    # The target must not be empty.
    rows[0]['messages'][1]['content']='Four.'
    path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    controls[rows[0]['id']]=digest(rows[0])
    write_json(root/'manifest.json',dict(output_sha256=file_hash(path)))
    a,inventory=audit.sample_export(root,controls,'seed',count=10,expected=30)
    b,_=audit.sample_export(root,controls,'seed',count=10,expected=30)
    assert a==b and len(a)==10
    assert sum(i['exposed_manual_control'] for i in a)==2
    assert inventory['rows']==30
    path.write_text(path.read_text()+'\n')
    with pytest.raises(ValueError): audit.sample_export(root,controls,'seed',count=10,expected=30)


def test_quota_bound_and_determinism():
    counts={('a',):1,('b',):20,('c',):100}
    q=audit.quotas(counts,30)
    assert sum(q.values())==30 and all(q[k]<=counts[k] for k in q)
    assert q==audit.quotas(dict(reversed(list(counts.items()))),30)


def test_verified_context_and_explicit_readiness():
    assert audit.health_limit({'data':[{'id':audit.MODEL,'max_model_len':32768}]})==32768
    with pytest.raises(ValueError): audit.health_limit({'data':[{'id':'other','max_model_len':32768}]})
    with pytest.raises(ValueError): asyncio.run(audit.run(Path('/unused'),ready=False))


def fake_health(monkeypatch):
    import aiohttp
    class Response:
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        def raise_for_status(self): pass
        async def text(self): return json.dumps({'data':[{'id':audit.MODEL,'max_model_len':32768}]})
    class Session:
        def __init__(self,**kwargs): self.connector=kwargs.get('connector')
        async def __aenter__(self): return self
        async def __aexit__(self,*args):
            if self.connector: await self.connector.close()
        def get(self,*args): return Response()
    monkeypatch.setattr(aiohttp,'ClientSession',Session)


def test_run_resume_and_unknown_errors_never_reject(tmp_path,monkeypatch):
    fake_health(monkeypatch)
    items=[item(i) for i in range(16)]
    manifest=dict(endpoints=audit.ENDPOINTS,context_limit=32768)
    write_json(tmp_path/'manifest.json',manifest)
    monkeypatch.setattr(audit,'verify',lambda root:(manifest,items))
    calls=[]
    async def query(session,endpoint,payload,writer,metadata):
        calls.append(metadata['id'])
        await asyncio.sleep(0)
        if metadata['id']=='0' and calls.count('0')==1: raise asyncio.TimeoutError()
        return dict(content=json.dumps(verdict()),finish_reason='stop',raw_request_id='fake',usage={})
    result=asyncio.run(audit.run(tmp_path,ready=True,query=query))
    assert result['counts']['complete']==15 and result['counts']['abort_status_unknown']==1
    assert not result['counts'].get('reject')
    asyncio.run(audit.run(tmp_path,ready=True,query=query))
    assert len(calls)==16
    result=asyncio.run(audit.run(tmp_path,ready=True,retry_errors=True,query=query))
    assert result['counts']['complete']==16 and len(calls)==17
    assert len(list((tmp_path/'error-archive').glob('*.json')))==1


def test_interrupted_context_and_schema_failure(tmp_path,monkeypatch):
    fake_health(monkeypatch)
    items=[item(i) for i in range(3)]
    items[1]['prompt_tokens']=32768
    manifest=dict(endpoints=audit.ENDPOINTS,context_limit=32768)
    write_json(tmp_path/'manifest.json',manifest)
    monkeypatch.setattr(audit,'verify',lambda root:(manifest,items))
    write_json(audit.outcome_path(tmp_path,items[0]),dict(status='inflight',
        row_sha256=items[0]['row_sha256'],request_sha256=digest(items[0]['request'])))
    calls=[]
    async def query(*args):
        calls.append(True)
        return dict(content='{"disposition":"reject"}',finish_reason='stop',raw_request_id='fake')
    result=asyncio.run(audit.run(tmp_path,ready=True,query=query))
    assert result['counts']==dict(abort_status_unknown=1,preflight_blocked=1,invalid_response=1)
    assert len(calls)==1


def test_verification_alert_does_not_relabel(tmp_path):
    items=[item(i) for i in range(20)]
    for i,row in enumerate(items):
        result=verdict(); result['disposition']='needs_verification' if i<2 else 'keep'
        write_json(audit.outcome_path(tmp_path,row),dict(status='complete',result=result))
    result=audit.assessment(tmp_path,items)
    assert result['verification_over_budget'] and result['counts']['needs_verification']==2
    assert result['full_audit_authorized'] is False


def test_manual_controls_exactly_twelve_and_hidden():
    controls=[json.loads(l) for l in audit.MANUAL.read_text().splitlines()]
    assert len(controls)==len(audit.CONTROL_VERDICTS)==12
    for control in controls:
        row=control['example']
        payload=audit.request(row)
        assert 'manual_disposition' not in json.dumps(payload)
        assert row['id'] not in json.dumps(payload)
