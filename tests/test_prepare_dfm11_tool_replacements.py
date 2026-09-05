from scripts.prepare_dfm7_special_sources import (
    glaive_native_tool_row,
    parse_toolace_tool_calls,
    toolace_native_tool_row,
)
from scripts.prepare_dfm11_tool_replacements import canonicalize_native_row


def test_glaive_assigns_unique_call_ids_and_pairs_results():
    row = {
        "system": 'SYSTEM: {"name":"lookup","parameters":{"type":"object","properties":{}}}',
        "chat": (
            'USER: First\nASSISTANT: <functioncall> {"name":"lookup","arguments":{}}\n'
            'FUNCTION RESPONSE: {"value":1}\nASSISTANT: Again\n'
            'USER: Second\nASSISTANT: <functioncall> {"name":"lookup","arguments":{}}\n'
            'FUNCTION RESPONSE: {"value":2}\nASSISTANT: Done'
        ),
    }
    converted = glaive_native_tool_row(row)
    assert converted is not None
    calls = [message["tool_calls"][0] for message in converted["messages"] if message.get("tool_calls")]
    results = [message for message in converted["messages"] if message["role"] == "tool"]
    assert [call["id"] for call in calls] == ["call_0", "call_1"]
    assert [result["tool_call_id"] for result in results] == ["call_0", "call_1"]


def test_toolace_parses_declared_names_containing_parentheses():
    calls = parse_toolace_tool_calls(
        '[Directional Movement Index (DX)(symbol="Tesla", interval="1day")]',
        tool_name_map={"Directional Movement Index (DX)": "Directional_Movement_Index_DX"},
    )
    assert calls == [{
        "type": "function",
        "id": "call_0",
        "function": {
            "name": "Directional_Movement_Index_DX",
            "arguments": {"symbol": "Tesla", "interval": "1day"},
        },
    }]


def test_toolace_splits_parallel_results_and_pairs_ids():
    system = (
        'Functions: [{"name":"one","parameters":{"type":"object","properties":{}}},'
        '{"name":"two","parameters":{"type":"object","properties":{}}}]'
    )
    row = {
        "system": system,
        "conversations": [
            {"from": "user", "value": "Use both."},
            {"from": "assistant", "value": "[one(), two()]"},
            {"from": "tool", "value": '[{"name":"one","results":{"x":1}}, {"name":"two","results":{"y":2}}]'},
            {"from": "assistant", "value": "Done."},
        ],
    }
    converted = toolace_native_tool_row(row)
    assert converted is not None
    assistant = converted["messages"][2]
    results = converted["messages"][3:5]
    assert [call["id"] for call in assistant["tool_calls"]] == ["call_0", "call_1"]
    assert [result["tool_call_id"] for result in results] == ["call_0", "call_1"]
    assert [result["content"] for result in results] == ['{"x": 1}', '{"y": 2}']


def test_toolace_rejects_ambiguous_result_count():
    row = {
        "system": 'Functions: [{"name":"one","parameters":{"type":"object","properties":{}}},'
                  '{"name":"two","parameters":{"type":"object","properties":{}}}]',
        "conversations": [
            {"from": "user", "value": "Use both."},
            {"from": "assistant", "value": "[one(), two()]"},
            {"from": "tool", "value": '[{"name":"one","results":{"x":1}}]'},
        ],
    }
    assert toolace_native_tool_row(row) is None


def test_native_canonicalizer_materializes_string_arguments_and_ids():
    converted = canonicalize_native_row({
        "tools": [{"type": "function", "function": {
            "name": "lookup", "parameters": {"type": "object", "properties": {}}
        }}],
        "messages": [
            {"role": "user", "content": "Look it up."},
            {"role": "assistant", "content": None, "tool_calls": [{
                "id": "upstream-id", "type": "function",
                "function": {"name": "lookup", "arguments": '{"q":"x"}'},
            }]},
            {"role": "tool", "tool_call_id": "upstream-id", "content": '{"answer":1}'},
            {"role": "assistant", "content": "The answer is 1."},
        ],
    })
    assert converted is not None
    call = converted["messages"][1]["tool_calls"][0]
    assert call["id"] == "call_0"
    assert call["function"]["arguments"] == {"q": "x"}
    assert converted["messages"][2]["tool_call_id"] == "call_0"
