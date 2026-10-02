import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from dfm12.io import digest, file_hash, load, rows, write_json
from dfm12.reordering_sources import blocks_for, dutch_blocks, GOVERNMENT, SourceRows


def para(name):
    return (name + " describes an ordinary historical building beside the river in the village. "
            "The building was carefully restored by several skilled local workers during the following year.")


def article(identity, parts):
    return {"id": identity, "title": "Article " + identity,
            "url": "https://nn.wikipedia.org/wiki/Article_" + identity, "text": "\n\n".join(parts)}


class Renderer:
    info = load("data/sampled_dfm11/metadata.json")["tokenizer_info"]
    def count(self, messages):
        return 500


def test_dutch_only_reviewed_single_newlines():
    row = {"text": "\n".join(para(x) for x in "ABC")}
    blocks = dutch_blocks(row, GOVERNMENT)
    assert len(blocks) == 3 and all(b["eligible"] for b in blocks)
    for b in blocks:
        assert row["text"][slice(*b["source_span"])] == b["text"]
    other = dutch_blocks(row, "data/wikiwijs/data.parquet")
    assert len(other) == 1 and not other[0]["eligible"]
    with pytest.raises(ValueError, match="unreviewed"):
        dutch_blocks(row, "invented")


def test_heading_stays_a_barrier():
    blocks = dutch_blocks({"text": para("A") + "\nHeading\n" + para("B") + "\n" + para("C")}, GOVERNMENT)
    assert [b["eligible"] for b in blocks] == [True, False, True, True]


def test_full_scan_receipts_native_preference_and_immutable_output(tmp_path):
    from dfm12.cpu_reordering_expand import scan_language
    path = tmp_path / "input.parquet"
    records = [article("1", [para(x) for x in "ABC"]),
               article("2", [" ".join(para(x) for x in "DEF")]),
               article("3", ["short fragment"])]
    pq.write_table(pa.Table.from_pylist(records), path, row_group_size=1)
    source = {"language": "nn", "repo": "test", "revision": "pinned", "file": "a.parquet",
              "path": str(path), "file_sha256": file_hash(path)}
    receipt = scan_language(tmp_path / "out", "nn", [source], Renderer(), 10)
    assert receipt["counts"]["scanned"] == 3
    assert receipt["candidate_counts"] == {"paragraph-reordering": 1, "text-block-reordering": 1}
    assert receipt["by_file"]["a.parquet"]["all_rows_scanned"]
    path_out = tmp_path / "out/candidates/nn/paragraph-reordering.jsonl"
    before = path_out.read_bytes()
    with pytest.raises(FileExistsError):
        scan_language(tmp_path / "out", "nn", [source], Renderer(), 10)
    assert path_out.read_bytes() == before
    source_rows = SourceRows([source], cache_groups=1)
    assert source_rows.get(dict(source, ordinal=2))[0] == records[2]
    with pytest.raises(ValueError, match="invalid_source_ordinal"):
        source_rows.get(dict(source, ordinal=3))


def test_source_cache_fails_on_changed_file(tmp_path):
    path = tmp_path / "input.parquet"
    pq.write_table(pa.Table.from_pylist([article("1", [para("A")])]), path)
    source = {"repo": "test", "revision": "pinned", "file": "a", "path": str(path), "file_sha256": "wrong"}
    with pytest.raises(ValueError, match="source_file_changed"):
        SourceRows([source]).get(dict(source, ordinal=0))


def test_transitive_late_bridge_retains_earliest_priority():
    from dfm12.reordering_integration import Equivalence
    e = Equivalence()
    assert e.add(["url:a", "answer:a"]) == 0
    assert e.add(["url:b", "answer:b"]) == 1
    assert e.add(["url:a", "answer:b"]) == 2
    assert [e.find(i) for i in range(3)] == [0, 0, 0]


def test_url_identity_normalizes_editions_spaces_and_encoding():
    from dfm12.reordering_integration import identity_keys
    a = {"id": "1", "language": "sv", "messages": [{"content": "answer A"}],
         "provenance": {"url": "https://sv.wikipedia.org/wiki/One%20Two"}}
    b = {"id": "2", "language": "sv", "messages": [{"content": "answer B"}],
         "provenance": {"url": "https://sv.wikipedia.org/wiki/One_Two"}}
    ka, kb = identity_keys(a, "source A"), identity_keys(b, "source B")
    assert set(ka) & set(kb)
    b["language"] = "nn"
    assert not set(ka) & set(identity_keys(b, "source B"))


def setup_source(tmp_path):
    from dfm12.structure_preserving import make_candidate
    from dfm12.sentence_blocks import fallback_candidate
    row = article("1", [" ".join(para(x) for x in "ABC"), para("D"), para("E")])
    path = tmp_path / "source.parquet"
    pq.write_table(pa.Table.from_pylist([row]), path)
    source = {"language": "nn", "repo": "test", "revision": "pin", "file": "a.parquet",
              "path": str(path), "file_sha256": file_hash(path)}
    provenance = {k: v for k, v in source.items() if k not in {"language", "path"}}
    provenance.update(source_id="1", ordinal=0, url=row["url"], source_text_hash=digest(row["text"]),
                      document_hash=digest(["nn", " ".join(row["text"].split())]))
    blocks = blocks_for(row, "nn", source["file"])
    native = make_candidate(blocks, "nn", provenance, Renderer())
    fallback = fallback_candidate(row["text"], "nn", provenance, Renderer(), runs=[blocks[0]["source_span"]])
    return source, row, blocks, native, fallback


