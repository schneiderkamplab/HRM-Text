import json

from scripts.mimir_benchmark_campaigns import (
    canonicalize_ifeval_response,
    execute_program,
    render_and_check,
    verify_constraints,
)


def test_ifeval_constraints_accept_and_reject_exactly() -> None:
    constraints = [
        {"type": "required_word", "value": "evidence"},
        {"type": "forbidden_word", "value": "clearly"},
        {"type": "prefix", "value": "Assessment:"},
        {"type": "suffix", "value": "[END]"},
    ]
    valid = "Assessment: The evidence supports a limited conclusion. [END]"
    assert all(verify_constraints(valid, constraints).values())
    invalid = "Assessment: Clearly, the claim is limited. [END]"
    assert not all(verify_constraints(invalid, constraints).values())


def test_ifeval_canonicalizes_requested_markdown_headings_and_json_fence() -> None:
    sections = [{"type": "exact_sections", "values": ["Summary", "Implication"]}]
    assert canonicalize_ifeval_response("## Summary\nOne.\n## Implication\nTwo.", sections) == (
        "Summary:\nOne.\nImplication:\nTwo."
    )
    keys = [{"type": "json_keys", "values": ["claim", "support", "scope"]}]
    assert canonicalize_ifeval_response('```json\n{"claim":"x","support":"y","scope":"z"}\n```', keys).startswith("{")


def test_ifeval_serializes_teacher_json_object_as_exact_payload() -> None:
    request = {
        "campaign": "ifeval_verifier",
        "task_variant": "json_schema",
        "constraints": [{"type": "json_keys", "values": ["claim", "support", "scope"]}],
    }
    value = {
        "instruction": "Summarize the supported claim as structured data.",
        "response": {"claim": "x", "support": "y", "scope": "z"},
        "verification": "The response uses only the three requested keys in their requested order.",
    }
    examples, checks = render_and_check(request, value)
    assert all(checks.values())
    assert json.loads(examples[0]["response"])["claim"] == "x"


def test_drop_program_is_executable_and_grounded() -> None:
    assert execute_program("addition", ["12", "8"]) == "20"
    request = {
        "campaign": "drop_reasoning",
        "task_variant": "addition",
        "operation": "addition",
        "grounding_passage": "The first group had 12 members and the second had 8 members.",
    }
    value = {
        "question": "How many members were in the two groups altogether?",
        "answer": "20",
        "program": {"operation": "addition", "operands": ["12", "8"]},
        "explanation": "Adding the two explicitly stated group sizes gives the total.",
    }
    _, checks = render_and_check(request, value)
    assert all(checks.values())


def test_drop_renders_verified_numeric_result_without_units() -> None:
    request = {
        "campaign": "drop_reasoning",
        "task_variant": "addition",
        "operation": "addition",
        "grounding_passage": "There were 12 red items and 8 blue items.",
    }
    value = {
        "question": "How many red and blue items were there in total?",
        "answer": "20 items",
        "program": {"operation": "addition", "operands": ["12", "8"]},
        "verification": "The two explicit counts are added to obtain the total.",
    }
    examples, checks = render_and_check(request, value)
    assert all(checks.values())
    assert examples[0]["response"] == "20"


def test_coreference_pair_requires_invariant_answer_and_swapped_positions() -> None:
    request = {
        "campaign": "event_coreference",
        "task_variant": "coreference_swap_pair",
        "correct_position": 0,
        "swapped_position": 2,
    }
    value = {
        "shared_correct_answer": "Anna",
        "examples": [
            {
                "context": "Anna thanked Bea because she had helped.",
                "question": "Who had helped?",
                "options": ["Anna", "Bea", "Clara", "Dana"],
                "correct_index": 0,
            },
            {
                "context": "Roles were swapped in the controlled scenario.",
                "question": "Who had helped?",
                "options": ["Bea", "Clara", "Anna", "Dana"],
                "correct_index": 2,
            },
        ],
        "rationale": "The controlled swap changes option position while retaining the intended answer text.",
    }
    _, checks = render_and_check(request, value)
    assert all(checks.values())


def test_coreference_pair_repositions_teacher_answer_deterministically() -> None:
    request = {
        "campaign": "event_coreference",
        "task_variant": "role_reversal_pair",
        "correct_position": 1,
        "swapped_position": 3,
    }
    value = {
        "shared_correct_answer": "Anna",
        "examples": [
            {"context": "A context.", "question": "Who acted?", "options": ["Anna", "Bea", "Clara", "Dana"], "correct_index": 0},
            {"context": "A swapped context.", "question": "Who acted?", "options": ["Bea", "Anna", "Clara", "Dana"], "correct_index": 1},
        ],
        "verification": "The answer text is unchanged while its balanced option position changes.",
    }
    examples, checks = render_and_check(request, value)
    assert all(checks.values())
    assert [row["correct_index"] for row in examples] == [1, 3]
