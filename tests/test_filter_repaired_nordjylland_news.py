from scripts.filter_repaired_nordjylland_news import accepted


def judgment(**overrides):
    value = {
        "usable_for_training": True,
        "complete": True,
        "language_quality": 4,
        "instruction_answer_coherence": 4,
        "grounding": 4,
        "training_value": 4,
    }
    value.update(overrides)
    return value


def test_strict_acceptance_contract() -> None:
    assert accepted(judgment())
    assert not accepted(judgment(grounding=3))
    assert not accepted(judgment(complete=False))
    assert not accepted(judgment(usable_for_training=False))
