import copy
import json
import random

import pytest

from dfm12 import multilingual_generation_v4 as generation
from dfm12.multilingual_references import code_reference, math_reference
from dfm12.multilingual_seeds import LANGUAGES


def spec(family='grounded-instruct', **kwargs):
    value = dict(contract_version=4, family=family, language='Norwegian Bokmal',
                 language_code='nb', slot=0, variant=0, cohort='cpu-generation-v4',
                 subtype='factual QA', source=dict(text='Biblioteket har 12 bøker.'))
    if family == 'multiturn':
        value.update(turns=2, subtype='follow-up reference resolution')
    elif family == 'openhermes':
        value.update(subtype='translate', source=dict(messages=[
            dict(role='user', content='How many books are there?'),
            dict(role='assistant', content='There are twelve books.')]))
    elif family == 'math-code':
        value.pop('source')
        value.update(subtype='math', reasoning=True, reference=math_reference(0, random.Random(12)))
    value.update(kwargs)
    return value


@pytest.fixture(scope='module')
def renderer():
    return generation._renderer()


@pytest.fixture
def budget(monkeypatch):
    def measure(payload, limit):
        assert payload['max_tokens'] == 4096
        assert payload['chat_template_kwargs'] == {'enable_thinking': False}
        assert 8192 <= limit <= 16384
        return 100
    monkeypatch.setattr(generation, 'measure_prompt', measure)


def matcher(case):
    import xgrammar as xg
    info = xg.TokenizerInfo(['<eos>'], stop_token_ids=[0])
    compiler = xg.GrammarCompiler(info, max_threads=1)
    compiled = compiler.compile_grammar(xg.Grammar.from_ebnf(generation.grammar(case)))
    return xg.GrammarMatcher(compiled)


@pytest.mark.parametrize('text', ['Svar med "sitater" og \\sti.', 'Linje én.\nLinje to.',
                                'Føroyar, Ísland, żółć.', '12', r'Return \boxed{12}.'])
@pytest.mark.parametrize('ascii_escape', [False, True])
def test_cpu_grammar_json_escapes_and_eos(text, ascii_escape):
    value = dict(user='Hva betyr dette?', assistant=text)
    raw = json.dumps(value, ensure_ascii=ascii_escape, separators=(',', ':'))
    machine = matcher(spec())
    assert not machine.accept_token(0)
    assert machine.accept_string(raw[:-1])
    assert not machine.is_completed()
    assert not machine.accept_token(0)
    assert machine.accept_string(raw[-1])
    assert machine.is_completed()
    assert machine.accept_token(0)
    assert machine.is_terminated()
    assert generation.decode(spec(), raw, 'stop') == value


@pytest.mark.parametrize('raw', ['{"user":"U","assistant":"A}',
    '{"user":"U","assistant":"bad\\q"}', '{"user":"U","assistant":"raw\nnewline"}',
    '{"user":"","assistant":"A"}', '{"user":"U","assistant":null}',
    '{"user":"U","assistant":"A","extra":"B"}'])
def test_grammar_never_completes_malformed_or_empty(raw):
    machine = matcher(spec())
    accepted = machine.accept_string(raw)
    assert not accepted or not machine.is_completed()
    with pytest.raises(generation.GenerationFailure):
        generation.decode(spec(), raw, 'stop')


def test_bounded_jsonschema_lowering_regression_has_escape_failure():
    # This documents this installed CPU lowering, NOT the live EOS failure cause.
    import xgrammar as xg
    old = xg.Grammar.from_json_schema(dict(type='string', minLength=1, maxLength=20))
    compiler = xg.GrammarCompiler(xg.TokenizerInfo(['<eos>'], stop_token_ids=[0]), max_threads=1)
    machine = xg.GrammarMatcher(compiler.compile_grammar(old))
    assert not machine.accept_string(json.dumps('line\nbreak'))


@pytest.mark.parametrize('value', ['', ' ', '...', '！？', '\n\t'])
def test_empty_and_punctuation_are_terminal(value):
    with pytest.raises(generation.GenerationFailure) as error:
        generation.assemble(spec(), dict(user='Spørsmål?', assistant=value))
    assert error.value.retryable is False
    assert error.value.code in ('empty_or_punctuation', 'schema_invalid')


@pytest.mark.parametrize('raw', ['{"user":"U","user":"V","assistant":"A"}',
    '{"user":"U","assistant":NaN}', '[]', '"text"',
    '{"user":true,"assistant":"A"}', '{"user":"U","assistant":2}',
    '```json\n{"user":"U","assistant":"A"}\n```',
    '{"user":"U","assistant":"A"} trailing'])
