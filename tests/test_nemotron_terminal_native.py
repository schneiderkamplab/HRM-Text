from pathlib import Path

import jinja2
import pyarrow as pa
import pyarrow.parquet as pq

from scripts.prepare_nemotron_terminal_native import convert_file
from scripts.tokenize_chat_template import (
    examples_from_messages,
    read_parquet,
    tokenize_example,
)


class CharacterTokenizer:
    class Encoding:
        def __init__(self, text: str) -> None:
            self.ids = [ord(char) for char in text]

    def encode(self, text: str, add_special_tokens: bool = False) -> "CharacterTokenizer.Encoding":
        return self.Encoding(text)


def test_native_conversion_defers_assistant_expansion_to_tokenizer(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source = source_root / "skill_based" / "data_filtered.parquet"
    source.parent.mkdir(parents=True)
    messages = [
        {"role": "system", "content": "Use the terminal carefully."},
        {"role": "user", "content": "List the directory."},
        {"role": "assistant", "content": '{"commands":[{"keystrokes":"ls\\n"}]}'},
        {"role": "user", "content": "Now show hidden files."},
        {"role": "assistant", "content": '{"commands":[{"keystrokes":"ls -la\\n"}]}'},
    ]
    schema = pa.schema(
        [
            (
                "conversations",
                pa.list_(pa.struct([("content", pa.string()), ("role", pa.string())])),
            ),
            ("model", pa.string()),
        ]
    )
    pq.write_table(
        pa.Table.from_pylist([{"conversations": messages, "model": "teacher"}], schema=schema),
        source,
    )

    output_root = tmp_path / "converted"
    result = convert_file(source, source_root, output_root)
    output = output_root / result["output_file"]
    rows = pq.read_table(output).to_pylist()

    assert result["rows"] == 1
    assert result["assistant_turns"] == 2
    assert len(rows) == 1
    assert [message["role"] for message in rows[0]["messages"]] == [
        "system",
        "user",
        "assistant",
        "user",
        "assistant",
    ]

    examples = list(examples_from_messages(rows[0]["messages"]))
    assert len(examples) == 2
    assert [message["role"] for message in examples[1].prompt_messages] == [
        "system",
        "user",
        "assistant",
        "user",
    ]


def test_context_limit_removes_only_complete_old_turns() -> None:
    messages = [
        {"role": "system", "content": "terminal"},
        {"role": "user", "content": "old question " * 10},
        {"role": "assistant", "content": "old answer " * 10},
        {"role": "user", "content": "new question"},
        {"role": "assistant", "content": "new answer"},
    ]
    example = list(examples_from_messages(messages))[-1]
    template = jinja2.Environment().from_string(
        "{% for message in messages %}[{{ message.role }}]{{ message.content }}{% endfor %}"
        "{% if add_generation_prompt %}[assistant]{% endif %}"
    )
    encoded = tokenize_example(
        CharacterTokenizer(),
        template,
        example,
        enable_thinking=False,
        max_seq_len=80,
    )

    assert encoded is not None
    prompt_ids, response_ids = encoded
    prompt = "".join(chr(token) for token in prompt_ids)
    assert "[system]terminal" in prompt
    assert "[user]new question" in prompt
    assert "old question" not in prompt
    assert "old answer" not in prompt
    assert len(prompt_ids) + len(response_ids) <= 80


def test_context_limit_keeps_user_request_and_recent_tool_cycles() -> None:
    messages = [
        {"role": "user", "content": "research the topic"},
        {"role": "assistant", "content": "old call " * 10},
        {"role": "tool", "content": "old result " * 10},
        {"role": "assistant", "content": "recent call"},
        {"role": "tool", "content": "recent result"},
        {"role": "assistant", "content": "final answer"},
    ]
    example = list(examples_from_messages(messages))[-1]
    template = jinja2.Environment().from_string(
        "{% for message in messages %}[{{ message.role }}]{{ message.content }}{% endfor %}"
        "{% if add_generation_prompt %}[assistant]{% endif %}"
    )
    encoded = tokenize_example(
        CharacterTokenizer(),
        template,
        example,
        enable_thinking=False,
        max_seq_len=125,
    )

    assert encoded is not None
    prompt_ids, response_ids = encoded
    prompt = "".join(chr(token) for token in prompt_ids)
    assert "[user]research the topic" in prompt
    assert "[assistant]recent call" in prompt
    assert "[tool]recent result" in prompt
    assert "old call" not in prompt
    assert "old result" not in prompt
    assert len(prompt_ids) + len(response_ids) <= 125


def test_terminal_window_pins_first_user_request() -> None:
    messages = [
        {"role": "user", "content": "fix the package"},
        {"role": "assistant", "content": "old command " * 10},
        {"role": "user", "content": "New Terminal Output: failed"},
        {"role": "assistant", "content": "retry command"},
    ]
    example = list(examples_from_messages(messages))[-1]
    template = jinja2.Environment().from_string(
        "{% for message in messages %}[{{ message.role }}]{{ message.content }}{% endfor %}"
        "{% if add_generation_prompt %}[assistant]{% endif %}"
    )
    encoded = tokenize_example(
        CharacterTokenizer(),
        template,
        example,
        enable_thinking=False,
        max_seq_len=100,
        preserve_first_user=True,
    )

    assert encoded is not None
    prompt_ids, response_ids = encoded
    prompt = "".join(chr(token) for token in prompt_ids)
    assert "[user]fix the package" in prompt
    assert "[user]New Terminal Output: failed" in prompt
    assert "old command" not in prompt
    assert len(prompt_ids) + len(response_ids) <= 100


def test_nested_message_parquet_reads_across_row_groups(tmp_path: Path) -> None:
    path = tmp_path / "messages.parquet"
    message_type = pa.list_(
        pa.struct([("role", pa.string()), ("content", pa.string())])
    )
    messages = [
        [
            {"role": "user", "content": f"Question {index}"},
            {"role": "assistant", "content": f"Answer {index}"},
        ]
        for index in range(20_000)
    ]
    pq.write_table(
        pa.Table.from_arrays([pa.array(messages, type=message_type)], names=["messages"]),
        path,
        row_group_size=10_000,
    )

    examples = list(read_parquet(path))

    assert len(examples) == 20_000
    assert examples[-1].response == "Answer 19999"
