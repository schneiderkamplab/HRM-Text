import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from scripts import evaluate_dfm12_identity_continuation as evaluation
from scripts.smoke_dfm12_identity import QUESTIONS


def case():
    return {'id': 'test', 'suite': 'heldout', 'language': 'en',
            'users': ['Name?', 'Who trained you?'], 'expected_targets': ['GOLD FIRST', 'GOLD SECOND'],
            'requests': [['name'], ['creator']]}


def generated(text):
    return {'response': text, 'finish_reason': 'eos', 'truncated': False, 'generated_token_count': 4}


def test_model_generated_history_not_gold_and_reset():
    prompts = []
    def generate(messages):
        prompts.append(messages)
        return generated('MODEL ' + str(len(prompts)))
    first = evaluation.run_conversation(case(), generate)
    assert prompts[1] == [{'role': 'user', 'content': 'Name?'},
                          {'role': 'assistant', 'content': 'MODEL 1'},
                          {'role': 'user', 'content': 'Who trained you?'}]
    assert 'GOLD' not in json.dumps(prompts)
    assert first['turns'][0]['expected_target'] == 'GOLD FIRST'
    evaluation.run_conversation(case(), generate)
    assert prompts[2] == [{'role': 'user', 'content': 'Name?'}]


def test_timeout_preserves_completed_turn_and_never_approves():
    partial = {'id': 'test', 'suite': 'heldout', 'language': 'en', 'turns': [],
               'generated_history': [], 'status': 'incomplete'}
    saved = []
    def generate(messages):
        if len(messages) > 1:
            raise evaluation.EvaluationBudgetExceeded('budget')
        return generated('MODEL')
    with pytest.raises(evaluation.EvaluationBudgetExceeded):
        evaluation.run_conversation(case(), generate, partial, lambda: saved.append(len(partial['turns'])))
    assert saved == [1] and len(partial['turns']) == 1
    report = {'status': 'incomplete_budget', 'cases': [case()],
              'runs': [{'label': 'previous', 'conversations': [partial]}]}
    summary = evaluation.summarize(report)
    assert summary['identity_positive'] is None
    assert 'parent review' in summary['full_suite_gate']
    assert summary['expected_turns_per_checkpoint'] == 2


def test_heuristics_are_not_exact_match_or_truth_judges():
    expected = 'I am Mimir.'
    result = evaluation.heuristic('My name is Mimir, a language model.', expected)
    assert result['anchor_recall'] == 1
    assert result['semantic_correctness'] == 'not_assessed'
    assert evaluation.heuristic('I am not Mimir.', expected)['anchor_recall'] == 1
    wrong = evaluation.heuristic('Google trained me. Kristoffer Nielbo leads my training team. '
                                'Both versions always used full backpropagation.',
                                'Peter Schneider-Kamp; historical v1 uses 5 steps.', ['members', 'bp_contrast'])
    assert len(wrong['review_flags']) == 4
    assert evaluation.heuristic('No tools.', 'No tools.')['anchor_recall'] is None


class Tokenizer:
    def apply_chat_template(self, messages, **kwargs):
        assert kwargs == dict(tokenize=False, add_generation_prompt=True, enable_thinking=False)
        return json.dumps(messages)
    def encode(self, text, **kwargs):
        assert kwargs == {'add_special_tokens': False}
        return list(text.encode())


def test_context_overflow_rejected_not_truncated():
    with pytest.raises(ValueError, match='no truncation'):
        evaluation.render_prompt(Tokenizer(), [{'role': 'user', 'content': 'x' * 100}], 150, 100)
    with pytest.raises(ValueError, match='unprimed'):
        evaluation.render_prompt(Tokenizer(), [{'role': 'system', 'content': 'facts'},
                                              {'role': 'user', 'content': 'Name?'}], 4096, 512)


@pytest.mark.parametrize('stop', ['eos', 'length'])
def test_generation_adapter_uses_raw_ids_and_tracks_stop(monkeypatch, stop):
    checkpoint = SimpleNamespace(model=object(), carry=None, tokenizer=Tokenizer(),
                                 stop_token_id=lambda: 2, decode_generation=lambda tokens, eos: 'answer')
    messages = [{'role': 'user', 'content': 'first'}, {'role': 'assistant', 'content': 'actual model'},
                {'role': 'user', 'content': 'second'}]
    def inference(adapter, iterator, context, max_new, batch, temperature):
        assert batch == 1 and temperature == 0 and context == 4096
        assert adapter.tokenize_prompt('', '').tolist() == list(json.dumps(messages).encode())
        assert list(iterator) == [(0, ('raw', ''))]
        tokens = np.array([44, 2] if stop == 'eos' else [44] * max_new)
        yield 0, adapter.decode_generation(tokens, 2)
    monkeypatch.setitem(sys.modules, 'simple_inference_engine', SimpleNamespace(inference_generate=inference))
    result = evaluation.generate_turn(checkpoint, messages, 4096, 512)
    assert result['finish_reason'] == stop
    assert result['truncated'] == (stop == 'length')
    assert result['generated_token_count'] == (2 if stop == 'eos' else 512)


def test_reports_include_pending_prompts_targets_and_no_approval(tmp_path):
    report = {'status': 'preflight', 'cases': [case()], 'runs': [
        {'label': 'previous', 'tag': 'step_1', 'checkpoint': '/old', 'conversations': []}]}
    evaluation.save(tmp_path, report)
    text = (tmp_path / 'responses.md').read_text()
    assert 'Name?' in text and 'GOLD FIRST' in text and 'not generated' in text
    summary = json.loads((tmp_path / 'summary.json').read_text())
    assert summary['identity_positive'] is None


def test_real_heldout_and_regression_contract():
    if not evaluation.DEFAULT_DATA.exists():
        pytest.skip('Local heldout artifact unavailable')
    cases, manifest = evaluation.load_cases(evaluation.DEFAULT_DATA)
    assert len(cases) == 116
    assert sum(len(c['users']) for c in cases) == 206
    assert [(c['id'], c['language'], c['users'][0]) for c in cases[:16]] == QUESTIONS
    assert all(c['language'] == ('da' if i % 2 == 0 else 'en') for i, c in enumerate(cases[16:]))
    lengths = evaluation.tokenizer_lengths(cases, manifest)
    assert lengths['da']['assistant_targets'] == lengths['en']['assistant_targets'] == 95
    assert lengths['da']['max_target_tokens'] == 182
    assert lengths['en']['max_target_tokens'] == 130


def test_gpu_occupied_fails_without_model_load(monkeypatch):
    outputs = iter(['7, 100000, 0\n', '999999\n'])
    monkeypatch.setattr(evaluation.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout=next(outputs)))
    with pytest.raises(RuntimeError, match='refusing to compete'):
        evaluation.gpu_status()