def pool(tmp_path, name, candidate, priority):
    from dfm12.reordering_integration import input_entry
    directory = tmp_path / name
    directory.mkdir()
    path = directory / "candidates.jsonl"
    path.write_text(json.dumps(candidate) + "\n")
    write_json(directory / "receipt.json", {"sha256": file_hash(path)})
    return input_entry(path, candidate["task"], priority)


def test_integration_prioritizes_native_preserves_lineage_and_does_not_overwrite(tmp_path):
    from dfm12.reordering_integration import integrate
    source, row, blocks, native, fallback = setup_source(tmp_path)
    a = pool(tmp_path, "new-native", native, 5)
    b = pool(tmp_path, "old-native", native, 6)
    c = pool(tmp_path, "fallback", fallback, 0)
    originals = {e["path"]: file_hash(e["path"]) for e in [a, b, c]}
    output = tmp_path / "integrated"
    result = integrate(output, [c, b, a], [source], Renderer())
    assert result["counts"] == {"nn/paragraph-reordering": 1}
    assert sum(result["duplicates"].values()) == 2
    assert result["accepted"] == 0 and result["final_sampling"] is False
    kept = next(rows(output / "candidates/nn/paragraph-reordering.jsonl"))
    assert kept["id"] == native["id"] and kept["messages"] == native["messages"]
    assert kept["provenance"] == native["provenance"]
    duplicates = list(rows(output / "duplicates.jsonl"))
    assert all(d["winner_id"] == native["id"] for d in duplicates)
    assert all("provenance" in d and "origin" in d for d in duplicates)
    for path, sha in originals.items():
        assert file_hash(path) == sha
    from dfm12.verify_reordering_integration import verify
    checked = verify(output, Renderer())
    assert checked["counts"] == result["counts"]
    assert checked["cross_pool_exact_duplicates"] == 0
    path = output / "candidates/nn/paragraph-reordering.jsonl"
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="output_changed"):
        verify(output, Renderer())
    with pytest.raises(FileExistsError):
        integrate(output, [a], [source], Renderer())


def test_bad_legacy_candidate_is_quarantined_not_rewritten(tmp_path):
    from dfm12.reordering_integration import integrate
    source, row, blocks, native, _ = setup_source(tmp_path)
    native["messages"][1]["content"] = "Invented\n\nParagraph\n\nBoundaries"
    entry = pool(tmp_path, "bad", native, 1)
    result = integrate(tmp_path / "out", [entry], [source], Renderer())
    assert not result["counts"]
    quarantine = list(rows(tmp_path / "out/quarantine.jsonl"))
    assert len(quarantine) == 1 and quarantine[0]["reason"] == "original_target_mismatch"
    from dfm12.verify_reordering_integration import verify
    checked = verify(tmp_path / "out", Renderer())
    assert checked["counts"] == {} and checked["quarantined"] == 1


def test_replay_rejects_forged_spans_labels_and_oversized_render(tmp_path):
    import copy
    from dfm12.reordering_integration import validate_reordering
    source, row, blocks, native, fallback = setup_source(tmp_path)
    assert validate_reordering(native, row, blocks, Renderer()) == 500
    assert validate_reordering(fallback, row, blocks, Renderer()) == 500
    wrong = copy.deepcopy(fallback)
    wrong["provenance"]["block_selection"]["sentence_spans"][0] = [1, 2]
    with pytest.raises(ValueError, match="invalid_synthetic_spans"):
        validate_reordering(wrong, row, blocks, Renderer())
    wrong = copy.deepcopy(native)
    wrong["provenance"]["synthetic_boundaries"] = True
    with pytest.raises(ValueError, match="synthetic_mislabeled"):
        validate_reordering(wrong, row, blocks, Renderer())
    class Oversize(Renderer):
        def count(self, messages):
            return 4097
    with pytest.raises(ValueError, match="rendered_context"):
        validate_reordering(native, row, blocks, Oversize())
    from dfm12.reordering_integration import REVIEWED_EXCLUSIONS
    repo, revision, lang, source_id = next(iter(REVIEWED_EXCLUSIONS))
    native["language"] = lang
    native["provenance"].update(repo=repo, revision=revision, source_id=source_id)
    with pytest.raises(ValueError, match="reviewed_source_damage"):
        validate_reordering(native, row, blocks, Renderer())


def test_diagnostic_and_modified_inputs_are_rejected(tmp_path):
    from dfm12.reordering_integration import input_entry
    source, row, blocks, native, _ = setup_source(tmp_path)
    entry = pool(tmp_path, "pool", native, 1)
    path = tmp_path / "pool/candidates.jsonl"
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="checksum_mismatch"):
        input_entry(path, native["task"], 1)
    write_json(tmp_path / "pool/diagnostic-only.json", {"eligible_for_handoff": False})
    with pytest.raises(ValueError, match="diagnostic_pool"):
        input_entry(path, native["task"], 1)
