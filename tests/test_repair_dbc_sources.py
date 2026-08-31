from scripts.repair_dbc_sources import abstract_prompt, normalize, review_prompt, stable_variant, target_hash


def test_hash_normalizes_whitespace_and_case() -> None:
    assert target_hash("  An  ABSTRACT\n") == target_hash("an abstract")


def test_prompt_selection_is_stable_and_language_matched() -> None:
    assert stable_variant("row-1", 3) == stable_variant("row-1", 3)
    assert "Hamlet" in abstract_prompt("EN", "row-1", "Hamlet", "William Shakespeare")
    danish = abstract_prompt("DA", "row-2", "Hamlet", "William Shakespeare").lower()
    assert any(marker in danish for marker in ("hvad", "kort", "introduktion"))


def test_review_prompt_uses_human_readable_metadata() -> None:
    prompt = review_prompt("DA", "review-1", [("Bogen", "Forfatteren", "")])
    assert "Bogen" in prompt
    assert "Forfatteren" in prompt
    assert "work-of:" not in prompt


def test_normalize_collapses_whitespace() -> None:
    assert normalize(" a\n b  c ") == "a b c"
