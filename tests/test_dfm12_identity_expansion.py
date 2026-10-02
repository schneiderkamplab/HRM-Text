import copy
from collections import Counter
from pathlib import Path
import re

import pytest
import yaml

from dfm12 import identity_expansion as exp
from dfm12.io import file_hash, load, rows, write_json


@pytest.fixture(scope="module")
def compiled():
    return exp.compile_spec()


def changed_spec(tmp_path, edit):
    spec = yaml.safe_load(exp.SPEC.read_text())
    edit(spec)
    path = tmp_path / "spec.yaml"
    path.write_text(yaml.safe_dump(spec, allow_unicode=True))
    return path


def test_counts_and_diversity(compiled):
    assert len(compiled) == 1100
    assert compiled == exp.compile_spec()
    summary = exp.diversity(compiled)
    for lang in ("da", "en"):
        for split in exp.EXPECTED:
            value = summary[lang][split]
            assert value["conversations"] == exp.EXPECTED[split]
            assert value["turn_histogram"] == exp.HISTOGRAM[split]
            assert value["families"] == exp.FAMILIES[split]
        assert len(summary[lang]["train"]["opening_topics"]) == 12
        assert len(summary[lang]["train"]["request_counts"]) == 29
        assert summary[lang]["train"]["unique_normalized_user_turns"] >= 350
        assert summary[lang]["train"]["unique_normalized_question_atoms"] >= 75
        assert summary[lang]["heldout"]["unique_normalized_user_turns"] >= 60
        assert summary[lang]["train"]["answer_modes"] == {"concise": 475, "detailed": 475}
    for row, p in compiled:
        assert not any(p[k] for k in ("human_reviewed", "gpu_audited", "native_gold"))
        assert all(m["role"] in ("user", "assistant") for m in row["messages"])


def test_direct_zero_one_and_substantive_branches(compiled):
    spec = exp.read_spec()
    for family in spec["families"]:
        if family["turns"] != 1:
            continue
        for lang in ("da", "en"):
            group = [(r, p) for r, p in compiled if p["family"] == family["id"] and r["language"] == lang]
            assert group[0][0]["messages"][0]["content"] == family[lang]
            for index, (row, p) in enumerate(group):
                refs = p["turn_references"]
                assert len(refs) == 1
                assert len(refs[0]["requests"]) == (1 if index < 2 else 2)
                assert refs[0]["mode"] == ("concise" if index % 2 == 0 else "detailed")
                if index == 1:
                    assert row["messages"][0]["content"].startswith(family[lang] + "\n\n")
            assert len({tuple(p["turn_references"][0]["requests"]) for _, p in group[2:]}) == len(group) - 2
    english = {r["messages"][0]["content"]: r["messages"][1]["content"]
               for r, p in compiled if r["language"] == "en" and p["variant"] == 0}
    assert "Kristoffer Nielbo" in english["Who leads DFM?"]
    assert english["Who leads your training team?"] == "My training team is led by Peter Schneider-Kamp."
    assert english["Is Kristoffer Nielbo training lead?"].startswith("No,")
    assert "Norse mythology" in english["Why was your particular name chosen?"]


def test_brevity_and_explicit_claims():
    spec = exp.read_spec()
    for request in spec["requests"].values():
        for lang in ("da", "en"):
            assert 1 <= len(re.findall(r"[.!?](?:\s|$)", request["concise"][lang])) <= 2
    for lang in ("da", "en"):
        assert "Gemma" in spec["requests"]["gemma_weights"]["concise"][lang]
        assert "16" in spec["requests"]["hardware"]["detailed"][lang]


