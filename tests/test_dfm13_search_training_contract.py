from copy import deepcopy
import pytest
from scripts import dfm13_search_training_contract as contract


def row():
    return dict(id='sample', tools=deepcopy(contract.base.TOOLS), target_message_indices=[3], messages=[
        dict(role='user', content='original'),
        dict(role='assistant', content='', tool_calls=[dict(id='call-a', type='function',
            function=dict(name='search', arguments=dict(query='real query')))]),
        dict(role='tool', name='search', tool_call_id='call-a', content='{"results":[]}'),
        dict(role='assistant', content='answer')])


def test_native_calls_and_singular_final_target():
    source = row(); valid, calls = contract.strict_row(source, 'original')
    view, = list(contract.student_views(valid))
    assert view['target_message_index'] == 3 and 'target_message_indices' not in view
    example, = list(contract.training.examples_from_messages(view['messages'], view['tools'], view['target_message_index']))
    assert example.assistant_message['content'] == 'answer'
    assert example.prompt_messages[1]['tool_calls'] == source['messages'][1]['tool_calls']
    assert example.prompt_messages[2]['role'] == 'tool'
    assert calls[2]['arguments'] == {'query': 'real query'}


@pytest.mark.parametrize('arguments', ['{"query":"a","query":"b"}', '{"query":NaN}', {'query': True}, ['q']])
def test_bad_args_rejected(arguments):
    source = row(); source['messages'][1]['tool_calls'][0]['function']['arguments'] = arguments
    with pytest.raises(ValueError):
        contract.strict_row(source, 'original')


def test_orphan_response_and_steering_rejected():
    source = row(); source['messages'][2]['tool_call_id'] = 'invented'
    with pytest.raises(ValueError, match='orphan'):
        contract.strict_row(source, 'original')
    with pytest.raises(ValueError, match='steering'):
        contract.strict_row(row(), 'different original')


def test_tool_schema_not_external_network_ref():
    source = row(); source['tools'][0]['function']['parameters'] = {'$ref': 'https://example.org/schema'}
    with pytest.raises(ValueError, match='schema'):
        contract.strict_row(source, 'original')


def test_call_id_renaming_deduplicates_but_mask_change_does_not():
    first = row(); second = deepcopy(first)
    second['messages'][1]['tool_calls'][0]['id'] = 'different'
    second['messages'][2]['tool_call_id'] = 'different'
    assert contract.fingerprint(first) == contract.fingerprint(second)
    second['target_message_indices'] = [1, 3]
    assert contract.fingerprint(first) != contract.fingerprint(second)


def test_hash_hold_cannot_be_overridden_by_keep_or_approval():
    source = row(); receipt = dict(admission_authorized=True, candidate_sha256='filehash',
        independent_review_complete=True, decision='admit', provenance_verified=True, student_mask_verified=True,
        approved_target_message_indices=[3], unresolved_findings=[])
    with pytest.raises(ValueError, match='candidate-hash hold'):
        contract.require_admission(source, receipt, 'filehash', [dict(candidate_content_sha256=contract.base.digest(source))])
    with pytest.raises(ValueError, match='forbidden'):
        contract.require_admission(source, {'decision': 'keep'}, 'filehash', [])


def test_changed_excerpt_fails_provenance():
    source = row(); source['messages'][2]['content'] = '{"raw_cache_sha256":"h","results":[{"url":"https://example.org","body":"invented"}]}'
    cache = [dict(query='real query', sha256='h', payload=dict(data=[dict(url='https://example.org', content='real text')]))]
    checked = contract.evidence_check(source, {2:dict(name='search', arguments=dict(query='real query'))}, cache)
    assert checked['complete'] is False and checked['failures']


def test_real_student_gemma_native_render_and_final_only_mask():
    if not contract.METADATA.exists():
        pytest.skip('repository student tokenizer assets unavailable')
    metadata = contract.repair.read(contract.METADATA)
    info = metadata['tokenizer_info']
    tokenizer = contract.Tokenizer.from_file(info['tokenizer_path'])
    template = contract.jinja2.Environment().from_string(contract.Path(info['chat_template_path']).read_text())
    source = row()
    source['messages'][2]['content'] = '{"results":[],"note":"CACHE_SENTINEL"}'
    example, = list(contract.training.examples_from_messages(source['messages'], source['tools'], 3))
    text = contract.training.render(template, example.prompt_messages, source['tools'], True, False)
    assert '<|tool_call>call:search{' in text and '<tool_call|>' in text
    assert '<|tool_response>' in text and 'CACHE_SENTINEL' in text
    prompt, target = contract.training.tokenize_example(tokenizer, template, example, False)
    assert 'CACHE_SENTINEL' not in tokenizer.decode(target, skip_special_tokens=False)
    assert 'answer' in tokenizer.decode(target, skip_special_tokens=False)
    result, = contract.rendered_targets(source, tokenizer, template, info, 4096)
    assert result['target_kind'] == 'final_answer'
    assert result['prompt_tokens'] == len(prompt) and result['target_tokens'] == len(target)
    assert result['shifted_masked_tokens'] == len(prompt) - 1
