from scripts.repair_danish_university_portals_bt import structural_reason, strict_pass


def test_structural_reason_rejects_incomplete_and_corrupt_targets() -> None:
    assert (
        structural_reason(
            "Forklar emnet",
            "Dette er en længere dansk sætning med relevant indhold, som slutter brat",
        )
        == "incomplete_ending"
    )
    assert structural_reason("Forklar emnet", "Dette\ter en ellers afsluttet sætning.") == "control_or_tab_corruption"
    assert (
        structural_reason(
            "Forklar emnet",
            "Dette har funktionsned -sættelser og rekrutte -ringsproblemer.",
        )
        == "repeated_broken_hyphenation"
    )


def test_structural_reason_retains_complete_answer() -> None:
    assert structural_reason("Forklar emnet", "Dette er en fuldstændig og selvstændig besvarelse.") is None


def test_strict_pass_requires_all_dimensions() -> None:
    row = {
        "judgment": {
            "usable_for_training": True,
            "language_quality": {"score": 5},
            "instruction_answer_coherence": {"score": 4},
            "training_value": {"score": 4},
        }
    }
    assert strict_pass(row)
    row["judgment"]["training_value"]["score"] = 3
    assert not strict_pass(row)