def test_neutral_questions_and_polar_corrections(compiled):
    hits = Counter()
    for row, p in compiled:
        for index, ref in enumerate(p["turn_references"]):
            paragraphs = row["messages"][2 * index + 1]["content"].split("\n\n")
            for key, form, answer in zip(ref["requests"], ref["answer_forms"], paragraphs):
                if form == "neutral_concise":
                    assert not answer.startswith(("No,", "Nej,"))
                    assert answer[0].isupper()
                    hits[(row["language"], p["split"])] += 1
                elif form == "concise" and key in ("old_tokenizer", "context", "kristoffer", "gemma_weights"):
                    assert answer.startswith(("No,", "Nej,"))
    assert hits == {("da", "train"): 5, ("en", "train"): 5,
                    ("da", "heldout"): 3, ("en", "heldout"): 3}


@pytest.mark.parametrize("edit,match", [
    (lambda s: s["formats"]["concise"].update(bogus="x"), "exactly da/en"),
    (lambda s: s["requests"]["name"]["train"].update(bogus="x"), "exactly da/en"),
    (lambda s: s["requests"]["name"].update(bogus="x"), "unexpected request"),
    (lambda s: s["families"][0].update(bogus="x"), "unexpected family"),
    (lambda s: s.update(profile="generic"), "facts/profile"),
    (lambda s: s.update(facts_sha256="bad"), "facts/profile"),
    (lambda s: s["requests"]["name"].update(facts=["made_up"]), "fact references"),
    (lambda s: s["requests"]["members"]["concise"].update(en="Peter only"), "missing team"),
    (lambda s: s["requests"]["team_lead"]["detailed"].update(en="Kristoffer leads it"), "conflation"),
    (lambda s: s["requests"]["architecture"]["concise"].update(en="Eight layers"), "incomplete architecture"),
    (lambda s: s["requests"]["kristoffer"]["concise"].update(en="Maybe"), "explicit premise"),
    (lambda s: s["families"].pop(), "family split counts"),
    (lambda s: s["families"][0].update(turns=5), "invalid family"),
    (lambda s: s["families"][-1].update(en=s["families"][0]["en"]), "heldout normalized"),
])
def test_invalid_spec(tmp_path, edit, match):
    with pytest.raises(ValueError, match=match):
        exp.compile_spec(changed_spec(tmp_path, edit))


def test_split_isolation_and_permitted_train_repetition(compiled):
    for lang in ("da", "en"):
        train = [(r, p) for r, p in compiled if r["language"] == lang and p["split"] == "train"]
        test = [(r, p) for r, p in compiled if r["language"] == lang and p["split"] == "heldout"]
        a, b = exp.question_sets(train), exp.question_sets(test)
        assert not a[0] & b[0] and not a[1] & b[1]
        questions = [m["content"] for r, _ in train for m in r["messages"] if m["role"] == "user"]
        assert max(Counter(questions).values()) > 1
        exp.validate_compiled(compiled)


def test_original_overlap_including_unwrapped_atoms(compiled):
    row, p = next((r, p) for r, p in compiled if p["split"] == "heldout")
    original = copy.deepcopy(row)
    original["messages"][0]["content"] = p["turn_references"][0]["question_atoms"][0]
    original["messages"][1]["content"] = "Original answer."
    with pytest.raises(ValueError, match="heldout question"):
        exp.check_original([original], [(row, p)])
    train = next((r, p) for r, p in compiled if p["split"] == "train")
    with pytest.raises(ValueError, match="duplicates original"):
        exp.check_original([train[0]], [train])


