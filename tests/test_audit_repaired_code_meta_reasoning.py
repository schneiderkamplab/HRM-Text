import pytest

from scripts.audit_repaired_code_meta_reasoning import family_for_instruction
from scripts.repair_code_meta_reasoning import FAMILY_CONTRACTS


def test_classifies_each_repaired_contract() -> None:
    for family, contract in FAMILY_CONTRACTS.items():
        assert family_for_instruction(f"{contract}\n\nCoding problem:\nX") == family


def test_classifies_unit_test_context() -> None:
    assert (
        family_for_instruction(
            "You are a developer who must act as a meticulous reviewer.\nReview this code."
        )
        == "code_unit_test_walkthrough.txt"
    )


def test_rejects_unknown_instruction() -> None:
    with pytest.raises(ValueError):
        family_for_instruction("Solve this without a repaired task contract.")
