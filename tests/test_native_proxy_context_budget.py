import pytest

from scripts.native_compatible_openai_proxy import fit_native_prompt


class Tokenizer:
    def encode(self, text, **kwargs):
        return list(text)

    def decode(self, tokens, **kwargs):
        return ''.join(tokens)

    def apply_chat_template(self, messages, **kwargs):
        assert kwargs['tokenize'] is False
        return 'BU' + messages[0]['content'] + 'EM'


def payload(text, output=20):
    return {'messages': [{'role': 'user', 'content': text}], 'max_tokens': output}


def test_fitting_prompt_unchanged():
    original = payload('short')
    result, receipt = fit_native_prompt(original, Tokenizer(), 'template', 100)
    assert result is original
    assert receipt is None


def test_exact_boundary_and_one_over():
    original = payload('a' * 76)
    assert fit_native_prompt(original, Tokenizer(), '', 100)[1] is None
    result, receipt = fit_native_prompt(payload('a' * 77), Tokenizer(), '', 100)
    assert receipt['retained_prompt_tokens'] + result['max_tokens'] <= 100


def test_long_input_keeps_head_tail_template_and_output_budget():
    original = payload('INSTRUCTION ' + 'x' * 1000 + ' FINAL QUESTION')
    result, receipt = fit_native_prompt(original, Tokenizer(), '', 100)
    assert result['messages'][0]['content'].startswith('INSTRUCTION')
    assert result['messages'][0]['content'].endswith('FINAL QUESTION')
    assert result['max_tokens'] == original['max_tokens']
    assert receipt['original_prompt_tokens'] > receipt['retained_prompt_tokens']
    assert len(original['messages'][0]['content']) > 1000


@pytest.mark.parametrize('output', [None, 0, -1, 100, 101])
def test_invalid_budgets_rejected(output):
    with pytest.raises(ValueError):
        fit_native_prompt(payload('text', output), Tokenizer(), '', 100)


def test_oversize_tools_not_silently_truncated():
    original = {**payload('x' * 1000), 'tools': [{'function': {'name': 'test'}}]}
    with pytest.raises(ValueError):
        fit_native_prompt(original, Tokenizer(), '', 100)
