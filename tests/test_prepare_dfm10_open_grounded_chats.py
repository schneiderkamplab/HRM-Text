import json
from pathlib import Path

from scripts.prepare_dfm10_open_grounded_chats import (
    atomic_shards,
    clean_wikipedia_article,
    openstax_candidates,
)


def test_wikipedia_cleanup_keeps_article_body_and_drops_reference_tail() -> None:
    text = """Fotosyntese

Fotosyntese omdanner lysenergi til kemisk energi i planter og andre organismer.

Processen bruger kuldioxid og vand og frigiver ilt.

Referencer

ISBN 978-0-00-000000-0
https://example.invalid/reference
"""
    title, paragraphs = clean_wikipedia_article(text) or (None, [])
    assert title == "Fotosyntese"
    assert "lysenergi" in "\n".join(paragraphs)
    assert "example.invalid" not in "\n".join(paragraphs)


def test_wikipedia_cleanup_rejects_list_pages() -> None:
    assert clean_wikipedia_article("Liste over emner\n\nEt langt afsnit.") is None


def test_openstax_requests_are_distinct_and_preserve_immutable_provenance(tmp_path: Path) -> None:
    passage = tmp_path / "passages.jsonl"
    row = {
        "artifact_sha256": "artifact-sha",
        "attribution": "OpenStax, Biology 2e, CC BY 4.0",
        "book_slug": "biology-2e",
        "book_title": "Biology 2e",
        "category": "biology",
        "document_id": "chapter-1",
        "evidence_url": "https://example.org/evidence",
        "immutable_ref": "sha256:artifact-sha",
        "license": "CC-BY-4.0",
        "local_provenance": {"path": "artifact.pdf"},
        "passage": "A sufficiently detailed licensed biology passage.",
        "passage_index": 3,
        "passage_sha256": "passage-sha",
        "source_url": "https://openstax.org/books/biology-2e",
    }
    passage.write_text(json.dumps(row) + "\n")

    focuses = [f"focus-{index}" for index in range(8)]
    requests = openstax_candidates(passage, focuses, "test-v1")

    assert len(requests) == 8
    assert len({request["request_id"] for request in requests}) == 8
    assert {request["conversation_focus"] for request in requests} == set(focuses)
    assert all(request["target_exchanges"] == "5-7" for request in requests)
    assert all(request["license"] == "CC-BY-4.0" for request in requests)
    assert all(request["provenance"]["immutable_ref"] == "sha256:artifact-sha" for request in requests)
    assert all(request["attribution"] == row["attribution"] for request in requests)


def test_atomic_shards_write_every_request_once(tmp_path: Path) -> None:
    rows = [
        {"request_id": f"{index:064x}", "value": index}
        for index in range(17)
    ]
    summary = atomic_shards(rows, tmp_path / "shards", shards=4)
    written = []
    for path in sorted((tmp_path / "shards").glob("part-*.jsonl")):
        written.extend(json.loads(line) for line in path.read_text().splitlines())

    assert summary["rows"] == 17
    assert sorted(row["value"] for row in written) == list(range(17))
