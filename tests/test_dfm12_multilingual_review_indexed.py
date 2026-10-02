import copy
import json
from pathlib import Path

import jsonschema
import pytest

from dfm12 import multilingual_review_indexed as indexed
from dfm12.io import load, file_hash
from dfm12.multilingual_calibration import calibration_cases

ROOT = Path('data/dfm12/multilingual-quarantine700-20260927-infra-retry-v1')


def record():
    return {'messages': [{'role': 'user', 'content': 'Return exactly the requested answer.'},
                         {'role': 'assistant', 'content': 'The answer is fifteen.\n\\boxed{15}'}]}


def review(candidate):
    entries = indexed.evidence(candidate)
    first = next(e for e in entries if e['evidence_id'] in indexed.primary_evidence_ids(entries))
    return dict(evidence=dict(evidence_id=first['evidence_id'], literal_quote=first['text']),
                back_translation='The literal answer is fifteen as requested in the question.',
                **{key: True for key in indexed.FLAGS},
                issues={key: None for key in indexed.FLAGS})


def rejection(candidate):
    result = review(candidate)
    result['meaning_correct'] = False
    result['issues']['meaning_correct'] = dict(result['evidence'],
        explanation='The literal answer contradicts the value required by the request.')
    return result


def test_positive_negative_are_structurally_valid_not_semantic_gold():
    candidate = record()
    assert indexed.keeps(review(candidate), candidate)
    result = indexed.assess(rejection(candidate), candidate)
    assert result['structural_valid'] and result['reviewer_keep'] is False
    assert result['keep'] is False


@pytest.mark.parametrize('field,value,code', [
    ('back_translation', '', 'text_too_short'),
    ('back_translation', '15 + 3 = 18', 'text_not_meaningful'),
    ('back_translation', 'Everything is correct', 'text_not_meaningful'),
    ('back_translation', 'a' * 601, 'text_too_long'),
    ('meaning_correct', 1, 'flag_type'),
    ('issues', [], 'issue_slots'),
])
def test_precise_errors(field, value, code):
    candidate = record()
    result = review(candidate)
    result[field] = value
    with pytest.raises(indexed.ContractError, match=code):
        indexed.keeps(result, candidate, deterministic=False)
    assert indexed.assess(result, candidate)['semantic_flags'] is None


@pytest.mark.parametrize('length,valid', [(23, False), (24, True), (360, True), (361, False)])
def test_explanation_length_boundaries(length, valid):
    candidate = record()
    result = rejection(candidate)
    result['issues']['meaning_correct']['explanation'] = 'a' * length
    if valid:
        assert indexed.keeps(result, candidate) is False
    else:
        with pytest.raises(indexed.ContractError, match='text_too_'):
            indexed.keeps(result, candidate)


def test_exact_id_text_no_offsets_or_foreign_candidate():
    candidate = record()
    original = review(candidate)
    for replacement in ({'evidence_id': 'foreign'}, {'literal_quote': 'The answer is sixteen.'},
                        {'start': 0}, {'message_index': 1}):
        result = copy.deepcopy(original)
        result['evidence'].update(replacement)
        with pytest.raises(indexed.ContractError):
            indexed.keeps(result, candidate)
    other = copy.deepcopy(candidate)
    other['messages'][0]['content'] = 'Changed request'
    with pytest.raises(indexed.ContractError, match='unknown_evidence_id'):
        indexed.keeps(original, other)


def test_natural_language_preference_and_numeric_fallback():
    candidate = record()
    result = review(candidate)
    numeric = next(e for e in indexed.evidence(candidate) if not e['prose_preferred'])
    result['evidence'] = dict(evidence_id=numeric['evidence_id'], literal_quote=numeric['text'])
    with pytest.raises(indexed.ContractError, match='prefer_natural_language'):
        indexed.keeps(result, candidate)
    candidate['messages'][1]['content'] = '15'
    assert indexed.keeps(review(candidate), candidate)
    candidate['messages'][1]['content'] = ': , '
    with pytest.raises(indexed.ContractError, match='no_meaningful'):
        indexed.evidence(candidate)


