import json

import numpy as np
import pytest

from scripts.prepare_metadata_categories import FIELDS, prepare, sha256, validate_ranges
from scripts.prepare_metadata_categories import recover_dfm15, source_category, validate_conditioning


def fixture(tmp_path):
    data = tmp_path / "sample"
    epoch = data / "epoch_0"
    epoch.mkdir(parents=True)
    np.save(data / "tokens.npy", np.arange(40, dtype=np.int32))
    (data / "metadata.json").write_text("{}")
    rows = dict(inst_start=[20, 0, 10], inst_len=[2, 2, 0],
                resp_start=[22, 2, 10], resp_len=[3, 3, 4])
    for k, values in rows.items():
        np.save(epoch / (k + ".npy"), np.array(values, dtype=np.uint64))
    evidence = tmp_path / "source-receipt.json"
    evidence.write_text("{}")
    manifest = dict(provenance_status="verified", epoch=0, stored_tokens=40,
                    metadata_sha256=sha256(data / "metadata.json"),
                    index_sha256={k: sha256(epoch / (k + ".npy")) for k in FIELDS},
                    evidence=[dict(path=str(evidence), sha256=sha256(evidence))],
                    ranges=[dict(start=i*10, end=(i+1)*10, source=f"source-{i}",
                                 category=i, rationale="explicit test source")
                            for i in range(3)])
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return data, path, manifest


def test_exact_order_counts_and_immutable_publish(tmp_path):
    data, path, _ = fixture(tmp_path)
    before = {p: sha256(p) for p in data.rglob("*.npy")}
    r = prepare(data, path, tmp_path / "out", chunk_rows=1, publish=True)
    assert r["status"] == "verified" and r["published"]
    assert r["token_exposure"] == 14
    assert np.load(data / "epoch_0/category_id.npy").tolist() == [2, 0, 1]
    assert all(sha256(p) == h for p, h in before.items())
    with pytest.raises(FileExistsError):
        prepare(data, path, tmp_path / "again", publish=True)


@pytest.mark.parametrize("change", ["gap", "candidate", "hash", "cross_source"])
def test_fail_closed(tmp_path, change):
    data, path, m = fixture(tmp_path)
    if change == "gap":
        m["ranges"].pop()
    elif change == "candidate":
        m["provenance_status"] = "candidate"
    elif change == "hash":
        m["index_sha256"]["inst_start"] = "bad"
    else:
        np.save(data / "epoch_0/inst_start.npy", np.array([0, 0, 10], dtype=np.uint64))
        m["index_sha256"]["inst_start"] = sha256(data / "epoch_0/inst_start.npy")
    path.write_text(json.dumps(m))
    r = prepare(data, path, tmp_path / "out", publish=True)
    assert r["status"] == "blocked"
    assert not (tmp_path / "out/category_id.npy").exists()
    assert not (data / "epoch_0/category_id.npy").exists()


def test_range_validation(tmp_path):
    _, _, m = fixture(tmp_path)
    m["ranges"][1]["start"] = 9
    with pytest.raises(ValueError, match="Overlapping"):
        validate_ranges(m["ranges"], 40)
    m["ranges"][1]["start"] = 10.5
    with pytest.raises(ValueError, match="integers"):
        validate_ranges(m["ranges"], 40)


@pytest.mark.parametrize("value,message", [(-1, "Negative"), (40, "Out-of-bounds")])
def test_negative_and_out_of_bounds(tmp_path, value, message):
    data, path, _ = fixture(tmp_path)
    np.save(data / "epoch_0/resp_start.npy", np.array([value, 2, 10]))
    with pytest.raises(ValueError, match=message):
        prepare(data, path, tmp_path / "out")


def test_evidence_tamper(tmp_path):
    data, path, m = fixture(tmp_path)
    m["evidence"][0]["sha256"] = "bad"
    path.write_text(json.dumps(m))
    with pytest.raises(ValueError, match="Evidence hash"):
        prepare(data, path, tmp_path / "out")


@pytest.mark.parametrize("value,message", [(0, "Empty response"), (4098, "context")])
def test_invalid_lengths(tmp_path, value, message):
    data, path, _ = fixture(tmp_path)
    np.save(data / "epoch_0/resp_len.npy", np.array([value, 3, 4], dtype=np.uint64))
    with pytest.raises(ValueError, match=message):
        prepare(data, path, tmp_path / "out")


def test_input_mutation_prevents_publication(tmp_path, monkeypatch):
    import scripts.prepare_metadata_categories as module
    data, path, _ = fixture(tmp_path)
    original = module.assign

    def mutate(*args):
        (data / "metadata.json").write_text('{"changed": true}')
        return original(*args)

    monkeypatch.setattr(module, "assign", mutate)
    with pytest.raises(ValueError, match="Input changed"):
        prepare(data, path, tmp_path / "out", publish=True)
    assert not (data / "epoch_0/category_id.npy").exists()


def test_chunk_invariance(tmp_path):
    data, path, _ = fixture(tmp_path)
    a = prepare(data, path, tmp_path / "one", chunk_rows=1)
    b = prepare(data, path, tmp_path / "many", chunk_rows=100)
    assert a["index_sha256"] == b["index_sha256"]
    assert a["category_sha256"] == b["category_sha256"]


