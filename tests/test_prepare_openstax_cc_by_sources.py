from pathlib import Path

from scripts.prepare_openstax_cc_by_sources import (
    PRIMARY,
    SUPPLEMENTAL,
    chunk_blocks,
    collection_metadata,
    extract_blocks,
    load_books,
)


def test_allowlist_matches_inventory() -> None:
    books = load_books(Path("docs/openstax_cc_by_inventory.csv"))
    assert len(books) == 61
    assert sum(len(slugs) for slugs in PRIMARY.values()) == 51
    assert len(SUPPLEMENTAL) == 10
    assert len({book.slug for book in books}) == 61


def test_collection_requires_book_level_metadata(tmp_path: Path) -> None:
    path = tmp_path / "book.collection.xml"
    path.write_text("""<?xml version="1.0"?>
<col:collection xmlns:col="http://cnx.rice.edu/collxml" xmlns:md="http://cnx.rice.edu/mdml">
  <metadata><md:slug>example-book</md:slug>
  <md:license url="http://creativecommons.org/licenses/by/4.0/">CC BY</md:license></metadata>
  <col:content><col:module document="m1"/></col:content>
</col:collection>""")
    assert collection_metadata(path) == (
        "example-book", "http://creativecommons.org/licenses/by/4.0/", ["m1"]
    )


def test_extract_blocks_drops_figures_and_media_attributions() -> None:
    title, blocks = extract_blocks(b"""<document xmlns="http://cnx.rice.edu/cnxml">
      <title>Useful section</title><content>
      <para>Grounding text.</para>
      <figure><media><image src="restricted.jpg"/></media>
      <caption>Third-party restricted caption.</caption></figure>
      <para>More grounding text.</para></content></document>""")
    assert title == "Useful section"
    assert "Grounding text." in blocks
    assert "More grounding text." in blocks
    assert not any("restricted" in block for block in blocks)


def test_extract_blocks_supports_archived_xhtml() -> None:
    title, blocks = extract_blocks(b"""<html xmlns="http://www.w3.org/1999/xhtml">
      <head><title>Archived page</title></head><body>
      <h1>Economic systems</h1><p>A sufficiently useful grounding paragraph.</p>
      </body></html>""")
    assert title == "Archived page"
    assert "Economic systems" in blocks
    assert "A sufficiently useful grounding paragraph." in blocks


def test_chunk_blocks_respects_size_and_minimum() -> None:
    chunks = chunk_blocks("Title", ["a" * 900, "b" * 900], 500, 1200)
    assert len(chunks) == 2
    assert all(500 <= len(chunk) <= 1200 for chunk in chunks)