def test_no_lost_text_no_mutation_no_user_evidence():
    candidate = record()
    candidate['messages'][1]['content'] = 'long word ' * 150 + '\nLast sentence.'
    before = copy.deepcopy(candidate)
    entries = indexed.evidence(candidate)
    assert ''.join(e['text'] for e in entries) == candidate['messages'][1]['content']
    assert all(len(e['text']) <= 200 and e['message_index'] == 1 for e in entries)
    assert candidate == before


@pytest.mark.parametrize('key', indexed.FLAGS)
def test_exactly_one_issue_per_false_dimension(key):
    candidate = record()
    result = review(candidate)
    result[key] = False
    with pytest.raises(indexed.ContractError, match='false_flag_missing_issue'):
        indexed.keeps(result, candidate)
    result['issues'][key] = dict(result['evidence'], explanation='The candidate violates the explicit required output.')
    assert not indexed.keeps(result, candidate)
    result[key] = True
    with pytest.raises(indexed.ContractError, match='true_flag_has_issue'):
        indexed.keeps(result, candidate)


def test_tool_checks_and_diagnostic_only_bypass_preserved():
    candidate = copy.deepcopy(next(c['record'] for c in calibration_cases()
                                  if c['group'] == 'tool_quantity' and c['polarity'] == 'positive'))
    assert indexed.keeps(review(candidate), candidate)
    candidate['messages'][1]['tool_calls'][0]['function']['arguments']['quantity'] = 'wrong type'
    result = review(candidate)
    assert indexed.keeps(result, candidate, deterministic=False)
    assert not indexed.keeps(result, candidate)
    assert indexed.assess(result, candidate)['structural_valid']
    assert not indexed.assess(result, candidate)['keep']


def test_compiled_grammar_pairs_exact_text_with_id_and_issue_obligation():
    import xgrammar as xgr
    candidate = record()
    payload = indexed.request(candidate)
    tokens = xgr.TokenizerInfo([bytes([i]) for i in range(256)] + [b'<eos>'],
                              vocab_type=xgr.VocabType.RAW, stop_token_ids=[256])
    compiled = xgr.GrammarCompiler(tokens, max_threads=1).compile_grammar(
        xgr.Grammar.from_ebnf(payload['structured_outputs']['grammar']))
    def accepts(result):
        return xgr.GrammarMatcher(compiled).accept_string(json.dumps(result, separators=(',', ':')))
    assert accepts(review(candidate))
    assert accepts(rejection(candidate))
    result = review(candidate)
    result['meaning_correct'] = False
    assert not accepts(result)
    result = review(candidate)
    result['evidence']['literal_quote'] += ' repaired'
    assert not accepts(result)
    assert 'skeptical language editor' in payload['messages'][0]['content']


class Tokenizer:
    def __init__(self, count):
        self.count = count

    def apply_chat_template(self, *args, **kwargs):
        assert kwargs == dict(tokenize=True, add_generation_prompt=True, enable_thinking=False)
        return [1] * self.count


def test_budget_defaults_8k_and_16k_requires_verified_capacity():
    from dfm12.multilingual_tasks import MODEL
    payload = dict(model=MODEL, messages=[], max_tokens=4096, chat_template_kwargs={'enable_thinking': False})
    assert indexed.PromptBudget(Tokenizer(4096)).measure(payload) == 4096
    with pytest.raises(indexed.ContractError, match='review_context_exceeded'):
        indexed.PromptBudget(Tokenizer(4097)).measure(payload)
    with pytest.raises(ValueError, match='Verified server context'):
        indexed.PromptBudget(Tokenizer(8000), context_limit=16384)
    assert indexed.PromptBudget(Tokenizer(8000), context_limit=16384, server_context=16384).measure(payload) == 8000
    with pytest.raises(indexed.ContractError):
        indexed.PromptBudget(Tokenizer(12289), context_limit=16384, server_context=16384).measure(payload)


