import argparse

from scripts import repair_govreport_summarization as repair


def args(**overrides):
    values = {
        "min_report_chars": 100,
        "min_summary_chars": 20,
        "max_summary_report_ratio": 0.5,
        "max_response_tokens": 100,
        "max_seq_len": 200,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_build_row_retains_complete_source_without_truncation(monkeypatch) -> None:
    monkeypatch.setattr(repair, "encode_row", lambda instruction, response: (100, 30))
    report = "A complete report sentence. " * 12
    summary = "A concise supported summary."
    stats = repair.FileStats(source="test")

    row = repair.build_row({"report": report, "summary": summary}, args(), stats)

    assert row is not None
    assert row["instruction"].endswith(repair.clean_text(report))
    assert row["response"] == summary
    assert stats.written == 0


def test_build_row_rejects_context_overflow(monkeypatch) -> None:
    monkeypatch.setattr(repair, "encode_row", lambda instruction, response: (190, 30))
    stats = repair.FileStats(source="test")
    row = repair.build_row(
        {"report": "Complete report. " * 20, "summary": "A complete supported summary."},
        args(),
        stats,
    )
    assert row is None
    assert stats.context_too_long == 1


def test_build_row_rejects_summary_larger_than_half_source(monkeypatch) -> None:
    monkeypatch.setattr(repair, "encode_row", lambda instruction, response: (100, 30))
    stats = repair.FileStats(source="test")
    row = repair.build_row(
        {"report": "R" * 100, "summary": "A complete but disproportionate summary. " * 2},
        args(),
        stats,
    )
    assert row is None
    assert stats.excessive_summary_ratio == 1


def test_build_row_rejects_incomplete_summary(monkeypatch) -> None:
    monkeypatch.setattr(repair, "encode_row", lambda instruction, response: (100, 30))
    stats = repair.FileStats(source="test")
    row = repair.build_row(
        {"report": "Complete report. " * 20, "summary": "This ends with and"},
        args(min_summary_chars=10),
        stats,
    )
    assert row is None
    assert stats.incomplete_summary == 1


def test_filter_cross_file_duplicates_keeps_first_occurrence() -> None:
    rows = [
        {"response": "First unique summary."},
        {"response": "Duplicate summary."},
        {"response": "Second unique summary."},
    ]
    seen = {repair.summary_digest("Duplicate summary.")}

    kept, removed = repair.filter_cross_file_duplicates(rows, seen)

    assert [row["response"] for row in kept] == [
        "First unique summary.",
        "Second unique summary.",
    ]
    assert removed == 1
