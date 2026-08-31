from pathlib import Path

from scripts.build_dolci_tool_use_tokenizer_staging import split_jsonl


def test_split_jsonl_preserves_every_line(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    source.write_text("".join(f'{{"row":{index}}}\n' for index in range(7)))
    output = tmp_path / "parts"
    output.mkdir()
    paths = split_jsonl(source, output, 30)
    assert [path.name for path in paths] == [
        "source.part-000.jsonl",
        "source.part-001.jsonl",
        "source.part-002.jsonl",
    ]
    assert "".join(path.read_text() for path in paths) == source.read_text()
    assert all(path.stat().st_size <= 30 for path in paths)


def test_split_jsonl_keeps_an_oversized_line_whole(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    source.write_bytes(b'{"long":"0123456789"}\n{"short":1}\n')
    output = tmp_path / "parts"
    output.mkdir()

    paths = split_jsonl(source, output, 10)

    assert [path.read_bytes() for path in paths] == [
        b'{"long":"0123456789"}\n',
        b'{"short":1}\n',
    ]
