import pytest

from scripts.review_dfm13_arena_candidates import parse_numpy_repr, messages


def test_numpy_history_preserves_strings_and_text():
    raw = "[{'role': 'user', 'content': array([{'type': 'text', 'text': 'a } { b'}], dtype=object)} {'role': 'assistant', 'content': 'ok'}]"
    assert messages(parse_numpy_repr(raw)) == [
        {'role': 'user', 'content': 'a } { b'},
        {'role': 'assistant', 'content': 'ok'},
    ]


@pytest.mark.parametrize('raw', [
    "__import__('os').system('echo unsafe')",
    "[{'role': 'user'}, ...]",
    "array([1], dtype=int)",
    "[x for x in [1]]",
])
def test_rejects_code_and_truncation(raw):
    with pytest.raises(ValueError):
        parse_numpy_repr(raw)


def test_rejects_nontext():
    with pytest.raises(ValueError):
        messages([{'role': 'user', 'content': [{'type': 'image', 'image': 'x'}]}])
