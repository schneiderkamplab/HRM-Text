import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from dfm12.cpu_paragraph_repair import bounded_rows, prepare_component
from dfm12.io import digest, load, write_json
from dfm12.paragraph_repair import paragraph_window
from dfm12.transform import transform, window


def paragraphs():
    return [f"Paragraph {i} contains complete prose with enough words to represent a genuine source paragraph."
            for i in range(5)]


@pytest.mark.parametrize("separator", ["\n\n", "\r\n\r\n", "\n \t\n", "\u2029"])
def test_explicit_boundaries_contiguous_and_deterministic(separator):
    parts = paragraphs()
    result = paragraph_window(separator.join(parts), "seed")
    assert result == paragraph_window(separator.join(parts), "seed")
    text, meta = result
    start = meta["paragraph_start"]
    assert text.split("\n\n") == parts[start:start + 3]


def test_single_lines_require_source_opt_in():
    text = "\n".join(paragraphs())
    with pytest.raises(ValueError):
        paragraph_window(text, 1)
    assert len(paragraph_window(text, 1, single_lines=True)[0].split("\n\n")) == 3


@pytest.mark.parametrize("separator", [" ", "\\n", "\u2028"])
def test_never_invent_paragraph_boundaries(separator):
    with pytest.raises(ValueError):
        paragraph_window(separator.join(paragraphs()), 1)


def test_never_join_across_heading_or_truncate_oversized_paragraph():
    p = paragraphs()
    for barrier in ["A heading", "long " * 2000 + "."]:
        with pytest.raises(ValueError):
            paragraph_window("\n\n".join(p[:2] + [barrier] + p[2:4]), 1)
    with pytest.raises(ValueError):
        paragraph_window("\n\n".join([p[0]] * 3), 1)


def test_find_valid_run_after_oversized_block_and_avoid_tail_loss():
    text = "\n\n".join(["long " * 2000 + "."] + paragraphs()[:3])
    for seed in range(30):
        assert paragraph_window(text, seed)[0] == "\n\n".join(paragraphs()[:3])
    assert any(len(window(text, seed).split("\n\n")) < 3 for seed in range(30))


def test_wrapped_lines_are_not_paragraphs():
    text = "\n".join("a short line of text" for _ in range(20))
    with pytest.raises(ValueError):
        paragraph_window(text, 1, single_lines=True)


def test_bounded_reader_ordinals_and_budget(tmp_path):
    path = tmp_path / "test.parquet"
    pq.write_table(pa.Table.from_pylist([{"id": i} for i in range(100)]), path, row_group_size=10)
    result = list(bounded_rows(path, 13))
    assert len(result) == 13
    assert all(ordinal == row["id"] for ordinal, row in result)
    assert max(ordinal for ordinal, _ in result) >= 90


def test_isolated_preparation_preserves_legacy_outputs_and_ids(tmp_path):
    root, output = tmp_path / "legacy", tmp_path / "repair"
    relative = "data/test/data.parquet"
    source = dict(repo="test/source", revision="pinned", kind="documents", status="review",
                  review="required", language="nl", files=[relative])
    write_json(root / "sources.lock.json", {"sources": {"test": source}})
    write_json(root / "approvals/test.json", dict(revision="pinned", evidence="reviewed", files=[relative]))
    write_json(root / "cpu-preparation.json", {"test": {"download": "complete"}})
    write_json(root / "baselines.json", {"tasks": {"paragraph-reordering": {"target_per_language": 10}}})
    path = root / "downloads/test" / relative
    path.parent.mkdir(parents=True)
    text = "\n\n".join(paragraphs())
    pq.write_table(pa.Table.from_pylist([{"text": text, "id": "original"}]), path)
    legacy = root / "candidates/test/receipt.json"
    write_json(legacy, {"unchanged": True})

    class Renderer:
        info = {"test": True}
        def count(self, messages):
            return 100

    receipt = prepare_component(root, output, "test", Renderer(), {"seed": 42}, 10, 10)
    assert receipt["counts"] == {"nl": 1}
    row = json.loads((output / "candidates/test-paragraph-repair-v1/candidates.jsonl").read_text())
    assert row["task"] == "paragraph-reordering"
    assert row["provenance"]["ordinal"] == 0
    assert row["provenance"]["source_text_hash"] == digest(text)
    selected = row["messages"][-1]["content"]
    assert row["id"] == transform(selected, "nl", "paragraph-reordering", {}, 42)["id"]
    assert load(legacy) == {"unchanged": True}
    assert not (root / "jobs.sqlite").exists()
    with pytest.raises(FileExistsError):
        prepare_component(root, output, "test", Renderer(), {"seed": 42}, 10, 10)
