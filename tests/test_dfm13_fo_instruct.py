import pytest

from scripts.prepare_dfm13_fo_instruct import convert
from dfm12.fo_instruct_assembly import unready
from scripts.assemble_dfm13_additions import unready_reason


def test_preserves_source_text_and_native_target():
    row = {'instruction': '  Question?\n', 'output': 'Answer.\n', 'contributor_id': 'one'}
    converted = convert(row, 3)
    assert converted['messages'] == [
        {'role': 'user', 'content': row['instruction']},
        {'role': 'assistant', 'content': row['output']}]
    assert converted['target_message_index'] == 1
    assert converted['chat_template_kwargs'] == {'enable_thinking': False}
    assert converted['metadata']['contributor_id'] == 'one'


@pytest.mark.parametrize('value', ['', '  ', None, 123])
def test_reject_empty_or_nontext(value):
    with pytest.raises(ValueError):
        convert({'instruction': value, 'output': 'Answer'}, 0)


def test_explicit_repeat_contract():
    entry = dict(name='setur_fo_instruct', repeat=10, status='source_native_tokenized',
                 tokenization_performed=True, publication_contract='setur-fo-instruct-native-v1')
    assert unready_reason(entry) is None
    assert unready(dict(entry, repeat=1))
