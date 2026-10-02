import xml.etree.ElementTree as ET

import pytest

from dfm12.structure_preserving import (make_candidate, prose, sparv_blocks,
                                       sparv_spacing, wikimedia_blocks)


def paragraph(name):
    return (name + " is a long example of an ordinary prose paragraph with enough words "
            "to pass the structural checks and preserve its original complete content.")


def article(parts, lang="nn"):
    return {"id": "123", "title": "Article", "url": f"https://{lang}.wikipedia.org/wiki/Article",
            "text": "\n\n".join(parts)}


class Renderer:
    def count(self, messages):
        return 100


def test_exact_spans_and_target():
    row = article([paragraph(x) for x in ["First", "Second", "Third"]])
    blocks = wikimedia_blocks(row, "nn")
    for block in blocks:
        start, end = block["source_span"]
        assert row["text"][start:end] == block["text"]
    result = make_candidate(blocks, "nn", {"document_hash": "abc"}, Renderer())
    assert result["messages"][1]["content"] == row["text"]
    assert result["task"] == "paragraph-reordering"
    assert result["rendered_tokens"] == 100


@pytest.mark.parametrize("barrier", ["Heading", "Heading\n" + paragraph("Fourth"),
                                    "* " + paragraph("List"), "x" * 6100])
def test_never_bridge_barrier(barrier):
    row = article([paragraph("First"), barrier, paragraph("Second"), paragraph("Third")])
    with pytest.raises(ValueError, match="no_contiguous"):
        make_candidate(wikimedia_blocks(row, "nn"), "nn", {"document_hash": "x"}, Renderer())


def test_flattened_and_duplicate_paragraphs_rejected():
    for parts in [[paragraph("First") * 5], [paragraph("First")] * 3]:
        with pytest.raises(ValueError, match="no_contiguous"):
            make_candidate(wikimedia_blocks(article(parts), "nn"), "nn", {"document_hash": "x"}, Renderer())


def test_edition_mismatch():
    with pytest.raises(ValueError, match="wrong_edition"):
        wikimedia_blocks(article([paragraph("First")], "no"), "nn")


@pytest.mark.parametrize("marker", ["\n", "\u2028", "\ufffd", "{{bad}}", "()"])
def test_ambiguous_or_corrupt_blocks(marker):
    assert not prose(paragraph("First") + marker + paragraph("Second"))


def test_actual_limit_even_if_renderer_does_not_enforce():
    class Oversize:
        def count(self, messages):
            return 4097
    with pytest.raises(ValueError, match="rendered_context"):
        make_candidate(wikimedia_blocks(article([paragraph(x) for x in "ABC"]), "nn"),
                       "nn", {"document_hash": "x"}, Oversize())


def test_observed_missing_template_values_and_bot_geography():
    assert not prose(paragraph("The temperature is  degrees and distance is  kilometers"))
    assert not prose(paragraph("The population is ."))
    row = article([paragraph("Terr\u00e4ngen runt orten")], "sv")
    with pytest.raises(ValueError, match="formulaic_bot"):
        wikimedia_blocks(row, "sv")


def test_sparv_explicit_paragraphs_and_spacing():
    root = ET.Element("text", {"url": "https://sv.wikipedia.org/wiki/Article", "_id": "a",
                               "permalink": "https://sv.wikipedia.org/wiki/?oldid=123"})
    for name in "ABC":
        p = ET.SubElement(root, "paragraph")
        s = ET.SubElement(p, "sentence")
        for word in paragraph(name).split():
            ET.SubElement(s, "token", {"_tail": r"\s"}).text = word
    blocks = sparv_blocks(root)
    assert [p["text"] for p in blocks] == [paragraph(x) for x in "ABC"]
    assert all(p["eligible"] for p in blocks)
    del next(root.iter("token")).attrib["_tail"]
    assert not sparv_blocks(root)[0]["eligible"]


def test_sparv_sentence_only_not_paragraphs():
    root = ET.fromstring('<text url="https://sv.wikipedia.org/wiki/A" _id="a" permalink="p"><sentence/></text>')
    with pytest.raises(ValueError, match="no_xml_paragraphs"):
        sparv_blocks(root)
    assert sparv_spacing(r"\s\n\t") == " \n\t"
    with pytest.raises(ValueError):
        sparv_spacing(r"\u0020")


def test_sparv_omitted_empty_attribute_means_punctuation_adjacency():
    root = ET.Element("text", {"url": "https://sv.wikipedia.org/wiki/Article", "_id": "a", "permalink": "p"})
    p = ET.SubElement(root, "paragraph")
    for word in paragraph("First").rstrip(".").split():
        ET.SubElement(p, "token", {"_tail": r"\s"}).text = word
    del p[-1].attrib["_tail"]
    ET.SubElement(p, "token", {"_tail": r"\n\n"}).text = "."
    assert sparv_blocks(root)[0]["text"] == paragraph("First")
    assert sparv_blocks(root)[0]["eligible"]


def test_real_training_renderer():
    from dfm12.io import load
    from dfm12.prepare import Renderer as TrainingRenderer
    renderer = TrainingRenderer(load("data/sampled_dfm11/metadata.json")["tokenizer_info"], 4096)
    row = article([paragraph(x) for x in "ABC"])
    result = make_candidate(wikimedia_blocks(row, "nn"), "nn", {"document_hash": "abc"}, renderer)
    assert 0 < result["rendered_tokens"] <= 4096


def test_isolated_cpu_receipt_and_no_overwrite(tmp_path, monkeypatch):
    import json
    import shutil
    import pyarrow as pa
    import pyarrow.parquet as pq
    from dfm12 import cpu_structure_preserving as cpu
    from dfm12.io import file_hash, load
    source = tmp_path / "source.parquet"
    row = article([paragraph(x) for x in "ABC"])
    pq.write_table(pa.Table.from_pylist([row]), source)
    inventory = [{"path": "20231101.nn/train-00000-of-00001.parquet", "lfs": {"oid": file_hash(source)}}]
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return inventory
    monkeypatch.setattr(cpu.requests, "get", lambda *a, **k: Response())
    def fetch(url, path, expected_hash):
        path.parent.mkdir(parents=True)
        shutil.copyfile(source, path)
        return {"sha256": file_hash(path)}
    monkeypatch.setattr(cpu, "fetch", fetch)
    renderer = Renderer()
    renderer.info = load("data/sampled_dfm11/metadata.json")["tokenizer_info"]
    root = tmp_path / "output"
    receipt = cpu.prepare_language(root, "nn", renderer, 100, 10)
    assert receipt["candidates"] == 1
    output = root / "candidates/nn/candidates.jsonl"
    before = output.read_bytes()
    assert receipt["sha256"] == file_hash(output)
    assert json.loads(before)["provenance"]["ordinal"] == 0
    with pytest.raises(FileExistsError):
        cpu.prepare_language(root, "nn", renderer, 100, 10)
    assert output.read_bytes() == before
