import copy
from pathlib import Path

import pytest
import yaml

from dfm12 import identity_extension as ext
from dfm12.io import file_hash, load, rows, write_json


def spec_copy(tmp_path, edit):
    data = yaml.safe_load(ext.SPEC.read_text())
    edit(data)
    path = tmp_path / "spec.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True))
    return path


def test_counts_splits_and_determinism():
    records = ext.compile_spec()
    assert records == ext.compile_spec()
    assert len(records) == 64
    for lang in ext.LANGUAGES:
        assert sum(r["language"] == lang and p["split"] == "train" for r, p in records) == 24
        assert sum(r["language"] == lang and p["split"] == "heldout" for r, p in records) == 8
    by_group = {}
    for row, provenance in records:
        by_group.setdefault(provenance["group"], set()).add(provenance["split"])
        assert not provenance["human_reviewed"] and not provenance["gpu_audited"]
        assert row["messages"][0]["role"] == "user"
        assert all(m["role"] != "system" for m in row["messages"])
    assert all(len(splits) == 1 for splits in by_group.values())
    assert any(len(r["messages"]) == 6 for r, _ in records)


def test_explicit_questions_and_brief_answers():
    records = ext.compile_spec()
    english = {r["messages"][0]["content"]: r for r, _ in records if r["language"] == "en"}
    assert "Kristoffer Nielbo" in english["Who leads DFM?"]["messages"][1]["content"]
    team = english["Who leads your training team?"]["messages"][1]["content"]
    assert "Peter Schneider-Kamp" in team and "Kristoffer" not in team
    correction = english["Is Kristoffer Nielbo training lead?"]["messages"][1]["content"]
    assert correction.startswith("No,") and "uninvolved" not in correction
    for row, provenance in records:
        for i, ref in enumerate(provenance["turn_references"]):
            if ref["answer"] == "namesake_short":
                assert len(row["messages"][2 * i + 1]["content"].split(". ")) <= 2


@pytest.mark.parametrize("edit,match", [
    (lambda s: s.update(profile="generic"), "facts/profile"),
    (lambda s: s.update(facts_sha256="0" * 64), "facts/profile"),
    (lambda s: s["cases"].append(copy.deepcopy(s["cases"][0])), "duplicate group"),
    (lambda s: s["cases"][-1]["turns"][0].update(en=s["cases"][0]["turns"][0]["en"]), "duplicate curated question"),
    (lambda s: s["answers"]["team"].update(en="Kristoffer and Peter"), "conflated"),
    (lambda s: s["answers"]["architecture"].update(en="Eight layers"), "incomplete XL"),
    (lambda s: s["answers"]["role_correction"].update(en="Maybe."), "explicit correction"),
    (lambda s: s["answers"]["name"].update(facts=["invented"]), "fact references"),
])
def test_reject_invalid_spec(tmp_path, edit, match):
    with pytest.raises(ValueError, match=match):
        ext.compile_spec(spec_copy(tmp_path, edit))


def test_original_overlap_policy():
    row, provenance = ext.compile_spec()[0]
    with pytest.raises(ValueError, match="duplicates original"):
        ext.check_overlap([row], [(row, provenance)])
    original = copy.deepcopy(row)
    original["messages"][1]["content"] = "Different original answer."
    assert len(ext.check_overlap([original], [(row, provenance)])) == 1
    with pytest.raises(ValueError, match="heldout question"):
        ext.check_overlap([original], [(row, dict(provenance, split="heldout"))])


@pytest.fixture
def built(tmp_path, monkeypatch):
    import dfm12.export_validator
    monkeypatch.setattr(dfm12.export_validator, "validate", lambda _: {"valid": True})
    metadata = tmp_path / "tokenizer-metadata.json"
    token_file = tmp_path / "tokenizer.json"
    template = tmp_path / "template.jinja"
    token_file.write_text("unit-test-only")
    template.write_text("unit-test-only")
    info = {"tokenizer_path": str(token_file), "chat_template_path": str(template)}
    write_json(metadata, {"tokenizer_info": info})

    class FakeRenderer:
        def __init__(self, _):
            self.info = info

        def __call__(self, messages):
            n = len(messages) // 2
            return {"assistant_targets": n, "rendered_tokens": n * 20,
                    "max_rendered_length": 20}

    monkeypatch.setattr(ext, "NativeRenderer", FakeRenderer)
    exports = tmp_path / "exports"
    for lang in ext.LANGUAGES:
        package = exports / f"dfm12-identity-xl-full-bp-{lang}"
        data = package / "data/train-00000.jsonl.gz"
        ext.write_rows(data, [{"id": "original-" + lang, "language": lang,
                              "messages": [{"role": "user", "content": "Original question " + lang},
                                           {"role": "assistant", "content": "Original answer"}]}])
        write_json(package / "metadata/manifest.json", {
            "source": {"profile": "xl-full-bp", "facts_sha256": ext.FACTS_SHA},
            "data_files": [{"file": "data/train-00000.jsonl.gz"}], "metadata_files": []})
    snapshots = {p: p.read_bytes() for p in exports.rglob("*") if p.is_file()}
    output = tmp_path / "extension"
    result = ext.build(output, exports=exports, metadata=metadata)
    return output, result, snapshots, exports, metadata


def test_build_merges_preserves_and_separates(built):
    output, result, snapshots, _, _ = built
    assert all(p.read_bytes() == content for p, content in snapshots.items())
    manifest = load(output / "manifest.json")
    assert ext.verify(output)["valid"]
    for lang in ext.LANGUAGES:
        merged = list(rows(output / manifest["languages"][lang]["input"]))
        heldout = list(rows(output / f"heldout/{lang}/test.jsonl.gz"))
        assert len(merged) == 25 and len(heldout) == 8
        assert merged[0]["id"] == "original-" + lang
        assert not {r["id"] for r in merged} & {r["id"] for r in heldout}
        assert result["languages"][lang]["counts"]["new_train"]["conversations"] == 24
    assert len(list((output / "inputs").rglob("*.gz"))) == 2


def test_no_overwrite_and_reproducible(built):
    output, _, _, exports, metadata = built
    with pytest.raises(FileExistsError):
        ext.build(output, exports=exports, metadata=metadata)
    second = output.with_name("second")
    ext.build(second, exports=exports, metadata=metadata)
    assert file_hash(output / "manifest.json") == file_hash(second / "manifest.json")


@pytest.mark.parametrize("target", ["artifact", "manifest", "source", "extra"])
def test_integrity_rejects_drift(built, target):
    output, _, snapshots, _, _ = built
    if target == "artifact":
        next((output / "inputs").rglob("*.gz")).write_bytes(b"corrupt")
    elif target == "manifest":
        with (output / "manifest.json").open("a") as handle:
            handle.write(" ")
    elif target == "source":
        next(iter(snapshots)).write_bytes(b"corrupt")
    else:
        (output / "inputs/accidental-heldout.jsonl").write_text("{}")
    with pytest.raises(ValueError):
        ext.verify(output)


def test_actual_student_renderer():
    metadata = ext.ROOT / "data/sampled_dfm11/metadata.json"
    if not metadata.exists():
        pytest.skip("local student tokenizer metadata unavailable")
    renderer = ext.NativeRenderer(metadata)
    for row, _ in ext.compile_spec():
        result = renderer(row["messages"])
        assert result["max_rendered_length"] <= 4096
        assert result["assistant_targets"] == len(row["messages"]) // 2
    with pytest.raises(ValueError, match="oversized"):
        renderer([{"role": "user", "content": "Question " * 10000},
                  {"role": "assistant", "content": "Answer."}])
