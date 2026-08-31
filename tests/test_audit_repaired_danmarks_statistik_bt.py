import scripts.audit_repaired_danmarks_statistik_bt as audit


def test_strict_usable_requires_no_named_problem() -> None:
    judgment = {
        "usable_for_training": True,
        "complete": True,
        "primary_problem": "none",
        "language_quality": 5,
        "instruction_answer_coherence": 4,
        "grounding": 4,
        "training_value": 4,
    }
    assert audit.strict_usable(judgment)
    judgment["primary_problem"] = "indirect_answer"
    assert not audit.strict_usable(judgment)


def test_strict_usable_requires_coherent_grounded_pair() -> None:
    judgment = {
        "usable_for_training": True,
        "complete": True,
        "primary_problem": "none",
        "language_quality": 5,
        "instruction_answer_coherence": 3,
        "grounding": 4,
        "training_value": 4,
    }
    assert not audit.strict_usable(judgment)
