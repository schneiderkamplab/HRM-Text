from scripts.repair_scientific_summaries import clean_text, is_complete_text, make_instruction


def test_completion_rejects_mid_sentence_and_ellipsis() -> None:
    assert not is_complete_text("This is a sufficiently long target that ends with and", 20)
    assert not is_complete_text("This is a sufficiently long target that trails off...", 20)
    assert is_complete_text("This is a sufficiently long and complete scientific statement.", 20)


def test_instruction_describes_grounded_contract() -> None:
    instruction = make_instruction("A paper", [("Key results", "The result is complete.")])
    assert "using only" in instruction
    assert "Title: A paper" in instruction
    assert "Key results:" in instruction


def test_clean_text_preserves_paragraphs_but_normalizes_spaces() -> None:
    assert clean_text(" A   line\n\n\n B\tline ") == "A line\n\nB line"
