from scripts.recover_danish_university_portals_incomplete import (
    bounded_continuation,
    combine_target_and_continuation,
    locate_target_end,
    normalize_pdf_layout,
)


def test_normalization_repairs_pdf_splits_but_preserves_suspended_compounds() -> None:
    text = "forsøgs- og kontrolgrupper med re -sultater og linje-\nskift"
    assert normalize_pdf_layout(text) == "forsøgs- og kontrolgrupper med resultater og linjeskift"


def test_locate_target_end_uses_exact_or_unique_suffix() -> None:
    source = "Indledning. Dette er den autoritative passage og dens fortsættelse."
    assert locate_target_end("Dette er den autoritative passage", source) == (45, "exact", 33)
    target = "En omskrevet begyndelse; den autoritative passage"
    end, method, anchor = locate_target_end(target, source) or (0, "", 0)
    assert source[:end].endswith("den autoritative passage")
    assert method == "unique_suffix"
    assert anchor >= 20


def test_continuation_skips_leading_footnotes() -> None:
    tail = """

135 Konkurrenceankenævnets afgørelse af 7. april 1999, j. nr. 1.

136 Arbejdsrettens afgørelse af 24. august 2007, sag 2.

hver enkelt person og afsluttes med en konkret vurdering.

Næste afsnit skal ikke med.
"""
    assert bounded_continuation(tail) == (
        "hver enkelt person og afsluttes med en konkret vurdering.",
        3,
    )


def test_continuation_does_not_stop_at_colon() -> None:
    tail = """

Som et eksempel:

Den næste passage leverer det eksempel, som sætningen lover.
"""
    assert bounded_continuation(tail) == (
        "Som et eksempel: Den næste passage leverer det eksempel, som sætningen lover.",
        1,
    )


def test_combine_repairs_word_split_at_old_boundary() -> None:
    assert combine_target_and_continuation("Fokusgrup-", "perne fortsætter.") == "Fokusgrupperne fortsætter."