@pytest.mark.parametrize("name,category", [
    ("dfm14-da-synthetic-math-code-r1", 1),
    ("dfm11-toolace-native-tool-use-repaired__train", 1),
    ("allenai_tulu_3_personas_math__train:native", 1),
    ("dfm14_dala_v2_compact_ar_correction__part", 2),
    ("opus_da_en_repaired__part", 2),
    ("transformations-danish-english__part", 2),
    ("allenai_big_reasoning_traces__train", 0),
    ("dfm14-da-synthetic-openhermes-r1", 0),
    ("faroese-dyna-instruct__part-000000", 0),
])
def test_source_domain_policy(name, category):
    assert source_category(name)[0] == category


def test_recover_complete_assembly_and_detect_gap(tmp_path):
    from pathlib import Path

    def write(path, value):
        path = tmp_path / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        return path

    def tokens(path, n):
        path = tmp_path / path / "tokens.npy"
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path, np.zeros(n, dtype=np.int32))

    data = tmp_path / "incoming/x/data/sampled_dfm15"
    tokens("incoming/x/data/sampled_dfm15", 52)
    write("incoming/x/data/sampled_dfm15/metadata.json", {})
    tokens("data/tokenized_dfm11/math__train", 10)
    recon = Path("data/dfm14/inheritance-reconciliation")
    for version, base in [(12, 10), (13, 20), (14, 30)]:
        write(recon / f"sampled_dfm{version}/token-copy.json",
              dict(base_tokens=base, addition_tokens=10))
    inventory = [dict(part="chat__part", group="dfm12", tokens=10),
                 dict(part="mixed__part", group="dfm13", tokens=10)]
    inventory_path = write(recon / "component-inventory.json", inventory)
    tokens("source14", 10)
    write("config/dfm14_sources.json",
          dict(additions=[dict(name="summary", parts=[str(tmp_path / "source14")])]))
    native = Path("data/dfm15/native-reasoning-v2")
    write(native / "repairs.json", dict(parts=[
        dict(name="math__train", offset=0, tokens=10, new_tokens=2)]))
    write(native / "sampled_dfm15/token-copy.json", dict(base_tokens=40, tokens=42))
    tokens("source15", 5)
    registry = write("incoming/x/config/dfm15_sources.json", dict(additions=[
        dict(name="gsm-symbolic-en-train", tokens=5,
             parts=[dict(path="/work/dfm/HRM-Text/source15")])]))
    write("incoming/x/data/sampled_dfm15/validated.json",
          dict(registry_sha256=sha256(registry), stored_tokens=52))
    for name, start, end, new in [
        ("math-answer-conditioning", 47, 49, [47, 1, 48, 1]),
        ("math-answer-conditioning-v2", 49, 52, [49, 1, 50, 2]),
    ]:
        folder = Path("incoming/x/data/dfm15") / name
        write(folder / "before.json", dict(stored_tokens=start))
        write(folder / "preparation.json", dict(changed_unique=1))
        np.savez(tmp_path / folder / "mapping.npz",
                 old=np.array([[0, 1, 1, 1]], dtype=np.uint64),
                 new=np.array([new], dtype=np.uint64))
    write("incoming/x/data/dfm15/math-answer-conditioning-v2/source-ranges.json",
          [dict(name="math__train", start=0, end=10),
           dict(name="gsm-symbolic-en-train", start=42, end=47)])
    census = write("census.json", dict(dataset=str(data), epoch=0,
                   metadata_sha256=sha256(data / "metadata.json"), index_sha256={}))
    for path in ("data_io/sample_tokenized.py", "dfm14/reconcile_inheritance.py",
                 "dfm14/build.py", "dfm12/build_training.py", "dfm14/repair_reasoning.py",
                 "scripts/build_dfm15_full_sample.py", "scripts/condition_dfm15_math_answers.py"):
        write(path, {})
    manifest = tmp_path / "manifest.json"
    recover_dfm15(data, manifest, tmp_path, census)
    result = json.loads(manifest.read_text())
    assert result["provenance_status"] == "verified"
    ranges = result["ranges"]
    assert ranges[0]["start"] == 0 and ranges[-1]["end"] == 52
    assert all(a["end"] == b["start"] for a, b in zip(ranges, ranges[1:]))
    inventory[0]["tokens"] = 11
    inventory_path.write_text(json.dumps(inventory))
    with pytest.raises(ValueError, match="offset mismatch"):
        recover_dfm15(data, tmp_path / "bad.json", tmp_path, census)


def test_conditioning_rejects_gap_and_wrong_domain(tmp_path):
    path = tmp_path / "mapping.npz"
    r = [dict(start=0, end=10, category=0)]
    np.savez(path, old=np.array([[0, 1, 1, 1]], dtype=np.uint64),
             new=np.array([[10, 1, 11, 1]], dtype=np.uint64))
    with pytest.raises(ValueError, match="math source ownership"):
        validate_conditioning(path, r, 10, 12)
    with pytest.raises(ValueError, match="contiguous"):
        validate_conditioning(path, r, 11, 12)
