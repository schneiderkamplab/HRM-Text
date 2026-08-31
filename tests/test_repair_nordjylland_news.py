import argparse
from collections import Counter

from scripts import repair_nordjylland_news as repair


def args(**overrides):
    values = {
        "min_article_chars": 100,
        "min_summary_chars": 15,
        "max_summary_article_ratio": 0.60,
        "max_response_tokens": 256,
        "max_seq_len": 4096,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_prompt_accepts_grounded_headline_contract(monkeypatch) -> None:
    monkeypatch.setattr(repair, "encode_row", lambda *unused: (300, 20))
    article = "Aalborg Kommune åbner et nyt bibliotek på mandag. " * 4
    counts = Counter()
    row = repair.build_row(
        {"text": article, "summary": "Nyt bibliotek åbner i Aalborg"},
        7, args(), object(), object(), counts,
    )
    assert row is not None
    assert "informativ overskrift" in row["instruction"]
    assert row["source_row_index"] == 7


def test_rejects_exact_template_overflow(monkeypatch) -> None:
    monkeypatch.setattr(repair, "encode_row", lambda *unused: (4080, 30))
    counts = Counter()
    row = repair.build_row(
        {"text": "En fuld artikel. " * 20, "summary": "Et fuldstændigt resumé."},
        0, args(), object(), object(), counts,
    )
    assert row is None
    assert counts["context_too_long"] == 1


def test_rejects_dangling_target() -> None:
    assert not repair.is_complete_target("Nyheden handler om Aalborg og", 15)
    assert repair.is_complete_target("Nyheden handler om Aalborg", 15)


def test_cleaning_does_not_truncate() -> None:
    source = " Første linje.\r\n\r\n\r\nAnden\tlinje. "
    assert repair.clean_text(source) == "Første linje.\n\nAnden linje."
