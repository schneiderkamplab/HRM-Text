import json
from pathlib import Path

import pytest

from dfm12.audit_full import validate_sources
from dfm12.audit_gates import FILES
from dfm12.dala_completed_audit import isolated_output, prepare, validate_authorization, validate_client_limits
from dfm12.dala_integrate import conversations, integrate, snapshot
from dfm12.dala_verify import verify
from dfm12.io import file_hash, load, write_json
from tests.test_dfm12_dala_integrate import manifest, pair


def producer_fixture(root):
    base = root / "wiki/artifacts/six-language-expansion"
    runs = {l: "run" for l in ("pl", "is")}
    write_json(base / "current-run.json", {"run_id": "run", "language_runs": runs,
               "finalization": "wiki/artifacts/six-language-expansion/run/finalization.json"})
    final = {"status": "candidate_datasets_complete_require_linguistic_review", "language_runs": runs,
             "outputs": {}, "pairs": {}, "cross_dataset_isolation": "isolation.json"}
    isolation = {}
    write_json(base / "scale_v1/late-review-exclusions.json", {})
    for lang in runs:
        train = [pair(lang, identifier=lang, text="Good training " + lang)]
        held = [pair(lang, "test", "held-" + lang, "Good heldout " + lang)]
        if lang == "pl":
            train.append(pair(lang, identifier="raw-held-collision", text=held[0]["original"]))
        raw = root / "raw" / lang
        selected = root / "final" / lang
        for directory, tests in ((raw, held), (selected, [] if lang == "pl" else held)):
            directory.mkdir(parents=True)
            (directory / "documents.jsonl").write_text("".join(json.dumps(p) + "\n" for p in train + held))
            write_json(directory / "rules.json", {})
            m = manifest(lang)
            m.update(language=lang, schema_version="2", artifacts={}, splits={},
                     verification={"pairs": len(train) + len(tests), "exact_edit_reconstruction": True,
                                   "correction_roundtrip": True, "document_split_isolation": True})
            for split, values in (("train", train), ("test", tests), ("validation", [])):
                (directory / split).mkdir()
                (directory / split / "pairs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in values))
                m["splits"][split] = {"pairs": len(values)}
            for path in directory.rglob("*.json*"):
                m["artifacts"][str(path.relative_to(directory))] = {"bytes": path.stat().st_size, "sha256": file_hash(path)}
            if directory == selected:
                m["cross_dataset_isolation"] = {"input": str(raw.relative_to(root)),
                                               "input_manifest_sha256": file_hash(raw / "manifest.json")}
            write_json(directory / "manifest.json", m)
        write_json(base / f"run/{lang}-status.json", {"language": lang, "exit_code": 0, "output": str(raw.relative_to(root))})
        final["outputs"][lang] = str(selected.relative_to(root))
        final["pairs"][lang] = load(selected / "manifest.json")["verification"]["pairs"]
        isolation[lang] = {"retained_pairs": final["pairs"][lang], "output": final["outputs"][lang]}
    write_json(root / "isolation.json", isolation)
    write_json(base / "run/finalization.json", final)
    return base


@pytest.mark.parametrize("language", ["pl", "is"])
def test_native_standard_balanced_views_and_train_only(language):
    p = pair(language)
    views = list(conversations(p, manifest(language)["prompts"], "pin"))
    assert [r["messages"][-1]["content"] for r in views] == ["yes", "no", p["original"], p["original"]]
    assert all(r["language"] == language and r["provenance"]["split"] == "train" for r in views)
    with pytest.raises(ValueError):
        list(conversations(pair(language, "test"), manifest(language)["prompts"], "pin"))
    with pytest.raises(ValueError):
        list(conversations(p, manifest("nb")["prompts"], "pin"))


def test_final_snapshot_requires_terminal_and_ancestry(tmp_path):
    producer = tmp_path / "producer"
    base = producer_fixture(producer)
    path = base / "run/finalization.json"
    final = load(path)
    write_json(path, dict(final, status="waiting_for_builds"))
    with pytest.raises(ValueError, match="not complete"):
        snapshot(producer, tmp_path / "waiting", ("pl", "is"), True)
    write_json(path, final)
    selected = producer / "final/pl/manifest.json"
    m = load(selected)
    m["cross_dataset_isolation"]["input_manifest_sha256"] = "wrong"
    write_json(selected, m)
    with pytest.raises(ValueError, match="producer evidence"):
        snapshot(producer, tmp_path / "wrong", ("pl", "is"), True)


def test_limits_and_root_isolation(tmp_path):
    auth = {"max_client_concurrency_per_endpoint": 128, "max_preparation_workers": 2, "endpoints": ["one"]}
    validate_client_limits(auth, 128, 2, ["one"])
    for concurrency, workers, endpoints in [(129, 2, ["one"]), (128, 3, ["one"]), (128, 2, ["other"])]:
        with pytest.raises(ValueError):
            validate_client_limits(auth, concurrency, workers, endpoints)
    for output in (tmp_path, tmp_path / "parent", tmp_path / "parent/sub"):
        with pytest.raises(ValueError):
            isolated_output(output, [tmp_path / "parent"])
    with pytest.raises(ValueError, match="exactly one"):
        validate_sources([], "legacy", tmp_path, tmp_path, "generic")


def test_full_final_import_and_scoped_authorization(tmp_path, monkeypatch):
    monkeypatch.setenv("TOKENIZERS_PARALLELISM", "false")
    producer, output = tmp_path / "producer", tmp_path / "integration"
    base = producer_fixture(producer)
    integrate(producer, output, 1, ("pl", "is"), final_outputs=True)
    report = verify(output, ("pl", "is"))
    assert report["producer_finalized"] is True
    assert sum(report["counts"].values()) == 8
    assert load(output / "screening.json")["counts"]["pl"]["heldout_text_pairs"] == 1
    seed = output / "previous.sqlite"
    seed.write_bytes(b"fixture")
    write_json(output / "previous-screen.json", {"seed": str(seed), "seed_sha256": file_hash(seed), "inputs": {}})
    parent, swedish, audit, cross = [tmp_path / p for p in ("parent", "swedish", "audit", "cross")]
    for p in (parent, swedish):
        write_json(p / "sources.json", {"sources": []})
    write_json(parent / "operational-approval.json", {"fixture": True})
    write_json(parent / "configuration.json", {"endpoints": ["one"]})
    write_json(cross / "coverage.json", {"files": []})
    for name in FILES:
        (cross / name).write_text("")
    screen = cross / "audit-manifest.json"
    write_json(screen, {"snapshot_stable_at_finalization": True,
                       "coverage_sha256": file_hash(cross / "coverage.json"),
                       "outputs": {name: file_hash(cross / name) for name in FILES}})
    auth = prepare(output, audit, parent, swedish, screen, ["pl", "is"])
    sources = load(audit / "sources.json")["sources"]
    assert [s["component"] for s in sources[:2]] == ["dala-pl-acceptability", "dala-is-acceptability"]
    validate_sources(sources, output=audit, crossscreen=screen, dala_authorization=auth)
    with pytest.raises(ValueError, match="excluded"):
        validate_sources(sources)
    with pytest.raises(ValueError, match="components differ"):
        validate_authorization(sources[:2], auth, audit, screen)
    with pytest.raises(ValueError):
        validate_authorization(sources, auth, parent, screen)
    with pytest.raises(ValueError, match="already pinned"):
        prepare(output, audit, parent, swedish, screen, ["pl", "is"])
    exclusions = base / "scale_v1/late-review-exclusions.json"
    write_json(exclusions, {"pl": ["new"]})
    with pytest.raises(ValueError, match="Late exclusions changed"):
        validate_authorization(sources, auth, audit, screen)
    write_json(exclusions, {})
    raw_held = producer / "raw/pl/test/pairs.jsonl"
    raw_held.write_text("")
    with pytest.raises(ValueError, match="artifact changed"):
        validate_authorization(sources, auth, audit, screen)
