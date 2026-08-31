from scripts.decontaminate_mimir_grounded_500k_exact import (
    generated_units,
    normalize_exact,
    static_archive_rows,
)


def test_normalized_exact_ignores_case_punctuation_and_unicode_width() -> None:
    assert normalize_exact("Ｗhat—IS momentum?") == normalize_exact("what is momentum")


def test_mcq_units_include_question_stem() -> None:
    units = generated_units(
        "Which statement is correct?\nA. First\nB. Second\nC. Third\nD. Fourth\n"
        "Answer with exactly one option letter."
    )
    assert normalize_exact("Which statement is correct?") in units


def test_static_archive_rows(monkeypatch) -> None:
    import io
    import zipfile

    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("data/dev.jsonl", '{"goal": "test goal"}\n')

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return archive.getvalue()

    monkeypatch.setattr("urllib.request.urlopen", lambda _url: Response())
    rows, evidence = static_archive_rows({
        "archive_url": "https://example.test/piqa.zip",
        "archive_member": "data/dev.jsonl",
    })
    assert rows == [{"goal": "test goal"}]
    assert evidence["archive_member"] == "data/dev.jsonl"
    assert len(evidence["archive_sha256"]) == 64
