from scripts.prepare_openmathinstruct2_repair import answers_match, digest, last_boxed, normalized_answer
from scripts.score_openmathinstruct2_prm import solution_steps
from scripts.build_openmathinstruct2_repaired import normalized_cot, unbox_all


def test_nested_boxed_answer() -> None:
    assert last_boxed(r"Work. Therefore \boxed{\frac{1}{3}}.") == r"\frac{1}{3}"


def test_fast_answer_equivalence() -> None:
    matched, answer, mode = answers_match(r"\frac{1}{3}", r"Thus \boxed{\dfrac{1}{3}}.")
    assert matched
    assert answer == r"\dfrac{1}{3}"
    assert mode == "normalized_exact"


def test_hash_normalization() -> None:
    assert digest("A  problem\n") == digest("a problem")
    assert normalized_answer(" $ 4. $ ") == "4"


def test_solution_step_segmentation() -> None:
    assert solution_steps("First.\n\nSecond.\n\nFinal.") == ["First.", "Second.", "Final."]


def test_normalized_cot_has_one_box() -> None:
    result = normalized_cot(r"Try \boxed{3}, then conclude \boxed{4}.", "4")
    assert result.count(r"\boxed{") == 1
    assert result.endswith(r"\boxed{4}.")
    assert unbox_all(r"x=\boxed{\frac{1}{2}}") == r"x=\frac{1}{2}"


def test_normalized_cot_handles_unclosed_box() -> None:
    result = normalized_cot(
        r"Malformed \boxed{\begin{pmatrix} then conclude \boxed{4}.",
        r"\boxed{4}",
    )
    assert result.count(r"\boxed{") == 1
    assert result.endswith(r"\boxed{4}.")