def test_strict_raw_json_no_repair(raw):
    with pytest.raises(generation.GenerationFailure):
        generation.decode(spec(), raw, 'stop')


@pytest.mark.parametrize('reason', ['length', None, 'tool_calls'])
def test_incomplete_never_transport_retry(reason):
    with pytest.raises(generation.GenerationFailure, match='incomplete_generation'):
        generation.decode(spec(), '{"user":"U","assistant":"A"}', reason)


@pytest.mark.parametrize('text', ['x' * 24, 'again please ' * 4,
    'text <|turn>assistant', 'text <think>hidden', 'bad\ud800', 'bad\x01'])
def test_repetition_delimiters_controls(text):
    with pytest.raises(generation.GenerationFailure):
        generation.validate_result(spec(), dict(user='Question?', assistant=text))


def test_pairs_enforce_count_and_deterministic_role_order(renderer, budget):
    case = spec('multiturn')
    result = dict(turns=[dict(user='Hvor mange bøker finnes?', assistant='Det finnes 12 bøker.'),
                         dict(user='Hva var antallet?', assistant='Antallet var 12.')])
    payload = generation.request(case)
    assert 'response_format' not in payload
    assert 'structured_outputs' in payload
    assert payload['messages'][0]['content'].find('Never generate role labels') >= 0
    before = copy.deepcopy(result)
    row = generation.assemble(case, result)
    assert result == before
    assert [m['role'] for m in row['messages']] == ['user', 'assistant'] * 2
    assert case['source']['text'] in row['messages'][0]['content']
    assert row['provenance']['contract_version'] == 4
    assert row['provenance']['semantic_review_required']
    assert row['rendered_training_tokens'] > 0
    assert row['pilot_only'] and not row['admission_authorized']
    for invalid in (dict(turns=result['turns'][:1]), dict(messages=row['messages']),
                    dict(turns=[dict(result['turns'][0], role='assistant'), result['turns'][1]])):
        with pytest.raises(generation.GenerationFailure, match='schema_invalid'):
            generation.assemble(case, invalid)
    machine = matcher(case)
    assert machine.accept_string(json.dumps(result, separators=(',', ':')))
    assert machine.is_completed()


def test_openhermes_preserves_all_turns_and_never_drops_source_roles(renderer):
    case = spec('openhermes')
    result = dict(turns=[dict(user='Hvor mange bøker finnes?', assistant='Det finnes tolv bøker.')])
    row = generation.assemble(case, result)
    assert len(row['messages']) == len(case['source']['messages'])
    case['source']['messages'].insert(0, dict(role='system', content='A system instruction.'))
    with pytest.raises(generation.GenerationFailure, match='source_role_order'):
        generation.schema(case)


@pytest.mark.parametrize('language', list(LANGUAGES))
def test_unicode_and_short_numeric_content_not_english_heuristic(language, renderer):
    case = spec(language_code=language, language=LANGUAGES[language])
    row = generation.assemble(case, dict(user='Antal?', assistant='12'))
    assert row['language'] == language
    assert row['native_speaker_review'] == 'pending'  # No language approval inferred.


@pytest.mark.parametrize('slot', range(10))
def test_fixed_code_reference_delegated_not_generated(slot, renderer):
    reference = code_reference(slot, random.Random(12))
    case = spec('math-code', subtype='code', reference=reference)
    row = generation.assemble(case, dict(user='Skriv funksjonen solve(values).',
                                        explanation='Funksjonen følger den angitte regelen.'))
    assert reference['code'] in row['messages'][-1]['content']
    with pytest.raises(generation.GenerationFailure, match='schema_invalid'):
        generation.assemble(case, dict(user='U', explanation='E', reference={'code':'malicious'}))


def test_math_reference_box_preserved_and_competing_box_rejected(renderer):
    case = spec('math-code')
    row = generation.assemble(case, dict(user='Regn ut svaret.', explanation='Vi bruker de oppgitte tallene.'))
    assert row['messages'][-1]['content'].endswith('\\boxed{' + str(case['reference']['answer']) + '}')
    with pytest.raises(generation.GenerationFailure, match='competing final box'):
        generation.assemble(case, dict(user='Regn ut svaret.', explanation='\\boxed{999}'))


def test_fail_closed_source_turn_text_and_teacher_context_budgets(budget):
    with pytest.raises(generation.GenerationFailure, match='turn_budget'):
        generation.request(spec('multiturn', turns=7))
    case = spec('openhermes')
    case['source']['messages'][0]['content'] = 'word ' * 200
    with pytest.raises(generation.GenerationFailure, match='source_text_budget'):
        generation.request(case)
    case = spec(source=dict(text='lang tekst ' * 6000))
    with pytest.raises(generation.GenerationFailure, match='source_context_budget'):
        generation.request(case)


