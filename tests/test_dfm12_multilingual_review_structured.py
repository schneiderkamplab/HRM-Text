import copy
import json

import pytest

from dfm12.multilingual_review_structured import keeps, request, deterministic_checks

RECORD = {'messages': [{'role': 'user', 'content': 'Say RED.'},
                       {'role': 'assistant', 'content': 'BLUE'}]}


def review():
    return dict(message_index=1, literal_quote='BLUE',
                back_translation='The candidate says blue instead of the requested red.',
                language_correct=True, meaning_correct=False, constraints_met=True,
                issues=[dict(dimension='meaning_correct', message_index=1, quote='BLUE',
                             explanation='The stated color differs from the requested color.')])


def test_no_mechanical_quote_repetition_required():
    assert keeps(review(), RECORD) is False
    assert keeps(dict(review(), meaning_correct=True, issues=[]), RECORD) is True


@pytest.mark.parametrize('field,value', [('message_index', 0), ('message_index', True),
    ('message_index', -1), ('literal_quote', 'RED'), ('back_translation', 'N/A'),
    ('issues', []), ('meaning_correct', 0)])
def test_invalid_evidence(field, value):
    with pytest.raises(ValueError):
        keeps(dict(review(), **{field: value}), RECORD)


@pytest.mark.parametrize('field,value', [('dimension', 'language_correct'),
    ('message_index', 0), ('quote', 'RED'), ('explanation', ':'), ('extra', True)])
def test_invalid_issue(field, value):
    result = review()
    result['issues'][0][field] = value
    with pytest.raises(ValueError):
        keeps(result, RECORD)


def test_duplicate_issue_fails():
    result = review()
    result['issues'] *= 2
    with pytest.raises(ValueError):
        keeps(result, RECORD)


def test_structure_checks_are_applicable_only_and_block_acceptance():
    assert deterministic_checks(RECORD) == []
    record = dict(RECORD, source_messages=[{'role': 'user', 'content': 'Say RED.'}])
    assert keeps(dict(review(), meaning_correct=True, issues=[]), record) is False
    tool = copy.deepcopy(RECORD)
    tool['messages'][1]['tool_calls'] = [{'function': {'arguments': '{invalid'}}]
    assert deterministic_checks(tool)[0]['passed'] is False
    tool['messages'][1]['tool_calls'][0]['function']['arguments'] = '{"count":2}'
    assert deterministic_checks(tool)[0]['passed'] is True


def test_compact_grammar_escapes_and_default_model():
    import xgrammar as xgr
    payload = request(RECORD)
    assert payload['model'] == 'google/gemma-4-26B-A4B-it'
    assert payload['chat_template_kwargs'] == {'enable_thinking': False}
    assert payload['max_tokens'] == 4096
    tokenizer = xgr.TokenizerInfo([bytes([i]) for i in range(256)] + [b'<eos>'],
                                vocab_type=xgr.VocabType.RAW, stop_token_ids=[256])
    compiled = xgr.GrammarCompiler(tokenizer, max_threads=1).compile_grammar(
        xgr.Grammar.from_ebnf(payload['structured_outputs']['grammar']))
    result = review()
    result['issues'][0]['explanation'] += ' It says "blue".'
    assert xgr.GrammarMatcher(compiled).accept_string(json.dumps(result, separators=(',', ':')))
    assert not xgr.GrammarMatcher(compiled).accept_string(json.dumps(result, indent=2))
    result['message_index'] = 0
    assert not xgr.GrammarMatcher(compiled).accept_string(json.dumps(result, separators=(',', ':')))


def test_explicit_absolute_indices_and_unmodified_context():
    from dfm12.multilingual_review_structured import schema
    record = copy.deepcopy(RECORD)
    record['messages'] += [{'role': 'user', 'content': 'Again.'},
                           {'role': 'assistant', 'content': 'BLUE'}]
    before = copy.deepcopy(record)
    payload = request(record)
    body = json.loads(payload['messages'][1]['content'])
    assert body['record'] == before == record
    assert [e['message_index'] for e in body['indexed_candidate_assistant_entries']] == [1, 3]
    assert schema(record)['properties']['message_index']['enum'] == [1, 3]
    assert schema(record)['properties']['issues']['items']['properties']['message_index']['enum'] == [1, 3]
    assert 'not just digits' in payload['messages'][0]['content']


def test_structured_scoring_separates_format_from_decisions():
    from dfm12.multilingual_calibration import score_reviews
    case = dict(name='test', split='development', record=dict(RECORD, language='nb'),
                expected_keep=False, expected_dimensions={'meaning_correct': False})
    report = score_reviews([case], {'test': review()}, validator=keeps)
    assert report['by_language']['nb']['development']['agreement'] == 1
    bad = dict(review(), issues=[])
    report = score_reviews([case], {'test': bad}, validator=keeps)
    assert report['by_language']['nb']['development']['invalid'] == 1
    assert report['by_language']['nb']['development']['false_accepts'] == 0


@pytest.mark.parametrize('explanation', ['The number fifteen.', 'The number 17.'])
def test_short_meaningful_numeric_explanation(explanation):
    number = '17' if '17' in explanation else '15'
    record = {'messages': [{'role': 'user', 'content': 'Compute.'},
                           {'role': 'assistant', 'content': number}]}
    result = dict(review(), literal_quote=number, back_translation=explanation,
                  meaning_correct=True, issues=[])
    assert keeps(result, record) is True
    for placeholder in ('15', 'N/A', ':', 'good', 'Looks good.', 'Correct answer',
                        'The answer is correct.', 'Not applicable'):
        with pytest.raises(ValueError):
            keeps(dict(result, back_translation=placeholder), record)
