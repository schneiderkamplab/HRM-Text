import copy
from collections import Counter
from pathlib import Path

import pytest
import yaml

from dfm12 import identity_repair_expansion as repair
from dfm12.io import file_hash, load, rows, write_json


@pytest.fixture(scope="module")
def compiled():
    return repair.compile_spec()


def test_counts_diversity_and_brief_targets(compiled):
    assert len(compiled) == 1100
    assert compiled == repair.compile_spec()
    d = repair.prior.diversity(compiled)
    for lang in ("da", "en"):
        assert d[lang]["train"]["conversations"] == 500
        assert d[lang]["heldout"]["conversations"] == 50
        assert d[lang]["train"]["turn_histogram"] == {1: 250, 2: 100, 3: 100, 4: 50}
        assert d[lang]["heldout"]["turn_histogram"] == {1: 25, 2: 10, 3: 10, 4: 5}
        assert d[lang]["train"]["opening_topics"]["from_scratch"] == 100
        assert d[lang]["train"]["unique_normalized_user_turns"] >= 350
        assert d[lang]["heldout"]["unique_normalized_user_turns"] >= 60
        assert len(d[lang]["train"]["request_counts"]) == 28
    for r, p in compiled:
        assert all(m["role"] in ("user", "assistant") for m in r["messages"])
        assert not any(p[k] for k in ("human_reviewed", "gpu_audited", "native_gold"))
        assert len(r["messages"]) // 2 <= 4


def test_fact_bindings_and_lineage_not_reset():
    spec = repair.read_spec()
    for lang in ("da", "en"):
        for mode in ("brief", "contrast"):
            bank = {key: r[mode][lang] for key, r in spec["requests"].items()}
            for name in ("Peter Schneider-Kamp", "Jacob Nielsen", "Lukas Galke Poech",
                         "Gianluca Barmina", "Annemette Brok Pirchert", "Kenneth Enevoldsen"):
                assert name in bank["roster"]
            assert "Kristoffer" not in bank["team"]
            assert "161" in bank["datasets"]
            assert "datasæt" in bank["datasets"] if lang == "da" else "dataset" in bank["datasets"]
            assert "32" in bank["depth32"] and "16" in bank["depth32"]
            assert "8" in bank["passes8"] and "6" in bank["passes8"] and "2" in bank["passes8"]
            assert "4096" in bank["context_tokens"] and "tokens" in bank["context_tokens"]
            assert "Gemma 4" in bank["tokenizer_source"]
            assert "checkpoint" in bank["continuation"]
            assert "ikke" in bank["continuation"] if lang == "da" else "not" in bank["continuation"]
            assert "tilfældig" in bank["continuation"] if lang == "da" else "random" in bank["continuation"]
    assert "checkpoint_continuation" in spec["requests"]["continuation"]["facts"]
    assert spec["requests"]["synthetic_weights"]["train"]["en"].startswith("If a model")
    assert "not the same as copying" in spec["requests"]["synthetic_weights"]["brief"]["en"]
    assert repair.base.file_hash(repair.base.FACTS) == repair.base.FACTS_SHA


def test_direct_variants_and_answer_polarity(compiled):
    spec = repair.read_spec()
    families = {f["id"]: f for f in spec["families"]}
    for row, p in compiled:
        family = families[p["family"]]
        if family["turns"] == 1:
            if p["variant"] == 0:
                assert row["messages"][0]["content"] == family[row["language"]]
            assert len(p["turn_references"][0]["requests"]) == (1 if p["variant"] < 2 else 2)
        for index, ref in enumerate(p["turn_references"]):
            for key, answer in zip(ref["requests"], row["messages"][2 * index + 1]["content"].split("\n\n")):
                assert answer.startswith(("No,", "Nej,")) == (spec["requests"][key]["polarity"] == "negative")