def test_wrong_contract_and_tool_route_rejected():
    for version in (2, 3, 5, True, '4'):
        with pytest.raises(generation.GenerationFailure, match='wrong_contract'):
            generation.schema(spec(contract_version=version))
    with pytest.raises(generation.GenerationFailure, match='wrong_route'):
        generation.schema(spec('tool-dialogue'))


def test_legacy_compactor_leaves_v4_grammar_unchanged(budget):
    from dfm12.multilingual_quarantine_pilot import compact_request
    payload = generation.request(spec())
    transport, cpu_schema = compact_request(payload)
    assert transport == payload and cpu_schema is None
    # New caller MUST run v4 decode/assemble; no schema is smuggled to the API.
    assert generation.schema(spec())['additionalProperties'] is False


def test_real_teacher_template_prompt_budget():
    payload = generation.request(spec('math-code'))
    assert generation.measure_prompt(payload) + payload['max_tokens'] <= 8192


def test_verified_endpoint_context_is_minimum_of_entire_pool(budget):
    from dfm12.multilingual_tasks import MODEL
    document = lambda n: {'data': [dict(id=MODEL, max_model_len=n)]}
    assert generation.context_limit() == 8192
    assert generation.context_limit([document(16384), document(32768)]) == 16384
    assert generation.context_limit([document(16384), document(8192)]) == 8192
    generation.request(spec('math-code'), endpoint_models=document(16384))
    for docs in ([], document(True), document(4096), {'data': []},
                 {'data': [dict(id='wrong', max_model_len=16384)]}):
        with pytest.raises(generation.GenerationFailure, match='endpoint_context_unverified'):
            generation.context_limit(docs)


def test_context_preflight_uses_16k_only_when_explicitly_verified(monkeypatch):
    from types import SimpleNamespace
    from dfm12.multilingual_tasks import MODEL
    tokenizer = SimpleNamespace(apply_chat_template=lambda *a, **kw: [1] * 5000)
    monkeypatch.setattr(generation, '_prompt_budget', lambda: SimpleNamespace(tokenizer=tokenizer))
    with pytest.raises(generation.GenerationFailure, match='teacher_context_budget'):
        generation.request(spec('math-code'))
    generation.request(spec('math-code'), endpoint_models={'data': [dict(id=MODEL, max_model_len=16384)]})


def test_actual_teacher_tokenizer_grammar_eos_and_escaped_box():
    import xgrammar as xg
    tokenizer = generation._prompt_budget().tokenizer
    stop = tokenizer.convert_tokens_to_ids('<turn|>')
    info = xg.TokenizerInfo.from_huggingface(tokenizer, stop_token_ids=[stop])
    compiler = xg.GrammarCompiler(info, max_threads=1)
    compiled = compiler.compile_grammar(xg.Grammar.from_ebnf(generation.grammar(spec())))
    machine = xg.GrammarMatcher(compiled)
    raw = json.dumps(dict(user='Return \\boxed{12}.', assistant='Quote "tolv".\nAnswer: 12.'),
                     ensure_ascii=False, separators=(',', ':'))
    assert machine.accept_string(raw[:-1])
    assert not machine.accept_token(stop)
    assert machine.accept_string('}')
    assert machine.accept_token(stop)
    assert machine.is_terminated()
    machine = xg.GrammarMatcher(compiled)
    for token in tokenizer.encode(raw, add_special_tokens=False):
        assert machine.accept_token(token)
    assert machine.is_completed()
    assert machine.accept_token(stop)


def test_actual_student_template_preserves_every_assistant_boundary(renderer):
    from scripts.tokenize_chat_template import examples_from_messages, render, tokenize_example
    case = spec('multiturn')
    row = generation.assemble(case, dict(turns=[
        dict(user='Hvor mange bøker?', assistant='Det finnes 12 bøker.'),
        dict(user='Gjenta antallet.', assistant='Antallet er 12.')]))
    examples = list(examples_from_messages(row['messages'], []))
    assert len(examples) == 2
    for example in examples:
        prefix, target = tokenize_example(renderer.tokenizer, renderer.template, example, False)
        text = render(renderer.template, example.prompt_messages + [example.assistant_message], [], False, False)
        assert renderer.tokenizer.encode(text, add_special_tokens=False).ids == prefix + target
        assert len(prefix) + len(target) <= 4096
    assert examples[-1].prompt_messages == row['messages'][:-1]
