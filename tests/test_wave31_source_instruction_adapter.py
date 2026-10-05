import json
from copy import deepcopy

import jsonschema
import pytest

from dfm12 import wave31_source_instruction_adapter as a


@pytest.fixture
def spec():
    return dict(contract_version=4, language_code='en', language='English',
                family='grounded-instruct', subtype='extraction', slot=0, variant=0,
                source={'text': 'The workshop opened in 1987.\nIt has two rooms.'})


def test_full_source_present_once_and_assistant_unchanged(spec):
    row = a.assemble(spec, {'instruction': 'When did the workshop open?', 'assistant': 'In 1987.'})
    assert row['messages'][0]['content'].count(spec['source']['text']) == 1
    assert row['messages'][1]['content'] == 'In 1987.'
    assert row['rendered_training_tokens'] <= 4096
    assert not row['admission_authorized']


@pytest.mark.parametrize('depth', [0, 1, 2])
def test_exact_whole_source_serialization_only(spec, depth):
    source = spec['source']['text'] + '\nCode: print(r"C:\\new\\test")'
    value = source
    for _ in range(depth):
        value = json.dumps(value, ensure_ascii=False)[1:-1]
    user, receipt = a.normalize_user('Read: ' + value + ' When opened?', source)
    assert user == 'Read: ' + source + ' When opened?'
    assert r'C:\new\test' in user
    assert receipt['mode'] == 'exact_source_echo_retained_once'


def test_literal_backslashes_outside_source_not_unescaped(spec):
    row = a.assemble(spec, {'instruction': r'Explain literal \n, using the passage.',
                            'assistant': r'The string \n is literal.'})
    assert r'\n' in row['messages'][0]['content']
    assert row['messages'][1]['content'] == r'The string \n is literal.'


def test_overlong_mutated_echo_fails_closed(spec):
    source = 'First line.\n' + 'Distinct passage ' * 70
    with pytest.raises(ValueError, match='uncertain_source_echo'):
        a.normalize_user('Summarize ' + source.replace('First', 'Changed'), source)


def test_duplicate_sources_refused(spec):
    with pytest.raises(ValueError, match='multiple_source'):
        a.normalize_user(spec['source']['text'] * 2, spec['source']['text'])


def test_field_bound_and_roles_remain(spec):
    with pytest.raises(jsonschema.ValidationError):
        a.assemble(spec, {'instruction': 'x' * 901, 'assistant': 'Fine'})
    with pytest.raises(jsonschema.ValidationError):
        a.assemble(spec, {'instruction': 'Question', 'assistant': 'x' * 2401})
    with pytest.raises(jsonschema.ValidationError):
        a.assemble(spec, {'instruction': 'Question', 'assistant': 'Fine', 'tools': []})


def test_no_translation_or_math_route(spec):
    for family in ('openhermes', 'math-code', 'multiturn', 'tool-dialogue'):
        changed = deepcopy(spec); changed['family'] = family
        with pytest.raises(ValueError, match='only supports'):
            a.schema(changed)


def test_context_overflow_no_truncation(spec):
    # Unique words avoid triggering the independent repetition gate.
    spec['source']['text'] = ' '.join('sourceword' + str(i) for i in range(6000))
    with pytest.raises(ValueError, match='4096'):
        a.assemble(spec, {'instruction': 'Summarize the source.', 'assistant': 'A source.'})


def test_old_long_user_allowed_only_as_verified_source(spec):
    spec['source']['text'] = ' '.join('item' + str(i) for i in range(250))
    row = a.assemble(spec, {'user': 'Summarize: ' + spec['source']['text'], 'assistant': 'Items are listed.'}, legacy=True)
    assert len(row['messages'][0]['content']) > 900
    assert row['messages'][0]['content'].count(spec['source']['text']) == 1


def test_duplicate_json_keys_rejected(spec):
    with pytest.raises(ValueError):
        a.assemble(spec, '{"instruction":"one","instruction":"two","assistant":"answer"}')


def test_incomplete_finish_is_not_salvaged(spec):
    with pytest.raises(ValueError, match='incomplete_generation'):
        a.decode(spec, '{"instruction":"When?","assistant":"1987"}', 'length')


def test_successor_request_isolated(spec):
    historical = {'request': {'model': 'test', 'messages': [
        {'role': 'system', 'content': 'old'}, {'role': 'user', 'content': 'source data'}]}}
    prepared = a.request(spec, historical)
    assert historical['request']['messages'][0]['content'] == 'old'
    assert prepared['schema']['properties']['instruction']['maxLength'] == 900
    assert 'complete unmodified source' in prepared['request']['messages'][0]['content']
