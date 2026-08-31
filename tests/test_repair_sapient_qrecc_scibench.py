from scripts.repair_sapient_qrecc_scibench import dialogue_context, extract_supplied_answer, qrecc_task


def test_extracts_zero_shot_answer() -> None:
    instruction = "Imagine the conversation that came before this response? Response: In 1956, Johnny Unitas joined the Baltimore Colts."
    assert extract_supplied_answer(instruction) == "In 1956, Johnny Unitas joined the Baltimore Colts."


def test_extracts_last_few_shot_problem() -> None:
    instruction = "Example: Response: wrong\n\nInput: What came before. To combat this, she developed a citizen network.\nSolution:"
    assert extract_supplied_answer(instruction) == "To combat this, she developed a citizen network."


def test_extracts_dialogue_context_without_open_answer_marker() -> None:
    assert dialogue_context("DIALOG:\nWhy is the sky blue?\n-") == "DIALOG:\nWhy is the sky blue?"


def test_rejects_missing_few_shot_answer() -> None:
    instruction = "See the last examples. Predict the preceding dialog. DIALOG:\nWhy?\n-\nPreceding conversation:"
    assert extract_supplied_answer(instruction) is None


def test_qrecc_answer_and_next_question_modes() -> None:
    answer = qrecc_task("DIALOG:\nWhere is Winchester?", "Virginia")
    assert answer and answer[0] == "answer" and answer[2] == "Virginia"
    question = qrecc_task("DIALOG:\nWhere?\n- In Virginia.", "What city is it in?")
    assert question and question[0] == "next_question"