@pytest.mark.parametrize("edit,match", [
    (lambda s: s.update(profile="generic"), "facts/profile"),
    (lambda s: s["formats"]["brief"].update(extra="x"), "exactly da/en"),
    (lambda s: s["requests"]["scratch"]["brief"].update(extra="x"), "exactly da/en"),
    (lambda s: s["families"][0].update(extra="x"), "family keys"),
    (lambda s: s["requests"]["scratch"].update(facts=["unsupported"]), "fact references"),
    (lambda s: s["requests"]["scratch"]["brief"].update(en="No, Gemma."), "polarity"),
    (lambda s: s["requests"]["scratch"]["brief"].update(en="One. Two. Three."), "two-sentence"),
    (lambda s: s["families"].pop(), "family counts"),
    (lambda s: s["families"][0].update(turns=4), "turn histogram"),
    (lambda s: s["families"][-1].update(en=s["families"][0]["en"]), "question leakage"),
])
def test_invalid_spec(tmp_path, edit, match):
    spec = yaml.safe_load(repair.SPEC.read_text())
    edit(spec)
    path = tmp_path / "spec.yaml"
    path.write_text(yaml.safe_dump(spec, allow_unicode=True))
    with pytest.raises(ValueError, match=match):
        repair.compile_spec(path)


def test_actual_previous_lineage_and_question_separation(compiled):
    if not repair.PREVIOUS.exists():
        pytest.skip("local prior artifact unavailable")
    inherited, _ = repair.check_lineage(repair.PREVIOUS, compiled)
    assert len(inherited["da"][0]) == 1469
    assert len(inherited["en"][0]) == 1482
    for lang in ("da", "en"):
        assert len(inherited[lang][1]) == 50
    bad = copy.deepcopy(compiled)
    old = list(rows(repair.PREVIOUS / "heldout/en/test.jsonl.gz"))[0]
    r, p = next((r, p) for r, p in bad if r["language"] == "en" and p["split"] == "train")
    r["messages"][0]["content"] = old["messages"][0]["content"]
    with pytest.raises(ValueError, match="prior heldout/development"):
        repair.check_lineage(repair.PREVIOUS, bad)


@pytest.fixture
def built(tmp_path, monkeypatch):
    if not repair.PREVIOUS.exists():
        pytest.skip("local prior artifact unavailable")
    class FakeRenderer:
        def __init__(self, metadata):
            self.info = load(metadata)["tokenizer_info"]

        def __call__(self, messages):
            n = len(messages) // 2
            return dict(assistant_targets=n, rendered_tokens=20 * n, max_rendered_length=20)

    monkeypatch.setattr(repair.base, "NativeRenderer", FakeRenderer)
    root = tmp_path / "v3"
    repair.build(root)
    return root


def test_materialization_reconstruction_and_reproducibility(built):
    root = built
    m = load(root / "manifest.json")
    assert repair.verify(root)["valid"]
    assert m["prior_heldout_status"].startswith("development_")
    for lang, total in (("da", 1969), ("en", 1982)):
        merged = list(rows(root / m["languages"][lang]["input"]))
        test = list(rows(root / f"heldout/{lang}/test.jsonl.gz"))
        dev = list(rows(root / f"development/{lang}/previous-heldout.jsonl.gz"))
        assert len(merged) == total and len(test) == len(dev) == 50
        assert len(list(rows(root / f"curated/{lang}/train.jsonl.gz"))) == 500
        assert not {r["id"] for r in merged} & {r["id"] for r in test + dev}
    assert len(list((root / "inputs").rglob("*.gz"))) == 2
    assert Counter(p["split"] for p in rows(root / "metadata/provenance.jsonl.gz")) == {
        "train": 3951, "heldout": 100, "development": 100}
    with pytest.raises(FileExistsError):
        repair.build(root)
    other = root.with_name("repeat")
    repair.build(other)
    assert file_hash(other / "manifest.json") == file_hash(root / "manifest.json")


@pytest.mark.parametrize("target", ["seal", "artifact", "extra"])
def test_integrity_fail_closed(built, target):
    if target == "seal":
        write_json(built / "seal.json", {"manifest_sha256": "bad"})
    elif target == "artifact":
        next((built / "inputs").rglob("*.gz")).write_bytes(b"bad")
    else:
        (built / "inputs/leaked-development.jsonl").write_text("{}")
    with pytest.raises(ValueError):
        repair.verify(built)


def test_all_actual_native_renders(compiled):
    metadata = repair.ROOT / "data/sampled_dfm11/metadata.json"
    if not metadata.exists():
        pytest.skip("local tokenizer unavailable")
    renderer = repair.base.NativeRenderer(metadata)
    for row, _ in compiled:
        actual = renderer(row["messages"])
        assert actual["max_rendered_length"] <= 4096
        assert actual["assistant_targets"] == len(row["messages"]) // 2
    with pytest.raises(ValueError, match="oversized"):
        renderer([{"role": "user", "content": "Question " * 10000},
                  {"role": "assistant", "content": "Answer."}])
