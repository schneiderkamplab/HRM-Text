from scripts.repair_code_meta_reasoning import (
    deterministic_rejection,
    make_instruction,
)


def test_restores_family_specific_task_contract() -> None:
    instruction = make_instruction("planning.txt", "Find the shortest path.", "ignored")
    assert "planning document" in instruction
    assert "Do not provide source code" in instruction
    assert instruction.endswith("Find the shortest path.")


def test_unit_test_family_keeps_required_reference_context() -> None:
    source_prompt = "Review this implementation and these tests."
    assert (
        make_instruction("code_unit_test_walkthrough.txt", "A problem", source_prompt)
        == source_prompt
    )


def test_rejects_known_unsafe_and_contaminated_rows() -> None:
    assert (
        deterministic_rejection(
            "code_quality_evaluation_low.txt", "Solve it", "bad code", "prompt"
        )
        == "unsafe_family"
    )
    assert (
        deterministic_rejection(
            "code_implement_solution.txt",
            "Write average_waiting_time.",
            "```python\ndef max_accordion_length(): pass\n```",
            "prompt",
        )
        == "contaminated_function_name"
    )


def test_rejects_missing_visual_and_incomplete_structures() -> None:
    assert (
        deterministic_rejection(
            "code_recovery.txt",
            "You are a critical reviewer. Compare the chosen and rejected responses.",
            "The chosen response is better.",
            "prompt",
        )
        == "nested_meta_task"
    )
    assert (
        deterministic_rejection(
            "planning.txt", "<image> infer the task", "A complete plan.", "prompt"
        )
        == "missing_image"
    )
    assert (
        deterministic_rejection(
            "code_implement_solution.txt", "Solve it", "Only prose.", "prompt"
        )
        == "missing_solution_code"
    )
    assert (
        deterministic_rejection(
            "code_unit_test_walkthrough.txt", "Solve it", "All tests pass.", "context"
        )
        == "missing_verdict"
    )


def test_accepts_a_well_formed_debugging_trace() -> None:
    response = "```python\nbuggy()\n```\nThen fix it.\n```python\ncorrect()\n```"
    assert (
        deterministic_rejection(
            "code_recovery_multi_turn.txt", "Solve it", response, "prompt"
        )
        is None
    )
