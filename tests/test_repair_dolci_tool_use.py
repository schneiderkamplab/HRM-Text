from pathlib import Path

import jinja2

from scripts.repair_dolci_tool_use import (
    parse_concatenated_values,
    repaired_dolci_row,
    validate_call_arguments,
)


TOOLS = '[{"type":"function","function":{"name":"weather","description":"Weather","parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}}]'


def row(messages):
    return {
        "id": "example-1",
        "messages": [
            {"role": "system", "content": "Use <functions></functions> XML tags.", "functions": TOOLS},
            *messages,
        ],
    }


def test_parse_concatenated_values_preserves_parallel_results() -> None:
    assert parse_concatenated_values('{"a":1}\n{"b":2}') == [{"a": 1}, {"b": 2}]


def test_repair_preserves_tool_result_and_unique_call_id() -> None:
    repaired, disposition = repaired_dolci_row(
        row(
            [
                {"role": "user", "content": "Weather in Rome?"},
                {"role": "assistant", "content": None, "function_calls": "weather(city='Rome')"},
                {"role": "environment", "content": '{"temperature":21}'},
                {"role": "assistant", "content": "It is 21 degrees."},
            ]
        )
    )
    assert disposition == "accepted"
    assert repaired is not None
    assert [message["role"] for message in repaired["messages"]] == [
        "system",
        "user",
        "assistant",
        "tool",
        "assistant",
    ]
    call = repaired["messages"][2]["tool_calls"][0]
    assert call["id"] == "call_0"
    assert repaired["messages"][3]["tool_call_id"] == "call_0"


def test_top_level_list_tool_result_is_serialized_for_template() -> None:
    repaired, disposition = repaired_dolci_row(
        row(
            [
                {"role": "user", "content": "Weather in Rome?"},
                {"role": "assistant", "content": None, "function_calls": "weather(city='Rome')"},
                {"role": "environment", "content": '[{"temperature":21}]'},
                {"role": "assistant", "content": "It is 21 degrees."},
            ]
        )
    )
    assert disposition == "accepted"
    assert repaired is not None
    assert repaired["messages"][3]["content"] == '[{"temperature":21}]'


def test_gemma_template_renders_mapping_tool_result() -> None:
    repaired, disposition = repaired_dolci_row(
        row(
            [
                {"role": "user", "content": "Weather in Rome?"},
                {"role": "assistant", "content": None, "function_calls": "weather(city='Rome')"},
                {"role": "environment", "content": '{"temperature":21}'},
                {"role": "assistant", "content": "It is 21 degrees."},
            ]
        )
    )
    assert disposition == "accepted" and repaired is not None
    template = jinja2.Environment().from_string(
        Path("data_io/chat_templates/gemma4_native_chat.jinja").read_text()
    )
    rendered = template.render(
        messages=repaired["messages"],
        tools=repaired["tools"],
        add_generation_prompt=False,
        enable_thinking=False,
        bos_token="<bos>",
        eos_token="<eos>",
    )
    assert "response:weather{temperature:21}" in rendered


def test_repair_rejects_missing_tool_result() -> None:
    repaired, disposition = repaired_dolci_row(
        row(
            [
                {"role": "user", "content": "Weather in Rome?"},
                {"role": "assistant", "content": None, "function_calls": "weather(city='Rome')"},
            ]
        )
    )
    assert repaired is None
    assert disposition == "missing_tool_response"


def test_repair_rejects_undeclared_call() -> None:
    repaired, disposition = repaired_dolci_row(
        row(
            [
                {"role": "user", "content": "Weather in Rome?"},
                {"role": "assistant", "content": None, "function_calls": "other(city='Rome')"},
                {"role": "environment", "content": '{"temperature":21}'},
            ]
        )
    )
    assert repaired is None
    assert disposition == "undeclared_tool"


def test_required_argument_validation() -> None:
    function = {
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        }
    }
    assert validate_call_arguments({}, function) == "missing_required_argument"
    assert validate_call_arguments({"city": "Rome"}, function) is None


def test_repair_rejects_consecutive_assistant_messages() -> None:
    repaired, disposition = repaired_dolci_row(
        row(
            [
                {"role": "user", "content": "Weather in Rome?"},
                {"role": "assistant", "content": "I will check."},
                {"role": "assistant", "content": "It is warm."},
            ]
        )
    )
    assert repaired is None
    assert disposition == "invalid_assistant_sequence"
