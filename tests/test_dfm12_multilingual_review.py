import asyncio
import json

import pytest

from dfm12 import multilingual_pilot as pilot
from dfm12.multilingual_prepare_next import QUOTAS
from dfm12.multilingual_review import calibration_cases, review_keeps
from dfm12.multilingual_tasks import assemble, spec_for


def approved():
    return dict(language_correct=True, meaning_correct=True, constraints_met=True,
                issues=[], back_translation='The answer is fifteen.')


def test_fail_closed_review():
    assert review_keeps(approved())
    assert not review_keeps(dict(approved(), meaning_correct=False))
    assert not review_keeps(dict(approved(), issues=['Wrong number.']))
    with pytest.raises(ValueError):
        review_keeps(dict(approved(), language_correct='true'))
    with pytest.raises(ValueError):
        review_keeps(dict(approved(), back_translation=''))


def test_second_cohort_config_is_pinned(tmp_path):
    assert sum(QUOTAS.values()) == 5000
    config = dict(contract_version=3, cohort='second', quotas=QUOTAS, second_review=True)
    (tmp_path/'pilot-config.json').write_text(json.dumps(config))
    (tmp_path/'previous-hashes.json').write_text('["existing"]')
    store = pilot.Store(tmp_path)
    assert len(store.pending()) == 35000
    assert store.db.execute('SELECT identity FROM accepted_hashes WHERE hash="existing"').fetchone()[0] == 'previous-pilot'
    store.db.close()
    (tmp_path/'pilot-config.json').write_text(json.dumps(dict(config, second_review=False)))
    with pytest.raises(ValueError, match='configuration changed'):
        pilot.Store(tmp_path)


def tool_result(spec):
    scenario = spec['scenario']
    arguments = dict(scenario['arguments'])
    missing = arguments.pop(scenario['missing_field']) if spec['subtype'] == 'clarify' else None
    if spec['subtype'] == 'multi':
        arguments.update(scenario['action_arguments'])
    return dict(user='Please process ' + json.dumps(arguments), clarification='Which location?',
                clarification_reply=str(missing), final='Done.', retry='Retry.', no_call='General information.')


def test_v3_tools_require_grounded_arguments():
    config = dict(contract_version=3, cohort='second', quotas=QUOTAS)
    for slot in range(25):
        spec = spec_for('nb','tool-dialogue',slot,0,{},config)
        row = assemble(spec,tool_result(spec))
        assert row['provenance']['cohort'] == 'second'
        if spec['subtype'] != 'no-call':
            with pytest.raises(ValueError):
                assemble(spec,dict(tool_result(spec),user='Please do it.'))


def test_second_review_veto_and_resume(tmp_path, monkeypatch):
    from aiohttp import web
    monkeypatch.setattr(pilot, 'LANGUAGES', {'nb': 'Norwegian Bokmal'})
    monkeypatch.setattr(pilot, 'training_renderer', lambda root: None)
    monkeypatch.setattr(pilot, 'student_validate', lambda renderer, row: row)
    (tmp_path/'pilot-config.json').write_text(json.dumps(dict(
        contract_version=3, cohort='second', quotas={'math-code':1}, second_review=True)))
    (tmp_path/'previous-hashes.json').write_text('[]')
    for language in ('nb', 'openhermes'):
        (tmp_path/f'seeds-{language}.json').write_text('[]')
    calls = {'generate':0, 'audit':0, 'review':0}
    calibration = {json.dumps(case['record'],sort_keys=True):case['expected_keep']
                   for case in calibration_cases()}

    async def scenario():
        async def response(request):
            body = await request.json()
            name = body['response_format']['json_schema']['name']
            if name == 'language_meaning_review':
                record = json.loads(body['messages'][-1]['content'])
                keep = calibration.get(json.dumps(record,sort_keys=True))
                if keep is None:
                    calls['review'] += 1
                    keep = calls['review'] > 1
                result = dict(approved(), meaning_correct=keep,
                              issues=[] if keep else ['Incorrect translation.'])
            elif name == 'audit':
                calls['audit'] += 1
                result = dict(keep=True,language_quality=5,coherence=5,usefulness=5,reason='OK')
            else:
                calls['generate'] += 1
                result = {'user':'Problem', 'explanation':'Explanation'}
            return web.json_response({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result)}}]})
        app = web.Application()
        app.router.add_post('/chat/completions',response)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner,'127.0.0.1',0)
        await site.start()
        endpoint = f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}'
        try:
            await pilot.execute(tmp_path,[endpoint],1)
            assert calls == {'generate':2,'audit':2,'review':2}
            await pilot.execute(tmp_path,[endpoint],1)
            assert calls == {'generate':2,'audit':2,'review':2}
        finally:
            await runner.cleanup()
    asyncio.run(scenario())
    row = json.loads((tmp_path/'accepted/math-code-nb.jsonl').read_text())
    assert row['audit']['second_review']['meaning_correct']
