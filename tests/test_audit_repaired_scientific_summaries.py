import pytest

from scripts.audit_repaired_scientific_summaries import parse_judgment, stable_priority


def test_stable_priority_is_repeatable_and_row_specific() -> None:
    assert stable_priority("a.parquet", 3, 7) == stable_priority("a.parquet", 3, 7)
    assert stable_priority("a.parquet", 3, 7) != stable_priority("a.parquet", 4, 7)


def test_parse_judgment_recovers_whitespace_stall_after_substantive_fields() -> None:
    content = """{
      "language_quality": 4,
      "instruction_answer_coherence": 5,
      "grounding": 4,
      "training_value": 4,
      "complete": true,
      "usable_for_training": true


    """
    judgment, recovered = parse_judgment(content)
    assert recovered is True
    assert judgment["primary_problem"] == "none"
    assert judgment["usable_for_training"] is True


def test_parse_judgment_does_not_recover_missing_decisions() -> None:
    with pytest.raises(ValueError, match="complete"):
        parse_judgment(
            '{"language_quality": 4, "instruction_answer_coherence": 5, '
            '"grounding": 4, "training_value": 4'
        )
