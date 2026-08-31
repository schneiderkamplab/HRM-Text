from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "answer_contract", ROOT / "scripts/build_mimir_answer_contract_calibration.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def source_row() -> dict:
    return {
        "row_id": "source-1",
        "messages": [
            {
                "role": "user",
                "content": "Which value is even?\nA. 3\nB. 4\nC. 5\nD. 7\nAnswer with exactly one option letter.",
            },
            {"role": "assistant", "content": "B"},
        ],
        "generation": {"rationale": "Four is divisible by two."},
        "provenance": {"dataset": "fixture"},
        "quality_audit": {"scores": {"keep": True}},
    }


def test_selection_contract_variants_validate() -> None:
    source = source_row()
    for index in range(5):
        row = MODULE.selection_row(source, index)
        assert MODULE.expected_response(row) == row["messages"][1]["content"]


def test_binary_contract_balances_truth_value() -> None:
    source = source_row()
    assert MODULE.binary_row(source, 0)["messages"][1]["content"] == "Yes"
    assert MODULE.binary_row(source, 1)["messages"][1]["content"] == "false"


def test_reason_and_json_contracts_validate() -> None:
    source = source_row()
    reason = MODULE.reason_final_row(source, 0)
    structured = MODULE.structured_row(source, 0)
    assert reason["messages"][1]["content"].endswith("ANSWER: B")
    assert structured["messages"][1]["content"] == '{"answer":"B"}'
    MODULE.expected_response(reason)
    MODULE.expected_response(structured)


def test_parse_mcq_collapses_exact_repeated_option_block() -> None:
    source = source_row()
    instruction = source["messages"][0]["content"]
    suffix = "\nAnswer with exactly one option letter."
    body = instruction.removesuffix(suffix)
    question, option_block = body.split("\n", 1)
    source["messages"][0]["content"] = f"{question}\n{option_block}\n{option_block}{suffix}"
    parsed_question, options, answer = MODULE.parse_mcq(source)
    assert parsed_question == question
    assert options == [("A", "3"), ("B", "4"), ("C", "5"), ("D", "7")]
    assert answer == "B"
