import json
from pathlib import Path
import sqlite3

import pytest

from dfm12 import tlpc_grounded_campaign as campaign
from dfm12 import tlpc_grounded_specs as specs
from dfm12.io import digest


def specification(family='grounded-qa'):
    return dict(language_code='fa', family=family, slot=100000, contract_version=4, variant=0,
        source=dict(id='a'*64, text='این یک متن فارسی درباره فناوری است. '*30,
                    title='Title', date='2020-01', url='https://example.org',
                    elements=[{'text':'DUPLICATION'}], original_cache_path='/SECRET/PATH'))


def output(family='grounded-qa'):
    return {'messages':[dict(role='user' if i%2==0 else 'assistant',
        content='این یک پرسش یا پاسخ فارسی درباره متن است.')
        for i in range(2 if family=='grounded-qa' else 6)]}


@pytest.mark.parametrize('family,count', [('grounded-qa',2),('grounded-chat',6)])
def test_native_full_source_and_compact_requests(family,count):
    spec=specification(family); candidate=specs.assemble(spec,output(family))
    assert len(candidate['messages'])==count
    assert spec['source']['text'] in candidate['messages'][0]['content']
    generate=specs.generation_request(spec); review=specs.review_request(spec,candidate)
    for request in (generate,review):
        text=json.dumps(request,ensure_ascii=False)
        assert '/SECRET/PATH' not in text and 'DUPLICATION' not in text
        assert text.count(spec['source']['text'])==1
        assert request['chat_template_kwargs']=={'enable_thinking':False}


def test_malformed_and_wrong_language_rejected():
    row=output(); row['messages'][0]['role']='assistant'
    with pytest.raises(ValueError): specs.assemble(specification(),row)
    row=output(); row['messages'][0]['content']='This is entirely English.'
    with pytest.raises(ValueError): specs.assemble(specification(),row)


def test_exact_targets_and_private_modules():
    from dfm12 import multilingual_quarter
    old=multilingual_quarter.VERSION
    clients=[campaign.controller({'shard':i,'family':f}) for i in range(8) for f in specs.FAMILIES]
    assert sum(campaign.quotas({'shard':i,'family':f})[0]['accepted_target'] for i in range(8) for f in specs.FAMILIES)==100000
    assert multilingual_quarter.VERSION==old
    clients[0].v6.validate_endpoints(['http://127.0.0.1:8800/v1'])
    with pytest.raises(ValueError): clients[0].v6.validate_endpoints(['http://127.0.0.1:8801/v1'])


def test_disjoint_task_sources_and_bounded_reuse(tmp_path):
    db=sqlite3.connect(tmp_path/'sources.sqlite')
    db.execute('CREATE TABLE sources(id TEXT PRIMARY KEY,site TEXT,record_json TEXT)')
    for i in range(30):
        key=digest(i); row=specification()['source'];row['id']=key
        db.execute('INSERT INTO sources VALUES(?,?,?)',(key,'site',json.dumps(row)))
    db.commit();db.close()
    providers=[specs.SourceProvider(tmp_path,tmp_path,{'family':f}) for f in specs.FAMILIES]
    assert set(providers[0].keys).isdisjoint(providers[1].keys)
    assert len(providers[0].keys)+len(providers[1].keys)==30
    for p,f in zip(providers,specs.FAMILIES):
        assert p.next_spec('fa',f,100000)['source']['id']==p.keys[0]
        with pytest.raises(specs.SeedUnavailable):p.next_spec('fa',f,100000+6*len(p.keys))
        p.close()


def test_exactly_once_acceptance_and_quota_reservation(tmp_path):
    c=campaign.controller({'shard':0,'family':'grounded-qa'})
    ledger=c.Ledger(tmp_path/'jobs.sqlite')
    ledger.initialize([{'language':'fa','family':'grounded-qa','accepted_target':1}])
    class Provider:
        def next_spec(self,*args): return specification()
    job=ledger.reserve(Provider(),specs.SeedUnavailable,tmp_path)
    assert ledger.reserve(Provider(),specs.SeedUnavailable,tmp_path) is None
    c.Seen(ledger,job['id']).add('fingerprint')
    result=dict(id=job['id'],spec_sha256=digest(job['spec']),terminal=True,status='valid',effective_keep=True,fingerprint='fingerprint')
    assert ledger.finish(job['id'],result)
    assert not ledger.finish(job['id'],result)
    assert tuple(ledger.db.execute('SELECT accepted,active FROM groups').fetchone())==(1,0)
    ledger.close()


def test_metrics_fail_closed_no_fixed_spacing():
    c=campaign.controller({'shard':0,'family':'grounded-qa'})
    base='vllm:kv_cache_usage_perc 0.3\nvllm:num_requests_waiting 0\n'
    with pytest.raises(ValueError):c.admission_metrics(base)
    assert c.admission_metrics(base+'vllm:num_requests_running 1024\n')['waiting']==1
    assert c.admission_metrics(base+'vllm:num_requests_running 100\n')['waiting']==0
    import asyncio
    from collections import Counter
    gate=c.AdmissionGate(None,['endpoint'],Counter(),{},asyncio.Event(),.8)
    assert gate.max_kv==.98 and gate.spacing==0


def test_unfinished_overlap_export_denied(tmp_path):
    from dfm12.io import write_json
    write_json(tmp_path/'campaign.json',{'clients':[]})
    write_json(tmp_path/'screen.json',{'inherited_complete':False})
    with pytest.raises(ValueError): campaign.export(tmp_path,tmp_path/'export',tmp_path/'screen.json')
