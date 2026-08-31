from __future__ import annotations

import pytest

from scripts.tokenize_chat_template import examples_from_messages


MESSAGES = [
    {"role": "user", "content": "Fix the issue."},
    {"role": "assistant", "content": "I will inspect it."},
    {"role": "tool", "content": "result", "name": "shell", "tool_call_id": "call_0"},
    {"role": "assistant", "content": "The fix is complete."},
]


def test_messages_default_to_every_assistant_target() -> None:
    examples = list(examples_from_messages(MESSAGES))
    assert [example.response for example in examples] == ["I will inspect it.", "The fix is complete."]


def test_messages_can_select_one_assistant_target() -> None:
    examples = list(examples_from_messages(MESSAGES, target_message_index=3))
    assert len(examples) == 1
    assert examples[0].response == "The fix is complete."
    assert [message["role"] for message in examples[0].prompt_messages] == ["user", "assistant", "tool"]


def test_target_message_index_must_be_in_range() -> None:
    with pytest.raises(ValueError, match="outside"):
        list(examples_from_messages(MESSAGES, target_message_index=9))
