import pytest

from scripts.dfm16_story_v3 import (check_contract, spec_for, request, plain_payload,
    strict_verdict, ConversationAudit, REVIEW_RULES)


def test_review_is_blind_plain_and_non_thinking(tmp_path):
    adapter = ConversationAudit(tmp_path, tmp_path/'out', 'http://localhost:8805/v1')
    adapter.model = 'Qwen/Qwen3.8-27B'
    value = adapter.prepare(dict(language='en', task='qa', messages=[], manual_label='hold',
                                 specification={'secret': 'reject'}))
    assert value['model'] == adapter.model
    assert value['chat_template_kwargs'] == {'enable_thinking': False}
    assert 'manual_label' not in str(value) and 'secret' not in str(value)
    assert 'response_format' not in value and 'structured_outputs' not in value


def test_no_reasoning_in_judge_output():
    body = {'choices': [{'finish_reason': 'stop', 'message': {'content': 'accept'}}]}
    assert strict_verdict(body)['decision'] == 'accept'
    body['choices'][0]['message']['reasoning_content'] = 'analysis'
    with pytest.raises(ValueError, match='unexpected_thinking'):
        strict_verdict(body)


def conversation():
    return {'messages': [
        {'role': 'user', 'content': 'Write 3-20 words.'},
        {'role': 'assistant', 'content': 'Old opening.\n\nMiddle.\n\nOld ending.'},
        {'role': 'user', 'content': 'Change only opening.'},
        {'role': 'assistant', 'content': 'New opening.\n\nMiddle.\n\nOld ending.'},
        {'role': 'user', 'content': 'Change only ending.'},
        {'role': 'assistant', 'content': 'New opening.\n\nMiddle.\n\nNew ending.'},
        {'role': 'user', 'content': 'Undo opening only.'},
        {'role': 'assistant', 'content': 'Old opening.\n\nMiddle.\n\nNew ending.'}]}


def test_edit_boundaries_and_selective_undo():
    spec = spec_for('revision', 0, 'en')
    spec['length_words'] = '3-20'
    row = dict(language='en', task='revision', specification=spec)
    candidate = conversation()
    check_contract(candidate, row)
    candidate['messages'][7]['content'] = candidate['messages'][5]['content']
    with pytest.raises(ValueError):
        check_contract(candidate, row)
    candidate = conversation()
    candidate['messages'][3]['content'] = 'New opening.\n\nChanged middle.\n\nOld ending.'
    with pytest.raises(ValueError, match='unaffected'):
        check_contract(candidate, row)


def test_length_visible_and_not_inherited_by_qa():
    row = dict(language='en', task='creative', specification={'length_words': '3-20'})
    candidate = conversation()
    candidate['messages'][0]['content'] = 'Write something.'
    with pytest.raises(ValueError, match='not_visible'):
        check_contract(candidate, row)
    assert 'length_words' not in spec_for('qa', 0, 'en')
    check_contract(candidate, dict(language='en', task='qa', specification={}))


def test_prompt_explains_applicability_and_preservation():
    row = dict(language='en', task='rewrite', variant=0, seed='Some seed',
               specification=spec_for('rewrite', 0, 'en'))
    payload = request(row, 'generator')
    assert 'OPPOSITE form' in payload['messages'][0]['content']
    assert 'copy every other' in payload['messages'][0]['content']
    assert payload['chat_template_kwargs']['enable_thinking'] is False


def test_independent_audit_runtime_and_model_receipt(tmp_path):
    import asyncio
    import json
    import httpx
    from audit_pipeline.runtime import run
    from dfm12.io import file_hash, load, write_json
    root, output = tmp_path/'in', tmp_path/'out'
    root.mkdir()
    source = root/'rows.jsonl'
    source.write_text(json.dumps(dict(id='a', audit_id='a', language='en', task='qa',
        messages=[dict(role='user', content='Two plus two?'),
                  dict(role='assistant', content='Four.')]))+'\n')
    write_json(root/'manifest.json', dict(chunks=[dict(job_id='one', input='rows.jsonl',
        rows=1, sha256=file_hash(source), task='qa')]))
    adapter = ConversationAudit(root, output, 'http://localhost:8805/v1')
    adapter.model = 'Qwen/Qwen3.8-27B'
    def handle(request):
        if request.url.path.endswith('/models'):
            return httpx.Response(200, json={'data': [{'id': adapter.model, 'max_model_len': 32768}]})
        payload = json.loads(request.content)
        assert payload['model'] == adapter.model
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop',
            'message': {'content': 'accept'}}]})
    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    asyncio.run(run(adapter, adapter.endpoint, 256, client=client, signals=False))
    receipt = load(output/'one/receipt.json')
    assert receipt['model'] == adapter.model
    assert receipt['counts'] == {'accept': 1}
