import copy
import json

import pytest

from dfm12.multilingual_calibration import calibration_cases
from dfm12.multilingual_review_tools import (arguments, canonical_messages, deterministic_checks,
    evidence, keeps, request, schema, _location)


def tool_record():
    return copy.deepcopy(next(c['record'] for c in calibration_cases()
        if c['group']=='tool_quantity' and c['polarity']=='positive'))


def review(record):
    entry = next(e for e in evidence(record) if e['pointer'].endswith('/arguments/quantity'))
    return dict(message_index=entry['message_index'], pointer=entry['pointer'], literal_quote=entry['text'],
        back_translation='The quantity is two tickets as explicitly requested.',
        language_correct=True, meaning_correct=True, constraints_met=True,
        issues=dict(language_correct=None, meaning_correct=None, constraints_met=None))


def test_mapping_and_json_string_arguments_have_identical_evidence():
    record = tool_record()
    before = copy.deepcopy(record)
    other = copy.deepcopy(record)
    function = other['messages'][1]['tool_calls'][0]['function']
    function['arguments'] = json.dumps(function['arguments'])
    assert canonical_messages(record) == canonical_messages(other)
    assert evidence(record) == evidence(other)
    assert all(c['passed'] for c in deterministic_checks(record))
    assert keeps(review(record), record)
    assert keeps(review(other), other)
    assert record == before


@pytest.mark.parametrize('value', ['{"q":1,"q":2}', '{"q":NaN}', '{"q":Infinity}',
    '{"q":-Infinity}', {'q':float('nan')}, {'q':float('inf')}, '[]', 'null', '[1]', 1])
def test_invalid_argument_representation(value):
    with pytest.raises((ValueError,TypeError)):
        arguments(value)


@pytest.mark.parametrize('change', [dict(quantity='2'), dict(quantity=0), dict(event_id=42), dict(extra=1)])
def test_actual_schema_failures_still_reject(change):
    record = tool_record()
    record['messages'][1]['tool_calls'][0]['function']['arguments'].update(change)
    assert not all(c['passed'] for c in deterministic_checks(record))
    result = review(record)
    assert keeps(result, record, deterministic=False)
    assert not keeps(result, record)


def test_external_refs_never_resolve():
    record = tool_record()
    record['tools'][0]['function']['parameters'] = {'$ref':'https://example.invalid/schema'}
    assert not deterministic_checks(record)[0]['passed']


def test_exact_pointer_and_cpu_offsets():
    record = tool_record()
    result = review(record)
    assert _location(result, record, 'literal_quote') == [dict(start=0,end=1)]
    for patch in (dict(pointer='/messages/0/content'),dict(message_index=0),dict(literal_quote='999')):
        with pytest.raises(ValueError):
            keeps(dict(result, **patch),record)


def test_false_dimension_must_have_issue_even_when_another_rejects():
    record = tool_record()
    result = dict(review(record), meaning_correct=False, constraints_met=False)
    result['issues']['meaning_correct'] = dict(message_index=1,
        pointer=result['pointer'], quote=result['literal_quote'],
        explanation='The actual quantity contradicts the required quantity.')
    with pytest.raises(ValueError, match='False dimension'):
        keeps(result,record)
    result['issues']['constraints_met'] = copy.deepcopy(result['issues']['meaning_correct'])
    assert keeps(result,record) is False


def test_compact_grammar_enforces_issue_obligation_and_has_no_offsets():
    import xgrammar as xgr
    record = tool_record()
    payload = request(record)
    assert 'start' not in schema(record)['anyOf'][0]['properties']
    assert 'extra prose' in payload['messages'][0]['content']
    tokenizer = xgr.TokenizerInfo([bytes([i]) for i in range(256)] + [b'<eos>'],
                                vocab_type=xgr.VocabType.RAW, stop_token_ids=[256])
    compiled = xgr.GrammarCompiler(tokenizer,max_threads=1).compile_grammar(
        xgr.Grammar.from_ebnf(payload['structured_outputs']['grammar']))
    result = review(record)
    assert xgr.GrammarMatcher(compiled).accept_string(json.dumps(result,separators=(',',':')))
    result['meaning_correct'] = False
    assert not xgr.GrammarMatcher(compiled).accept_string(json.dumps(result,separators=(',',':')))


def test_old_tool_positives_no_longer_vetoed():
    positives = [c for c in calibration_cases() if c['group'] in ('tool_quantity','tool_schema') and c['expected_keep']]
    assert len(positives)==14
    assert all(all(x['passed'] for x in deterministic_checks(c['record'])) for c in positives)


def test_fresh_controls_balanced_and_negative_schema_link_failures_real():
    from dfm12.multilingual_tool_calibration import fresh_cases
    cases = fresh_cases()
    fresh = [c for c in cases if c['split']=='fresh_heldout']
    assert len(cases)==228 and len(fresh)==56
    assert sum(c['expected_keep'] for c in fresh)==28
    for case in fresh:
        checks = deterministic_checks(case['record'])
        if case['expected_keep']:
            assert all(c['passed'] for c in checks)
        elif case['group'] in ('tool_argument_schema','tool_result_binding'):
            assert not all(c['passed'] for c in checks)
