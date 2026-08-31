from __future__ import annotations

from scripts.repair_nemotron_swe_sources import (
    AGENTLESS_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    clean_assistant_content,
    clean_issue_prompt,
    normalize_agentless_target,
    normalize_target,
    normalize_tool_result,
    valid_executable_call,
)


def call_message(name: str, arguments: dict, call_id: str = "call_1") -> dict:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}],
    }


def test_clean_issue_prompt_removes_phase_boilerplate() -> None:
    raw = """<uploaded_files>\n/workspace/repo\n</uploaded_files>\n<issue_description>\nFix the parser.\n</issue_description>\nFollow these phases to resolve the issue:\nPhase 1..."""
    cleaned = clean_issue_prompt(raw)
    assert cleaned is not None
    assert "Repository: /workspace/repo" in cleaned
    assert "Fix the parser." in cleaned
    assert "Phase 1" not in cleaned


def test_finish_becomes_normal_assistant_answer() -> None:
    kind, target = normalize_target(call_message("finish", {"message": "Implemented and tested."}))
    assert kind == "finish"
    assert target == {"role": "assistant", "content": "Implemented and tested."}


def test_think_cycle_is_removed() -> None:
    kind, target = normalize_target(call_message("think", {"thought": "private reasoning"}))
    assert kind == "think"
    assert target is None


def test_editor_call_requires_command_specific_fields() -> None:
    assert valid_executable_call("str_replace_editor", {"command": "view", "path": "/workspace/a.py"})
    assert valid_executable_call("str_replace_editor", {"command": "undo_edit", "path": "/workspace/a.py"})
    assert not valid_executable_call("str_replace_editor", {"command": "str_replace", "path": "/workspace/a.py"})


def test_obsolete_phase_heading_is_removed_without_removing_body() -> None:
    content = "## Phase 3. EXPLORATION: Find the code\nI will inspect parser.py."
    assert clean_assistant_content(content) == "I will inspect parser.py."


def test_ordinary_numbered_heading_is_preserved() -> None:
    content = "### 1.1 Code Analysis\nInspect the parser implementation."
    assert clean_assistant_content(content) == content


def test_tool_result_must_match_call_id_and_name() -> None:
    _, target = normalize_target(call_message("execute_bash", {"command": "pytest"}))
    assert target is not None
    call = target["tool_calls"][0]
    good = {"role": "tool", "name": "execute_bash", "tool_call_id": "call_1", "content": "ok"}
    bad = good | {"tool_call_id": "other"}
    assert normalize_tool_result(good, call) is not None
    assert normalize_tool_result(bad, call) is None


def test_agentless_prompt_defers_to_each_explicit_software_task() -> None:
    assert "Follow the user's requested task" in AGENTLESS_SYSTEM_PROMPT
    assert "analysis, file list, test, patch guidance" in AGENTLESS_SYSTEM_PROMPT
    assert "Do not claim to have inspected or changed" in AGENTLESS_SYSTEM_PROMPT
    assert "make minimal and correct source changes" in SYSTEM_PROMPT
    assert AGENTLESS_SYSTEM_PROMPT != SYSTEM_PROMPT


def test_agentless_target_drops_hidden_reasoning_metadata() -> None:
    source = {
        "role": "assistant",
        "content": "A complete requested test.",
        "reasoning_content": "private scratch work",
    }
    assert normalize_agentless_target(source) == {
        "role": "assistant",
        "content": "A complete requested test.",
    }
