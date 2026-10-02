import json
import pytest

from dfm12.multilingual_review_evidence import keeps, request, VERSION

RECORD = {'language': 'nb', 'family': 'math-code', 'messages': [
    {'role': 'user', 'content': 'What is 7+8?'}, {'role': 'assistant', 'content': '16'}]}


def review():
    return dict(literal_quote='16', back_translation='Literal "16" means sixteen, but the request 7+8 requires fifteen.',
                language_correct=True, meaning_correct=False, constraints_met=True,
                issues=['meaning_correct: Literal "16" contradicts the requested sum 7+8=15.'])


def test_negative_evidence_and_positive_evidence():
    assert keeps(review(), RECORD) is False
    positive = dict(review(), meaning_correct=True, issues=[])
    assert keeps(positive, RECORD) is True  # Semantic agreement is a separate calibration check.


@pytest.mark.parametrize('changes', [
    {'back_translation': 'N/A'}, {'back_translation': ':'}, {'literal_quote': 'invented quote'},
    {'issues': []}, {'issues': ['language_correct: Literal "16" is an invented language error.']},
    {'issues': ['meaning_correct: Something is wrong but no literal evidence is quoted.']},
    {'back_translation': 'The model answer is good and there are no problems here.'},
    {'metadata': 'not an authorized output field'},
])
def test_placeholders_fabricated_quotes_and_inconsistent_flags_fail(changes):
    with pytest.raises(ValueError):
        keeps(dict(review(), **changes), RECORD)


def test_evidence_first_schema_and_same_model():
    payload = request(RECORD)
    grammar = payload['structured_outputs']['grammar']
    import xgrammar as xgr
    tokenizer = xgr.TokenizerInfo([bytes([i]) for i in range(256)] + [b'<eos>'],
                                vocab_type=xgr.VocabType.RAW, stop_token_ids=[256])
    compiled = xgr.GrammarCompiler(tokenizer, max_threads=1).compile_grammar(xgr.Grammar.from_ebnf(grammar))
    ordered = review()
    assert xgr.GrammarMatcher(compiled).accept_string(json.dumps(ordered, separators=(',', ':')))
    wrong_order = {'language_correct': ordered['language_correct'], **ordered}
    assert not xgr.GrammarMatcher(compiled).accept_string(json.dumps(wrong_order, separators=(',', ':')))
    assert payload['model'] == 'google/gemma-4-26B-A4B-it'
    assert payload['chat_template_kwargs'] == {'enable_thinking': False}
    assert payload['max_tokens'] == 4096
    assert 'response_format' not in payload
    assert 'ONE FLAT OBJECT' in payload['messages'][0]['content']
    assert f'Output schema ({VERSION})' in payload['messages'][0]['content']
    assert 'Repeat literal_quote EXACTLY' in payload['messages'][0]['content']


def test_plain_arm_changes_only_transport_and_preserves_validator():
    from dfm12.multilingual_diagnose import diagnostic_request, configured_review_keeps
    grammar = diagnostic_request(RECORD, 'evidence4096')
    plain = diagnostic_request(RECORD, 'evidence_plain4096')
    del grammar['structured_outputs']
    assert grammar == plain
    config = {'review_options': {'variant': 'evidence_plain4096'}}
    assert configured_review_keeps(review(), RECORD, config) is False
    with pytest.raises(ValueError):
        configured_review_keeps(dict(review(), back_translation='N/A'), RECORD, config)