@pytest.fixture
def built(tmp_path, monkeypatch):
    import dfm12.export_validator
    monkeypatch.setattr(dfm12.export_validator, "validate", lambda _: {"valid": True})
    metadata = tmp_path / "tokenizer-metadata.json"
    token_file, template = tmp_path / "tokenizer.json", tmp_path / "template.jinja"
    token_file.write_text("unit-test-only")
    template.write_text("unit-test-only")
    info = {"tokenizer_path": str(token_file), "chat_template_path": str(template)}
    write_json(metadata, {"tokenizer_info": info})

    class FakeRenderer:
        def __init__(self, _):
            self.info = info

        def __call__(self, messages):
            n = len(messages) // 2
            return {"assistant_targets": n, "rendered_tokens": n * 20, "max_rendered_length": 20}

    monkeypatch.setattr(exp.base, "NativeRenderer", FakeRenderer)
    exports = tmp_path / "exports"
    for lang in ("da", "en"):
        package = exports / f"dfm12-identity-xl-full-bp-{lang}"
        exp.base.write_rows(package / "data/train.jsonl.gz", [{
            "id": "original-" + lang, "language": lang,
            "messages": [{"role": "user", "content": "Original question " + lang},
                         {"role": "assistant", "content": "Original answer"}]}])
        write_json(package / "metadata/manifest.json", {
            "source": {"profile": "xl-full-bp", "facts_sha256": exp.base.FACTS_SHA},
            "data_files": [{"file": "data/train.jsonl.gz"}], "metadata_files": []})
    snapshots = {p: p.read_bytes() for p in exports.rglob("*") if p.is_file()}
    output = tmp_path / "expansion"
    exp.build(output, exports=exports, metadata=metadata)
    return output, snapshots, exports, metadata


def test_build_and_reproduction(built):
    output, snapshots, exports, metadata = built
    assert exp.verify(output)["valid"]
    assert all(p.read_bytes() == data for p, data in snapshots.items())
    m = load(output / "manifest.json")
    for lang in ("da", "en"):
        merged = list(rows(output / m["languages"][lang]["input"]))
        heldout = list(rows(output / f"heldout/{lang}/test.jsonl.gz"))
        assert len(merged) == 501 and len(heldout) == 50
        assert merged[0]["id"] == "original-" + lang
        assert not {r["id"] for r in merged} & {r["id"] for r in heldout}
        assert (output / f"review/{lang}-train.md").exists()
        assert m["languages"][lang]["counts"]["new_train"]["assistant_targets"] == 950
    assert len(list((output / "inputs").rglob("*.gz"))) == 2
    with pytest.raises(FileExistsError):
        exp.build(output, exports=exports, metadata=metadata)
    second = output.with_name("reproduced")
    exp.build(second, exports=exports, metadata=metadata)
    assert file_hash(output / "manifest.json") == file_hash(second / "manifest.json")


@pytest.mark.parametrize("target", ["source", "artifact", "manifest", "unlisted", "unsafe_path"])
def test_seal_and_sources(built, target):
    output, snapshots, _, _ = built
    if target == "source":
        next(iter(snapshots)).write_bytes(b"tamper")
    elif target == "artifact":
        next((output / "inputs").rglob("*.gz")).write_bytes(b"tamper")
    elif target == "manifest":
        with (output / "manifest.json").open("a") as handle:
            handle.write(" ")
    elif target == "unlisted":
        (output / "inputs/leaked-test.jsonl").write_text("{}")
    else:
        m = load(output / "manifest.json")
        m["files"][0]["path"] = "../outside"
        write_json(output / "manifest.json", m)
        write_json(output / "seal.json", {"manifest_sha256": file_hash(output / "manifest.json")})
    with pytest.raises(ValueError):
        exp.verify(output)


def test_actual_renderer_all_conversations_and_v1_integrity(compiled):
    metadata = exp.ROOT / "data/sampled_dfm11/metadata.json"
    if not metadata.exists():
        pytest.skip("local student tokenizer unavailable")
    renderer = exp.base.NativeRenderer(metadata)
    for row, _ in compiled:
        result = renderer(row["messages"])
        assert result["max_rendered_length"] <= 4096
        assert result["assistant_targets"] == len(row["messages"]) // 2
    v1 = exp.ROOT / "data/dfm12/identity-extension-da-en-20260926-v1"
    if v1.exists():
        assert exp.base.verify(v1)["manifest_sha256"] == "908e1c13fb7e69230f6fafddc30ef3500c3ba1332e7fc333dd6239899db1d3fc"
