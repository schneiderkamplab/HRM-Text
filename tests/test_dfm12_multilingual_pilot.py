import json
import asyncio

import pytest

from dfm12.multilingual_pilot import Store, student_validate
from dfm12.multilingual_tasks import QUOTAS, assemble, spec_for


def seeds():
    return {'nb':[{'text':'Source passage.','id':'x'}],
            'openhermes':[{'messages':[{'role':'user','content':'Hello'},{'role':'assistant','content':'Hi'}]}]}


def test_targets_and_resume(tmp_path):
    assert sum(QUOTAS.values()) == 5000
    store = Store(tmp_path)
    assert len(store.pending()) == 35000
    key = ('nb','multiturn',0)
    store.save(key,status='accepted',candidate=json.dumps({'id':'abc'}),audit=json.dumps({'keep':True}))
    store.db.close()
    again = Store(tmp_path)
    assert len(again.pending()) == 34999
    again.export()
    assert json.loads((tmp_path/'accepted/multiturn-nb.jsonl').read_text())['id'] == 'abc'
    again.db.close()


def test_contract_migration_preserves_accepted(tmp_path):
    store = Store(tmp_path)
    accepted = ('nb','multiturn',0)
    failed = ('nb','multiturn',1)
    store.save(accepted,status='accepted',attempts=1)
    store.save(failed,status='exhausted',attempts=6)
    store.event(failed,5,'failed_attempt',{'error':"ValueError('Wrong turn count')"})
    assert store.repair_contract_v1() == 1
    assert store.repair_contract_v1() == 0
    assert store.db.execute("SELECT status FROM slots WHERE language='nb' AND family='multiturn' AND slot=0").fetchone()[0] == 'accepted'
    assert store.db.execute("SELECT status,attempts FROM slots WHERE language='nb' AND family='multiturn' AND slot=1").fetchone() == ('pending',0)
    store.db.close()


def test_math_and_code_reference():
    for slot in range(30):
        spec = spec_for('nb','math-code',slot,0,seeds())
        row = assemble(spec,{'user':'Solve this problem','explanation':'Explanation'})
        answer = row['messages'][-1]['content']
        if slot % 2 == 0:
            assert answer.endswith('\\boxed{'+str(spec['reference']['answer'])+'}')
            assert answer.count('\\boxed') == 1
        else:
            assert spec['reference']['code'] in answer


def test_tools_cpu_owned():
    for subtype in ('single','clarify','multi','error','no-call'):
        spec = spec_for('nb','tool-dialogue',0,0,seeds())
        spec['subtype'] = subtype
        result = {key:'Some natural text' for key in ('user','clarification','clarification_reply','final','retry','no_call')}
        row = assemble(spec,result)
        assert row['tools'][0]['function']['name'] == 'lookup_stock'
        calls = [call for message in row['messages'] for call in message.get('tool_calls',[])]
        assert len(calls) == {'single':1,'clarify':1,'multi':2,'error':2,'no-call':0}[subtype]


def test_grounding_visible():
    spec = spec_for('nb','grounded-instruct',0,0,seeds())
    row = assemble(spec,{'user':'What is it?','assistant':'The answer.'})
    assert spec['source']['text'] in row['messages'][0]['content']


def test_wrong_turn_count_rejected():
    spec = spec_for('nb','multiturn',0,0,seeds())
    with pytest.raises(ValueError,match='turn count'):
        assemble(spec,{'messages':[{'role':'user','content':'Hello'},{'role':'assistant','content':'Hi'}]})


def test_generation_audit_retry_and_resume(tmp_path, monkeypatch):
    from aiohttp import web
    from dfm12 import multilingual_pilot as pilot
    monkeypatch.setattr(pilot, 'LANGUAGES', {'nb':'Norwegian Bokmal'})
    monkeypatch.setattr(pilot, 'QUOTAS', {'math-code':1})
    monkeypatch.setattr(pilot, 'training_renderer', lambda root: None)
    monkeypatch.setattr(pilot, 'student_validate', lambda renderer, row: row)
    for name in ('nb','openhermes'):
        (tmp_path/f'seeds-{name}.json').write_text('[]')
    calls = {'generate':0,'audit':0}
    async def scenario():
        async def response(request):
            body = await request.json()
            if body['temperature']:
                calls['generate'] += 1
                result = {'user':'Test problem','explanation':'Explanation'}
            else:
                calls['audit'] += 1
                result = dict(keep=calls['audit']>1,language_quality=5,coherence=5,usefulness=5,reason='test')
            return web.json_response({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result)}}]})
        app = web.Application()
        app.router.add_post('/chat/completions',response)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner,'127.0.0.1',0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        try:
            await pilot.execute(tmp_path,[f'http://127.0.0.1:{port}'],1)
            assert calls == {'generate':2,'audit':2}
            await pilot.execute(tmp_path,[f'http://127.0.0.1:{port}'],1)
            assert calls == {'generate':2,'audit':2}
        finally:
            await runner.cleanup()
    asyncio.run(scenario())
    accepted = [json.loads(line) for line in (tmp_path/'accepted/math-code-nb.jsonl').read_text().splitlines()]
    assert len(accepted) == 1
    assert accepted[0]['audit']['keep'] is True
