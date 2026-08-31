from scripts.filter_opus_da_en import classify_pair


def labels(*pairs: tuple[str, float]) -> tuple[list[str], list[float]]:
    return [f"__label__{name}" for name, _ in pairs], [score for _, score in pairs]


def classify(da: str, en: str, da_lid, en_lid, score: float):
    return classify_pair(
        da,
        en,
        *da_lid,
        *en_lid,
        score,
        min_alignment=0.60,
        wrong_language_confidence=0.70,
        max_length_ratio=3.0,
    )


def test_accepts_well_aligned_pair() -> None:
    result = classify(
        "Dette er en dansk sætning om vejret.",
        "This is a Danish sentence about the weather.",
        labels(("dan_Latn", 0.98), ("eng_Latn", 0.01)),
        labels(("eng_Latn", 0.99), ("dan_Latn", 0.01)),
        0.91,
    )
    assert result == (True, "accepted")


def test_rejects_swapped_direction() -> None:
    result = classify(
        "This side is clearly an English sentence.",
        "Denne side er tydeligvis en dansk sætning.",
        labels(("eng_Latn", 0.98), ("dan_Latn", 0.01)),
        labels(("dan_Latn", 0.99), ("eng_Latn", 0.01)),
        0.95,
    )
    assert result == (False, "swapped_direction")


def test_rejects_semantic_misalignment() -> None:
    result = classify(
        "Naturen bliver brugt meget intensivt.",
        "The committee approved the annual budget.",
        labels(("dan_Latn", 0.98), ("eng_Latn", 0.01)),
        labels(("eng_Latn", 0.99), ("dan_Latn", 0.01)),
        0.21,
    )
    assert result == (False, "semantic_misalignment")


def test_short_shared_name_is_not_rejected_by_language_id() -> None:
    result = classify(
        "København",
        "Copenhagen",
        labels(("eng_Latn", 0.55), ("dan_Latn", 0.20)),
        labels(("eng_Latn", 0.99), ("dan_Latn", 0.01)),
        0.83,
    )
    assert result == (True, "accepted")


def test_rejects_large_coverage_gap() -> None:
    result = classify(
        "Tabel nummer fire med en lang beskrivelse af forbrugeremner i organisationerne.",
        "Table four",
        labels(("dan_Latn", 0.98), ("eng_Latn", 0.01)),
        labels(("eng_Latn", 0.99), ("dan_Latn", 0.01)),
        0.71,
    )
    assert result == (False, "length_mismatch")


def test_rejects_confident_third_language_on_danish_side() -> None:
    result = classify(
        "Parque Nacional Huascarán",
        "Huascaran National Park",
        labels(("spa_Latn", 0.92), ("eng_Latn", 0.03), ("dan_Latn", 0.01)),
        labels(("eng_Latn", 0.99), ("dan_Latn", 0.01)),
        0.94,
    )
    assert result == (False, "danish_side_is_third_language")