def test_all_179_actual_failure_fixtures_remain_frozen():
    inventory = load(ROOT / 'noninfra-review-v1/inventory.json')
    assert len(inventory['rows']) == 179
    audit = generation = 0
    for row in inventory['rows']:
        assert file_hash(ROOT / row['outcome_path']) == row['outcome_sha256']
        if row['status'] == 'invalid_generation':
            generation += 1
            continue  # This reviewer cannot repair/admit failed generation.
        audit += 1
        candidate = {'messages': row['candidate_messages']}
        try:
            entries = indexed.evidence(candidate)
        except indexed.ContractError as exc:
            assert exc.code == 'no_meaningful_assistant_evidence'
            assert not any(c.isalnum() for m in candidate['messages']
                           if m['role'] == 'assistant' for c in m.get('content', ''))
            continue  # Punctuation-only candidate still fails closed.
        assert all(0 < len(e['text']) <= 200 for e in entries)
        positive = review(candidate)  # Synthetic contract fixture, NOT a model judgment.
        negative = rejection(candidate)
        indexed.validate(positive, candidate)
        indexed.validate(negative, candidate)
        with pytest.raises(indexed.ContractError, match='review_keys'):
            indexed.validate(row['review'], candidate)
    assert (audit, generation) == (81, 98)


def test_schema_cpu_matches_positive_negative_and_malformed():
    candidate = record()
    contract = indexed.schema(candidate)
    jsonschema.validate(review(candidate), contract)
    jsonschema.validate(rejection(candidate), contract)
    result = review(candidate)
    result['evidence']['literal_quote'] = 'rewritten'
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(result, contract)


def test_installed_length_bounded_string_grammar_escape_regression():
    import xgrammar as xgr
    tokens = xgr.TokenizerInfo([bytes([i]) for i in range(256)] + [b'<eos>'],
                              vocab_type=xgr.VocabType.RAW, stop_token_ids=[256])
    compiler = xgr.GrammarCompiler(tokens, max_threads=1)
    observed = {}
    for bounded in (False, True):
        contract = {'type': 'string'}
        if bounded:
            contract.update(minLength=1, maxLength=360)
        compiled = compiler.compile_grammar(xgr.Grammar.from_json_schema(contract,
            any_whitespace=False, indent=None, separators=(',', ':')))
        observed[bounded] = [xgr.GrammarMatcher(compiled).accept_string(json.dumps(text))
            for text in ('Plain text here.', 'Quoted "word" here.', 'First line\nSecond line', 'a\\b')]
    assert observed[False] == [True, True, True, True]
    assert observed[True] == [True, False, False, False]


def test_all_242_controls_preserve_independent_flags_and_deterministic_checks():
    from dfm12.multilingual_tool_calibration import routed_cases
    from dfm12.multilingual_review_routed import deterministic_checks
    cases = routed_cases()
    assert len(cases) == 242
    for case in cases:
        candidate = case['record']
        assert indexed.deterministic_checks(candidate) == deterministic_checks(candidate)
        for key in indexed.FLAGS:
            result = review(candidate)
            result[key] = False
            result['issues'][key] = dict(result['evidence'],
                explanation='This is a contract-only negative fixture for an independent dimension.')
            assessment = indexed.assess(result, candidate)
            assert assessment['structural_valid'] and assessment['semantic_flags'][key] is False
            assert not assessment['reviewer_keep'] and not assessment['keep']
        assert indexed.assess(review(candidate), candidate)['reviewer_keep'] is True


@pytest.mark.parametrize('subtype', ('single', 'clarify', 'multi', 'error', 'retry', 'no-call'))
def test_native_tool_all_six_subtypes(subtype):
    import random
    from dfm12 import multilingual_tool_dialogue as native
    from dfm12.multilingual_references import tool_scenario
    from dfm12.multilingual_tasks import assemble
    spec = native.configure(dict(contract_version=4, language='English', language_code='en',
        family='tool-dialogue', slot=0, variant=0, cohort='indexed-cpu-fixture',
        audience='adult', tone='concise', subtype=subtype,
        scenario=tool_scenario(0, random.Random(42))))
    if subtype == 'no-call':
        output = dict(user='Explain this hypothetical service.',
                      explanation='A lookup could precede a separately requested action.')
    else:
        output = dict(user='Please perform the supplied mock task.',
                      final='The mock action succeeded.' if subtype == 'multi' else
                            'The lookup failed temporarily.' if subtype == 'error' else
                            'The lookup returned availability; no action was performed.')
        if subtype == 'clarify':
            output.update(clarification='Please supply the missing lookup argument.',
                          clarification_reply='Here is the requested information.')
    candidate = assemble(spec, output)
    before = copy.deepcopy(candidate)
    assert all(c['passed'] for c in indexed.deterministic_checks(candidate))
    assert indexed.keeps(review(candidate), candidate)
    assert not indexed.keeps(rejection(candidate), candidate)
    assert candidate == before
